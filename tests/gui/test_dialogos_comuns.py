"""Testes headless para DialogoPIN e DialogoConfirmarCancelamento."""

from types import SimpleNamespace
from unittest.mock import patch

from registro.gui.comum.dialogo_cancelamento import (
    DialogoConfirmarCancelamento,
    solicitar_cancelamento_consumo,
)
from registro.gui.comum.dialogo_pin import DialogoPIN, solicitar_pin


def test_dialogo_pin_fluxo_completo(app_root):
    with patch(
        "registro.gui.comum.dialogo_pin.tem_pin_configurado", return_value=False
    ):
        assert solicitar_pin(parent=app_root) is True

    dlg = DialogoPIN(parent=app_root)
    dlg._confirmar()
    assert "Digite o PIN" in dlg.lbl_erro.cget("text")

    dlg._ao_pressionar_tecla(SimpleNamespace(char="1"))
    dlg._adicionar_digito("2")
    dlg._apagar_digito()
    dlg._limpar()
    assert dlg._valor_pin == ""

    dlg._adicionar_digito("1")
    dlg._adicionar_digito("2")
    with patch("registro.gui.comum.dialogo_pin.verificar_pin", return_value=False):
        dlg._confirmar()
        assert "PIN incorreto" in dlg.lbl_erro.cget("text")
        assert dlg._valor_pin == ""

    dlg._adicionar_digito("9")
    with patch("registro.gui.comum.dialogo_pin.verificar_pin", return_value=True):
        dlg._confirmar()
    assert dlg.resultado is True


def test_dialogo_pin_cancelar_e_solicitar_pin(app_root):
    with (
        patch("registro.gui.comum.dialogo_pin.tem_pin_configurado", return_value=True),
        patch.object(DialogoPIN, "wait_window", lambda self: self._cancelar()),
    ):
        assert solicitar_pin(parent=app_root) is False


def test_dialogo_confirmar_cancelamento_fluxo(app_root):
    with patch.object(
        DialogoConfirmarCancelamento,
        "wait_window",
        lambda self, _w=None: self._confirmar(),
    ):
        res = solicitar_cancelamento_consumo(
            app_root, "IQ3000001", "Aluno Teste", "Admin", "Erro"
        )
    assert res == (True, "Admin", "Erro")

    with patch.object(
        DialogoConfirmarCancelamento,
        "wait_window",
        lambda self, _w=None: self._cancelar(),
    ):
        res_canc = solicitar_cancelamento_consumo(app_root, "IQ3000001", "Aluno Teste")
    assert res_canc == (False, "", "")
