# ----------------------------------------------------------------------------
# Arquivo: registro/gui/painel/abas/aba_turmas.py (Aba de Gestão de Turmas)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

import tkinter as tk
from tkinter import filedialog
import traceback
from datetime import datetime
from pathlib import Path

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, EW, LEFT, NSEW, RIGHT, W, X
from ttkbootstrap.dialogs import Messagebox

from registro.gui.comum.controles.rounded_button import RoundedButton
from registro.gui.comum.controles.treeview_simples import TreeviewSimples
from registro.gui.painel.dialogos import TurmaDialog, VincularAlunoDialog
from registro.nucleo.facade import FachadaRegistro


class AbaTurmas(ttk.Frame):
    """
    Aba de gerenciamento completo de Turmas (Grupos).
    Layout dividido lado a lado:
    - Esquerda: lista de turmas com CRUD e exportação.
    - Direita: lista de alunos vinculados à turma selecionada com vinculação/desvinculação rápida.
    """

    def __init__(self, parent, fachada_nucleo: FachadaRegistro):
        super().__init__(parent)
        self.fachada_nucleo = fachada_nucleo
        self.turma_selecionada_id = None
        self.turma_selecionada_nome = None

        self._criar_widgets()
        self._carregar_turmas()

    def _criar_widgets(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # -----------------------------
        # Painel Esquerdo: Turmas
        # -----------------------------
        frame_esquerdo = ttk.Labelframe(self, text="🏫 Turmas Cadastradas", padding=10)
        frame_esquerdo.grid(row=0, column=0, sticky=NSEW, padx=(0, 5))
        frame_esquerdo.columnconfigure(0, weight=1)
        frame_esquerdo.rowconfigure(2, weight=1)

        # Barra de Ações de Turmas
        acoes_turma_frame = ttk.Frame(frame_esquerdo)
        acoes_turma_frame.grid(row=0, column=0, sticky=EW, pady=(0, 10))

        RoundedButton(
            acoes_turma_frame,
            text="+ Nova Turma",
            command=self._adicionar_turma,
            bootstyle="success",
        ).pack(side=LEFT, padx=(0, 5))

        self.btn_edit_turma = RoundedButton(
            acoes_turma_frame,
            text="Editar",
            command=self._editar_turma,
            state="disabled",
        )
        self.btn_edit_turma.pack(side=LEFT, padx=5)

        self.btn_del_turma = RoundedButton(
            acoes_turma_frame,
            text="Excluir",
            command=self._excluir_turma,
            bootstyle="danger",
            state="disabled",
        )
        self.btn_del_turma.pack(side=LEFT, padx=5)

        # Botão de Exportação de Turmas
        self.btn_export_turmas = ttk.Menubutton(
            acoes_turma_frame,
            text="Exportar ▾",
            bootstyle="secondary-outline",
        )
        menu_exp_turmas = tk.Menu(self.btn_export_turmas, tearoff=0)
        menu_exp_turmas.add_command(
            label="Exportar para Excel (.xlsx)", command=lambda: self._exportar_turmas("xlsx")
        )
        menu_exp_turmas.add_command(
            label="Exportar para CSV (.csv)", command=lambda: self._exportar_turmas("csv")
        )
        self.btn_export_turmas["menu"] = menu_exp_turmas
        self.btn_export_turmas.pack(side=RIGHT, padx=(5, 0))

        # Busca de Turmas
        busca_turma_frame = ttk.Frame(frame_esquerdo)
        busca_turma_frame.grid(row=1, column=0, sticky=EW, pady=(0, 10))
        ttk.Label(busca_turma_frame, text="Buscar:").pack(side=LEFT, padx=(0, 5))
        self.busca_turma_var = tk.StringVar()
        self.busca_turma_var.trace_add("write", lambda *_: self._carregar_turmas())
        ttk.Entry(busca_turma_frame, textvariable=self.busca_turma_var).pack(
            side=LEFT, fill=X, expand=True
        )

        # Tabela de Turmas
        self.turmas_coldata = [
            {"text": "ID", "width": 50},
            {"text": "Nome da Turma", "stretch": True},
            {"text": "Qtd Alunos", "width": 90},
            {"text": "Ativa", "width": 70},
        ]
        self.turmas_table = TreeviewSimples(
            master=frame_esquerdo,
            dados_colunas=self.turmas_coldata,
            height=15,
            header_bootstyle="primary",
            select_bootstyle="primary",
            enable_hover=True,
        )
        self.turmas_table.grid(row=2, column=0, sticky=NSEW)
        self.turmas_table.view.bind("<<TreeviewSelect>>", self._on_turma_select)

        # -----------------------------
        # Painel Direito: Alunos da Turma
        # -----------------------------
        self.frame_direito = ttk.Labelframe(
            self, text="👥 Alunos da Turma Selecionada", padding=10
        )
        self.frame_direito.grid(row=0, column=1, sticky=NSEW, padx=(5, 0))
        self.frame_direito.columnconfigure(0, weight=1)
        self.frame_direito.rowconfigure(2, weight=1)

        # Barra de Ações de Alunos na Turma
        acoes_alunos_frame = ttk.Frame(self.frame_direito)
        acoes_alunos_frame.grid(row=0, column=0, sticky=EW, pady=(0, 10))

        self.btn_vincular_aluno = RoundedButton(
            acoes_alunos_frame,
            text="+ Vincular Aluno",
            command=self._vincular_aluno,
            bootstyle="info",
            state="disabled",
        )
        self.btn_vincular_aluno.pack(side=LEFT, padx=(0, 5))

        self.btn_desvincular_aluno = RoundedButton(
            acoes_alunos_frame,
            text="Desvincular",
            command=self._desvincular_aluno,
            bootstyle="warning",
            state="disabled",
        )
        self.btn_desvincular_aluno.pack(side=LEFT, padx=5)

        # Rótulo de status da turma selecionada
        self.lbl_turma_info = ttk.Label(
            self.frame_direito,
            text="Selecione uma turma à esquerda para visualizar seus alunos.",
            font="-weight bold",
            bootstyle="secondary",
        )
        self.lbl_turma_info.grid(row=1, column=0, sticky=W, pady=(0, 10))

        # Tabela de Alunos da Turma
        self.alunos_turma_coldata = [
            {"text": "ID", "width": 50},
            {"text": "Prontuário", "width": 120},
            {"text": "Nome", "stretch": True},
            {"text": "Ativo", "width": 70},
        ]
        self.alunos_turma_table = TreeviewSimples(
            master=self.frame_direito,
            dados_colunas=self.alunos_turma_coldata,
            height=15,
            header_bootstyle="info",
            select_bootstyle="info",
            enable_hover=True,
        )
        self.alunos_turma_table.grid(row=2, column=0, sticky=NSEW)
        self.alunos_turma_table.view.bind(
            "<<TreeviewSelect>>", self._on_aluno_turma_select
        )

    def _carregar_turmas(self):
        try:
            termo = self.busca_turma_var.get().strip()
            turmas = self.fachada_nucleo.listar_turmas_detalhadas(termo_busca=termo)
            dados = [
                (
                    t["id"],
                    t["nome"],
                    t["total_alunos"],
                    "Sim" if t["ativo"] else "Não",
                )
                for t in turmas
            ]
            self.turmas_table.construir_dados_tabela(dados)
        except Exception:
            traceback.print_exc()
        self._on_turma_select()

    def _on_turma_select(self, _=None):
        sel = self.turmas_table.obter_linha_selecionada()
        if sel:
            self.turma_selecionada_id = int(sel[0])
            self.turma_selecionada_nome = sel[1]
            self.btn_edit_turma.config(state="normal")
            self.btn_del_turma.config(state="normal")
            self.btn_vincular_aluno.config(state="normal")
            self.frame_direito.configure(
                text=f"👥 Alunos de: {self.turma_selecionada_nome}"
            )
            self.lbl_turma_info.configure(
                text=f"Gerenciando estudantes da turma '{self.turma_selecionada_nome}'",
                bootstyle="info",
            )
            self._carregar_alunos_turma()
        else:
            self.turma_selecionada_id = None
            self.turma_selecionada_nome = None
            self.btn_edit_turma.config(state="disabled")
            self.btn_del_turma.config(state="disabled")
            self.btn_vincular_aluno.config(state="disabled")
            self.btn_desvincular_aluno.config(state="disabled")
            self.frame_direito.configure(text="👥 Alunos da Turma Selecionada")
            self.lbl_turma_info.configure(
                text="Selecione uma turma à esquerda para visualizar seus alunos.",
                bootstyle="secondary",
            )
            self.alunos_turma_table.construir_dados_tabela([])

    def _carregar_alunos_turma(self):
        if not self.turma_selecionada_id:
            return
        try:
            alunos = self.fachada_nucleo.listar_alunos_por_turma(
                self.turma_selecionada_id
            )
            dados = [
                (
                    a["id"],
                    a["prontuario"],
                    a["nome"],
                    "Sim" if a["ativo"] else "Não",
                )
                for a in alunos
            ]
            self.alunos_turma_table.construir_dados_tabela(dados)
        except Exception:
            traceback.print_exc()
        self._on_aluno_turma_select()

    def _on_aluno_turma_select(self, _=None):
        has_sel = bool(self.alunos_turma_table.obter_linha_selecionada())
        self.btn_desvincular_aluno.config(state="normal" if has_sel else "disabled")

    def _adicionar_turma(self):
        dialog = TurmaDialog(self, self.fachada_nucleo)
        if dialog.result:
            self._carregar_turmas()

    def _editar_turma(self):
        if not self.turma_selecionada_id:
            return
        dialog = TurmaDialog(self, self.fachada_nucleo, turma_id=self.turma_selecionada_id)
        if dialog.result:
            self._carregar_turmas()

    def _excluir_turma(self):
        if not self.turma_selecionada_id:
            return
        res = self.fachada_nucleo.deletar_grupo(self.turma_selecionada_id, forcar=False)
        if res.get("status") == "deleted":
            Messagebox.show_info(res.get("mensagem"), "Sucesso")
            self._carregar_turmas()
        elif res.get("status") == "has_relations":
            confirm = Messagebox.show_question(
                f"{res.get('mensagem')}\n\nDeseja desvincular todos os alunos e excluir esta turma definitivamente?",
                "Confirmar Exclusão Forçada",
            )
            if confirm == "Yes":
                res_forcar = self.fachada_nucleo.deletar_grupo(
                    self.turma_selecionada_id, forcar=True
                )
                Messagebox.show_info(res_forcar.get("mensagem"), "Concluído")
                self._carregar_turmas()

    def _vincular_aluno(self):
        if not self.turma_selecionada_id:
            return
        dialog = VincularAlunoDialog(
            self,
            self.fachada_nucleo,
            turma_id=self.turma_selecionada_id,
            nome_turma=self.turma_selecionada_nome or "",
        )
        if dialog.result:
            self._carregar_alunos_turma()
            self._carregar_turmas()

    def _desvincular_aluno(self):
        sel = self.alunos_turma_table.obter_linha_selecionada()
        if not sel or not self.turma_selecionada_id:
            return
        id_aluno = int(sel[0])
        nome_aluno = sel[2]
        confirm = Messagebox.show_question(
            f"Deseja remover o aluno '{nome_aluno}' da turma '{self.turma_selecionada_nome}'?",
            "Confirmar Desvinculação",
        )
        if confirm == "Yes":
            ok = self.fachada_nucleo.desvincular_aluno_turma(
                self.turma_selecionada_id, id_aluno
            )
            if ok:
                Messagebox.show_info("Aluno desvinculado com sucesso.", "Sucesso")
                self._carregar_alunos_turma()
                self._carregar_turmas()

    def _exportar_turmas(self, formato: str):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ext = ".xlsx" if formato == "xlsx" else ".csv"
            ftypes = (
                [("Excel", "*.xlsx")]
                if formato == "xlsx"
                else [("CSV", "*.csv")]
            )
            filepath = filedialog.asksaveasfilename(
                initialfile=f"export_turmas_{timestamp}",
                defaultextension=ext,
                filetypes=ftypes,
            )
            if not filepath:
                return

            if formato == "xlsx":
                self.fachada_nucleo.exportar_turmas_para_xlsx(Path(filepath))
            else:
                self.fachada_nucleo.exportar_turmas_para_csv(Path(filepath))

            Messagebox.show_info(f"Turmas exportadas com sucesso em:\n{filepath}", "Sucesso")
        except Exception as e:
            Messagebox.show_error(f"Falha ao exportar turmas: {e}", "Erro")
