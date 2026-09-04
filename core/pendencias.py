"""Fluxo de PENDÊNCIAS: lê a planilha de controle de pagamento (só a ELITE
tem) e monta a mensagem de cobrança pronta para colar no WhatsApp.

Cada linha pendente é classificada automaticamente por quem cobra:
- Tipo de cobrança com "AUDIÊNCIA" no texto -> cobrança da EXIMIA.
- Qualquer outro tipo (LAUDOS, MENSALIDADE, etc.) -> cobrança da ELITE.

Se a empresa tiver pendência dos dois tipos ao mesmo tempo, geramos duas
mensagens separadas (uma para cada PIX/empresa cobradora).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from core.excel_reader import load_data_sheets
from core.utils import format_brl, normalize

REQUIRED_HEADERS = ["EMPRESA", "TIPO DE COBRANÇA", "VALOR"]
CHAVE_DUPLICIDADE = ["DATA", "EMPRESA", "TIPO DE COBRANÇA", "VALOR"]

# Quando a mesma cobrança (mesma data + empresa + tipo + valor) aparece
# duas vezes na planilha — comum quando uma aba antiga (ex: "2025") e uma
# aba nova ("2026") guardam o mesmo lançamento — precisamos ficar com a
# linha que tem a informação de pagamento mais definitiva, não com
# "a primeira que aparecer no arquivo". Sem isso, uma linha antiga sem o
# campo PAGO preenchido podia vencer uma linha marcada "SIM" e a cobrança
# aparecia como pendente mesmo já paga.
_PRIORIDADE_PAGO = {"SIM": 0}  # tudo que não é SIM cai no default (1); vazio cai em 2

# Uma linha só conta como pendente quando o campo PAGO tem um status
# explícito diferente de "SIM" (cobre "NÃO", "EM ATRASO", "ACORDO",
# "PENDENTE", "VERIFICAR", etc.). Célula vazia NÃO conta como pendente —
# normalmente é um lançamento antigo que nunca chegou a ser marcado, não
# uma cobrança em aberto de verdade.
STATUS_PAGO_OK = normalize("SIM")


def _e_pendente(pago_valor) -> bool:
    if pago_valor is None or (isinstance(pago_valor, float) and pd.isna(pago_valor)):
        return False
    texto = normalize(pago_valor)
    if not texto:
        return False
    return texto != STATUS_PAGO_OK

PIX_EXIMIA = "✅ PIX: CPNJ: 655965130001-52 \nEXIMIA CAMARA DE CONCILIACAO MEDIACAO & ARBITRAGEM LTDA"
PIX_ELITE = "✅ PIX: CPNJ 51.673.385/0001-99\nELITE MEDIAÇÕES LTDA"

_RE_INTERVALO_DATAS = re.compile(r"(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s*-\s*(\d{1,2}/\d{1,2}(?:/\d{2,4})?)")


def _parse_valor(valor) -> Optional[float]:
    """Converte o valor da célula em número, mesmo quando foi digitado como
    texto (ex: 'R$ 3.200,00' em vez de 3200) — evita perder a linha da
    pendência só porque alguém formatou o valor na mão."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        if isinstance(valor, float) and pd.isna(valor):
            return None
        return float(valor)
    texto = str(valor).strip()
    if not texto:
        return None
    texto = texto.replace("R$", "").replace("r$", "").strip()
    texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


@dataclass
class ItemPendencia:
    descricao: str
    valor: float


@dataclass
class MensagemPendencia:
    empresa: str
    cobrador: str  # "EXIMIA" ou "ELITE"
    itens: List[ItemPendencia] = field(default_factory=list)
    total: float = 0.0


def carregar_planilha(path: str) -> pd.DataFrame:
    # Não passamos chave_duplicidade aqui de propósito: o dedup genérico do
    # excel_reader mantém "a primeira linha que aparecer", sem olhar pra
    # coluna PAGO — poderia descartar justo a linha com a confirmação de
    # pagamento e ficar com uma linha antiga em branco. Quem decide qual
    # linha vence, aqui, é _resolver_lancamentos_duplicados (mais abaixo).
    df = load_data_sheets(path, REQUIRED_HEADERS)
    if df.empty:
        raise ValueError(
            "Não encontrei nenhuma aba com as colunas 'EMPRESA', 'TIPO DE COBRANÇA' e "
            "'VALOR' (ou 'VALOR FALTANTE') nesta planilha. Verifique se é o arquivo de "
            "controle de pagamento/pendência correto."
        )
    return _resolver_lancamentos_duplicados(df)


def _resolver_lancamentos_duplicados(df: pd.DataFrame) -> pd.DataFrame:
    """Quando data+empresa+tipo+valor se repetem (o mesmo lançamento
    guardado em duas abas), mantém só a linha com o status de PAGO mais
    definitivo — 'SIM' sempre vence, célula vazia sempre perde."""
    col_pago = _col_optional(df, "PAGO")
    if col_pago is None:
        return df

    colunas_chave = [_col_optional(df, c) for c in CHAVE_DUPLICIDADE]
    colunas_chave = [c for c in colunas_chave if c is not None]
    if not colunas_chave:
        return df

    def _prioridade(v) -> int:
        if v is None or (isinstance(v, float) and pd.isna(v)) or not str(v).strip():
            return 2  # célula vazia: menos confiável, perde em caso de empate
        return _PRIORIDADE_PAGO.get(normalize(v), 1)

    prioridade = df[col_pago].apply(_prioridade)
    df = df.assign(_prioridade_pago=prioridade)
    df = df.sort_values("_prioridade_pago", kind="stable")
    df = df.drop_duplicates(subset=colunas_chave, keep="first")
    return df.drop(columns="_prioridade_pago").reset_index(drop=True)


