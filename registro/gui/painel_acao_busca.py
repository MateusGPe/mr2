# ----------------------------------------------------------------------------
# Arquivo: registro/gui/painel_acao_busca.py (Painel de Ação/Busca)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

import logging
import re
import tkinter as tk
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import ttkbootstrap as ttk
from fuzzywuzzy import fuzz
from ttkbootstrap.constants import DISABLED, LEFT, NORMAL, W
from ttkbootstrap.dialogs import Messagebox

from registro.controles.treeview_simples import TreeviewSimples
from registro.gui.constants import REGEX_LIMPEZA_PRONTUARIO
from registro.nucleo.exceptions import ErroSessaoNaoAtiva
from registro.nucleo.facade import FachadaRegistro

if TYPE_CHECKING:
    from registro.gui.app_registro import AppRegistro

logger = logging.getLogger(__name__)


class PainelAcaoBusca(ttk.Frame):
    """
    Painel da interface gráfica para busca e registro de consumo dos estudantes.

    Este painel contém um campo de busca, uma lista de resultados de estudantes
    elegíveis, uma área de pré-visualização do estudante selecionado e botões
    para registrar o consumo.
    """

    TERMOS_BUSCA_TODOS: List[str] = ["todos", "---", "***", ".."]
    ATRASO_DEBOUNCE_BUSCA: int = 100

    def __init__(
        self,
        master: tk.Widget,
        app: "AppRegistro",
        fachada_nucleo: "FachadaRegistro",
    ):
        super().__init__(master, padding=10)
        self._app = app
        self._fachada = fachada_nucleo

        # Atributos de estado
        self._id_after_busca: Optional[str] = None
        self._dados_correspondencias_elegiveis_atuais: List[Dict[str, Any]] = []
        self._dados_elegivel_selecionado: Optional[Dict[str, Any]] = None

        # Atributos de widgets da interface
        self._var_entrada_busca: tk.StringVar = tk.StringVar()
        self._entrada_busca: Optional[ttk.Entry] = None
        self._botao_limpar: Optional[ttk.Button] = None
        self._tree_estudantes_elegiveis: Optional[TreeviewSimples] = None
        self._label_aluno_selecionado: Optional[ttk.Label] = None
        self._botao_registrar: Optional[ttk.Button] = None
        self._label_feedback_acao: Optional[ttk.Label] = None

        self.grupos_excluidos: List[str] = []
        self.grupos_selecionados: List[str] = []

        self._configurar_layout()
        self._criar_widgets()
        self._configurar_vinculos_eventos()

    # --------------------------------------------------------------------------
    # Propriedades
    # --------------------------------------------------------------------------

    @property
    def id_after_busca(self) -> Optional[str]:
        return self._id_after_busca

    @id_after_busca.setter
    def id_after_busca(self, value: Optional[str]):
        self._id_after_busca = value

    # --------------------------------------------------------------------------
    # Configuração da Interface Gráfica
    # --------------------------------------------------------------------------

    def _configurar_layout(self):
        """Configura o grid layout do painel."""
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def _criar_widgets(self):
        """Cria e posiciona os widgets no painel."""
        self._criar_barra_busca()
        self._criar_area_preview()
        self._criar_lista_elegiveis()

    def _criar_barra_busca(self):
        """Cria a barra de busca com campo de entrada e botões."""
        barra_busca = ttk.Frame(self, bootstyle="ligth", padding=1)
        barra_busca.grid(row=0, column=0, sticky="ew", pady=(0, 1))
        barra_busca.grid_columnconfigure(0, weight=1)

        self._entrada_busca = ttk.Entry(
            barra_busca,
            textvariable=self._var_entrada_busca,
            font=(None, 12),
            bootstyle="ligth",
        )
        self._entrada_busca.grid(row=0, column=0, sticky="ew")

        self._botao_limpar = ttk.Button(
            barra_busca,
            text="❌",
            command=self.limpar_busca,
            bootstyle="danger",
            state=DISABLED,
        )
        self._botao_limpar.grid(row=0, column=1, padx=2, sticky="ew")

        self._botao_registrar = ttk.Button(
            barra_busca,
            text="➕",
            command=self._registrar_elegivel_selecionado,
            bootstyle="success",
            state=DISABLED,
        )
        self._botao_registrar.grid(row=0, column=2, sticky="ew", padx=(0, 2))

    def _criar_area_preview(self):
        """Cria a área de pré-visualização do aluno selecionado."""
        frame_preview = ttk.Frame(
            self, padding=(0, 1), height=200, bootstyle="secondary"
        )
        frame_preview.grid(row=1, column=0, sticky="nsew", pady=(0, 5))

        self._label_aluno_selecionado = ttk.Label(
            frame_preview,
            text="Pesquise um aluno.",
            justify=LEFT,
            bootstyle="inverse-info",
            wraplength=350,
            style="Preview.TLabel",
        )
        self._label_aluno_selecionado.pack(fill="both", side="left", expand=True)

    def _criar_lista_elegiveis(self):
        """Cria a tabela (Treeview) para listar os estudantes elegíveis."""
        cols_elegiveis = [
            {"text": "Nome", "stretch": True},
            {"text": "Prontuario", "width": 80, "anchor": W, "minwidth": 100},
            {"text": "Turma", "width": 80, "anchor": W, "minwidth": 100},
            {"text": "Prato/Status", "width": 130, "anchor": W, "minwidth": 80},
        ]
        self._tree_estudantes_elegiveis = TreeviewSimples(
            master=self,
            dados_colunas=cols_elegiveis,
            height=10,
            enable_hover=True,
        )
        self._tree_estudantes_elegiveis.grid(row=2, column=0, sticky="nsew")

    def _configurar_vinculos_eventos(self):
        """Configura os bindings de eventos para os widgets."""
        self._var_entrada_busca.trace_add("write", self._na_mudanca_entrada_busca)

        if self._entrada_busca:
            self._entrada_busca.bind(
                "<Return>", lambda _: self._registrar_elegivel_selecionado()
            )
            self._entrada_busca.bind(
                "<Down>", lambda _: self._selecionar_proximo_elegivel(1)
            )
            self._entrada_busca.bind(
                "<Up>", lambda _: self._selecionar_proximo_elegivel(-1)
            )
            self._entrada_busca.bind(
                "<Escape>", lambda _: self._var_entrada_busca.set("")
            )

        if self._tree_estudantes_elegiveis:
            self._tree_estudantes_elegiveis.view.bind(
                "<<TreeviewSelect>>", self._ao_selecionar_estudante_elegivel
            )
            self._tree_estudantes_elegiveis.view.bind(
                "<Double-1>", lambda _: self._registrar_elegivel_selecionado()
            )

    # --------------------------------------------------------------------------
    # Métodos Públicos de Controle da Interface
    # --------------------------------------------------------------------------

    def habilitar_controles(self):
        """Habilita os controles do painel para interação."""
        if self._entrada_busca:
            self._entrada_busca.config(state=NORMAL)
        if self._botao_limpar:
            self._botao_limpar.config(state=NORMAL)
        if self._botao_registrar:
            self._botao_registrar.config(state=DISABLED)
        logger.debug("Controles do painel de ação habilitados.")
        self.focar_entrada()

    def desabilitar_controles(self):
        """Desabilita os controles do painel."""
        if self._entrada_busca:
            self._entrada_busca.config(state=DISABLED)
            self._var_entrada_busca.set("")
        if self._botao_limpar:
            self._botao_limpar.config(state=DISABLED)
        if self._botao_registrar:
            self._botao_registrar.config(state=DISABLED)
        if self._tree_estudantes_elegiveis:
            self._tree_estudantes_elegiveis.deletar_linhas()

        self._dados_elegivel_selecionado = None
        self._dados_correspondencias_elegiveis_atuais = []
        self._atualizar_label_preview()
        logger.debug("Controles do painel de ação desabilitados.")

    def focar_entrada(self):
        """Coloca o foco no campo de busca."""
        if self._entrada_busca:
            self.after(30, self._entrada_busca.focus_set)
            logger.debug("Foco agendado para o campo de busca.")
        else:
            logger.warning("Tentativa de focar campo de busca não inicializado.")

    def limpar_busca(self, *_):
        """Limpa o campo de busca e reseta a lista de resultados."""
        logger.debug("Limpando busca no painel de ação.")
        if self._entrada_busca:
            self._var_entrada_busca.set("")
            self.focar_entrada()
        else:
            logger.warning("Tentativa de limpar busca com campo não inicializado.")

    def atualizar_resultados(self):
        """Força a atualização dos resultados da busca."""
        logger.debug("Atualizando resultados da busca.")
        if self._id_after_busca is not None:
            self.after_cancel(self._id_after_busca)
            self._id_after_busca = None
        self._executar_busca_real()

    # --------------------------------------------------------------------------
    # Manipuladores de Eventos (Callbacks)
    # --------------------------------------------------------------------------

    def _na_mudanca_entrada_busca(self, *_):
        """
        Callback acionado quando o texto no campo de busca é alterado.
        Inicia um temporizador para executar a busca após um curto atraso (debounce).
        """
        if self._id_after_busca is not None:
            self.after_cancel(self._id_after_busca)
            self._id_after_busca = None

        termo_busca = self._var_entrada_busca.get()
        if len(termo_busca) < 2:
            self._resetar_estado_busca()
            return

        if self._botao_limpar:
            self._botao_limpar.config(state=NORMAL)

        self._id_after_busca = self.after(
            self.ATRASO_DEBOUNCE_BUSCA, self._executar_busca_real
        )

    def _ao_selecionar_estudante_elegivel(self, _=None):
        """
        Callback acionado quando um estudante é selecionado na lista de elegíveis.
        """
        if not self._tree_estudantes_elegiveis:
            return

        iid_selecionado = self._tree_estudantes_elegiveis.obter_iid_selecionado()
        if not iid_selecionado:
            self._dados_elegivel_selecionado = None
            self._atualizar_label_preview()
            if self._botao_registrar:
                self._botao_registrar.config(state=DISABLED)
            return

        try:
            dados_estudante = next(
                (
                    d
                    for d in self._dados_correspondencias_elegiveis_atuais
                    if d.get("Pront") == iid_selecionado
                ),
                None,
            )
            if dados_estudante:
                self._dados_elegivel_selecionado = dados_estudante
                if self._botao_registrar:
                    self._botao_registrar.config(state=NORMAL)
            else:
                logger.error(
                    "Inconsistência de dados para o prontuário: %s", iid_selecionado
                )
                self._dados_elegivel_selecionado = None
                if self._botao_registrar:
                    self._botao_registrar.config(state=DISABLED)
        except (ValueError, IndexError, AttributeError, tk.TclError) as e:
            logger.exception("Erro ao processar seleção de elegível: %s", e)
            self._dados_elegivel_selecionado = None
            if self._botao_registrar:
                self._botao_registrar.config(state=DISABLED)
        finally:
            self._atualizar_label_preview()

    # --------------------------------------------------------------------------
    # Lógica de Busca e Registro
    # --------------------------------------------------------------------------

    def _executar_busca_real(self):
        """
        Executa a busca na fachada do núcleo com o termo atual e atualiza a
        lista de resultados.
        """
        self._id_after_busca = None
        termo_busca = self._var_entrada_busca.get()

        if len(termo_busca) < 2:
            self._resetar_estado_busca()
            return

        pular_grupos = termo_busca.endswith(".")
        if pular_grupos:
            termo_busca = termo_busca[:-1].strip()

        logger.debug(
            "Executando busca por: '%s' (ignorar grupos: %s)", termo_busca, pular_grupos
        )

        try:
            elegiveis = self._fachada.obter_estudantes_para_sessao(
                consumido=False, pular_grupos=pular_grupos
            )
        except ErroSessaoNaoAtiva:
            logger.error("Nenhuma sessão ativa para realizar a busca.")
            elegiveis = []
        except Exception as e: # pylint: disable=broad-exception-caught
            logger.exception("Erro ao buscar elegíveis da fachada: %s", e)
            elegiveis = None

        if elegiveis is None:
            Messagebox.show_error(
                "Erro", "Falha ao carregar lista de estudantes.", parent=self._app
            )
            return

        if termo_busca in self.TERMOS_BUSCA_TODOS:
            correspondencias = self._obter_elegiveis_nao_servidos(elegiveis)
        else:
            correspondencias = self._executar_busca_fuzzy(termo_busca, elegiveis)

        self._dados_correspondencias_elegiveis_atuais = correspondencias
        self._atualizar_treeview_elegiveis(correspondencias)
        self._auto_selecionar_primeiro_resultado()

    def _registrar_elegivel_selecionado(self):
        """
        Registra o consumo para o estudante atualmente selecionado na lista.
        """
        if not self._dados_elegivel_selecionado:
            logger.warning("Tentativa de registro sem aluno selecionado.")
            return

        pront = self._dados_elegivel_selecionado.get("Pront")
        nome = self._dados_elegivel_selecionado.get("Nome", "?")
        if not pront:
            Messagebox.show_error(
                "Erro no Registro",
                "Prontuário do aluno selecionado está ausente ou inválido.",
                parent=self._app,
            )
            return

        logger.info("Registrando consumo para: %s - %s", pront, nome)
        try:
            resultado = self._fachada.registrar_consumo(pront, pular_grupos=True)
            logger.info("Resultado do registro para %s: %s", pront, resultado)

            tupla_estudante = (
                str(resultado.get("prontuario", pront)),
                str(resultado.get("nome", nome)),
                str(resultado.get("turma", "")),
                str(resultado.get("hora_consumo", datetime.now().strftime("%H:%M:%S"))),
                str(resultado.get("prato", "")),
            )
            self._app.notificar_sucesso_registro(tupla_estudante)
            self.limpar_busca()

        except Exception as e: # pylint: disable=broad-exception-caught
            logger.warning("Falha ao registrar %s: %s", pront, e)
            if "já consumiu" in str(e).lower():
                Messagebox.show_warning(
                    "Já Registrado",
                    f"{nome} ({pront})\nJá consta como registrado nesta sessão.",
                    parent=self._app,
                )
                self.limpar_busca()
            else:
                Messagebox.show_error(
                    "Erro no Registro",
                    f"Não foi possível registrar o consumo para:\n{nome} ({pront})\nErro: {e}",
                    parent=self._app,
                )
        finally:
            self._dados_elegivel_selecionado = None
            self._atualizar_label_preview()
            if self._botao_registrar:
                self._botao_registrar.config(state=DISABLED)

    # --------------------------------------------------------------------------
    # Métodos Auxiliares
    # --------------------------------------------------------------------------

    def _resetar_estado_busca(self):
        """Limpa a lista de resultados e reseta os componentes relacionados."""
        if self._botao_limpar:
            self._botao_limpar.config(state=DISABLED)
        if self._tree_estudantes_elegiveis:
            self._tree_estudantes_elegiveis.deletar_linhas()

        self._dados_elegivel_selecionado = None
        self._dados_correspondencias_elegiveis_atuais = []

        if self._botao_registrar:
            self._botao_registrar.config(state=DISABLED)

        self._atualizar_label_preview()

    def _obter_elegiveis_nao_servidos(
        self, estudantes_elegiveis: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Retorna todos os estudantes elegíveis que ainda não consumiram."""
        logger.debug("Filtrando %d alunos elegíveis.", len(estudantes_elegiveis))

        # Renomeia as chaves para corresponder ao que a busca fuzzy espera
        elegiveis_formatados = [
            {
                "Pront": s.get("pront"),
                "Nome": s.get("nome"),
                "Turma": s.get("turma"),
                "Prato": s.get("prato"),
                "score": 100,  # Score fixo para ordenação
            }
            for s in estudantes_elegiveis
        ]

        elegiveis_formatados.sort(key=lambda x: x.get("Nome", "").lower())
        return elegiveis_formatados

    def _executar_busca_fuzzy(
        self, termo_busca: str, estudantes_elegiveis: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Executa uma busca por aproximação (fuzzy) nos nomes e prontuários
        dos estudantes elegíveis.
        """
        termo_lower = termo_busca.lower().strip()
        correspondencias = []

        # Determina se a busca é por prontuário ou nome
        busca_por_pront = bool(
            re.fullmatch(r"(?:[a-z]{2})?[\dx\s]+", termo_lower, re.IGNORECASE)
        )
        chave_busca = "pront" if busca_por_pront else "nome"

        termo_limpo = (
            REGEX_LIMPEZA_PRONTUARIO.sub("", termo_lower)
            if busca_por_pront
            else termo_lower
        )

        limite_score = 85 if busca_por_pront else 70

        for estudante in estudantes_elegiveis:
            valor_campo = estudante.get(chave_busca, "")
            if not valor_campo:
                continue

            valor_comparar = (
                REGEX_LIMPEZA_PRONTUARIO.sub("", valor_campo.lower())
                if busca_por_pront
                else valor_campo.lower()
            )

            score = fuzz.partial_ratio(termo_limpo, valor_comparar)

            if busca_por_pront and termo_limpo == valor_comparar:
                score = 100

            if score >= limite_score:
                copia_estudante = {
                    "Pront": estudante.get("pront"),
                    "Nome": estudante.get("nome"),
                    "Turma": estudante.get("turma"),
                    "Prato": estudante.get("prato"),
                    "score": score,
                }
                correspondencias.append(copia_estudante)

        correspondencias.sort(key=lambda x: (-x["score"], x.get("Nome", "").lower()))
        return correspondencias

    def _atualizar_treeview_elegiveis(self, dados: List[Dict[str, Any]]):
        """
        Atualiza a tabela de estudantes elegíveis com os resultados da busca.
        """
        if not self._tree_estudantes_elegiveis:
            return

        self._tree_estudantes_elegiveis.deletar_linhas()
        if not dados:
            return

        linhas_para_inserir = []
        for item in dados:
            status_prato = item.get("Prato") or "Sem Reserva"
            linha = (
                str(item.get("Nome", "N/A")),
                str(item.get("Pront", "N/A")),
                str(item.get("Turma", "N/A")),
                str(status_prato),
            )
            linhas_para_inserir.append(linha)

        try:
            view = self._tree_estudantes_elegiveis.view
            for linha in linhas_para_inserir:
                # O IID (identificador do item) será o prontuário
                view.insert("", tk.END, iid=linha[1], values=linha)
            self._tree_estudantes_elegiveis.apply_zebra_striping()
        except Exception as e: # pylint: disable=broad-exception-caught
            logger.exception("Erro ao construir tabela de elegíveis: %s", e)
            Messagebox.show_error(
                "Erro de UI", "Não foi possível exibir os resultados.", parent=self._app
            )

    def _atualizar_label_preview(self, erro: bool = False):
        """Atualiza o texto e o estilo do label de pré-visualização."""
        if not self._label_aluno_selecionado:
            return

        if erro:
            texto = "Erro ao obter dados do aluno."
            estilo = "inverse-danger"
        elif self._dados_elegivel_selecionado:
            pront = self._dados_elegivel_selecionado.get("Pront", "?")
            nome = self._dados_elegivel_selecionado.get("Nome", "?")
            turma = self._dados_elegivel_selecionado.get("Turma", "S/ Turma")
            prato = self._dados_elegivel_selecionado.get("Prato") or "Sem Reserva"
            texto = f"Pront: {pront}\nNome: {nome}\nTurma: {turma}\nPrato: {prato}"
            estilo = "inverse-primary"
        else:
            texto = "Pesquise um aluno."
            estilo = "inverse-info"

        self._label_aluno_selecionado.config(text=texto, bootstyle=estilo)

    def _selecionar_proximo_elegivel(self, delta: int):
        """
        Move a seleção na lista de elegíveis para cima ou para baixo.
        `delta` pode ser 1 (para baixo) ou -1 (para cima).
        """
        if (
            not self._tree_estudantes_elegiveis
            or not self._tree_estudantes_elegiveis.obter_iids_filhos()
        ):
            return

        lista_iids = self._tree_estudantes_elegiveis.obter_iids_filhos()
        iid_selecionado = self._tree_estudantes_elegiveis.obter_iid_selecionado()
        tamanho = len(lista_iids)

        try:
            indice_atual = lista_iids.index(iid_selecionado) if iid_selecionado else -1
            proximo_indice = (indice_atual + delta) % tamanho
            proximo_iid = lista_iids[proximo_indice]

            view = self._tree_estudantes_elegiveis.view
            view.focus(proximo_iid)
            view.selection_set(proximo_iid)
            view.see(proximo_iid)
        except (ValueError, IndexError) as e:
            logger.warning("Erro ao navegar na lista de elegíveis: %s", e)

    def _auto_selecionar_primeiro_resultado(self):
        """Seleciona automaticamente o primeiro item da lista de resultados."""
        try:
            if self._tree_estudantes_elegiveis and (
                iids := self._tree_estudantes_elegiveis.obter_iids_filhos()
            ):
                primeiro_iid = iids[0]
                view = self._tree_estudantes_elegiveis.view
                view.focus(primeiro_iid)
                view.selection_set(primeiro_iid)
                view.see(primeiro_iid)
        except Exception as e: # pylint: disable=broad-exception-caught
            logger.error("Erro ao auto-selecionar primeiro item: %s", e)
