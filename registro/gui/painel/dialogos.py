# ----------------------------------------------------------------------------
# Arquivo: registro/gui/painel/dialogos.py (Módulo de Diálogos)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

import tkinter as tk
import traceback
from datetime import datetime

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, END, EW, HORIZONTAL, LEFT, NSEW, RIGHT, E, W, X
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap import ScrolledFrame
from ttkbootstrap.widgets import DateEntry

from registro.nucleo.exceptions import ErroSessao
from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.utils import DADOS_SESSAO


class StudentDialog(ttk.Toplevel):
    def __init__(self, parent, fachada: FachadaRegistro, student_id: int | None = None):
        title = "Editar Aluno" if student_id else "Adicionar Aluno"
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title(title)

        self.fachada = fachada
        self.student_id = student_id
        self.result = False
        self.var_ativo = tk.BooleanVar(value=True)

        self._create_widgets()
        self._load_data()

        if self.student_id:
            self._load_student_data()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.wait_window(self)

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(expand=True, fill=BOTH)
        main_frame.columnconfigure(0, weight=1)

        form_frame = ttk.Frame(main_frame)
        form_frame.grid(row=0, column=0, sticky=EW)
        form_frame.columnconfigure(0, weight=1)

        ttk.Label(form_frame, text="Nome Completo:", anchor=W).grid(
            row=0, column=0, sticky=EW, pady=(0, 5)
        )
        self.nome_entry = ttk.Entry(form_frame, width=40)
        self.nome_entry.grid(row=1, column=0, sticky=EW, pady=(0, 10))

        ttk.Label(form_frame, text="Prontuário:", anchor=W).grid(
            row=2, column=0, sticky=EW, pady=(0, 5)
        )
        self.prontuario_entry = ttk.Entry(form_frame, width=40)
        self.prontuario_entry.grid(row=3, column=0, sticky=EW, pady=(0, 10))

        ttk.Label(form_frame, text="Turma Principal:", anchor=W).grid(
            row=4, column=0, sticky=EW, pady=(0, 5)
        )
        self.grupo_combobox = ttk.Combobox(form_frame, state="readonly")
        self.grupo_combobox.grid(row=5, column=0, sticky=EW, pady=(0, 15))

        self.chk_ativo = ttk.Checkbutton(
            form_frame,
            text="Aluno Ativo no Sistema",
            variable=self.var_ativo,
            bootstyle="round-toggle",
        )
        self.chk_ativo.grid(row=6, column=0, sticky=W, pady=(0, 10))

        ttk.Separator(main_frame, orient=tk.HORIZONTAL).grid(
            row=1, column=0, sticky=EW, pady=10
        )

        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=2, column=0, sticky=EW)
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        ttk.Button(
            btn_frame, text="Cancelar", command=self._on_cancel, bootstyle="outline"
        ).grid(row=0, column=0, sticky=W)
        ttk.Button(
            btn_frame, text="Salvar", command=self._on_save, bootstyle="success"
        ).grid(row=0, column=1, sticky=E)

        self.nome_entry.focus_set()

    def _load_data(self):
        try:
            grupos = self.fachada.listar_todos_os_grupos()
            opcoes = ["(Nenhuma)"] + [g["nome"] for g in grupos]
            self.grupo_combobox["values"] = opcoes
            self.grupo_combobox.set(opcoes[1] if len(opcoes) > 1 else "(Nenhuma)")
        except Exception:
            Messagebox.show_error(
                "Não foi possível carregar a lista de turmas.", "Erro"
            )
            traceback.print_exc()

    def _load_student_data(self):
        try:
            student_data = self.fachada.repo_estudante.por_ids({self.student_id})
            student_data = student_data[0] if student_data else None

            if not student_data:
                Messagebox.show_error(
                    f"Aluno com ID {self.student_id} não encontrado.", "Erro"
                )
                self.destroy()
                return

            self.title(f"Editar Aluno: {student_data.nome}")
            self.nome_entry.insert(0, student_data.nome)
            self.prontuario_entry.insert(0, student_data.prontuario)
            self.prontuario_entry.config(state="readonly")
            self.var_ativo.set(bool(student_data.ativo) if student_data.ativo is not None else True)

            if student_data.grupos:
                self.grupo_combobox.set(student_data.grupos[0].nome)
            else:
                self.grupo_combobox.set("(Nenhuma)")
        except Exception:
            Messagebox.show_error(
                "Erro ao carregar dados do aluno. Verifique o console.", "Erro"
            )
            traceback.print_exc()

    def _on_save(self):
        nome = self.nome_entry.get().strip()
        prontuario = self.prontuario_entry.get().strip()
        grupo_selecionado = self.grupo_combobox.get()
        grupos = [grupo_selecionado] if grupo_selecionado and grupo_selecionado != "(Nenhuma)" else []

        if not nome or not prontuario:
            Messagebox.show_warning("Nome e prontuário são obrigatórios.", "Validação")
            return

        try:
            if self.student_id:
                self.fachada.atualizar_estudante(
                    self.student_id,
                    {"nome": nome, "ativo": self.var_ativo.get()},
                    grupos=grupos,
                )
            else:
                self.fachada.criar_estudante(
                    prontuario,
                    nome,
                    grupos=grupos,
                )
            self.result = True
            self.destroy()
        except ValueError as e:
            Messagebox.show_error(str(e), "Erro ao Salvar")
        except Exception:
            Messagebox.show_error(
                "Ocorreu um erro ao salvar o aluno. Verifique o console.", "Erro Crítico"
            )
            traceback.print_exc()

    def _on_cancel(self):
        self.result = False
        self.destroy()


