# ----------------------------------------------------------------------------
# Arquivo: tests/integration/test_ciclo_completo_grade_sessao.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Teste de integração de ponta a ponta (E2E) simulando o ciclo de vida completo
de uma refeição:
- Grade horária com múltiplos slots e restrições de categoria
- Início de sessão, persistência em session.json
- Validação temporal de slots, tolerâncias e bloqueios
- Bypasses de operador (permitir_fora_horario e pular_grupos)
- Atualização dinâmica da grade em runtime
- Mutações de filtros de turma e categoria durante o atendimento
- Estorno/soft delete de consumo e reatendimento
- Encerramento e limpeza da sessão
"""

from pathlib import Path
from unittest.mock import patch
import pytest

from registro.nucleo import constants
from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.services import grade_horarios_service


@pytest.fixture
def cenario_integrado(facade: FachadaRegistro, criar_grupo, criar_estudante, criar_reserva, tmp_path, monkeypatch):
    """Monta o ecossistema completo para a jornada de integração."""
    # Redireciona caminhos de configuração para diretório temporário
    caminho_grade = tmp_path / "grade_horarios.json"
    caminho_sessao = tmp_path / "session.json"
    monkeypatch.setattr(grade_horarios_service, "CAMINHO_GRADE_HORARIOS", caminho_grade)
    monkeypatch.setattr(constants, "CAMINHO_GRADE_HORARIOS", caminho_grade)
    monkeypatch.setattr(constants, "CAMINHO_SESSAO", caminho_sessao)

    # 1. Configuração inicial da grade semanal:
    # Slot 1: 11:30 - 12:15 -> Turma 1º A (qualquer categoria)
    # Slot 2: 12:15 - 13:00 -> Categoria PAP (independente da turma)
    grade = {
        "segunda": {
            "almoco": [
                {
                    "inicio": "11:30",
                    "fim": "12:15",
                    "turmas": ["1º A"],
                    "categorias": ["*"],
                },
                {
                    "inicio": "12:15",
                    "fim": "13:00",
                    "turmas": ["*"],
                    "categorias": ["PAP"],
                },
            ]
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho_grade)

    # 2. Criação de turmas, categoria PAP e discentes
    g_1a = criar_grupo(nome="1º A", ativo=True, tipo="turma")
    g_2a = criar_grupo(nome="2º A", ativo=True, tipo="turma")
    g_pap = criar_grupo(nome="PAP", ativo=True, tipo="categoria")

    # Estudante 1: 1º A, sem categoria
    e_1a_reg = criar_estudante(
        prontuario="IQ1001",
        nome="Carlos Regular",
        ativo=True,
        grupos=[g_1a],
    )

    # Estudante 2: 1º A, com PAP
    e_1a_pap = criar_estudante(
        prontuario="IQ1002",
        nome="Ana PAP",
        ativo=True,
        grupos=[g_1a, g_pap],
    )

    # Estudante 3: 2º A, sem categoria
    e_2a_reg = criar_estudante(
        prontuario="IQ2001",
        nome="Bruno Regular",
        ativo=True,
        grupos=[g_2a],
    )

    # Estudante 4: 2º A, com PAP
    e_2a_pap = criar_estudante(
        prontuario="IQ2002",
        nome="Diana PAP",
        ativo=True,
        grupos=[g_2a, g_pap],
    )

    facade._sessao_db.commit()

    # 3. Criação de reservas de almoço para todos no dia 10/11/2026
    data_refeicao = "10/11/2026"
    for est in [e_1a_reg, e_1a_pap, e_2a_reg, e_2a_pap]:
        criar_reserva(estudante=est, data=data_refeicao, cancelada=False, prato="Padrão")

    return {
        "facade": facade,
        "caminho_grade": caminho_grade,
        "caminho_sessao": caminho_sessao,
        "data_refeicao": data_refeicao,
        "e_1a_reg": e_1a_reg,
        "e_1a_pap": e_1a_pap,
        "e_2a_reg": e_2a_reg,
        "e_2a_pap": e_2a_pap,
    }


def test_jornada_completa_refeicao_grade_sessao_e_filtros(cenario_integrado, monkeypatch):
    """Executa a simulação completa de ponta a ponta."""
    facade: FachadaRegistro = cenario_integrado["facade"]
    caminho_grade: Path = cenario_integrado["caminho_grade"]
    caminho_sessao: Path = cenario_integrado["caminho_sessao"]
    e_1a_reg = cenario_integrado["e_1a_reg"]
    e_2a_reg = cenario_integrado["e_2a_reg"]
    e_2a_pap = cenario_integrado["e_2a_pap"]

    # Simula que hoje é segunda-feira
    monkeypatch.setattr(grade_horarios_service, "obter_dia_semana_atual", lambda: "segunda")

    # -------------------------------------------------------------------------
    # Passo 1: Iniciar Sessão Ativa de Almoço
    # -------------------------------------------------------------------------
    dados_sessao = {
        "refeicao": "almoço",
        "periodo": "tarde",
        "data": "2026-11-10",
        "hora": "11:30",
        "item_servido": "Almoço Completo",
        "grupos": ["1º A", "2º A"],
    }
    id_sessao = facade.iniciar_nova_sessao(dados_sessao)
    assert id_sessao is not None
    facade.salvar_estado_sessao(id_sessao)
    assert caminho_sessao.exists()

    # -------------------------------------------------------------------------
    # Passo 2: Horário 11:45 (Slot 1 ativo para 1º A)
    # -------------------------------------------------------------------------
    with patch("registro.nucleo.services.consumo_service.datetime") as mock_dt, \
         patch("registro.nucleo.services.grade_horarios_service.datetime") as mock_dt_grade:
        mock_dt.now.return_value.strftime.side_effect = lambda fmt: "11:45" if "%H:%M" in fmt else "11:45:00"
        mock_dt_grade.now.return_value.strftime.side_effect = lambda fmt: "11:45" if "%H:%M" in fmt else "11:45:00"
        mock_dt_grade.now.return_value.weekday.return_value = 0  # segunda

        # 2.1 Aluno 1º A REGULAR chega no horário -> Autorizado!
        res_1a = facade.registrar_consumo_com_reserva(e_1a_reg.prontuario)
        assert res_1a["autorizado"] is True

        # 2.2 Aluno 1º A tenta passar novamente no mesmo dia -> Bloqueado!
        res_duplicado = facade.registrar_consumo_com_reserva(e_1a_reg.prontuario)
        assert res_duplicado["autorizado"] is False
        assert "já registrado" in res_duplicado["motivo"]

        # 2.3 Aluno 2º A PAP tenta passar às 11:45 (slot dele é 12:15 às 13:00) -> Bloqueado por horário!
        res_2a_cedo = facade.registrar_consumo_com_reserva(e_2a_pap.prontuario)
        assert res_2a_cedo["autorizado"] is False
        assert "Fora do horário da sua turma. Seu horário: 12:15 às 13:00." in res_2a_cedo["motivo"]

        # 2.4 Operador concede exceção (override) para o aluno 2º A PAP comer mais cedo -> Autorizado!
        res_override = facade.registrar_consumo_com_reserva(
            e_2a_pap.prontuario, permitir_fora_horario=True
        )
        assert res_override["autorizado"] is True

    # -------------------------------------------------------------------------
    # Passo 3: Horário 12:30 (Slot 2 ativo, restrito a PAP)
    # -------------------------------------------------------------------------
    with patch("registro.nucleo.services.consumo_service.datetime") as mock_dt, \
         patch("registro.nucleo.services.grade_horarios_service.datetime") as mock_dt_grade:
        mock_dt.now.return_value.strftime.side_effect = lambda fmt: "12:30" if "%H:%M" in fmt else "12:30:00"
        mock_dt_grade.now.return_value.strftime.side_effect = lambda fmt: "12:30" if "%H:%M" in fmt else "12:30:00"
        mock_dt_grade.now.return_value.weekday.return_value = 0

        # 3.1 Aluno 2º A sem PAP tenta comer no slot exclusivo para PAP -> Bloqueado por categoria!
        res_reg_bloqueado = facade.registrar_consumo_com_reserva(e_2a_reg.prontuario)
        assert res_reg_bloqueado["autorizado"] is False
        assert "Categoria (Nenhuma) não permitida neste horário. Permitidas: PAP." in res_reg_bloqueado["motivo"]

    # -------------------------------------------------------------------------
    # Passo 4: Atualização Dinâmica da Grade Horária em Runtime
    # A direção libera a turma 2º A no slot 2 (regra OU com PAP).
    # -------------------------------------------------------------------------
    grade_atualizada = grade_horarios_service.carregar_grade_horarios(caminho_grade)
    grade_atualizada["segunda"]["almoco"][1]["turmas"] = ["2º A"]
    grade_horarios_service.salvar_grade_horarios(grade_atualizada, caminho_grade)

    with patch("registro.nucleo.services.consumo_service.datetime") as mock_dt, \
         patch("registro.nucleo.services.grade_horarios_service.datetime") as mock_dt_grade:
        mock_dt.now.return_value.strftime.side_effect = lambda fmt: "12:35" if "%H:%M" in fmt else "12:35:00"
        mock_dt_grade.now.return_value.strftime.side_effect = lambda fmt: "12:35" if "%H:%M" in fmt else "12:35:00"
        mock_dt_grade.now.return_value.weekday.return_value = 0

        # 4.1 Agora o aluno 2º A REGULAR tenta novamente -> Autorizado com sucesso!
        res_reg_liberado = facade.registrar_consumo_com_reserva(e_2a_reg.prontuario)
        assert res_reg_liberado["autorizado"] is True

    # -------------------------------------------------------------------------
    # Passo 5: Mutações no Filtro de Turmas, Desfazer Consumo e Bypass Total
    # Operador ajusta o filtro da sessão para desativar a turma 2º A.
    # -------------------------------------------------------------------------
    facade.atualizar_grupos_sessao(["1º A"])

    # 5.1 Discente de 2º A com reserva válida permanece elegível na listagem
    elegiveis = facade.obter_estudantes_para_sessao()
    prontuarios_elegiveis = {e["pront"] for e in elegiveis}
    assert "IQ2001" in prontuarios_elegiveis

    # 5.2 Estorno / Desfazer consumo do aluno 1º A (soft delete) e reatendimento
    desfeito = facade.desfazer_consumo_por_prontuario(e_1a_reg.prontuario)
    assert desfeito is True

    # Aluno tenta novamente e consegue registrar novo consumo
    with patch("registro.nucleo.services.consumo_service.datetime") as mock_dt, \
         patch("registro.nucleo.services.grade_horarios_service.datetime") as mock_dt_grade:
        mock_dt.now.return_value.strftime.side_effect = lambda fmt: "11:50" if "%H:%M" in fmt else "11:50:00"
        mock_dt_grade.now.return_value.strftime.side_effect = lambda fmt: "11:50" if "%H:%M" in fmt else "11:50:00"
        mock_dt_grade.now.return_value.weekday.return_value = 0

        res_reconsumo = facade.registrar_consumo_com_reserva(e_1a_reg.prontuario)
        assert res_reconsumo["autorizado"] is True

    # 5.3 Desativação completa da grade horária (remoção do arquivo)
    # A restrição horária entra em fallback livre
    caminho_grade.unlink(missing_ok=True)
    assert not caminho_grade.exists()

    with patch("registro.nucleo.services.consumo_service.datetime") as mock_dt, \
         patch("registro.nucleo.services.grade_horarios_service.datetime") as mock_dt_grade:
        mock_dt.now.return_value.strftime.side_effect = lambda fmt: "23:59" if "%H:%M" in fmt else "23:59:00"
        mock_dt_grade.now.return_value.strftime.side_effect = lambda fmt: "23:59" if "%H:%M" in fmt else "23:59:00"

        # Com pular_grupos=True e grade desativada, discente do 2º A consome mesmo fora do horário
        # e fora da turma da sessão ativa
        criar_estudante = cenario_integrado["facade"].criar_estudante
        criar_reserva = cenario_integrado["facade"].criar_reserva

        est_extra = criar_estudante(prontuario="IQ9999", nome="Extra Bypass")
        criar_reserva(
            prontuario_estudante="IQ9999",
            dados_reserva={"data": "10/11/2026", "prato": "Vegetariano", "cancelada": False},
        )

        res_bypass = facade.registrar_consumo_com_reserva(
            est_extra["prontuario"], pular_grupos=True
        )
        assert res_bypass["autorizado"] is True

    # -------------------------------------------------------------------------
    # Passo 6: Finalização e Limpeza da Sessão
    # -------------------------------------------------------------------------
    assert caminho_sessao.exists()
    assert facade.id_sessao_ativa == id_sessao

    facade.limpar_estado_sessao()
    assert not caminho_sessao.exists()
    assert facade.id_sessao_ativa is None


def test_horario_livre_atraso_refeicao(cenario_integrado, criar_grupo, criar_estudante, criar_reserva, monkeypatch):
    """Testa o modo Horário Livre (ignorar_horario_grade) quando o almoço atrasa 1+ hora."""
    facade: FachadaRegistro = cenario_integrado["facade"]
    e_1a_reg = cenario_integrado["e_1a_reg"]
    e_2a_reg = cenario_integrado["e_2a_reg"]
    e_2a_pap = cenario_integrado["e_2a_pap"]

    g_3c = criar_grupo(nome="3º C", ativo=True, tipo="turma")
    e_3c = criar_estudante(prontuario="IQ3001", nome="Eduardo 3C", ativo=True, grupos=[g_3c])
    facade._sessao_db.commit()
    criar_reserva(estudante=e_3c, data="10/11/2026", cancelada=False, prato="Padrão")

    monkeypatch.setattr(grade_horarios_service, "obter_dia_semana_atual", lambda: "segunda")

    id_sessao = facade.iniciar_nova_sessao({
        "refeicao": "almoço",
        "periodo": "tarde",
        "data": "2026-11-10",
        "hora": "11:30",
        "item_servido": "Almoço Completo",
        "grupos": ["1º A", "2º A", "3º C"],
    })
    assert id_sessao is not None
    assert facade.ignorar_horario_grade is False

    # Almoço atrasado: são 14:15 (slots eram 11:30-12:15 e 12:15-13:00)
    with patch("registro.nucleo.services.consumo_service.datetime") as mock_dt, \
         patch("registro.nucleo.services.grade_horarios_service.datetime") as mock_dt_grade:
        mock_dt.now.return_value.strftime.side_effect = lambda fmt: "14:15" if "%H:%M" in fmt else "14:15:00"
        mock_dt_grade.now.return_value.strftime.side_effect = lambda fmt: "14:15" if "%H:%M" in fmt else "14:15:00"
        mock_dt_grade.now.return_value.weekday.return_value = 0

        # Modo normal bloqueia 1º A por horário
        res_bloq = facade.registrar_consumo(e_1a_reg.prontuario)
        assert res_bloq["autorizado"] is False
        assert "Fora do horário" in res_bloq["motivo"]

        # Operador ativa Horário Livre na sessão
        facade.definir_ignorar_horario_grade(True)

        # 1º A REGULAR (prevista na grade de segunda) -> Autorizado!
        res_1a_ok = facade.registrar_consumo(e_1a_reg.prontuario)
        assert res_1a_ok["autorizado"] is True

        # 2º A PAP (prevista na grade de segunda) -> Autorizado!
        res_2a_pap_ok = facade.registrar_consumo(e_2a_pap.prontuario)
        assert res_2a_pap_ok["autorizado"] is True

        # 2º A sem PAP (slot 2 exige PAP) -> Bloqueado por categoria!
        res_2a_reg_bloq = facade.registrar_consumo(e_2a_reg.prontuario)
        assert res_2a_reg_bloq["autorizado"] is False
        assert "Categoria (Nenhuma) não permitida" in res_2a_reg_bloq["motivo"]

        # 3º C (não prevista na grade de segunda) -> Bloqueado mesmo com reserva!
        res_3c_bloq = facade.registrar_consumo(e_3c.prontuario)
        assert res_3c_bloq["autorizado"] is False
        assert "não permitida" in res_3c_bloq["motivo"] or "não possui autorização" in res_3c_bloq["motivo"]

