"""Testes funcionais headless para AppRegistro."""

import tkinter as tk
from pathlib import Path
from unittest.mock import patch

from ttkbootstrap import Style

from registro.gui.registrar.app import AppRegistro


def test_app_registro_fluxo_principal(
    app_root,
    facade,
    mock_messagebox,
    criar_grupo,
    criar_estudante,
    criar_sessao,
    criar_reserva,
    tmp_path: Path,
):
    grupo = criar_grupo(nome="1INFO")
    estudante = criar_estudante(
        prontuario="PRONT200", nome="Carlos Teste", grupos=[grupo]
    )
    criar_reserva(estudante=estudante, data="13/11/2026", prato="Padrão")
    sessao = criar_sessao(refeicao="Almoço", data="13/11/2026", grupos=[grupo])
    facade.definir_sessao_ativa(sessao.id)
    facade.salvar_estado_sessao(sessao.id)

    def _fake_window_init(self, *args, **kwargs):
        top = tk.Toplevel(app_root)
        self.__dict__.update(top.__dict__)
        self._style = Style()

    with (
        patch("tkinter.Tk.__init__", _fake_window_init),
        patch.object(AppRegistro, "_sincronizar_dados_mestre"),
    ):
        app = AppRegistro(fachada_nucleo=facade)
        try:
            assert app.get_fachada() is facade

            app.mostrar_barra_progresso(True, "Carregando...")
            app.mostrar_barra_progresso(False)

            # Resultado de dialogo
            assert app.tratar_resultado_dialogo_sessao(None) is True
            assert app.tratar_resultado_dialogo_sessao(sessao.id) is True

            # Alternar horario livre
            app._var_horario_livre.set(True)
            app._ao_alternar_horario_livre()
            assert facade.ignorar_horario_grade is True
            app._var_horario_livre.set(False)
            app._ao_alternar_horario_livre()
            assert facade.ignorar_horario_grade is False

            # Filtro de turmas
            app.ao_aplicar_filtro_turmas(["1INFO", "#2INFO"])
            assert "2INFO" in facade.excecao_grupos

            # Notificacao e delecao de consumo
            facade.definir_ignorar_horario_grade(True)
            res_reg = facade.registrar_consumo("PRONT200")
            assert res_reg["autorizado"] is True
            app.notificar_sucesso_registro(
                ("PRONT200", "Carlos Teste", "1INFO", "11:50:00")
            )
            app.tratar_delecao_consumo(
                ("PRONT200", "Carlos Teste", "1INFO", "11:50:00"),
                "iid_1",
                operador="Admin",
                motivo="Teste",
            )

            # Abertura de dialogos e janela self service
            with (
                patch("registro.gui.registrar.app.DialogoSessao") as mock_ds,
                patch("registro.gui.registrar.app.DialogoFiltroTurmas") as mock_df,
                patch("registro.gui.registrar.app.subprocess.Popen") as mock_popen,
            ):
                app._abrir_dialogo_sessao()
                mock_ds.assert_called_once()
                app._abrir_dialogo_filtro_turmas()
                mock_df.assert_called_once()
                app._abrir_janela_self_service()
                mock_popen.assert_called_once()

            # Exportar para Excel (direciona Path.home para tmp_path)
            (tmp_path / "Documents").mkdir(exist_ok=True)
            with patch("pathlib.Path.home", return_value=tmp_path):
                assert app.exportar_sessao_para_excel() is True

            # Encerramento
            app.ao_fechar_app(acionado_por_fim_sessao=True)
        finally:
            if app.winfo_exists():
                app.destroy()
