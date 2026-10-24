import tkinter as tk
from unittest.mock import MagicMock, patch
import pytest

from registro.gui.autoatendimento.totem import FrameSelfService
from registro.gui.autoatendimento.app import AppSelfService

@pytest.fixture
def mock_fachada():
    fachada = MagicMock()
    fachada.id_sessao_ativa = 1
    fachada.obter_detalhes_sessao_ativa.return_value = {
        "refeicao": "almoço",
        "hora": "12:00",
        "data": "2026-10-23",
        "item_servido": "Arroz e Feijão",
        "grupos": ["1INFO"],
    }
    fachada.obter_estudantes_para_sessao.return_value = []
    fachada.listar_todas_sessoes.return_value = []
    fachada.listar_todos_os_grupos.return_value = [{"nome": "1INFO"}]
    return fachada


def test_totem_pode_processar_leitura_com_e_sem_dialogo(app_root, mock_fachada):
    """Garante que _pode_processar_leitura só retorne True quando o totem estiver visível e sem diálogos."""
    app_root.deiconify()
    try:
        with patch.object(FrameSelfService, "_iniciar_camera"):
            totem = FrameSelfService(
                master=app_root,
                fachada=mock_fachada,
                notification_callback=MagicMock(),
            )
            totem.pack()
            app_root.update()

            # Sem diálogos e mapeado: deve ser True
            assert totem._pode_processar_leitura() is True

            # Cria diálogo Toplevel
            dialogo = tk.Toplevel(app_root)
            dialogo.deiconify()
            app_root.update()

            # Com diálogo aberto: deve ser False
            assert totem._pode_processar_leitura() is False

            dialogo.destroy()
            app_root.update()

            # Após destruir diálogo: volta a ser True
            assert totem._pode_processar_leitura() is True

            # Se desmapeado (pack_forget)
            totem.pack_forget()
            app_root.update()
            assert totem._pode_processar_leitura() is False

            totem.destroy()
    finally:
        app_root.withdraw()


def test_focar_entrada_nao_rouba_foco_com_dialogo(app_root, mock_fachada):
    """Testa que focar_entrada respeita o bloqueio quando um diálogo modal existe."""
    with patch.object(FrameSelfService, "_iniciar_camera"):
        totem = FrameSelfService(
            master=app_root,
            fachada=mock_fachada,
            notification_callback=MagicMock(),
        )
        totem.pack()
        app_root.update()

        dialogo = tk.Toplevel(app_root)
        entry_dialogo = tk.Entry(dialogo)
        entry_dialogo.pack()
        entry_dialogo.focus_set()
        app_root.update()

        # Tenta chamar focar_entrada no totem
        totem.focar_entrada()
        app_root.update()

        # O foco NÃO deve ter ido para a entrada do totem
        assert app_root.focus_get() != totem._entrada_manual

        dialogo.destroy()
        totem.destroy()


def test_ao_clicar_qualquer_lugar_ignora_cliques_externos(app_root, mock_fachada):
    """Garante que cliques em diálogos ou widgets externos ao totem não disparem focar_entrada."""
    with patch.object(FrameSelfService, "_iniciar_camera"):
        totem = FrameSelfService(
            master=app_root,
            fachada=mock_fachada,
            notification_callback=MagicMock(),
        )
        totem.pack()
        app_root.update()

        dialogo = tk.Toplevel(app_root)
        lbl_dialogo = tk.Label(dialogo, text="Dentro do diálogo")
        lbl_dialogo.pack()
        app_root.update()

        mock_event = MagicMock()
        mock_event.widget = lbl_dialogo

        with patch.object(totem, "after") as mock_after:
            totem._ao_clicar_qualquer_lugar(mock_event)
            mock_after.assert_not_called()

        dialogo.destroy()
        totem.destroy()


def test_pausa_qr_code_quando_dialogo_aberto(app_root, mock_fachada):
    """Garante que frames da câmera não processem QR Code quando há diálogo aberto."""
    with patch.object(FrameSelfService, "_iniciar_camera"):
        totem = FrameSelfService(
            master=app_root,
            fachada=mock_fachada,
            notification_callback=MagicMock(),
        )
        totem.pack()
        app_root.update()

        dialogo = tk.Toplevel(app_root)
        dialogo.deiconify()
        app_root.update()

        fake_frame = MagicMock()
        with patch.object(totem, "_detectar_qr_code") as mock_detectar, \
             patch.object(totem, "_exibir_frame_no_label"):
            totem._cap = MagicMock()
            totem._cap.read.return_value = (True, fake_frame)
            totem._running = True
            totem._cooldown_frames = 0

            # Executa verificação
            if totem._pode_processar_leitura():
                totem._detectar_qr_code(fake_frame)

            mock_detectar.assert_not_called()

        dialogo.destroy()
        totem.destroy()


def test_teclado_global_nao_redireciona_com_dialogo(app_root, mock_fachada):
    """Garante que digitações no teclado não sejam capturadas pelo scanner se um diálogo estiver aberto."""
    with patch.object(FrameSelfService, "_iniciar_camera"):
        totem = FrameSelfService(
            master=app_root,
            fachada=mock_fachada,
            notification_callback=MagicMock(),
        )
        totem.pack()
        app_root.update()

        # Cria um mock do AppSelfService para testar a lógica do método
        fake_app = MagicMock(spec=AppSelfService)
        fake_app.selected_frame_name = "selfservice"
        fake_app.frames = {"selfservice": totem}

        dialogo = tk.Toplevel(app_root)
        entry_dialogo = tk.Entry(dialogo)
        entry_dialogo.pack()
        dialogo.deiconify()
        app_root.update()

        fake_app.winfo_children.return_value = [dialogo]

        mock_event = MagicMock()
        mock_event.widget = entry_dialogo
        mock_event.keysym = "a"
        mock_event.char = "a"

        totem._entrada_manual.delete(0, tk.END)

        # Chama a função desvinculada passando fake_app
        AppSelfService._ao_pressionar_tecla_global(fake_app, mock_event)

        # Não deve ter inserido caractere no scanner do totem
        assert totem._entrada_manual.get() == ""

        dialogo.destroy()
        totem.destroy()
