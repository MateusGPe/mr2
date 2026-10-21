"""
Testes unitários para padrões, detecção de tipos e normalização em registro.nucleo.importar.patterns_find.
"""

from registro.nucleo.importar import patterns_find


def test_checar_prontuario():
    """Valida regex e formatos aceitos de prontuário."""
    assert patterns_find.checar_prontuario("IQ3001234") == "IQ3001234"
    assert patterns_find.checar_prontuario("  sp3098765  ") == "SP3098765"
    assert patterns_find.checar_prontuario("ABC12345X") == "ABC12345X"

    # Inválidos
    assert patterns_find.checar_prontuario("123") is None
    assert patterns_find.checar_prontuario("") is None
    assert patterns_find.checar_prontuario(None) is None
    assert patterns_find.checar_prontuario("A123") is None


def test_checar_nome():
    """Valida identificação de nomes e exclusão de palavras proibidas ou números."""
    assert patterns_find.checar_nome("Carlos Eduardo da Silva") == "Carlos Eduardo da Silva"
    assert patterns_find.checar_nome("ana maria") == "Ana Maria"

    # Inválidos: números, palavra única ou palavras de cardápio
    assert patterns_find.checar_nome("Carlos123") is None
    assert patterns_find.checar_nome("Carlos") is None
    assert patterns_find.checar_nome("Prato Vegetariano") is None
    assert patterns_find.checar_nome("") is None
    assert patterns_find.checar_nome(None) is None


def test_checar_data_e_obter_data():
    """Valida conversão e normalização de datas em múltiplos formatos."""
    assert patterns_find.checar_data("21/10/2026") == "21/10/2026"
    assert patterns_find.checar_data("2026-10-21") == "21/10/2026"
    assert patterns_find.checar_data("21-10-2026 12:30:00") == "21/10/2026"

    # Inválidos
    assert patterns_find.checar_data("data-invalida") is None
    assert patterns_find.checar_data("") is None
    assert patterns_find.checar_data(None) is None


def test_checar_turma():
    """Valida regex para nomenclatura padrão de turmas."""
    assert patterns_find.checar_turma("1º A - MEC") == "1º A - MEC"
    assert patterns_find.checar_turma("2ª B - INFO") == "2ª B - INFO"
    assert patterns_find.checar_turma("Texto Qualquer Sem Padrao") is None
    assert patterns_find.checar_turma("") is None


def test_detectar_tipo_coluna():
    """Testa inferência vertical de tipo de dados de uma coluna."""
    col_prontuarios = ["IQ3001001", "IQ3001002", "IQ3001003", "invalido"]
    assert patterns_find.detectar_tipo_coluna(col_prontuarios, limiar=0.7) == "prontuario"

    col_nomes = ["João Silva", "Maria Souza", "Carlos Ferreira", ""]
    assert patterns_find.detectar_tipo_coluna(col_nomes, limiar=0.7) == "nome"

    col_datas = ["21/10/2026", "22/10/2026", "23/10/2026"]
    assert patterns_find.detectar_tipo_coluna(col_datas) == "data"

    assert patterns_find.detectar_tipo_coluna([]) is None
    assert patterns_find.detectar_tipo_coluna(["", "  "]) is None


def test_ajustar_chaves_e_valores():
    """Testa mapeamento de cabeçalhos e formatação de valores."""
    entrada = {
        "Matrícula": "  iq3001234 ",
        "Nome": "joão da silva",
        "Turma": "1º A - MEC",
        "Data": "2026-10-21",
    }
    saida = patterns_find.ajustar_chaves_e_valores(entrada)

    assert saida["prontuario"] == "IQ3001234"
    assert saida["nome"] == "João da Silva"
    assert saida["turma"] == "1º A - MEC"
    assert saida["data"] == "21/10/2026"
