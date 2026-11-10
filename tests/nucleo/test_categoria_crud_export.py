"""
Testes para criação, atualização, importação e exportação com categoria de discentes.
"""

from pathlib import Path
from registro.nucleo.facade import FachadaRegistro


def test_criar_e_atualizar_estudante_com_categoria(facade: FachadaRegistro):
    """Testa criação e atualização de estudante definindo categoria PAP e REGULAR."""
    aluno = facade.criar_estudante("IQ3009901", "Aluno PAP Teste", categoria="PAP")
    assert aluno["categoria"] == "PAP"

    # Atualiza para REGULAR
    facade.atualizar_estudante(aluno["id"], {"categoria": "REGULAR"})
    aluno_db = facade.repo_estudante.por_ids({aluno["id"]})[0]
    assert aluno_db.categoria == "REGULAR"


def test_salvar_importacao_preserva_categoria(facade: FachadaRegistro):
    """Garante que a rotina salvar_importacao_dados não descarta a categoria."""
    dados_importados = [
        {
            "prontuario": "IQ3008801",
            "nome": "Estudante Importado PAP",
            "data": "2026-11-09",
            "prato": "Geral",
            "categoria": "PAP",
        },
        {
            "prontuario": "IQ3008802",
            "nome": "Estudante Importado Regular",
            "data": "2026-11-09",
            "prato": "Vegetariano",
            "categoria": "REGULAR",
        },
    ]

    res = facade.salvar_importacao_dados(dados_importados)
    assert res["estudantes_criados"] == 2

    e1 = facade.repo_estudante.por_prontuarios({"IQ3008801"})[0]
    assert e1 is not None
    assert e1.categoria == "PAP"

    e2 = facade.repo_estudante.por_prontuarios({"IQ3008802"})[0]
    assert e2 is not None
    assert e2.categoria == "REGULAR"


def test_exportar_estudantes_inclui_coluna_categoria(facade: FachadaRegistro, tmp_path: Path):
    """Garante que as exportações CSV e XLSX incluem a coluna Categoria."""
    facade.criar_estudante("IQ3007701", "Aluno Export PAP", categoria="PAP")
    facade.criar_estudante("IQ3007702", "Aluno Export Regular", categoria="REGULAR")

    csv_path = tmp_path / "alunos.csv"
    facade.exportar_estudantes_para_csv(csv_path)
    assert csv_path.exists()
    conteudo_csv = csv_path.read_text(encoding="utf-8")
    assert "categoria" in conteudo_csv.lower()
    assert "PAP" in conteudo_csv
    assert "REGULAR" in conteudo_csv

    xlsx_path = tmp_path / "alunos.xlsx"
    facade.exportar_estudantes_para_xlsx(xlsx_path)
    assert xlsx_path.exists()
