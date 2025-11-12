# ----------------------------------------------------------------------------
# Arquivo: registro/gui/treeview_simples.py (Helper TreeView, Estilo Bootstrap)
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
        rowheight: int = 30,
        font: Optional[Tuple[str, int]] = None,
        heading_font: Optional[Tuple[str, int]] = None,
        header_bootstyle: str = "light",
        select_bootstyle: str = "primary",
        enable_hover: bool = False,
        enable_sorting: bool = True,
        style_overrides: Optional[Dict[str, str]] = None,
    ):
        """
        Um wrapper de ttk.Treeview autônomo e altamente personalizável.

        Args:
            master: O widget pai.
            dados_colunas: Configuração das colunas.
            height: Altura da Treeview em número de linhas.
            rowheight: A altura de cada linha em pixels.
            font: Uma tupla (nome, tamanho) para a fonte das linhas.
            heading_font: Uma tupla (nome, tamanho, peso) para a fonte do cabeçalho.
            header_bootstyle: Cor base do tema para o CABEÇALHO (light, primary, etc.).
            select_bootstyle: Cor base do tema para a SELEÇÃO de linha e HOVER.
            enable_hover: Ativa o efeito de destaque de linha ao passar o mouse.
            enable_sorting: Ativa a ordenação ao clicar no cabeçalho.
            style_overrides: Dicionário para sobrescrever cores específicas.
        """
        self.master = master
        self.dados_colunas = dados_colunas
        self.header_bootstyle = header_bootstyle
        self.select_bootstyle = select_bootstyle

        # Parâmetros de estilo
        self.rowheight = rowheight
        self.row_font = font or ("Segoe UI", 9)
        self.heading_font = heading_font or ("Segoe UI", 10, "bold")

        self.ids_colunas: List[str] = []
        self.mapa_texto_coluna: Dict[str, str] = {}
        self._ultimo_iid_hover: Optional[str] = None
        self._ultimo_tags_hover: Union[Tuple[str, ...], Literal[""]] = ""
        self.style_config: Dict[str, str] = {}

        # --- Criação de Widgets ---
        self.frame = ttk.Frame(
            master, borderwidth=0, padding=(4, 1, 4, 4), bootstyle=header_bootstyle
        )
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        self.view = ttk.Treeview(
            self.frame,
            columns=self._setup_column_ids(),
            show="headings",
            height=height,
            selectmode="browse",
        )
        self.view.grid(row=0, column=0, sticky="nsew")

        # --- Configuração de Estilo Único ---
        self._create_and_apply_style(style_overrides or {})

        self.sb_v = ttk.Scrollbar(self.frame, orient=VERTICAL, command=self.view.yview)
        self.sb_h = ttk.Scrollbar(
            self.frame, orient=HORIZONTAL, command=self.view.xview
        )
        self.view.configure(
            yscrollcommand=self._autohide_scrollbar_v,
            xscrollcommand=self._autohide_scrollbar_h,
        )
        self._configurar_colunas()

        # --- Ativação de Funcionalidades ---
        if enable_sorting:
            self.configurar_ordenacao()
        if enable_hover:
            self._ativar_efeito_hover()

        self.view.bind("<<TreeviewSelect>>", self._ao_selecionar_item)

    def _create_and_apply_style(self, overrides: Dict[str, str]):
        """Cria e aplica um conjunto de estilos únicos para esta instância da Treeview."""
        style = ttkb.Style.get_instance()
        unique_id = self.view.winfo_id()

        # Nomes de estilo únicos para evitar conflitos globais
        body_style_name = f"tv_s_body_{unique_id}.Treeview"
        heading_style_name = f"{body_style_name}.Heading"

        # 1. Configurar o corpo da Treeview (linhas)
        style.configure(
            body_style_name,
            font=self.row_font,
            rowheight=self.rowheight,
            borderwidth=0,
            highlightthickness=0,
        )

        # 2. Configurar o Cabeçalho
        try:
            colors: Colors = cast(Colors, style.colors)
            header_bg = colors.get(self.header_bootstyle) or colors.light
            header_fg = colors.get_foreground(
                self.header_bootstyle
            ) or colors.get_foreground("light")

            style.configure(
                heading_style_name,
                font=self.heading_font,
                background=header_bg,
                foreground=header_fg,
            )

            # Mapeamento de hover e press para o cabeçalho
            hover_color = Colors.update_hsv(header_bg, vd=0.15)
            press_color = Colors.update_hsv(header_bg, vd=-0.15)
            style.map(
                heading_style_name,
                background=[
                    ("pressed", press_color),
                    ("active", hover_color),
                ],
            )
        except Exception:
            logger.warning(
                "Não foi possível aplicar estilos de cabeçalho ttkbootstrap."
            )

        # 3. Configurar as cores das TAGS (zebra, seleção, hover)
        self._setup_tag_styles(overrides)

        # 4. Aplicar o estilo principal ao widget
        self.view.configure(style=body_style_name)

    def _setup_tag_styles(self, overrides: Dict[str, str]):
        """Define a paleta de cores para as tags, usando o tema e overrides."""
        defaults = {}
        try:
            style = ttkb.Style.get_instance()
            colors: Colors = cast(Colors, style.colors)

            defaults["odd_row_bg"] = colors.light

            accent_bg = colors.get(self.select_bootstyle) or colors.primary
            accent_fg = colors.get_foreground(
                self.select_bootstyle
            ) or colors.get_foreground("primary")

            defaults["selected_bg"] = accent_bg
            defaults["selected_fg"] = accent_fg

            defaults["hover_bg"] = Colors.update_hsv(accent_bg, vd=0.15, sd=-0.15)
            defaults["hover_fg"] = accent_fg

        except Exception:
            logger.warning("Usando cores de fallback para tags.")
            defaults = {
                "odd_row_bg": "#F0F0F0",
                "hover_bg": "#E6F7FF",
                "hover_fg": "#000000",
                "selected_bg": "#007bff",
                "selected_fg": "#FFFFFF",
            }

        self.style_config = {**defaults, **overrides}

        self.view.tag_configure("oddrow", background=self.style_config["odd_row_bg"])
        self.view.tag_configure("evenrow", background="")
        self.view.tag_configure(
            "selected",
            background=self.style_config["selected_bg"],
            foreground=self.style_config["selected_fg"],
        )
        self.view.tag_configure(
            "hover",
            background=self.style_config["hover_bg"],
            foreground=self.style_config["hover_fg"],
        )

    # ... (O resto da classe permanece exatamente o mesmo da versão anterior) ...
    def _setup_column_ids(self) -> List[str]:
        for i, cd in enumerate(self.dados_colunas):
            iid = cd.get("iid")
            texto = cd.get("text", f"col_{i}")
            id_fallback = str(iid) if iid else re.sub(r"\W|^(?=\d)", "_", texto).lower()
            id_col = id_fallback
            if id_col in self.ids_colunas:
                id_col = f"{id_col}_{i}"
            self.ids_colunas.append(id_col)
            self.mapa_texto_coluna[id_col] = texto
        return self.ids_colunas

    def _ativar_efeito_hover(self):
        self.view.bind("<Motion>", self._ao_mover_mouse)
        self.view.bind("<Leave>", self._ao_sair_mouse)

    def _ao_mover_mouse(self, event: tk.Event):
        iid = self.view.identify_row(event.y)
        if iid != self._ultimo_iid_hover:
            if self._ultimo_iid_hover and self.view.exists(self._ultimo_iid_hover):
                self.view.item(self._ultimo_iid_hover, tags=self._ultimo_tags_hover)
            if iid:
                tags_existentes = self.view.item(iid, "tags")
                self._ultimo_tags_hover = tags_existentes
                if "selected" not in tags_existentes:
                    self.view.item(iid, tags=["hover"])
            self._ultimo_iid_hover = iid

    def _ao_sair_mouse(self, _event: tk.Event):
        if self._ultimo_iid_hover:
            if self.view.exists(self._ultimo_iid_hover):
                self.view.item(self._ultimo_iid_hover, tags=self._ultimo_tags_hover)
            self._ultimo_iid_hover = None
            self._ultimo_tags_hover = ""

    def _ao_selecionar_item(self, _event: tk.Event):
        for item_id in self.view.get_children():
            tags = list(self.view.item(item_id, "tags"))
            if "selected" in tags:
                tags.remove("selected")
                self.view.item(item_id, tags=tags)
        if iid_selecionado := self.obter_iid_selecionado():
            tags = list(self.view.item(iid_selecionado, "tags"))
            if "hover" in tags:
                tags.remove("hover")
            if "selected" not in tags:
                tags.append("selected")
            self.view.item(iid_selecionado, tags=tags)

    def apply_zebra_striping(self):
        for i, item_id in enumerate(self.view.get_children()):
            tags = [
                t
                for t in self.view.item(item_id, "tags")
                if t not in ("oddrow", "evenrow")
            ]
            tags.append("oddrow" if i % 2 == 1 else "evenrow")
            self.view.item(item_id, tags=tags)

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

    def construir_dados_tabela(self, dados_linhas: List[Tuple]):
        self.deletar_linhas()
        [self.view.insert("", END, values=v) for v in dados_linhas]
        self.apply_zebra_striping()

    def obter_iids_filhos(self) -> Tuple[str, ...]:
        return self.view.get_children()

    def obter_iid_selecionado(self) -> Optional[str]:
        return sel[0] if (sel := self.view.selection()) else None

    def obter_valores_linha(self, iid: str) -> Optional[Tuple]:
        return (
            tuple(self.view.set(iid).get(c, "") for c in self.ids_colunas)
            if self.view.exists(iid)
            else None
        )

    def obter_linha_selecionada(self) -> Optional[Tuple]:
        if not (ln := self.view.selection()):
            return None
        iid = ln[0]
        return (
            tuple(self.view.set(iid).get(c, "") for c in self.ids_colunas)
            if self.view.exists(iid)
            else None
        )

    def id_coluna_pelo_indice(self, indice: int) -> Optional[str]:
        return (
            self.ids_colunas[i] if 0 <= (i := indice) < len(self.ids_colunas) else None
        )
