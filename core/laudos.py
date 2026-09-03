"""Regras do fluxo de LAUDOS: filtro por período (dia 20 a dia 20), empresa
e status, cálculo de valores e montagem do texto final do relatório."""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

import pandas as pd

from core.config_store import get_valor_laudo
from core.excel_reader import load_data_sheets
from core.utils import format_brl, normalize, parse_date_cell

STATUS_MAP = {
    "SOLICITACAO": "SOLICITAÇÃO",
    "SOLICITAÇÃO": "SOLICITAÇÃO",
    "CORRIGIDO": "CORREÇÃO",
    "CORRECAO": "CORREÇÃO",
    "CORREÇÃO": "CORREÇÃO",
}

# Cobrança padrão: solicitação e correção contam juntas no relatório
# (laudos "Cancelado" continuam de fora, mesmo nesse modo).
STATUS_AMBOS = "AMBOS"
STATUS_VALIDOS = {"SOLICITAÇÃO", "CORREÇÃO"}
OPCOES_STATUS = ["Solicitação + Corrigido (cobrança)", "Somente Solicitação", "Somente Corrigido"]
STATUS_OPCAO_MAP = {
    normalize(OPCOES_STATUS[0]): STATUS_AMBOS,
    normalize(OPCOES_STATUS[1]): "SOLICITAÇÃO",
    normalize(OPCOES_STATUS[2]): "CORREÇÃO",
}

REQUIRED_HEADERS = ["EMPRESA", "TIPO DE LAUDO", "DATA"]
# Identifica um laudo de verdade (evita perder registros por causa de
# colunas secundárias como observação/entrega vindas diferentes entre abas).
CHAVE_DUPLICIDADE = ["DATA", "NOME DO CLIENTE", "EMPRESA", "TIPO DE LAUDO"]


@dataclass
class LaudosResult:
    empresa: str
    cnpj: Optional[str]
    periodo_ini: date
    periodo_fim: date
    status: str
    linhas: pd.DataFrame  # colunas: DATA, CLIENTE, TIPO, VALOR
    tipos_sem_valor: List[str] = field(default_factory=list)
    total: float = 0.0


def periodo_20_a_20(ano: int, mes: int) -> Tuple[date, date]:
    """Constrói o período padrão de laudos: dia 21 do mês informado até
    dia 20 do mês seguinte (ambas as pontas incluídas)."""
    ini = date(ano, mes, 21)
    if mes == 12:
        prox_ano, prox_mes = ano + 1, 1
    else:
        prox_ano, prox_mes = ano, mes + 1
    fim = date(prox_ano, prox_mes, 20)
    return ini, fim


def carregar_planilha(path: str) -> pd.DataFrame:
    df = load_data_sheets(path, REQUIRED_HEADERS, chave_duplicidade=CHAVE_DUPLICIDADE)
    if df.empty:
        raise ValueError(
            "Não encontrei nenhuma aba com as colunas 'EMPRESA' e 'TIPO DE LAUDO' "
            "nesta planilha. Verifique se o arquivo é o correto."
        )
    return df


def listar_empresas(df: pd.DataFrame) -> List[str]:
    col = _col(df, "EMPRESA")
    valores = sorted({str(v).strip() for v in df[col].dropna() if str(v).strip()})
    return valores


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


def gerar_relatorio(
    df: pd.DataFrame,
    config: Dict,
    empresa: str,
    periodo_ini: date,
    periodo_fim: date,
    status: str,
    cnpj: Optional[str] = None,
) -> LaudosResult:
    col_empresa = _col(df, "EMPRESA")
    col_tipo = _col(df, "TIPO DE LAUDO")
    col_data = _col(df, "DATA")
    col_cliente = _col_optional(df, "NOME DO CLIENTE") or _col_optional(df, "CLIENTE")
    col_status = _col_optional(df, "ENTRADA DE LAUDO") or _col_optional(df, "STATUS")

    alvo_empresa = normalize(empresa)
    status_key = normalize(status)
    if status_key in STATUS_OPCAO_MAP:
        status_normalizado = STATUS_OPCAO_MAP[status_key]
    elif status_key in {normalize("Ambos"), normalize("Solicitação + Corrigido")}:
        status_normalizado = STATUS_AMBOS
    else:
        status_normalizado = STATUS_MAP.get(status_key, status_key)

    empresas_disponiveis = {normalize(v) for v in df[col_empresa].dropna()}
    if alvo_empresa not in empresas_disponiveis:
        raise ValueError(
            f"A empresa '{empresa}' não foi encontrada na planilha. "
            f"Confira o nome exato (empresas disponíveis: "
            f"{', '.join(sorted({str(v).strip() for v in df[col_empresa].dropna()}))[:500]})."
        )

    linhas = []
    tipos_sem_valor: set = set()

    for _, row in df.iterrows():
        if normalize(row.get(col_empresa)) != alvo_empresa:
            continue
        data_val = parse_date_cell(row.get(col_data))
        if data_val is None or not (periodo_ini <= data_val <= periodo_fim):
            continue
        if col_status is not None:
            status_linha = STATUS_MAP.get(normalize(row.get(col_status)), normalize(row.get(col_status)))
            if status_normalizado == STATUS_AMBOS:
                if status_linha not in STATUS_VALIDOS:  # exclui Cancelado/vazio
                    continue
            elif status_linha != status_normalizado:
                continue
        tipo = str(row.get(col_tipo)).strip() if row.get(col_tipo) is not None else ""
        if not tipo:
            continue
        valor = get_valor_laudo(config, tipo)
        if valor is None:
            tipos_sem_valor.add(tipo)
            valor = 0.0
        cliente = str(row.get(col_cliente)).strip() if col_cliente and row.get(col_cliente) is not None else ""
        linhas.append({"DATA": data_val, "CLIENTE": cliente, "TIPO": tipo.upper(), "VALOR": valor})

    linhas_df = pd.DataFrame(linhas, columns=["DATA", "CLIENTE", "TIPO", "VALOR"])
    if not linhas_df.empty:
        linhas_df = linhas_df.sort_values("CLIENTE", key=lambda s: s.map(normalize)).reset_index(drop=True)

    total = float(linhas_df["VALOR"].sum()) if not linhas_df.empty else 0.0

    status_label = {
        STATUS_AMBOS: "Solicitação + Corrigido",
        "SOLICITAÇÃO": "Solicitação",
        "CORREÇÃO": "Corrigido",
    }.get(status_normalizado, status_normalizado)

    return LaudosResult(
        empresa=empresa.strip(),
        cnpj=cnpj,
        periodo_ini=periodo_ini,
        periodo_fim=periodo_fim,
        status=status_label,
        linhas=linhas_df,
        tipos_sem_valor=sorted(tipos_sem_valor),
        total=total,
    )


def formatar_texto(result: LaudosResult) -> str:
    linhas_txt = [
        f"Empresa: {result.empresa.upper()}",
    ]
    if result.cnpj:
        linhas_txt.append(f"CNPJ: {result.cnpj}")
    linhas_txt.append("")
    linhas_txt.append(f"{'DATA':<12}{'CLIENTE':<45}{'TIPO DE LAUDO':<18}{'VALOR':>10}")
    for _, row in result.linhas.iterrows():
        data_str = row["DATA"].strftime("%d/%m/%Y")
        linhas_txt.append(f"{data_str:<12}{row['CLIENTE']:<45}{row['TIPO']:<18}{format_brl(row['VALOR']):>10}")
    linhas_txt.append("")
    linhas_txt.append(f"Total{' ' * 70}{format_brl(result.total)}")
    return "\n".join(linhas_txt)
