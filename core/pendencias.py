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

# Uma linha conta como pendente sempre que o campo PAGO não for exatamente
# "SIM" (cobre "NÃO", "EM ATRASO", "ACORDO", "PENDENTE" e também célula
# vazia — nesse último caso vale conferir manualmente antes de enviar).
STATUS_PAGO_OK = normalize("SIM")

PIX_EXIMIA = "✅ PIX: CPNJ: 655965130001-52 \nEXIMIA CAMARA DE CONCILIACAO MEDIACAO & ARBITRAGEM LTDA"
PIX_ELITE = "✅ PIX: CPNJ 51.673.385/0001-99\nELITE MEDIAÇÕES LTDA"

_RE_INTERVALO_DATAS = re.compile(r"(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s*-\s*(\d{1,2}/\d{1,2}(?:/\d{2,4})?)")


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
    df = load_data_sheets(path, REQUIRED_HEADERS, chave_duplicidade=CHAVE_DUPLICIDADE)
    if df.empty:
        raise ValueError(
            "Não encontrei nenhuma aba com as colunas 'EMPRESA', 'TIPO DE COBRANÇA' e "
            "'VALOR' (ou 'VALOR FALTANTE') nesta planilha. Verifique se é o arquivo de "
            "controle de pagamento/pendência correto."
        )
    return df


def listar_empresas(df: pd.DataFrame) -> List[str]:
    """Todas as empresas que aparecem na planilha, tenham pendência ou não."""
    col = _col(df, "EMPRESA")
    return sorted({str(v).strip() for v in df[col].dropna() if str(v).strip()})


def listar_empresas_com_pendencia(df: pd.DataFrame) -> List[str]:
    """Só as empresas que têm pelo menos uma linha pendente (PAGO diferente
    de 'SIM', valor válido e maior que zero) — usado para o menu da tela,
    já que não faz sentido listar quem não deve nada."""
    col_empresa = _col(df, "EMPRESA")
    col_valor = _col(df, "VALOR")
    col_pago = _col_optional(df, "PAGO")

    empresas: set = set()
    for _, row in df.iterrows():
        empresa = row.get(col_empresa)
        if empresa is None or not str(empresa).strip():
            continue
        if col_pago is not None and normalize(row.get(col_pago)) == STATUS_PAGO_OK:
            continue
        valor = row.get(col_valor)
        try:
            if valor is None or float(valor) <= 0:
                continue
        except (TypeError, ValueError):
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
        if col_pago is not None:
            pago_valor = row.get(col_pago)
            if normalize(pago_valor) == STATUS_PAGO_OK:
                continue  # já pago, não entra na cobrança
        tipo = row.get(col_tipo)
        valor = row.get(col_valor)
        if tipo is None or valor is None:
            continue
        try:
            valor_float = float(valor)
        except (TypeError, ValueError):
            continue
        if valor_float <= 0:
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
