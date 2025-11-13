# ----------------------------------------------------------------------------
# Arquivo: registro/gui/painel_status_registrados.py (Painel de Status/Registrados)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

import logging
import tkinter as tk
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import CENTER, PRIMARY, WARNING
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.localization import MessageCatalog

from registro.controles.treeview_simples import TreeviewSimples
from registro.nucleo.exceptions import ErroSessaoNaoAtiva
from registro.nucleo.facade import FachadaRegistro

if TYPE_CHECKING:
    from registro.gui.app_registro import AppRegistro

logger = logging.getLogger(__name__)


class PainelStatusRegistrados(ttk.Frame):
    ID_COLUNA_ACAO = "coluna_acao"
    TEXTO_COLUNA_ACAO = "❌"

    def __init__(
        self,
        master: tk.Widget,
        app: "AppRegistro",
        fachada_nucleo: "FachadaRegistro",
    ):
        super().__init__(master, padding=(10, 10, 10, 0))
        self._app = app
        self._fachada: FachadaRegistro = fachada_nucleo

        self._label_contagem_registrados: Optional[ttk.Label] = None
        self._label_contagem_restantes: Optional[ttk.Label] = None
        self._tabela_estudantes_registrados: Optional[TreeviewSimples] = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._definicao_cols_registrados: List[Dict[str, Any]] = []

        self._criar_tabela_registrados()
        self._criar_area_contadores()

        if self._tabela_estudantes_registrados:
            self._tabela_estudantes_registrados.view.bind(
                "<Button-1>", self._ao_clicar_tabela_registrados
            )
            self._tabela_estudantes_registrados.view.bind(
                "<Delete>", self._ao_teclar_delete_tabela
            )
            self._tabela_estudantes_registrados.view.bind(
                "<BackSpace>", self._ao_teclar_delete_tabela
            )

    def _obter_definicao_cols_registrados(self) -> List[Dict[str, Any]]:
        return [
            {
                "text": "🆔 Pront.",
                "stretch": False,
                "width": 100,
                "iid": "pront",
                "minwidth": 80,
            },
            {
                "text": "✍️ Nome",
                "stretch": True,
                "iid": "nome",
                "minwidth": 150,
            },
            {
                "text": "👥 Turma",
                "stretch": False,
                "width": 150,
                "iid": "turma",
                "minwidth": 100,
            },
            {
                "text": "⏱️ Hora",
                "stretch": False,
                "width": 70,
                "anchor": CENTER,
                "iid": "hora",
                "minwidth": 60,
            },
            {
                "text": "🍽️ Prato/Status",
                "stretch": True,
                "width": 150,
                "iid": "prato",
                "minwidth": 100,
            },
            {
                "text": self.TEXTO_COLUNA_ACAO,
                "stretch": False,
                "width": 40,
                "anchor": CENTER,
                "iid": self.ID_COLUNA_ACAO,
                "minwidth": 30,
            },
        ]

    def _criar_area_contadores(self):
        frame_contadores = ttk.Frame(self, padding=(5, 5))
        frame_contadores.grid(row=0, column=0, sticky="ew")
        frame_contadores.columnconfigure(0, weight=1)
        frame_contadores.columnconfigure(1, weight=1)

        self._label_contagem_registrados = ttk.Label(
            frame_contadores,
            text="Registrados: -",
            bootstyle="secondary",  # type: ignore
            font=("Helvetica", 10, "bold"),
            padding=(5, 2),
            anchor=CENTER,
        )
        self._label_contagem_registrados.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self._label_contagem_restantes = ttk.Label(
            frame_contadores,
            text="Elegíveis: - / Restantes: -",
            bootstyle="secondary",  # type: ignore
            font=("Helvetica", 10, "bold"),
            padding=(5, 2),
            anchor=CENTER,
        )
        self._label_contagem_restantes.grid(row=0, column=1, sticky="ew", padx=(5, 0))

    def _criar_tabela_registrados(self):
        self._definicao_cols_registrados = self._obter_definicao_cols_registrados()
        self._tabela_estudantes_registrados = TreeviewSimples(
            master=self,
            dados_colunas=self._definicao_cols_registrados,
            height=15,
            enable_hover=True,
            # header_bootstyle="dark",
        )
        self._tabela_estudantes_registrados.grid(
            row=1, column=0, sticky="nsew", pady=(0, 10)
        )

        cols_ordenaveis = [
            str(cd.get("iid"))
            for cd in self._definicao_cols_registrados
            if cd.get("iid") and cd.get("iid") != self.ID_COLUNA_ACAO
        ]
        self._tabela_estudantes_registrados.configurar_ordenacao(
            colunas_ordenaveis=cols_ordenaveis or None
        )

    def carregar_estudantes_registrados(self):
        if not self._tabela_estudantes_registrados:
            return
        logger.debug("Carregando tabela de registrados...")
        try:
            dados_servidos = self._fachada.obter_estudantes_para_sessao(
                consumido=True, pular_grupos=True
            )
            if dados_servidos:
                linhas_com_acao = []
                for estudante in dados_servidos:
                    display_prato = estudante.get("prato") or "Sem Reserva"
                    linha = (
                        estudante.get("pront", ""),
                        estudante.get("nome", ""),
                        estudante.get("turma", ""),
                        estudante.get("hora_consumo", ""),
                        display_prato,
                    )
                    linha_final = tuple(map(str, linha)) + (self.TEXTO_COLUNA_ACAO,)
                    linhas_com_acao.append(linha_final)

                self._tabela_estudantes_registrados.construir_dados_tabela(
                    dados_linhas=sorted(
                        linhas_com_acao, key=lambda l: l[3], reverse=True
                    )
                )
                logger.info("%d alunos registrados carregados.", len(linhas_com_acao))
            else:
                self._tabela_estudantes_registrados.deletar_linhas()
                logger.info("Nenhum aluno registrado para exibir.")
            self.atualizar_contadores()
        except ErroSessaoNaoAtiva:
            logger.warning("Tentativa de carregar registrados sem sessão ativa.")
            self._tabela_estudantes_registrados.deletar_linhas()
            self.atualizar_contadores()
        except Exception as e:
            logger.exception("Erro ao carregar tabela de registrados: %s", e)
            Messagebox.show_error(
                "Erro",
                "Não foi possível carregar a lista de registrados.",
                parent=self._app,
            )
            if self._tabela_estudantes_registrados:
                self._tabela_estudantes_registrados.deletar_linhas()
            self.atualizar_contadores()

    def atualizar_contadores(self):
        if not self._label_contagem_registrados or not self._label_contagem_restantes:
            return

        texto_reg = "Registrados: -"
        texto_rem = "Elegíveis: - / Restantes: -"
        estilo_reg, estilo_rem = "secondary", "secondary"

        try:
            lista_registrados = self._fachada.obter_estudantes_para_sessao(
                consumido=True, pular_grupos=True
            )
            lista_elegiveis = self._fachada.obter_estudantes_para_sessao(
                consumido=False
            )
            contagem_registrados = len(lista_registrados)
            contagem_restantes = len(lista_elegiveis)
            total_elegiveis = contagem_registrados + contagem_restantes
            texto_reg = f"Registrados: {contagem_registrados}"
            texto_rem = (
                f"Elegíveis: {total_elegiveis} / Restantes: {contagem_restantes}"
            )
            estilo_reg = PRIMARY
            estilo_rem = PRIMARY
        except ErroSessaoNaoAtiva:
            pass
        except Exception as e:
            logger.exception("Erro ao atualizar contadores: %s", e)
            texto_reg, texto_rem = "Registrados: Erro", "Elegíveis: Erro"
            estilo_reg, estilo_rem = "danger", "danger"

        self._label_contagem_registrados.config(
            text=texto_reg, bootstyle=estilo_reg  # type: ignore
        )
        self._label_contagem_restantes.config(
            text=texto_rem, bootstyle=estilo_rem  # type: ignore
        )

    def limpar_tabela(self):
        logger.debug("Limpando tabela de registrados e contadores.")
        if self._tabela_estudantes_registrados:
            self._tabela_estudantes_registrados.deletar_linhas()
        self.atualizar_contadores()

    def remover_linha_da_tabela(self, iid_para_deletar: str):
        if not self._tabela_estudantes_registrados:
            return
        try:
            if self._tabela_estudantes_registrados.view.exists(iid_para_deletar):
                self._tabela_estudantes_registrados.deletar_linhas([iid_para_deletar])
                logger.debug("Linha %s removida da UI.", iid_para_deletar)
                self.atualizar_contadores()
            else:
                logger.warning(
                    "Tentativa de remover IID %s inexistente.", iid_para_deletar
                )
                self.carregar_estudantes_registrados()
        except Exception as e:
            logger.exception("Erro ao remover linha %s da UI: %s", iid_para_deletar, e)
            self.carregar_estudantes_registrados()

    def _ao_clicar_tabela_registrados(self, event: tk.Event):
        if not self._tabela_estudantes_registrados:
            return
        iid, id_col = self._tabela_estudantes_registrados.identificar_celula_clicada(
            event
        )

        if iid and id_col == self.ID_COLUNA_ACAO:
            logger.debug("Coluna de ação clicada para iid: %s", iid)
            self._confirmar_e_deletar_consumo(iid)
        elif iid and self._tabela_estudantes_registrados.view.exists(iid):
            if id_col != self.ID_COLUNA_ACAO:
                try:
                    self._tabela_estudantes_registrados.view.focus(iid)
                    if (
                        self._tabela_estudantes_registrados.obter_iid_selecionado()
                        != iid
                    ):
                        self._tabela_estudantes_registrados.view.selection_set(iid)
                except tk.TclError as e:
                    logger.warning("Erro Tcl ao focar/selecionar linha %s: %s", iid, e)

    def _ao_teclar_delete_tabela(self, _=None):
        if not self._tabela_estudantes_registrados:
            return
        iid_selecionado = self._tabela_estudantes_registrados.obter_iid_selecionado()
        if iid_selecionado:
            logger.debug("Tecla Delete pressionada para iid: %s", iid_selecionado)
            self._confirmar_e_deletar_consumo(iid_selecionado)

    def _confirmar_e_deletar_consumo(self, iid_para_deletar: str):
        if not self._tabela_estudantes_registrados:
            return

        valores_linha = self._tabela_estudantes_registrados.obter_valores_linha(
            iid_para_deletar
        )
        if not valores_linha or len(valores_linha) != len(
            self._definicao_cols_registrados
        ):
            logger.error(
                "Não foi possível obter valores para iid %s.", iid_para_deletar
            )
            Messagebox.show_error(
                "Erro Interno",
                "Erro ao obter dados da linha.",
                parent=self._app,
            )
            return

        try:
            dados_para_logica = tuple(valores_linha[:5])
            pront, nome = dados_para_logica[0], dados_para_logica[1]
            if not pront:
                raise ValueError("Prontuário vazio.")
        except (IndexError, ValueError) as e:
            logger.error("Erro ao extrair dados da linha %s: %s.", iid_para_deletar, e)
            Messagebox.show_error(
                "Erro de Dados",
                "Erro ao processar dados da linha.",
                parent=self._app,
            )
            return

        msg_confirmacao = f"Remover registro para:\n{pront} - {nome}?"
        if Messagebox.yesno(
            "Confirmar Remoção",
            msg_confirmacao,
            icon=WARNING,
            parent=self._app,
        ) == MessageCatalog.translate("Yes"):
            logger.info(
                "Confirmada exclusão para %s (iid: %s).", pront, iid_para_deletar
            )
            self._app.tratar_delecao_consumo(dados_para_logica, iid_para_deletar)
        else:
            logger.debug("Exclusão de %s cancelada.", pront)
