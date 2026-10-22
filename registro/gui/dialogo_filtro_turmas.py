# ----------------------------------------------------------------------------
# Arquivo: registro/gui/dialogo_filtro_turmas.py (Diálogo de Filtro de Turmas)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

import logging
import tkinter as tk
from tkinter import BOTH, EW, HORIZONTAL, NSEW, YES, W
from typing import TYPE_CHECKING, Callable, List, Tuple

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.scrolled import ScrolledFrame

from registro.nucleo.facade import FachadaRegistro

if TYPE_CHECKING:
    from registro.gui.app_registro import AppRegistro

logger = logging.getLogger(__name__)


def _toggle_selecao_coluna(vars_coluna: List[tk.BooleanVar]):
    """
    Alterna o estado de uma lista de BooleanVars. Se algum estiver True,
    todos se tornam False; se todos estiverem False, todos se tornam True.
    """
    if not vars_coluna:
        return
    novo_estado = not any(var.get() for var in vars_coluna)
    for var in vars_coluna:
        var.set(novo_estado)


def criar_secao_filtro_turmas_dialogo(
    master: tk.Widget, turmas: List[str]
) -> Tuple[List[Tuple[str, tk.BooleanVar, ttk.Checkbutton]], ttk.Frame]:
    """
    Cria a seção de filtro de turmas com cabeçalho e lista rolável de checkboxes.

    Args:
        master: O widget pai onde esta seção será inserida.
        turmas: A lista de nomes de turmas a serem exibidas.

    Returns:
        Uma tupla contendo os dados dos checkboxes e o frame principal da seção.
    """
    frame_secao = ttk.Frame(master)
    frame_secao.columnconfigure(0, weight=2)
    frame_secao.columnconfigure((1, 2), weight=1)
    frame_secao.rowconfigure(2, weight=1)

    if not turmas:
        ttk.Label(frame_secao, text="Nenhuma turma disponível.").grid(row=0, column=0)
        return [], frame_secao

    vars_com_reserva = []
    vars_sem_reserva = []
    ttk.Label(frame_secao, text="Turma", font="-weight bold", anchor=W).grid(
        row=0, column=0, sticky=EW, padx=5
    )
    ttk.Button(
        frame_secao,
        text="COM Reserva",
        bootstyle="success-outline",
        command=lambda: _toggle_selecao_coluna(vars_com_reserva),
    ).grid(row=0, column=1, sticky=EW, padx=5)
    ttk.Button(
        frame_secao,
        text="SEM Reserva (#)",
        bootstyle="warning-outline",
        command=lambda: _toggle_selecao_coluna(vars_sem_reserva),
    ).grid(row=0, column=2, sticky=EW, padx=5)
    ttk.Separator(frame_secao, orient=HORIZONTAL).grid(
        row=1, column=0, columnspan=3, sticky=EW, pady=5
    )

    frame_rolavel = ScrolledFrame(frame_secao, padding=5, autohide=True)
    frame_rolavel.grid(row=2, column=0, columnspan=3, sticky=NSEW)
    frame_rolavel.columnconfigure(0, weight=2)
    frame_rolavel.columnconfigure((1, 2), weight=1)

    dados_checkbuttons = []
    for i, nome_turma in enumerate(turmas):
        var_com = tk.BooleanVar(value=False)
        var_sem = tk.BooleanVar(value=False)
        vars_com_reserva.append(var_com)
        vars_sem_reserva.append(var_sem)

        ttk.Label(frame_rolavel, text=nome_turma, anchor=W).grid(
            row=i, column=0, sticky="ew", padx=(10, 5), pady=2
        )
        cb_com = ttk.Checkbutton(
            frame_rolavel, variable=var_com, bootstyle="success-square-toggle"
        )
        cb_com.grid(row=i, column=1, pady=2)
        cb_sem = ttk.Checkbutton(
            frame_rolavel, variable=var_sem, bootstyle="warning-square-toggle"
        )
        cb_sem.grid(row=i, column=2, pady=2)

        dados_checkbuttons.extend(
            [
                (nome_turma, var_com, cb_com),
                (f"#{nome_turma}", var_sem, cb_sem),
            ]
        )

    return dados_checkbuttons, frame_secao


