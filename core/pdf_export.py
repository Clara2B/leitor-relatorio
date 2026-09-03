"""Geração do relatório em PDF, usando a folha personalizada (logo + faixa
dourada + rodapé) igual aos modelos que a empresa já usa.

As imagens de fundo ficam em `assets/` — uma para laudos (marca ELITE) e
outra para audiências (marca EXIMIA). Se quiser trocar a folha (outra marca,
outro rodapé), basta substituir o arquivo de imagem correspondente; o
programa não precisa mudar.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING

from reportlab.lib.colors import HexColor, white, whitesmoke
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from core.utils import format_brl

if TYPE_CHECKING:
    from core.audiencias import AudienciasResult
    from core.laudos import LaudosResult

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
FUNDO_LAUDOS = ASSETS_DIR / "laudos_logo_0.jpeg"
FUNDO_AUDIENCIAS = ASSETS_DIR / "audiencias_logo_0.jpeg"

NAVY = HexColor("#152A40")
NAVY_CLARO = HexColor("#1F3B57")

LARGURA, ALTURA = A4
MARGEM = 42
TOPO_CONTEUDO = ALTURA - 230  # abaixo do bloco de logo
RODAPE_LIMITE = 70  # não desenhar depois disso (fica em cima do rodapé da folha)


def _fundo(c: canvas.Canvas, caminho_imagem: Path, cobrir_rodape: bool = False):
    if caminho_imagem.exists():
        c.drawImage(
            ImageReader(str(caminho_imagem)),
            0,
            0,
            width=LARGURA,
            height=ALTURA,
            preserveAspectRatio=False,
            mask="auto",
        )
    if cobrir_rodape:
        # A folha da ELITE já vem com uma linha de contato (instagram/
        # WhatsApp/e-mail) impressa perto do rodapé — pinta um retângulo
        # branco por cima para escondê-la.
        c.setFillColor(white)
        c.rect(0, 0, LARGURA, 60, stroke=0, fill=1)


def _cabecalho_empresa(c: canvas.Canvas, y: float, empresa: str, cnpj: str | None, linhas_extra: list[str]) -> float:
    """Desenha a faixa azul-marinho com Empresa/CNPJ e linhas extras
    (período, valor, etc.). Retorna o novo Y (topo livre abaixo dela)."""
    altura_linha = 18
    n_linhas = 2 + len(linhas_extra) if cnpj else 1 + len(linhas_extra)
    altura_faixa = altura_linha * n_linhas + 12
    c.setFillColor(NAVY)
    c.rect(MARGEM, y - altura_faixa, LARGURA - 2 * MARGEM, altura_faixa, stroke=0, fill=1)

    texto_y = y - 20
    c.setFillColor(whitesmoke)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(LARGURA / 2, texto_y, f"Empresa: {empresa.upper()}")
    texto_y -= altura_linha
    if cnpj:
        c.setFont("Helvetica", 10)
        c.drawCentredString(LARGURA / 2, texto_y, f"CNPJ: {cnpj}")
        texto_y -= altura_linha
    c.setFont("Helvetica", 10)
    for linha in linhas_extra:
        c.drawCentredString(LARGURA / 2, texto_y, linha)
        texto_y -= altura_linha

    return y - altura_faixa - 14


def gerar_pdf_laudos(result: "LaudosResult") -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    _fundo(c, FUNDO_LAUDOS, cobrir_rodape=True)

    y = _cabecalho_empresa(c, TOPO_CONTEUDO, result.empresa, result.cnpj, [f"Status: {result.status}"])

    col_data_x = MARGEM + 6
    col_cliente_x = MARGEM + 58
    col_tipo_x = MARGEM + 218
    col_status_x = MARGEM + 353
    col_valor_x = LARGURA - MARGEM - 10

    altura_linha = 16
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(NAVY)
    y -= 6
    c.drawString(col_data_x, y, "DATA")
    c.drawString(col_cliente_x, y, "CLIENTE")
    c.drawString(col_tipo_x, y, "TIPO DE LAUDO")
    c.drawString(col_status_x, y, "STATUS")
    c.drawRightString(col_valor_x, y, "VALOR")
    y -= 6
    c.setStrokeColor(NAVY)
    c.line(MARGEM, y, LARGURA - MARGEM, y)
    y -= altura_linha

    c.setFont("Helvetica", 9)
    for i, (_, row) in enumerate(result.linhas.iterrows()):
        if y < RODAPE_LIMITE + 30:
            c.showPage()
            _fundo(c, FUNDO_LAUDOS, cobrir_rodape=True)
            y = TOPO_CONTEUDO - 20
            c.setFont("Helvetica", 9)
        c.setFillColor(HexColor("#222222"))
        c.drawString(col_data_x, y, row["DATA"].strftime("%d/%m/%Y"))
        c.drawString(col_cliente_x, y, str(row["CLIENTE"])[:26])
        c.drawString(col_tipo_x, y, str(row["TIPO"])[:21])
        c.drawString(col_status_x, y, str(row["STATUS"]))
        c.drawRightString(col_valor_x, y, format_brl(row["VALOR"]))
        y -= altura_linha

    y -= 4
    c.setFillColor(NAVY)
    c.rect(MARGEM, y - 20, LARGURA - 2 * MARGEM, 22, stroke=0, fill=1)
    c.setFillColor(whitesmoke)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(col_data_x, y - 14, "Total")
    c.drawRightString(col_valor_x, y - 14, format_brl(result.total))

    c.showPage()
    c.save()
    return buffer.getvalue()


def gerar_pdf_audiencias(result: "AudienciasResult") -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    _fundo(c, FUNDO_AUDIENCIAS)

    linhas_extra = [
        f"Período: {result.periodo_ini.strftime('%d/%m/%Y')} - {result.periodo_fim.strftime('%d/%m/%Y')}",
    ]
    if result.valor_unitario is not None:
        linhas_extra.append(f"Valor por audiência: {format_brl(result.valor_unitario)}")
    linhas_extra.append(f"Quantidade solicitada no período: {len(result.clientes)}")

    y = _cabecalho_empresa(c, TOPO_CONTEUDO, result.empresa, result.cnpj, linhas_extra)

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(NAVY)
    y -= 10
    c.drawCentredString(LARGURA / 2, y, "Clientes")
    y -= 16

    altura_linha = 16
    c.setFont("Helvetica", 9)
    for i, nome in enumerate(result.clientes, start=1):
        if y < RODAPE_LIMITE + 30:
            c.showPage()
            _fundo(c, FUNDO_AUDIENCIAS)
            y = TOPO_CONTEUDO - 20
            c.setFont("Helvetica", 9)
        c.setFillColor(HexColor("#222222"))
        c.drawString(MARGEM + 6, y, f"{i} - {nome.upper()}")
        y -= altura_linha

    if result.total is not None:
        y -= 6
        c.setFillColor(NAVY)
        c.rect(MARGEM, y - 20, LARGURA - 2 * MARGEM, 22, stroke=0, fill=1)
        c.setFillColor(whitesmoke)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(MARGEM + 10, y - 14, "Total")
        c.drawRightString(LARGURA - MARGEM - 10, y - 14, format_brl(result.total))

    c.showPage()
    c.save()
    return buffer.getvalue()
