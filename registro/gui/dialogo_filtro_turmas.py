# ----------------------------------------------------------------------------
# Arquivo: registro/gui/dialogo_filtro_turmas.py (Diálogo de Filtro de Turmas - View)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

import logging
import tkinter as tk
from tkinter import BOTH, EW, HORIZONTAL, NSEW, YES, W
from typing import TYPE_CHECKING, Callable, List, Set, Tuple, Union

import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledFrame
from ttkbootstrap.dialogs import Messagebox

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

    novo_estado = not any(var.get() for var in vars_coluna)
    for var in vars_coluna:
        var.set(novo_estado)


def criar_secao_filtro_turmas_dialogo(
    master: tk.Widget, turmas_disponiveis: List[str]
) -> Tuple[List[Tuple[str, tk.BooleanVar, ttk.Checkbutton]], ttk.Frame]:
    """
    Cria a seção de filtro de turmas, com um cabeçalho fixo e uma lista
    de checkboxes rolável.
    """
    # 1. Cria um Frame principal para conter tanto o cabeçalho quanto a área rolável.
    frame_secao = ttk.Frame(master)
    frame_secao.columnconfigure(0, weight=2)
    frame_secao.columnconfigure((1, 2), weight=1)
    # A linha da área rolável (linha 2) deve se expandir verticalmente.
    frame_secao.rowconfigure(2, weight=1)

    dados_checkbuttons = []

    # Se não houver turmas, exibe a mensagem no frame principal e retorna.
    if not turmas_disponiveis:
        ttk.Label(frame_secao, text="Nenhuma turma disponível.").grid(
            row=0, column=0, columnspan=3, pady=5
        )
        return [], frame_secao

    # Listas para controlar a seleção de colunas inteiras.
    vars_com_reserva_col: List[tk.BooleanVar] = []
    vars_sem_reserva_col: List[tk.BooleanVar] = []

    # --- 2. Cria o CABEÇALHO FIXO dentro do 'frame_secao' ---
    ttk.Label(frame_secao, text="Turma", font="-weight bold", anchor=W).grid(
        row=0, column=0, sticky=EW, padx=5, pady=(0, 5)
    )
    btn_cabecalho_com_reserva = ttk.Button(
        frame_secao,
        text="COM Reserva",
        bootstyle="success-outline",  # type: ignore
        command=lambda: _toggle_selecao_coluna(vars_com_reserva_col),
    )
    btn_cabecalho_com_reserva.grid(row=0, column=1, sticky=EW, padx=5, pady=(0, 5))

    btn_cabecalho_sem_reserva = ttk.Button(
        frame_secao,
        text="SEM Reserva (#)",
        bootstyle="warning-outline",  # type: ignore
        command=lambda: _toggle_selecao_coluna(vars_sem_reserva_col),
    )
    btn_cabecalho_sem_reserva.grid(row=0, column=2, sticky=EW, padx=5, pady=(0, 5))

    ttk.Separator(frame_secao, orient=HORIZONTAL).grid(
        row=1, column=0, columnspan=3, sticky=EW, pady=(0, 10)
    )
    # --- Fim do Cabeçalho ---

    # 3. Cria a ÁREA ROLÁVEL (ScrolledFrame) e a posiciona abaixo do cabeçalho.
    frame_rolavel = ScrolledFrame(frame_secao, padding=5)
    frame_rolavel.grid(row=2, column=0, columnspan=3, sticky=NSEW)
    frame_rolavel.columnconfigure(0, weight=2)
    frame_rolavel.columnconfigure((1, 2), weight=1)

    # 4. Adiciona os CHECKBOXES DAS TURMAS DENTRO do 'frame_rolavel'.
    for i, nome_turma in enumerate(turmas_disponiveis):
        indice_linha = i  # O índice começa em 0 dentro do ScrolledFrame
        var_com_reserva = tk.BooleanVar(value=False)
        var_sem_reserva = tk.BooleanVar(value=False)

        vars_com_reserva_col.append(var_com_reserva)
        vars_sem_reserva_col.append(var_sem_reserva)

        ttk.Label(frame_rolavel, text=nome_turma, anchor=W).grid(
            column=0, row=indice_linha, sticky="ew", padx=(10, 5), pady=2
        )
        btn_com_reserva = ttk.Checkbutton(
            frame_rolavel,
            variable=var_com_reserva,
            bootstyle="success-square-toggle",  # type: ignore
        )
        btn_com_reserva.grid(column=1, row=indice_linha, pady=2)
        btn_sem_reserva = ttk.Checkbutton(
            frame_rolavel,
            variable=var_sem_reserva,
            bootstyle="warning-square-toggle",  # type: ignore
        )
        btn_sem_reserva.grid(column=2, row=indice_linha, pady=2)

        dados_checkbuttons.extend(
            [
                (nome_turma, var_com_reserva, btn_com_reserva),
                (f"#{nome_turma}", var_sem_reserva, btn_sem_reserva),
            ]
        )

    # 5. Retorna os dados dos checkboxes e o FRAME PRINCIPAL da seção.
    return dados_checkbuttons, frame_secao


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
            Messagebox.show_error(
                "Erro de Banco de Dados",
                "Não foi possível buscar as turmas.",
                parent=self,
            )
            turmas_disponiveis = []

        grupos = self._fachada.obter_detalhes_sessao_ativa().get("grupos", set())
        excessao_grupos = {f"#{eg}" for eg in self._fachada.excessao_grupos}

        self._dados_checkbox, frame_checkbox = criar_secao_filtro_turmas_dialogo(
            frame_principal, turmas_disponiveis
        )
        frame_checkbox.grid(row=0, column=0, sticky=NSEW, pady=(0, 10))

        self._inicializar_checkboxes(grupos | excessao_grupos)

        frame_botoes = ttk.Frame(frame_principal)
        frame_botoes.grid(row=1, column=0, sticky=EW)
        frame_botoes.columnconfigure((0, 1, 2, 3), weight=1)

        ttk.Button(
            frame_botoes,
            text="⚪",
            command=self._limpar_todos,
            bootstyle="secondary-outline",  # type: ignore
        ).grid(row=0, column=0, padx=3, pady=5, sticky=EW)
        ttk.Button(
            frame_botoes,
            text="✅",
            command=self._selecionar_todos,
            bootstyle="secondary-outline",  # type: ignore
        ).grid(row=0, column=1, padx=3, pady=5, sticky=EW)
        ttk.Button(
            frame_botoes,
            text="❌",
            command=self._ao_cancelar,
            bootstyle="danger",  # type: ignore
        ).grid(row=0, column=2, padx=3, pady=5, sticky=EW)
        ttk.Button(
            frame_botoes,
            text="✔️",
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

    def _inicializar_checkboxes(self, identificadores_selecionados: Set[str]):
        if not self._dados_checkbox:
            return
        conjunto_selecionados = identificadores_selecionados
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
            Messagebox.show_error(
                "Erro no Callback",
                f"Falha ao aplicar filtros:\n{e}",
                parent=self,
            )
