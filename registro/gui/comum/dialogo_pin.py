# ----------------------------------------------------------------------------
# Arquivo: registro/gui/comum/dialogo_pin.py (Diálogo de Autenticação com Teclado Touch)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Diálogo modal moderno com teclado numérico em tela (touchscreen-friendly)
para validação de PIN de operador no Totem de Autoatendimento ou Configurações.
"""

import tkinter as tk
from typing import Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import CENTER, BOTH, X

from registro.nucleo.config_service import tem_pin_configurado, verificar_pin


class DialogoPIN(ttk.Toplevel):
    """
    Janela modal para entrada de PIN via teclado em tela ou físico.
    """

    def __init__(
        self,
        parent: Optional[tk.Widget] = None,
        titulo: str = "🔒 Autenticação do Operador",
        mensagem: str = "Digite o PIN de segurança para continuar:",
    ):
        super().__init__(parent)
        self.title(titulo)
        self.resizable(False, False)
        self.transient(parent)

        self.resultado: bool = False
        self._valor_pin: str = ""

        self._centralizar_e_dimensionar()
        self._construir_interface(mensagem)
        self._vincular_teclado()

        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        self.grab_set()
        self.focus_force()

    def _centralizar_e_dimensionar(self):
        largura, altura = 360, 480
        self.update_idletasks()
        try:
            if self.master:
                px = self.master.winfo_rootx() + (self.master.winfo_width() // 2) - (largura // 2)
                py = self.master.winfo_rooty() + (self.master.winfo_height() // 2) - (altura // 2)
            else:
                px = (self.winfo_screenwidth() // 2) - (largura // 2)
                py = (self.winfo_screenheight() // 2) - (altura // 2)
        except Exception:
            px = 100
            py = 100
        self.geometry(f"{largura}x{altura}+{max(0, px)}+{max(0, py)}")

    def _construir_interface(self, mensagem: str):
        container = ttk.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        # Mensagem do cabeçalho
        lbl_msg = ttk.Label(
            container,
            text=mensagem,
            font=("Segoe UI", 11, "bold"),
            anchor=CENTER,
            justify=CENTER,
            wraplength=320,
        )
        lbl_msg.pack(fill=X, pady=(0, 10))

        # Mostrador do PIN mascarado
        frame_display = ttk.Frame(container, padding=5)
        frame_display.pack(fill=X, pady=(0, 10))

        self.lbl_display = ttk.Label(
            frame_display,
            text="",
            font=("Segoe UI", 24, "bold"),
            anchor=CENTER,
            bootstyle="primary",
            relief="groove",
            padding=10,
        )
        self.lbl_display.pack(fill=X)

        # Mensagem de erro / feedback
        self.lbl_erro = ttk.Label(
            container,
            text="",
            font=("Segoe UI", 9, "bold"),
            bootstyle="danger",
            anchor=CENTER,
        )
        self.lbl_erro.pack(fill=X, pady=(0, 10))

        # Grid do Teclado Numérico Touch
        frame_teclado = ttk.Frame(container)
        frame_teclado.pack(fill=BOTH, expand=True)

        botoes = [
            ("1", 0, 0), ("2", 0, 1), ("3", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("7", 2, 0), ("8", 2, 1), ("9", 2, 2),
            ("⌫", 3, 0), ("0", 3, 1), ("✕", 3, 2),
        ]

        for i in range(3):
            frame_teclado.columnconfigure(i, weight=1, uniform="col")
        for i in range(4):
            frame_teclado.rowconfigure(i, weight=1, uniform="row")

        for texto, l, c in botoes:
            if texto == "⌫":
                cmd = self._apagar_digito
                estilo = "secondary-outline"
            elif texto == "✕":
                cmd = self._limpar
                estilo = "secondary-outline"
            else:
                cmd = lambda d=texto: self._adicionar_digito(d)
                estilo = "light"

            btn = ttk.Button(
                frame_teclado,
                text=texto,
                bootstyle=estilo,
                command=cmd,
                cursor="hand2",
            )
            btn.grid(row=l, column=c, padx=4, pady=4, sticky="nsew")

        # Botões de Ação
        frame_acoes = ttk.Frame(container)
        frame_acoes.pack(fill=X, pady=(15, 0))

        btn_cancelar = ttk.Button(
            frame_acoes,
            text="Cancelar (Esc)",
            bootstyle="secondary",
            command=self._cancelar,
            cursor="hand2",
        )
        btn_cancelar.pack(side="left", expand=True, fill=X, padx=(0, 5))

        btn_confirmar = ttk.Button(
            frame_acoes,
            text="Confirmar (↵)",
            bootstyle="success",
            command=self._confirmar,
            cursor="hand2",
        )
        btn_confirmar.pack(side="right", expand=True, fill=X, padx=(5, 0))

        self._atualizar_display()

    def _vincular_teclado(self):
        """Permite digitação via teclado físico do computador."""
        self.bind("<Key>", self._ao_pressionar_tecla)
        self.bind("<Return>", lambda e: self._confirmar())
        self.bind("<KP_Enter>", lambda e: self._confirmar())
        self.bind("<Escape>", lambda e: self._cancelar())
        self.bind("<BackSpace>", lambda e: self._apagar_digito())

    def _ao_pressionar_tecla(self, event: tk.Event):
        if event.char and event.char.isdigit():
            self._adicionar_digito(event.char)

    def _adicionar_digito(self, digito: str):
        if len(self._valor_pin) < 12:
            self._valor_pin += digito
            self.lbl_erro.config(text="")
            self._atualizar_display()

    def _apagar_digito(self):
        if self._valor_pin:
            self._valor_pin = self._valor_pin[:-1]
            self.lbl_erro.config(text="")
            self._atualizar_display()

    def _limpar(self):
        self._valor_pin = ""
        self.lbl_erro.config(text="")
        self._atualizar_display()

    def _atualizar_display(self):
        if not self._valor_pin:
            self.lbl_display.config(text="●  " * 4, bootstyle="secondary")
        else:
            self.lbl_display.config(
                text="● " * len(self._valor_pin), bootstyle="primary"
            )

    def _confirmar(self):
        if not self._valor_pin:
            self.lbl_erro.config(text="Digite o PIN antes de confirmar.")
            return

        if verificar_pin(self._valor_pin):
            self.resultado = True
            self.destroy()
        else:
            self.lbl_erro.config(text="PIN incorreto. Tente novamente.")
            self._valor_pin = ""
            self._atualizar_display()

    def _cancelar(self):
        self.resultado = False
        self.destroy()


def solicitar_pin(
    parent: Optional[tk.Widget] = None,
    titulo: str = "🔒 Autenticação do Operador",
    mensagem: str = "Digite o PIN de segurança para continuar:",
) -> bool:
    """
    Função utilitária de alto nível para verificação de PIN.
    Se não houver PIN configurado no sistema, retorna True automaticamente.
    Caso contrário, exibe o diálogo touch modal e aguarda o resultado.
    """
    if not tem_pin_configurado():
        return True

    dialogo = DialogoPIN(parent=parent, titulo=titulo, mensagem=mensagem)
    dialogo.wait_window()
    return dialogo.resultado
