# ----------------------------------------------------------------------------
# Arquivo: tests/gui/test_gui_launcher_funcional.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Testes funcionais para a interface gráfica do Launcher (Janela de Menu Inicial e Migração),
validando interação de botões, fechamento de janela e fluxo de atualização.
"""

from unittest.mock import MagicMock, patch
import pytest
import ttkbootstrap as ttk

from registro.launcher import (
    abrir_menu_inicial,
    executar_autoatendimento,
    executar_painel,
    executar_registrar,
    executar_setup,
    verificar_e_migrar_banco_se_necessario,
)


def _executar_com_janela_capturada(app_root, acao_ao_abrir):
    """Helper para capturar a janela do menu inicial simulando interação sem bloquear."""
    janela_ref = []

    class MockWindow(ttk.Toplevel):
        def __init__(self, *args, **kwargs):
            super().__init__(app_root)
            self.withdraw()
            janela_ref.append(self)

        def mainloop(self):
            acao_ao_abrir(self)

    with patch("ttkbootstrap.Window", MockWindow):
        return abrir_menu_inicial()


def test_launcher_menu_inicial_selecionar_registrar(app_root):
    """Cenário Provável: Usuário clica no botão 'Registrar' no menu gráfico."""
    def clicar_registrar(root):
        for child in root.winfo_children():
            for subchild in child.winfo_children():
                if hasattr(subchild, "cget") and "Registrar Refeições" in subchild.cget("text"):
                    subchild.invoke()
                    return
        root.destroy()

    alvo = _executar_com_janela_capturada(app_root, clicar_registrar)
    assert alvo == executar_registrar


def test_launcher_menu_inicial_selecionar_autoatendimento(app_root):
    """Cenário Provável: Usuário clica no botão 'Totem de Autoatendimento' no menu gráfico."""
    def clicar_auto(root):
        for child in root.winfo_children():
            for subchild in child.winfo_children():
                if hasattr(subchild, "cget") and "Totem de Autoatendimento" in subchild.cget("text"):
                    subchild.invoke()
                    return
        root.destroy()

    alvo = _executar_com_janela_capturada(app_root, clicar_auto)
    assert alvo == executar_autoatendimento


def test_launcher_menu_inicial_fechar_sem_selecao(app_root):
    """Cenário Improvável: Usuário fecha a janela sem clicar em nenhum botão."""
    def fechar_janela(root):
        root.destroy()

    alvo = _executar_com_janela_capturada(app_root, fechar_janela)
    assert alvo is None


def test_launcher_migracao_confirmada(mock_messagebox):
    """Cenário Provável: Banco precisa de migração e operador aceita atualizar."""
    with patch("registro.nucleo.migracao_service.verificar_necessidade_migracao", return_value=True), \
         patch("registro.nucleo.migracao_service.executar_migracao", return_value=True) as mock_migrar:

        verificar_e_migrar_banco_se_necessario()

        assert len(mock_messagebox.yesno_calls) == 1
        mock_migrar.assert_called_once()
        assert len(mock_messagebox.info_calls) == 1
        assert "sucesso" in mock_messagebox.info_calls[0]["message"].lower()


def test_launcher_migracao_recusada(mock_messagebox):
    """Cenário Alternativo: Banco precisa de migração mas operador rejeita a operação."""
    from ttkbootstrap.localization.msgcat import MessageCatalog
    mock_messagebox.yesno_response = MessageCatalog.translate("No")

    with patch("registro.nucleo.migracao_service.verificar_necessidade_migracao", return_value=True), \
         patch("registro.nucleo.migracao_service.executar_migracao") as mock_migrar:

        verificar_e_migrar_banco_se_necessario()

        assert len(mock_messagebox.yesno_calls) == 1
        mock_migrar.assert_not_called()
        assert len(mock_messagebox.info_calls) == 0
