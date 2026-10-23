# ----------------------------------------------------------------------------
# Arquivo: registro/gui/painel/abas/aba_alunos.py (Aba de Alunos)
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
from registro.gui.painel.dialogos import StudentDialog
from registro.gui.comum.controles.treeview_simples import TreeviewSimples


class AbaAlunos(ttk.Frame):
    def __init__(self, parent, fachada_nucleo):
        super().__init__(parent)
        self.fachada_nucleo = fachada_nucleo
        self.dados_alunos_atuais = []
        self._criar_widgets()
        self._carregar_alunos()

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

        btn_add = RoundedButton(
            actions_frame,
            text="+ Adicionar Aluno",
            command=self._adicionar_aluno,
            bootstyle="success",
        )
        btn_add.pack(side=LEFT, padx=(0, 5))

        self.btn_edit_aluno = RoundedButton(
            actions_frame,
            text="Editar",
            command=self._editar_aluno,
            state="disabled",
        )
        self.btn_edit_aluno.pack(side=LEFT, padx=5)

        self.btn_status_aluno = RoundedButton(
            actions_frame,
            text="Ativar / Desativar",
            command=self._alternar_status_aluno,
            bootstyle="secondary",
            state="disabled",
        )
        self.btn_status_aluno.pack(side=LEFT, padx=5)

        self.btn_delete_aluno = RoundedButton(
            actions_frame,
            text="Excluir",
            command=self._deletar_aluno,
            bootstyle="danger",
            state="disabled",
        )
        self.btn_delete_aluno.pack(side=LEFT, padx=5)

        # Menu de Exportação
        self.btn_export = ttk.Menubutton(
            actions_frame,
            text="Exportar ▾",
            bootstyle="secondary-outline",
        )
        menu_exp = tk.Menu(self.btn_export, tearoff=0)
        menu_exp.add_command(
            label="Exportar Alunos (Excel .xlsx)",
            command=lambda: self._exportar_alunos("xlsx"),
        )
        menu_exp.add_command(
            label="Exportar Alunos (CSV .csv)",
            command=lambda: self._exportar_alunos("csv"),
        )
        self.btn_export["menu"] = menu_exp
        self.btn_export.pack(side=LEFT, padx=10)

        # -----------------------------
        # Painel de Filtros
        # -----------------------------
        filter_frame = ttk.Frame(top_panel)
        filter_frame.grid(row=0, column=1, sticky=EW)

        # Busca Textual
        ttk.Label(filter_frame, text="Buscar:").pack(side=LEFT, padx=(5, 3))
        self.search_aluno_var = tk.StringVar()
        self.search_aluno_var.trace_add("write", lambda *_: self._carregar_alunos())
        self.search_entry = ttk.Entry(filter_frame, textvariable=self.search_aluno_var, width=22)
        self.search_entry.pack(side=LEFT, padx=3)

        # Filtro por Turma
        ttk.Label(filter_frame, text="Turma:").pack(side=LEFT, padx=(10, 3))
        self.filter_turma_var = tk.StringVar(value="Todas")
        self.cbo_turma = ttk.Combobox(
            filter_frame,
            textvariable=self.filter_turma_var,
            state="readonly",
            width=18,
        )
        self.cbo_turma.pack(side=LEFT, padx=3)
        self.cbo_turma.bind("<<ComboboxSelected>>", lambda *_: self._carregar_alunos())

        # Filtro por Status
        ttk.Label(filter_frame, text="Status:").pack(side=LEFT, padx=(10, 3))
        self.filter_status_var = tk.StringVar(value="Todos")
        self.cbo_status = ttk.Combobox(
            filter_frame,
            textvariable=self.filter_status_var,
            values=["Todos", "Ativos", "Inativos"],
            state="readonly",
            width=10,
        )
        self.cbo_status.pack(side=LEFT, padx=3)
        self.cbo_status.bind("<<ComboboxSelected>>", lambda *_: self._carregar_alunos())

        self._atualizar_turmas_combobox()

        # -----------------------------
        # Tabela de Alunos
        # -----------------------------
        container = ttk.Frame(self)
        container.grid(row=1, column=0, sticky=NSEW)

        self.alunos_coldata = [
            {"text": "ID", "stretch": False, "width": 60},
            {"text": "Nome", "stretch": True},
            {"text": "Prontuário", "stretch": False, "width": 150},
            {"text": "Grupos / Turmas", "stretch": True},
            {"text": "Ativo", "stretch": False, "width": 80},
        ]
        self.alunos_table = TreeviewSimples(
            master=container,
            dados_colunas=self.alunos_coldata,
            height=15,
            header_bootstyle="primary",
            select_bootstyle="primary",
            enable_hover=True,
        )
        self.alunos_table.pack(expand=True, fill=BOTH)
        self.alunos_table.view.bind("<<TreeviewSelect>>", self._on_aluno_select)
        self.alunos_table.view.bind("<Double-1>", lambda *_: self._editar_aluno())

    def _atualizar_turmas_combobox(self):
        try:
            grupos = self.fachada_nucleo.listar_todos_os_grupos()
            turmas = ["Todas"] + [g["nome"] for g in grupos]
            self.cbo_turma["values"] = turmas
            if self.filter_turma_var.get() not in turmas:
                self.filter_turma_var.set("Todas")
        except Exception:
            pass

    def _get_dados_linha_selecionada(self):
        return self.alunos_table.obter_linha_selecionada()

    def _on_aluno_select(self, _=None):
        is_selected = bool(self._get_dados_linha_selecionada())
        self.btn_edit_aluno.config(state="normal" if is_selected else "disabled")
        self.btn_status_aluno.config(state="normal" if is_selected else "disabled")
        self.btn_delete_aluno.config(state="normal" if is_selected else "disabled")

    def _carregar_alunos(self):
        try:
            self._atualizar_turmas_combobox()
            termo = self.search_aluno_var.get().strip()
            turma_nome = self.filter_turma_var.get()

            status_str = self.filter_status_var.get()
            status_ativo = None
            if status_str == "Ativos":
                status_ativo = True
            elif status_str == "Inativos":
                status_ativo = False

            alunos = self.fachada_nucleo.listar_estudantes_fuzzy(
                termo_busca=termo,
                limite=60,
                turma_nome=turma_nome,
                status_ativo=status_ativo,
            )

            self.dados_alunos_atuais = alunos
            dados = [
                (
                    aluno["id"],
                    aluno["nome"],
                    aluno["prontuario"],
                    ", ".join(aluno.get("grupos", [])),
                    "Sim" if aluno.get("ativo", False) else "Não",
                )
                for aluno in alunos
            ]
            self.alunos_table.construir_dados_tabela(dados)
        except Exception:
            Messagebox.show_error("Erro ao carregar alunos. Verifique o console.", "Erro")
            traceback.print_exc()
        self._on_aluno_select()

    def _get_aluno_selecionado_id(self):
        selecionado = self._get_dados_linha_selecionada()
        return int(selecionado[0]) if selecionado else None

    def _adicionar_aluno(self):
        dialog = StudentDialog(self, self.fachada_nucleo)
        if dialog.result:
            self._carregar_alunos()

    def _editar_aluno(self):
        aluno_id = self._get_aluno_selecionado_id()
        if not aluno_id:
            return
        dialog = StudentDialog(self, self.fachada_nucleo, student_id=aluno_id)
        if dialog.result:
            self._carregar_alunos()

    def _alternar_status_aluno(self):
        aluno_id = self._get_aluno_selecionado_id()
        if not aluno_id:
            return
        ok = self.fachada_nucleo.alternar_status_estudante(aluno_id)
        if ok:
            self._carregar_alunos()

    def _deletar_aluno(self):
        aluno_id = self._get_aluno_selecionado_id()
        if not aluno_id:
            return
        sel = self._get_dados_linha_selecionada()
        nome_aluno = sel[1] if sel else "o aluno"

        confirm = Messagebox.show_question(
            f"Deseja realmente excluir {nome_aluno}?", "Confirmar Exclusão"
        )
        if confirm != "Yes":
            return

        res = self.fachada_nucleo.deletar_estudante(aluno_id, forcar_desativacao=False)
        if res.get("status") == "deleted":
            Messagebox.show_info(res.get("mensagem"), "Sucesso")
            self._carregar_alunos()
        elif res.get("status") == "has_records":
            pergunta = Messagebox.show_question(
                f"{res.get('mensagem')}\n\nDeseja desativar este aluno para mantê-lo no histórico?",
                "Histórico Existente",
            )
            if pergunta == "Yes":
                res_desat = self.fachada_nucleo.deletar_estudante(
                    aluno_id, forcar_desativacao=True
                )
                Messagebox.show_info(res_desat.get("mensagem"), "Concluído")
                self._carregar_alunos()
        else:
            Messagebox.show_error(res.get("mensagem", "Erro desconhecido."), "Erro")

    def _exportar_alunos(self, formato: str):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ext = ".xlsx" if formato == "xlsx" else ".csv"
            ftypes = (
                [("Excel", "*.xlsx")]
                if formato == "xlsx"
                else [("CSV", "*.csv")]
            )
            filepath = filedialog.asksaveasfilename(
                initialfile=f"export_alunos_{timestamp}",
                defaultextension=ext,
                filetypes=ftypes,
            )
            if not filepath:
                return

            export_dados = [
                {
                    "id": a["id"],
                    "prontuario": a["prontuario"],
                    "nome": a["nome"],
                    "grupos": ", ".join(a.get("grupos", [])),
                    "ativo": "Sim" if a.get("ativo", True) else "Não",
                }
                for a in self.dados_alunos_atuais
            ]

            if formato == "xlsx":
                self.fachada_nucleo.exportar_estudantes_para_xlsx(
                    Path(filepath), estudantes_dados=export_dados
                )
            else:
                self.fachada_nucleo.exportar_estudantes_para_csv(
                    Path(filepath), estudantes_dados=export_dados
                )

            Messagebox.show_info(f"Alunos exportados com sucesso em:\n{filepath}", "Sucesso")
        except Exception as e:
            Messagebox.show_error(f"Falha ao exportar alunos: {e}", "Erro")
