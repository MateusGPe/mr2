# ----------------------------------------------------------------------------
# Arquivo: tests/test_dialogo_pin.py
# ----------------------------------------------------------------------------
"""
Testes unitários para o diálogo de PIN do operador.
"""

from unittest.mock import MagicMock, patch
import pytest

from registro.gui.comum.dialogo_pin import solicitar_pin


def test_solicitar_pin_sem_pin_configurado():
    with patch("registro.gui.comum.dialogo_pin.tem_pin_configurado", return_value=False):
        # Deve retornar True sem abrir nenhuma janela
        assert solicitar_pin() is True


def test_solicitar_pin_com_pin_configurado_confirmado():
    with patch("registro.gui.comum.dialogo_pin.tem_pin_configurado", return_value=True):
        mock_dialogo = MagicMock()
        mock_dialogo.resultado = True

        with patch("registro.gui.comum.dialogo_pin.DialogoPIN", return_value=mock_dialogo) as mock_cls:
            res = solicitar_pin(titulo="Teste", mensagem="Digite:")
            mock_cls.assert_called_once()
            mock_dialogo.wait_window.assert_called_once()
            assert res is True


def test_solicitar_pin_com_pin_configurado_cancelado():
    with patch("registro.gui.comum.dialogo_pin.tem_pin_configurado", return_value=True):
        mock_dialogo = MagicMock()
        mock_dialogo.resultado = False

        with patch("registro.gui.comum.dialogo_pin.DialogoPIN", return_value=mock_dialogo):
            res = solicitar_pin()
            assert res is False
