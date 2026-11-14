# ----------------------------------------------------------------------------
# Arquivo: registro/gui/registrar/dialogo_sessao.py (Diálogo de Gerenciamento de Sessão)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

import datetime as dt
import logging
import threading
import tkinter as tk
from pathlib import Path
from threading import Thread
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    TypedDict,
    Union,
)

import ttkbootstrap as ttk
from sqlalchemy.exc import SQLAlchemyError
from ttkbootstrap.constants import EW, NSEW
from ttkbootstrap.dialogs import Messagebox

from registro.gui.comum.controles.treeview_simples import TreeviewSimples
from registro.gui.comum.utils import capitalizar
from registro.gui.registrar._dialogo_sessao_abas import _DialogoSessaoAbasMixin
from registro.gui.registrar._dialogo_sessao_grade import _DialogoSessaoGradeMixin
from registro.gui.registrar.dialogo_sessao_logica import (
    carregar_opcoes_lanche_arquivo,
    chave_ordenacao_sessao,
    expandir_grupos_slot,
    filtrar_linhas_sessoes,
    formatar_linhas_sessoes,
    ordenar_slots_grade,
    resumo_slot_texto,
    slot_esta_ativo_agora,
)
from registro.nucleo.constants import CAMINHO_JSON_LANCHES, NOME_LANCHE_PADRAO
from registro.nucleo.exceptions import ErroAPIGoogle, ErroSessaoNaoAtiva
from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.services import grade_horarios_service
from registro.nucleo.utils import salvar_json

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

DadosNovaSessao = TypedDict(
    "DadosNovaSessao",
    {
        "refeição": Literal["Lanche", "Almoço"],
        "lanche": Optional[str],
        "período": str,
        "data": str,
        "hora": str,
        "groups": List[str],
    },
)


