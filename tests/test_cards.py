# ----------------------------------------------------------------------------
# Arquivo: tests/test_cards.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Testes unitários para o submódulo de cartões e crachás (registro.cards).
Valida o carregamento de arquivos CSV/XLSX, geração de PDF e geração de HTML.
"""

from pathlib import Path
import openpyxl
import pytest

from registro.cards.generator import (
    CardOptions,
    generate_cards_html,
    generate_cards_pdf,
    generate_qr_base64,
    generate_qr_pil,
    load_students_from_file,
)


def test_card_options_defaults():
    """Valida valores padrão da classe CardOptions."""
    opts = CardOptions()
    assert opts.cols == 3
    assert opts.rows == 7
    assert opts.show_cut_lines is True
    assert opts.show_page_number is True
    assert opts.header_text == ""


def test_generate_qr_pil_and_base64():
    """Garante que a geração de QR Code em PIL e Base64 seja válida e não vazia."""
    img = generate_qr_pil("TESTE-12345")
    assert img.size[0] > 0
    assert img.size[1] > 0

    b64 = generate_qr_base64("TESTE-12345")
    assert b64.startswith("data:image/png;base64,")
    assert len(b64) > 100


def test_load_students_from_csv_comma(tmp_path: Path):
    """Testa leitura de arquivo CSV com delimitador por vírgula e cabeçalho padrão."""
    csv_file = tmp_path / "students.csv"
    csv_file.write_text(
        "register,name,turma\n"
        "SP1001,Alice da Silva,1A\n"
        "SP1002,Bob dos Santos,1B\n",
        encoding="utf-8",
    )

    alunos = load_students_from_file(csv_file)
    assert len(alunos) == 2
    assert alunos[0]["register"] == "SP1001"
    assert alunos[0]["name"] == "Alice da Silva"
    assert alunos[0]["turma"] == "1A"
    assert alunos[1]["register"] == "SP1002"


def test_load_students_from_csv_semicolon_and_aliases(tmp_path: Path):
    """Testa leitura de CSV com ponto-e-vírgula e cabeçalhos em português (matrícula/aluno)."""
    csv_file = tmp_path / "alunos.csv"
    csv_file.write_text(
        "Matrícula;Nome do Aluno;Curso\n"
        "IQ2026001;Carlos Eduardo;Engenharia\n"
        "IQ2026002;Daniela Rocha;Informática\n",
        encoding="utf-8-sig",
    )

    alunos = load_students_from_file(csv_file)
    assert len(alunos) == 2
    assert alunos[0]["register"] == "IQ2026001"
    assert alunos[0]["name"] == "Carlos Eduardo"
    assert alunos[0]["turma"] == "Engenharia"


def test_load_students_from_excel(tmp_path: Path):
    """Testa leitura de planilha Excel (.xlsx)."""
    xlsx_file = tmp_path / "discentes.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Prontuário", "Discente", "Turma"])
    ws.append(["SP9901", "Fernanda Lima", "3A"])
    ws.append(["SP9902", "Gabriel Souza", "3B"])
    wb.save(xlsx_file)

    alunos = load_students_from_file(xlsx_file)
    assert len(alunos) == 2
    assert alunos[0]["register"] == "SP9901"
    assert alunos[0]["name"] == "Fernanda Lima"
    assert alunos[0]["turma"] == "3A"


def test_load_students_file_not_found():
    """Garante levantamento de FileNotFoundError para arquivo inexistente."""
    with pytest.raises(FileNotFoundError):
        load_students_from_file("arquivo_inexistente_123456.csv")


def test_generate_cards_pdf(tmp_path: Path):
    """Gera PDF com múltiplos estudantes e valida integridade do arquivo gerado."""
    estudantes = [
        {"register": f"SP{1000 + i}", "name": f"Aluno Número {i}", "turma": "1A"}
        for i in range(25)  # 25 alunos forçam geração de 2 páginas (21 por página em 3x7)
    ]
    out_pdf = tmp_path / "cartoes.pdf"
    opts = CardOptions(cols=3, rows=7, show_cut_lines=True, header_text="IFSP Teste", show_page_number=True)

    total = generate_cards_pdf(estudantes, out_pdf, opts)
    assert total == 25
    assert out_pdf.exists()
    assert out_pdf.stat().st_size > 1000  # PDF não-vazio com conteúdo vetorial


def test_generate_cards_html(tmp_path: Path):
    """Gera HTML e valida estrutura de páginas e células geradas."""
    estudantes = [
        {"register": "SP101", "name": "Maria Silva", "turma": "1A"},
        {"register": "SP102", "name": "João Souza", "turma": "1B"},
    ]
    out_html = tmp_path / "cartoes.html"
    opts = CardOptions(cols=2, rows=5, show_cut_lines=True, header_text="Escola Técnica")

    total = generate_cards_html(estudantes, out_html, opts)
    assert total == 2
    assert out_html.exists()

    content = out_html.read_text(encoding="utf-8")
    assert "SP101" in content
    assert "Maria Silva" in content
    assert "Escola Técnica" in content
    assert "data:image/png;base64," in content
    assert "grid-template-columns: repeat(2, 1fr)" in content
    assert "-webkit-line-clamp: 2" in content
    assert "white-space: normal" in content


def test_formatar_nome_em_linhas():
    """Valida quebra inteligente de nomes em até 2 linhas e redução suave de fonte."""
    from io import BytesIO
    from reportlab.pdfgen import canvas
    from registro.cards.generator import _formatar_nome_em_linhas

    c = canvas.Canvas(BytesIO())

    # Nome curto cabe em 1 linha
    linhas, font_sz = _formatar_nome_em_linhas(c, "Ana Silva", max_w=150, fonte="Helvetica")
    assert len(linhas) == 1
    assert linhas[0] == "ANA SILVA"
    assert font_sz == 7.0

    # Nome longo quebra em 2 linhas
    linhas, font_sz = _formatar_nome_em_linhas(
        c, "Pedro Henrique de Albuquerque Cavalcanti", max_w=90, fonte="Helvetica"
    )
    assert len(linhas) == 2
    assert "PEDRO" in linhas[0]
    assert "CAVALCANTI" in linhas[1]

    # Nome excessivamente longo quebra em 2 linhas e ajusta para a menor fonte
    linhas_longo, font_sz_longo = _formatar_nome_em_linhas(
        c,
        "Pedro Henrique de Albuquerque Cavalcanti e Silva Junior Sobrinho do Carmo",
        max_w=60,
        fonte="Helvetica",
    )
    assert len(linhas_longo) == 2
    assert font_sz_longo <= 6.0


def test_generate_cards_pdf_with_multiline_names(tmp_path: Path):
    """Gera PDF com nomes de comprimentos variados validando a robustez do leiaute."""
    estudantes = [
        {"register": "SP001", "name": "Ana", "turma": "1A"},
        {"register": "SP002", "name": "João da Silva Sauro Cavalcanti de Albuquerque", "turma": "1A"},
        {"register": "SP003", "name": "Maria Eduarda Santos Rodrigues Ferreira da Costa", "turma": "2B"},
    ]
    out_pdf = tmp_path / "cartoes_nomes_longos.pdf"
    opts = CardOptions(cols=3, rows=7)
    total = generate_cards_pdf(estudantes, out_pdf, opts)
    assert total == 3
    assert out_pdf.exists()
    assert out_pdf.stat().st_size > 1000

