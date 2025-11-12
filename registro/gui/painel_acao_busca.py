# ----------------------------------------------------------------------------
# Arquivo: registro/gui/painel_acao_busca.py (Painel de Ação/Busca)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

import logging
import re
import tkinter as tk
from datetime import datetime
from tkinter import messagebox
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import ttkbootstrap as ttk
from fuzzywuzzy import fuzz
from ttkbootstrap.constants import (
    DANGER,
    DEFAULT,
    DISABLED,
    INFO,
    LEFT,
    NORMAL,
    SUCCESS,
    WARNING,
    W,
    X,
)

from registro.nucleo.exceptions import ErroSessaoNaoAtiva
from registro.nucleo.facade import FachadaRegistro
from registro.gui.constants import REGEX_LIMPEZA_PRONTUARIO
from registro.gui.treeview_simples import TreeviewSimples

if TYPE_CHECKING:
    from registro.gui.app_registro import AppRegistro

logger = logging.getLogger(__name__)


class PainelAcaoBusca(ttk.Frame):
    ATRASO_DEBOUNCE_BUSCA = 350

    def __init__(
        self,
        master: tk.Widget,
        app: "AppRegistro",
        fachada_nucleo: "FachadaRegistro",
    ):
        super().__init__(master, padding=10)
        self._app = app
        self._fachada = fachada_nucleo

        self._id_after_busca: Optional[str] = None
        self._dados_correspondencias_elegiveis_atuais: List[Dict[str, Any]] = []
        self._dados_elegivel_selecionado: Optional[Dict[str, Any]] = None

        self._var_entrada_busca: tk.StringVar = tk.StringVar()
        self._entrada_busca: Optional[ttk.Entry] = None
        self._botao_limpar: Optional[ttk.Button] = None
        self._tree_estudantes_elegiveis: Optional[TreeviewSimples] = None
        self._label_aluno_selecionado: Optional[ttk.Label] = None
        self._botao_registrar: Optional[ttk.Button] = None
        self._label_feedback_acao: Optional[ttk.Label] = None

        self.grupos_excluidos: List[str] = []
        self.grupos_selecionados: List[str] = []

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._criar_barra_busca()
        self._criar_lista_elegiveis()
        self._criar_area_preview()
        self._criar_area_acao()

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

    @property
    def id_after_busca(self) -> Optional[str]:
        return self._id_after_busca

    @id_after_busca.setter
    def id_after_busca(self, value: Optional[str]):
        self._id_after_busca = value

    def _criar_barra_busca(self):
        barra_busca = ttk.Frame(self)
        barra_busca.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        barra_busca.grid_columnconfigure(0, weight=1)

        self._entrada_busca = ttk.Entry(
            barra_busca,
            textvariable=self._var_entrada_busca,
            font=(None, 12),
            bootstyle=INFO,  # type: ignore
        )
        self._entrada_busca.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self._var_entrada_busca.trace_add("write", self._na_mudanca_entrada_busca)

        self._botao_limpar = ttk.Button(
            barra_busca,
            text="❌",
            width=3,
            command=self.limpar_busca,
            bootstyle="danger-outline",  # type: ignore
        )
        self._botao_limpar.grid(row=0, column=1)

    def _criar_lista_elegiveis(self):
        # frame_elegiveis = ttk.Labelframe(
        #     self, text="🔍 Alunos Elegíveis (Resultados da Busca)", padding=(5, 5)
        # )
        # frame_elegiveis.grid(row=2, column=0, sticky="nsew", pady=(10, 10))
        # frame_elegiveis.grid_rowconfigure(0, weight=1)
        # frame_elegiveis.grid_columnconfigure(0, weight=1)

        cols_elegiveis = [
            {"text": "Nome", "stretch": True, "iid": "name"},
            {
                "text": "Turma | Pront",
                "width": 160,
                "anchor": W,
                "iid": "info",
                "minwidth": 100,
            },
            {
                "text": "Prato/Status",
                "width": 130,
                "anchor": W,
                "iid": "dish",
                "minwidth": 80,
            },
        ]
        self._tree_estudantes_elegiveis = TreeviewSimples(
            master=self, dados_colunas=cols_elegiveis, height=10
        )
        self._tree_estudantes_elegiveis.grid(row=2, column=0, sticky="nsew")

    def _criar_area_preview(self):
        frame_preview = ttk.Frame(self, padding=(0, 0))
        frame_preview.grid(row=3, column=0, sticky="ew", pady=(5, 0))
        self._label_aluno_selecionado = ttk.Label(
            frame_preview,
            text="Selecione um aluno da lista.",
            justify=LEFT,
            bootstyle="inverse-info",  # type: ignore
            wraplength=350,
            style="Preview.TLabel",
        )
        self._label_aluno_selecionado.pack(fill=X, expand=True)

    def _criar_area_acao(self):
        frame_acao = ttk.Frame(self)
        frame_acao.grid(row=1, column=0, sticky="ew", pady=(5, 5))
        frame_acao.columnconfigure(1, weight=1)

        self._botao_registrar = ttk.Button(
            frame_acao,
            text="➕ Registrar Selecionado",
            command=self._registrar_elegivel_selecionado,
            bootstyle="success",  # type: ignore
            state=DISABLED,
        )
        self._botao_registrar.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        self._label_feedback_acao = ttk.Label(
            frame_acao, text="", anchor=W, style="Feedback.TLabel"
        )
        self._label_feedback_acao.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        frame_acao.columnconfigure(0, weight=2)

    def limpar_busca(self, *_):
        logger.debug("Limpando busca no painel de ação.")
        if self._entrada_busca:
            self._var_entrada_busca.set("")
            self.focar_entrada()
        else:
            logger.warning("Tentativa de limpar busca com campo não inicializado.")

    def focar_entrada(self):
        if self._entrada_busca:
            self.after(30, self._entrada_busca.focus_set)
            logger.debug("Foco agendado para o campo de busca.")
        else:
            logger.warning("Tentativa de focar campo de busca não inicializado.")

    def atualizar_resultados(self):
        logger.debug("Atualizando resultados da busca.")
        if self._id_after_busca is not None:
            self.after_cancel(self._id_after_busca)
            self._id_after_busca = None
        self._executar_busca_real()

    def desabilitar_controles(self):
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
        if self._label_feedback_acao:
            self._label_feedback_acao.config(text="")
        logger.debug("Controles do painel de ação desabilitados.")

    def habilitar_controles(self):
        if self._entrada_busca:
            self._entrada_busca.config(state=NORMAL)
        if self._botao_limpar:
            self._botao_limpar.config(state=NORMAL)
        if self._botao_registrar:
            self._botao_registrar.config(state=DISABLED)
        logger.debug("Controles do painel de ação habilitados.")
        self.focar_entrada()

    def _na_mudanca_entrada_busca(self, *_):
        if self._id_after_busca is not None:
            self.after_cancel(self._id_after_busca)
            self._id_after_busca = None

        termo_busca = self._var_entrada_busca.get()
        if len(termo_busca) < 2:
            if self._tree_estudantes_elegiveis:
                self._tree_estudantes_elegiveis.deletar_linhas()
            self._dados_elegivel_selecionado = None
            self._dados_correspondencias_elegiveis_atuais = []
            if self._botao_registrar:
                self._botao_registrar.config(state=DISABLED)
            self._atualizar_label_preview()
            if self._label_feedback_acao:
                placeholder = (
                    "Digite para buscar..."
                    if not termo_busca
                    else "Mínimo 2 caracteres..."
                )
                self._label_feedback_acao.config(
                    text=placeholder, bootstyle=DEFAULT  # type: ignore
                )
            return

        self._id_after_busca = self.after(
            self.ATRASO_DEBOUNCE_BUSCA, self._executar_busca_real
        )

    def _selecionar_proximo_elegivel(self, delta: int = 1):
        try:
            if (
                not self._tree_estudantes_elegiveis
                or not self._tree_estudantes_elegiveis.obter_iids_filhos()
            ):
                return

            iid_selecionado = self._tree_estudantes_elegiveis.obter_iid_selecionado()
            lista_iids = self._tree_estudantes_elegiveis.obter_iids_filhos()
            tamanho_lista = len(lista_iids)

            if not iid_selecionado:
                proximo_indice = 0 if delta > 0 else tamanho_lista - 1
            else:
                try:
                    indice_atual = lista_iids.index(iid_selecionado)
                    proximo_indice = (indice_atual + delta) % tamanho_lista
                except ValueError:
                    proximo_indice = 0 if delta > 0 else tamanho_lista - 1

            if 0 <= proximo_indice < tamanho_lista:
                proximo_iid = lista_iids[proximo_indice]
                self._tree_estudantes_elegiveis.view.focus(proximo_iid)
                self._tree_estudantes_elegiveis.view.selection_set(proximo_iid)
                self._tree_estudantes_elegiveis.view.see(proximo_iid)
            else:
                logger.warning("Índice de seleção (%d) inválido.", proximo_indice)
        except Exception as e:
            logger.exception("Erro ao selecionar próximo item da busca: %s", e)

    def _executar_busca_real(self):
        self._id_after_busca = None
        termo_busca = self._var_entrada_busca.get()
        if len(termo_busca) < 2:
            if self._label_feedback_acao:
                self._label_feedback_acao.config(text="")
            if self._tree_estudantes_elegiveis:
                self._tree_estudantes_elegiveis.deletar_linhas()
            self._dados_elegivel_selecionado = None
            self._dados_correspondencias_elegiveis_atuais = []
            self._atualizar_label_preview()
            if self._botao_registrar:
                self._botao_registrar.config(state=DISABLED)
            return

        pular_grupos = False
        if termo_busca.endswith("."):
            termo_busca = termo_busca[:-1].strip()
            pular_grupos = True

        logger.debug(
            "Executando busca por: %s (ignorar grupos: %s)",
            termo_busca,
            str(pular_grupos),
        )

        try:
            elegiveis = self._fachada.obter_estudantes_para_sessao(
                consumido=False, pular_grupos=pular_grupos
            )
        except ErroSessaoNaoAtiva:
            logger.error("Nenhuma sessão ativa para realizar a busca.")
            elegiveis = []
        except Exception as e:
            logger.exception("Erro ao buscar elegíveis da fachada: %s", e)
            elegiveis = None

        if elegiveis is None:
            logger.error("Lista de elegíveis N/A durante a busca.")
            if self._label_feedback_acao:
                self._label_feedback_acao.config(
                    text="Erro ao carregar lista", bootstyle=DANGER  # type: ignore
                )
            if self._tree_estudantes_elegiveis:
                self._tree_estudantes_elegiveis.deletar_linhas()
            return

        elegiveis_renomeados = [
            {
                "Pront": s.get("pront"),
                "Nome": s.get("nome"),
                "Turma": s.get("turma"),
                "Prato": s.get("prato"),
            }
            for s in elegiveis
        ]

        if termo_busca in ["todos", "---", "***"]:
            correspondencias = self._obter_elegiveis_nao_servidos(elegiveis_renomeados)
        else:
            correspondencias = self._executar_busca_fuzzy(
                termo_busca, elegiveis_renomeados
            )

        if self._tree_estudantes_elegiveis:
            self._atualizar_treeview_elegiveis(correspondencias)

        if correspondencias:
            if self._label_feedback_acao:
                self._label_feedback_acao.config(
                    text=f"{len(correspondencias)} resultado(s)", bootstyle=INFO  # type: ignore
                )
            try:
                if (
                    self._tree_estudantes_elegiveis
                    and self._tree_estudantes_elegiveis.obter_iids_filhos()
                ):
                    primeiro_iid = self._tree_estudantes_elegiveis.obter_iids_filhos()[
                        0
                    ]
                    self._tree_estudantes_elegiveis.view.focus(primeiro_iid)
                    self._tree_estudantes_elegiveis.view.selection_set(primeiro_iid)
                    self._tree_estudantes_elegiveis.view.see(primeiro_iid)
            except Exception as e:
                logger.error("Erro ao auto-selecionar primeiro item: %s", e)
        else:
            if self._label_feedback_acao:
                self._label_feedback_acao.config(
                    text="Nenhum resultado encontrado", bootstyle=WARNING  # type: ignore
                )
            self._dados_elegivel_selecionado = None
            self._atualizar_label_preview()
            if self._botao_registrar:
                self._botao_registrar.config(state=DISABLED)

    def _obter_elegiveis_nao_servidos(
        self, estudantes_elegiveis: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        logger.debug("Filtrando %d alunos elegíveis.", len(estudantes_elegiveis))
        elegiveis_nao_servidos = []
        contador_pulados = 0

        for estudante in estudantes_elegiveis:
            pront = estudante.get("Pront")
            if not pront:
                logger.warning(
                    "Aluno elegível sem prontuário: %s", estudante.get("Nome")
                )
                contador_pulados += 1
                continue

            copia_estudante = estudante.copy()
            exibicao_turma = copia_estudante.get("Turma", "S/ Turma")
            exibicao_pront = pront
            copia_estudante["info"] = f"{exibicao_turma} | {exibicao_pront}"
            copia_estudante["score"] = 100
            elegiveis_nao_servidos.append(copia_estudante)

        logger.debug(
            "Filtragem concluída. %d alunos não servidos, %d pulados.",
            len(elegiveis_nao_servidos),
            contador_pulados,
        )
        elegiveis_nao_servidos.sort(key=lambda x: x.get("Nome", "").lower())
        for i, estudante in enumerate(elegiveis_nao_servidos):
            estudante["score"] = (i * 100) // len(elegiveis_nao_servidos)
        self._dados_correspondencias_elegiveis_atuais = elegiveis_nao_servidos
        return elegiveis_nao_servidos

    def _executar_busca_fuzzy(
        self, termo_busca: str, estudantes_elegiveis: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        termo_lower = termo_busca.lower().strip()
        correspondencias_encontradas = []
        busca_por_pront = bool(
            re.fullmatch(r"(?:[a-z]{2})?[\dx\s]+", termo_lower, re.IGNORECASE)
        )
        chave_busca = "Pront" if busca_por_pront else "Nome"
        termo_busca_limpo = (
            REGEX_LIMPEZA_PRONTUARIO.sub("", termo_lower)
            if busca_por_pront
            else termo_lower
        )
        funcao_match = fuzz.partial_ratio
        limite = 85 if busca_por_pront else 70

        for estudante in estudantes_elegiveis:
            pront = estudante.get("Pront")
            valor_cru_para_match = estudante.get(chave_busca, "")
            if not valor_cru_para_match:
                continue

            valor_lower_para_match = valor_cru_para_match.lower()
            if busca_por_pront:
                valor_para_comparar = REGEX_LIMPEZA_PRONTUARIO.sub(
                    "", valor_lower_para_match
                )
            else:
                valor_para_comparar = valor_lower_para_match
            score = funcao_match(termo_busca_limpo, valor_para_comparar)

            if busca_por_pront and termo_busca_limpo == valor_para_comparar:
                score = 100

            if score >= limite:
                copia_estudante = estudante.copy()
                exibicao_turma = estudante.get("Turma", "S/ Turma")
                exibicao_pront = pront or "S/ Pront."
                copia_estudante["info"] = f"{exibicao_turma} | {exibicao_pront}"
                copia_estudante["score"] = score
                correspondencias_encontradas.append(copia_estudante)

        correspondencias_encontradas.sort(
            key=lambda x: (-x["score"], x.get("Nome", "").lower())
        )
        self._dados_correspondencias_elegiveis_atuais = correspondencias_encontradas
        return correspondencias_encontradas

    def _atualizar_treeview_elegiveis(
        self, dados_correspondencias: List[Dict[str, Any]]
    ):
        if not self._tree_estudantes_elegiveis:
            return
        self._tree_estudantes_elegiveis.deletar_linhas()
        if not dados_correspondencias:
            return

        dados_linhas = []
        for m in dados_correspondencias:
            status_prato = m.get("Prato") or "Sem Reserva"
            linha = (
                str(m.get("Nome", "N/A")),
                str(m.get("info", "N/A")),
                str(status_prato),
            )
            dados_linhas.append(linha)

        try:
            self._tree_estudantes_elegiveis.construir_dados_tabela(
                dados_linhas=dados_linhas
            )
        except Exception as e:
            logger.exception("Erro ao construir tabela de elegíveis: %s", e)
            messagebox.showerror(
                "Erro de UI", "Não foi possível exibir os resultados.", parent=self._app
            )

    def _ao_selecionar_estudante_elegivel(self, _=None):
        if not self._tree_estudantes_elegiveis:
            return

        iid_selecionado = self._tree_estudantes_elegiveis.obter_iid_selecionado()
        if iid_selecionado:
            try:
                valores_selecionados = (
                    self._tree_estudantes_elegiveis.obter_valores_linha(iid_selecionado)
                )
                if not valores_selecionados:
                    raise ValueError("Não foi possível obter valores da linha.")

                nome_selecionado = valores_selecionados[0]
                info_selecionada = valores_selecionados[1]
                dados_estudante_encontrado = None
                for dados_estudante in self._dados_correspondencias_elegiveis_atuais:
                    if (
                        dados_estudante.get("Nome") == nome_selecionado
                        and dados_estudante.get("info") == info_selecionada
                    ):
                        dados_estudante_encontrado = dados_estudante
                        break

                if dados_estudante_encontrado:
                    self._dados_elegivel_selecionado = dados_estudante_encontrado
                    self._atualizar_label_preview()
                    if self._botao_registrar:
                        self._botao_registrar.config(state=NORMAL)
                    pront = self._dados_elegivel_selecionado.get("Pront", "?")
                    if self._label_feedback_acao:
                        self._label_feedback_acao.config(
                            text=f"Selecionado: {pront}", bootstyle=INFO  # type: ignore
                        )
                else:
                    logger.error(
                        "Inconsistência de dados para linha: %s", valores_selecionados
                    )
                    self._dados_elegivel_selecionado = None
                    self._atualizar_label_preview(erro=True)
                    if self._botao_registrar:
                        self._botao_registrar.config(state=DISABLED)
                    if self._label_feedback_acao:
                        self._label_feedback_acao.config(
                            text="Erro Seleção", bootstyle=DANGER  # type: ignore
                        )
            except (ValueError, IndexError, AttributeError, tk.TclError) as e:
                logger.exception("Erro ao processar seleção de elegível: %s", e)
                self._dados_elegivel_selecionado = None
                self._atualizar_label_preview(erro=True)
                if self._botao_registrar:
                    self._botao_registrar.config(state=DISABLED)
                if self._label_feedback_acao:
                    self._label_feedback_acao.config(
                        text="Erro Seleção", bootstyle=DANGER  # type: ignore
                    )
        else:
            self._dados_elegivel_selecionado = None
            self._atualizar_label_preview()
            if self._botao_registrar:
                self._botao_registrar.config(state=DISABLED)

            termo_busca = self._var_entrada_busca.get()
            if self._label_feedback_acao:
                if len(termo_busca) < 2:
                    placeholder = (
                        "Digite para buscar..."
                        if not termo_busca
                        else "Mínimo 2 caracteres..."
                    )
                    self._label_feedback_acao.config(
                        text=placeholder, bootstyle=DEFAULT  # type: ignore
                    )
                else:
                    if self._dados_correspondencias_elegiveis_atuais:
                        cont_resultados = len(
                            self._dados_correspondencias_elegiveis_atuais
                        )
                        self._label_feedback_acao.config(
                            text=f"{cont_resultados} resultado(s)",
                            bootstyle=INFO,  # type: ignore
                        )
                    else:
                        self._label_feedback_acao.config(
                            text="Nenhum resultado encontrado", bootstyle=WARNING  # type: ignore
                        )

    def _atualizar_label_preview(self, erro: bool = False):
        if not self._label_aluno_selecionado:
            return

        estilo = "inverse-secondary"
        if erro:
            texto = "Erro ao obter dados do aluno."
            estilo = "inverse-danger"
        elif self._dados_elegivel_selecionado:
            pront = self._dados_elegivel_selecionado.get("Pront", "?")
            nome = self._dados_elegivel_selecionado.get("Nome", "?")
            turma = self._dados_elegivel_selecionado.get("Turma", "S/ Turma")
            prato_raw = self._dados_elegivel_selecionado.get("Prato")
            prato = prato_raw if prato_raw is not None else "Sem Reserva"
            texto = f"Pront: {pront}\nNome: {nome}\n" f"Turma: {turma}\nPrato: {prato}"
            estilo = "inverse-info"
        else:
            texto = "Selecione um aluno da lista acima."
        self._label_aluno_selecionado.config(text=texto, bootstyle=estilo)  # type: ignore

    def _registrar_elegivel_selecionado(self):
        if not self._dados_elegivel_selecionado:
            logger.warning("Tentativa de registro sem aluno selecionado.")
            if self._botao_registrar:
                self._botao_registrar.config(state=DISABLED)
            return

        pront = self._dados_elegivel_selecionado.get("Pront")
        nome = self._dados_elegivel_selecionado.get("Nome", "?")
        if not pront:
            logger.error(
                "Prontuário ausente para registro: %s", self._dados_elegivel_selecionado
            )
            messagebox.showerror(
                "Erro no Registro",
                "Prontuário do aluno selecionado está ausente ou inválido.",
                parent=self._app,
            )
            return

        logger.info("Registrando aluno elegível: %s - %s", pront, nome)
        try:
            resultado = self._fachada.registrar_consumo(pront, pular_grupos=True)
            logger.info(
                "Resultado do registro, prontuario %s: %s", pront, str(resultado)
            )

            tupla_estudante = (
                str(resultado.get("prontuario", pront)),
                str(resultado.get("nome", nome)),
                str(resultado.get("turma", "")),
                str(resultado.get("hora_consumo", datetime.now().strftime("%H:%M:%S"))),
                str(resultado.get("prato", "")),
            )
            self._app.notificar_sucesso_registro(tupla_estudante)
            if self._label_feedback_acao:
                self._label_feedback_acao.config(
                    text=f"Registrado: {pront}", bootstyle=SUCCESS  # type: ignore
                )
            self._dados_elegivel_selecionado = None
            self._atualizar_label_preview()
            if self._botao_registrar:
                self._botao_registrar.config(state=DISABLED)
            self.limpar_busca()
        except Exception as e:
            logger.warning("Falha ao registrar %s: %s", pront, e)
            ja_servido = "já consumiu" in str(e).lower()
            if ja_servido:
                messagebox.showwarning(
                    "Já Registrado",
                    f"{nome} ({pront})\nJá consta como registrado nesta sessão.",
                    parent=self._app,
                )
                fb_texto = f"JÁ REGISTRADO: {pront}"
                fb_estilo = WARNING
                self._dados_elegivel_selecionado = None
                self._atualizar_label_preview()
                if self._botao_registrar:
                    self._botao_registrar.config(state=DISABLED)
                self.limpar_busca()
            else:
                messagebox.showerror(
                    "Erro no Registro",
                    f"Não foi possível registrar o consumo para:\n{nome} ({pront})\n"
                    f"Erro: {e}",
                    parent=self._app,
                )
                fb_texto = f"ERRO registro {pront}"
                fb_estilo = DANGER

            if self._label_feedback_acao:
                self._label_feedback_acao.config(text=fb_texto, bootstyle=fb_estilo)  # type: ignore
            if not self._dados_elegivel_selecionado and self._botao_registrar:
                self._botao_registrar.config(state=DISABLED)
