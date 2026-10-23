# ----------------------------------------------------------------------------
# Arquivo: registro/cards/generator.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Motor de geração de crachás e cartões de identificação com QR Code.
Suporta exportação de alta fidelidade para PDF (ReportLab) e HTML moderno.
"""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import base64
import csv
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

import openpyxl
import qrcode
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


@dataclass
class CardOptions:
    """Configurações de formatação e leiaute da grade de cartões."""

    cols: int = 3
    rows: int = 7
    show_cut_lines: bool = True
    header_text: str = ""
    show_page_number: bool = True
    page_width: float = 210 * mm
    page_height: float = 297 * mm


def _obter_caminho_recurso(nome_arquivo: str) -> Optional[Path]:
    """Retorna o caminho de um recurso em ambiente de desenvolvimento ou empacotado."""
    candidatos = [
        Path(nome_arquivo),
        Path(__file__).resolve().parent / nome_arquivo,
        Path(__file__).resolve().parent.parent / nome_arquivo,
        Path(__file__).resolve().parent.parent.parent / nome_arquivo,
    ]
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            candidatos.insert(0, Path(sys._MEIPASS) / nome_arquivo)
        candidatos.insert(1, Path(sys.executable).parent / nome_arquivo)

    for cand in candidatos:
        if cand.exists():
            return cand
    return None


_FONTE_REGISTRADA = False


def _configurar_fontes_reportlab() -> Tuple[str, str]:
    """Registra fontes personalizadas ou retorna as fontes padrão equivalentes."""
    global _FONTE_REGISTRADA
    nome_regular = "Helvetica"
    nome_bold = "Helvetica-Bold"

    if not _FONTE_REGISTRADA:
        caminho_roboto = _obter_caminho_recurso("roboto.ttf")
        if caminho_roboto:
            try:
                pdfmetrics.registerFont(TTFont("Roboto-Card", str(caminho_roboto)))
                nome_regular = "Roboto-Card"
                nome_bold = "Roboto-Card"
                _FONTE_REGISTRADA = True
            except Exception:
                pass
    elif "Roboto-Card" in pdfmetrics.getRegisteredFontNames():
        nome_regular = "Roboto-Card"
        nome_bold = "Roboto-Card"

    return nome_regular, nome_bold


def generate_qr_pil(data: str) -> Image.Image:
    """Gera uma imagem PIL com o QR Code para inserção direta no ReportLab."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=12,
        border=0,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def generate_qr_base64(data: str) -> str:
    """Gera um QR Code em Base64 para incorporação direta no documento HTML."""
    img = generate_qr_pil(data)
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def _normalizar_linha(linha: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Identifica colunas de matrícula e nome independentemente de variações de cabeçalho."""
    chaves = {k.strip().lower(): v for k, v in linha.items() if k is not None}

    chave_reg = None
    for k in chaves:
        if any(term in k for term in ("reg", "matr", "pront", "id", "código", "codigo")):
            chave_reg = k
            break

    chave_nome = None
    for k in chaves:
        if any(term in k for term in ("nam", "nom", "alun", "estud", "discente")):
            chave_nome = k
            break

    chave_turma = None
    for k in chaves:
        if any(term in k for term in ("turm", "clas", "curso", "ano")):
            chave_turma = k
            break

    valores = list(chaves.values())
    if not chave_reg and valores:
        reg_val = str(valores[0] or "").strip()
    else:
        reg_val = str(chaves.get(chave_reg, "") if chave_reg else "").strip()

    if not chave_nome and len(valores) > 1:
        nome_val = str(valores[1] or "").strip()
    else:
        nome_val = str(chaves.get(chave_nome, "") if chave_nome else "").strip()

    turma_val = str(chaves.get(chave_turma, "") if chave_turma else "").strip()

    if not reg_val and not nome_val:
        return None

    return {
        "register": reg_val,
        "name": nome_val,
        "turma": turma_val,
    }


def load_students_from_file(filepath: Union[Path, str]) -> List[Dict[str, str]]:
    """
    Carrega estudantes a partir de um arquivo CSV ou planilha Excel (.xlsx, .xls).
    Retorna uma lista de dicionários com chaves 'register', 'name' e opcional 'turma'.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    estudantes: List[Dict[str, str]] = []

    if path.suffix.lower() in (".xlsx", ".xls"):
        wb = openpyxl.load_workbook(path, data_only=True)
        sheet = wb.active
        linhas = list(sheet.iter_rows(values_only=True))
        if not linhas:
            return []

        cabecalho = [str(c or "").strip() for c in linhas[0]]
        for row in linhas[1:]:
            dicionario = {}
            for col_idx, valor in enumerate(row):
                chave = cabecalho[col_idx] if col_idx < len(cabecalho) and cabecalho[col_idx] else f"col_{col_idx}"
                dicionario[chave] = str(valor or "").strip()
            item = _normalizar_linha(dicionario)
            if item:
                estudantes.append(item)
    else:
        conteudo = ""
        for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:
                conteudo = path.read_text(encoding=encoding)
                break
            except UnicodeDecodeError:
                continue

        linhas_brutas = [l for l in conteudo.splitlines() if l.strip()]
        if not linhas_brutas:
            return []

        delimitador = ","
        primeira_linha = linhas_brutas[0]
        if ";" in primeira_linha and primeira_linha.count(";") > primeira_linha.count(","):
            delimitador = ";"
        elif "\t" in primeira_linha:
            delimitador = "\t"

        reader = csv.DictReader(linhas_brutas, delimiter=delimitador)
        for row in reader:
            item = _normalizar_linha(row)
            if item:
                estudantes.append(item)

    return estudantes


def _formatar_nome_em_linhas(
    c: canvas.Canvas,
    nome: str,
    max_w: float,
    fonte: str,
) -> Tuple[List[str], float]:
    """
    Quebra o nome do discente em até 2 linhas usando quebra inteligente por palavras.
    Caso o nome seja excessivamente longo, reduz gradualmente o tamanho da fonte (de 7.0pt a 5.8pt).
    Retorna a lista de linhas formatadas e o tamanho final da fonte adotado.
    """
    palavras = nome.strip().upper().split()
    if not palavras:
        return ([], 7.0)

    # Tenta tamanhos de fonte progressivamente menores para acomodar em 2 linhas
    tamanhos = [7.0, 6.5, 6.0, 5.8]
    melhor_linhas: List[str] = []
    melhor_tamanho: float = 7.0

    for sz in tamanhos:
        linhas: List[str] = []
        linha_atual: List[str] = []

        for p in palavras:
            candidata = " ".join(linha_atual + [p]) if linha_atual else p
            if c.stringWidth(candidata, fonte, sz) <= max_w:
                linha_atual.append(p)
            else:
                if linha_atual:
                    linhas.append(" ".join(linha_atual))
                    linha_atual = [p]
                else:
                    # Palavra individual maior que a largura disponível: força divisão
                    linhas.append(p)
                    linha_atual = []

        if linha_atual:
            linhas.append(" ".join(linha_atual))

        if len(linhas) <= 2:
            return (linhas, sz)

        melhor_linhas = linhas
        melhor_tamanho = sz

    # Se ainda exceder 2 linhas com a menor fonte (5.8pt), condensa a sobra na 2ª linha com reticências
    linha1 = melhor_linhas[0]
    linha2 = " ".join(melhor_linhas[1:])
    while linha2 and c.stringWidth(linha2 + "…", fonte, melhor_tamanho) > max_w:
        linha2 = linha2[:-1].strip()
    if linha2:
        linha2 = linha2 + "…"

    return ([linha1, linha2], melhor_tamanho)


def generate_cards_pdf(
    students: List[Dict[str, str]],
    output_path: Union[Path, str],
    options: Optional[CardOptions] = None,
) -> int:
    """
    Gera arquivo PDF vetorial com a grade de cartões dimensionada para folha A4.
    Retorna o número total de cartões processados.
    """
    if options is None:
        options = CardOptions()

    cols = max(1, options.cols)
    rows = max(1, options.rows)
    cards_per_page = cols * rows

    page_w, page_h = options.page_width, options.page_height
    cell_w = page_w / cols
    cell_h = page_h / rows

    fonte_reg, fonte_bold = _configurar_fontes_reportlab()

    c = canvas.Canvas(str(output_path), pagesize=(page_w, page_h))
    total_estudantes = len(students)
    page_num = 1

    for start_idx in range(0, max(1, total_estudantes), cards_per_page):
        batch = students[start_idx : start_idx + cards_per_page]

        # 1. Desenho das células da grade
        for idx in range(cards_per_page):
            col_idx = idx % cols
            row_idx = idx // cols

            x_left = col_idx * cell_w
            y_top = page_h - (row_idx * cell_h)
            y_bottom = y_top - cell_h

            # Linhas de corte (bordas das células)
            if options.show_cut_lines:
                c.setLineWidth(0.4)
                c.setStrokeColorRGB(0.2, 0.2, 0.2)
                c.rect(x_left, y_bottom, cell_w, cell_h, stroke=1, fill=0)

            # Se não houver estudante para este índice na última página, desenha apenas a célula vazia
            if idx >= len(batch):
                continue

            estudante = batch[idx]
            matricula = estudante.get("register", "").strip()
            nome = estudante.get("name", "").strip()
            turma = estudante.get("turma", "").strip()

            # Desenha QR Code
            qr_size = min(cell_w * 0.40, cell_h * 0.88)
            margin_x = 2.0 * mm
            qr_x = x_left + margin_x
            qr_y = y_bottom + (cell_h - qr_size) / 2.0

            if matricula:
                try:
                    img_qr = generate_qr_pil(matricula)
                    c.drawInlineImage(img_qr, qr_x, qr_y, width=qr_size, height=qr_size)
                except Exception:
                    pass

            # Informações textuais (lado direito do cartão)
            text_x = qr_x + qr_size + 2.5 * mm
            max_text_w = x_left + cell_w - text_x - 2.0 * mm

            # Cabeçalho institucional opcional
            if options.header_text:
                c.setFont(fonte_reg, 5.5)
                c.setFillColorRGB(0.4, 0.4, 0.4)
                c.drawString(text_x, y_top - 4.5 * mm, options.header_text[:40])

            # Nome do estudante (quebra de linha inteligente em até 2 linhas e ajuste fino de fonte)
            linhas_nome, tam_fonte_nome = _formatar_nome_em_linhas(c, nome, max_text_w, fonte_reg)

            # Ajusta posição vertical conforme a quantidade de linhas do nome
            if len(linhas_nome) > 1:
                reg_y = y_bottom + cell_h * 0.56
                c.setFont(fonte_bold, 11)
                c.setFillColorRGB(0.0, 0.0, 0.0)
                c.drawString(text_x, reg_y, matricula)

                c.setFont(fonte_reg, tam_fonte_nome)
                c.setFillColorRGB(0.15, 0.15, 0.15)
                line1_y = reg_y - 3.5 * mm
                c.drawString(text_x, line1_y, linhas_nome[0])

                espacamento = (tam_fonte_nome * 0.38 + 0.3) * mm
                line2_y = line1_y - espacamento
                c.drawString(text_x, line2_y, linhas_nome[1])
                name_bottom_y = line2_y
            else:
                reg_y = y_bottom + cell_h * 0.52
                c.setFont(fonte_bold, 11)
                c.setFillColorRGB(0.0, 0.0, 0.0)
                c.drawString(text_x, reg_y, matricula)

                c.setFont(fonte_reg, tam_fonte_nome)
                c.setFillColorRGB(0.15, 0.15, 0.15)
                name_y = reg_y - 3.8 * mm
                if linhas_nome:
                    c.drawString(text_x, name_y, linhas_nome[0])
                name_bottom_y = name_y

            # Turma se informada
            if turma:
                c.setFont(fonte_reg, 5.5)
                c.setFillColorRGB(0.4, 0.4, 0.4)
                turma_display = turma[:30]
                c.drawString(text_x, name_bottom_y - 2.8 * mm, turma_display)

            # Indicador de número de página
            if options.show_page_number:
                c.saveState()
                c.setFont(fonte_bold, 5.5)
                c.setFillColorRGB(0.5, 0.5, 0.5)
                c.translate(x_left + cell_w - 1.5 * mm, y_top - 2.5 * mm)
                c.rotate(-90)
                c.drawString(0, 0, f"P.{page_num}")
                c.restoreState()

        c.showPage()
        page_num += 1

    c.save()
    return total_estudantes


def generate_cards_html(
    students: List[Dict[str, str]],
    output_path: Union[Path, str],
    options: Optional[CardOptions] = None,
) -> int:
    """
    Gera arquivo HTML moderno com grade flexível dimensionada para impressão A4.
    Retorna o número total de cartões processados.
    """
    if options is None:
        options = CardOptions()

    cols = max(1, options.cols)
    rows = max(1, options.rows)
    chunk_size = cols * rows

    border_style = "0.5pt solid black" if options.show_cut_lines else "none"

    html_start = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Cartões de Identificação</title>
<style>
    @page {{
        size: A4;
        margin: 0;
    }}
    body {{
        margin: 0;
        padding: 0;
        background: #fff;
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
        -webkit-print-color-adjust: exact;
    }}
    .page {{
        width: 210mm;
        height: 297mm;
        display: grid;
        grid-template-columns: repeat({cols}, 1fr);
        grid-template-rows: repeat({rows}, 1fr);
        page-break-after: always;
        box-sizing: border-box;
    }}
    .cell {{
        border: {border_style};
        display: flex;
        flex-direction: row;
        align-items: center;
        justify-content: flex-start;
        box-sizing: border-box;
        position: relative;
        padding: 1.5mm;
        overflow: hidden;
    }}
    .qr-wrapper {{
        height: 92%;
        aspect-ratio: 1;
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        margin-right: 2mm;
    }}
    .qr-img {{
        width: 100%;
        height: 100%;
        object-fit: contain;
    }}
    .content-footer {{
        flex-grow: 1;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: flex-start;
        overflow: hidden;
        min-width: 0;
    }}
    .inst-header {{
        font-size: 5.5pt;
        color: #666;
        margin-bottom: 2px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 100%;
    }}
    .reg {{
        font-size: 11pt;
        font-weight: 900;
        letter-spacing: -0.5px;
        line-height: 1.1;
    }}
    .name {{
        font-size: 7pt;
        text-transform: uppercase;
        font-weight: 500;
        margin-top: 2px;
        color: #222;
        white-space: normal;
        line-height: 1.18;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        max-width: 100%;
        word-break: break-word;
    }}
    .turma {{
        font-size: 5.5pt;
        color: #555;
        margin-top: 2px;
    }}
    .page-indicator {{
        font-size: 5.5pt;
        font-weight: bold;
        color: #777;
        transform: rotate(-90deg);
        transform-origin: bottom right;
        white-space: nowrap;
        position: absolute;
        right: 4px;
        top: 8px;
    }}
    @media print {{
        .page {{ border: none; }}
        .cell {{ border-color: black !important; }}
    }}
</style>
</head>
<body>
"""
    cards_html = ""
    page_num = 1
    total = len(students)

    for i in range(0, max(1, total), chunk_size):
        cards_html += '<div class="page">'
        batch = students[i : i + chunk_size]
        for row in batch:
            qr = generate_qr_base64(row.get("register", ""))
            indicator_html = (
                f'<div class="page-indicator">P.{page_num}</div>' if options.show_page_number else ""
            )
            header_html = (
                f'<div class="inst-header">{options.header_text}</div>' if options.header_text else ""
            )
            turma_html = (
                f'<div class="turma">{row["turma"]}</div>' if row.get("turma") else ""
            )

            cards_html += f"""
            <div class="cell">
                {indicator_html}
                <div class="qr-wrapper">
                    <img src="{qr}" class="qr-img" alt="QR">
                </div>
                <div class="content-footer">
                    {header_html}
                    <div class="reg">{row.get('register', '')}</div>
                    <div class="name">{row.get('name', '')}</div>
                    {turma_html}
                </div>
            </div>"""

        # Preenchimento de células vazias para fechar a página
        for _ in range(chunk_size - len(batch)):
            cards_html += '<div class="cell"></div>'

        cards_html += "</div>"
        page_num += 1

    html_end = "</body></html>"
    Path(output_path).write_text(html_start + cards_html + html_end, encoding="utf-8")
    return total
