# ----------------------------------------------------------------------------
# Arquivo: tests/e2e/test_e2e_autorizacao_cotas_horarios.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Testes E2E rigorosos para:
1. Matriz de decisão de autorização (`registrar_consumo`, `registrar_consumo_com_reserva`
   e coerência estrita com `obter_estudantes_para_sessao`).
2. Cotas diárias independentes (Almoço, Jantar, Lanche por período) entre múltiplas sessões.
3. Grade horária em fronteiras exatas de minuto, tolerância, equivalência de categorias,
   `ignorar_horario_grade`, `permitir_fora_horario` e tolerância a slots inválidos.
4. Bloqueio de estudante inativo e sanitização de prontuários.
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
    """Fixa relógio e dia da semana nos serviços de consumo e grade horária."""
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


# ============================================================================
# 1. Matriz Parametrizada de Autorização (Modo Padrão vs Estrito vs GUI)
# ============================================================================


@pytest.mark.parametrize(
    "refeicao, estado_reserva, na_turma_sessao, em_excecao, pular_grupos, aluno_ativo, "
    "esperado_padrao, esperado_estrito, esperado_listado_gui",
    [
        # --- ALMOÇO (Modo Padrão autoriza reserva mesmo fora da turma da sessão; GUI alinha) ---
        ("almoço", "almoco", True, False, False, True, True, True, True),
        ("almoço", "almoco", False, False, False, True, True, False, True),
        ("almoço", "ambos", False, False, False, True, True, False, True),
        ("almoço", "jantar_only", True, False, False, True, False, False, False),
        ("almoço", "cancelada", True, False, False, True, False, False, False),
        ("almoço", "nenhuma", True, False, False, True, False, False, False),
        ("almoço", "nenhuma", False, True, False, True, True, False, True),
        ("almoço", "nenhuma", False, False, True, True, True, False, True),
        ("almoço", "almoco", True, False, True, True, True, True, True),
        # Estudante inativo sempre bloqueado mesmo com reserva e pular_grupos=True
        ("almoço", "almoco", True, False, True, False, False, False, False),
        # --- JANTAR ---
        ("jantar", "jantar_only", True, False, False, True, True, True, True),
        ("jantar", "jantar_only", False, False, False, True, True, False, True),
        ("jantar", "almoco", True, False, False, True, False, False, False),
        ("jantar", "ambos", False, True, False, True, True, True, True),
        ("jantar", "nenhuma", False, False, True, True, True, False, True),
        ("jantar", "jantar_only", True, False, False, False, False, False, False),
        # --- LANCHE (Regra baseada exclusivamente em grupos/exceção/bypass) ---
        ("lanche", "nenhuma", True, False, False, True, True, False, True),
        ("lanche", "nenhuma", False, False, False, True, False, False, False),
        ("lanche", "nenhuma", False, True, False, True, True, False, True),
        ("lanche", "nenhuma", False, False, True, True, True, False, True),
        ("lanche", "nenhuma", True, False, True, False, False, False, False),
    ],
)
def test_matriz_completa_autorizacao_e_coerencia_gui(
    facade: FachadaRegistro,
    db_session,
    criar_grupo,
    criar_estudante,
    criar_sessao,
    criar_reserva,
    refeicao,
    estado_reserva,
    na_turma_sessao,
    em_excecao,
    pular_grupos,
    aluno_ativo,
    esperado_padrao,
    esperado_estrito,
    esperado_listado_gui,
):
    """
    Valida toda a matriz combinatória de regras entre:
    - `registrar_consumo` (padrão usado pelo Totem/Operador)
    - `registrar_consumo_com_reserva` (modo estrito)
    - `obter_estudantes_para_sessao` (lista exibida na interface)
    """
    g_sessao = criar_grupo(nome="1º A", tipo="turma")
    g_fora = criar_grupo(nome="2º B", tipo="turma")
    g_exc = criar_grupo(nome="3º C", tipo="turma")

    grupos_aluno = [g_sessao if na_turma_sessao else (g_exc if em_excecao else g_fora)]
    aluno = criar_estudante(
        prontuario="IQ3000100",
        nome="Aluno Matriz",
        ativo=aluno_ativo,
        grupos=grupos_aluno,
    )

    data_br = "10/11/2026"
    if estado_reserva == "almoco":
        criar_reserva(estudante=aluno, data=data_br, almoco=True, jantar=False, prato="Frango")
    elif estado_reserva == "jantar_only":
        criar_reserva(estudante=aluno, data=data_br, almoco=False, jantar=True, prato="Sopa")
    elif estado_reserva == "ambos":
        criar_reserva(estudante=aluno, data=data_br, almoco=True, jantar=True, prato="Especial")
    elif estado_reserva == "cancelada":
        criar_reserva(estudante=aluno, data=data_br, almoco=True, jantar=True, cancelada=True)

    sessao = criar_sessao(
        refeicao=refeicao,
        data=data_br,
        hora="12:00",
        periodo="Integral",
        item_servido="Bolo" if refeicao == "lanche" else None,
        grupos=[g_sessao],
    )
    facade.id_sessao_ativa = sessao.id
    excecao = {"3º C"} if em_excecao else set()

    # 1. Verifica coerência da listagem da GUI antes de consumir
    elegiveis = facade.obter_estudantes_para_sessao(
        consumido=False, excecao_grupos=excecao, pular_grupos=pular_grupos
    )
    listado = any(e["pront"] == aluno.prontuario for e in elegiveis)
    assert listado is esperado_listado_gui

    # 2. Testa modo estrito (com rollback/limpeza via estorno caso grave)
    res_estrito = facade.registrar_consumo_com_reserva(
        aluno.prontuario, excecao_grupos=excecao, pular_grupos=pular_grupos
    )
    assert res_estrito["autorizado"] is esperado_estrito
    if not aluno_ativo:
        assert "inativo" in res_estrito["motivo"].lower()

    if esperado_estrito:
        consumos_ativos = db_session.query(Consumo).filter_by(sessao_id=sessao.id, ativo=True).all()
        assert len(consumos_ativos) == 1
        assert facade.desfazer_consumo(consumos_ativos[0].id, motivo="Reset matriz") is True
    else:
        assert db_session.query(Consumo).filter_by(sessao_id=sessao.id, ativo=True).count() == 0

    # 3. Testa modo padrão (usado pelo Totem e Operador)
    res_padrao = facade.registrar_consumo(
        f"  {aluno.prontuario.lower()}  ",
        excecao_grupos=excecao,
        pular_grupos=pular_grupos,
    )
    assert res_padrao["autorizado"] is esperado_padrao
    if esperado_padrao:
        assert res_padrao["prontuario"] == aluno.prontuario
        assert db_session.query(Consumo).filter_by(sessao_id=sessao.id, ativo=True).count() == 1
    else:
        assert db_session.query(Consumo).filter_by(sessao_id=sessao.id, ativo=True).count() == 0


