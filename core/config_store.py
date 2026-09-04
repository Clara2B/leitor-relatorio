"""Leitura e escrita da tabela de valores (tipos de laudo, empresas de
audiência e CNPJs), guardada no banco de dados local (SQLite).

Não é preciso mexer em código para adicionar/editar/remover nada disso:
tudo é editável pela própria tela do programa (aba "Gerenciar valores").
Como fica num banco de dados compartilhado (veja core/db.py), qualquer
pessoa que rode o programa nesta mesma máquina/rede vê as mudanças na hora.
"""
from __future__ import annotations

from typing import Any, Dict

from core import db
from core.utils import normalize


def load_config() -> Dict[str, Any]:
    """Lê o estado atual do banco de dados. Chame de novo sempre que
    precisar dos dados mais recentes (ex: a cada rerun da tela) — outra
    pessoa pode ter editado algo nesse meio-tempo."""
    db.init_db()
    with db.get_connection() as conn:
        laudos = dict(conn.execute("SELECT tipo, valor FROM laudos_valores").fetchall())
        audiencias = {
            empresa: {"valor": valor}
            for empresa, valor in conn.execute("SELECT empresa, valor FROM audiencias_valores").fetchall()
        }
        cnpjs = dict(conn.execute("SELECT empresa, cnpj FROM cnpjs").fetchall())
    return {"laudos": laudos, "audiencias": audiencias, "cnpjs": cnpjs}


def get_valor_laudo(config: Dict[str, Any], tipo_laudo: str):
    """Retorna o valor cadastrado para um tipo de laudo, ignorando
    acentuação/caixa/espaços. Retorna None se não encontrado."""
    alvo = normalize(tipo_laudo)
    for tipo, valor in config.get("laudos", {}).items():
        if normalize(tipo) == alvo:
            return float(valor)
    return None


def set_valor_laudo(config: Dict[str, Any], tipo_laudo: str, valor: float) -> None:
    config.setdefault("laudos", {})
    alvo = normalize(tipo_laudo)
    # Se já existe uma chave equivalente (ignorando acento/caixa), atualiza-a
    # em vez de criar uma segunda entrada duplicada.
    chave = next((t for t in config["laudos"] if normalize(t) == alvo), tipo_laudo)
    config["laudos"][chave] = float(valor)
    with db.get_connection() as conn:
        if chave != tipo_laudo:
            conn.execute("DELETE FROM laudos_valores WHERE tipo = ?", (chave,))
        conn.execute(
            "INSERT OR REPLACE INTO laudos_valores (tipo, valor) VALUES (?, ?)",
            (tipo_laudo if chave == tipo_laudo else chave, float(valor)),
        )


def remove_valor_laudo(config: Dict[str, Any], tipo_laudo: str) -> None:
    alvo = normalize(tipo_laudo)
    with db.get_connection() as conn:
        for tipo_existente in list(config.get("laudos", {}).keys()):
            if normalize(tipo_existente) == alvo:
                del config["laudos"][tipo_existente]
                conn.execute("DELETE FROM laudos_valores WHERE tipo = ?", (tipo_existente,))


def get_config_audiencia(config: Dict[str, Any], empresa: str):
    """Retorna {"valor":...} para a empresa, ou None."""
    alvo = normalize(empresa)
    for nome, dados in config.get("audiencias", {}).items():
        if normalize(nome) == alvo:
            return dados
    return None


def set_config_audiencia(config: Dict[str, Any], empresa: str, valor: float) -> None:
    config.setdefault("audiencias", {})
    alvo = normalize(empresa)
    chave = next((e for e in config["audiencias"] if normalize(e) == alvo), empresa)
    config["audiencias"][chave] = {"valor": float(valor)}
    with db.get_connection() as conn:
        if chave != empresa:
            conn.execute("DELETE FROM audiencias_valores WHERE empresa = ?", (chave,))
        conn.execute(
            "INSERT OR REPLACE INTO audiencias_valores (empresa, valor) VALUES (?, ?)",
            (empresa if chave == empresa else chave, float(valor)),
        )


def remove_config_audiencia(config: Dict[str, Any], empresa: str) -> None:
    alvo = normalize(empresa)
    with db.get_connection() as conn:
        for nome_existente in list(config.get("audiencias", {}).keys()):
            if normalize(nome_existente) == alvo:
                del config["audiencias"][nome_existente]
                conn.execute("DELETE FROM audiencias_valores WHERE empresa = ?", (nome_existente,))


def get_cnpj_empresa(config: Dict[str, Any], empresa: str) -> str:
    """Retorna o CNPJ cadastrado para a empresa (usado para preencher o
    campo automaticamente), ou "" se não houver nenhum cadastrado. A busca
    ignora acento/caixa/espaço e também casa por "contém" (ex: empresa da
    planilha "WN FAST" encontra o cadastro "FAST")."""
    alvo = normalize(empresa)
    cnpjs = config.get("cnpjs", {})
    for nome, cnpj in cnpjs.items():
        if normalize(nome) == alvo:
            return cnpj
    for nome, cnpj in cnpjs.items():
        nome_norm = normalize(nome)
        if nome_norm and (nome_norm in alvo or alvo in nome_norm):
            return cnpj
    return ""


def set_cnpj_empresa(config: Dict[str, Any], empresa: str, cnpj: str) -> None:
    config.setdefault("cnpjs", {})
    alvo = normalize(empresa)
    chave = next((e for e in config["cnpjs"] if normalize(e) == alvo), empresa)
    config["cnpjs"][chave] = cnpj
    with db.get_connection() as conn:
        if chave != empresa:
            conn.execute("DELETE FROM cnpjs WHERE empresa = ?", (chave,))
        conn.execute(
            "INSERT OR REPLACE INTO cnpjs (empresa, cnpj) VALUES (?, ?)",
            (empresa if chave == empresa else chave, cnpj),
        )


def remove_cnpj_empresa(config: Dict[str, Any], empresa: str) -> None:
    alvo = normalize(empresa)
    with db.get_connection() as conn:
        for nome_existente in list(config.get("cnpjs", {}).keys()):
            if normalize(nome_existente) == alvo:
                del config["cnpjs"][nome_existente]
                conn.execute("DELETE FROM cnpjs WHERE empresa = ?", (nome_existente,))
