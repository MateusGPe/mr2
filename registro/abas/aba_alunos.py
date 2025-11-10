# gestao_refeitorio/abas/aba_alunos.py

import tkinter as tk
import traceback

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, EW, LEFT, NSEW, E, W, X
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

        # Painel superior unificado para filtros e ações (padrão AbaReservas)
        top_panel = ttk.Frame(self)
        top_panel.grid(row=0, column=0, sticky=EW, pady=(0, 10))
        top_panel.columnconfigure(1, weight=1)  # Coluna do filtro/busca expande

        # Ações à esquerda
        actions_frame = ttk.Frame(top_panel)
        actions_frame.grid(row=0, column=0, sticky=W, padx=(0, 10))

        btn_add = ttk.Button(
            actions_frame,
            text="Adicionar Aluno",
            command=self._adicionar_aluno,
            bootstyle="success",
        )
        btn_add.pack(side=LEFT, padx=5)

        self.btn_edit_aluno = ttk.Button(
            actions_frame, text="Editar", command=self._editar_aluno, state="disabled"
        )
        self.btn_edit_aluno.pack(side=LEFT, padx=5)

        self.btn_delete_aluno = ttk.Button(
            actions_frame,
            text="Excluir",
            command=self._deletar_aluno,
            bootstyle="danger-outline",
            state="disabled",
        )
        self.btn_delete_aluno.pack(side=LEFT, padx=5)

        # Filtros/Busca à direita
        filter_frame = ttk.Frame(top_panel)
        filter_frame.grid(row=0, column=1, sticky=EW)

        ttk.Label(filter_frame, text="Buscar Aluno:").pack(side=LEFT, padx=(0, 5))
        self.search_aluno_var = tk.StringVar()
        self.search_aluno_var.trace_add("write", lambda *_: self._carregar_alunos())
        self.search_entry = ttk.Entry(filter_frame, textvariable=self.search_aluno_var)
        self.search_entry.pack(side=LEFT, fill=X, expand=True)

        # Tabela de Alunos
        container = ttk.Frame(self)
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
            rowdata=[],
            paginated=True,
            pagesize=20,
            bootstyle="primary",
            searchable=False,
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
        self.search_entry.focus_set()

    def _carregar_alunos(self):
        try:
            termo = self.search_aluno_var.get()
            alunos = self.fachada_nucleo.listar_estudantes_fuzzy(
                termo_busca=termo, limite=80
            )
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
            except Exception as e:
                Messagebox.show_error(
                    f"Erro ao excluir. Verifique registros associados: {e}",
                    "Erro",
                )
                traceback.print_exc()
