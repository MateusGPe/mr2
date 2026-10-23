# ----------------------------------------------------------------------------
# Arquivo: registro/gui/autoatendimento/dashboard.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Painel AbaDashboard para monitoramento em tempo real da sessão no Autoatendimento.
Apresenta cartões KPI, taxas de adesão, distribuição por prato/turma e métricas de fluxo.
"""

import logging
import tkinter as tk
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple

import ttkbootstrap as ttk
from ttkbootstrap.constants import HORIZONTAL, LEFT, X
from ttkbootstrap.dialogs import Messagebox

if TYPE_CHECKING:
    from registro.nucleo.facade import FachadaRegistro

logger = logging.getLogger(__name__)


class AbaDashboard(ttk.Frame):
    """
    Painel avançado com estatísticas consolidadas e métricas em tempo real
    da sessão de autoatendimento.
    """

    def __init__(
        self,
        master: tk.Widget,
        fachada: "FachadaRegistro",
        id_sessao: Optional[int],
        voltar_callback: Optional[Callable[[], None]] = None,
        abrir_controles_callback: Optional[Callable[..., None]] = None,
        navegar_callback: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(master, padding=(16, 12))
        self.fachada = fachada
        self.id_sessao = id_sessao
        self.voltar_callback = voltar_callback
        self.abrir_controles_callback = abrir_controles_callback
        self.navegar_callback = navegar_callback

        self.rowconfigure(1, weight=0)  # Linha dos KPI Cards
        self.rowconfigure(2, weight=1)  # Linha das Análises e Distribuições
        self.columnconfigure(0, weight=1)

        self._construir_interface()
        self.atualizar_dados()

    def _construir_interface(self):
        """Constrói a interface com navegação, cards KPI e painéis analíticos."""
        # --- Barra Superior de Navegação ---
        frame_topo = ttk.Frame(self)
        frame_topo.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        frame_topo.columnconfigure(1, weight=1)

        frame_nav_esq = ttk.Frame(frame_topo)
        frame_nav_esq.grid(row=0, column=0, sticky="w")

        if self.voltar_callback:
            ttk.Button(
                frame_nav_esq,
                text=" ⬅ Voltar ao Totem ",
                command=self.voltar_callback,
                bootstyle="primary",
                padding=(10, 6),
            ).pack(side=LEFT, padx=(0, 6))

        if self.navegar_callback:
            ttk.Button(
                frame_nav_esq,
                text=" 📋 Ver Registros (CRUD) ",
                command=lambda: self.navegar_callback("consumos"),
                bootstyle="info-outline",
                padding=(10, 6),
            ).pack(side=LEFT)

        ttk.Label(
            frame_topo,
            text="📊 Dashboard & Estatísticas da Sessão",
            font=("Segoe UI", 18, "bold"),
            anchor="center",
        ).grid(row=0, column=1, sticky="ew")

        frame_nav_dir = ttk.Frame(frame_topo)
        frame_nav_dir.grid(row=0, column=2, sticky="e")

        ttk.Button(
            frame_nav_dir,
            text=" 🔄 Atualizar ",
            command=self.atualizar_dados,
            bootstyle="secondary-outline",
            padding=(8, 6),
        ).pack(side=LEFT, padx=(0, 6))

        if self.abrir_controles_callback:
            btn_ctrl = ttk.Button(
                frame_nav_dir,
                text=" ⚙️ Controles ",
                bootstyle="secondary",
                padding=(8, 6),
            )
            btn_ctrl.config(
                command=lambda b=btn_ctrl: self.abrir_controles_callback(widget=b)
            )
            btn_ctrl.pack(side=LEFT)

        # --- Linha 1: Cards KPI Principais ---
        frame_kpis = ttk.Frame(self)
        frame_kpis.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        for col in range(5):
            frame_kpis.columnconfigure(col, weight=1)

        # 1. Total Consumos
        card_total = ttk.Frame(frame_kpis, bootstyle="primary", padding=(12, 12))
        card_total.grid(row=0, column=0, sticky="nsew", padx=4)
        ttk.Label(
            card_total,
            text="Refeições Servidas",
            font=("Segoe UI", 10),
            bootstyle="@primary",
        ).pack(anchor="center")
        self.lbl_total_consumos = ttk.Label(
            card_total,
            text="0",
            font=("Segoe UI", 36, "bold"),
            bootstyle="@primary",
        )
        self.lbl_total_consumos.pack(expand=True)
        self.lbl_total_sub = ttk.Label(
            card_total,
            text="Atendimentos registrados",
            font=("Segoe UI", 8),
            bootstyle="@primary",
        )
        self.lbl_total_sub.pack(anchor="center")

        # 2. Restantes
        card_rest = ttk.Frame(frame_kpis, bootstyle="warning", padding=(12, 12))
        card_rest.grid(row=0, column=1, sticky="nsew", padx=4)
        ttk.Label(
            card_rest,
            text="Alunos Restantes",
            font=("Segoe UI", 10),
            bootstyle="@warning",
        ).pack(anchor="center")
        self.lbl_restantes = ttk.Label(
            card_rest,
            text="0",
            font=("Segoe UI", 36, "bold"),
            bootstyle="@warning",
        )
        self.lbl_restantes.pack(expand=True)
        self.lbl_restantes_sub = ttk.Label(
            card_rest,
            text="Aguardando atendimento",
            font=("Segoe UI", 8),
            bootstyle="@warning",
        )
        self.lbl_restantes_sub.pack(anchor="center")

        # 3. Taxa de Adesão
        card_adesao = ttk.Frame(
            frame_kpis, bootstyle="success", padding=(12, 12)
        )
        card_adesao.grid(row=0, column=2, sticky="nsew", padx=4)
        ttk.Label(
            card_adesao,
            text="Taxa de Adesão",
            font=("Segoe UI", 10),
            bootstyle="@success",
        ).pack(anchor="center")
        self.lbl_adesao = ttk.Label(
            card_adesao,
            text="0%",
            font=("Segoe UI", 36, "bold"),
            bootstyle="@success",
        )
        self.lbl_adesao.pack(expand=True)
        self.progress_adesao = ttk.Progressbar(
            card_adesao, value=0, maximum=100, bootstyle="success-striped"
        )
        self.progress_adesao.pack(fill=X, padx=10, pady=(2, 4))
        self.lbl_esperados = ttk.Label(
            card_adesao,
            text="0 de 0 esperados",
            font=("Segoe UI", 8),
            bootstyle="@success",
        )
        self.lbl_esperados.pack(anchor="center")

        # 4. Reservas vs Avulsos
        card_reserva = ttk.Frame(frame_kpis, bootstyle="info", padding=(12, 12))
        card_reserva.grid(row=0, column=3, sticky="nsew", padx=4)
        ttk.Label(
            card_reserva,
            text="Com Reserva / Avulso",
            font=("Segoe UI", 10),
            bootstyle="@info",
        ).pack(anchor="center")
        self.lbl_reserva_info = ttk.Label(
            card_reserva,
            text="0 / 0",
            font=("Segoe UI", 28, "bold"),
            bootstyle="@info",
        )
        self.lbl_reserva_info.pack(expand=True)
        self.lbl_reserva_sub = ttk.Label(
            card_reserva,
            text="Planejados vs Exceções",
            font=("Segoe UI", 8),
            bootstyle="@info",
        )
        self.lbl_reserva_sub.pack(anchor="center")

        # 5. Último Atendimento
        card_ultimo = ttk.Frame(
            frame_kpis, bootstyle="secondary", padding=(12, 12)
        )
        card_ultimo.grid(row=0, column=4, sticky="nsew", padx=4)
        ttk.Label(
            card_ultimo,
            text="Último Registro",
            font=("Segoe UI", 10),
            bootstyle="@secondary",
        ).pack(anchor="center")
        self.lbl_ultimo_consumo_nome = ttk.Label(
            card_ultimo,
            text="--",
            font=("Segoe UI", 13, "bold"),
            bootstyle="@secondary",
            wraplength=180,
            anchor="center",
            justify="center",
        )
        self.lbl_ultimo_consumo_nome.pack(expand=True)
        self.lbl_ultimo_consumo_hora = ttk.Label(
            card_ultimo, text="", font=("Segoe UI", 11), bootstyle="@secondary"
        )
        self.lbl_ultimo_consumo_hora.pack(anchor="center")

        # --- Linha 2: Painéis de Distribuição e Desempenho Analítico ---
        frame_analises = ttk.Frame(self)
        frame_analises.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        frame_analises.columnconfigure((0, 1, 2), weight=1)
        frame_analises.rowconfigure(0, weight=1)

        # Painel A: Distribuição por Prato
        self.card_pratos = ttk.LabelFrame(
            frame_analises,
            text=" 🍽️ Distribuição por Cardápio / Prato ",
            padding=12,
        )
        self.card_pratos.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.card_pratos.rowconfigure(0, weight=1)
        self.card_pratos.columnconfigure(0, weight=1)

        self.frame_lista_pratos = ttk.Frame(self.card_pratos)
        self.frame_lista_pratos.grid(row=0, column=0, sticky="nsew")
        self.frame_lista_pratos.columnconfigure(1, weight=1)

        # Painel B: Top Turmas
        self.card_turmas = ttk.LabelFrame(
            frame_analises, text=" 👥 Top Turmas Atendidas ", padding=12
        )
        self.card_turmas.grid(row=0, column=1, sticky="nsew", padx=4)
        self.card_turmas.rowconfigure(0, weight=1)
        self.card_turmas.columnconfigure(0, weight=1)

        self.frame_lista_turmas = ttk.Frame(self.card_turmas)
        self.frame_lista_turmas.grid(row=0, column=0, sticky="nsew")
        self.frame_lista_turmas.columnconfigure(1, weight=1)

        # Painel C: Fluxo e Performance
        self.card_fluxo = ttk.LabelFrame(
            frame_analises,
            text=" ⏱️ Ritmo de Atendimento & Horários ",
            padding=12,
        )
        self.card_fluxo.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        self.card_fluxo.rowconfigure(4, weight=1)
        self.card_fluxo.columnconfigure(0, weight=1)

        self.lbl_pico_horario = ttk.Label(
            self.card_fluxo,
            text="🔥 Horário de Pico: --",
            font=("Segoe UI", 10, "bold"),
            bootstyle="primary",
        )
        self.lbl_pico_horario.grid(row=0, column=0, sticky="w", pady=2)

        self.lbl_velocidade = ttk.Label(
            self.card_fluxo,
            text="⚡ Velocidade: -- atendimentos/minuto",
            font=("Segoe UI", 9),
        )
        self.lbl_velocidade.grid(row=1, column=0, sticky="w", pady=2)

        self.lbl_primeiro_consumo = ttk.Label(
            self.card_fluxo,
            text="🚩 Início da Fila: --",
            font=("Segoe UI", 9),
            bootstyle="secondary",
        )
        self.lbl_primeiro_consumo.grid(row=2, column=0, sticky="w", pady=2)

        ttk.Separator(self.card_fluxo, orient=HORIZONTAL).grid(
            row=3, column=0, sticky="ew", pady=6
        )

        ttk.Label(
            self.card_fluxo,
            text="Faixas de Horário (Intervalos):",
            font=("Segoe UI", 9, "bold"),
        ).grid(row=4, column=0, sticky="w", pady=(0, 4))

        self.frame_lista_faixas = ttk.Frame(self.card_fluxo)
        self.frame_lista_faixas.grid(row=5, column=0, sticky="nsew")
        self.frame_lista_faixas.columnconfigure(1, weight=1)

        # --- Rodapé da Sessão ---
        frame_rodape = ttk.Frame(self)
        frame_rodape.grid(row=3, column=0, sticky="ew")
        frame_rodape.columnconfigure(0, weight=1)

        self.lbl_info_sessao = ttk.Label(
            frame_rodape,
            text="Sessão não iniciada",
            font=("Segoe UI", 9),
            bootstyle="secondary",
        )
        self.lbl_info_sessao.grid(row=0, column=0, sticky="w")

        ttk.Button(
            frame_rodape,
            text=" 📥 Exportar Relatório de Sessão (XLSX) ",
            command=self._exportar_relatorio,
            bootstyle="secondary-outline",
            padding=(10, 4),
        ).grid(row=0, column=1, sticky="e")

    def definir_sessao(self, id_sessao: Optional[int]):
        """Atualiza a sessão ativa exibida no dashboard."""
        self.id_sessao = id_sessao
        self.atualizar_dados()

    def atualizar_dados(
        self, ultimo_consumo: Optional[Tuple[str, ...]] = None
    ):
        """Calcula e atualiza os contadores, gráficos e distribuições no dashboard."""
        if (
            not self.id_sessao
            or not self.fachada
            or not self.fachada.id_sessao_ativa
        ):
            self.lbl_total_consumos.config(text="0")
            self.lbl_restantes.config(text="0")
            self.lbl_adesao.config(text="0%")
            self.progress_adesao.config(value=0)
            self.lbl_esperados.config(text="Sem Sessão Ativa")
            self.lbl_reserva_info.config(text="0 / 0")
            self.lbl_ultimo_consumo_nome.config(text="Sem Sessão")
            self.lbl_ultimo_consumo_hora.config(text="")
            self.lbl_info_sessao.config(
                text="⚠️ Nenhuma sessão ativa no momento."
            )
            self._limpar_paineis_analiticos()
            return

        try:
            stats = None
            if hasattr(self.fachada, "obter_estatisticas_sessao"):
                try:
                    stats = self.fachada.obter_estatisticas_sessao(
                        self.id_sessao
                    )
                except Exception as ex_stats:
                    logger.debug(
                        "Falha em obter_estatisticas_sessao: %s", ex_stats
                    )

            if not stats:
                consumidos = self.fachada.obter_estudantes_para_sessao(
                    consumido=True
                )
                stats = {
                    "total_consumidos": len(consumidos),
                    "total_restantes": 0,
                    "total_esperado": len(consumidos),
                    "taxa_adesao": 100.0 if consumidos else 0.0,
                    "total_com_reserva": len(consumidos),
                    "total_sem_reserva": 0,
                    "distribuicao_pratos": {},
                    "distribuicao_turmas": {},
                    "distribuicao_horarios": {},
                    "horario_pico": None,
                    "primeiro_consumo": None,
                    "ultimo_consumo": None,
                    "velocidade_por_minuto": 0.0,
                }

            # Atualiza KPI Cards
            tot_cons = stats.get("total_consumidos", 0)
            tot_rest = stats.get("total_restantes", 0)
            tot_esp = stats.get("total_esperado", 0)
            taxa = stats.get("taxa_adesao", 0.0)
            c_res = stats.get("total_com_reserva", 0)
            s_res = stats.get("total_sem_reserva", 0)

            self.lbl_total_consumos.config(text=str(tot_cons))
            self.lbl_restantes.config(text=str(tot_rest))
            self.lbl_adesao.config(text=f"{taxa:.1f}%")
            self.progress_adesao.config(value=taxa)
            self.lbl_esperados.config(
                text=f"{tot_cons} de {tot_esp} esperados"
            )
            self.lbl_reserva_info.config(text=f"{c_res} / {s_res}")
            pct_res = (
                f"{(c_res / tot_cons * 100):.0f}% com reserva"
                if tot_cons > 0
                else "--"
            )
            self.lbl_reserva_sub.config(text=pct_res)

            # Último consumo
            if ultimo_consumo and len(ultimo_consumo) >= 4:
                self.lbl_ultimo_consumo_nome.config(
                    text=str(ultimo_consumo[1])
                )
                self.lbl_ultimo_consumo_hora.config(
                    text=f"às {ultimo_consumo[3]}"
                )
            else:
                uc = stats.get("ultimo_consumo")
                if uc:
                    self.lbl_ultimo_consumo_nome.config(
                        text=str(uc.get("nome", "--"))
                    )
                    self.lbl_ultimo_consumo_hora.config(
                        text=f"às {uc.get('hora_consumo', '')}"
                    )
                else:
                    self.lbl_ultimo_consumo_nome.config(text="--")
                    self.lbl_ultimo_consumo_hora.config(text="")

            # Atualiza Distribuição de Pratos
            self._atualizar_painel_pratos(
                stats.get("distribuicao_pratos", {}), tot_cons
            )

            # Atualiza Top Turmas
            self._atualizar_painel_turmas(
                stats.get("distribuicao_turmas", {}), tot_cons
            )

            # Atualiza Ritmo de Atendimento
            self._atualizar_painel_fluxo(stats)

            # Rodapé informativo da sessão
            refeicao = str(stats.get("refeicao", "Sessão")).capitalize()
            data = str(stats.get("data", ""))
            hora_prev = str(stats.get("hora_prevista", ""))
            item = str(stats.get("item_servido") or "")
            item_txt = f" • Item: {item}" if item else ""
            self.lbl_info_sessao.config(
                text=f"🍲 {refeicao} ({hora_prev}){item_txt} | 📅 Data: {data} | ID Sessão: {self.id_sessao}"
            )

        except Exception as e:
            logger.error("Erro ao atualizar dashboard analítico: %s", e)

    def _limpar_paineis_analiticos(self):
        for widget in self.frame_lista_pratos.winfo_children():
            widget.destroy()
        for widget in self.frame_lista_turmas.winfo_children():
            widget.destroy()
        for widget in self.frame_lista_faixas.winfo_children():
            widget.destroy()

    def _atualizar_painel_pratos(
        self, dist_pratos: Dict[str, int], total: int
    ):
        for widget in self.frame_lista_pratos.winfo_children():
            widget.destroy()

        if not dist_pratos:
            ttk.Label(
                self.frame_lista_pratos,
                text="Nenhum prato registrado ainda.",
                font=("Segoe UI", 9, "italic"),
                bootstyle="secondary",
            ).pack(anchor="w", pady=6)
            return

        for _idx, (prato, count) in enumerate(dist_pratos.items()):
            pct = (count / total * 100) if total > 0 else 0
            frame_item = ttk.Frame(self.frame_lista_pratos)
            frame_item.pack(fill=X, pady=3)
            frame_item.columnconfigure(1, weight=1)

            ttk.Label(
                frame_item,
                text=f"{prato}:",
                font=("Segoe UI", 9, "bold"),
                width=16,
                anchor="w",
            ).grid(row=0, column=0, sticky="w")

            prog = ttk.Progressbar(
                frame_item, value=pct, maximum=100, bootstyle="info"
            )
            prog.grid(row=0, column=1, sticky="ew", padx=6)

            ttk.Label(
                frame_item,
                text=f"{count} ({pct:.0f}%)",
                font=("Segoe UI", 9),
                width=10,
                anchor="e",
            ).grid(row=0, column=2, sticky="e")

    def _atualizar_painel_turmas(
        self, dist_turmas: Dict[str, int], _total: int
    ):
        for widget in self.frame_lista_turmas.winfo_children():
            widget.destroy()

        if not dist_turmas:
            ttk.Label(
                self.frame_lista_turmas,
                text="Nenhum atendimento por turma.",
                font=("Segoe UI", 9, "italic"),
                bootstyle="secondary",
            ).pack(anchor="w", pady=6)
            return

        top_turmas = list(dist_turmas.items())[:6]
        max_turma = top_turmas[0][1] if top_turmas else 1

        for _idx, (turma, count) in enumerate(top_turmas):
            pct_bar = (count / max_turma * 100) if max_turma > 0 else 0
            frame_item = ttk.Frame(self.frame_lista_turmas)
            frame_item.pack(fill=X, pady=3)
            frame_item.columnconfigure(1, weight=1)

            ttk.Label(
                frame_item,
                text=turma[:18],
                font=("Segoe UI", 9, "bold"),
                width=18,
                anchor="w",
            ).grid(row=0, column=0, sticky="w")

            prog = ttk.Progressbar(
                frame_item, value=pct_bar, maximum=100, bootstyle="success"
            )
            prog.grid(row=0, column=1, sticky="ew", padx=6)

            ttk.Label(
                frame_item,
                text=f"{count}",
                font=("Segoe UI", 9, "bold"),
                width=6,
                anchor="e",
            ).grid(row=0, column=2, sticky="e")

    def _atualizar_painel_fluxo(self, stats: Dict[str, Any]):
        pico = stats.get("horario_pico")
        if pico:
            self.lbl_pico_horario.config(
                text=f"🔥 Horário de Pico: {pico[0]} ({pico[1]} refeições)"
            )
        else:
            self.lbl_pico_horario.config(
                text="🔥 Horário de Pico: Em cálculo..."
            )

        vel = stats.get("velocidade_por_minuto", 0.0)
        self.lbl_velocidade.config(
            text=f"⚡ Velocidade Média: {vel:.1f} atendimentos/min"
        )

        pc = stats.get("primeiro_consumo")
        if pc:
            self.lbl_primeiro_consumo.config(
                text=f"🚩 Primeiro Atendimento: às {pc.get('hora_consumo', '')} ({pc.get('nome', '')[:20]})"
            )
        else:
            self.lbl_primeiro_consumo.config(text="🚩 Primeiro Atendimento: --")

        # Faixas de Horário
        for widget in self.frame_lista_faixas.winfo_children():
            widget.destroy()

        dist_horarios = stats.get("distribuicao_horarios", {})
        if not dist_horarios:
            ttk.Label(
                self.frame_lista_faixas,
                text="Sem dados temporais disponíveis.",
                font=("Segoe UI", 8, "italic"),
                bootstyle="secondary",
            ).pack(anchor="w")
            return

        for faixa, qtd in list(dist_horarios.items())[-5:]:
            f_row = ttk.Frame(self.frame_lista_faixas)
            f_row.pack(fill=X, pady=1)
            f_row.columnconfigure(1, weight=1)

            ttk.Label(
                f_row, text=faixa, font=("Segoe UI", 8), width=18, anchor="w"
            ).grid(row=0, column=0, sticky="w")
            ttk.Label(
                f_row,
                text=f"{qtd} atendimentos",
                font=("Segoe UI", 8, "bold"),
                anchor="e",
            ).grid(row=0, column=1, sticky="e")

    def _exportar_relatorio(self):
        """Exporta os dados de consumo e resumo da sessão para arquivo Excel."""
        if not self.id_sessao or not self.fachada:
            Messagebox.show_warning(
                "Aviso", "Nenhuma sessão ativa para exportar.", parent=self
            )
            return

        try:
            caminho = self.fachada.exportar_sessao_para_xlsx(self.id_sessao)
            Messagebox.show_info(
                "Exportação Concluída",
                f"Relatório exportado com sucesso para:\n{caminho}",
                parent=self,
            )
        except Exception as e:
            logger.exception("Erro ao exportar planilha de sessão: %s", e)
            Messagebox.show_error(
                "Erro na Exportação",
                f"Não foi possível exportar:\n{e}",
                parent=self,
            )