class TurmaDialog(ttk.Toplevel):
    def __init__(self, parent, fachada: FachadaRegistro, turma_id: int | None = None):
        title = "Editar Turma" if turma_id else "Adicionar Nova Turma"
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title(title)

        self.fachada = fachada
        self.turma_id = turma_id
        self.result = False
        self.var_ativo = tk.BooleanVar(value=True)

        self._create_widgets()
        if self.turma_id:
            self._load_turma_data()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.wait_window(self)

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(expand=True, fill=BOTH)
        main_frame.columnconfigure(0, weight=1)

        form_frame = ttk.Frame(main_frame)
        form_frame.grid(row=0, column=0, sticky=EW)
        form_frame.columnconfigure(0, weight=1)

        ttk.Label(form_frame, text="Nome da Turma:", anchor=W).grid(
            row=0, column=0, sticky=EW, pady=(0, 5)
        )
        self.nome_entry = ttk.Entry(form_frame, width=35)
        self.nome_entry.grid(row=1, column=0, sticky=EW, pady=(0, 15))

        self.chk_ativo = ttk.Checkbutton(
            form_frame,
            text="Turma Ativa",
            variable=self.var_ativo,
            bootstyle="round-toggle",
        )
        self.chk_ativo.grid(row=2, column=0, sticky=W, pady=(0, 10))

        ttk.Separator(main_frame, orient=tk.HORIZONTAL).grid(
            row=1, column=0, sticky=EW, pady=10
        )

        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=2, column=0, sticky=EW)
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        ttk.Button(
            btn_frame, text="Cancelar", command=self._on_cancel, bootstyle="outline"
        ).grid(row=0, column=0, sticky=W)
        ttk.Button(
            btn_frame, text="Salvar", command=self._on_save, bootstyle="success"
        ).grid(row=0, column=1, sticky=E)

        self.nome_entry.focus_set()

    def _load_turma_data(self):
        try:
            turmas = self.fachada.listar_turmas_detalhadas()
            turma = next((t for t in turmas if t["id"] == self.turma_id), None)
            if not turma:
                Messagebox.show_error("Turma não encontrada.", "Erro")
                self.destroy()
                return

            self.nome_entry.insert(0, turma["nome"])
            self.var_ativo.set(turma["ativo"])
        except Exception:
            traceback.print_exc()

    def _on_save(self):
        nome = self.nome_entry.get().strip()
        ativo = self.var_ativo.get()

        if not nome:
            Messagebox.show_warning("O nome da turma é obrigatório.", "Validação")
            return

        try:
            if self.turma_id:
                self.fachada.atualizar_grupo(self.turma_id, {"nome": nome, "ativo": ativo})
            else:
                self.fachada.criar_grupo(nome, ativo=ativo)
            self.result = True
            self.destroy()
        except ValueError as e:
            Messagebox.show_error(str(e), "Erro ao Salvar")
        except Exception as e:
            Messagebox.show_error(f"Erro inesperado: {e}", "Erro")

    def _on_cancel(self):
        self.result = False
        self.destroy()


