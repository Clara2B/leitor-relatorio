"""Funções auxiliares de normalização de texto e datas."""
from __future__ import annotations

import unicodedata
from datetime import date, datetime
from typing import Optional

import pandas as pd


def normalize(text) -> str:
    """Remove acentos, espaços extras e diferenças de maiúsculas/minúsculas.

    Usado para comparar nomes de empresa, tipo de laudo e status sem que
    pequenas diferenças de digitação (espaço a mais, acento, caixa) quebrem
    o filtro.
    """
    if text is None:
        return ""
    text = str(text).strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = " ".join(text.split())  # colapsa espaços internos duplicados
    return text.upper()


def parse_date_cell(value) -> Optional[date]:
    """Converte um valor de célula (datetime, string dd/mm/aaaa, etc.) em date."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, pd.Timestamp):
        return value.date()
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    # último recurso: deixa o pandas tentar interpretar
    try:
        parsed = pd.to_datetime(text, dayfirst=True, errors="raise")
        return parsed.date()
    except Exception:
        return None


def format_brl(value: float) -> str:
    """Formata um número como moeda brasileira: R$ 1.234,56"""
    text = f"{value:,.2f}"
    text = text.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {text}"
