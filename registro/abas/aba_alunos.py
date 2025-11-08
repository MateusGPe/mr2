# gestao_refeitorio/abas/aba_alunos.py

import tkinter as tk
import traceback

import ttkbootstrap as ttk
from ttkbootstrap.constants import EW, LEFT, X, BOTH, NSEW
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.tableview import Tableview

from registro.dialogos import StudentDialog


class AbaAlunos(ttk.Frame):
    def __init__(self, parent, fachada_nucleo):
        super().__init__(parent)
        self.fachada_nucleo = fachada_nucleo
        self._criar_widgets()
        self._carregar_alunos()

    def _criar_widgets(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, padding=(10, 10, 10, 0))
        toolbar.grid(row=0, column=0, sticky=EW)

        self.search_aluno_var = tk.StringVar()
        self.search_aluno_var.trace_add("write", lambda *_: self._carregar_alunos())
        ttk.Entry(toolbar, textvariable=self.search_aluno_var, width=40).pack(
            side=LEFT, fill=X, expand=True
        )

        ttk.Button(
            toolbar,
            text="Adicionar",
            command=self._adicionar_aluno,
            bootstyle="success",
        ).pack(side=LEFT, padx=5)

        self.btn_edit_aluno = ttk.Button(
            toolbar, text="Editar", command=self._editar_aluno, state="disabled"
        )
        self.btn_edit_aluno.pack(side=LEFT, padx=5)

        self.btn_delete_aluno = ttk.Button(
            toolbar,
            text="Excluir",
            command=self._deletar_aluno,
            bootstyle="danger-outline",
            state="disabled",
        )
        self.btn_delete_aluno.pack(side=LEFT, padx=5)

        container = ttk.Frame(self, padding=(10, 0, 10, 10))
        container.grid(row=1, column=0, sticky=NSEW)

        self.alunos_coldata = [
            {"text": "ID", "stretch": False, "width": 60},
            {"text": "Nome", "stretch": True},
            {"text": "Prontuário", "stretch": False, "width": 150},
            {"text": "Grupos", "stretch": True},
            {"text": "Ativo", "stretch": False, "width": 80},
        ]
        self.alunos_table = Tableview(
            master=container,
            coldata=self.alunos_coldata,
            paginated=True,
            bootstyle="primary",
        )
        self.alunos_table.pack(expand=True, fill=BOTH)
        self.alunos_table.view.bind("<<TreeviewSelect>>", self._on_aluno_select)

    def _get_dados_linha_selecionada(self):
        """Retorna os dados da linha selecionada na tabela."""
        selecao = self.alunos_table.view.selection()
        if not selecao:
            return None
        return self.alunos_table.view.item(selecao[0], "values")

    def _on_aluno_select(self, _=None):
        is_selected = bool(self._get_dados_linha_selecionada())
        self.btn_edit_aluno.config(state="normal" if is_selected else "disabled")
        self.btn_delete_aluno.config(state="normal" if is_selected else "disabled")

    def _carregar_alunos(self):
        try:
            termo = self.search_aluno_var.get()
            alunos = self.fachada_nucleo.listar_estudantes(termo_busca=termo)
            dados = [
                (
                    a["id"],
                    a["nome"],
                    a["prontuario"],
                    ", ".join(a["grupos"]),
                    "Sim" if a["ativo"] else "Não",
                )
                for a in alunos
            ]
            self.alunos_table.build_table_data(self.alunos_coldata, dados)
        except Exception:
            Messagebox.show_error(
                "Erro ao carregar alunos. Verifique o console.", "Erro"
            )
            traceback.print_exc()
        self._on_aluno_select()

    def _adicionar_aluno(self):
        dialog = StudentDialog(self, self.fachada_nucleo)
        if dialog.result:
            self._carregar_alunos()

    def _get_aluno_selecionado_id(self):
        selecionado = self._get_dados_linha_selecionada()
        return selecionado[0] if selecionado else None

    def _editar_aluno(self):
        aluno_id = self._get_aluno_selecionado_id()
        if not aluno_id:
            return
        dialog = StudentDialog(self, self.fachada_nucleo, student_id=aluno_id)
        if dialog.result:
            self._carregar_alunos()

    def _deletar_aluno(self):
        aluno_id = self._get_aluno_selecionado_id()
        if not aluno_id:
            return

        confirmado = Messagebox.okcancel(
            f"Deseja excluir o aluno com ID {aluno_id}?", "Confirmar Exclusão"
        )
        if confirmado:
            try:
                self.fachada_nucleo.deletar_estudante(aluno_id)
                self._carregar_alunos()
            except Exception:
                Messagebox.show_error(
                    "Erro ao excluir. Verifique registros associados.", "Erro"
                )
                traceback.print_exc()
