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
from typing import Any, Dict, List, Optional, Tuple, cast

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
        bootstyle: str = "primary",  # << MUDADO: 'primary' é o padrão
        enable_hover: bool = False,
        enable_sorting: bool = True,
        style_overrides: Optional[Dict[str, str]] = None,
    ):
        """
        Um wrapper de ttk.Treeview com funcionalidades e estilo inspirados no Bootstrap.

        Args:
            master: O widget pai.
            dados_colunas: Configuração das colunas.
            height: Altura da Treeview em número de linhas.
            bootstyle: A cor base do tema (primary, success, etc.) para seleção e hover.
            enable_hover: Ativa o efeito de destaque de linha ao passar o mouse.
            enable_sorting: Ativa a ordenação ao clicar no cabeçalho.
            style_overrides: Dicionário para sobrescrever cores específicas do tema.
                Chaves: 'odd_row_bg', 'hover_bg', 'hover_fg', 'selected_bg', 'selected_fg'.
        """
        self.master = master
        self.dados_colunas = dados_colunas
        self.bootstyle = bootstyle
        self.ids_colunas: List[str] = []
        self.mapa_texto_coluna: Dict[str, str] = {}
        self._ultimo_iid_hover: Optional[str] = None
        self._ultimo_tags_hover: Tuple[str, ...] = tuple()
        self.style_config: Dict[str, str] = {}

        # --- Criação de Widgets (semelhante a antes) ---
        self.frame = ttk.Frame(master, borderwidth=0, padding=2, bootstyle=bootstyle)
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        self.view = ttk.Treeview(
            self.frame,
            columns=self._setup_column_ids(),
            show="headings",
            height=height,
            selectmode="browse",
            style="Custom.Treeview",  # Usa o estilo global da app
        )
        # --- Configuração de Estilo Centralizada ---
        self._setup_styles(style_overrides or {})
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

        # --- Ativação de Funcionalidades ---
        if enable_sorting:
            self.configurar_ordenacao()
        if enable_hover:
            self._ativar_efeito_hover()

        # Vincula o evento de seleção para aplicar a tag 'selected'
        self.view.bind("<<TreeviewSelect>>", self._ao_selecionar_item)

    def _setup_column_ids(self) -> List[str]:
        """Processa e armazena os IDs das colunas."""
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

    def _setup_styles(self, overrides: Dict[str, str]):
        """Define a paleta de cores, usando o tema como base e aplicando overrides."""
        defaults = {}
        try:
            style = ttkb.Style.get_instance()
            colors: Colors = cast(Colors, style.colors)

            # Cores base do tema
            defaults["odd_row_bg"] = colors.light

            # Cores baseadas no bootstyle (ex: 'primary', 'success')
            accent_bg = colors.get(self.bootstyle) or colors.primary
            accent_fg = colors.get_foreground(self.bootstyle) or colors.get_foreground(
                "primary"
            )

            defaults["selected_bg"] = accent_bg
            defaults["selected_fg"] = accent_fg

            # A cor de hover é uma versão mais clara da cor de seleção
            defaults["hover_bg"] = Colors.update_hsv(accent_bg, vd=0.15, sd=-0.15)
            defaults["hover_fg"] = accent_fg

        except Exception:
            logger.warning(
                "Não foi possível obter estilo ttkbootstrap. Usando cores de fallback."
            )
            defaults = {
                "odd_row_bg": "#F0F0F0",
                "hover_bg": "#E6F7FF",
                "hover_fg": "#000000",
                "selected_bg": "#007bff",
                "selected_fg": "#FFFFFF",
            }

        self.style_config = defaults
        self.style_config.update(overrides)  # Aplica personalizações do usuário

        # Configura todas as tags de uma vez
        self.view.tag_configure("oddrow", background=self.style_config["odd_row_bg"])
        self.view.tag_configure("evenrow", background="")  # Padrão
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

    def _ativar_efeito_hover(self):
        self.view.bind("<Motion>", self._ao_mover_mouse)
        self.view.bind("<Leave>", self._ao_sair_mouse)

    def _ao_mover_mouse(self, event: tk.Event):
        iid = self.view.identify_row(event.y)
        if iid != self._ultimo_iid_hover:
            if self._ultimo_iid_hover:
                self.view.item(self._ultimo_iid_hover, tags=self._ultimo_tags_hover)
            if iid:
                tags_existentes = self.view.item(iid, "tags")
                self._ultimo_tags_hover = tags_existentes
                # Não aplica hover se o item já estiver selecionado
                if "selected" not in tags_existentes:
                    self.view.item(iid, tags=["hover"])
            self._ultimo_iid_hover = iid

    def _ao_sair_mouse(self, event: tk.Event):
        if self._ultimo_iid_hover:
            self.view.item(self._ultimo_iid_hover, tags=self._ultimo_tags_hover)
            self._ultimo_iid_hover = None
            self._ultimo_tags_hover = tuple()

    def _ao_selecionar_item(self, event: tk.Event):
        """Aplica a tag 'selected' ao item selecionado e limpa dos outros."""
        # Limpa a tag 'selected' de todos os itens primeiro
        for item_id in self.view.get_children():
            tags = list(self.view.item(item_id, "tags"))
            if "selected" in tags:
                tags.remove("selected")
                self.view.item(item_id, tags=tags)

        # Aplica a tag 'selected' ao item recém-selecionado
        iid_selecionado = self.obter_iid_selecionado()
        if iid_selecionado:
            tags = list(self.view.item(iid_selecionado, "tags"))
            # Remove o hover se ele existir, pois a seleção tem prioridade
            if "hover" in tags:
                tags.remove("hover")
            if "selected" not in tags:
                tags.append("selected")
            self.view.item(iid_selecionado, tags=tags)

    def apply_zebra_striping(self):
        """Aplica cores alternadas às linhas, respeitando a seleção."""
        for i, item_id in enumerate(self.view.get_children()):
            tags = list(self.view.item(item_id, "tags"))
            # Remove tags de estilo antigas
            tags = [t for t in tags if t not in ("oddrow", "evenrow")]

            # Adiciona a tag de zebra apropriada
            if i % 2 == 1:
                tags.append("oddrow")
            else:
                tags.append("evenrow")
            self.view.item(item_id, tags=tags)

    # ... O resto dos métodos (ordenar, deletar, etc.) permanece o mesmo ...
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
        if (regiao := self.view.identify_region(event.x, event.y)) != "cell":
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
        # A zebra é aplicada ao construir a tabela, não precisa aqui

    def construir_dados_tabela(self, dados_linhas: List[Tuple]):
        self.deletar_linhas()
        for valores in dados_linhas:
            self.view.insert("", END, values=valores)
        self.apply_zebra_striping()  # Aplica a zebra depois de inserir todos os dados

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