# ============================================================================
# 2. Cotas Diárias Cross-Sessão e Independência de Turnos/Períodos
# ============================================================================


def test_cotas_cross_sessao_blindadas_contra_bypass_e_turnos_independentes(
    facade: FachadaRegistro,
    db_session,
    criar_grupo,
    criar_estudante,
    criar_reserva,
):
    """
    Garante de ponta a ponta que:
    - Um estudante com reserva Almoço+Jantar pode consumir 1 Almoço e 1 Jantar no mesmo dia.
    - Mesmo abrindo uma 2ª sessão de Almoço e ativando `pular_grupos=True` + `permitir_fora_horario=True`,
      a cota diária impede o segundo almoço.
    - Lanches permitem 1 consumo por período (Matutino vs Vespertino vs Noturno), bloqueando
      duplicidade dentro do mesmo período em sessões distintas (case-insensitive).
    """
    turma = criar_grupo(nome="2º INFO", tipo="turma")
    aluno = criar_estudante(prontuario="IQ3010001", nome="Lucas Cota", grupos=[turma])
    criar_reserva(
        estudante=aluno,
        data="10/11/2026",
        prato="Executivo",
        almoco=True,
        jantar=True,
    )

    # Sessão 1 de Almoço
    id_alm_1 = facade.iniciar_nova_sessao({
        "refeicao": "almoço",
        "periodo": "Tarde",
        "data": "2026-11-10",
        "hora": "11:30",
        "grupos": ["2º INFO"],
    })
    assert id_alm_1 is not None
    res_alm_1 = facade.registrar_consumo("iq3010001")
    assert res_alm_1["autorizado"] is True
    assert res_alm_1["prato"] == "Executivo"

    # Sessão 2 de Almoço no mesmo dia -> cota diária bloqueia mesmo com pular_grupos=True
    id_alm_2 = facade.iniciar_nova_sessao({
        "refeicao": "almoço",
        "periodo": "Tarde",
        "data": "2026-11-10",
        "hora": "12:45",
        "grupos": ["2º INFO"],
    })
    assert id_alm_2 is not None
    res_alm_2 = facade.registrar_consumo(
        "IQ3010001", pular_grupos=True, permitir_fora_horario=True
    )
    assert res_alm_2["autorizado"] is False
    assert "Cota diária atingida" in res_alm_2["motivo"]

    # Sessão de Jantar no mesmo dia -> usa a mesma reserva (jantar=True) e autoriza
    id_jan = facade.iniciar_nova_sessao({
        "refeicao": "jantar",
        "periodo": "Noite",
        "data": "2026-11-10",
        "hora": "19:00",
        "grupos": ["2º INFO"],
    })
    assert id_jan is not None
    res_jan = facade.registrar_consumo("IQ3010001")
    assert res_jan["autorizado"] is True
    assert res_jan["prato"] == "Executivo"

    # Sessão de Jantar 2 no mesmo dia -> bloqueada
    id_jan_2 = facade.iniciar_nova_sessao({
        "refeicao": "jantar",
        "periodo": "Noite",
        "data": "2026-11-10",
        "hora": "20:00",
        "grupos": ["2º INFO"],
    })
    res_jan_2 = facade.registrar_consumo("IQ3010001", pular_grupos=True)
    assert res_jan_2["autorizado"] is False
    assert "Cota diária atingida" in res_jan_2["motivo"]

    # Lanches no mesmo dia: Matutino OK -> segundo "matutino" bloqueado -> Vespertino OK
    id_lan_m1 = facade.iniciar_nova_sessao({
        "refeicao": "lanche",
        "periodo": "Matutino",
        "data": "2026-11-10",
        "hora": "09:30",
        "item_servido": "Biscoito",
        "grupos": ["2º INFO"],
    })
    assert facade.registrar_consumo("IQ3010001")["autorizado"] is True

    facade.iniciar_nova_sessao({
        "refeicao": "lanche",
        "periodo": "matutino",
        "data": "2026-11-10",
        "hora": "10:15",
        "item_servido": "Fruta",
        "grupos": ["2º INFO"],
    })
    res_lan_m2 = facade.registrar_consumo("IQ3010001", pular_grupos=True)
    assert res_lan_m2["autorizado"] is False
    assert "Cota atingida" in res_lan_m2["motivo"]

    facade.iniciar_nova_sessao({
        "refeicao": "lanche",
        "periodo": "Vespertino",
        "data": "2026-11-10",
        "hora": "15:30",
        "item_servido": "Suco",
        "grupos": ["2º INFO"],
    })
    res_lan_v = facade.registrar_consumo("IQ3010001")
    assert res_lan_v["autorizado"] is True
    assert res_lan_v["prato"] == "Suco"

    # Total exato de consumos gravados no dia = 4 (1 almoço, 1 jantar, 2 lanches)
    assert db_session.query(Consumo).filter_by(estudante_id=aluno.id, ativo=True).count() == 4
    # Confirma que aluno atendido em sessão aparece em consumido=True mesmo após remoção da turma
    facade.id_sessao_ativa = id_lan_m1
    facade.atualizar_grupos_sessao([])
    atendidos_m1 = facade.obter_estudantes_para_sessao(consumido=True)
    assert [a["pront"] for a in atendidos_m1] == ["IQ3010001"]


