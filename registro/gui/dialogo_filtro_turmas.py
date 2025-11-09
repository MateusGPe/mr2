# ----------------------------------------------------------------------------
# Arquivo: registro/gui/dialogo_filtro_turmas.py (Diálogo de Filtro de Turmas - View)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

import logging
import tkinter as tk
from tkinter import BOTH, EW, HORIZONTAL, NSEW, W, YES, messagebox
from typing import TYPE_CHECKING, Callable, List, Tuple, Union

import ttkbootstrap as ttk
from registro.nucleo.facade import FachadaRegistro

if TYPE_CHECKING:
    from registro.gui.app_registro import AppRegistro

logger = logging.getLogger(__name__)


def _toggle_selecao_coluna(vars_coluna: List[tk.BooleanVar]):
    """
    Alterna o estado de uma lista de BooleanVars.
    - Se algum estiver True, todos se tornarão False.
    - Se todos estiverem False, todos se tornarão True.
    """
    if not vars_coluna:
        return
    # Determina o novo estado: True se TODOS estiverem False, caso contrário False.
    novo_estado = not any(var.get() for var in vars_coluna)
    for var in vars_coluna:
        var.set(novo_estado)


def criar_secao_filtro_turmas_dialogo(
    master: tk.Widget, turmas_disponiveis: List[str]
) -> Tuple[List[Tuple[str, tk.BooleanVar, ttk.Checkbutton]], ttk.Frame]:
    """Cria a seção de checkboxes para o filtro de turmas em um layout de tabela."""
    frame_interno = ttk.Frame(master, padding=5)
    frame_interno.columnconfigure(0, weight=2)
    frame_interno.columnconfigure((1, 2), weight=1)

    dados_checkbuttons = []

    if not turmas_disponiveis:
        ttk.Label(frame_interno, text="Nenhuma turma disponível.").grid(
            row=0, column=0, columnspan=3, pady=5
        )
        return [], frame_interno

    # --- Listas para agrupar as variáveis de cada coluna ---
    vars_com_reserva_col: List[tk.BooleanVar] = []
    vars_sem_reserva_col: List[tk.BooleanVar] = []

    # --- Cabeçalho da Tabela (estático) ---
    ttk.Label(frame_interno, text="Turma", font="-weight bold", anchor=W).grid(
        row=0, column=0, sticky=EW, padx=5, pady=(0, 5)
    )

    # --- Linhas de Dados (uma por turma) ---
    # O grid dos cabeçalhos foi movido para depois do loop para que os comandos
    # dos botões tenham acesso às listas de variáveis já povoadas.
    for i, nome_turma in enumerate(turmas_disponiveis):
        indice_linha = (
            i + 2
        )  # Começa da linha 2 para deixar espaço para cabeçalho/separador
        var_com_reserva = tk.BooleanVar(value=False)
        var_sem_reserva = tk.BooleanVar(value=False)

        # Adiciona as variáveis às listas de controle de coluna
        vars_com_reserva_col.append(var_com_reserva)
        vars_sem_reserva_col.append(var_sem_reserva)

        ttk.Label(frame_interno, text=nome_turma, anchor=W).grid(
            column=0, row=indice_linha, sticky="ew", padx=(10, 5), pady=2
        )
        btn_com_reserva = ttk.Checkbutton(
            frame_interno, variable=var_com_reserva, bootstyle="success-square-toggle"
        )
        btn_com_reserva.grid(column=1, row=indice_linha, pady=2)
        btn_sem_reserva = ttk.Checkbutton(
            frame_interno, variable=var_sem_reserva, bootstyle="warning-square-toggle"
        )
        btn_sem_reserva.grid(column=2, row=indice_linha, pady=2)

        dados_checkbuttons.extend(
            [
                (nome_turma, var_com_reserva, btn_com_reserva),
                (f"#{nome_turma}", var_sem_reserva, btn_sem_reserva),
            ]
        )

    # --- Cabeçalhos Interativos (Botões) ---
    # Criados aqui para que as lambdas capturem as listas de vars já completas.
    btn_cabecalho_com_reserva = ttk.Button(
        frame_interno,
        text="COM Reserva",
        bootstyle="success-outline",  # type: ignore
        command=lambda: _toggle_selecao_coluna(vars_com_reserva_col),
    )
    btn_cabecalho_com_reserva.grid(row=0, column=1, sticky=EW, padx=5, pady=(0, 5))

    btn_cabecalho_sem_reserva = ttk.Button(
        frame_interno,
        text="SEM Reserva (#)",
        bootstyle="warning-outline",  # type: ignore
        command=lambda: _toggle_selecao_coluna(vars_sem_reserva_col),
    )
    btn_cabecalho_sem_reserva.grid(row=0, column=2, sticky=EW, padx=5, pady=(0, 5))

    ttk.Separator(frame_interno, orient=HORIZONTAL).grid(
        row=1, column=0, columnspan=3, sticky=EW, pady=(0, 10)
    )

    return dados_checkbuttons, frame_interno


