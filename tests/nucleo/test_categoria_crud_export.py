"""
Testes para criação, atualização, importação de reservas com categoria pontual e exportação.
"""

from pathlib import Path
from registro.nucleo.facade import FachadaRegistro


def test_criar_e_atualizar_estudante_com_categoria(facade: FachadaRegistro):
    """Testa criação e atualização de estudante separando turma e múltiplas categorias."""
    aluno = facade.criar_estudante(
        "IQ3009901",
        "Aluno Categorias Teste",
        grupos=["2º A - MAC"],
        categorias=["PAP", "ESP1"],
    )
    assert aluno["categoria"] == "ESP1, PAP"

    # Atualiza removendo ESP1 e adicionando LIB0
    facade.atualizar_estudante(
        aluno["id"],
        {"nome": "Aluno Categorias Teste"},
        grupos=["2º A - MAC"],
        categorias=["LIB0"],
    )
    aluno_db = facade.repo_estudante.por_ids({aluno["id"]})[0]
    assert aluno_db.turmas_nomes == ["2º A - MAC"]
    assert aluno_db.categorias_nomes == ["LIB0"]


def test_salvar_importacao_preserva_categoria(facade: FachadaRegistro):
    """Garante que salvar_importacao_dados vincula categorias à reserva sem vincular ao estudante."""
    dados_importados = [
        {
            "prontuario": "IQ3008801",
            "nome": "Estudante Importado Optativa",
            "data": "09/11/2026",
            "prato": "Geral",
            "categoria": "ESP1, LIB0",
        },
        {
            "prontuario": "IQ3008802",
            "nome": "Estudante Importado Sem Tag",
            "data": "09/11/2026",
            "prato": "Vegetariano",
            "categoria": "REGULAR",
        },
    ]

    res = facade.salvar_importacao_dados(dados_importados)
    assert res["estudantes_criados"] == 2
    assert res["reservas_criadas"] == 2

    e1 = facade.repo_estudante.por_prontuarios_com_grupos({"IQ3008801"})[0]
    assert e1.categorias_nomes == []  # Não vinculado permanentemente ao estudante!

    reservas = facade.listar_reservas({"data": "09/11/2026"})
    mapa_res = {r["prontuario_estudante"]: r for r in reservas}
    assert mapa_res["IQ3008801"]["categorias"] == ["ESP1", "LIB0"]
    assert mapa_res["IQ3008802"]["categorias"] == []


def test_exportar_estudantes_inclui_coluna_categoria(facade: FachadaRegistro, tmp_path: Path):
    """Garante que as exportações CSV e XLSX incluem Turma e Categoria separadas."""
    facade.criar_estudante(
        "IQ3007701",
        "Aluno Export PAP",
        grupos=["1º A - MEC"],
        categorias=["PAP", "ESP1"],
    )
    facade.criar_estudante(
        "IQ3007702",
        "Aluno Export Sem Tag",
        grupos=["2º A - MAC"],
    )

    csv_path = tmp_path / "alunos.csv"
    facade.exportar_estudantes_para_csv(csv_path)
    assert csv_path.exists()
    conteudo_csv = csv_path.read_text(encoding="utf-8")
    assert "categoria" in conteudo_csv.lower()
    assert "ESP1, PAP" in conteudo_csv
    assert "1º A - MEC" in conteudo_csv

    xlsx_path = tmp_path / "alunos.xlsx"
    facade.exportar_estudantes_para_xlsx(xlsx_path)
    assert xlsx_path.exists()
