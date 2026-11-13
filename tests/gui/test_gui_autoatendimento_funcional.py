# ----------------------------------------------------------------------------
# Arquivo: tests/gui/test_gui_autoatendimento_funcional.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Testes funcionais e de casos de uso (prováveis e improváveis) para o
Totem de Autoatendimento, integrando com SQLite em memória e FachadaRegistro real.
"""

import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

from registro.gui.autoatendimento.app import AbaConsumos, AbaDashboard, AppSelfService
from registro.gui.autoatendimento.totem import FrameSelfService


@pytest.fixture
def totem_setup(app_root, facade, criar_grupo, criar_estudante, criar_sessao):
    """Configura ambiente com grupo, estudante e sessão para testes do Totem."""
    grupo = criar_grupo(nome="1º A - INFO", ativo=True)
    estudante = criar_estudante(
        prontuario="IQ3000001",
        nome="João da Silva Santos",
        ativo=True,
        grupos=[grupo],
    )
    sessao = criar_sessao(
        refeicao="lanche",
        data="21/10/2026",
        hora="09:30",
        item_servido="Suco e Biscoito",
        grupos=[grupo],
    )
    facade.definir_sessao_ativa(sessao.id)

    with patch.object(FrameSelfService, "_iniciar_camera"):
        notif_cb = MagicMock()
        totem = FrameSelfService(
            master=app_root,
            fachada=facade,
            notification_callback=notif_cb,
        )
        totem.pack()
        app_root.update()
        yield {
            "totem": totem,
            "facade": facade,
            "grupo": grupo,
            "estudante": estudante,
            "sessao": sessao,
            "notif_cb": notif_cb,
        }
        totem.stop()
        totem.destroy()


def test_totem_leitura_nominal_sucesso(totem_setup, app_root):
    """Cenário Provável: Leitura nominal de prontuário registra consumo no SQLite e atualiza a UI."""
    totem = totem_setup["totem"]
    facade = totem_setup["facade"]
    estudante = totem_setup["estudante"]
    notif_cb = totem_setup["notif_cb"]

    totem._var_entrada_manual.set(estudante.prontuario)
    totem._ao_submeter_manual()
    app_root.update()

    # Validações no Banco SQLite
    consumidos = facade.obter_estudantes_para_sessao(consumido=True)
    assert len(consumidos) == 1
    assert consumidos[0]["pront"] == estudante.prontuario
    assert consumidos[0]["nome"] == estudante.nome

    # Validações Visuais na GUI
    assert totem._lbl_status["text"] == "REGISTRADO COM SUCESSO!"
    assert totem._frame_estudante["bg"] == totem.COR_FUNDO_SUCESSO
    assert totem._lbl_nome["text"] == estudante.nome
    assert totem._lbl_turma["text"] == "1º A - INFO"
    assert totem._total_atendidos_sessao == 1
    notif_cb.assert_called_once()


def test_totem_formatacao_matricula_digitos_parciais(totem_setup, app_root):
    """Cenário Provável: Entrada manual ou scanner com dígitos parciais (ex: '1') padroniza para 'IQ3000001'."""
    totem = totem_setup["totem"]
    facade = totem_setup["facade"]

    # Digita apenas '1' no leitor manual
    totem._var_entrada_manual.set("1")
    totem._ao_submeter_manual()
    app_root.update()

    consumidos = facade.obter_estudantes_para_sessao(consumido=True)
    assert len(consumidos) == 1
    assert consumidos[0]["pront"] == "IQ3000001"
    assert totem._lbl_status["text"] == "REGISTRADO COM SUCESSO!"


def test_totem_duplo_consumo_rejeitado(totem_setup, app_root):
    """Cenário Provável: Tentativa consecutiva de registro do mesmo estudante é rejeitada (não autorizada)."""
    totem = totem_setup["totem"]
    facade = totem_setup["facade"]
    estudante = totem_setup["estudante"]

    # Primeiro consumo: Sucesso
    totem._processar_codigo(estudante.prontuario, manual=True)
    app_root.update()
    assert totem._lbl_status["text"] == "REGISTRADO COM SUCESSO!"
    assert len(facade.obter_estudantes_para_sessao(consumido=True)) == 1

    # Segundo consumo: Duplicidade
    totem._processar_codigo(estudante.prontuario, manual=True)
    app_root.update()

    # O banco de dados deve manter apenas 1 registro de consumo
    assert len(facade.obter_estudantes_para_sessao(consumido=True)) == 1

    # GUI deve exibir erro visual
    assert totem._lbl_status["text"] == "ATENÇÃO: NÃO AUTORIZADO"
    assert totem._frame_estudante["bg"] == totem.COR_FUNDO_ERRO
    msg = totem._lbl_mensagem["text"].lower()
    assert "já registrado" in msg or "já consumiu" in msg


def test_totem_almoco_com_reserva_vegetariana(
    app_root, facade, criar_grupo, criar_estudante, criar_sessao, criar_reserva
):
    """Cenário Provável: Refeição de almoço com reserva específica ('Vegetariano') exibe o prato corretamente."""
    grupo = criar_grupo(nome="2INFO")
    estudante = criar_estudante(
        prontuario="IQ3000002", nome="Beatriz Souza", grupos=[grupo]
    )
    sessao_almoco = criar_sessao(
        refeicao="almoço",
        data="21/10/2026",
        hora="12:00",
        grupos=[grupo],
    )
    criar_reserva(estudante=estudante, data="21/10/2026", prato="Vegetariano")
    facade.definir_sessao_ativa(sessao_almoco.id)

    with patch.object(FrameSelfService, "_iniciar_camera"):
        totem = FrameSelfService(
            master=app_root, fachada=facade, notification_callback=MagicMock()
        )
        totem.pack()
        app_root.update()

        totem._processar_codigo("IQ3000002", manual=True)
        app_root.update()

        assert totem._lbl_status["text"] == "REGISTRADO COM SUCESSO!"
        assert "Vegetariano" in totem._lbl_prato["text"]
        totem.stop()
        totem.destroy()


def test_totem_almoco_sem_reserva_rejeitado(
    app_root, facade, criar_grupo, criar_estudante, criar_sessao
):
    """Cenário Provável: Refeição de almoço sem reserva é rejeitada com mensagem correspondente."""
    grupo = criar_grupo(nome="3INFO")
    criar_estudante(prontuario="IQ3000003", nome="Carlos Lima", grupos=[grupo])
    sessao_almoco = criar_sessao(
        refeicao="almoço",
        data="21/10/2026",
        hora="12:00",
        grupos=[grupo],
    )
    facade.definir_sessao_ativa(sessao_almoco.id)

    with patch.object(FrameSelfService, "_iniciar_camera"):
        totem = FrameSelfService(
            master=app_root, fachada=facade, notification_callback=MagicMock()
        )
        totem.pack()
        app_root.update()

        totem._processar_codigo("IQ3000003", manual=True)
        app_root.update()

        assert totem._lbl_status["text"] == "ATENÇÃO: NÃO AUTORIZADO"
        assert totem._frame_estudante["bg"] == totem.COR_FUNDO_ERRO
        msg = totem._lbl_mensagem["text"].lower()
        assert "sem reserva" in msg or "reserva" in msg or "acesso negado" in msg

        totem.stop()
        totem.destroy()


def test_totem_leitura_sem_sessao_ativa_improvavel(app_root, facade):
    """Cenário Improvável: Leitor acionado quando não há nenhuma sessão ativa na fachada."""
    facade.id_sessao_ativa = None

    with patch.object(FrameSelfService, "_iniciar_camera"):
        totem = FrameSelfService(
            master=app_root, fachada=facade, notification_callback=MagicMock()
        )
        totem.pack()
        app_root.update()

        totem._processar_codigo("IQ3000001", manual=True)
        app_root.update()

        assert totem._lbl_status["text"] == "ATENÇÃO: NÃO AUTORIZADO"
        assert "nenhuma sessão ativa" in totem._lbl_mensagem["text"].lower()
        totem.stop()
        totem.destroy()


def test_totem_cooldown_ignora_leituras_repetidas_improvavel(totem_setup, app_root):
    """Cenário Improvável: Durante o cooldown da câmera, leituras sucessivas são ignoradas."""
    totem = totem_setup["totem"]
    totem._cooldown_frames = 15

    with patch.object(totem, "_registrar_entrada") as mock_reg:
        # Quando manual=False (câmera) e cooldown > 0, deve ignorar
        totem._processar_codigo("IQ3000001", manual=False)
        mock_reg.assert_not_called()


def test_totem_bloqueio_durante_dialogo_modal(totem_setup, app_root):
    """Cenário Improvável: Diálogo modal aberto no Toplevel suspende processamento de leitura."""
    totem = totem_setup["totem"]
    app_root.deiconify()
    app_root.update()

    assert totem._pode_processar_leitura() is True

    # Cria janela Toplevel simulando diálogo aberto (ex: PIN ou seleção de sessão)
    dialogo_modal = tk.Toplevel(app_root)
    dialogo_modal.transient(app_root)
    app_root.update()

    assert totem._pode_processar_leitura() is False

    dialogo_modal.destroy()
    app_root.update()

    assert totem._pode_processar_leitura() is True
    app_root.withdraw()


def test_totem_busca_fuzzy_por_nome(
    app_root, facade, criar_grupo, criar_estudante, criar_sessao
):
    """Cenários Prováveis e Improváveis de Busca Fuzzy: match único, ambíguo e não encontrado."""
    grupo = criar_grupo(nome="ADM")
    criar_estudante(prontuario="IQ3000010", nome="Mariana Albuquerque", grupos=[grupo])
    criar_estudante(prontuario="IQ3000020", nome="Mariano Silva", grupos=[grupo])
    criar_estudante(prontuario="IQ3000021", nome="Mariano Souza", grupos=[grupo])

    sessao = criar_sessao(refeicao="lanche", data="21/10/2026", grupos=[grupo])
    facade.definir_sessao_ativa(sessao.id)

    with patch.object(FrameSelfService, "_iniciar_camera"):
        totem = FrameSelfService(
            master=app_root, fachada=facade, notification_callback=MagicMock()
        )
        totem.pack()
        app_root.update()

        # 1. Match único e claro
        sucesso, msg, dados = totem._buscar_por_nome_e_registrar("Mariana Albuquerque")
        assert sucesso is True
        assert dados["prontuario"] == "IQ3000010"

        # 2. Match ambíguo (Mariano Silva vs Mariano Souza)
        sucesso_amb, msg_amb, _ = totem._buscar_por_nome_e_registrar("Mariano S")
        assert sucesso_amb is False
        assert "Múltiplos resultados" in msg_amb

        # 3. Aluno não encontrado
        sucesso_inex, msg_inex, _ = totem._buscar_por_nome_e_registrar(
            "Nome Inexistente Total"
        )
        assert sucesso_inex is False
        assert "não encontrado" in msg_inex.lower()

        totem.stop()
        totem.destroy()


def test_autoatendimento_integracao_aba_consumos_e_dashboard(
    app_root, facade, criar_grupo, criar_estudante, criar_sessao
):
    """Testa sincronização em tempo real das abas de Consumos e Dashboard com registros reais."""
    grupo = criar_grupo(nome="INFO")
    estudante = criar_estudante(
        prontuario="IQ3000050", nome="Fernando Dias", grupos=[grupo]
    )
    sessao = criar_sessao(refeicao="lanche", data="21/10/2026", grupos=[grupo])
    facade.definir_sessao_ativa(sessao.id)

    # 1. Dashboard inicial
    dash = AbaDashboard(master=app_root, fachada=facade, id_sessao=sessao.id)
    app_root.update()
    assert dash.lbl_total_consumos["text"] == "0"

    # 2. Consumos inicial
    consumos = AbaConsumos(master=app_root, fachada=facade, id_sessao=sessao.id)
    app_root.update()
    assert len(consumos._consumos_raw) == 0

    # 3. Registra consumo real no backend
    facade.registrar_consumo(estudante.prontuario)

    # Simula recebimento de notificação na AbaConsumos
    consumos.adicionar_consumo(
        (
            estudante.prontuario,
            estudante.nome,
            "INFO",
            "09:35",
            "Lanche",
        )
    )
    assert len(consumos._consumos_raw) == 1

    # Testa busca na AbaConsumos
    consumos.var_busca.set("Fernando")
    consumos._ao_digitar_busca()
    assert len(consumos._mapa_iid_para_consumo) == 1

    consumos.var_busca.set("Inexistente")
    consumos._ao_digitar_busca()
    assert len(consumos._mapa_iid_para_consumo) == 0

    dash.destroy()
    consumos.destroy()


def test_app_self_service_inicializacao_com_facade(app_root, facade, mock_messagebox):
    """Garante que a janela AppSelfService inicializa com fachada injetada sem erros."""
    with (
        patch("ttkbootstrap.window._require_single_root"),
        patch(
            "registro.gui.autoatendimento.app.obter_config_totem",
            return_value={"fullscreen": False},
        ),
    ):
        app = AppSelfService(fachada_nucleo=facade)
        app.withdraw()
        app.update()
        assert app.fachada_nucleo is facade
        assert "selfservice" in app.frames
        assert "dashboard" in app.frames
        assert "consumos" in app.frames
        app.destroy()


def test_totem_busca_por_nome_nao_bypassa_regras(
    app_root, facade, criar_grupo, criar_estudante, criar_sessao, tmp_path, monkeypatch
):
    """Busca por nome no Totem deve respeitar grupos da sessão, reserva e trava de horário."""
    from registro.nucleo import constants
    from registro.nucleo.services import grade_horarios_service

    caminho_grade = tmp_path / "grade_totem.json"
    monkeypatch.setattr(grade_horarios_service, "CAMINHO_GRADE_HORARIOS", caminho_grade)
    monkeypatch.setattr(constants, "CAMINHO_GRADE_HORARIOS", caminho_grade)
    monkeypatch.setattr(
        grade_horarios_service, "obter_dia_semana_atual", lambda: "segunda"
    )
    grade_horarios_service.salvar_grade_horarios(
        {
            "segunda": {
                "lanche": [
                    {
                        "inicio": "09:00",
                        "fim": "09:30",
                        "turmas": ["1º A"],
                        "categorias": ["*"],
                    },
                ],
                "almoco": [],
                "jantar": [],
            }
        },
        caminho_grade,
    )

    g_1a = criar_grupo(nome="1º A")
    g_2b = criar_grupo(nome="2º B")
    # Nome com 'X' não deve ser confundido com matrícula IQ300000X
    criar_estudante(prontuario="IQ300000X", nome="Outro Estudante", grupos=[g_1a])
    criar_estudante(prontuario="IQ3000099", nome="Alexandre Xavier", grupos=[g_2b])
    criar_estudante(prontuario="IQ3000088", nome="Beatriz Autorizada", grupos=[g_1a])

    sessao_lanche = criar_sessao(refeicao="lanche", data="21/10/2026", grupos=[g_1a])
    facade.definir_sessao_ativa(sessao_lanche.id)

    with patch.object(FrameSelfService, "_iniciar_camera"):
        totem = FrameSelfService(
            master=app_root, fachada=facade, notification_callback=MagicMock()
        )
        totem.pack()
        app_root.update()

        # 1. Estudante de turma não autorizada digitando o nome (com 'X') é bloqueado
        with patch.object(grade_horarios_service, "datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "09:15"
            sucesso_2b, _, _ = totem._registrar_entrada("Alexandre Xavier")
            assert sucesso_2b is False

        # 2. Estudante de turma autorizada fora do horário digitando o nome é bloqueado
        with patch.object(grade_horarios_service, "datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "10:30"
            sucesso_fora, motivo_fora, _ = totem._registrar_entrada(
                "Beatriz Autorizada"
            )
            assert sucesso_fora is False
            assert "09:00 às 09:30" in motivo_fora

        # 3. Estudante autorizada dentro do horário digitando o nome é liberada
        with patch.object(grade_horarios_service, "datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "09:15"
            sucesso_ok, _, dados_ok = totem._registrar_entrada("Beatriz Autorizada")
            assert sucesso_ok is True
            assert dados_ok["prontuario"] == "IQ3000088"

        totem.stop()
        totem.destroy()


def test_totem_timer_feedback_usb_cancela_anterior(totem_setup, app_root):
    """Sem câmera, uma nova leitura USB deve cancelar o timer de reset visual anterior."""
    totem = totem_setup["totem"]
    totem._running = False

    with patch.object(totem, "after_cancel", wraps=totem.after_cancel) as mock_cancel:
        totem._processar_codigo("IQ3000001", manual=True)
        primeiro_id = totem._id_after_feedback
        assert primeiro_id is not None

        totem._processar_codigo("IQ3000001", manual=True)
        mock_cancel.assert_any_call(primeiro_id)
        assert totem._id_after_feedback != primeiro_id


def test_totem_borda_vermelha_em_erro_camera(totem_setup):
    """Durante cooldown de erro com câmera ativa, a borda no vídeo deve ser vermelha (BGR)."""
    import numpy as np

    totem = totem_setup["totem"]
    totem._running = True
    totem._cooldown_frames = 5
    totem._ultimo_estado_feedback = "erro"
    frame_fake = np.zeros((40, 40, 3), dtype=np.uint8)
    totem._cap = MagicMock()
    totem._cap.read.return_value = (True, frame_fake)

    with (
        patch("registro.gui.autoatendimento.totem.cv2.rectangle") as mock_rect,
        patch.object(totem, "_exibir_frame_no_label"),
        patch.object(totem, "after"),
    ):
        totem._atualizar_frame()
        mock_rect.assert_called_once()
        assert mock_rect.call_args[0][3] == (0, 0, 255)