def listar_empresas(df: pd.DataFrame) -> List[str]:
    """Todas as empresas que aparecem na planilha, tenham pendência ou não."""
    col = _col(df, "EMPRESA")
    return sorted({str(v).strip() for v in df[col].dropna() if str(v).strip()})


def listar_empresas_com_pendencia(df: pd.DataFrame) -> List[str]:
    """Só as empresas que têm pelo menos uma linha pendente (PAGO com um
    status explícito diferente de 'SIM', valor válido e maior que zero) —
    usado para o menu da tela, já que não faz sentido listar quem não
    deve nada."""
    col_empresa = _col(df, "EMPRESA")
    col_valor = _col(df, "VALOR")
    col_pago = _col_optional(df, "PAGO")

    empresas: set = set()
    for _, row in df.iterrows():
        empresa = row.get(col_empresa)
        if empresa is None or not str(empresa).strip():
            continue
        if col_pago is None or not _e_pendente(row.get(col_pago)):
            continue
        valor = _parse_valor(row.get(col_valor))
        if valor is None or valor <= 0:
            continue
        empresas.add(str(empresa).strip())
    return sorted(empresas)


def _col(df: pd.DataFrame, nome: str) -> str:
    for c in df.columns:
        if normalize(c) == normalize(nome):
            return c
    raise KeyError(f"Coluna '{nome}' não encontrada na planilha. Colunas disponíveis: {list(df.columns)}")


def _col_optional(df: pd.DataFrame, nome: str) -> Optional[str]:
    try:
        return _col(df, nome)
    except KeyError:
        return None


def _classificar_cobrador(tipo_cobranca: str) -> str:
    return "EXIMIA" if "AUDIENCIA" in normalize(tipo_cobranca) else "ELITE"


def _formatar_descricao(tipo_cobranca: str) -> str:
    """Deixa o texto do tipo de cobrança pronto para a mensagem: tira
    espaços extras e troca 'DD/MM - DD/MM' por 'DD/MM à DD/MM' (só quando
    for mesmo um intervalo de datas, para não mexer em textos como
    'MENSALIDADE PROCESSUAL')."""
    texto = " ".join(str(tipo_cobranca).split())
    return _RE_INTERVALO_DATAS.sub(r"\1 à \2", texto)


def gerar_mensagens(df: pd.DataFrame, empresa: str) -> List[MensagemPendencia]:
    """Retorna uma mensagem por cobrador (EXIMIA/ELITE) que tiver alguma
    pendência dessa empresa. Lista vazia = nenhuma pendência encontrada."""
    col_empresa = _col(df, "EMPRESA")
    col_tipo = _col(df, "TIPO DE COBRANÇA")
    col_valor = _col(df, "VALOR")
    col_pago = _col_optional(df, "PAGO")

    alvo_empresa = normalize(empresa)
    empresas_disponiveis = {normalize(v) for v in df[col_empresa].dropna()}
    if alvo_empresa not in empresas_disponiveis:
        raise ValueError(
            f"A empresa '{empresa}' não foi encontrada na planilha. "
            f"Confira o nome exato (empresas disponíveis: "
            f"{', '.join(sorted({str(v).strip() for v in df[col_empresa].dropna()}))[:500]})."
        )

    por_cobrador: Dict[str, MensagemPendencia] = {}

    for _, row in df.iterrows():
        if normalize(row.get(col_empresa)) != alvo_empresa:
            continue
        if col_pago is None or not _e_pendente(row.get(col_pago)):
            continue  # já pago, sem status marcado, ou sem coluna PAGO — não entra na cobrança
        tipo = row.get(col_tipo)
        valor_float = _parse_valor(row.get(col_valor))
        if tipo is None or valor_float is None or valor_float <= 0:
            continue

        cobrador = _classificar_cobrador(tipo)
        msg = por_cobrador.setdefault(cobrador, MensagemPendencia(empresa=empresa.strip(), cobrador=cobrador))
        msg.itens.append(ItemPendencia(descricao=_formatar_descricao(tipo), valor=valor_float))
        msg.total += valor_float

    # ordem estável: EXIMIA antes de ELITE, só por consistência na tela
    return [por_cobrador[c] for c in ("EXIMIA", "ELITE") if c in por_cobrador]


def formatar_texto(msg: MensagemPendencia) -> str:
    linhas = [
        "Bom dia, tudo bem?!",
        "Notamos que possuem alguns pagamentos pendentes!",
        "Segue mais informações e forma de pagamento:",
        "",
        "Pendências:",
    ]
    for item in msg.itens:
        linhas.append(f"- {item.descricao} - {format_brl(item.valor)}")
    linhas.append("")
    linhas.append(f"Total Pendente: {format_brl(msg.total)}")
    linhas.append("")
    linhas.append(PIX_EXIMIA if msg.cobrador == "EXIMIA" else PIX_ELITE)
    return "\n".join(linhas)
