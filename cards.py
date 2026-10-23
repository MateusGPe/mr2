# ----------------------------------------------------------------------------
# Arquivo: cards.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Utilitário para geração de crachás/cartões de identificação com QR Code em HTML.
Lê uma lista de estudantes de um arquivo CSV e gera um arquivo HTML formatado para
impressão em folhas A4 (grade de 3x7 cartões por página).
"""

import base64
import csv
import io
import qrcode

# --- 1. CONFIGURAÇÃO ---
csv_filename = "students.csv"


def generate_qr_base64(data: str) -> str:
    """Gera um QR Code em formato Base64 para incorporação direta no HTML."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=20,
        border=0,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"


# --- 2. TEMPLATE MODERNO PARA IMPRESSÃO EM FOLHA CHEIA ---
html_start = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
    /* 1. REMOVE LIMITAÇÕES DE MARGEM DA PÁGINA */
    @page { 
        size: A4; 
        margin: 0; 
    }
    body { 
        margin: 0; padding: 0; background: #fff; 
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
        -webkit-print-color-adjust: exact;
    }
    
    /* 2. GRADE DE CARTÕES NA PÁGINA (A4 Completo) */
    .page {
        width: 210mm;
        height: 297mm;
        display: grid;
        grid-template-columns: repeat(3, 1fr); /* 3 Colunas */
        grid-template-rows: repeat(7, 1fr);    /* 7 Linhas (~42.4mm) */
        page-break-after: always;
        border: 0.5pt solid black; /* Borda externa da página */
    }

    /* 3. BORDAS COMPARTILHADAS (Linha única de corte) */
    .cell {
        border: 0.5pt solid black;
        display: flex;
        flex-direction: row;
        align-items: center;
        justify-content: flex-start;
        box-sizing: border-box;
        position: relative;
        padding: 1.5mm;
        overflow: hidden;
    }

    /* 4. PROPORÇÃO E ÁREA DO QR CODE */
    .qr-wrapper {
        height: 96%;
        width: auto;
        aspect-ratio: 1;
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        margin-right: 2mm;
    }

    .qr-img {
        width: 100%;
        height: 100%;
        object-fit: contain;
    }

    /* Tipografia e Metadados */
    .content-footer {
        flex-grow: 1;
        height: 100%;
        text-align: left;
        border-top: none;
        padding-top: 0;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: flex-start;
        overflow: hidden;
        min-width: 0;
    }

    .text-block {
        display: flex;
        flex-direction: column;
    }

    .reg { 
        font-size: 12pt; 
        font-weight: 900; 
        letter-spacing: -0.5px;
        line-height: 1;
    }
    
    .name { 
        font-size: 7pt; 
        text-transform: uppercase;
        font-weight: 500;
        margin-top: 4px;
        color: #333;
    }

    /* Indicador de página no cartão */
    .page-indicator {
        font-size: 6pt;
        font-weight: bold;
        transform: rotate(-90deg);
        transform-origin: bottom right;
        white-space: nowrap;
        position: absolute;
        right: 5px;
        top: 10px;
    }

    @media print {
        .cell { border-color: black !important; }
    }
</style>
</head>
<body>
"""

html_end = "</body></html>"


def main():
    """Lê o arquivo de estudantes e compila a grade de cartões em HTML."""
    cards_html = ""
    try:
        with open(csv_filename, mode="r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            chunk_size = 21
            page_num = 1
            for i in range(0, len(reader), chunk_size):
                cards_html += '<div class="page">'
                batch = reader[i : i + chunk_size]
                for row in batch:
                    qr = generate_qr_base64(row["register"])
                    cards_html += f"""
                    <div class="cell">
                        <div class="page-indicator">P.{page_num}</div>
                        <div class="qr-wrapper">
                            <img src="{qr}" class="qr-img">
                        </div>
                        <div class="content-footer">
                            <div class="text-block">
                                <span class="reg">{row['register']}</span>
                                <span class="name">{row['name']}</span>
                            </div>
                        </div>
                    </div>"""
                # Preenche células vazias para manter a grade uniforme
                for _ in range(chunk_size - len(batch)):
                    cards_html += '<div class="cell"></div>'
                cards_html += "</div>"
                page_num += 1

        with open("printable_cards.html", "w", encoding="utf-8") as out:
            out.write(html_start + cards_html + html_end)
        print("Sucesso! Layout de cartões gerado em 'printable_cards.html'.")
    except Exception as e:
        print(f"Erro ao gerar cartões: {e}")


if __name__ == "__main__":
    main()
