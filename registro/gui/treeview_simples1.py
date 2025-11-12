# ----------------------------------------------------------------------------
# Arquivo: registro/gui/treeview_simples.py (Helper TreeView)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

import logging
import re
import tkinter as tk
from functools import partial
from tkinter import ttk
from typing import Any, Dict, List, Literal, Optional, Tuple, Union, cast

import ttkbootstrap as ttkb
from ttkbootstrap.constants import END, HORIZONTAL, VERTICAL, W
from ttkbootstrap.style import Colors

logger = logging.getLogger(__name__)


class TreeviewSimples:
    def __init__(
        self,
        master: tk.Widget,
        dados_colunas: List[Dict[str, Any]],
        height: int = 10,
        bootstyle: str = "light",
        enable_hover: bool = False,
        enable_sorting: bool = True,
        style_overrides: Optional[Dict[str, str]] = None,
    ):
        """
        Um wrapper de ttk.Treeview com funcionalidades aprimoradas e fácil customização.

        Args:
            master: O widget pai.
            dados_colunas: Lista de dicionários, cada um configurando uma coluna.
            height: A altura da Treeview em número de linhas.
            bootstyle: O estilo base do ttkbootstrap para a Treeview.
            enable_hover: Se True, ativa o efeito de destaque de linha ao passar o mouse.
            enable_sorting: Se True, ativa a ordenação de colunas ao clicar no cabeçalho.
            style_overrides: Um dicionário para sobrescrever as cores padrão.
                Chaves possíveis: 'odd_row_bg', 'hover_bg', 'hover_fg'.
                Ex: {'odd_row_bg': '#EEE', 'hover_bg': 'lightblue'}
        """
        self.master = master
        self.dados_colunas = dados_colunas
        self.ids_colunas: List[str] = []
        self.mapa_texto_coluna: Dict[str, str] = {}
        self._ultimo_iid_hover: Optional[str] = None
        self._ultimo_tags_hover: Union[Tuple[str, ...], Literal[""]] = ""

        # 1. Centralized style configuration
        self.style_config: Dict[str, str] = {}
        self._setup_styles(bootstyle,style_overrides or {})

        # ... (código de setup de colunas, como antes)
        for i, cd in enumerate(self.dados_colunas):
            iid = cd.get("iid")
            texto = cd.get("text", f"col_{i}")
            id_fallback = str(iid) if iid else re.sub(r"\W|^(?=\d)", "_", texto).lower()
            id_col = id_fallback
            if id_col in self.ids_colunas:
                id_col = f"{id_col}_{i}"
            self.ids_colunas.append(id_col)
            self.mapa_texto_coluna[id_col] = texto

        # ... (criação do frame e widgets, como antes)
        self.frame = ttk.Frame(master, borderwidth=0, padding=(4, 0, 4, 4))
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        self.view = ttk.Treeview(
            self.frame,
            columns=self.ids_colunas,
            show="headings",
            height=height,
            selectmode="browse",
            style="Custom.Treeview",
            bootstyle=bootstyle,  # type: ignore
        )
        self.view.grid(row=0, column=0, sticky="nsew")
        self.sb_v = ttk.Scrollbar(self.frame, orient=VERTICAL, command=self.view.yview)
        self.sb_h = ttk.Scrollbar(
            self.frame, orient=HORIZONTAL, command=self.view.xview
        )
        self.view.configure(
            yscrollcommand=self._autohide_scrollbar_v,
            xscrollcommand=self._autohide_scrollbar_h,
        )
        self._configurar_colunas()

        # 2. Declarative feature activation
        if enable_sorting:
            self.configurar_ordenacao()
        if enable_hover:
            self._ativar_efeito_hover()

    def _setup_styles(self, bootstyle:str, overrides: Dict[str, str]):
        """Define a paleta de cores, usando o tema como base e aplicando overrides."""
        # Defaults
        defaults = {
            "odd_row_bg": "#F0F0F0",
            "hover_bg": "#E6F7FF",
            "hover_fg": "#000000",
        }

        # Try to get theme-based colors
        try:
            if style := ttkb.Style.get_instance():
                colors: Colors = cast(Colors, style.colors)
                defaults["odd_row_bg"] = colors.light
                defaults["hover_bg"] = colors.active or colors.primary
                defaults["hover_fg"] = colors.get_foreground(
                    "active"
                ) or colors.get_foreground("primary")
        except Exception:  # pylint: disable=broad-except
            logger.warning(
                "Não foi possível obter o estilo ttkbootstrap. Usando cores padrão."
            )

        # Combine defaults with user overrides
        self.style_config = defaults
        self.style_config.update(overrides)

        logger.debug("Estilos da Treeview configurados: %s", self.style_config)

    def _ativar_efeito_hover(self):
        """Ativa o efeito de destaque de linha ao passar o mouse."""
        # Configura a tag 'hover' com as cores do nosso dicionário de estilos
        self.view.tag_configure(
            "hover",
            background=self.style_config["hover_bg"],
            foreground=self.style_config["hover_fg"],
        )
        self.view.bind("<Motion>", self._ao_mover_mouse)
        self.view.bind("<Leave>", self._ao_sair_mouse)

    def _ao_mover_mouse(self, event: tk.Event):
        """Callback para quando o mouse se move sobre a Treeview."""
        iid = self.view.identify_row(event.y)
        if iid != self._ultimo_iid_hover:
            if self._ultimo_iid_hover:
                self.view.item(self._ultimo_iid_hover, tags=self._ultimo_tags_hover)
            if iid:
                # Salva as tags existentes antes de adicionar 'hover'
                tags_existentes = self.view.item(iid, "tags")
                self._ultimo_tags_hover = tags_existentes
                # Adiciona a tag 'hover' às tags existentes
                self.view.item(iid, tags=list(tags_existentes) + ["hover"])
            self._ultimo_iid_hover = iid

    def _ao_sair_mouse(self, _event: tk.Event):
        """Callback para quando o mouse sai da área da Treeview."""
        if self._ultimo_iid_hover:
            self.view.item(self._ultimo_iid_hover, tags=self._ultimo_tags_hover)
            self._ultimo_iid_hover = None
            self._ultimo_tags_hover = tuple()

    def apply_zebra_striping(self):
        """Aplica cores alternadas às linhas."""
        # Usa a cor do nosso dicionário de estilos
        self.view.tag_configure("oddrow", background=self.style_config["odd_row_bg"])
        self.view.tag_configure("evenrow", background="")

        for i, item_id in enumerate(self.view.get_children()):
            if i % 2 == 1:
                self.view.item(item_id, tags=("oddrow",))
            else:
                self.view.item(item_id, tags=("evenrow",))

    def _autohide_scrollbar_v(self, first, last):
        first, last = float(first), float(last)
        if first == 0.0 and last == 1.0:
            self.sb_v.grid_remove()
        else:
            self.sb_v.grid(row=0, column=1, sticky="ns")
        self.sb_v.set(first, last)

    def _autohide_scrollbar_h(self, first, last):
        first, last = float(first), float(last)
        if first == 0.0 and last == 1.0:
            self.sb_h.grid_remove()
        else:
            self.sb_h.grid(row=1, column=0, sticky="ew")
        self.sb_h.set(first, last)

    def _configurar_colunas(self):
        for i, cd in enumerate(self.dados_colunas):
            id_col = self.ids_colunas[i]
            width, minwidth = cd.get("width", 100), cd.get("minwidth", 40)
            stretch, anchor = cd.get("stretch", False), cd.get("anchor", W)
            texto = cd.get("text", id_col)
            self.view.column(
                id_col, width=width, minwidth=minwidth, stretch=stretch, anchor=anchor
            )
            self.view.heading(id_col, text=texto, anchor=anchor)

    def configurar_ordenacao(self, colunas_ordenaveis: Optional[List[str]] = None):
        ids_col_alvo = (
            colunas_ordenaveis if colunas_ordenaveis is not None else self.ids_colunas
        )
        for id_col in ids_col_alvo:
            if id_col in self.ids_colunas:
                self.view.heading(
                    id_col, command=partial(self.ordenar_coluna, id_col, False)
                )

    def ordenar_coluna(self, id_col: str, reverso: bool):
        dados = [
            (self.view.set(iid, id_col), iid) for iid in self.view.get_children("")
        ]

        def sort_key(item):
            val = item[0]
            try:
                return float(val)
            except (ValueError, TypeError):
                return str(val).lower()

        dados.sort(key=sort_key, reverse=reverso)
        for i, (_, iid) in enumerate(dados):
            self.view.move(iid, "", i)
        self.apply_zebra_striping()
        self.view.heading(
            id_col, command=partial(self.ordenar_coluna, id_col, not reverso)
        )

    def identificar_celula_clicada(
        self, event: tk.Event
    ) -> Tuple[Optional[str], Optional[str]]:
        if self.view.identify_region(event.x, event.y) != "cell":
            return None, None
        iid = self.view.identify_row(event.y)
        simbolo_col = self.view.identify_column(event.x)
        id_coluna = self.id_coluna_pelo_indice(int(simbolo_col.replace("#", "")) - 1)
        return iid, id_coluna

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def deletar_linhas(self, iids: Optional[List[str]] = None):
        self.view.delete(*(iids if iids is not None else self.view.get_children()))
        self.apply_zebra_striping()

    def construir_dados_tabela(self, dados_linhas: List[Tuple]):
        self.deletar_linhas()
        for valores in dados_linhas:
            self.view.insert("", END, values=valores)  # type: ignore
        self.apply_zebra_striping()

    def obter_iids_filhos(self) -> Tuple[str, ...]:
        return self.view.get_children()

    def obter_iid_selecionado(self) -> Optional[str]:
        return sel[0] if (sel := self.view.selection()) else None

    def obter_valores_linha(self, iid: str) -> Optional[Tuple]:
        if not self.view.exists(iid):
            return None
        return tuple(self.view.set(iid).get(cid, "") for cid in self.ids_colunas)

    def id_coluna_pelo_indice(self, indice: int) -> Optional[str]:
        return self.ids_colunas[indice] if 0 <= indice < len(self.ids_colunas) else None