class DialogoFiltroTurmas(tk.Toplevel):
    def __init__(
        self,
        parent: Union["AppRegistro", None],
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

        frame_principal = ttk.Frame(self, padding=15)
        frame_principal.pack(fill=BOTH, expand=YES)
        frame_principal.rowconfigure(0, weight=1)
        frame_principal.columnconfigure(0, weight=1)

        try:
            turmas_disponiveis = sorted(
                g["nome"] for g in self._fachada.listar_todos_os_grupos()
            )
        except Exception as e:
            logger.exception(
                "Erro ao buscar turmas disponíveis da fachada. %s: %s",
                type(e).__name__,
                e,
            )
            messagebox.showerror(
                "Erro de Banco de Dados",
                "Não foi possível buscar as turmas.",
                parent=self,
            )
            turmas_disponiveis = []

        grupos = self._fachada.obter_detalhes_sessao_ativa().get("grupos", [])
        excessao_grupos = [f"#{eg}" for eg in self._fachada.excessao_grupos]
        identificadores_selecionados_atualmente: List[str] = grupos + excessao_grupos

        self._dados_checkbox, frame_checkbox = criar_secao_filtro_turmas_dialogo(
            frame_principal, turmas_disponiveis
        )
        frame_checkbox.grid(row=0, column=0, sticky=NSEW, pady=(0, 10))

        self._inicializar_checkboxes(identificadores_selecionados_atualmente)

        frame_botoes = ttk.Frame(frame_principal)
        frame_botoes.grid(row=1, column=0, sticky=EW)
        frame_botoes.columnconfigure((0, 1, 2, 3), weight=1)

        ttk.Button(
            frame_botoes,
            text="⚪ Limpar Todos",
            command=self._limpar_todos,
            bootstyle="secondary-outline",  # type: ignore
        ).grid(row=0, column=0, padx=3, pady=5, sticky=EW)
        ttk.Button(
            frame_botoes,
            text="✅ Selecionar Todos",
            command=self._selecionar_todos,
            bootstyle="secondary-outline",  # type: ignore
        ).grid(row=0, column=1, padx=3, pady=5, sticky=EW)
        ttk.Button(
            frame_botoes,
            text="❌ Cancelar",
            command=self._ao_cancelar,
            bootstyle="danger",  # type: ignore
        ).grid(row=0, column=2, padx=3, pady=5, sticky=EW)
        ttk.Button(
            frame_botoes,
            text="✔️ Aplicar Filtros",
            command=self._ao_aplicar,
            bootstyle="success",  # type: ignore
        ).grid(row=0, column=3, padx=3, pady=5, sticky=EW)

        self.protocol("WM_DELETE_WINDOW", self._ao_cancelar)
        self.update_idletasks()
        self._centralizar_janela()
        self.resizable(True, True)
        self.deiconify()

    def _centralizar_janela(self):
        self.update_idletasks()
        parente = self._app_parente

        if not parente:
            logger.warning("Tentativa de centralizar o diálogo sem janela pai.")
            return

        parente_x = parente.winfo_x()
        parente_y = parente.winfo_y()
        parente_w = parente.winfo_width()
        parente_h = parente.winfo_height()
        dialog_w = self.winfo_width()
        dialog_h = self.winfo_height()
        pos_x = parente_x + (parente_w // 2) - (dialog_w // 2)
        pos_y = parente_y + (parente_h // 2) - (dialog_h // 2)
        self.geometry(f"+{pos_x}+{pos_y}")

    def _inicializar_checkboxes(self, identificadores_selecionados: List[str]):
        if not self._dados_checkbox:
            return
        conjunto_selecionados = set(identificadores_selecionados)
        for identificador, var_tk, _ in self._dados_checkbox:
            var_tk.set(identificador in conjunto_selecionados)

    def _limpar_todos(self):
        if not self._dados_checkbox:
            return
        logger.debug("Limpando todas as seleções do filtro de turmas.")
        for _, var_tk, _ in self._dados_checkbox:
            var_tk.set(False)

    def _selecionar_todos(self):
        if not self._dados_checkbox:
            return
        logger.debug("Selecionando todas as opções do filtro de turmas.")
        for _, var_tk, _ in self._dados_checkbox:
            var_tk.set(True)

    def _ao_cancelar(self):
        logger.debug("Diálogo de filtro de turmas cancelado.")
        self.grab_release()
        self.destroy()

    def _ao_aplicar(self):
        if not self._dados_checkbox:
            self._ao_cancelar()
            return

        identificadores_recem_selecionados = [
            identificador
            for identificador, var_tk, _ in self._dados_checkbox
            if var_tk.get()
        ]
        logger.info(
            "Aplicando filtros de turma: %s", identificadores_recem_selecionados
        )

        try:
            self._callback_aplicar(identificadores_recem_selecionados)
            self.grab_release()
            self.destroy()
        except Exception as e:
            logger.exception(
                "Erro ocorreu durante a execução do callback de aplicação de filtro."
            )
            messagebox.showerror(
                "Erro no Callback",
                f"Falha ao aplicar filtros:\n{e}",
                parent=self,
            )
