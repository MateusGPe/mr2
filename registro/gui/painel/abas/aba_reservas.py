# ----------------------------------------------------------------------------
# Arquivo: registro/gui/painel/abas/aba_reservas.py (Aba de Reservas)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

import tkinter as tk
from tkinter import filedialog
import traceback
from datetime import datetime
from pathlib import Path

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, EW, LEFT, NSEW, RIGHT, W, X
from ttkbootstrap.dialogs import Messagebox

from registro.gui.comum.controles.rounded_button import RoundedButton
from registro.gui.painel.dialogos import ReservaDialog
from registro.gui.comum.controles.treeview_simples import TreeviewSimples


class AbaReservas(ttk.Frame):
    def __init__(self, parent, fachada_nucleo):
        super().__init__(parent)
        self.fachada_nucleo = fachada_nucleo
        self.dados_reservas_atuais = []
        self._criar_widgets()
        self._carregar_reservas()

    def _criar_widgets(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top_panel = ttk.Frame(self)
        top_panel.grid(row=0, column=0, sticky=EW, pady=(0, 10))
        top_panel.columnconfigure(1, weight=1)

        # -----------------------------
        # Barra de Ações
        # -----------------------------
        actions_frame = ttk.Frame(top_panel)
        actions_frame.grid(row=0, column=0, sticky=W, padx=(0, 10))

        RoundedButton(
            actions_frame,
            text="+ Nova Reserva",
            command=self._adicionar_reserva,
            bootstyle="success",
        ).pack(side=LEFT, padx=(0, 5))

        self.btn_edit_reserva = RoundedButton(
            actions_frame,
            text="Editar",
            command=self._editar_reserva,
            state="disabled",
        )
        self.btn_edit_reserva.pack(side=LEFT, padx=5)

        self.btn_toggle_cancel = RoundedButton(
            actions_frame,
            text="Cancelar / Reativar",
            command=self._alternar_cancelamento_reserva,
            bootstyle="warning",
            state="disabled",
        )
        self.btn_toggle_cancel.pack(side=LEFT, padx=5)

        self.btn_delete_reserva = RoundedButton(
            actions_frame,
            text="Excluir",
            command=self._deletar_reserva,
            bootstyle="danger",
            state="disabled",
        )
        self.btn_delete_reserva.pack(side=LEFT, padx=5)

        # Menu de Exportação
        self.btn_export = ttk.Menubutton(
            actions_frame,
            text="Exportar ▾",
            bootstyle="secondary-outline",
        )
        menu_exp = tk.Menu(self.btn_export, tearoff=0)
        menu_exp.add_command(
            label="Exportar Reservas (Excel .xlsx)",
            command=lambda: self._exportar_reservas("xlsx"),
        )
        menu_exp.add_command(
            label="Exportar Reservas (CSV .csv)",
            command=lambda: self._exportar_reservas("csv"),
        )
        self.btn_export["menu"] = menu_exp
        self.btn_export.pack(side=LEFT, padx=10)

        # -----------------------------
        # Painel de Filtros
        # -----------------------------
        filter_frame = ttk.Frame(top_panel)
        filter_frame.grid(row=0, column=1, sticky=EW)

        # Busca Textual por Aluno
        ttk.Label(filter_frame, text="Aluno:").pack(side=LEFT, padx=(5, 3))
        self.search_aluno_var = tk.StringVar()
        self.search_aluno_var.trace_add("write", lambda *_: self._filtrar_reservas())
        self.search_entry = ttk.Entry(filter_frame, textvariable=self.search_aluno_var, width=15)
        self.search_entry.pack(side=LEFT, padx=3)

        # Filtro por Data
        ttk.Label(filter_frame, text="Data:").pack(side=LEFT, padx=(10, 3))
        datas_existentes = self.fachada_nucleo.listar_datas_reservas()
        valores_data = ["Todas"] + datas_existentes
        self.var_data = tk.StringVar(value=datas_existentes[0] if datas_existentes else "Todas")
        self.cbo_data = ttk.Combobox(
            filter_frame,
            textvariable=self.var_data,
            values=valores_data,
            state="readonly",
            width=12,
            bootstyle="info",
        )
        self.cbo_data.pack(side=LEFT, padx=3)
        self.cbo_data.bind("<<ComboboxSelected>>", lambda *_: self._filtrar_reservas())

        # Filtro por Turma
        ttk.Label(filter_frame, text="Turma:").pack(side=LEFT, padx=(10, 3))
        self.filter_turma_combobox = ttk.Combobox(
            filter_frame,
            values=["Todas"] + self._get_grupos_disponiveis(),
            state="readonly",
            width=18,
        )
        self.filter_turma_combobox.set("Todas")
        self.filter_turma_combobox.pack(side=LEFT, padx=3)
        self.filter_turma_combobox.bind("<<ComboboxSelected>>", lambda *_: self._filtrar_reservas())

        # -----------------------------
        # Tabela de Reservas
        # -----------------------------
        container = ttk.Frame(self)
        container.grid(row=1, column=0, sticky=NSEW)

        self.reservas_coldata = [
            {"text": "ID", "width": 60},
            {"text": "Data", "width": 110},
            {"text": "Aluno", "stretch": True},
            {"text": "Prontuário", "width": 140},
            {"text": "Prato", "width": 130},
            {"text": "Status", "width": 100},
        ]
        self.reservas_table = TreeviewSimples(
            master=container,
            dados_colunas=self.reservas_coldata,
            height=15,
            header_bootstyle="info",
            select_bootstyle="info",
            enable_hover=True,
        )
        self.reservas_table.pack(expand=True, fill=BOTH)
        self.reservas_table.view.bind("<<TreeviewSelect>>", self._on_reserva_select)
        self.reservas_table.view.bind("<Double-1>", lambda *_: self._editar_reserva())

    def _get_dados_linha_selecionada(self):
        return self.reservas_table.obter_linha_selecionada()

    def _on_reserva_select(self, _=None):
        sel = self._get_dados_linha_selecionada()
        is_selected = bool(sel)
        self.btn_edit_reserva.configure(state="normal" if is_selected else "disabled")
        self.btn_toggle_cancel.configure(state="normal" if is_selected else "disabled")
        self.btn_delete_reserva.configure(state="normal" if is_selected else "disabled")

        if is_selected and len(sel) >= 6:
            status = sel[5]
            if status == "Cancelada":
                self.btn_toggle_cancel.configure(text="Reativar Reserva", bootstyle="success")
            else:
                self.btn_toggle_cancel.configure(text="Cancelar Reserva", bootstyle="warning")

    def _get_grupos_disponiveis(self):
        try:
            return sorted([g["nome"] for g in self.fachada_nucleo.listar_todos_os_grupos()])
        except Exception:
            return []

    def _filtrar_reservas(self, _event=None):
        filtro = {}
        data_filtro = self.var_data.get()
        if data_filtro and data_filtro != "Todas":
            filtro["data"] = data_filtro

        turma_filtro = self.filter_turma_combobox.get()
        if turma_filtro and turma_filtro != "Todas":
            filtro["grupos"] = [turma_filtro]

        termo_aluno = self.search_aluno_var.get().strip().lower()

        try:
            reservas = self.fachada_nucleo.listar_reservas(filtros=filtro if filtro else None)

            if termo_aluno:
                reservas = [
                    r for r in reservas
                    if termo_aluno in (r.get("nome_estudante") or "").lower()
                    or termo_aluno in (r.get("prontuario_estudante") or "").lower()
                ]

            self.dados_reservas_atuais = reservas
            dados = [
                (
                    r["id"],
                    r["data"],
                    r["nome_estudante"],
                    r["prontuario_estudante"],
                    r["prato"] or "Padrão",
                    "Cancelada" if r["cancelada"] else "Ativa",
                )
                for r in reservas
            ]
            self.reservas_table.construir_dados_tabela(dados)
        except Exception:
            Messagebox.show_error("Erro ao carregar reservas. Verifique o console.", "Erro")
            traceback.print_exc()
        self._on_reserva_select()

    def _carregar_reservas(self):
        try:
            datas = self.fachada_nucleo.listar_datas_reservas()
            self.cbo_data["values"] = ["Todas"] + datas
            turmas = ["Todas"] + self._get_grupos_disponiveis()
            self.filter_turma_combobox["values"] = turmas
        except Exception:
            pass
        self._filtrar_reservas()

    def _get_reserva_selecionada_id(self):
        selecionado = self._get_dados_linha_selecionada()
        return int(selecionado[0]) if selecionado else None

    def _adicionar_reserva(self):
        dialog = ReservaDialog(self, self.fachada_nucleo)
        if dialog.result:
            self._carregar_reservas()

    def _editar_reserva(self):
        reserva_id = self._get_reserva_selecionada_id()
        if not reserva_id:
            return
        dialog = ReservaDialog(self, self.fachada_nucleo, reserva_id=reserva_id)
        if dialog.result:
            self._carregar_reservas()

    def _alternar_cancelamento_reserva(self):
        reserva_id = self._get_reserva_selecionada_id()
        if not reserva_id:
            return
        sel = self._get_dados_linha_selecionada()
        status_atual = sel[5] if sel and len(sel) >= 6 else "Ativa"

        if status_atual == "Cancelada":
            self.fachada_nucleo.reativar_reserva(reserva_id)
        else:
            self.fachada_nucleo.cancelar_reserva(reserva_id)

        self._filtrar_reservas()

    def _deletar_reserva(self):
        reserva_id = self._get_reserva_selecionada_id()
        if not reserva_id:
            return

        confirmado = Messagebox.show_question(
            f"Deseja excluir definitivamente a reserva com ID {reserva_id}?",
            "Confirmar Exclusão",
        )
        if confirmado == "Yes":
            try:
                self.fachada_nucleo.deletar_reserva(reserva_id)
                self._carregar_reservas()
            except Exception as e:
                Messagebox.show_error(f"Erro ao excluir reserva: {e}", "Erro")
                traceback.print_exc()

    def _exportar_reservas(self, formato: str):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ext = ".xlsx" if formato == "xlsx" else ".csv"
            ftypes = (
                [("Excel", "*.xlsx")]
                if formato == "xlsx"
                else [("CSV", "*.csv")]
            )
            filepath = filedialog.asksaveasfilename(
                initialfile=f"export_reservas_{timestamp}",
                defaultextension=ext,
                filetypes=ftypes,
            )
            if not filepath:
                return

            export_dados = [
                {
                    "id": r["id"],
                    "data": r["data"],
                    "prontuario": r["prontuario_estudante"],
                    "nome": r["nome_estudante"],
                    "prato": r.get("prato") or "Padrão",
                    "cancelada": "Sim" if r["cancelada"] else "Não",
                }
                for r in self.dados_reservas_atuais
            ]

            if formato == "xlsx":
                self.fachada_nucleo.exportar_reservas_para_xlsx(
                    Path(filepath), reservas_dados=export_dados
                )
            else:
                self.fachada_nucleo.exportar_reservas_para_csv(
                    Path(filepath), reservas_dados=export_dados
                )

            Messagebox.show_info(f"Reservas exportadas com sucesso em:\n{filepath}", "Sucesso")
        except Exception as e:
            Messagebox.show_error(f"Falha ao exportar reservas: {e}", "Erro")
