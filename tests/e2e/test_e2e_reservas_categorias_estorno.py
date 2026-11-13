# ----------------------------------------------------------------------------
# Arquivo: tests/e2e/test_e2e_reservas_categorias_estorno.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Testes E2E rigorosos para:
1. Vínculo pontual de categorias na reserva (sem contaminar o perfil permanente do estudante).
2. Ciclo completo de estorno (soft delete), reuso controlado de reserva, auditoria e reatendimento.
3. Cancelamento/reativação de reserva, atualização de prato/horário e exclusividade de turnos.
"""

from contextlib import contextmanager
from unittest.mock import patch

import pytest

from registro.nucleo import constants
from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.models import Consumo
from registro.nucleo.services import grade_horarios_service


@contextmanager
def _fixar_relogio(hora_hm: str, dia_semana: str = "segunda"):
    weekday_map = {
        "segunda": 0,
        "terca": 1,
        "quarta": 2,
        "quinta": 3,
        "sexta": 4,
        "sabado": 5,
        "domingo": 6,
    }
    hora_hms = f"{hora_hm}:00"
    with patch("registro.nucleo.services.consumo_service.datetime") as mock_dt_c, \
         patch("registro.nucleo.services.grade_horarios_service.datetime") as mock_dt_g:
        mock_dt_c.now.return_value.strftime.side_effect = (
            lambda fmt: hora_hm if fmt == "%H:%M" else hora_hms
        )
        mock_dt_g.now.return_value.strftime.side_effect = (
            lambda fmt: hora_hm if fmt == "%H:%M" else hora_hms
        )
        mock_dt_g.now.return_value.weekday.return_value = weekday_map.get(dia_semana, 0)
        yield


def test_categoria_pontual_na_reserva_vale_apenas_na_data_e_nao_contamina_estudante(
    facade: FachadaRegistro,
    criar_grupo,
    criar_estudante,
    tmp_path,
    monkeypatch,
):
    """
    Cenário:
    - Aluno regular (1º A, sem categorias fixas).
    - Recebe reserva no Dia 1 (segunda) com categoria pontual `PAP`.
    - No Dia 1, no slot exclusivo para `PAP`, o aluno é autorizado e registrado como `PAP`.
    - No Dia 2 (terça), com reserva regular (sem categoria pontual), o aluno NÃO herda `PAP`
      e é bloqueado no slot exclusivo para `PAP`, provando ausência de contaminação permanente.
    """
    caminho_grade = tmp_path / "grade_horarios.json"
    monkeypatch.setattr(grade_horarios_service, "CAMINHO_GRADE_HORARIOS", caminho_grade)
    monkeypatch.setattr(constants, "CAMINHO_GRADE_HORARIOS", caminho_grade)

    grade_horarios_service.salvar_grade_horarios(
        {
            "segunda": {
                "almoco": [
                    {"inicio": "12:00", "fim": "12:30", "turmas": ["*"], "categorias": ["PAP"]},
                ]
            },
            "terca": {
                "almoco": [
                    {"inicio": "12:00", "fim": "12:30", "turmas": ["*"], "categorias": ["PAP"]},
                ]
            },
        },
        caminho_grade,
    )

    turma = criar_grupo(nome="1º A", tipo="turma")
    aluno = criar_estudante(prontuario="IQ3040001", nome="Aluno Pontual", grupos=[turma])

    # Reserva Dia 1 com vínculo pontual PAP
    res_d1 = facade.criar_reserva(
        aluno.prontuario,
        {
            "data": "10/11/2026",
            "prato": "Especial",
            "almoco": True,
            "jantar": False,
            "categorias": ["PAP"],
        },
    )
    assert res_d1["categorias"] == ["PAP"]

    # Reserva Dia 2 sem categoria pontual
    res_d2 = facade.criar_reserva(
        aluno.prontuario,
        {
            "data": "11/11/2026",
            "prato": "Tradicional",
            "almoco": True,
            "jantar": False,
        },
    )
    assert res_d2["categorias"] == []

    # Perfil permanente do aluno continua sem categoria
    perfil = facade.repo_estudante.ler_um(aluno.id)
    assert [g.nome for g in perfil.grupos if g.eh_categoria] == []

    # Dia 1 (segunda, 12:10): autorizado como PAP
    id_s1 = facade.iniciar_nova_sessao({
        "refeicao": "almoço",
        "periodo": "Tarde",
        "data": "2026-11-10",
        "hora": "12:00",
        "grupos": ["1º A"],
    })
    assert id_s1 is not None

    elegiveis_d1 = facade.obter_estudantes_para_sessao(consumido=False)
    assert len(elegiveis_d1) == 1
    assert elegiveis_d1[0]["categoria"] == "PAP"

    with _fixar_relogio("12:10", "segunda"):
        reg_d1 = facade.registrar_consumo(aluno.prontuario)
        assert reg_d1["autorizado"] is True
        assert reg_d1["categoria"] == "PAP"

    # Dia 2 (terça, 12:10): bloqueado no slot exclusivo PAP pois não possui categoria permanente
    id_s2 = facade.iniciar_nova_sessao({
        "refeicao": "almoço",
        "periodo": "Tarde",
        "data": "2026-11-11",
        "hora": "12:00",
        "grupos": ["1º A"],
    })
    assert id_s2 is not None

    with _fixar_relogio("12:10", "terca"):
        reg_d2 = facade.registrar_consumo(aluno.prontuario)
        assert reg_d2["autorizado"] is False
        assert "não possui autorização" in reg_d2["motivo"]


def test_ciclo_estorno_reuso_reserva_cancelamento_reativacao_e_edicao(
    facade: FachadaRegistro,
    db_session,
    criar_grupo,
    criar_estudante,
):
    """
    Valida todo o ciclo de mutações em reservas e consumos:
    1. Reserva Almoço+Jantar: consumo de almoço bloqueia reuso em 2ª sessão de almoço.
    2. Estorno (soft delete) do almoço grava auditoria completa e libera a reserva para reatendimento.
    3. Cancelar reserva impede consumo mesmo na sessão ativa; reativar reserva volta a permitir.
    4. `atualizar_consumo` altera hora_consumo e prato da reserva vinculada.
    5. Estorno de lanche libera a cota do mesmo período para novo registro.
    """
    turma = criar_grupo(nome="3º MEC", tipo="turma")
    aluno = criar_estudante(prontuario="IQ3050001", nome="Mariana Ciclo", grupos=[turma])

    res = facade.criar_reserva(
        aluno.prontuario,
        {"data": "10/11/2026", "prato": "Frango", "almoco": True, "jantar": True},
    )
    id_reserva = res["id"]

    # Sessões de Almoço 1, Almoço 2 e Jantar no mesmo dia
    id_alm_1 = facade.iniciar_nova_sessao({
        "refeicao": "almoço",
        "periodo": "Tarde",
        "data": "2026-11-10",
        "hora": "11:30",
        "grupos": ["3º MEC"],
    })
    id_alm_2 = facade.iniciar_nova_sessao({
        "refeicao": "almoço",
        "periodo": "Tarde",
        "data": "2026-11-10",
        "hora": "12:30",
        "grupos": ["3º MEC"],
    })
    id_jan = facade.iniciar_nova_sessao({
        "refeicao": "jantar",
        "periodo": "Noite",
        "data": "2026-11-10",
        "hora": "19:00",
        "grupos": ["3º MEC"],
    })

    # 1. Consome almoço na sessão 1
    facade.id_sessao_ativa = id_alm_1
    r1 = facade.registrar_consumo(aluno.prontuario)
    assert r1["autorizado"] is True

    # 2. Tentativa na sessão 2 de almoço -> bloqueada pela cota diária
    facade.id_sessao_ativa = id_alm_2
    r2_dup = facade.registrar_consumo(aluno.prontuario)
    assert r2_dup["autorizado"] is False

    # 3. Estorno do consumo na sessão 1
    facade.id_sessao_ativa = id_alm_1
    ok_estorno = facade.desfazer_consumo_por_prontuario(
        aluno.prontuario, operador="Maria Operadora", motivo="Leitura acidental"
    )
    assert ok_estorno is True

    consumo_cancelado = (
        db_session.query(Consumo)
        .filter_by(estudante_id=aluno.id, sessao_id=id_alm_1, ativo=False)
        .one()
    )
    assert consumo_cancelado.deletado_por == "Maria Operadora"
    assert consumo_cancelado.motivo_cancelamento == "Leitura acidental"
    assert consumo_cancelado.deletado_em is not None

    # 4. Cancela a reserva antes do reatendimento -> agora não pode mais consumir
    facade.cancelar_reserva(id_reserva)
    facade.id_sessao_ativa = id_alm_2
    r_canc = facade.registrar_consumo(aluno.prontuario)
    assert r_canc["autorizado"] is False

    # 5. Reativa reserva e consome almoço na sessão 2 + atualiza prato/horário
    facade.reativar_reserva(id_reserva)
    r_reat = facade.registrar_consumo(aluno.prontuario)
    assert r_reat["autorizado"] is True
    assert r_reat["prato"] == "Frango"

    consumo_ativo = facade.repo_consumo.por_prontuario_e_sessao(aluno.prontuario, id_alm_2)
    assert consumo_ativo is not None
    assert facade.atualizar_consumo(consumo_ativo.id, hora_consumo="12:34:56", prato="Omelete") is True
    db_session.refresh(consumo_ativo)
    assert consumo_ativo.hora_consumo == "12:34:56"
    assert consumo_ativo.reserva.prato == "Omelete"

    # 6. Mesmo após estorno+reatendimento no almoço, jantar da mesma reserva continua liberado
    facade.id_sessao_ativa = id_jan
    r_jan = facade.registrar_consumo(aluno.prontuario)
    assert r_jan["autorizado"] is True
    assert r_jan["prato"] == "Omelete"

    # 7. Lanche: estorno libera cota do mesmo período
    facade.iniciar_nova_sessao({
        "refeicao": "lanche",
        "periodo": "Vespertino",
        "data": "2026-11-10",
        "hora": "15:30",
        "item_servido": "Maçã",
        "grupos": ["3º MEC"],
    })
    assert facade.registrar_consumo(aluno.prontuario)["autorizado"] is True
    assert facade.desfazer_consumo_por_prontuario(aluno.prontuario) is True
    assert facade.registrar_consumo(aluno.prontuario)["autorizado"] is True


def test_validacao_turnos_reserva_impede_reserva_sem_almoco_nem_jantar(
    facade: FachadaRegistro,
    criar_estudante,
):
    """Reserva não pode ser criada nem atualizada com almoco=False e jantar=False."""
    est = criar_estudante(prontuario="IQ3050099", nome="Sem Turno")

    with pytest.raises(ValueError, match="pelo menos Almoço ou Jantar"):
        facade.criar_reserva(
            est.prontuario,
            {"data": "10/11/2026", "almoco": False, "jantar": False},
        )

    res = facade.criar_reserva(
        est.prontuario,
        {"data": "10/11/2026", "almoco": True, "jantar": False},
    )
    with pytest.raises(ValueError, match="pelo menos Almoço ou Jantar"):
        facade.atualizar_reserva(res["id"], {"almoco": False, "jantar": False})