class VincularAlunoDialog(ttk.Toplevel):
    def __init__(self, parent, fachada: FachadaRegistro, turma_id: int, nome_turma: str):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title(f"Vincular Aluno à Turma: {nome_turma}")
        self.geometry("600x500")

        self.fachada = fachada
        self.turma_id = turma_id
        self.result = False

        self._create_widgets()
        self._carregar_alunos()

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.wait_window(self)

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(expand=True, fill=BOTH)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        search_frame = ttk.Frame(main_frame)
        search_frame.grid(row=0, column=0, sticky=EW, pady=(0, 10))

        ttk.Label(search_frame, text="Buscar Aluno:").pack(side=LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._carregar_alunos())
        self.entry_search = ttk.Entry(search_frame, textvariable=self.search_var)
        self.entry_search.pack(side=LEFT, fill=X, expand=True)

        from registro.gui.comum.controles.treeview_simples import TreeviewSimples

        self.table = TreeviewSimples(
            master=main_frame,
            dados_colunas=[
                {"text": "ID", "width": 50},
                {"text": "Prontuário", "width": 120},
                {"text": "Nome", "stretch": True},
                {"text": "Turmas Atuais", "stretch": True},
            ],
            height=12,
            header_bootstyle="primary",
            select_bootstyle="primary",
            enable_hover=True,
        )
        self.table.grid(row=1, column=0, sticky=NSEW)
        self.table.view.bind("<Double-1>", lambda *_: self._vincular())

        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=2, column=0, sticky=EW, pady=(10, 0))

        ttk.Button(btn_frame, text="Fechar", command=self.destroy, bootstyle="outline").pack(
            side=LEFT
        )
        ttk.Button(
            btn_frame,
            text="Vincular Aluno Selecionado",
            command=self._vincular,
            bootstyle="success",
        ).pack(side=RIGHT)

    def _carregar_alunos(self):
        try:
            termo = self.search_var.get().strip()
            alunos = self.fachada.listar_estudantes_fuzzy(termo_busca=termo, limite=80)
            dados = [
                (
                    a["id"],
                    a["prontuario"],
                    a["nome"],
                    ", ".join(a.get("grupos", [])),
                )
                for a in alunos
            ]
            self.table.construir_dados_tabela(dados)
        except Exception:
            traceback.print_exc()

    def _vincular(self):
        sel = self.table.obter_linha_selecionada()
        if not sel:
            Messagebox.show_warning("Selecione um aluno na tabela.", "Aviso")
            return
        id_aluno = int(sel[0])
        try:
            self.fachada.vincular_aluno_turma(self.turma_id, id_aluno)
            self.result = True
            Messagebox.show_info("Aluno vinculado com sucesso!", "Sucesso")
            self.destroy()
        except Exception as e:
            Messagebox.show_error(f"Erro ao vincular: {e}", "Erro")


