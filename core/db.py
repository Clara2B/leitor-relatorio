"""Banco de dados local (SQLite) com os valores compartilhados do sistema:
tipos de laudo, empresas de audiência e CNPJs.

Por que SQLite? O programa roda direto no computador/servidor da empresa —
não precisa de nenhum serviço externo (nem internet) para funcionar. O
arquivo `data/leitor_relatorio.sqlite3` guarda tudo; todas as pessoas que
rodam o programa nessa mesma máquina/rede enxergam e editam os mesmos dados,
na hora, sem precisar reiniciar nada.

Não é preciso instalar nada além do que já está no requirements.txt — o
`sqlite3` já vem embutido no Python.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterator
from contextlib import contextmanager

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "leitor_relatorio.sqlite3"

# Arquivo antigo (versão anterior do programa, antes do banco de dados).
# Se existir e o banco ainda estiver vazio, os dados são importados uma
# única vez automaticamente.
LEGACY_CONFIG_JSON = Path(__file__).resolve().parent.parent / "config.json"

DEFAULT_LAUDOS = {
    "AUTO": 40.0,
    "AUTO-BALÃO": 60.0,
    "CONSÓRCIO": 200.0,
    "EMPRÉSTIMO": 40.0,
    "LOTEAMENTO": 400.0,
    "IMÓVEL": 70.0,
}


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Cria as tabelas (se ainda não existirem) e importa o config.json
    antigo uma única vez, se houver."""
    with get_connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS laudos_valores ("
            "tipo TEXT PRIMARY KEY, valor REAL NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS audiencias_valores ("
            "empresa TEXT PRIMARY KEY, valor REAL NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS cnpjs ("
            "empresa TEXT PRIMARY KEY, cnpj TEXT NOT NULL)"
        )

        total_laudos = conn.execute("SELECT COUNT(*) FROM laudos_valores").fetchone()[0]

        if total_laudos == 0:
            _migrar_config_json_ou_padrao(conn)


def _migrar_config_json_ou_padrao(conn: sqlite3.Connection) -> None:
    """Roda só na primeira vez (tabela laudos_valores vazia). Se existir um
    config.json de uma instalação anterior, importa dele; senão, começa com
    os tipos de laudo padrão."""
    dados = None
    if LEGACY_CONFIG_JSON.exists():
        try:
            with open(LEGACY_CONFIG_JSON, "r", encoding="utf-8") as f:
                dados = json.load(f)
        except (json.JSONDecodeError, OSError):
            dados = None

    if dados:
        for tipo, valor in dados.get("laudos", {}).items():
            conn.execute(
                "INSERT OR REPLACE INTO laudos_valores (tipo, valor) VALUES (?, ?)",
                (tipo, float(valor)),
            )
        for empresa, info in dados.get("audiencias", {}).items():
            valor = info.get("valor") if isinstance(info, dict) else info
            if valor is not None:
                conn.execute(
                    "INSERT OR REPLACE INTO audiencias_valores (empresa, valor) VALUES (?, ?)",
                    (empresa, float(valor)),
                )
        for empresa, cnpj in dados.get("cnpjs", {}).items():
            conn.execute(
                "INSERT OR REPLACE INTO cnpjs (empresa, cnpj) VALUES (?, ?)",
                (empresa, str(cnpj)),
            )
        # marca o arquivo antigo como já importado, para não confundir
        try:
            LEGACY_CONFIG_JSON.rename(
                LEGACY_CONFIG_JSON.with_suffix(".json.importado")
            )
        except OSError:
            pass
    else:
        for tipo, valor in DEFAULT_LAUDOS.items():
            conn.execute(
                "INSERT OR REPLACE INTO laudos_valores (tipo, valor) VALUES (?, ?)",
                (tipo, float(valor)),
            )
