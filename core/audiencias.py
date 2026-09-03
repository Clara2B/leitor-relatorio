"""Regras do fluxo de AUDIÊNCIAS: filtro quinzenal + empresa, sem status
(sempre solicitação), valor vindo da tabela de configuração por empresa."""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

import pandas as pd

from core.config_store import get_config_audiencia
from core.excel_reader import load_data_sheets
from core.utils import format_brl, normalize, parse_date_cell

REQUIRED_HEADERS = ["EMPRESA", "NOME COMPLETO", "DATA DE RECEBIMENTO"]
# Identifica uma audiência de verdade (evita perder registros por causa de
# colunas secundárias como advogada/checklist vindas diferentes entre abas).
CHAVE_DUPLICIDADE = ["DATA DE RECEBIMENTO", "EMPRESA", "NOME COMPLETO", "CPF"]


@dataclass
class AudienciasResult:
    empresa: str
    cnpj: Optional[str]
    periodo_ini: date
    periodo_fim: date
    modalidade: Optional[str]
    valor_unitario: Optional[float]
    clientes: List[str] = field(default_factory=list)
    total: Optional[float] = None
    valor_cadastrado: bool = True


def periodo_quinzenal(ano: int, mes: int, quinzena: int) -> Tuple[date, date]:
    """quinzena=1 -> dia 1 ao dia 15; quinzena=2 -> dia 16 ao último dia do mês."""
    if quinzena == 1:
        return date(ano, mes, 1), date(ano, mes, 15)
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, 16), date(ano, mes, ultimo_dia)


def carregar_planilha(path: str) -> pd.DataFrame:
    df = load_data_sheets(path, REQUIRED_HEADERS, chave_duplicidade=CHAVE_DUPLICIDADE)
    if df.empty:
        raise ValueError(
            "Não encontrei nenhuma aba com as colunas 'EMPRESA' e 'NOME COMPLETO' "
            "nesta planilha. Verifique se o arquivo é o correto."
        )
    return df


def listar_empresas(df: pd.DataFrame) -> List[str]:
    col = _col(df, "EMPRESA")
    return sorted({str(v).strip() for v in df[col].dropna() if str(v).strip()})


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
    cnpj: Optional[str] = None,
) -> AudienciasResult:
    col_empresa = _col(df, "EMPRESA")
    col_cliente = _col(df, "NOME COMPLETO")
    col_data = _col_optional(df, "DATA DE RECEBIMENTO") or _col(df, "DATA")

    alvo_empresa = normalize(empresa)
    empresas_disponiveis = {normalize(v) for v in df[col_empresa].dropna()}
    if alvo_empresa not in empresas_disponiveis:
        raise ValueError(
            f"A empresa '{empresa}' não foi encontrada na planilha. "
            f"Confira o nome exato (empresas disponíveis: "
            f"{', '.join(sorted({str(v).strip() for v in df[col_empresa].dropna()}))[:500]})."
        )

    clientes = []
    for _, row in df.iterrows():
        if normalize(row.get(col_empresa)) != alvo_empresa:
            continue
        data_val = parse_date_cell(row.get(col_data))
        if data_val is None or not (periodo_ini <= data_val <= periodo_fim):
            continue
        cliente = str(row.get(col_cliente)).strip() if row.get(col_cliente) is not None else ""
        if cliente:
            clientes.append(cliente)

    clientes = sorted(clientes, key=normalize)

    cfg_empresa = get_config_audiencia(config, empresa)
    modalidade = cfg_empresa.get("modalidade") if cfg_empresa else None
    valor_unitario = float(cfg_empresa["valor"]) if cfg_empresa and cfg_empresa.get("valor") is not None else None
    total = valor_unitario * len(clientes) if valor_unitario is not None else None

    return AudienciasResult(
        empresa=empresa.strip(),
        cnpj=cnpj,
        periodo_ini=periodo_ini,
        periodo_fim=periodo_fim,
        modalidade=modalidade,
        valor_unitario=valor_unitario,
        clientes=clientes,
        total=total,
        valor_cadastrado=cfg_empresa is not None,
    )


def formatar_texto(result: AudienciasResult) -> str:
    linhas = [f"Empresa: {result.empresa.upper()}"]
    if result.cnpj:
        linhas.append(f"CNPJ: {result.cnpj}")
    linhas.append(f"Período: {result.periodo_ini.strftime('%d/%m/%Y')} -{result.periodo_fim.strftime('%d/%m/%Y')}")
    linhas.append(f"Modalidade de Contratação: {result.modalidade or '(não cadastrada)'}")
    if result.valor_unitario is not None:
        linhas.append(f"Valor por audiência: {format_brl(result.valor_unitario)}")
    linhas.append(f"Quantidade solicitada no período: {len(result.clientes)}")
    linhas.append("Clientes:")
    for i, nome in enumerate(result.clientes, start=1):
        linhas.append(f"{i} - {nome.upper()}")
    if result.total is not None:
        linhas.append(f"Total {format_brl(result.total)}")
    return "\n".join(linhas)
