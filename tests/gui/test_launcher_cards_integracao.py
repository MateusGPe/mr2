"""
Testes de integração do módulo Cards, CLI do launcher e grade de horários na fachada.
"""

from registro.launcher import executar_cards, identificar_alvo_cli
from registro.nucleo.facade import FachadaRegistro


def test_launcher_cli_cards():
    """Garante que flags CLI para cards apontam para executar_cards."""
    assert identificar_alvo_cli(["--cards"]) == executar_cards
    assert identificar_alvo_cli(["/cards"]) == executar_cards
    assert identificar_alvo_cli(["cards"]) == executar_cards
    assert identificar_alvo_cli(["--crachas"]) == executar_cards


def test_facade_grade_horarios_metodos(facade: FachadaRegistro):
    """Testa métodos de grade horária expostos pela FachadaRegistro."""
    dia = facade.obter_dia_semana_atual()
    assert dia in ("segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo")

    grade = facade.obter_grade_horarios()
    assert isinstance(grade, dict)
    assert "segunda" in grade

    turmas = facade.obter_turmas_previstas_para_refeicao(
        refeicao="almoco", dia_semana="segunda"
    )
    assert isinstance(turmas, list)
