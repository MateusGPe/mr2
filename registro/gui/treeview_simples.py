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
from typing import Any, Dict, List, Optional, Tuple

from ttkbootstrap.constants import END, HORIZONTAL, VERTICAL, W

logger = logging.getLogger(__name__)


class TreeviewSimples:
    def __init__(
        self,
        master: tk.Widget,
        dados_colunas: List[Dict[str, Any]],
        height: int = 10,
        bootstyle: str = "light",
    ):
        self.master = master
        self.dados_colunas = dados_colunas
        self.ids_colunas: List[str] = []
        self.mapa_texto_coluna: Dict[str, str] = {}

        for i, cd in enumerate(self.dados_colunas):
            iid = cd.get("iid")
            texto = cd.get("text", f"col_{i}")
            id_fallback = str(iid) if iid else re.sub(r"\W|^(?=\d)", "_", texto).lower()
            id_col = id_fallback
            if id_col in self.ids_colunas:
                id_col_original = id_col
                id_col = f"{id_col}_{i}"
                logger.warning(
                    "ID de coluna duplicado '%s' detectado, usando único '%s'.",
                    id_col_original,
                    id_col,
                )
            self.ids_colunas.append(id_col)
            self.mapa_texto_coluna[id_col] = texto
        logger.debug("Colunas TreeviewSimples: IDs=%s", self.ids_colunas)

        self.frame = ttk.Frame(master)
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

        sb_v = ttk.Scrollbar(self.frame, orient=VERTICAL, command=self.view.yview)
        sb_v.grid(row=0, column=1, sticky="ns")
        sb_h = ttk.Scrollbar(self.frame, orient=HORIZONTAL, command=self.view.xview)
        sb_h.grid(row=1, column=0, sticky="ew")
        self.view.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)

        self._configurar_colunas()

    def _configurar_colunas(self):
        for i, cd in enumerate(self.dados_colunas):
            id_col = self.ids_colunas[i]
            width = cd.get("width", 100)
            minwidth = cd.get("minwidth", 40)
            stretch = cd.get("stretch", False)
            anchor = cd.get("anchor", W)
            texto = cd.get("text", id_col)

            try:
                self.view.column(
                    id_col,
                    width=width,
                    minwidth=minwidth,
                    stretch=stretch,
                    anchor=anchor,
                )
                self.view.heading(id_col, text=texto, anchor=anchor)
            except tk.TclError as e:
                logger.error(
                    "Erro ao configurar coluna '%s' (Texto: '%s'): %s", id_col, texto, e
                )

    def configurar_ordenacao(self, colunas_ordenaveis: Optional[List[str]] = None):
        ids_col_alvo = (
            colunas_ordenaveis if colunas_ordenaveis is not None else self.ids_colunas
        )
        logger.debug("Configurando ordenação para colunas: %s", ids_col_alvo)
        for id_col in ids_col_alvo:
            if id_col in self.ids_colunas:
                try:
                    self.view.heading(
                        id_col, command=partial(self.ordenar_coluna, id_col, False)
                    )
                except tk.TclError as e:
                    logger.error(
                        "Erro ao definir comando de ordenação para coluna '%s': %s",
                        id_col,
                        e,
                    )
            else:
                logger.warning(
                    "Não é possível configurar ordenação para ID de coluna: '%s'",
                    id_col,
                )

    def ordenar_coluna(self, id_col: str, reverso: bool):
        if id_col not in self.ids_colunas:
            logger.error("ID de coluna desconhecido para ordenação: %s", id_col)
            return
        logger.debug("Ordenando por coluna '%s', reverso=%s", id_col, reverso)

        try:
            dados = [
                (self.view.set(iid, id_col), iid) for iid in self.view.get_children("")
            ]
        except tk.TclError as e:
            logger.error(
                "Erro ao obter dados para ordenação da coluna '%s': %s", id_col, e
            )
            return

        try:

            def funcao_chave_ordenacao(item_tupla):
                valor = item_tupla[0]
                try:
                    return float(valor)
                except ValueError:
                    pass
                try:
                    return int(valor)
                except ValueError:
                    pass
                return str(valor).lower() if isinstance(valor, str) else valor

            dados.sort(key=funcao_chave_ordenacao, reverse=reverso)
        except Exception as erro_ordem:
            logger.exception(
                "Erro ao ordenar dados da coluna '%s': %s", id_col, erro_ordem
            )
            return

        for indice, (_, iid) in enumerate(dados):
            try:
                self.view.move(iid, "", indice)
            except tk.TclError as erro_mov:
                logger.error("Erro ao mover item '%s' na ordenação: %s", iid, erro_mov)

        try:
            self.view.heading(
                id_col, command=partial(self.ordenar_coluna, id_col, not reverso)
            )
        except tk.TclError as erro_cab:
            logger.error(
                "Erro ao atualizar comando de ordenação para '%s': %s", id_col, erro_cab
            )

    def identificar_celula_clicada(
        self, event: tk.Event
    ) -> Tuple[Optional[str], Optional[str]]:
        try:
            regiao = self.view.identify_region(event.x, event.y)
            if regiao != "cell":
                return None, None
            iid = self.view.identify_row(event.y)
            simbolo_col = self.view.identify_column(event.x)
            indice_col = int(simbolo_col.replace("#", "")) - 1
            id_coluna = self.id_coluna_pelo_indice(indice_col)
            return iid, id_coluna
        except (ValueError, IndexError, TypeError, tk.TclError) as e:
            logger.warning("Não foi possível identificar célula clicada: %s", e)
            return None, None

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def deletar_linhas(self, iids: Optional[List[str]] = None):
        iids_alvo = iids if iids is not None else self.view.get_children()
        if not iids_alvo:
            return
        try:
            self.view.delete(*iids_alvo)
        except tk.TclError as e:
            logger.error("Erro ao deletar linhas %s: %s", iids_alvo, e)

    def construir_dados_tabela(self, dados_linhas: List[Tuple]):
        self.deletar_linhas()
        for valores_linha in dados_linhas:
            try:
                if len(valores_linha) == len(self.ids_colunas):
                    self.view.insert("", END, values=valores_linha)
                else:
                    logger.warning(
                        "Incompatibilidade no número de colunas ao inserir linha: "
                        "%d valores vs %d colunas. Linha: %s",
                        len(valores_linha),
                        len(self.ids_colunas),
                        valores_linha,
                    )
            except Exception as e:
                logger.error("Erro ao inserir linha %s: %s", valores_linha, e)

    def inserir_linha(
        self, valores: Tuple, index: Any = END, iid: Optional[str] = None
    ) -> Optional[str]:
        try:
            return self.view.insert("", index, values=valores, iid=iid)
        except tk.TclError as e:
            logger.error(
                "Erro ao inserir linha com valores %s (IID: %s): %s", valores, iid, e
            )
            return None

    def obter_iids_filhos(self) -> Tuple[str, ...]:
        try:
            return self.view.get_children()
        except tk.TclError as e:
            logger.error("Erro ao obter IIDs filhos: %s", e)
            return tuple()

    def obter_iid_selecionado(self) -> Optional[str]:
        selecao = self.view.selection()
        return selecao[0] if selecao else None

    def obter_valores_linha(self, iid: str) -> Optional[Tuple]:
        if not self.view.exists(iid):
            logger.warning("Tentativa de obter valores para IID inexistente: %s", iid)
            return None
        try:
            item_dict = self.view.set(iid)
            return tuple(item_dict.get(cid, "") for cid in self.ids_colunas)
        except (tk.TclError, KeyError) as e:
            logger.error("Erro ao obter valores para IID %s: %s", iid, e)
            return None

    def obter_valores_linha_selecionada(self) -> Optional[Tuple]:
        iid = self.obter_iid_selecionado()
        return self.obter_valores_linha(iid) if iid else None

    def id_coluna_pelo_indice(self, indice: int) -> Optional[str]:
        if 0 <= indice < len(self.ids_colunas):
            return self.ids_colunas[indice]
        else:
            logger.warning("Índice de coluna inválido: %d", indice)
            return None
