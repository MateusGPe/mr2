# ----------------------------------------------------------------------------
# Arquivo: registro/gui/painel_status_registrados.py (Painel de Status)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

import logging
import tkinter as tk
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import CENTER, PRIMARY, WARNING
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.localization.msgcat import MessageCatalog

from registro.controles.treeview_simples import TreeviewSimples
from registro.nucleo.exceptions import ErroSessaoNaoAtiva
from registro.nucleo.facade import FachadaRegistro

if TYPE_CHECKING:
    from registro.gui.app_registro import AppRegistro

logger = logging.getLogger(__name__)


class PainelStatusRegistrados(ttk.Frame):
    """
    Painel da UI que exibe a lista de estudantes que já tiveram o consumo
    registrado na sessão atual, juntamente com contadores de status.
    """

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

        # Referências de widgets
        self._label_contagem_registrados: Optional[ttk.Label] = None
        self._label_contagem_restantes: Optional[ttk.Label] = None
        self._tabela_estudantes_registrados: Optional[TreeviewSimples] = None
        self._definicao_cols_registrados: List[Dict[str, Any]] = []

        self._configurar_layout()
        self._criar_widgets()
        self._configurar_vinculos_eventos()

    # --------------------------------------------------------------------------
    # Configuração da Interface Gráfica
    # --------------------------------------------------------------------------

    def _configurar_layout(self):
        """Configura o grid layout do painel."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def _criar_widgets(self):
        """Cria e posiciona os widgets no painel."""
        self._criar_area_contadores()
        self._criar_tabela_registrados()

    def _criar_area_contadores(self):
        """Cria os labels para exibir as contagens de status."""
        frame = ttk.Frame(self, padding=(5, 5))
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure((0, 1), weight=1)

        self._label_contagem_registrados = ttk.Label(
            frame,
            text="Registrados: -",
            bootstyle="secondary",
            font=("Helvetica", 10, "bold"),
            anchor=CENTER,
        )
        self._label_contagem_registrados.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self._label_contagem_restantes = ttk.Label(
            frame,
            text="Elegíveis: - / Restantes: -",
            bootstyle="secondary",
            font=("Helvetica", 10, "bold"),
            anchor=CENTER,
        )
        self._label_contagem_restantes.grid(row=0, column=1, sticky="ew", padx=(5, 0))

    def _criar_tabela_registrados(self):
        """Cria a tabela (Treeview) para listar os estudantes registrados."""
        self._definicao_cols_registrados = self._obter_definicao_colunas()
        self._tabela_estudantes_registrados = TreeviewSimples(
            master=self,
            dados_colunas=self._definicao_cols_registrados,
            height=15,
            enable_hover=True,
        )
        self._tabela_estudantes_registrados.grid(
            row=1, column=0, sticky="nsew", pady=(0, 10)
        )

        cols_ordenaveis = [
            str(cd.get("iid"))
            for cd in self._definicao_cols_registrados
            if cd.get("iid") != self.ID_COLUNA_ACAO
        ]
        self._tabela_estudantes_registrados.configurar_ordenacao(cols_ordenaveis)

    def _configurar_vinculos_eventos(self):
        """Configura os bindings de eventos para a tabela de registrados."""
        if self._tabela_estudantes_registrados:
            view = self._tabela_estudantes_registrados.view
            view.bind("<Button-1>", self._ao_clicar_tabela)
            view.bind("<Delete>", self._ao_teclar_delete)
            view.bind("<BackSpace>", self._ao_teclar_delete)

    # --------------------------------------------------------------------------
    # Métodos Públicos de Atualização
    # --------------------------------------------------------------------------

    def carregar_estudantes_registrados(self):
        """Busca os dados de estudantes servidos e popula a tabela."""
        if not self._tabela_estudantes_registrados:
            return

        logger.debug("Carregando tabela de registrados...")
        try:
            dados_servidos = self._fachada.obter_estudantes_para_sessao(
                consumido=True, pular_grupos=True
            )
            if dados_servidos:
                linhas = [self._formatar_linha_para_tabela(e) for e in dados_servidos]
                linhas_ordenadas = sorted(linhas, key=lambda l: l[3], reverse=True)
                self._tabela_estudantes_registrados.construir_dados_tabela(
                    linhas_ordenadas
                )
                logger.info("%d alunos registrados carregados.", len(linhas))
            else:
                self._tabela_estudantes_registrados.deletar_linhas()
                logger.info("Nenhum aluno registrado para exibir.")

            self.atualizar_contadores()

        except ErroSessaoNaoAtiva:
            logger.warning("Tentativa de carregar registrados sem sessão ativa.")
            self.limpar_tabela()
        except Exception as e: # pylint: disable=broad-exception-caught
            logger.exception("Erro ao carregar tabela de registrados: %s", e)
            Messagebox.show_error(
                "Erro",
                "Não foi possível carregar a lista de registrados.",
                parent=self._app,
            )
            self.limpar_tabela()

    def atualizar_contadores(self):
        """Atualiza os labels de contagem com os dados mais recentes da fachada."""
        if not self._label_contagem_registrados or not self._label_contagem_restantes:
            return

        try:
            registrados = self._fachada.obter_estudantes_para_sessao(
                consumido=True, pular_grupos=True
            )
            elegiveis = self._fachada.obter_estudantes_para_sessao(consumido=False)

            n_reg = len(registrados)
            n_rest = len(elegiveis)
            n_total = n_reg + n_rest

            texto_reg = f"Registrados: {n_reg}"
            texto_rem = f"Elegíveis: {n_total} / Restantes: {n_rest}"
            estilo = PRIMARY
        except ErroSessaoNaoAtiva:
            texto_reg, texto_rem = "Registrados: -", "Elegíveis: - / Restantes: -"
            estilo = "secondary"
        except Exception as e: # pylint: disable=broad-exception-caught
            logger.exception("Erro ao atualizar contadores: %s", e)
            texto_reg, texto_rem = "Registrados: Erro", "Elegíveis: Erro"
            estilo = "danger"

        self._label_contagem_registrados.config(text=texto_reg, bootstyle=estilo)
        self._label_contagem_restantes.config(text=texto_rem, bootstyle=estilo)

    def limpar_tabela(self):
        """Limpa a tabela de registrados e reseta os contadores."""
        logger.debug("Limpando tabela de registrados e contadores.")
        if self._tabela_estudantes_registrados:
            self._tabela_estudantes_registrados.deletar_linhas()
        self.atualizar_contadores()

    # --------------------------------------------------------------------------
    # Manipuladores de Eventos e Lógica de Deleção
    # --------------------------------------------------------------------------

    def _ao_clicar_tabela(self, event: tk.Event):
        """Callback para clique na tabela. Identifica se a coluna de ação foi clicada."""
        if not self._tabela_estudantes_registrados:
            return

        iid, id_col = self._tabela_estudantes_registrados.identificar_celula_clicada(
            event
        )
        if iid and id_col == self.ID_COLUNA_ACAO:
            logger.debug("Coluna de ação clicada para iid: %s", iid)
            self._confirmar_e_deletar_consumo(iid)
        elif iid and self._tabela_estudantes_registrados.view.exists(iid):
            # Foca e seleciona a linha clicada se não for a coluna de ação
            try:
                view = self._tabela_estudantes_registrados.view
                view.focus(iid)
                if view.selection() != (iid,):
                    view.selection_set(iid)
            except tk.TclError as e:
                logger.warning("Erro Tcl ao focar/selecionar linha %s: %s", iid, e)

    def _ao_teclar_delete(self, _=None):
        """Callback para as teclas Delete/Backspace na tabela."""
        if not self._tabela_estudantes_registrados:
            return
        if iid := self._tabela_estudantes_registrados.obter_iid_selecionado():
            logger.debug("Tecla Delete pressionada para iid: %s", iid)
            self._confirmar_e_deletar_consumo(iid)

    def _confirmar_e_deletar_consumo(self, iid: str):
        """Exibe um diálogo de confirmação e, se confirmado, solicita a deleção do consumo."""
        try:
            dados_linha = self._tabela_estudantes_registrados.obter_valores_linha(iid)
            if not dados_linha or len(dados_linha) < 2:
                raise ValueError("Dados da linha incompletos ou inválidos.")

            pront, nome = dados_linha[0], dados_linha[1]
            if not pront:
                raise ValueError("Prontuário vazio.")
        except (IndexError, ValueError) as e:
            logger.error("Erro ao extrair dados da linha %s: %s.", iid, e)
            Messagebox.show_error(
                "Erro de Dados", "Erro ao processar dados da linha.", parent=self._app
            )
            return

        msg = f"Remover registro para:\n{pront} - {nome}?"
        if Messagebox.yesno(
            "Confirmar Remoção", msg, icon=WARNING, parent=self._app
        ) == MessageCatalog.translate("Yes"):
            logger.info("Confirmada exclusão para %s (iid: %s).", pront, iid)
            dados_para_logica = tuple(dados_linha[:5])
            self._app.tratar_delecao_consumo(dados_para_logica, iid)
        else:
            logger.debug("Exclusão de %s cancelada.", pront)

    # --------------------------------------------------------------------------
    # Métodos Auxiliares
    # --------------------------------------------------------------------------

    def _obter_definicao_colunas(self) -> List[Dict[str, Any]]:
        """Retorna a definição das colunas para a tabela de registrados."""
        return [
            {"text": "🆔 Pront.", "width": 100, "iid": "pront", "minwidth": 80},
            {"text": "✍️ Nome", "stretch": True, "iid": "nome", "minwidth": 150},
            {"text": "👥 Turma", "width": 150, "iid": "turma", "minwidth": 100},
            {
                "text": "⏱️ Hora",
                "width": 70,
                "anchor": CENTER,
                "iid": "hora",
                "minwidth": 60,
            },
            {
                "text": "🍽️ Prato/Status",
                "stretch": True,
                "iid": "prato",
                "minwidth": 100,
            },
            {
                "text": self.TEXTO_COLUNA_ACAO,
                "width": 40,
                "anchor": CENTER,
                "iid": self.ID_COLUNA_ACAO,
                "minwidth": 30,
                "stretch": False,
            },
        ]

    def _formatar_linha_para_tabela(self, estudante: Dict[str, Any]) -> tuple:
        """Formata um dicionário de estudante em uma tupla para a Treeview."""
        display_prato = estudante.get("prato") or "Sem Reserva"
        linha = (
            estudante.get("pront", ""),
            estudante.get("nome", ""),
            estudante.get("turma", ""),
            estudante.get("hora_consumo", ""),
            display_prato,
        )
        return tuple(map(str, linha)) + (self.TEXTO_COLUNA_ACAO,)
