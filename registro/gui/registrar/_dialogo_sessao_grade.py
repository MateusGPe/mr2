# ----------------------------------------------------------------------------
# Arquivo: registro/gui/registrar/_dialogo_sessao_grade.py (Grade e Turmas)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""Mixin de integração com grade de horários, reservas e seleção de turmas."""

import tkinter as tk
from typing import Any, Callable, Dict, List, Optional, Tuple

import ttkbootstrap as ttk
from ttkbootstrap import ScrolledFrame
from ttkbootstrap.dialogs import Messagebox

from registro.gui.comum.utils import capitalizar
from registro.gui.registrar.dialogo_sessao_logica import (
    MAPA_NOMES_DIAS,
    extrair_grupos_reservas,
)
from registro.nucleo.config_service import obter_turmas_integrado


class _DialogoSessaoGradeMixin:
    """Gerencia grade horária, status de reservas e filtros/atalhos de turmas."""

    def _atualizar_contexto_grade(
        self: Any, modo_edicao: bool, aplicar_selecao: bool = False
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
                turmas_grade_norm = {
                    t.strip().lower() for t in turmas_grade if t and str(t).strip()
                }
                ctx["slot_selecionado_idx"] = None
                self._definir_checkboxes_turmas(
                    lambda n, _v: n.strip().lower() in turmas_grade_norm,
                    modo_edicao=modo_edicao,
                )
                self._renderizar_slots_grade(modo_edicao, slots)

    def _renderizar_slots_grade(
        self: Any, modo_edicao: bool, slots: List[Dict[str, Any]]
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

    def _ao_clicar_slot_grade(self: Any, modo_edicao: bool, idx: int):
        """Filtra/marca exclusivamente as turmas do horário clicado na grade."""
        ctx = self._contextos[self._chave_modo(modo_edicao)]
        dia_semana = self._obter_dia_semana_contexto(modo_edicao)
        refeicao = self._obter_refeicao_contexto(modo_edicao)
        slots = self._obter_slots_grade(dia_semana, refeicao)
        if not (0 <= idx < len(slots)):
            return

        ctx["slot_selecionado_idx"] = idx
        grupos_slot = self._expandir_grupos_slot(slots[idx])
        grupos_slot_norm = {
            g.strip().lower() for g in grupos_slot if g and str(g).strip()
        }
        self._definir_checkboxes_turmas(
            lambda n, _v: n.strip().lower() in grupos_slot_norm, modo_edicao=modo_edicao
        )
        self._renderizar_slots_grade(modo_edicao, slots)

    def _atualizar_status_reservas(self: Any, modo_edicao: bool):
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

    def _filtrar_checkboxes(self: Any, modo_edicao: bool):
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

    def _limpar_busca_turmas(self: Any, modo_edicao: bool):
        ctx = self._contextos[self._chave_modo(modo_edicao)]
        ctx["var_busca"].set("")
        self._filtrar_checkboxes(modo_edicao)

    def _atualizar_contador_turmas(self: Any, modo_edicao: bool):
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

    def _ao_selecionar_grade_do_dia(self: Any, modo_edicao: bool = False):
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
            turmas_grade_norm = {
                t.strip().lower() for t in turmas_grade if t and str(t).strip()
            }
            self._definir_checkboxes_turmas(
                lambda n, _v: n.strip().lower() in turmas_grade_norm,
                modo_edicao=modo_edicao,
            )
        else:
            Messagebox.show_info(
                f"Nenhuma turma prevista na grade para {capitalizar(refeicao)} na {MAPA_NOMES_DIAS.get(dia_semana, capitalizar(dia_semana))}.",
                "Grade de Horários",
                parent=self,
            )

    def _ao_selecionar_com_reserva(self: Any, modo_edicao: bool = False):
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

        grupos_com_reserva = extrair_grupos_reservas(reservas)
        if not grupos_com_reserva:
            Messagebox.show_info(
                "As reservas encontradas não possuem turmas ou categorias vinculadas.",
                "Sem Turmas nas Reservas",
                parent=self,
            )
            return

        self._limpar_slot_selecionado(modo_edicao)
        grupos_norm = {
            g.strip().lower() for g in grupos_com_reserva if g and str(g).strip()
        }
        self._definir_checkboxes_turmas(
            lambda n, _v: n.strip().lower() in grupos_norm, modo_edicao=modo_edicao
        )

    def _limpar_slot_selecionado(self: Any, modo_edicao: bool):
        ctx = self._contextos.get(self._chave_modo(modo_edicao))
        if ctx and ctx["slot_selecionado_idx"] is not None:
            ctx["slot_selecionado_idx"] = None
            dia = self._obter_dia_semana_contexto(modo_edicao)
            ref = self._obter_refeicao_contexto(modo_edicao)
            self._renderizar_slots_grade(modo_edicao, self._obter_slots_grade(dia, ref))

    def _ao_limpar_turmas(self: Any, modo_edicao: bool = False):
        self._limpar_slot_selecionado(modo_edicao)
        self._definir_checkboxes_turmas(lambda _n, _v: False, modo_edicao=modo_edicao)

    def _ao_selecionar_integral(self: Any, modo_edicao: bool = False):
        self._limpar_slot_selecionado(modo_edicao)
        turmas_integrado = set(obter_turmas_integrado())
        self._definir_checkboxes_turmas(
            lambda n, _v: n in turmas_integrado, modo_edicao=modo_edicao
        )

    def _ao_selecionar_outros(self: Any, modo_edicao: bool = False):
        self._limpar_slot_selecionado(modo_edicao)
        turmas_integrado = set(obter_turmas_integrado())
        self._definir_checkboxes_turmas(
            lambda n, _v: n not in turmas_integrado, modo_edicao=modo_edicao
        )

    def _ao_inverter_turmas(self: Any, modo_edicao: bool = False):
        self._limpar_slot_selecionado(modo_edicao)
        self._definir_checkboxes_turmas(
            lambda _n, v: not v.get(), modo_edicao=modo_edicao
        )

    def _obter_dados_checkboxes_ativos(
        self: Any,
    ) -> List[Tuple[str, tk.BooleanVar, ttk.Checkbutton]]:
        """Retorna os dados dos checkboxes da aba atualmente selecionada."""
        if self._notebook:
            texto = self._notebook.tab(self._notebook.select(), "text")
            if "Editar" in texto:
                return self._dados_checkbox_turmas_editar
        return self._dados_checkbox_turmas

    def _definir_checkboxes_turmas(
        self: Any,
        condicao: Callable[[str, tk.BooleanVar], bool],
        modo_edicao: bool = False,
    ):
        """Aplica uma condição a todos os checkboxes de turmas e atualiza o contador."""
        if modo_edicao:
            dados = self._dados_checkbox_turmas_editar
        else:
            dados = self._dados_checkbox_turmas or self._obter_dados_checkboxes_ativos()

        for nome, var, _ in dados:
            var.set(condicao(nome, var))

        self._atualizar_contador_turmas(modo_edicao)
