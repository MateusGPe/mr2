# ----------------------------------------------------------------------------
# Arquivo: tests/gui/test_gui_launcher_funcional.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Testes funcionais para a interface gráfica do Launcher (Janela de Menu Inicial),
validando interação de botões e fechamento de janela.
"""

from unittest.mock import patch

import ttkbootstrap as ttk

from registro.launcher import (
    abrir_menu_inicial,
    executar_autoatendimento,
    executar_registrar,
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
