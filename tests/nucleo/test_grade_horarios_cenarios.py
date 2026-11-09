# ----------------------------------------------------------------------------
# Arquivo: tests/nucleo/test_grade_horarios_cenarios.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Testes exaustivos de casos de uso (prováveis, improváveis e extremos) para
o serviço de grade horária semanal (grade_horarios_service).
"""

from pathlib import Path
from unittest.mock import patch

from registro.nucleo.services import grade_horarios_service


# ============================================================================
# 1. Testes de Parser e Conversão de Planilha (converter_linhas_configuracao_para_grade)
# ============================================================================


def test_converter_linhas_configuracao_variacoes_ortograficas_dias_e_refeicoes():
    """Verifica se variações de grafia e acentuação de dias e refeições são reconhecidas."""
    linhas = [
        ["Dia", "Refeição", "Início", "Fim", "Turmas", "Categorias"],  # Cabeçalho
        ["seg", "almoço", "11:30", "12:15", "1º INFO, 1º MEC", "REGULAR"],
        ["terça-feira", "almoco", "12:00", "12:30", "2º INFO", "TODAS"],
        ["quarta", "jantar", "18:30", "19:15", "3º INFO", "*"],
        ["qui", "lanche", "09:30", "09:50", "Todas", "PAP"],
        ["sexta-feira", "almoco", "11:45", "12:30", "*", "REGULAR, PAP"],
        ["sábado", "almoço", "12:00", "12:45", "SAB_TURMA", "REGULAR"],
        ["domingo", "lanche", "16:00", "16:30", "DOM_TURMA", "*"],
    ]

    grade = grade_horarios_service.converter_linhas_configuracao_para_grade(linhas)

    # Segunda - almoço
    assert len(grade["segunda"]["almoco"]) == 1
    assert grade["segunda"]["almoco"][0]["inicio"] == "11:30"
    assert grade["segunda"]["almoco"][0]["turmas"] == ["1º INFO", "1º MEC"]
    assert grade["segunda"]["almoco"][0]["categorias"] == ["REGULAR"]

    # Terça - almoço
    assert len(grade["terca"]["almoco"]) == 1
    assert grade["terca"]["almoco"][0]["turmas"] == ["2º INFO"]
    assert grade["terca"]["almoco"][0]["categorias"] == ["*"]

    # Quarta - jantar
    assert len(grade["quarta"]["jantar"]) == 1
    assert grade["quarta"]["jantar"][0]["categorias"] == ["*"]

    # Quinta - lanche
    assert len(grade["quinta"]["lanche"]) == 1
    assert grade["quinta"]["lanche"][0]["turmas"] == ["*"]
    assert grade["quinta"]["lanche"][0]["categorias"] == ["PAP"]

    # Sexta - almoço
    assert len(grade["sexta"]["almoco"]) == 1
    assert grade["sexta"]["almoco"][0]["turmas"] == ["*"]
    assert grade["sexta"]["almoco"][0]["categorias"] == ["REGULAR", "PAP"]

    # Sábado e Domingo
    assert len(grade["sabado"]["almoco"]) == 1
    assert len(grade["domingo"]["lanche"]) == 1


def test_converter_linhas_configuracao_linhas_vazias_e_malformadas():
    """Cenário improvável: linhas vazias, horários inválidos ou colunas ausentes."""
    linhas = [
        [],  # Linha vazia
        ["", "  ", ""],  # Linha em branco
        ["segunda", "almoco", "invalido", "12:30", "1º INFO"],  # Hora inválida
        ["segunda", "almoco", "12:00", "25:99", "1º INFO"],  # Minutos inválidos
        ["dia da semana", "tipo", "hora 1", "hora 2"],  # Cabeçalho alternativo
        ["segunda", "refeicao_desconhecida", "12:00", "12:30", "1º INFO"],  # Refeição inválida
        ["dia_alienigena", "almoco", "12:00", "12:30", "1º INFO"],  # Dia inválido
        ["segunda", "almoco"],  # Sem início e fim
        ["segunda", "almoco", "12:00", "12:30"],  # Sem turmas nem categorias (deve aceitar vazio)
    ]

    grade = grade_horarios_service.converter_linhas_configuracao_para_grade(linhas)

    # Apenas a última linha válida deve ter sido convertida
    assert len(grade["segunda"]["almoco"]) == 1
    slot = grade["segunda"]["almoco"][0]
    assert slot["inicio"] == "12:00"
    assert slot["fim"] == "12:30"
    assert slot["turmas"] == []
    assert slot["categorias"] == []


# ============================================================================
# 2. Testes de Persistência, Criação e Resiliência de Arquivo
# ============================================================================


def test_carregar_grade_horarios_arquivo_inexistente(tmp_path: Path):
    """Arquivo não existe: deve criar no disco com GRADE_PADRAO e retornar estrutura padrão."""
    arquivo = tmp_path / "subdir" / "grade_nova.json"
    assert not arquivo.exists()

    grade = grade_horarios_service.carregar_grade_horarios(arquivo)
    assert arquivo.exists()
    assert "segunda" in grade
    assert "almoco" in grade["segunda"]
    assert grade["segunda"]["almoco"] == []


def test_carregar_grade_horarios_arquivo_corrompido(tmp_path: Path):
    """Cenário improvável: JSON inválido no disco recupera silenciosamente GRADE_PADRAO."""
    arquivo = tmp_path / "grade_corrompida.json"
    arquivo.write_text("{conteudo: invalido, truncado...", encoding="utf-8")

    grade = grade_horarios_service.carregar_grade_horarios(arquivo)
    assert isinstance(grade, dict)
    assert "segunda" in grade
    assert grade["segunda"]["almoco"] == []


def test_salvar_grade_horarios_sucesso_e_falha(tmp_path: Path):
    """Testa salvamento com criação de diretórios intermediários e falha com caminho inválido."""
    caminho = tmp_path / "a" / "b" / "c" / "grade.json"
    grade_exemplo = {"segunda": {"almoco": [{"inicio": "11:30", "fim": "12:00"}]}}

    ok = grade_horarios_service.salvar_grade_horarios(grade_exemplo, caminho)
    assert ok is True
    assert caminho.exists()

    # Falha simulada ao salvar
    with patch("builtins.open", side_effect=PermissionError("Acesso negado")):
        falhou = grade_horarios_service.salvar_grade_horarios(grade_exemplo, caminho)
        assert falhou is False


# ============================================================================
# 3. Testes de Janela de Horário, Tolerância e Fronteiras Exatas
# ============================================================================


def test_validar_janela_horario_fronteiras_exatas(tmp_path: Path):
    """
    Testa cada minuto ao redor da janela 12:00 - 12:30 com tolerância de 5 min:
    - 11:54 -> Bloqueado (-6 min)
    - 11:55 -> Autorizado (-5 min, limite inferior de tolerância)
    - 12:00 -> Autorizado (início exato)
    - 12:15 -> Autorizado (meio)
    - 12:30 -> Autorizado (fim exato)
    - 12:35 -> Autorizado (+5 min, limite superior de tolerância)
    - 12:36 -> Bloqueado (+6 min)
    """
    caminho = tmp_path / "grade.json"
    grade = {
        "segunda": {
            "almoco": [{"inicio": "12:00", "fim": "12:30", "turmas": ["1º A"], "categorias": ["REGULAR"]}]
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho)

    params = {
        "turmas_estudante": ["1º A"],
        "refeicao": "almoço",
        "dia_semana": "segunda",
        "categoria_estudante": "REGULAR",
        "tolerancia_min": 5,
        "caminho_grade": caminho,
    }

    # 11:54 -> Fora
    ok, motivo = grade_horarios_service.validar_janela_horario(**params, hora_atual="11:54")
    assert ok is False
    assert "Fora do horário" in motivo

    # 11:55 -> Dentro da tolerância
    ok, _ = grade_horarios_service.validar_janela_horario(**params, hora_atual="11:55")
    assert ok is True

    # 12:00 -> Início
    ok, _ = grade_horarios_service.validar_janela_horario(**params, hora_atual="12:00")
    assert ok is True

    # 12:15 -> Meio
    ok, _ = grade_horarios_service.validar_janela_horario(**params, hora_atual="12:15")
    assert ok is True

    # 12:30 -> Fim
    ok, _ = grade_horarios_service.validar_janela_horario(**params, hora_atual="12:30")
    assert ok is True

    # 12:35 -> Limite da tolerância
    ok, _ = grade_horarios_service.validar_janela_horario(**params, hora_atual="12:35")
    assert ok is True

    # 12:36 -> Fora
    ok, motivo = grade_horarios_service.validar_janela_horario(**params, hora_atual="12:36")
    assert ok is False


def test_validar_janela_horario_tolerancia_zero(tmp_path: Path):
    """Com tolerância 0, 11:59 e 12:31 devem ser bloqueados para slot 12:00 - 12:30."""
    caminho = tmp_path / "grade.json"
    grade = {
        "segunda": {
            "almoco": [{"inicio": "12:00", "fim": "12:30", "turmas": ["1º A"]}]
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho)

    ok, _ = grade_horarios_service.validar_janela_horario(
        turmas_estudante=["1º A"],
        refeicao="almoço",
        hora_atual="11:59",
        dia_semana="segunda",
        tolerancia_min=0,
        caminho_grade=caminho,
    )
    assert ok is False

    ok, _ = grade_horarios_service.validar_janela_horario(
        turmas_estudante=["1º A"],
        refeicao="almoço",
        hora_atual="12:00",
        dia_semana="segunda",
        tolerancia_min=0,
        caminho_grade=caminho,
    )
    assert ok is True


# ============================================================================
# 4. Testes de Filtro de Categorias (REGULAR vs PAP vs TODAS)
# ============================================================================


def test_validar_janela_horario_restricao_categoria(tmp_path: Path):
    """Verifica bloqueio específico e mensagem contextualizada por categoria."""
    caminho = tmp_path / "grade.json"
    grade = {
        "segunda": {
            "almoco": [
                {
                    "inicio": "12:00",
                    "fim": "12:30",
                    "turmas": ["1º A"],
                    "categorias": ["PAP"],
                }
            ]
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho)

    # Aluno da turma 1º A, mas REGULAR -> Bloqueado por categoria
    ok, motivo = grade_horarios_service.validar_janela_horario(
        turmas_estudante=["1º A"],
        refeicao="almoço",
        hora_atual="12:15",
        dia_semana="segunda",
        categoria_estudante="REGULAR",
        caminho_grade=caminho,
    )
    assert ok is False
    assert "Categoria 'REGULAR' não permitida neste horário. Permitidas: PAP." in motivo

    # Aluno PAP -> Autorizado
    ok, motivo = grade_horarios_service.validar_janela_horario(
        turmas_estudante=["1º A"],
        refeicao="almoço",
        hora_atual="12:15",
        dia_semana="segunda",
        categoria_estudante="PAP",
        caminho_grade=caminho,
    )
    assert ok is True
    assert motivo == ""


def test_validar_janela_horario_curingas_turmas_e_categorias(tmp_path: Path):
    """Slots com '*' ou 'TODAS' autorizam qualquer turma e qualquer categoria."""
    caminho = tmp_path / "grade.json"
    grade = {
        "segunda": {
            "almoco": [
                {
                    "inicio": "12:00",
                    "fim": "12:30",
                    "turmas": ["*"],
                    "categorias": ["TODAS"],
                }
            ]
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho)

    ok, _ = grade_horarios_service.validar_janela_horario(
        turmas_estudante=["Qualquer Turma X"],
        refeicao="almoço",
        hora_atual="12:15",
        dia_semana="segunda",
        categoria_estudante="CATEGORIA_ESPECIAL",
        caminho_grade=caminho,
    )
    assert ok is True


# ============================================================================
# 5. Cenários Improváveis: Múltiplas Turmas, Hora Inválida, Fallbacks
# ============================================================================


def test_validar_janela_horario_discente_multiplas_turmas(tmp_path: Path):
    """Discente matriculado em múltiplas turmas (ex: regular + monitoria): qualquer match autoriza."""
    caminho = tmp_path / "grade.json"
    grade = {
        "segunda": {
            "almoco": [
                {"inicio": "12:00", "fim": "12:30", "turmas": ["1º A"]},
                {"inicio": "12:30", "fim": "13:00", "turmas": ["MONITORIA"]},
            ]
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho)

    # Discente com ['2º B', 'MONITORIA'] tentando às 12:45 -> Autorizado pelo match com MONITORIA
    ok, _ = grade_horarios_service.validar_janela_horario(
        turmas_estudante=["2º B", "MONITORIA"],
        refeicao="almoço",
        hora_atual="12:45",
        dia_semana="segunda",
        caminho_grade=caminho,
    )
    assert ok is True


def test_validar_janela_horario_hora_invalida_fallback_livre(tmp_path: Path):
    """Cenário improvável: se uma string de hora inválida for fornecida, faz fallback para permitir."""
    caminho = tmp_path / "grade.json"
    grade = {
        "segunda": {
            "almoco": [{"inicio": "12:00", "fim": "12:30", "turmas": ["1º A"]}]
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho)

    ok, motivo = grade_horarios_service.validar_janela_horario(
        turmas_estudante=["1º A"],
        refeicao="almoço",
        hora_atual="formato_invalido",
        dia_semana="segunda",
        caminho_grade=caminho,
    )
    assert ok is True
    assert motivo == ""


def test_validar_janela_horario_turma_nao_prevista_em_nenhum_slot(tmp_path: Path):
    """Discente cuja turma nem consta na grade do dia."""
    caminho = tmp_path / "grade.json"
    grade = {
        "segunda": {
            "almoco": [
                {"inicio": "12:00", "fim": "12:30", "turmas": ["1º A"]},
                {"inicio": "12:30", "fim": "13:00", "turmas": ["2º A"]},
            ]
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho)

    # Tentativa durante um slot ativo (12:15)
    ok, motivo = grade_horarios_service.validar_janela_horario(
        turmas_estudante=["Turma Fantasma"],
        refeicao="almoço",
        hora_atual="12:15",
        dia_semana="segunda",
        caminho_grade=caminho,
    )
    assert ok is False
    assert "Sua turma ou categoria não possui autorização" in motivo

    # Tentativa fora de qualquer slot ativo (14:00)
    ok, motivo = grade_horarios_service.validar_janela_horario(
        turmas_estudante=["Turma Fantasma"],
        refeicao="almoço",
        hora_atual="14:00",
        dia_semana="segunda",
        caminho_grade=caminho,
    )
    assert ok is False
    assert "Horário de refeição encerrado ou não iniciado para sua turma." in motivo


def test_obter_turmas_previstas_deduplicacao_e_curingas(tmp_path: Path):
    """Testa se turmas são ordenadas, desduplicadas e curingas são ignorados."""
    caminho = tmp_path / "grade.json"
    grade = {
        "segunda": {
            "almoco": [
                {"inicio": "12:00", "fim": "12:30", "turmas": ["2º BEM", "1º BEM", "*"]},
                {"inicio": "12:30", "fim": "13:00", "turmas": ["1º BEM", "TODAS", "3º BEM"]},
            ]
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho)

    turmas = grade_horarios_service.obter_turmas_previstas_para_refeicao(
        dia_semana="segunda",
        refeicao="almoço",
        caminho_grade=caminho,
    )
    assert turmas == ["1º BEM", "2º BEM", "3º BEM"]