class DialogoFiltroTurmas(tk.Toplevel):
    """
    Diálogo para permitir que o usuário filtre as turmas que participam
    da sessão de registro, podendo incluir ou excluir turmas.
    """

    def __init__(
        self,
        parent: "AppRegistro",
        fachada_nucleo: "FachadaRegistro",
        callback_aplicar: Callable[[List[str]], None],
    ):
        super().__init__(parent)
        self.withdraw()
        self.title("📊 Filtrar Turmas")
        self.transient(parent)
        self.grab_set()

        self._fachada = fachada_nucleo
        self._callback_aplicar = callback_aplicar
        self._app_parente = parent
        self._dados_checkbox: List[Tuple[str, tk.BooleanVar, ttk.Checkbutton]] = []

        self._criar_widgets()
        self._inicializar_estados()

        self.protocol("WM_DELETE_WINDOW", self._ao_cancelar)
        self._centralizar_janela()
        self.resizable(True, True)
        self.deiconify()

    def _criar_widgets(self):
        """Cria e organiza os widgets no diálogo."""
        frame_principal = ttk.Frame(self, padding=15)
        frame_principal.pack(fill=BOTH, expand=YES)
        frame_principal.rowconfigure(0, weight=1)
        frame_principal.columnconfigure(0, weight=1)

        try:
            turmas = sorted(g["nome"] for g in self._fachada.listar_todos_os_grupos())
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Erro ao buscar turmas da fachada: %s", e)
            Messagebox.show_error(
                "Erro", "Não foi possível buscar as turmas.", parent=self
            )
            turmas = []

        self._dados_checkbox, frame_checkbox = criar_secao_filtro_turmas_dialogo(
            frame_principal, turmas
        )
        frame_checkbox.grid(row=0, column=0, sticky=NSEW, pady=(0, 10))

        frame_botoes = self._criar_botoes_acao(frame_principal)
        frame_botoes.grid(row=1, column=0, sticky=EW)

    def _criar_botoes_acao(self, parent: tk.Widget) -> ttk.Frame:
        """Cria os botões de ação na parte inferior do diálogo."""
        frame = ttk.Frame(parent)
        frame.columnconfigure(tuple(range(4)), weight=1)
        botoes = [
            ("⚪", self._limpar_todos, "secondary-outline"),
            ("✅", self._selecionar_todos, "secondary-outline"),
            ("❌", self._ao_cancelar, "danger"),
            ("✔️", self._ao_aplicar, "success"),
        ]
        for i, (texto, cmd, estilo) in enumerate(botoes):
            ttk.Button(frame, text=texto, command=cmd, bootstyle=estilo).grid(
                row=0, column=i, padx=3, pady=5, sticky=EW
            )
        return frame

    def _inicializar_estados(self):
        """Inicializa o estado dos checkboxes com base nos filtros da sessão ativa."""
        try:
            detalhes_sessao = self._fachada.obter_detalhes_sessao_ativa()
            grupos_ativos = detalhes_sessao.get("grupos", set())
            grupos_excluidos = {f"#{eg}" for eg in self._fachada.excessao_grupos}
            selecionados = grupos_ativos | grupos_excluidos

            for identificador, var, _ in self._dados_checkbox:
                var.set(identificador in selecionados)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Erro ao inicializar estados do filtro: %s", e)

    def _limpar_todos(self):
        """Desmarca todos os checkboxes."""
        logger.debug("Limpando todas as seleções do filtro de turmas.")
        for _, var, _ in self._dados_checkbox:
            var.set(False)

    def _selecionar_todos(self):
        """Marca todos os checkboxes (coluna 'COM Reserva')."""
        logger.debug("Selecionando todas as opções do filtro de turmas.")
        for identificador, var, _ in self._dados_checkbox:
            if not identificador.startswith("#"):
                var.set(True)

    def _ao_cancelar(self):
        """Fecha o diálogo sem aplicar as alterações."""
        logger.debug("Diálogo de filtro de turmas cancelado.")
        self.grab_release()
        self.destroy()

    def _ao_aplicar(self):
        """Aplica os filtros selecionados e fecha o diálogo."""
        if not self._dados_checkbox:
            self._ao_cancelar()
            return

        selecionados = [ident for ident, var, _ in self._dados_checkbox if var.get()]
        logger.info("Aplicando filtros de turma: %s", selecionados)

        try:
            self._callback_aplicar(selecionados)
            self.grab_release()
            self.destroy()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Erro ao executar callback de aplicação de filtro.")
            Messagebox.show_error(
                "Erro", f"Falha ao aplicar filtros:\n{e}", parent=self
            )

    def _centralizar_janela(self):
        """Centraliza o diálogo em relação à janela principal."""
        self.update_idletasks()
        if not self._app_parente:
            return

        px, py = self._app_parente.winfo_x(), self._app_parente.winfo_y()
        pw, ph = self._app_parente.winfo_width(), self._app_parente.winfo_height()
        dw, dh = self.winfo_width(), self.winfo_height()

        pos_x = px + (pw // 2) - (dw // 2)
        pos_y = py + (ph // 2) - (dh // 2)
        self.geometry(f"+{pos_x}+{pos_y}")