class ReservaDialog(ttk.Toplevel):
    def __init__(self, parent, fachada: FachadaRegistro, reserva_id: int | None = None):
        title = "Editar Reserva" if reserva_id else "Adicionar Reserva"
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title(title)

        self.fachada = fachada
        self.reserva_id = reserva_id
        self.result = False

        self._load_student_cache()
        self._create_widgets()

        if self.reserva_id:
            self._load_reserva_data()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.wait_window(self)

    def _load_student_cache(self):
        try:
            self.student_cache = self.fachada.listar_estudantes()
            self.student_display_list = [
                f"{s.get('prontuario', 'N/A')} - {s.get('nome', 'Sem Nome')}"
                for s in self.student_cache
            ]
        except Exception:
            self.student_cache = []
            self.student_display_list = []
            Messagebox.show_error(
                "Não foi possível carregar a lista de alunos.", "Erro"
            )
            traceback.print_exc()

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(expand=True, fill=BOTH)
        main_frame.columnconfigure(0, weight=1)

        form_frame = ttk.Frame(main_frame)
        form_frame.grid(row=0, column=0, sticky=EW)
        form_frame.columnconfigure((0, 1), weight=1)

        ttk.Label(form_frame, text="Aluno:", anchor=W).grid(
            row=0, column=0, columnspan=2, sticky=EW, pady=(0, 5)
        )
        self.aluno_combobox = ttk.Combobox(
            form_frame, values=self.student_display_list, state="readonly"
        )
        self.aluno_combobox.grid(row=1, column=0, columnspan=2, sticky=EW, pady=(0, 10))
        # TODO: Implementar busca em tempo real no Combobox se a lista for muito grande

        ttk.Label(form_frame, text="Data:", anchor=W).grid(
            row=2, column=0, sticky=EW, pady=(0, 5)
        )
        self.data_entry = DateEntry(
            form_frame, bootstyle="primary", date_format="%Y-%m-%d"
        )
        self.data_entry.grid(row=3, column=0, sticky=EW, pady=(0, 10), padx=(0, 5))

        ttk.Label(form_frame, text="Prato:", anchor=W).grid(
            row=2, column=1, sticky=EW, pady=(0, 5), padx=(5, 0)
        )
        self.prato_combobox = ttk.Combobox(
            form_frame,
            values=["Tradicional", "Vegetariano", "Vegano"],
            state="readonly",
        )
        self.prato_combobox.grid(row=3, column=1, sticky=EW, pady=(0, 10), padx=(5, 0))
        self.prato_combobox.set("Tradicional")

        self.cancelada_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            form_frame,
            text="Reserva Cancelada",
            variable=self.cancelada_var,
            bootstyle="danger-round-toggle",
        ).grid(row=4, column=0, columnspan=2, sticky=W, pady=10)

        ttk.Separator(main_frame, orient=HORIZONTAL).grid(
            row=1, column=0, sticky=EW, pady=10
        )

        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=2, column=0, sticky=EW)
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        ttk.Button(
            btn_frame, text="Cancelar", command=self._on_cancel, bootstyle="outline"
        ).grid(row=0, column=0, sticky=W)
        ttk.Button(
            btn_frame, text="Salvar", command=self._on_save, bootstyle="success"
        ).grid(row=0, column=1, sticky=E)

    def _load_reserva_data(self):
        try:
            reserva = (
                self.fachada.repo_reserva.ler_filtrado(id=self.reserva_id)
                or [None]
            )[0]
            if not reserva:
                Messagebox.show_error(
                    f"Reserva com ID {self.reserva_id} não encontrada.", "Erro"
                )
                self.destroy()
                return

            self.title(f"Editar Reserva: {reserva.id}")
            aluno_display = f"{reserva.estudante.prontuario} - {reserva.estudante.nome}"
            self.aluno_combobox.set(aluno_display)
            self.aluno_combobox.config(state="disabled")

            self.data_entry.entry.delete(0, END)
            self.data_entry.entry.insert(0, reserva.data)
            self.prato_combobox.set(reserva.prato)
            self.cancelada_var.set(reserva.cancelada)

        except Exception:
            Messagebox.show_error(
                "Erro ao carregar dados da reserva. Verifique o console.", "Erro"
            )
            traceback.print_exc()

    def _on_save(self):
        aluno_selecionado = self.aluno_combobox.get().strip()
        data = self.data_entry.entry.get()
        prato = self.prato_combobox.get()
        cancelada = self.cancelada_var.get()

        if not aluno_selecionado or not data:
            Messagebox.show_warning("Aluno e data são obrigatórios.", "Validação")
            return

        try:
            prontuario = aluno_selecionado.split(" - ")[0]
        except IndexError:
            Messagebox.show_warning(
                "Formato de aluno inválido. Selecione um da lista.", "Validação"
            )
            return

        payload = {"data": data, "prato": prato, "cancelada": cancelada}

        try:
            if self.reserva_id:
                self.fachada.atualizar_reserva(self.reserva_id, payload)
            else:
                self.fachada.criar_reserva(prontuario, payload)

            self.result = True
            self.destroy()
        except ValueError as e:
            Messagebox.show_error(str(e), "Erro ao Salvar")
        except Exception:
            Messagebox.show_error(
                "Ocorreu um erro. Verifique o console.", "Erro Crítico"
            )
            traceback.print_exc()

    def _on_cancel(self):
        self.result = False
        self.destroy()