# ============================================================================
# 3. Grade Horária: Fronteiras Exatas de Minuto, Categorias e Bypasses
# ============================================================================


def test_grade_horaria_fronteiras_tolerancia_slots_invalidos_e_bypasses(
    facade: FachadaRegistro,
    criar_grupo,
    criar_estudante,
    criar_reserva,
    tmp_path,
    monkeypatch,
):
    """
    Valida fronteiras exatas de tolerância (5 minutos padrão), resiliência a slots inválidos,
    slots por categoria (PAP) e comportamento de `ignorar_horario_grade` vs `permitir_fora_horario`.
    """
    caminho_grade = tmp_path / "grade_horarios.json"
    monkeypatch.setattr(grade_horarios_service, "CAMINHO_GRADE_HORARIOS", caminho_grade)
    monkeypatch.setattr(constants, "CAMINHO_GRADE_HORARIOS", caminho_grade)

    grade = {
        "segunda": {
            "almoco": [
                # Slot malformado no meio da grade não pode derrubar a validação
                {"inicio": "99:99", "fim": "invalido", "turmas": ["1º A"], "categorias": ["*"]},
                # Slot 1: 11:30 - 12:00 (com tolerância 5 min: 11:25 até 12:05) -> 1º A
                {"inicio": "11:30", "fim": "12:00", "turmas": ["1º A"], "categorias": ["*"]},
                # Slot 2: 12:10 - 12:40 (tolerância: 12:05 até 12:45) -> apenas PAP
                {"inicio": "12:10", "fim": "12:40", "turmas": ["*"], "categorias": ["PAP"]},
            ]
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho_grade)

    g_1a = criar_grupo(nome="1º A", tipo="turma")
    g_2a = criar_grupo(nome="2º A", tipo="turma")
    g_pap = criar_grupo(nome="PAP", tipo="categoria")

    e_1a = criar_estudante(prontuario="IQ3020001", nome="Regular 1A", grupos=[g_1a])
    e_2a_pap = criar_estudante(prontuario="IQ3020002", nome="PAP 2A", grupos=[g_2a, g_pap])
    e_2a_reg = criar_estudante(prontuario="IQ3020003", nome="Fora Grade", grupos=[g_2a])

    for est in (e_1a, e_2a_pap, e_2a_reg):
        criar_reserva(estudante=est, data="10/11/2026", almoco=True)

    facade.iniciar_nova_sessao({
        "refeicao": "almoço",
        "periodo": "Tarde",
        "data": "2026-11-10",
        "hora": "11:30",
        "grupos": ["1º A", "2º A"],
    })

    # 11:24 -> 1 minuto antes da tolerância (11:25) -> BLOQUEADO com horário previsto
    with _fixar_relogio("11:24", "segunda"):
        r_antes = facade.registrar_consumo(e_1a.prontuario)
        assert r_antes["autorizado"] is False
        assert "11:30 às 12:00" in r_antes["motivo"]

    # 11:25 -> Fronteira exata inferior da tolerância -> AUTORIZADO
    with _fixar_relogio("11:25", "segunda"):
        r_borda_ini = facade.registrar_consumo(e_1a.prontuario)
        assert r_borda_ini["autorizado"] is True

    # Estorno para testar fronteira superior
    facade.desfazer_consumo_por_prontuario(e_1a.prontuario)

    # 12:06 -> 1 minuto após tolerância do Slot 1 (12:05), dentro do Slot 2 (PAP) -> bloqueado para 1º A regular informando seu horário
    with _fixar_relogio("12:06", "segunda"):
        r_apos = facade.registrar_consumo(e_1a.prontuario)
        assert r_apos["autorizado"] is False
        assert "Fora do horário da sua turma. Seu horário: 11:30 às 12:00." in r_apos["motivo"]

        # Mas e_2a_pap (2º A + PAP) é AUTORIZADO no Slot 2
        r_pap = facade.registrar_consumo(e_2a_pap.prontuario)
        assert r_pap["autorizado"] is True

    # 23:00 -> Fora de qualquer horário:
    # Com ignorar_horario_grade=True: libera quem existe na grade do dia (e_1a), mas bloqueia e_2a_reg (não consta em nenhum slot!)
    facade.definir_ignorar_horario_grade(True)
    with _fixar_relogio("23:00", "segunda"):
        r_ignora_ok = facade.registrar_consumo(e_1a.prontuario)
        assert r_ignora_ok["autorizado"] is True

        r_ignora_nao_previsto = facade.registrar_consumo(e_2a_reg.prontuario)
        assert r_ignora_nao_previsto["autorizado"] is False
        assert "não possui autorização" in r_ignora_nao_previsto["motivo"]

        # Com permitir_fora_horario=True (bypass do operador), ignora a grade totalmente
        r_bypass_horario = facade.registrar_consumo(e_2a_reg.prontuario, permitir_fora_horario=True)
        assert r_bypass_horario["autorizado"] is True
