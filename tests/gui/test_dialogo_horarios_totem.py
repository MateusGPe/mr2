# ----------------------------------------------------------------------------
# Arquivo: tests/gui/test_dialogo_horarios_totem.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Testes unitários e de integração para o diálogo de horários das turmas no totem
(DialogoGradeHorariosTotem) e sua integração com a tela principal do autoatendimento.
"""

from unittest.mock import MagicMock, patch
import pytest
import tkinter as tk

from registro.gui.autoatendimento.dialogo_horarios import DialogoGradeHorariosTotem
from registro.gui.autoatendimento.totem import FrameSelfService
from registro.nucleo.services import grade_horarios_service


@pytest.fixture
def fachada_mock_com_grade():
    fachada = MagicMock()
    fachada.id_sessao_ativa = 10
    fachada.obter_detalhes_sessao_ativa.return_value = {
        "id": 10,
        "refeicao": "almoco",
        "hora": "12:00",
        "data": "2026-11-09",
        "item_servido": "Feijoada Vegana",
        "grupos": ["1º A", "2º A"],
    }
    fachada.obter_dia_semana_atual.return_value = "segunda"
    fachada.obter_grade_horarios.return_value = {
        "segunda": {
            "almoco": [
                {
                    "inicio": "11:30",
                    "fim": "12:00",
                    "turmas": ["1º A"],
                    "categorias": ["REGULAR"],
                },
                {
                    "inicio": "12:00",
                    "fim": "12:30",
                    "turmas": ["2º A"],
                    "categorias": ["PAP"],
                },
                {
                    "inicio": "12:30",
                    "fim": "13:00",
                    "turmas": ["*"],
                    "categorias": ["*"],
                },
            ]
        }
    }
    return fachada


def test_dialogo_sem_sessao_ativa(app_root):
    """Testa aviso amigável quando nenhuma sessão está ativa."""
    fachada = MagicMock()
    fachada.id_sessao_ativa = None
    fachada.obter_detalhes_sessao_ativa.return_value = None

    dialogo = DialogoGradeHorariosTotem(
        parent=app_root,
        fachada=fachada,
        timeout_segundos=10,
    )
    app_root.update()

    assert dialogo.winfo_exists()
    assert dialogo._lbl_subtitulo.cget("text") == "Nenhuma sessão em andamento no momento"
    assert len(dialogo._cards_widgets) == 0

    dialogo.fechar()
    app_root.update()
    assert not dialogo.winfo_exists()


def test_dialogo_sem_grade_para_refeicao(app_root):
    """Testa aviso quando a refeição não possui slots configurados na grade."""
    fachada = MagicMock()
    fachada.id_sessao_ativa = 1
    fachada.obter_detalhes_sessao_ativa.return_value = {
        "id": 1,
        "refeicao": "jantar",
        "hora": "18:30",
        "data": "2026-11-09",
        "item_servido": "Sopa",
        "grupos": ["1º A"],
    }
    fachada.obter_dia_semana_atual.return_value = "segunda"
    fachada.obter_grade_horarios.return_value = {
        "segunda": {"jantar": []}
    }

    dialogo = DialogoGradeHorariosTotem(
        parent=app_root,
        fachada=fachada,
        timeout_segundos=10,
    )
    app_root.update()

    assert dialogo.winfo_exists()
    assert "Jantar" in dialogo._lbl_subtitulo.cget("text")
    assert len(dialogo._cards_widgets) == 0

    dialogo.fechar()
    app_root.update()


def test_dialogo_slots_status_timeline(app_root, fachada_mock_com_grade, monkeypatch):
    """Garante a categorização correta dos horários em Encerrado, Liberado Agora e Em Breve."""
    monkeypatch.setattr(grade_horarios_service, "obter_dia_semana_atual", lambda: "segunda")

    # Simula hora atual: 12:15 (slot 11:30 encerra às 12:05 com tolerância, 12:00-12:30 ativo, 12:30 futuro)
    dialogo = DialogoGradeHorariosTotem(
        parent=app_root,
        fachada=fachada_mock_com_grade,
        timeout_segundos=15,
        hora_simulada="12:15",
    )
    app_root.update()

    assert len(dialogo._cards_widgets) == 3

    # Slot 1: 11:30 às 12:00 -> Encerrado
    c1 = dialogo._cards_widgets[0]
    assert "ENCERRADO" in c1["badge"].cget("text")
    assert "Finalizado" in c1["substatus"].cget("text") or "finalizado" in c1["substatus"].cget("text")

    # Slot 2: 12:00 às 12:30 -> Liberado Agora
    c2 = dialogo._cards_widgets[1]
    assert "LIBERADO AGORA" in c2["badge"].cget("text")
    assert "Restam 15 min" in c2["substatus"].cget("text")

    # Slot 3: 12:30 às 13:00 -> Em Breve
    c3 = dialogo._cards_widgets[2]
    assert "EM BREVE" in c3["badge"].cget("text")
    assert "Inicia em 15 min" in c3["substatus"].cget("text")

    dialogo.fechar()
    app_root.update()


def test_leitura_scanner_usb_fecha_dialogo_e_chama_callback(app_root, fachada_mock_com_grade):
    """Testa leitura rápida via leitor USB / teclado com tecla Enter."""
    mock_callback = MagicMock()

    dialogo = DialogoGradeHorariosTotem(
        parent=app_root,
        fachada=fachada_mock_com_grade,
        on_codigo_lido=mock_callback,
        timeout_segundos=20,
    )
    app_root.update()

    # Simula digitação das teclas pelo leitor USB
    for char in "SP123456":
        event = MagicMock()
        event.keysym = char
        event.char = char
        dialogo._ao_pressionar_tecla(event)

    # Simula pressionar Return / Enter
    event_enter = MagicMock()
    event_enter.keysym = "Return"
    dialogo._ao_pressionar_tecla(event_enter)
    app_root.update()

    mock_callback.assert_called_once_with("SP123456")
    assert not dialogo.winfo_exists()


def test_tecla_escape_fecha_dialogo(app_root, fachada_mock_com_grade):
    """Testa fechamento via tecla Escape."""
    dialogo = DialogoGradeHorariosTotem(
        parent=app_root,
        fachada=fachada_mock_com_grade,
    )
    app_root.update()

    event_esc = MagicMock()
    event_esc.keysym = "Escape"
    dialogo._ao_pressionar_tecla(event_esc)
    app_root.update()

    assert not dialogo.winfo_exists()


def test_timeout_fechamento_automatico(app_root, fachada_mock_com_grade):
    """Testa ciclo de decremento e fechamento automático quando o tempo zera."""
    dialogo = DialogoGradeHorariosTotem(
        parent=app_root,
        fachada=fachada_mock_com_grade,
        timeout_segundos=1,
    )
    app_root.update()

    assert dialogo._tempo_restante == 1
    dialogo._ciclo_segundo()
    app_root.update()

    assert not dialogo.winfo_exists()


def test_totem_integracao_abrir_e_fechar_dialogo(app_root, fachada_mock_com_grade):
    """Testa os gatilhos no Totem para abrir, processar código com diálogo e fechar."""
    app_root.deiconify()
    try:
        with patch.object(FrameSelfService, "_iniciar_camera"):
            totem = FrameSelfService(
                master=app_root,
                fachada=fachada_mock_com_grade,
                notification_callback=MagicMock(),
            )
            totem.pack()
            app_root.update()

            # Abre o diálogo de horários
            totem._abrir_dialogo_horarios()
            app_root.update()

            assert totem._dialogo_horarios is not None
            assert totem._dialogo_horarios.winfo_exists()

            # O totem deve considerar que PODE processar leitura mesmo com o diálogo aberto
            assert totem._pode_processar_leitura() is True

            # Processar código externo deve fechar o diálogo de horários
            with patch.object(totem, "_registrar_entrada", return_value=(True, "OK", {"nome": "Teste"})):
                totem.processar_codigo_externo("12345")
                app_root.update()

                assert totem._dialogo_horarios is None

            totem.stop()
            totem.destroy()
            app_root.update()
    finally:
        app_root.withdraw()


def test_dialogo_e_totem_horario_livre(app_root, fachada_mock_com_grade, monkeypatch):
    """Verifica o badge discreto no Totem e o status flexibilizado no Diálogo de Horários quando Horário Livre está ativo."""
    monkeypatch.setattr(grade_horarios_service, "obter_dia_semana_atual", lambda: "segunda")
    fachada_mock_com_grade.ignorar_horario_grade = True
    fachada_mock_com_grade.filtro_categoria_sessao = None

    with patch.object(FrameSelfService, "_iniciar_camera"):
        totem = FrameSelfService(
            master=app_root,
            fachada=fachada_mock_com_grade,
            notification_callback=MagicMock(),
        )
        totem.pack()
        app_root.update()

        assert "Horário Livre" in totem._lbl_sessao_topo.cget("text")

        dialogo = DialogoGradeHorariosTotem(
            parent=app_root,
            fachada=fachada_mock_com_grade,
            timeout_segundos=10,
            hora_simulada="15:00",
        )
        app_root.update()

        assert "Horário Livre" in dialogo._lbl_subtitulo.cget("text")
        assert len(dialogo._cards_widgets) == 3
        for card in dialogo._cards_widgets:
            assert "LIBERADO (HORÁRIO LIVRE)" in card["badge"].cget("text")

        dialogo.fechar()
        totem.stop()
        totem.destroy()
        app_root.update()


def test_dialogo_slot_apenas_categoria_nao_exibe_todas_turmas(app_root, monkeypatch):
    """Slot com turmas='*' e categorias específicas não deve exibir 'Todas as turmas'."""
    monkeypatch.setattr(grade_horarios_service, "obter_dia_semana_atual", lambda: "segunda")

    fachada = MagicMock()
    fachada.id_sessao_ativa = 20
    fachada.ignorar_horario_grade = False
    fachada.obter_detalhes_sessao_ativa.return_value = {
        "id": 20,
        "refeicao": "almoco",
        "hora": "11:20",
        "data": "2026-11-09",
        "item_servido": "Almoço",
        "grupos": ["Evento Robótica"],
    }
    fachada.obter_grade_horarios.return_value = {
        "segunda": {
            "almoco": [
                {
                    "inicio": "11:15",
                    "fim": "11:35",
                    "turmas": ["*"],
                    "categorias": ["Evento Robótica"],
                }
            ]
        }
    }

    dialogo = DialogoGradeHorariosTotem(
        parent=app_root,
        fachada=fachada,
        timeout_segundos=10,
        hora_simulada="11:20",
    )
    app_root.update()

    assert len(dialogo._cards_widgets) == 1
    card_frame = dialogo._cards_widgets[0]["frame_card"]
    textos = []
    for child in card_frame.winfo_children():
        for sub in child.winfo_children():
            try:
                textos.append(sub.cget("text"))
            except Exception:
                pass

    texto_completo = " ".join(textos)
    assert "Todas as turmas" not in texto_completo
    assert "Evento Robótica" in texto_completo

    dialogo.fechar()
    app_root.update()


