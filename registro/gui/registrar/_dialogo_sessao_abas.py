# ----------------------------------------------------------------------------
# Arquivo: registro/gui/registrar/_dialogo_sessao_abas.py (Abas do Diálogo)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""Mixin de construção das abas e cards de interface do DialogoSessao."""

import datetime as dt
import tkinter as tk
from typing import Any, Callable, List, Optional, Tuple

import ttkbootstrap as ttk
from ttkbootstrap import ScrolledFrame
from ttkbootstrap.constants import EW, HORIZONTAL, NSEW, E, W

from registro.gui.comum.controles.treeview_simples import TreeviewSimples
from registro.gui.comum.utils import capitalizar
from registro.gui.registrar.dialogo_sessao_logica import indice_refeicao_por_hora


class _DialogoSessaoAbasMixin:
    """Constrói abas, cards de detalhes, grade horária, turmas e botões."""

    def _criar_aba(
        self: Any, texto_aba: str, construtor_conteudo: Callable
    ) -> ttk.Frame:
        """Cria uma aba no notebook e a popula usando uma função construtora."""
        frame_aba = ttk.Frame(self._notebook, padding=12)
        frame_aba.columnconfigure(0, weight=1)
        frame_aba.rowconfigure(0, weight=1)
        self._notebook.add(frame_aba, text=f"  {texto_aba}  ")
        construtor_conteudo(frame_aba)
        return frame_aba

    def _ao_mudar_aba(self: Any, _=None):
        """Atualiza o texto e estilo do botão principal com base na aba selecionada."""
        if not self._notebook or not self._btn_iniciar_acao:
            return
        aba_selecionada = self._notebook.tab(self._notebook.select(), "text").strip()
        if "Editar" in aba_selecionada:
            self._btn_iniciar_acao.config(
                text="💾 Salvar Alterações", bootstyle="primary"
            )
        elif "Carregar" in aba_selecionada:
            self._btn_iniciar_acao.config(text="📂 Carregar Sessão", bootstyle="info")
        else:
            self._btn_iniciar_acao.config(text="✔️ Iniciar Sessão", bootstyle="success")

    def _chave_modo(self: Any, modo_edicao: bool) -> str:
        return "editar" if modo_edicao else "nova"

    def _criar_workspace_duas_colunas(
        self: Any, parent: ttk.Frame, modo_edicao: bool
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

    def _criar_conteudo_aba_nova_sessao(self: Any, parent: ttk.Frame):
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

    def _criar_conteudo_aba_editar_sessao(self: Any, parent: ttk.Frame):
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

        self._dados_checkbox_turmas_editar = self._contextos["editar"][
            "dados_checkboxes"
        ]

        grupos_atuais = set(self._sessao_ativa_info.get("grupos", []))
        for nome_turma, var, _ in self._dados_checkbox_turmas_editar:
            if nome_turma in grupos_atuais:
                var.set(True)

        self._atualizar_contador_turmas(modo_edicao=True)
        self._atualizar_contexto_grade(modo_edicao=True, aplicar_selecao=False)

    def _criar_card_detalhes_nova_sessao(
        self: Any, parent: ttk.Frame
    ) -> ttk.Labelframe:
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

        self._combobox_refeicao.current(indice_refeicao_por_hora())

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

    def _criar_card_detalhes_editar_sessao(
        self: Any, parent: ttk.Frame
    ) -> ttk.Labelframe:
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
        self: Any, parent: ttk.Frame, modo_edicao: bool
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
            topo,
            text="Carregando grade...",
            font="-size 9 -weight bold",
            bootstyle="info",
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
        self: Any, parent: ttk.Frame, modo_edicao: bool
    ) -> ttk.Labelframe:
        """Card direito com busca, atalhos rápidos, grid de checkboxes e contador."""
        ctx = self._contextos[self._chave_modo(modo_edicao)]
        card = ttk.Labelframe(
            parent, text="🎟️ Turmas e Categorias Participantes", padding=12
        )
        card.columnconfigure(0, weight=1)
        card.rowconfigure(2, weight=1)

        frame_busca = ttk.Frame(card)
        frame_busca.grid(row=0, column=0, sticky=EW, pady=(0, 8))
        frame_busca.columnconfigure(1, weight=1)

        ttk.Label(frame_busca, text="🔍 Buscar:", font="-weight bold").grid(
            row=0, column=0, sticky=W, padx=(0, 6)
        )
        ent_busca = ttk.Entry(frame_busca, textvariable=ctx["var_busca"])
        ent_busca.grid(row=0, column=1, sticky=EW)
        ent_busca.bind("<KeyRelease>", lambda _e: self._filtrar_checkboxes(modo_edicao))

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

        frame_atalhos = ttk.Frame(card)
        frame_atalhos.grid(row=1, column=0, sticky=EW, pady=(0, 8))
        frame_atalhos.columnconfigure((0, 1, 2), weight=1)

        atalhos = [
            (
                "🕒 Grade do Dia",
                lambda: self._ao_selecionar_grade_do_dia(modo_edicao),
                "success-outline",
            ),
            (
                "📋 Com Reserva",
                lambda: self._ao_selecionar_com_reserva(modo_edicao),
                "primary-outline",
            ),
            (
                "🔗 Integrado",
                lambda: self._ao_selecionar_integral(modo_edicao),
                "info-outline",
            ),
            (
                "📚 Outros",
                lambda: self._ao_selecionar_outros(modo_edicao),
                "info-outline",
            ),
            (
                "🔄 Inverter",
                lambda: self._ao_inverter_turmas(modo_edicao),
                "secondary-outline",
            ),
            (
                "⚪ Limpar",
                lambda: self._ao_limpar_turmas(modo_edicao),
                "secondary-outline",
            ),
        ]
        for idx, (texto, cmd, estilo) in enumerate(atalhos):
            ttk.Button(frame_atalhos, text=texto, command=cmd, bootstyle=estilo).grid(
                row=idx // 3, column=idx % 3, sticky=EW, padx=2, pady=2
            )

        frame_checks = self._criar_checkboxes_turmas(card, modo_edicao=modo_edicao)
        frame_checks.grid(row=2, column=0, sticky=NSEW)

        return card

    def _criar_checkboxes_turmas(
        self: Any, master: tk.Widget, modo_edicao: bool
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
                row=row_base,
                column=0,
                columnspan=num_cols,
                sticky=EW,
                padx=8,
                pady=(8, 4),
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

    def _criar_conteudo_aba_carregar_sessao(self: Any, parent: ttk.Frame):
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

    def _criar_secao_botoes_principais(self: Any, parent: tk.Widget) -> ttk.Frame:
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
            frame,
            text="❌ Cancelar",
            command=self._ao_fechar,
            bootstyle="danger-outline",
        ).grid(row=0, column=1, sticky=E, padx=6)
        self._btn_iniciar_acao = ttk.Button(
            frame, text="✔️ Iniciar Sessão", command=self._ao_ok, bootstyle="success"
        )
        self._btn_iniciar_acao.grid(row=0, column=2, sticky=E)

        return frame
