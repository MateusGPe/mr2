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
    Optional,
    Set,
    Tuple,
    Union,
)

import ttkbootstrap as ttk
from ttkbootstrap import ScrolledFrame
from ttkbootstrap.constants import EW, HORIZONTAL, NSEW, E, W
from ttkbootstrap.dialogs import Messagebox

from registro.gui.comum.controles.treeview_simples import TreeviewSimples
from registro.gui.comum.utils import capitalizar
from registro.gui.registrar.constants import (
    CAMINHO_JSON_LANCHES,
    NOME_LANCHE_PADRAO,
    DadosNovaSessao,
    obter_turmas_integrado,
)
from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.services import grade_horarios_service
from registro.nucleo.utils import carregar_json, salvar_json

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

MAPA_NOMES_DIAS: Dict[str, str] = {
    "segunda": "Segunda-feira",
    "terca": "Terça-feira",
    "quarta": "Quarta-feira",
    "quinta": "Quinta-feira",
    "sexta": "Sexta-feira",
    "sabado": "Sábado",
    "domingo": "Domingo",
}


class DialogoSessao(tk.Toplevel):
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
        except Exception as e:
            logger.warning("Não foi possível carregar detalhes da sessão ativa: %s", e)
            self._sessao_ativa_info = None

        aba_ativa_inicial = None
        if self._sessao_ativa_info:
            aba_ativa_inicial = self._criar_aba(
                "✏️ Editar Sessão Ativa", self._criar_conteudo_aba_editar_sessao
            )

        self._criar_aba(
            "➕ Criar Nova Sessão", self._criar_conteudo_aba_nova_sessao
        )
        self._criar_aba(
            "📂 Carregar Sessão Existente", self._criar_conteudo_aba_carregar_sessao
        )

        if aba_ativa_inicial:
            self._notebook.select(aba_ativa_inicial)

        self._notebook.bind("<<NotebookTabChanged>>", self._ao_mudar_aba)

        botoes_frame = self._criar_secao_botoes_principais(main_frame)
        botoes_frame.grid(row=1, column=0, sticky=EW, pady=(12, 0))
        self._ao_mudar_aba()

    def _criar_aba(self, texto_aba: str, construtor_conteudo: Callable) -> ttk.Frame:
        """Cria uma aba no notebook e a popula usando uma função construtora."""
        frame_aba = ttk.Frame(self._notebook, padding=12)
        frame_aba.columnconfigure(0, weight=1)
        frame_aba.rowconfigure(0, weight=1)
        self._notebook.add(frame_aba, text=f"  {texto_aba}  ")
        construtor_conteudo(frame_aba)
        return frame_aba

    def _ao_mudar_aba(self, _=None):
        """Atualiza o texto e estilo do botão principal com base na aba selecionada."""
        if not self._notebook or not self._btn_iniciar_acao:
            return
        aba_selecionada = self._notebook.tab(self._notebook.select(), "text").strip()
        if "Editar" in aba_selecionada:
            self._btn_iniciar_acao.config(text="💾 Salvar Alterações", bootstyle="primary")
        elif "Carregar" in aba_selecionada:
            self._btn_iniciar_acao.config(text="📂 Carregar Sessão", bootstyle="info")
        else:
            self._btn_iniciar_acao.config(text="✔️ Iniciar Sessão", bootstyle="success")

    # ------------------------------------------------------------------------
    # Construção compartilhada do layout de 2 colunas (Nova / Editar Sessão)
    # ------------------------------------------------------------------------

    def _chave_modo(self, modo_edicao: bool) -> str:
        return "editar" if modo_edicao else "nova"

    def _criar_workspace_duas_colunas(
        self, parent: ttk.Frame, modo_edicao: bool
    ) -> Tuple[ttk.Frame, ttk.Frame]:
        """Estrutura padrão em 2 colunas: esquerda (detalhes + grade) e direita (turmas)."""
        container = ttk.Frame(parent)
        container.grid(row=0, column=0, sticky=NSEW)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=4, uniform="cols_sessao")
        container.columnconfigure(1, weight=6, uniform="cols_sessao")

        col_esq = ttk.Frame(container)
        col_esq.grid(row=0, column=0, sticky=NSEW, padx=(0, 10))
        col_esq.columnconfigure(0, weight=1)
        col_esq.rowconfigure(1, weight=1)

        col_dir = ttk.Frame(container)
        col_dir.grid(row=0, column=1, sticky=NSEW)
        col_dir.columnconfigure(0, weight=1)
        col_dir.rowconfigure(0, weight=1)

        chave = self._chave_modo(modo_edicao)
        self._contextos[chave] = {
            "dados_checkboxes": [],
            "widgets_turma": [],
            "lbl_sec_turmas": None,
            "lbl_sec_categorias": None,
            "var_busca": tk.StringVar(),
            "lbl_contador": None,
            "lbl_grade_header": None,
            "btn_todos_horarios": None,
            "frame_slots_grade": None,
            "lbl_status_reservas": None,
            "var_horario_livre": tk.BooleanVar(
                value=(
                    getattr(self._fachada, "ignorar_horario_grade", False) is True
                    if modo_edicao
                    else False
                )
            ),
            "slot_selecionado_idx": None,
        }
        return col_esq, col_dir

    def _criar_conteudo_aba_nova_sessao(self, parent: ttk.Frame):
        """Popula a aba de criação de nova sessão no layout de 2 colunas."""
        col_esq, col_dir = self._criar_workspace_duas_colunas(parent, modo_edicao=False)

        card_detalhes = self._criar_card_detalhes_nova_sessao(col_esq)
        card_detalhes.grid(row=0, column=0, sticky=EW, pady=(0, 10))

        card_grade = self._criar_card_grade_horarios(col_esq, modo_edicao=False)
        card_grade.grid(row=1, column=0, sticky=NSEW)

        card_turmas = self._criar_card_selecao_turmas(col_dir, modo_edicao=False)
        card_turmas.grid(row=0, column=0, sticky=NSEW)

        self._dados_checkbox_turmas = self._contextos["nova"]["dados_checkboxes"]
        self._atualizar_contexto_grade(modo_edicao=False, aplicar_selecao=True)

    def _criar_conteudo_aba_editar_sessao(self, parent: ttk.Frame):
        """Popula a aba de edição da sessão ativa no layout de 2 colunas."""
        if not self._sessao_ativa_info:
            ttk.Label(parent, text="Nenhuma sessão ativa encontrada.").grid(
                row=0, column=0, pady=20
            )
            return

        col_esq, col_dir = self._criar_workspace_duas_colunas(parent, modo_edicao=True)

        card_detalhes = self._criar_card_detalhes_editar_sessao(col_esq)
        card_detalhes.grid(row=0, column=0, sticky=EW, pady=(0, 10))

        card_grade = self._criar_card_grade_horarios(col_esq, modo_edicao=True)
        card_grade.grid(row=1, column=0, sticky=NSEW)

        card_turmas = self._criar_card_selecao_turmas(col_dir, modo_edicao=True)
        card_turmas.grid(row=0, column=0, sticky=NSEW)

        self._dados_checkbox_turmas_editar = self._contextos["editar"]["dados_checkboxes"]

        grupos_atuais = set(self._sessao_ativa_info.get("grupos", []))
        for nome_turma, var, _ in self._dados_checkbox_turmas_editar:
            if nome_turma in grupos_atuais:
                var.set(True)

        self._atualizar_contador_turmas(modo_edicao=True)
        self._atualizar_contexto_grade(modo_edicao=True, aplicar_selecao=False)

    def _criar_card_detalhes_nova_sessao(self, parent: ttk.Frame) -> ttk.Labelframe:
        """Card superior esquerdo com os dados da nova sessão."""
        card = ttk.Labelframe(parent, text="📝 Detalhes da Nova Sessão", padding=12)
        card.columnconfigure(1, weight=1)
        card.columnconfigure(3, weight=1)

        ttk.Label(card, text="Data:", font="-weight bold").grid(
            row=0, column=0, sticky=W, padx=(0, 6), pady=(0, 8)
        )
        self._entrada_data = ttk.DateEntry(
            card, width=12, bootstyle="primary", date_format="%d/%m/%Y"
        )
        self._entrada_data.grid(row=0, column=1, sticky=EW, padx=(0, 10), pady=(0, 8))
        self._entrada_data.bind(
            "<<DateEntrySelected>>",
            lambda _e: self._ao_alterar_data_ou_refeicao(aplicar_grade=True),
        )
        self._entrada_data.entry.bind(
            "<FocusOut>",
            lambda _e: self._ao_alterar_data_ou_refeicao(aplicar_grade=True),
        )
        self._entrada_data.entry.bind(
            "<Return>",
            lambda _e: self._ao_alterar_data_ou_refeicao(aplicar_grade=True),
        )

        ttk.Label(card, text="Horário:", font="-weight bold").grid(
            row=0, column=2, sticky=W, padx=(0, 6), pady=(0, 8)
        )
        self._entrada_hora = ttk.Entry(card, width=8)
        self._entrada_hora.insert(0, dt.datetime.now().strftime("%H:%M"))
        self._entrada_hora.grid(row=0, column=3, sticky=EW, pady=(0, 8))

        ttk.Label(card, text="Refeição:", font="-weight bold").grid(
            row=1, column=0, sticky=W, padx=(0, 6), pady=(0, 8)
        )
        self._combobox_refeicao = ttk.Combobox(
            card, values=["Lanche", "Almoço", "Jantar"], state="readonly"
        )
        self._combobox_refeicao.grid(
            row=1, column=1, columnspan=3, sticky=EW, pady=(0, 8)
        )

        ttk.Label(card, text="Cardápio:", font="-weight bold").grid(
            row=2, column=0, sticky=W, padx=(0, 6), pady=(0, 8)
        )
        self._combobox_lanche = ttk.Combobox(card, bootstyle="info")
        self._combobox_lanche.grid(
            row=2, column=1, columnspan=3, sticky=EW, pady=(0, 8)
        )

        hora_agora = dt.datetime.now().time()
        if dt.time(17, 30) <= hora_agora <= dt.time(21, 30):
            self._combobox_refeicao.current(2)
        elif dt.time(11, 0) <= hora_agora <= dt.time(14, 0):
            self._combobox_refeicao.current(1)
        else:
            self._combobox_refeicao.current(0)

        self._combobox_refeicao.bind(
            "<<ComboboxSelected>>",
            lambda _e: self._ao_alterar_data_ou_refeicao(aplicar_grade=True),
        )

        opcoes_lanche, lista_exibicao = self._carregar_opcoes_lanche()
        self._conjunto_opcoes_lanche = opcoes_lanche
        self._combobox_lanche["values"] = lista_exibicao
        self._ao_selecionar_refeicao()

        lbl_status = ttk.Label(
            card, text="", font="-size 9", wraplength=320, justify="left"
        )
        lbl_status.grid(row=3, column=0, columnspan=4, sticky=EW, pady=(2, 0))
        self._contextos["nova"]["lbl_status_reservas"] = lbl_status

        return card

    def _criar_card_detalhes_editar_sessao(self, parent: ttk.Frame) -> ttk.Labelframe:
        """Card superior esquerdo com o resumo da sessão ativa e edição do cardápio."""
        card = ttk.Labelframe(parent, text="📌 Sessão Ativa", padding=12)
        card.columnconfigure(1, weight=1)
        card.columnconfigure(3, weight=1)

        info = self._sessao_ativa_info or {}
        id_sessao = info.get("id", "?")
        refeicao = capitalizar(str(info.get("refeicao", "")))
        data = str(info.get("data", ""))
        hora = str(info.get("hora", ""))
        item_atual = str(info.get("item_servido") or "")

        ttk.Label(card, text="ID:", font="-weight bold").grid(
            row=0, column=0, sticky=W, padx=(0, 6), pady=(0, 6)
        )
        ttk.Label(card, text=f"#{id_sessao}", bootstyle="primary").grid(
            row=0, column=1, sticky=W, pady=(0, 6)
        )

        ttk.Label(card, text="Refeição:", font="-weight bold").grid(
            row=0, column=2, sticky=W, padx=(8, 6), pady=(0, 6)
        )
        ttk.Label(card, text=refeicao, bootstyle="info").grid(
            row=0, column=3, sticky=W, pady=(0, 6)
        )

        ttk.Label(card, text="Data/Hora:", font="-weight bold").grid(
            row=1, column=0, sticky=W, padx=(0, 6), pady=(0, 8)
        )
        ttk.Label(card, text=f"📅 {data} às {hora}").grid(
            row=1, column=1, columnspan=3, sticky=W, pady=(0, 8)
        )

        ttk.Label(card, text="Cardápio:", font="-weight bold").grid(
            row=2, column=0, sticky=W, padx=(0, 6), pady=(0, 8)
        )
        opcoes_lanche, lista_exibicao = self._carregar_opcoes_lanche()
        self._conjunto_opcoes_lanche = opcoes_lanche
        self._combobox_lanche_editar = ttk.Combobox(
            card, values=lista_exibicao, bootstyle="info"
        )
        self._combobox_lanche_editar.set(item_atual)
        self._combobox_lanche_editar.grid(
            row=2, column=1, columnspan=3, sticky=EW, pady=(0, 8)
        )

        lbl_status = ttk.Label(
            card, text="", font="-size 9", wraplength=320, justify="left"
        )
        lbl_status.grid(row=3, column=0, columnspan=4, sticky=EW, pady=(2, 0))
        self._contextos["editar"]["lbl_status_reservas"] = lbl_status

        return card

    def _criar_card_grade_horarios(
        self, parent: ttk.Frame, modo_edicao: bool
    ) -> ttk.Labelframe:
        """Card inferior esquerdo com slots interativos da Grade de Horários e Horário Livre."""
        ctx = self._contextos[self._chave_modo(modo_edicao)]
        card = ttk.Labelframe(parent, text="🕒 Grade de Horários do Dia", padding=12)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(1, weight=1)

        topo = ttk.Frame(card)
        topo.grid(row=0, column=0, sticky=EW, pady=(0, 8))
        topo.columnconfigure(0, weight=1)

        lbl_header = ttk.Label(
            topo, text="Carregando grade...", font="-size 9 -weight bold", bootstyle="info"
        )
        lbl_header.grid(row=0, column=0, sticky=W)
        ctx["lbl_grade_header"] = lbl_header

        btn_todos = ttk.Button(
            topo,
            text="Todos os horários",
            bootstyle="success-outline",
            command=lambda: self._ao_selecionar_grade_do_dia(modo_edicao=modo_edicao),
        )
        btn_todos.grid(row=0, column=1, sticky=E)
        ctx["btn_todos_horarios"] = btn_todos

        frame_slots = ScrolledFrame(card, auto_hide=True, bootstyle="round", padding=4)
        frame_slots.grid(row=1, column=0, sticky=NSEW, pady=(0, 8))
        frame_slots.columnconfigure(0, weight=1)
        ctx["frame_slots_grade"] = frame_slots

        sep = ttk.Separator(card, orient=HORIZONTAL)
        sep.grid(row=2, column=0, sticky=EW, pady=(2, 8))

        chk_livre = ttk.Checkbutton(
            card,
            text="🕒 Horário Livre (ignorar trava de horário da grade)",
            variable=ctx["var_horario_livre"],
            bootstyle="warning-round-toggle",
        )
        chk_livre.grid(row=3, column=0, sticky=W)

        return card

    def _criar_card_selecao_turmas(
        self, parent: ttk.Frame, modo_edicao: bool
    ) -> ttk.Labelframe:
        """Card direito com busca, atalhos rápidos, grid de checkboxes e contador."""
        ctx = self._contextos[self._chave_modo(modo_edicao)]
        card = ttk.Labelframe(
            parent, text="🎟️ Turmas e Categorias Participantes", padding=12
        )
        card.columnconfigure(0, weight=1)
        card.rowconfigure(2, weight=1)

        # 1. Busca + Contador
        frame_busca = ttk.Frame(card)
        frame_busca.grid(row=0, column=0, sticky=EW, pady=(0, 8))
        frame_busca.columnconfigure(1, weight=1)

        ttk.Label(frame_busca, text="🔍 Buscar:", font="-weight bold").grid(
            row=0, column=0, sticky=W, padx=(0, 6)
        )
        ent_busca = ttk.Entry(frame_busca, textvariable=ctx["var_busca"])
        ent_busca.grid(row=0, column=1, sticky=EW)
        ent_busca.bind(
            "<KeyRelease>", lambda _e: self._filtrar_checkboxes(modo_edicao)
        )

        ttk.Button(
            frame_busca,
            text="✕",
            width=3,
            bootstyle="secondary-outline",
            command=lambda: self._limpar_busca_turmas(modo_edicao),
        ).grid(row=0, column=2, padx=(4, 10))

        lbl_contador = ttk.Label(
            frame_busca,
            text="0 selecionadas",
            font="-size 9 -weight bold",
            bootstyle="primary",
        )
        lbl_contador.grid(row=0, column=3, sticky=E)
        ctx["lbl_contador"] = lbl_contador

        # 2. Barra de Atalhos (2x3 para boa legibilidade)
        frame_atalhos = ttk.Frame(card)
        frame_atalhos.grid(row=1, column=0, sticky=EW, pady=(0, 8))
        frame_atalhos.columnconfigure((0, 1, 2), weight=1)

        atalhos = [
            ("🕒 Grade do Dia", lambda: self._ao_selecionar_grade_do_dia(modo_edicao), "success-outline"),
            ("📋 Com Reserva", lambda: self._ao_selecionar_com_reserva(modo_edicao), "primary-outline"),
            ("🔗 Integrado", lambda: self._ao_selecionar_integral(modo_edicao), "info-outline"),
            ("📚 Outros", lambda: self._ao_selecionar_outros(modo_edicao), "info-outline"),
            ("🔄 Inverter", lambda: self._ao_inverter_turmas(modo_edicao), "secondary-outline"),
            ("⚪ Limpar", lambda: self._ao_limpar_turmas(modo_edicao), "secondary-outline"),
        ]
        for idx, (texto, cmd, estilo) in enumerate(atalhos):
            ttk.Button(
                frame_atalhos, text=texto, command=cmd, bootstyle=estilo
            ).grid(row=idx // 3, column=idx % 3, sticky=EW, padx=2, pady=2)

        # 3. Grade rolável de checkboxes (Turmas + Categorias)
        frame_checks = self._criar_checkboxes_turmas(card, modo_edicao=modo_edicao)
        frame_checks.grid(row=2, column=0, sticky=NSEW)

        return card

    def _criar_checkboxes_turmas(
        self, master: tk.Widget, modo_edicao: bool
    ) -> ScrolledFrame:
        """Cria os checkboxes separados em Turmas e Categorias dentro de um ScrolledFrame."""
        ctx = self._contextos[self._chave_modo(modo_edicao)]
        container = ScrolledFrame(master, auto_hide=True, bootstyle="round")

        turmas = self._turmas_disponiveis
        categorias = self._categorias_disponiveis
        if not turmas and not categorias:
            ttk.Label(container, text="Nenhuma turma ou categoria disponível.").pack(
                pady=16
            )
            return container

        num_cols = 3
        container.columnconfigure(list(range(num_cols)), weight=1)

        def _render_bloco(
            titulo: str, itens: List[str], row_base: int, estilo: str, secao: str
        ) -> Tuple[int, Optional[ttk.Label]]:
            if not itens:
                return row_base, None
            lbl_sec = ttk.Label(
                container,
                text=titulo,
                font="-size 9 -weight bold",
                bootstyle="info",
                anchor=W,
            )
            lbl_sec.grid(
                row=row_base, column=0, columnspan=num_cols, sticky=EW, padx=8, pady=(8, 4)
            )
            row_base += 1
            for i, nome in enumerate(itens):
                var = tk.BooleanVar(value=False)
                cb = ttk.Checkbutton(
                    container,
                    text=nome,
                    variable=var,
                    bootstyle=estilo,
                    command=lambda m=modo_edicao: self._atualizar_contador_turmas(m),
                )
                cb.grid(
                    row=row_base + (i // num_cols),
                    column=i % num_cols,
                    sticky=W,
                    padx=8,
                    pady=4,
                )
                ctx["dados_checkboxes"].append((nome, var, cb))
                ctx["widgets_turma"].append((nome, cb, secao))
            return row_base + ((len(itens) - 1) // num_cols) + 1, lbl_sec

        prox, lbl_t = _render_bloco(
            "🏫 Turmas", turmas, 0, "primary-round-toggle", "turma"
        )
        _, lbl_c = _render_bloco(
            "🏷️ Categorias (Eventos, Optativas, PAP...)",
            categorias,
            prox,
            "info-round-toggle",
            "categoria",
        )
        ctx["lbl_sec_turmas"] = lbl_t
        ctx["lbl_sec_categorias"] = lbl_c

        return container

    # ------------------------------------------------------------------------
    # Aba Carregar Sessão Existente
    # ------------------------------------------------------------------------

    def _criar_conteudo_aba_carregar_sessao(self, parent: ttk.Frame):
        """Popula a aba de carregamento com barra de filtro e Treeview detalhada."""
        parent.rowconfigure(0, weight=0)
        parent.rowconfigure(1, weight=0)
        parent.rowconfigure(2, weight=1)
        parent.rowconfigure(3, weight=0)

        barra_topo = ttk.Frame(parent)
        barra_topo.grid(row=0, column=0, sticky=EW, pady=(0, 8))
        barra_topo.columnconfigure(1, weight=1)

        ttk.Label(barra_topo, text="🔍 Filtrar sessões:", font="-weight bold").grid(
            row=0, column=0, sticky=W, padx=(0, 8)
        )
        self._var_busca_sessoes = tk.StringVar()
        ent_filtro = ttk.Entry(barra_topo, textvariable=self._var_busca_sessoes)
        ent_filtro.grid(row=0, column=1, sticky=EW)
        ent_filtro.bind("<KeyRelease>", lambda _e: self._filtrar_treeview_sessoes())

        self._lbl_contador_sessoes = ttk.Label(
            barra_topo, text="0 sessões", font="-size 9 -weight bold", bootstyle="info"
        )
        self._lbl_contador_sessoes.grid(row=0, column=2, sticky=E, padx=(10, 0))

        ttk.Separator(parent, orient=HORIZONTAL).grid(
            row=1, column=0, sticky=EW, pady=(0, 10)
        )

        cols = [
            {"text": "ID", "stretch": False, "width": 55},
            {"text": "Data", "stretch": False, "width": 95},
            {"text": "Hora", "stretch": False, "width": 70},
            {"text": "Refeição", "stretch": False, "width": 95},
            {"text": "Cardápio / Item", "stretch": True, "width": 190},
            {"text": "Turmas", "stretch": True, "width": 200},
        ]

        self._treeview_sessoes = TreeviewSimples(
            master=parent,
            dados_colunas=cols,
            height=12,
            select_bootstyle="info",
            enable_hover=True,
        )
        self._treeview_sessoes.view.bind("<Double-1>", lambda _: self._ao_ok())
        self._treeview_sessoes.frame.grid(row=2, column=0, sticky=NSEW)

        self._lbl_sem_sessoes = ttk.Label(
            parent,
            text="Nenhuma sessão anterior encontrada.",
            anchor="center",
            bootstyle="secondary",
        )

        ttk.Label(
            parent,
            text="💡 Dica: Dê um duplo clique em uma linha para carregar a sessão imediatamente.",
            font="-size 9",
            bootstyle="secondary",
        ).grid(row=3, column=0, sticky=W, pady=(8, 0))

        self._atualizar_treeview_sessoes_existentes()

    # ------------------------------------------------------------------------
    # Rodapé de botões principais
    # ------------------------------------------------------------------------

    def _criar_secao_botoes_principais(self, parent: tk.Widget) -> ttk.Frame:
        """Cria os botões principais na parte inferior do diálogo."""
        frame = ttk.Frame(parent)
        frame.columnconfigure(0, weight=1)

        ttk.Button(
            frame,
            text="📥 Sincronizar Nuvem",
            command=self._ao_sincronizar_reservas,
            bootstyle="warning-outline",
        ).grid(row=0, column=0, sticky=W)
        ttk.Button(
            frame, text="❌ Cancelar", command=self._ao_fechar, bootstyle="danger-outline"
        ).grid(row=0, column=1, sticky=E, padx=6)
        self._btn_iniciar_acao = ttk.Button(
            frame, text="✔️ Iniciar Sessão", command=self._ao_ok, bootstyle="success"
        )
        self._btn_iniciar_acao.grid(row=0, column=2, sticky=E)

        return frame

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
            except Exception:
                pass
        return dt.datetime.now().strftime("%d/%m/%Y")

    def _obter_refeicao_contexto(self, modo_edicao: bool) -> str:
        """Retorna o nome da refeição do contexto ativo em minúsculas."""
        if modo_edicao and self._sessao_ativa_info:
            return str(self._sessao_ativa_info.get("refeicao", "lanche")).strip().lower()
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

    def _obter_slots_grade(self, dia_semana: str, refeicao: str) -> List[Dict[str, Any]]:
        """Busca os slots configurados na grade horária para o dia e refeição."""
        grade: Any = None
        try:
            if self._fachada and hasattr(self._fachada, "obter_grade_horarios"):
                grade = self._fachada.obter_grade_horarios()
        except Exception as e:
            logger.debug("Falha ao ler grade pela fachada: %s", e)

        if not isinstance(grade, dict):
            grade = grade_horarios_service.carregar_grade_horarios()

        dia_norm = grade_horarios_service._normalizar_chave(dia_semana)
        ref_norm = grade_horarios_service._normalizar_chave(refeicao)
        slots = grade.get(dia_norm, {}).get(ref_norm, [])
        if not isinstance(slots, list):
            return []
        return sorted(
            [s for s in slots if isinstance(s, dict)],
            key=lambda s: str(s.get("inicio", "99:99")),
        )

    def _expandir_grupos_slot(self, slot: Dict[str, Any]) -> Set[str]:
        """Retorna os nomes de turmas/categorias autorizadas por um slot da grade."""
        turmas_slot = slot.get("turmas", [])
        cats_slot = slot.get("categorias", [])
        rest_turma = grade_horarios_service._tem_restricao_especifica(turmas_slot)
        rest_cat = grade_horarios_service._tem_restricao_especifica(cats_slot)

        grupos: Set[str] = set()
        coringas = {"*", "TODAS"}
        for t in turmas_slot:
            t_limpo = str(t).strip()
            if t_limpo and t_limpo.upper() not in coringas:
                grupos.add(t_limpo)
        for c in cats_slot:
            c_limpo = str(c).strip()
            if c_limpo and c_limpo.upper() not in coringas:
                grupos.add(c_limpo)

        if not rest_turma and not rest_cat:
            grupos.update(self._turmas_disponiveis)
            grupos.update(self._categorias_disponiveis)
        return grupos

    def _resumo_slot_texto(self, slot: Dict[str, Any]) -> str:
        """Gera descrição legível das turmas e categorias de um slot."""
        turmas_slot = [str(t).strip() for t in slot.get("turmas", []) if str(t).strip()]
        cats_slot = [str(c).strip() for c in slot.get("categorias", []) if str(c).strip()]
        rest_turma = grade_horarios_service._tem_restricao_especifica(turmas_slot)
        rest_cat = grade_horarios_service._tem_restricao_especifica(cats_slot)

        if not rest_turma and not rest_cat:
            return "Todas as turmas e categorias (*)"

        partes: List[str] = []
        if rest_turma:
            if len(turmas_slot) > 4:
                partes.append(", ".join(turmas_slot[:4]) + f" (+{len(turmas_slot) - 4})")
            else:
                partes.append(", ".join(turmas_slot))
        if rest_cat:
            partes.append("Cat: " + ", ".join(cats_slot))
        return " | ".join(partes)

    def _slot_esta_ativo_agora(self, slot: Dict[str, Any]) -> bool:
        """Verifica se o horário atual do sistema está dentro do slot."""
        try:
            ini = grade_horarios_service._hora_para_minutos(slot.get("inicio", ""))
            fim = grade_horarios_service._hora_para_minutos(slot.get("fim", ""))
            agora = dt.datetime.now()
            atual_m = agora.hour * 60 + agora.minute
            return ini <= atual_m <= fim
        except Exception:
            return False

    def _atualizar_contexto_grade(
        self, modo_edicao: bool, aplicar_selecao: bool = False
    ):
        """Atualiza o preview da grade de horários, reservas e (opcionalmente) marca turmas."""
        ctx = self._contextos.get(self._chave_modo(modo_edicao))
        if not ctx:
            return

        dia_semana = self._obter_dia_semana_contexto(modo_edicao)
        refeicao = self._obter_refeicao_contexto(modo_edicao)
        nome_dia = MAPA_NOMES_DIAS.get(dia_semana, capitalizar(dia_semana))
        nome_ref = capitalizar(refeicao)

        if ctx["lbl_grade_header"]:
            ctx["lbl_grade_header"].config(text=f"📅 {nome_dia} • {nome_ref}")

        self._atualizar_status_reservas(modo_edicao)
        slots = self._obter_slots_grade(dia_semana, refeicao)
        self._renderizar_slots_grade(modo_edicao, slots)

        if aplicar_selecao:
            turmas_grade = self._obter_turmas_grade(dia_semana, refeicao)
            if turmas_grade:
                turmas_grade_norm = {t.strip().lower() for t in turmas_grade if t and str(t).strip()}
                ctx["slot_selecionado_idx"] = None
                self._definir_checkboxes_turmas(
                    lambda n, _v: n.strip().lower() in turmas_grade_norm, modo_edicao=modo_edicao
                )
                self._renderizar_slots_grade(modo_edicao, slots)

    def _renderizar_slots_grade(
        self, modo_edicao: bool, slots: List[Dict[str, Any]]
    ):
        """Renderiza os cartões clicáveis dos horários da grade no painel esquerdo."""
        ctx = self._contextos[self._chave_modo(modo_edicao)]
        container: Optional[ScrolledFrame] = ctx.get("frame_slots_grade")
        if not container:
            return

        for w in container.winfo_children():
            w.destroy()

        if ctx.get("btn_todos_horarios"):
            estilo_todos = (
                "success" if ctx["slot_selecionado_idx"] is None else "success-outline"
            )
            ctx["btn_todos_horarios"].config(
                bootstyle=estilo_todos,
                state="normal" if slots else "disabled",
            )

        if not slots:
            ttk.Label(
                container,
                text=(
                    "Nenhum horário específico na grade para este dia/refeição.\n"
                    "Selecione as turmas manualmente ou use os atalhos à direita."
                ),
                font="-size 9",
                bootstyle="secondary",
                wraplength=290,
                justify="left",
            ).pack(fill=tk.X, padx=6, pady=12)
            return

        slot_sel = ctx.get("slot_selecionado_idx")
        for idx, slot in enumerate(slots):
            inicio = str(slot.get("inicio", "--:--"))
            fim = str(slot.get("fim", "--:--"))
            agora_ativo = self._slot_esta_ativo_agora(slot)
            selecionado = slot_sel == idx

            if selecionado:
                estilo_btn = "info"
                marcador = "✓ Filtrado"
            elif agora_ativo:
                estilo_btn = "success-outline"
                marcador = "● Agora"
            else:
                estilo_btn = "secondary-outline"
                marcador = "Clique p/ filtrar"

            texto_btn = (
                f"🕒 {inicio} – {fim}   [{marcador}]\n"
                f"    {self._resumo_slot_texto(slot)}"
            )
            btn = ttk.Button(
                container,
                text=texto_btn,
                bootstyle=estilo_btn,
                command=lambda m=modo_edicao, i=idx: self._ao_clicar_slot_grade(m, i),
            )
            btn.pack(fill=tk.X, padx=2, pady=3)

    def _ao_clicar_slot_grade(self, modo_edicao: bool, idx: int):
        """Filtra/marca exclusivamente as turmas do horário clicado na grade."""
        ctx = self._contextos[self._chave_modo(modo_edicao)]
        dia_semana = self._obter_dia_semana_contexto(modo_edicao)
        refeicao = self._obter_refeicao_contexto(modo_edicao)
        slots = self._obter_slots_grade(dia_semana, refeicao)
        if not (0 <= idx < len(slots)):
            return

        ctx["slot_selecionado_idx"] = idx
        grupos_slot = self._expandir_grupos_slot(slots[idx])
        grupos_slot_norm = {g.strip().lower() for g in grupos_slot if g and str(g).strip()}
        self._definir_checkboxes_turmas(
            lambda n, _v: n.strip().lower() in grupos_slot_norm, modo_edicao=modo_edicao
        )
        self._renderizar_slots_grade(modo_edicao, slots)

    def _atualizar_status_reservas(self, modo_edicao: bool):
        """Atualiza o indicador visual de reservas encontradas para a data e refeição."""
        ctx = self._contextos[self._chave_modo(modo_edicao)]
        lbl: Optional[ttk.Label] = ctx.get("lbl_status_reservas")
        if not lbl:
            return

        refeicao = self._obter_refeicao_contexto(modo_edicao)
        data_str = self._obter_data_contexto(modo_edicao)

        if refeicao not in ("almoço", "almoco", "jantar"):
            lbl.config(
                text="🥐 Lanche: registro livre para as turmas marcadas (sem exigência de reserva).",
                bootstyle="info",
            )
            return

        reservas = self._buscar_reservas_data_refeicao(data_str, refeicao)
        if reservas:
            lbl.config(
                text=f"📋 {len(reservas)} reservas ativas encontradas para {data_str}.",
                bootstyle="success",
            )
        else:
            lbl.config(
                text=f"⚠️ Nenhuma reserva ativa encontrada para {data_str} ({capitalizar(refeicao)}).",
                bootstyle="warning",
            )

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
        except Exception as e:
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
            except Exception as e:
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
        self._combobox_lanche.config(
            state="disabled" if eh_com_reserva else "normal"
        )
        if eh_com_reserva:
            self._combobox_lanche.set("")
        elif NOME_LANCHE_PADRAO in self._conjunto_opcoes_lanche:
            self._combobox_lanche.set(NOME_LANCHE_PADRAO)

    def _filtrar_checkboxes(self, modo_edicao: bool):
        """Filtra os checkboxes de turmas/categorias em tempo real conforme busca."""
        ctx = self._contextos[self._chave_modo(modo_edicao)]
        termo = ctx["var_busca"].get().strip().lower()

        visiveis_turma = 0
        visiveis_cat = 0
        for nome, cb, secao in ctx["widgets_turma"]:
            if not termo or termo in nome.lower():
                cb.grid()
                if secao == "turma":
                    visiveis_turma += 1
                else:
                    visiveis_cat += 1
            else:
                cb.grid_remove()

        if ctx.get("lbl_sec_turmas"):
            if visiveis_turma > 0:
                ctx["lbl_sec_turmas"].grid()
            else:
                ctx["lbl_sec_turmas"].grid_remove()

        if ctx.get("lbl_sec_categorias"):
            if visiveis_cat > 0:
                ctx["lbl_sec_categorias"].grid()
            else:
                ctx["lbl_sec_categorias"].grid_remove()

    def _limpar_busca_turmas(self, modo_edicao: bool):
        ctx = self._contextos[self._chave_modo(modo_edicao)]
        ctx["var_busca"].set("")
        self._filtrar_checkboxes(modo_edicao)

    def _atualizar_contador_turmas(self, modo_edicao: bool):
        """Atualiza o badge contador de turmas e categorias selecionadas."""
        ctx = self._contextos.get(self._chave_modo(modo_edicao))
        if not ctx or not ctx.get("lbl_contador"):
            return
        selecionadas = sum(1 for _n, var, _cb in ctx["dados_checkboxes"] if var.get())
        total = len(ctx["dados_checkboxes"])
        estilo = "success" if selecionadas > 0 else "secondary"
        ctx["lbl_contador"].config(
            text=f"✅ {selecionadas}/{total} selecionadas", bootstyle=estilo
        )

    def _ao_selecionar_grade_do_dia(self, modo_edicao: bool = False):
        """Seleciona as turmas previstas na grade horária para o dia e refeição."""
        ctx = self._contextos.get(self._chave_modo(modo_edicao))
        refeicao = self._obter_refeicao_contexto(modo_edicao)
        dia_semana = self._obter_dia_semana_contexto(modo_edicao)
        turmas_grade = self._obter_turmas_grade(dia_semana, refeicao)

        if ctx:
            ctx["slot_selecionado_idx"] = None
            slots = self._obter_slots_grade(dia_semana, refeicao)
            self._renderizar_slots_grade(modo_edicao, slots)

        if turmas_grade:
            turmas_grade_norm = {t.strip().lower() for t in turmas_grade if t and str(t).strip()}
            self._definir_checkboxes_turmas(
                lambda n, _v: n.strip().lower() in turmas_grade_norm, modo_edicao=modo_edicao
            )
        else:
            Messagebox.show_info(
                f"Nenhuma turma prevista na grade para {capitalizar(refeicao)} na {MAPA_NOMES_DIAS.get(dia_semana, capitalizar(dia_semana))}.",
                "Grade de Horários",
                parent=self,
            )

    def _ao_selecionar_com_reserva(self, modo_edicao: bool = False):
        """Seleciona automaticamente turmas e categorias presentes nas reservas da data."""
        data_str = self._obter_data_contexto(modo_edicao)
        refeicao = self._obter_refeicao_contexto(modo_edicao)
        reservas = self._buscar_reservas_data_refeicao(data_str, refeicao)

        if not reservas:
            Messagebox.show_info(
                f"Nenhuma reserva ativa encontrada para {data_str}.",
                "Sem Reservas",
                parent=self,
            )
            return

        grupos_com_reserva: Set[str] = set()
        for r in reservas:
            if not isinstance(r, dict):
                continue
            turma_str = str(r.get("turma_estudante", "") or "")
            for parte in turma_str.split(","):
                t = parte.strip()
                if t and t != "N/A":
                    grupos_com_reserva.add(t)
            for cat in r.get("categorias", []) or []:
                c = str(cat).strip()
                if c:
                    grupos_com_reserva.add(c)

        if not grupos_com_reserva:
            Messagebox.show_info(
                "As reservas encontradas não possuem turmas ou categorias vinculadas.",
                "Sem Turmas nas Reservas",
                parent=self,
            )
            return

        self._limpar_slot_selecionado(modo_edicao)
        grupos_norm = {g.strip().lower() for g in grupos_com_reserva if g and str(g).strip()}
        self._definir_checkboxes_turmas(
            lambda n, _v: n.strip().lower() in grupos_norm, modo_edicao=modo_edicao
        )

    def _limpar_slot_selecionado(self, modo_edicao: bool):
        ctx = self._contextos.get(self._chave_modo(modo_edicao))
        if ctx and ctx["slot_selecionado_idx"] is not None:
            ctx["slot_selecionado_idx"] = None
            dia = self._obter_dia_semana_contexto(modo_edicao)
            ref = self._obter_refeicao_contexto(modo_edicao)
            self._renderizar_slots_grade(modo_edicao, self._obter_slots_grade(dia, ref))

    def _ao_limpar_turmas(self, modo_edicao: bool = False):
        self._limpar_slot_selecionado(modo_edicao)
        self._definir_checkboxes_turmas(lambda _n, _v: False, modo_edicao=modo_edicao)

    def _ao_selecionar_integral(self, modo_edicao: bool = False):
        self._limpar_slot_selecionado(modo_edicao)
        turmas_integrado = set(obter_turmas_integrado())
        self._definir_checkboxes_turmas(
            lambda n, _v: n in turmas_integrado, modo_edicao=modo_edicao
        )

    def _ao_selecionar_outros(self, modo_edicao: bool = False):
        self._limpar_slot_selecionado(modo_edicao)
        turmas_integrado = set(obter_turmas_integrado())
        self._definir_checkboxes_turmas(
            lambda n, _v: n not in turmas_integrado, modo_edicao=modo_edicao
        )

    def _ao_inverter_turmas(self, modo_edicao: bool = False):
        self._limpar_slot_selecionado(modo_edicao)
        self._definir_checkboxes_turmas(
            lambda _n, v: not v.get(), modo_edicao=modo_edicao
        )

    def _obter_dados_checkboxes_ativos(
        self,
    ) -> List[Tuple[str, tk.BooleanVar, ttk.Checkbutton]]:
        """Retorna os dados dos checkboxes da aba atualmente selecionada."""
        if self._notebook:
            texto = self._notebook.tab(self._notebook.select(), "text")
            if "Editar" in texto:
                return self._dados_checkbox_turmas_editar
        return self._dados_checkbox_turmas

    def _definir_checkboxes_turmas(
        self, condicao: Callable[[str, tk.BooleanVar], bool], modo_edicao: bool = False
    ):
        """Aplica uma condição a todos os checkboxes de turmas e atualiza o contador."""
        if modo_edicao:
            dados = self._dados_checkbox_turmas_editar
        else:
            dados = self._dados_checkbox_turmas or self._obter_dados_checkboxes_ativos()

        for nome, var, _ in dados:
            var.set(condicao(nome, var))

        self._atualizar_contador_turmas(modo_edicao)

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

            logger.info("Sessão ativa ID %s atualizada.", self._sessao_ativa_info.get("id"))
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
            if horario_livre and hasattr(self._fachada, "definir_ignorar_horario_grade"):
                try:
                    self._fachada.definir_ignorar_horario_grade(True)
                    if hasattr(self._parente_app, "_atualizar_estado_horario_livre"):
                        self._parente_app._atualizar_estado_horario_livre()
                except Exception as e:
                    logger.warning("Não foi possível ativar Horário Livre após criar sessão: %s", e)
            self.grab_release()
            self.destroy()

    def _validar_entrada_nova_sessao(self) -> bool:
        """Verifica se os campos para criar uma nova sessão foram preenchidos corretamente."""
        try:
            dt.datetime.strptime(self._entrada_hora.get(), "%H:%M")
        except ValueError:
            Messagebox.show_warning(
                "Hora inválida. Use o formato HH:MM.", parent=self
            )
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
                if isinstance(g, dict) and g.get("nome") and g.get("tipo") != "categoria"
            )
            categorias = sorted(
                g.get("nome", "")
                for g in grupos
                if isinstance(g, dict) and g.get("nome") and g.get("tipo") == "categoria"
            )
            return turmas, categorias
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Erro ao buscar turmas e categorias: %s", e)
            Messagebox.show_error(
                "Não foi possível buscar as turmas.", parent=self
            )
            return [], []

    def _buscar_turmas_disponiveis(self) -> List[str]:
        """Busca a lista unificada de grupos da camada de negócio."""
        turmas, categorias = self._buscar_grupos_separados()
        return sorted(turmas + categorias)

    def _carregar_opcoes_lanche(self) -> Tuple[Set[str], List[str]]:
        """Carrega as opções de lanche a partir de um arquivo JSON."""
        caminho = Path(CAMINHO_JSON_LANCHES)
        padrao = [NOME_LANCHE_PADRAO]
        try:
            opcoes = carregar_json(str(caminho))
            if not isinstance(opcoes, list) or not all(
                isinstance(s, str) for s in opcoes
            ):
                raise TypeError("Conteúdo do JSON de lanches é inválido.")
            return set(opcoes) or set(padrao), sorted(opcoes) or padrao
        except (FileNotFoundError, TypeError) as e:
            logger.warning(
                "Arquivo de lanches não encontrado ou inválido: %s. Usando padrão.", e
            )
            salvar_json(str(caminho), padrao)
            return set(padrao), padrao
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Erro ao carregar lanches de '%s': %s", caminho, e)
            return set(), [f"Erro ao carregar {caminho.name}"]

    def _carregar_sessoes_existentes(self) -> List[Tuple]:
        """Busca e formata as sessões existentes para exibição na Treeview."""
        try:
            sessoes = self._fachada.listar_todas_sessoes()
            if not isinstance(sessoes, list):
                return []
            sessoes_ordenadas = sorted(
                sessoes, key=self._chave_ordenacao_sessao, reverse=True
            )
            linhas: List[Tuple] = []
            for s in sessoes_ordenadas:
                grupos = s.get("grupos") or []
                if len(grupos) > 3:
                    resumo_grupos = f"{len(grupos)} ({', '.join(grupos[:3])}...)"
                elif grupos:
                    resumo_grupos = ", ".join(grupos)
                else:
                    resumo_grupos = "-"

                linhas.append(
                    (
                        s.get("id"),
                        s.get("data"),
                        s.get("hora"),
                        capitalizar(s.get("refeicao", "")),
                        s.get("item_servido") or "-",
                        resumo_grupos,
                    )
                )
            return linhas
        except Exception as e:  # pylint: disable=broad-exception-caught
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

        termo = (
            self._var_busca_sessoes.get().strip().lower()
            if self._var_busca_sessoes
            else ""
        )
        if termo:
            linhas_filtradas = [
                linha
                for linha in self._todas_sessoes_linhas
                if any(termo in str(col).lower() for col in linha)
            ]
        else:
            linhas_filtradas = list(self._todas_sessoes_linhas)

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
        except Exception:  # pylint: disable=broad-exception-caught
            Messagebox.show_error(
                "Não foi possível salvar a nova opção de lanche.", parent=self
            )

    def _ao_sincronizar_reservas(self):
        """Inicia o processo de sincronização de reservas em uma thread."""
        if hasattr(self._parente_app, "mostrar_barra_progresso"):
            self._parente_app.mostrar_barra_progresso(
                True, "Sincronizando reservas..."
            )
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
        except Exception as e:  # pylint: disable=broad-exception-caught
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
            Messagebox.show_info(
                "Reservas sincronizadas com sucesso.", parent=self
            )
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
        try:
            return dt.datetime.strptime(
                sessao.get("data", "01/01/1900") + " " + sessao.get("hora", "00:00"),
                "%d/%m/%Y %H:%M",
            )
        except ValueError:
            return dt.datetime.min