class SessionDialog(ttk.Toplevel):
    def __init__(self, parent, fachada: FachadaRegistro):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title("Iniciar ou Selecionar Sessão de Consumo")
        self.fachada = fachada
        self.result = None
        self._create_widgets()
        self._load_data()
        self.wait_window(self)

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)

        new_session_frame = ttk.Labelframe(
            main_frame, text=" ➕ Criar Nova Sessão ", padding=15
        )
        new_session_frame.pack(fill=X, pady=(0, 10))
        new_session_frame.columnconfigure(0, weight=1)

        refeicao_label_frame = ttk.Frame(new_session_frame)
        refeicao_label_frame.pack(fill=X, pady=(0, 10))
        ttk.Label(refeicao_label_frame, text="Refeição:", anchor=W).pack(
            side=LEFT, padx=(0, 10)
        )
        self.refeicao_var = tk.StringVar(value="almoço")
        ttk.Radiobutton(
            refeicao_label_frame,
            text="Almoço",
            variable=self.refeicao_var,
            value="almoço",
        ).pack(side=LEFT, padx=5)
        ttk.Radiobutton(
            refeicao_label_frame,
            text="Lanche",
            variable=self.refeicao_var,
            value="lanche",
        ).pack(side=LEFT, padx=5)

        ttk.Label(new_session_frame, text="Grupos Permitidos:", anchor=W).pack(
            fill=X, pady=(5, 5)
        )
        scrolled_frame = ScrolledFrame(new_session_frame, auto_hide=True, height=120)
        scrolled_frame.pack(fill=X, expand=True, pady=5)
        self.grupos_frame = scrolled_frame.container
        self.grupos_vars = {}

        ttk.Button(
            new_session_frame,
            text="Iniciar Nova Sessão",
            command=self._on_create,
            bootstyle="success",
        ).pack(anchor=E, pady=(15, 0))

        existing_session_frame = ttk.Labelframe(
            main_frame, text=" 📝 Selecionar Sessão Existente ", padding=15
        )
        existing_session_frame.pack(fill=X)
        existing_session_frame.columnconfigure(0, weight=1)

        session_select_frame = ttk.Frame(existing_session_frame)
        session_select_frame.pack(fill=X, expand=True)

        self.sessoes_combobox = ttk.Combobox(session_select_frame, state="readonly")
        self.sessoes_combobox.pack(fill=X, expand=True, side=LEFT, padx=(0, 10))

        self.btn_select = ttk.Button(
            session_select_frame,
            text="Definir como Ativa",
            command=self._on_select,
            bootstyle="info",
        )
        self.btn_select.pack(side=LEFT)

    def _load_data(self):
        try:
            grupos = self.fachada.listar_todos_os_grupos()
            for grupo in sorted(grupos, key=lambda g: g["nome"]):
                var = tk.BooleanVar()
                cb = ttk.Checkbutton(
                    self.grupos_frame,
                    text=grupo["nome"],
                    variable=var,
                    bootstyle="primary-outline",
                )
                cb.pack(anchor=W, fill=X, padx=5, pady=2)
                self.grupos_vars[grupo["nome"]] = var

            sessoes = self.fachada.listar_todas_sessoes()
            sessoes_formatadas = []
            self.sessoes_map = {}
            for sessao in sorted(sessoes, key=lambda s: s["id"], reverse=True):
                texto = (
                    f"ID {sessao['id']}: {sessao['data']} {sessao['hora']} - "
                    f"{sessao['refeicao'].capitalize()}"
                )
                sessoes_formatadas.append(texto)
                self.sessoes_map[texto] = sessao["id"]

            self.sessoes_combobox["values"] = sessoes_formatadas
            if sessoes_formatadas:
                self.sessoes_combobox.current(0)
            else:
                self.sessoes_combobox.set("Nenhuma sessão anterior encontrada.")
                self.sessoes_combobox.config(state="disabled")
                self.btn_select.config(state="disabled")
        except Exception:
            Messagebox.show_error(
                "Erro ao carregar dados. Verifique o console.", "Erro"
            )
            traceback.print_exc()

    def _on_create(self):
        grupos_selecionados = [
            nome for nome, var in self.grupos_vars.items() if var.get()
        ]
        if not grupos_selecionados:
            Messagebox.show_warning("Selecione pelo menos um grupo.", "Aviso")
            return

        dados_sessao: DADOS_SESSAO = {
            "refeicao": self.refeicao_var.get(),
            "periodo": "Integral",  # TODO: Permitir configuração do período
            "data": datetime.now().strftime("%Y-%m-%d"),
            "hora": datetime.now().strftime("%H:%M"),
            "grupos": grupos_selecionados,
        }
        try:
            self.result = self.fachada.iniciar_nova_sessao(dados_sessao)
            if self.result is None:
                raise ErroSessao(
                    "Não é possível iniciar uma sessão de almoço sem reservas ativas para a data."
                )
            self.destroy()
        except Exception as e:
            Messagebox.show_error(f"Erro ao criar sessão: {e}", "Erro")
            traceback.print_exc()

    def _on_select(self):
        selecionado = self.sessoes_combobox.get()
        if not selecionado or not self.sessoes_map:
            Messagebox.show_warning("Selecione uma sessão válida.", "Aviso")
            return
        self.result = self.sessoes_map[selecionado]
        self.fachada.definir_sessao_ativa(self.result)
        self.destroy()
