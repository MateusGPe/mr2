# ----------------------------------------------------------------------------
# Arquivo: registro/gui/painel/abas/aba_dashboard.py (Aba de Dashboard)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

import traceback
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, EW, HORIZONTAL, LEFT, NSEW, RIGHT, W, X

from registro.gui.comum.controles.rounded_button import RoundedButton
from registro.gui.comum.controles.treeview_simples import TreeviewSimples


class AbaDashboard(ttk.Frame):
    def __init__(self, parent, fachada_nucleo):
        super().__init__(parent)
        self.fachada_nucleo = fachada_nucleo
        self._criar_widgets()
        self._carregar_estatisticas()

    def _criar_widgets(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # -----------------------------
        # Cabeçalho com botão Atualizar
        # -----------------------------
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=X, padx=15, pady=(10, 5))

        info_header = ttk.Frame(header_frame)
        info_header.pack(side=LEFT, fill=X, expand=True)

        ttk.Label(
            info_header,
            text="📊 Painel Administrativo & Estatísticas",
            font=("Segoe UI", 20, "bold"),
            bootstyle="primary",
        ).pack(anchor=W)

        ttk.Label(
            info_header,
            text="Visão analítica em tempo real de alunos, turmas, reservas e consumo do refeitório.",
            font=("Segoe UI", 11),
            bootstyle="secondary",
        ).pack(anchor=W, pady=(2, 0))

        RoundedButton(
            header_frame,
            text="🔄 Atualizar Dados",
            command=self._carregar_estatisticas,
            bootstyle="primary-outline",
        ).pack(side=RIGHT, padx=5)

        ttk.Separator(self, orient=HORIZONTAL).pack(fill=X, padx=15, pady=10)

        # -----------------------------
        # Cards Executivos (Linha 1)
        # -----------------------------
        stats_frame = ttk.Frame(self)
        stats_frame.pack(fill=X, padx=15, pady=5)
        stats_frame.columnconfigure((0, 1, 2, 3), weight=1)

        (
            self.card_alunos,
            self.lbl_alunos_val,
            self.lbl_alunos_sub,
        ) = self._criar_stat_card(
            stats_frame, 0, "Alunos Ativos", "0", "0 inativos", "success"
        )
        (
            self.card_turmas,
            self.lbl_turmas_val,
            self.lbl_turmas_sub,
        ) = self._criar_stat_card(
            stats_frame, 1, "Turmas Ativas", "0", "0 total", "primary"
        )
        (
            self.card_reservas,
            self.lbl_reservas_val,
            self.lbl_reservas_sub,
        ) = self._criar_stat_card(
            stats_frame, 2, "Reservas Hoje", "0", "0 ativas total", "info"
        )
        (
            self.card_consumos,
            self.lbl_consumos_val,
            self.lbl_consumos_sub,
        ) = self._criar_stat_card(
            stats_frame, 3, "Consumos Hoje", "0", "0 ontem", "warning"
        )

        # -----------------------------
        # Seção Analítica (Linha 2 - Lado a Lado)
        # -----------------------------
        details_frame = ttk.Frame(self)
        details_frame.pack(fill=BOTH, expand=True, padx=15, pady=10)
        details_frame.columnconfigure(0, weight=3)
        details_frame.columnconfigure(1, weight=2)
        details_frame.rowconfigure(0, weight=1)

        # Tabela: Distribuição por Turmas
        turmas_frame = ttk.Labelframe(
            details_frame, text="🏫 Visão Consolidada por Turma", padding=10
        )
        turmas_frame.grid(row=0, column=0, sticky=NSEW, padx=(0, 5))

        self.table_turmas = TreeviewSimples(
            master=turmas_frame,
            dados_colunas=[
                {"text": "Turma", "stretch": True},
                {"text": "Total Alunos", "width": 90},
                {"text": "Reservas Hoje", "width": 100},
                {"text": "Consumos Hoje", "width": 100},
            ],
            height=10,
            header_bootstyle="primary",
            select_bootstyle="primary",
            enable_hover=True,
        )
        self.table_turmas.pack(fill=BOTH, expand=True)

        # Tabela: Distribuição de Pratos
        pratos_frame = ttk.Labelframe(
            details_frame, text="🍽️ Distribuição de Pratos (Hoje)", padding=10
        )
        pratos_frame.grid(row=0, column=1, sticky=NSEW, padx=(5, 0))

        self.table_pratos = TreeviewSimples(
            master=pratos_frame,
            dados_colunas=[
                {"text": "Opção / Prato", "stretch": True},
                {"text": "Quantidade", "width": 100},
            ],
            height=10,
            header_bootstyle="info",
            select_bootstyle="info",
            enable_hover=True,
        )
        self.table_pratos.pack(fill=BOTH, expand=True)

    def _criar_stat_card(self, parent, column, label, value, subtext, style):
        card = ttk.Frame(parent, padding=15, bootstyle=style)
        card.grid(row=0, column=column, sticky=NSEW, padx=5, pady=5)
        card.columnconfigure(0, weight=1)

        value_label = ttk.Label(
            card,
            text=value,
            font=("Segoe UI", 28, "bold"),
            bootstyle=f"@{style}",
        )
        value_label.grid(row=0, column=0, sticky="w")

        label_text = ttk.Label(
            card, text=label, font=("Segoe UI", 12, "bold"), bootstyle=f"@{style}"
        )
        label_text.grid(row=1, column=0, sticky="w")

        sub_label = ttk.Label(
            card, text=subtext, font=("Segoe UI", 9), bootstyle=f"@{style}"
        )
        sub_label.grid(row=2, column=0, sticky="w", pady=(3, 0))

        return card, value_label, sub_label

    def _carregar_estatisticas(self):
        try:
            stats = self.fachada_nucleo.obter_estatisticas_dashboard()

            # Card Alunos
            alunos_ativos = stats.get("alunos_ativos", 0)
            alunos_inativos = stats.get("alunos_inativos", 0)
            self.lbl_alunos_val.configure(text=str(alunos_ativos))
            self.lbl_alunos_sub.configure(text=f"{alunos_inativos} inativo(s)")

            # Card Turmas
            turmas_ativas = stats.get("grupos_ativos", 0)
            turmas_total = stats.get("grupos_total", 0)
            self.lbl_turmas_val.configure(text=str(turmas_ativas))
            self.lbl_turmas_sub.configure(text=f"{turmas_total} cadastrada(s)")

            # Card Reservas
            reservas_hoje = stats.get("reservas_hoje", 0)
            reservas_total = stats.get("reservas_total", 0)
            self.lbl_reservas_val.configure(text=str(reservas_hoje))
            self.lbl_reservas_sub.configure(text=f"{reservas_total} ativas no total")

            # Card Consumos
            consumos_hoje = stats.get("consumos_hoje", 0)
            consumos_ontem = stats.get("consumo_ontem", 0)
            self.lbl_consumos_val.configure(text=str(consumos_hoje))
            self.lbl_consumos_sub.configure(text=f"{consumos_ontem} ontem | {stats.get('consumos_total', 0)} total")

            # Tabela Turmas
            dist_turmas = stats.get("distribuicao_turmas", [])
            dados_t = [
                (
                    item["turma"],
                    item["total_alunos"],
                    item["reservas_hoje"],
                    item["consumos_hoje"],
                )
                for item in dist_turmas
            ]
            self.table_turmas.construir_dados_tabela(dados_t)

            # Tabela Pratos
            dist_pratos = stats.get("distribuicao_pratos", {})
            dados_p = [
                (prato, qtd)
                for prato, qtd in sorted(dist_pratos.items(), key=lambda x: x[1], reverse=True)
            ]
            self.table_pratos.construir_dados_tabela(dados_p)

        except Exception:
            traceback.print_exc()
