"""
Testes unitários para o utilitário multiplataforma emitir_feedback_sonoro.
"""

import sys
from unittest.mock import MagicMock, patch

from registro.gui.comum.utils import emitir_feedback_sonoro, obter_caminho_documentos


def test_feedback_sonoro_windows(monkeypatch):
    """Testa se no Windows winsound.Beep é chamado com as frequências configuradas."""
    monkeypatch.setattr(sys, "platform", "win32")
    mock_winsound = MagicMock()
    with patch.dict("sys.modules", {"winsound": mock_winsound}):
        emitir_feedback_sonoro(sucesso=True)
        assert mock_winsound.Beep.called
        freq, dur = mock_winsound.Beep.call_args[0]
        assert freq == 1000
        assert dur == 200

        mock_winsound.reset_mock()
        emitir_feedback_sonoro(sucesso=False)
        assert mock_winsound.Beep.called
        freq_err, dur_err = mock_winsound.Beep.call_args[0]
        assert freq_err == 400
        assert dur_err == 1000


def test_feedback_sonoro_linux_widget_bell(monkeypatch):
    """Testa se no Linux widget.bell() é chamado."""
    monkeypatch.setattr(sys, "platform", "linux")
    mock_widget = MagicMock()
    emitir_feedback_sonoro(sucesso=True, widget=mock_widget)
    assert mock_widget.bell.called


def test_feedback_sonoro_desabilitado(monkeypatch):
    """Testa se nenhum som é emitido quando habilitado=False nas configurações."""
    monkeypatch.setattr(
        "registro.nucleo.config_service.obter_config_audio",
        lambda: {"habilitado": False},
    )
    mock_widget = MagicMock()
    emitir_feedback_sonoro(sucesso=True, widget=mock_widget)
    assert not mock_widget.bell.called


def test_gui_obter_caminho_documentos_linux(monkeypatch, tmp_path):
    """Testa obter_caminho_documentos da GUI no Linux."""
    import platform

    docs_pt = tmp_path / "Documentos"
    docs_pt.mkdir()
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.delenv("XDG_DOCUMENTS_DIR", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    caminho = obter_caminho_documentos()
    assert str(docs_pt.resolve()) == caminho
