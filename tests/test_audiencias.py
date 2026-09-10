from datetime import date
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from core.audiencias import gerar_relatorio, periodo_quinzenal
from core import db
from core.config_store import load_config


FAIXAS = {
    "faixas_audiencias": [
        {"inicio": 1, "fim": 20, "valor": 400.0},
        {"inicio": 21, "fim": 39, "valor": 350.0},
        {"inicio": 40, "fim": 60, "valor": 300.0},
        {"inicio": 61, "fim": 79, "valor": 250.0},
        {"inicio": 80, "fim": 100, "valor": 200.0},
    ]
}


def planilha(primeira, segunda, empresa="ALFA", ano=2026, mes=9):
    linhas = []
    for indice in range(primeira):
        linhas.append({
            "EMPRESA": empresa,
            "NOME COMPLETO": f"Primeira {indice}",
            "DATA DE RECEBIMENTO": date(ano, mes, 1),
        })
    for indice in range(segunda):
        linhas.append({
            "EMPRESA": empresa,
            "NOME COMPLETO": f"Segunda {indice}",
            "DATA DE RECEBIMENTO": date(ano, mes, 16),
        })
    return pd.DataFrame(linhas)


class PrecificacaoAudienciasTest(unittest.TestCase):
    def relatorio_segunda_quinzena(self, primeira, segunda):
        return gerar_relatorio(
            planilha(primeira, segunda), FAIXAS, "ALFA", *periodo_quinzenal(2026, 9, 2)
        )

    def test_primeira_quinzena_usa_a_faixa_inicial(self):
        result = gerar_relatorio(
            planilha(10, 5), FAIXAS, "ALFA", *periodo_quinzenal(2026, 9, 1)
        )
        self.assertEqual((result.quantidade_mes, result.valor_unitario, result.total), (10, 400.0, 4000.0))

    def test_opcao_b_cobra_somente_a_segunda_quinzena_na_nova_faixa(self):
        result = self.relatorio_segunda_quinzena(20, 1)
        self.assertEqual((result.quantidade_mes_anterior, result.quantidade_mes), (20, 21))
        self.assertEqual((result.valor_unitario, result.total), (350.0, 350.0))

    def test_faixa_de_39_audiencias(self):
        result = self.relatorio_segunda_quinzena(15, 24)
        self.assertEqual((result.quantidade_mes, result.valor_unitario, result.total), (39, 350.0, 8400.0))

    def test_proxima_faixa(self):
        result = self.relatorio_segunda_quinzena(20, 20)
        self.assertEqual((result.quantidade_mes, result.valor_unitario, result.total), (40, 300.0, 6000.0))

    def test_mes_anterior_nao_entra_no_acumulado(self):
        df = pd.concat([
            planilha(20, 20, ano=2026, mes=9),
            planilha(0, 1, ano=2026, mes=10),
        ], ignore_index=True)
        result = gerar_relatorio(df, FAIXAS, "ALFA", *periodo_quinzenal(2026, 10, 2))
        self.assertEqual((result.quantidade_mes, result.valor_unitario, result.total), (1, 400.0, 400.0))

    def test_faixas_sao_criadas_no_banco_local(self):
        caminho_original, diretorio_original = db.DB_PATH, db.DATA_DIR
        with tempfile.TemporaryDirectory() as diretorio:
            try:
                db.DATA_DIR = Path(diretorio)
                db.DB_PATH = db.DATA_DIR / "teste.sqlite3"
                faixas = load_config()["faixas_audiencias"]
            finally:
                db.DB_PATH, db.DATA_DIR = caminho_original, diretorio_original

        self.assertEqual(
            [(faixa["inicio"], faixa["fim"], faixa["valor"]) for faixa in faixas],
            [(1, 20, 400.0), (21, 39, 350.0), (40, 60, 300.0), (61, 79, 250.0), (80, 100, 200.0)],
        )


if __name__ == "__main__":
    unittest.main()
