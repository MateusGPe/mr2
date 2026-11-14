"""Testes funcionais headless para AppSelfService."""

import tkinter as tk
from unittest.mock import MagicMock, patch

from ttkbootstrap import Style

from registro.gui.autoatendimento.app import AppSelfService


def test_app_selfservice_fluxo_principal(
    app_root,
    facade,
    mock_messagebox,
    criar_grupo,
    criar_estudante,
    criar_sessao,
    criar_reserva,
):
    grupo = criar_grupo(nome="1INFO")
    estudante = criar_estudante(prontuario="PRONT100", nome="Ana Teste", grupos=[grupo])
    criar_reserva(estudante=estudante, data="13/11/2026", prato="Padrão")
    sessao = criar_sessao(refeicao="Almoço", data="13/11/2026", grupos=[grupo])
    sessao_id = sessao.id
    facade.definir_sessao_ativa(sessao_id)
    facade.salvar_estado_sessao(sessao_id)

    def _fake_window_init(self, *args, **kwargs):
        top = tk.Toplevel(app_root)
        self.__dict__.update(top.__dict__)
        self._style = Style()

    with (
        patch("ttkbootstrap.Window.__init__", _fake_window_init),
        patch(
            "registro.gui.autoatendimento.app.obter_config_totem",
            return_value={
                "fullscreen": False,
                "camera_on_start": False,
                "require_pin_to_exit": False,
                "feedback_delay_ms": 500,
            },
        ),
        patch(
            "registro.gui.autoatendimento.app.tem_pin_configurado", return_value=False
        ),
        patch.object(AppSelfService, "_sincronizar_dados_mestre"),
    ):
        app = AppSelfService(fachada_nucleo=facade)
        try:
            assert app.get_fachada() is facade
            assert app.id_sessao_ativa == sessao_id

            # Barra de progresso
            app.mostrar_barra_progresso(True, "Sincronizando")
            app.mostrar_barra_progresso(False)

            # Alternancia de frames
            app.show_frame("dashboard")
            assert app.selected_frame_name == "dashboard"
            app.show_frame("consumos")
            assert app.selected_frame_name == "consumos"
            app.show_frame("selfservice")
            assert app.selected_frame_name == "selfservice"

            # Fullscreen toggle
            app._toggle_fullscreen()
            assert app._fullscreen is True
            app._toggle_fullscreen()
            assert app._fullscreen is False

            # Horario livre
            app._alternar_ignorar_horario_grade()
            assert facade.ignorar_horario_grade is True
            app._alternar_ignorar_horario_grade()
            assert facade.ignorar_horario_grade is False

            # Filtros de turma on-the-fly
            app.ao_aplicar_filtro_turmas(["1INFO", "#2INFO"])
            assert "2INFO" in facade.excecao_grupos

            # Resultado de dialogo de sessao (None e int)
            assert app.tratar_resultado_dialogo_sessao(None) is True
            assert app.tratar_resultado_dialogo_sessao(sessao_id) is True

            # Notificacao de registro e alteracao de consumo
            app.notificar_sucesso_registro(
                ("PRONT100", "Ana Teste", "1INFO", "11:45:00")
            )
            app._ao_alterar_consumo()

            # Abertura de dialogos mockados
            with (
                patch("registro.gui.autoatendimento.app.DialogoSessao") as mock_ds,
                patch(
                    "registro.gui.autoatendimento.app.DialogoFiltroTurmas"
                ) as mock_df,
            ):
                app._abrir_dialogo_sessao()
                mock_ds.assert_called_once()
                app._abrir_dialogo_filtro_turmas()
                mock_df.assert_called_once()

            # Encerramento seguro sem bater na Google API
            with patch.object(app, "_executar_sinc_bloqueante", new=MagicMock()):
                app._on_closing()
        finally:
            if app.winfo_exists():
                app.destroy()
