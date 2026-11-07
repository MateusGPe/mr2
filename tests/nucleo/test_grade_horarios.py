"""
Testes unitários para o serviço de grade horária semanal e validação de janelas (grade_horarios_service).
"""

from pathlib import Path
from registro.nucleo.services import grade_horarios_service


def test_validar_janela_horario_no_slot(tmp_path: Path):
    caminho_grade = tmp_path / "grade_teste.json"
    grade = {
        "segunda": {
            "almoco": [
                {"inicio": "12:00", "fim": "12:30", "turmas": ["1º A", "1º B"]},
                {"inicio": "12:30", "fim": "13:00", "turmas": ["2º A", "2º B"]},
            ],
            "jantar": [],
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho_grade)

    # Aluno da turma 1º A tentando às 12:15 (dentro do slot 12:00 - 12:30)
    autorizado, motivo = grade_horarios_service.validar_janela_horario(
        turmas_estudante=["1º A"],
        refeicao="almoço",
        hora_atual="12:15",
        dia_semana="segunda",
        caminho_grade=caminho_grade,
    )
    assert autorizado is True
    assert motivo == ""


def test_validar_janela_horario_tolerancia(tmp_path: Path):
    caminho_grade = tmp_path / "grade_teste.json"
    grade = {
        "segunda": {
            "almoco": [
                {"inicio": "12:00", "fim": "12:30", "turmas": ["1º A"]},
            ]
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho_grade)

    # 5 minutos antes (11:55) -> Deve autorizar por tolerância
    autorizado, _ = grade_horarios_service.validar_janela_horario(
        turmas_estudante=["1º A"],
        refeicao="almoço",
        hora_atual="11:55",
        dia_semana="segunda",
        tolerancia_min=5,
        caminho_grade=caminho_grade,
    )
    assert autorizado is True

    # 6 minutos antes (11:54) -> Deve bloquear
    autorizado, motivo = grade_horarios_service.validar_janela_horario(
        turmas_estudante=["1º A"],
        refeicao="almoço",
        hora_atual="11:54",
        dia_semana="segunda",
        tolerancia_min=5,
        caminho_grade=caminho_grade,
    )
    assert autorizado is False
    assert "Fora do horário da sua turma" in motivo


def test_validar_janela_horario_turma_em_outro_slot(tmp_path: Path):
    caminho_grade = tmp_path / "grade_teste.json"
    grade = {
        "segunda": {
            "almoco": [
                {"inicio": "12:00", "fim": "12:30", "turmas": ["1º A"]},
                {"inicio": "12:30", "fim": "13:00", "turmas": ["2º A"]},
            ]
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho_grade)

    # Aluno da turma 2º A tentando consumir às 12:10 (slot da 1º A)
    autorizado, motivo = grade_horarios_service.validar_janela_horario(
        turmas_estudante=["2º A"],
        refeicao="almoço",
        hora_atual="12:10",
        dia_semana="segunda",
        caminho_grade=caminho_grade,
    )
    assert autorizado is False
    assert "Fora do horário da sua turma. Seu horário: 12:30 às 13:00." in motivo


def test_validar_janela_horario_fallback_sem_grade(tmp_path: Path):
    caminho_grade = tmp_path / "grade_teste.json"
    grade = {
        "terca": {
            "almoco": [],
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho_grade)

    # Dia sem slots definidos -> Fallback permite validação livre
    autorizado, motivo = grade_horarios_service.validar_janela_horario(
        turmas_estudante=["1º A"],
        refeicao="almoço",
        hora_atual="12:10",
        dia_semana="terca",
        caminho_grade=caminho_grade,
    )
    assert autorizado is True
    assert motivo == ""


def test_obter_turmas_previstas_para_refeicao(tmp_path: Path):
    caminho_grade = tmp_path / "grade_teste.json"
    grade = {
        "segunda": {
            "jantar": [
                {"inicio": "18:30", "fim": "19:15", "turmas": ["1º BEM", "SLL"]},
                {"inicio": "19:15", "fim": "20:00", "turmas": ["2º BEM", "3º BEM"]},
            ]
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho_grade)

    turmas = grade_horarios_service.obter_turmas_previstas_para_refeicao(
        dia_semana="segunda",
        refeicao="jantar",
        caminho_grade=caminho_grade,
    )
    assert turmas == ["1º BEM", "2º BEM", "3º BEM", "SLL"]

