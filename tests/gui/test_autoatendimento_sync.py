# ----------------------------------------------------------------------------
# Arquivo: tests/gui/test_autoatendimento_sync.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

from unittest.mock import MagicMock, patch
import pytest

from registro.gui.autoatendimento.app import AppSelfService


class DummyAppSelfService(AppSelfService):
    """Subclasse de teste que isola o ciclo de vida Tcl/Tk mas preserva a lógica de negócio."""

    def __init__(self, fachada):
        self.fachada_nucleo = fachada
        self.id_sessao_ativa = 1
        self.frames = {}
        self.totem_cfg = {"fullscreen": False, "require_pin_to_exit": False}
        self._frame_progresso = MagicMock()
        self._label_progresso = MagicMock()
        self._barra_progresso = MagicMock()

    def after(self, ms, func=None, *args):
        if func:
            return func(*args)
        return None

    def update(self):
        pass

    def destroy(self):
        pass


@pytest.fixture
def mock_fachada():
    """Fachada mockada com métodos comuns necessários para teste de sincronização."""
    fachada = MagicMock()
    fachada.listar_todas_sessoes.return_value = []
    fachada.listar_estudantes.return_value = []
    fachada.listar_estudantes_fuzzy.return_value = []
    fachada.listar_reservas.return_value = []
    fachada.listar_consumos_por_sessao.return_value = []
    fachada.listar_todos_os_grupos.return_value = []
    fachada.id_sessao_ativa = 1
    return fachada


@pytest.fixture
def dummy_app(mock_fachada):
    """Fornece uma instância isolada para teste de métodos do AppSelfService."""
    return DummyAppSelfService(mock_fachada)


def test_app_self_service_possui_metodos_sincronizacao(dummy_app):
    """Verifica se o AppSelfService define todos os métodos essenciais de sincronização."""
    assert hasattr(dummy_app, "_sincronizar_dados_mestre")
    assert hasattr(dummy_app, "sincronizar_sessao_com_planilha")
    assert hasattr(dummy_app, "_iniciar_thread_sinc")
    assert hasattr(dummy_app, "_executar_sinc_bloqueante")
    assert hasattr(dummy_app, "_acao_sinc_wrapper")
    assert hasattr(dummy_app, "_monitorar_thread_sinc")
    assert hasattr(dummy_app, "_logar_sincronizacao")
    assert hasattr(dummy_app, "mostrar_barra_progresso")


def test_mostrar_barra_progresso(dummy_app):
    """Testa a exibição e ocultação da barra de progresso no rodapé."""
    dummy_app.mostrar_barra_progresso(True, "Sincronizando...")
    dummy_app._barra_progresso.start.assert_called_once()
    dummy_app._label_progresso.config.assert_called_with(text="🔄 Sincronizando...")

    dummy_app.mostrar_barra_progresso(False)
    dummy_app._barra_progresso.stop.assert_called_once()
    dummy_app._frame_progresso.grid_remove.assert_called_once()


def test_sincronizacao_mestre_sucesso(dummy_app, mock_fachada):
    """Testa sincronização de entrada bem-sucedida com atualização da UI."""
    mock_fachada.sincronizar_do_google_sheets.return_value = 15
    with patch.object(dummy_app, "_atualizar_barra_sessao") as mock_update:
        dummy_app._acao_sinc_wrapper(mock_fachada.sincronizar_do_google_sheets)

        dummy_thread = MagicMock()
        dummy_thread.is_alive.return_value = False
        dummy_thread.error = None
        dummy_thread.success = True
        dummy_thread.records_affected = 15

        dummy_app._monitorar_thread_sinc(dummy_thread, "Sincronização de Cadastros", automatico=True)

        mock_fachada.registrar_log_sincronizacao.assert_called_with(
            direction="download",
            status="success",
            message="Sincronização de Cadastros concluída com sucesso.",
            records_affected=15,
        )
        mock_update.assert_called_once()


def test_sincronizacao_offline_resiliente(dummy_app, mock_fachada):
    """Testa comportamento resiliente quando offline (sem travar nem disparar exceção para o usuário)."""
    erro_conexao = ConnectionError("Não foi possível conectar ao Google Sheets (Offline)")
    mock_fachada.sincronizar_do_google_sheets.side_effect = erro_conexao

    dummy_thread = MagicMock()
    dummy_thread.is_alive.return_value = False
    dummy_thread.error = erro_conexao
    dummy_thread.success = False
    dummy_thread.records_affected = 0

    with patch("ttkbootstrap.dialogs.Messagebox.show_error") as mock_box:
        dummy_app._monitorar_thread_sinc(dummy_thread, "Sincronização de Cadastros", automatico=True)
        # Em modo automático, não deve exibir pop-up de erro ao usuário
        mock_box.assert_not_called()

        # Deve registrar log de falha de download
        mock_fachada.registrar_log_sincronizacao.assert_called_with(
            direction="download",
            status="failure",
            message=str(erro_conexao),
            records_affected=0,
        )


def test_on_closing_executa_sincronizacao_upload(dummy_app, mock_fachada):
    """Verifica se o fechamento tenta sincronizar os registros antes de sair."""
    with patch.object(dummy_app, "_executar_sinc_bloqueante") as mock_sinc_bloq, \
         patch.object(dummy_app, "destroy") as mock_destroy:
        dummy_app._on_closing()
        mock_sinc_bloq.assert_called_once_with(
            mock_fachada.sincronizar_todas_sessoes_para_google_sheets,
            "Sincronização de Servidos",
            timeout=8.0,
        )
        mock_fachada.salvar_estado_sessao.assert_called_once_with(1)
        mock_fachada.fechar_conexao.assert_called_once()
        mock_destroy.assert_called_once()