class DialogoSessao(tk.Toplevel, _DialogoSessaoAbasMixin, _DialogoSessaoGradeMixin):
    """
    Diálogo moderno para criar uma nova sessão, editar a sessão ativa ou carregar
    uma sessão existente, com integração dinâmica à grade horária e reservas.
    """

    def __init__(
        self,
        title: str,
        callback: Callable[[Union[DadosNovaSessao, int, None]], bool],
        parente_app: Any,
    ):
        super().__init__(parente_app)
        self.withdraw()
        self.title(title)
        self.transient(parente_app)
        self.grab_set()

        self._callback = callback
        self._parente_app = parente_app
        if hasattr(parente_app, "get_fachada"):
            self._fachada: "FachadaRegistro" = parente_app.get_fachada()
        elif hasattr(parente_app, "fachada_nucleo"):
            self._fachada = parente_app.fachada_nucleo
        elif hasattr(parente_app, "_fachada"):
            self._fachada = parente_app._fachada
        else:
            raise AttributeError("Parente não possui fachada de registro.")

        self._sessao_ativa_info: Optional[Dict[str, Any]] = None
        self._conjunto_opcoes_lanche: Set[str] = set()
        self._turmas_disponiveis: List[str] = []
        self._categorias_disponiveis: List[str] = []

        self._contextos: Dict[str, Dict[str, Any]] = {}
        self._dados_checkbox_turmas: List[
            Tuple[str, tk.BooleanVar, ttk.Checkbutton]
        ] = []
        self._dados_checkbox_turmas_editar: List[
            Tuple[str, tk.BooleanVar, ttk.Checkbutton]
        ] = []

        self._notebook: Optional[ttk.Notebook] = None
        self._entrada_hora: Optional[ttk.Entry] = None
        self._entrada_data: Optional[ttk.DateEntry] = None
        self._combobox_refeicao: Optional[ttk.Combobox] = None
        self._combobox_lanche: Optional[ttk.Combobox] = None
        self._combobox_lanche_editar: Optional[ttk.Combobox] = None
        self._btn_iniciar_acao: Optional[ttk.Button] = None

        self._treeview_sessoes: Optional[TreeviewSimples] = None
        self._var_busca_sessoes: Optional[tk.StringVar] = None
        self._lbl_contador_sessoes: Optional[ttk.Label] = None
        self._lbl_sem_sessoes: Optional[ttk.Label] = None
        self._todas_sessoes_linhas: List[Tuple] = []

        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)
        self.geometry("960x660")
        self.minsize(820, 560)

        self._criar_widgets()
        self._centralizar_janela()
        self.resizable(True, True)
        self.deiconify()

    def _criar_widgets(self):
        """Cria e organiza os widgets principais do diálogo."""
        main_frame = ttk.Frame(self, padding=14)
        main_frame.grid(row=0, column=0, sticky=NSEW)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)

        self._turmas_disponiveis, self._categorias_disponiveis = (
            self._buscar_grupos_separados()
        )

        self._notebook = ttk.Notebook(main_frame, bootstyle="primary")
        self._notebook.grid(row=0, column=0, sticky=NSEW)

        try:
            if self._fachada and self._fachada.id_sessao_ativa is not None:
                info = self._fachada.obter_detalhes_sessao_ativa()
                if isinstance(info, dict):
                    self._sessao_ativa_info = info
        except (ErroSessaoNaoAtiva, SQLAlchemyError, ValueError) as e:
            logger.warning("Não foi possível carregar detalhes da sessão ativa: %s", e)
            self._sessao_ativa_info = None

        aba_ativa_inicial = None
        if self._sessao_ativa_info:
            aba_ativa_inicial = self._criar_aba(
                "✏️ Editar Sessão Ativa", self._criar_conteudo_aba_editar_sessao
            )

        self._criar_aba("➕ Criar Nova Sessão", self._criar_conteudo_aba_nova_sessao)
        self._criar_aba(
            "📂 Carregar Sessão Existente", self._criar_conteudo_aba_carregar_sessao
        )

        if aba_ativa_inicial:
            self._notebook.select(aba_ativa_inicial)

        self._notebook.bind("<<NotebookTabChanged>>", self._ao_mudar_aba)

        botoes_frame = self._criar_secao_botoes_principais(main_frame)
        botoes_frame.grid(row=1, column=0, sticky=EW, pady=(12, 0))
        self._ao_mudar_aba()

    # ------------------------------------------------------------------------
    # Integração com Grade de Horários e Reservas
    # ------------------------------------------------------------------------

    def _obter_data_contexto(self, modo_edicao: bool) -> str:
        """Retorna a data (DD/MM/YYYY) do contexto ativo."""
        if modo_edicao and self._sessao_ativa_info:
            return str(self._sessao_ativa_info.get("data", "")).strip()
        if self._entrada_data:
            try:
                return str(self._entrada_data.entry.get()).strip()
            except tk.TclError as e:
                logger.debug("Campo de data indisponível ao obter contexto: %s", e)
        return dt.datetime.now().strftime("%d/%m/%Y")

    def _obter_refeicao_contexto(self, modo_edicao: bool) -> str:
        """Retorna o nome da refeição do contexto ativo em minúsculas."""
        if modo_edicao and self._sessao_ativa_info:
            return (
                str(self._sessao_ativa_info.get("refeicao", "lanche")).strip().lower()
            )
        if self._combobox_refeicao:
            val = self._combobox_refeicao.get().strip().lower()
            if val:
                return val
        return "lanche"

    def _obter_dia_semana_contexto(self, modo_edicao: bool) -> str:
        """Determina o dia da semana da grade considerando a data escolhida."""
        data_str = self._obter_data_contexto(modo_edicao)
        hoje_str = dt.datetime.now().strftime("%d/%m/%Y")
        if data_str and data_str != hoje_str:
            dia_data = grade_horarios_service.obter_dia_semana_por_data(data_str)
            if dia_data:
                return dia_data

        if self._fachada and hasattr(self._fachada, "obter_dia_semana_atual"):
            dia_fachada = self._fachada.obter_dia_semana_atual()
            if isinstance(dia_fachada, str) and dia_fachada:
                return dia_fachada
        return grade_horarios_service.obter_dia_semana_atual()

    def _obter_slots_grade(
        self, dia_semana: str, refeicao: str
    ) -> List[Dict[str, Any]]:
        """Busca os slots configurados na grade horária para o dia e refeição."""
        grade: Any = None
        try:
            if self._fachada and hasattr(self._fachada, "obter_grade_horarios"):
                grade = self._fachada.obter_grade_horarios()
        except (OSError, ValueError, SQLAlchemyError) as e:
            logger.debug("Falha ao ler grade pela fachada: %s", e)

        if not isinstance(grade, dict):
            grade = grade_horarios_service.carregar_grade_horarios()

        return ordenar_slots_grade(grade, dia_semana, refeicao)

    def _expandir_grupos_slot(self, slot: Dict[str, Any]) -> Set[str]:
        """Retorna os nomes de turmas/categorias autorizadas por um slot da grade."""
        return expandir_grupos_slot(
            slot, self._turmas_disponiveis, self._categorias_disponiveis
        )

    def _resumo_slot_texto(self, slot: Dict[str, Any]) -> str:
        """Gera descrição legível das turmas e categorias de um slot."""
        return resumo_slot_texto(slot)

    def _slot_esta_ativo_agora(self, slot: Dict[str, Any]) -> bool:
        """Verifica se o horário atual do sistema está dentro do slot."""
        return slot_esta_ativo_agora(slot)

    def _buscar_reservas_data_refeicao(
        self, data_str: str, refeicao: str
    ) -> List[Dict[str, Any]]:
        """Consulta reservas ativas da data/refeição com segurança frente a mocks."""
        if not self._fachada or not hasattr(self._fachada, "listar_reservas"):
            return []
        filtros: Dict[str, Any] = {"data": data_str, "cancelada": False}
        ref_norm = grade_horarios_service._normalizar_chave(refeicao)
        if ref_norm == "almoco":
            filtros["almoco"] = True
        elif ref_norm == "jantar":
            filtros["jantar"] = True

        try:
            res = self._fachada.listar_reservas(filtros)
            return res if isinstance(res, list) else []
        except (SQLAlchemyError, ValueError) as e:
            logger.debug("Erro ao consultar reservas para status: %s", e)
            return []

    def _obter_turmas_grade(self, dia_semana: str, refeicao: str) -> List[str]:
        """Obtém as turmas e categorias previstas na grade para dia e refeição."""
        turmas_grade: Any = None
        if self._fachada and hasattr(
            self._fachada, "obter_turmas_previstas_para_refeicao"
        ):
            try:
                turmas_grade = self._fachada.obter_turmas_previstas_para_refeicao(
                    refeicao=refeicao, dia_semana=dia_semana, incluir_categorias=True
                )
            except (OSError, ValueError, SQLAlchemyError) as e:
                logger.debug("Falha ao consultar grade pela fachada: %s", e)

        if isinstance(turmas_grade, list):
            return turmas_grade

        return grade_horarios_service.obter_turmas_previstas_para_refeicao(
            dia_semana=dia_semana,
            refeicao=refeicao,
            incluir_categorias=True,
            turmas_disponiveis=self._turmas_disponiveis,
            categorias_disponiveis=self._categorias_disponiveis,
        )

    # ------------------------------------------------------------------------
    # Eventos e ações da seleção de turmas
    # ------------------------------------------------------------------------

    def _ao_alterar_data_ou_refeicao(self, aplicar_grade: bool = True):
        """Responde à alteração de data ou refeição na aba de Nova Sessão."""
        self._ao_selecionar_refeicao()
        self._atualizar_contexto_grade(modo_edicao=False, aplicar_selecao=aplicar_grade)

    def _ao_selecionar_refeicao(self, _=None):
        """Habilita/desabilita o campo de lanche com base na refeição selecionada."""
        if not self._combobox_refeicao or not self._combobox_lanche:
            return
        eh_com_reserva = self._combobox_refeicao.get() in ("Almoço", "Jantar")
        self._combobox_lanche.config(state="disabled" if eh_com_reserva else "normal")
        if eh_com_reserva:
            self._combobox_lanche.set("")
        elif NOME_LANCHE_PADRAO in self._conjunto_opcoes_lanche:
            self._combobox_lanche.set(NOME_LANCHE_PADRAO)

    # ------------------------------------------------------------------------
    # Processamento de ações (Iniciar, Salvar, Carregar, Fechar)
    # ------------------------------------------------------------------------

    def _ao_ok(self):
        """Callback do botão de ação principal. Processa conforme a aba ativa."""
        if not self._notebook:
            return
        aba_selecionada = self._notebook.tab(self._notebook.select(), "text").strip()
        if "Editar" in aba_selecionada:
            self._processar_editar_sessao()
        elif "Carregar" in aba_selecionada:
            self._processar_carregar_sessao()
        else:
            self._processar_criar_sessao()

    def _processar_editar_sessao(self):
        """Salva as alterações feitas na sessão ativa (cardápio, turmas e horário livre)."""
        if not self._sessao_ativa_info:
            return

        turmas = [
            txt for txt, var, _ in self._dados_checkbox_turmas_editar if var.get()
        ]
        if not turmas:
            Messagebox.show_warning(
                "Selecione pelo menos uma turma para a sessão.", parent=self
            )
            return

        item = (
            self._combobox_lanche_editar.get().strip()
            if self._combobox_lanche_editar
            else ""
        )
        if item:
            self._salvar_nova_opcao_lanche(item)

        try:
            self._fachada.atualizar_sessao_ativa(
                item_servido=item,
                turmas=turmas,
            )
            ctx_editar = self._contextos.get("editar")
            if ctx_editar and hasattr(self._fachada, "definir_ignorar_horario_grade"):
                self._fachada.definir_ignorar_horario_grade(
                    bool(ctx_editar["var_horario_livre"].get())
                )

            logger.info(
                "Sessão ativa ID %s atualizada.", self._sessao_ativa_info.get("id")
            )
            Messagebox.show_info(
                f"Sessão ID {self._sessao_ativa_info.get('id')} atualizada com sucesso!\n"
                f"Turmas participantes: {len(turmas)}",
                "Sessão Atualizada",
                parent=self,
            )
            if hasattr(self._parente_app, "_atualizar_ui_apos_mudanca_dados"):
                self._parente_app._atualizar_ui_apos_mudanca_dados()
            if hasattr(self._parente_app, "_configurar_ui_para_sessao_carregada"):
                self._parente_app._configurar_ui_para_sessao_carregada()
            if hasattr(self._parente_app, "_atualizar_apos_mudanca_sessao"):
                self._parente_app._atualizar_apos_mudanca_sessao()
            self.grab_release()
            self.destroy()
        except Exception as e:
            logger.exception("Erro ao salvar alterações da sessão: %s", e)
            Messagebox.show_error(
                f"Falha ao salvar alterações:\n{e}", "Erro ao Atualizar", parent=self
            )

    def _processar_carregar_sessao(self):
        """Valida e envia o ID da sessão selecionada para a aplicação principal."""
        if not self._treeview_sessoes:
            return
        linha = self._treeview_sessoes.obter_linha_selecionada()
        if not linha:
            Messagebox.show_warning(
                "Selecione uma sessão para carregar.",
                "Nenhuma Sessão Selecionada",
                parent=self,
            )
            return

        id_sessao = int(linha[0])
        logger.info("Requisitando carregamento da sessão ID %s", id_sessao)
        if self._callback(id_sessao):
            self.grab_release()
            self.destroy()

    def _processar_criar_sessao(self):
        """Valida os dados e envia as informações da nova sessão para a aplicação principal."""
        if not self._validar_entrada_nova_sessao():
            return

        turmas = [txt for txt, var, _ in self._dados_checkbox_turmas if var.get()]
        refeicao = self._combobox_refeicao.get().lower()
        item = self._combobox_lanche.get().strip() if refeicao == "lanche" else None

        if item:
            self._salvar_nova_opcao_lanche(item)
            item = self._combobox_lanche.get().strip()

        try:
            data_ui = self._entrada_data.entry.get()
            data_backend = dt.datetime.strptime(data_ui, "%d/%m/%Y").strftime(
                "%Y-%m-%d"
            )
        except (ValueError, AttributeError) as e:
            logger.error("Erro ao converter data: %s", e)
            Messagebox.show_error("Data inválida.", "Erro Interno", parent=self)
            return

        dados_nova_sessao: DadosNovaSessao = {
            "refeicao": refeicao,
            "item_servido": item,
            "periodo": "Integral",
            "data": data_backend,
            "hora": self._entrada_hora.get(),
            "grupos": turmas,
        }

        ctx_nova = self._contextos.get("nova")
        horario_livre = bool(ctx_nova["var_horario_livre"].get()) if ctx_nova else False

        logger.info("Tentando criar uma nova sessão.")
        if self._callback(dados_nova_sessao):
            if horario_livre and hasattr(
                self._fachada, "definir_ignorar_horario_grade"
            ):
                try:
                    self._fachada.definir_ignorar_horario_grade(True)
                    if hasattr(self._parente_app, "_atualizar_estado_horario_livre"):
                        self._parente_app._atualizar_estado_horario_livre()
                except (SQLAlchemyError, tk.TclError, AttributeError) as e:
                    logger.warning(
                        "Não foi possível ativar Horário Livre após criar sessão: %s", e
                    )
            self.grab_release()
            self.destroy()

    def _validar_entrada_nova_sessao(self) -> bool:
        """Verifica se os campos para criar uma nova sessão foram preenchidos corretamente."""
        try:
            dt.datetime.strptime(self._entrada_hora.get(), "%H:%M")
        except ValueError:
            Messagebox.show_warning("Hora inválida. Use o formato HH:MM.", parent=self)
            return False

        if not self._entrada_data.entry.get():
            Messagebox.show_warning("Data é obrigatória.", parent=self)
            return False

        if not any(v.get() for _n, v, _c in self._dados_checkbox_turmas):
            Messagebox.show_warning("Selecione pelo menos uma turma.", parent=self)
            return False

        if (
            self._combobox_refeicao.get() == "Lanche"
            and not self._combobox_lanche.get().strip()
        ):
            Messagebox.show_warning(
                "Especifique o item servido para o lanche.", parent=self
            )
            return False

        return True

    def _ao_fechar(self):
        """Callback para fechar o diálogo, notificando a aplicação principal."""
        self.grab_release()
        self.destroy()
        self._callback(None)

    # ------------------------------------------------------------------------
    # Consultas de dados, lanches, sessões existentes e sincronização
    # ------------------------------------------------------------------------

    def _buscar_grupos_separados(self) -> Tuple[List[str], List[str]]:
        """Busca e separa os grupos cadastrados em (turmas, categorias)."""
        try:
            grupos = self._fachada.listar_todos_os_grupos()
            if not isinstance(grupos, list):
                return [], []
            turmas = sorted(
                g.get("nome", "")
                for g in grupos
                if isinstance(g, dict)
                and g.get("nome")
                and g.get("tipo") != "categoria"
            )
            categorias = sorted(
                g.get("nome", "")
                for g in grupos
                if isinstance(g, dict)
                and g.get("nome")
                and g.get("tipo") == "categoria"
            )
            return turmas, categorias
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Erro ao buscar turmas e categorias: %s", e)
            Messagebox.show_error("Não foi possível buscar as turmas.", parent=self)
            return [], []

    def _buscar_turmas_disponiveis(self) -> List[str]:
        """Busca a lista unificada de grupos da camada de negócio."""
        turmas, categorias = self._buscar_grupos_separados()
        return sorted(turmas + categorias)

    def _carregar_opcoes_lanche(self) -> Tuple[Set[str], List[str]]:
        """Carrega as opções de lanche a partir de um arquivo JSON."""
        return carregar_opcoes_lanche_arquivo(
            Path(CAMINHO_JSON_LANCHES), [NOME_LANCHE_PADRAO]
        )

    def _carregar_sessoes_existentes(self) -> List[Tuple]:
        """Busca e formata as sessões existentes para exibição na Treeview."""
        try:
            sessoes = self._fachada.listar_todas_sessoes()
            if not isinstance(sessoes, list):
                return []
            return formatar_linhas_sessoes(sessoes)
        except SQLAlchemyError as e:
            logger.exception("Erro ao buscar sessões: %s", e)
            return []

    def _atualizar_treeview_sessoes_existentes(self):
        """Recarrega os dados na tabela de sessões existentes."""
        self._todas_sessoes_linhas = self._carregar_sessoes_existentes()
        self._filtrar_treeview_sessoes()

    def _filtrar_treeview_sessoes(self):
        """Filtra as sessões existentes exibidas na Treeview."""
        if not self._treeview_sessoes:
            return

        termo = self._var_busca_sessoes.get() if self._var_busca_sessoes else ""
        linhas_filtradas = filtrar_linhas_sessoes(self._todas_sessoes_linhas, termo)

        if self._lbl_contador_sessoes:
            self._lbl_contador_sessoes.config(
                text=f"{len(linhas_filtradas)} sessão(ões)"
            )

        if not self._todas_sessoes_linhas:
            self._treeview_sessoes.frame.grid_remove()
            if self._lbl_sem_sessoes:
                self._lbl_sem_sessoes.grid(row=2, column=0, sticky=NSEW, pady=20)
            return

        if self._lbl_sem_sessoes:
            self._lbl_sem_sessoes.grid_remove()
        self._treeview_sessoes.frame.grid(row=2, column=0, sticky=NSEW)
        self._treeview_sessoes.construir_dados_tabela(linhas_filtradas)

    def _salvar_nova_opcao_lanche(self, selecao: str):
        """Salva uma nova opção de lanche no JSON se ela for nova e envia para a nuvem."""
        if not selecao or selecao in self._conjunto_opcoes_lanche or "Erro" in selecao:
            return

        normalizado = capitalizar(selecao)
        self._conjunto_opcoes_lanche.add(normalizado)
        try:
            valores_ordenados = sorted(list(self._conjunto_opcoes_lanche))
            if salvar_json(str(CAMINHO_JSON_LANCHES), valores_ordenados):
                if self._combobox_lanche:
                    self._combobox_lanche["values"] = valores_ordenados
                    self._combobox_lanche.set(normalizado)
                if self._combobox_lanche_editar:
                    self._combobox_lanche_editar["values"] = valores_ordenados
                    self._combobox_lanche_editar.set(normalizado)
                if hasattr(self._fachada, "adicionar_novo_lanche_bidirecional"):
                    self._fachada.adicionar_novo_lanche_bidirecional(normalizado)
        except (OSError, ValueError, tk.TclError, ErroAPIGoogle):
            Messagebox.show_error(
                "Não foi possível salvar a nova opção de lanche.", parent=self
            )

    def _ao_sincronizar_reservas(self):
        """Inicia o processo de sincronização de reservas em uma thread."""
        if hasattr(self._parente_app, "mostrar_barra_progresso"):
            self._parente_app.mostrar_barra_progresso(True, "Sincronizando reservas...")
        self.update_idletasks()

        thread = Thread(target=self._acao_sincronizacao, daemon=True)
        thread.start()
        self._monitorar_sincronizacao(thread)

    def _acao_sincronizacao(self):
        """Wrapper para a chamada de sincronização, capturando exceções."""
        thread = threading.current_thread()
        thread.error = None
        try:
            self._fachada.sincronizar_do_google_sheets()
        except Exception as e:  # noqa: BLE001 - ponte de erro entre thread worker e UI
            thread.error = e

    def _monitorar_sincronizacao(self, thread: Thread):
        """Verifica o status da thread e exibe o resultado ao final."""
        if thread.is_alive():
            self.after(150, lambda: self._monitorar_sincronizacao(thread))
            return

        if hasattr(self._parente_app, "mostrar_barra_progresso"):
            self._parente_app.mostrar_barra_progresso(False)
        erro = getattr(thread, "error", None)
        if erro:
            Messagebox.show_error(
                f"Falha ao sincronizar reservas:\n{erro}", parent=self
            )
        else:
            Messagebox.show_info("Reservas sincronizadas com sucesso.", parent=self)
            self._atualizar_treeview_sessoes_existentes()
            opcoes, lista_exib = self._carregar_opcoes_lanche()
            self._conjunto_opcoes_lanche = opcoes
            if self._combobox_lanche:
                self._combobox_lanche["values"] = lista_exib
            if self._combobox_lanche_editar:
                self._combobox_lanche_editar["values"] = lista_exib
            self._atualizar_contexto_grade(modo_edicao=False, aplicar_selecao=False)
            if "editar" in self._contextos:
                self._atualizar_contexto_grade(modo_edicao=True, aplicar_selecao=False)

    def _centralizar_janela(self):
        """Centraliza o diálogo em relação à janela principal."""
        self.update_idletasks()
        px, py = self._parente_app.winfo_x(), self._parente_app.winfo_y()
        pw, ph = self._parente_app.winfo_width(), self._parente_app.winfo_height()
        sw, sh = self.winfo_width(), self.winfo_height()
        x = max(20, px + (pw // 2) - (sw // 2))
        y = max(20, py + (ph // 2) - (sh // 2))
        self.geometry(f"{sw}x{sh}+{x}+{y}")

    def _chave_ordenacao_sessao(self, sessao: Dict) -> dt.datetime:
        """Chave de ordenação para as sessões, tratando datas mal formatadas."""
        return chave_ordenacao_sessao(sessao)
