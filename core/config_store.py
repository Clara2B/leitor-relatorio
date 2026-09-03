"""Leitura e escrita da tabela de valores (config.json).

Não é preciso mexer em código para adicionar/editar/remover tipos de laudo
ou empresas de audiência: tudo fica neste arquivo JSON, editável também
pela própria tela do programa (aba "Gerenciar valores").
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from core.utils import normalize

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "laudos": {
        "AUTO": 40.0,
        "AUTO-BALÃO": 60.0,
        "CONSÓRCIO": 200.0,
        "EMPRÉSTIMO": 40.0,
        "LOTEAMENTO": 400.0,
        "IMÓVEL": 70.0,
    },
    "audiencias": {},
}


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return json.loads(json.dumps(DEFAULT_CONFIG))
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("laudos", {})
    data.setdefault("audiencias", {})
    return data


def save_config(data: Dict[str, Any]) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=False)


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
    # Se já existe uma chave equivalente (ignorando acento/caixa), atualiza-a.
    alvo = normalize(tipo_laudo)
    for tipo_existente in list(config["laudos"].keys()):
        if normalize(tipo_existente) == alvo:
            config["laudos"][tipo_existente] = float(valor)
            save_config(config)
            return
    config["laudos"][tipo_laudo] = float(valor)
    save_config(config)


def remove_valor_laudo(config: Dict[str, Any], tipo_laudo: str) -> None:
    alvo = normalize(tipo_laudo)
    for tipo_existente in list(config.get("laudos", {}).keys()):
        if normalize(tipo_existente) == alvo:
            del config["laudos"][tipo_existente]
    save_config(config)


def get_config_audiencia(config: Dict[str, Any], empresa: str):
    """Retorna {"modalidade":..., "valor":...} para a empresa, ou None."""
    alvo = normalize(empresa)
    for nome, dados in config.get("audiencias", {}).items():
        if normalize(nome) == alvo:
            return dados
    return None


def set_config_audiencia(config: Dict[str, Any], empresa: str, modalidade: str, valor: float) -> None:
    config.setdefault("audiencias", {})
    alvo = normalize(empresa)
    for nome_existente in list(config["audiencias"].keys()):
        if normalize(nome_existente) == alvo:
            config["audiencias"][nome_existente] = {"modalidade": modalidade, "valor": float(valor)}
            save_config(config)
            return
    config["audiencias"][empresa] = {"modalidade": modalidade, "valor": float(valor)}
    save_config(config)


def remove_config_audiencia(config: Dict[str, Any], empresa: str) -> None:
    alvo = normalize(empresa)
    for nome_existente in list(config.get("audiencias", {}).keys()):
        if normalize(nome_existente) == alvo:
            del config["audiencias"][nome_existente]
    save_config(config)
