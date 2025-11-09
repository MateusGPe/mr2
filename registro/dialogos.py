# gestao_refeitorio/dialogos.py

import tkinter as tk
import traceback
from datetime import datetime

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, END, E, LEFT, EW, W, X
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.scrolled import ScrolledFrame
from ttkbootstrap.widgets import DateEntry

from registro.nucleo.exceptions import ErroSessao
from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.utils import DADOS_SESSAO


class StudentDialog(ttk.Toplevel):
    def __init__(self, parent, fachada: FachadaRegistro, student_id: int | None = None):
        super().__init__(parent, "Adicionar/Editar Aluno")
        self.transient(parent)
        self.grab_set()

        self.fachada = fachada
        self.student_id = student_id
        self.result = False

        self._create_widgets()
        self._load_data()

        if self.student_id:
            self._load_student_data()

        if self.winfo_exists():
            self.protocol("WM_DELETE_WINDOW", self._on_cancel)
            self.wait_window(self)

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(expand=True, fill=BOTH)

        ttk.Label(main_frame, text="Nome Completo:").grid(
            row=0, column=0, sticky=W, pady=(0, 5)
        )
        self.nome_entry = ttk.Entry(main_frame, width=40)
        self.nome_entry.grid(row=1, column=0, sticky=EW, pady=(0, 10))

        ttk.Label(main_frame, text="Prontuário:").grid(
            row=2, column=0, sticky=W, pady=(0, 5)
        )
        self.prontuario_entry = ttk.Entry(main_frame, width=40)
        self.prontuario_entry.grid(row=3, column=0, sticky=EW, pady=(0, 10))

        ttk.Label(main_frame, text="Turma Principal:").grid(
            row=4, column=0, sticky=W, pady=(0, 5)
        )
        self.grupo_combobox = ttk.Combobox(main_frame, state="readonly")
        self.grupo_combobox.grid(row=5, column=0, sticky=EW, pady=(0, 10))

        main_frame.columnconfigure(0, weight=1)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=6, column=0, sticky=EW, pady=(10, 0))
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
            self.grupo_combobox["values"] = [g["nome"] for g in grupos]
        except Exception:
            Messagebox.show_error(
                "Não foi possível carregar a lista de turmas.", "Erro"
            )
            traceback.print_exc()

    def _load_student_data(self):
        try:
            students_list = self.fachada.listar_estudantes()
            student_data = next(
                (
                    s
                    for s in students_list
                    if int(s.get("id", 0)) == int(self.student_id or 0)
                ),
                None,
            )

            if not student_data:
                Messagebox.show_error(
                    f"Aluno com ID {self.student_id} não encontrado.", "Erro"
                )
                self.destroy()
                return

            self.title(f"Editar Aluno: {student_data['nome']}")
            self.nome_entry.insert(0, student_data["nome"])
            self.prontuario_entry.insert(0, student_data["prontuario"])
            self.prontuario_entry.config(state="readonly")

            if student_data["grupos"]:
                self.grupo_combobox.set(student_data["grupos"][0])
        except Exception:
            Messagebox.show_error(
                "Erro ao carregar dados do aluno. Verifique o console.", "Erro"
            )
            traceback.print_exc()

    def _on_save(self):
        nome = self.nome_entry.get().strip()
        prontuario = self.prontuario_entry.get().strip()
        grupo_selecionado = self.grupo_combobox.get()

        if not nome or not prontuario:
            Messagebox.show_warning("Nome e prontuário são obrigatórios.", "Validação")
            return

        try:
            if self.student_id:
                self.fachada.atualizar_estudante(self.student_id, {"nome": nome})
            else:
                self.fachada.criar_estudante(prontuario, nome)
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


class ReservaDialog(ttk.Toplevel):
    def __init__(self, parent, fachada: FachadaRegistro, reserva_id: int | None = None):
        super().__init__(parent, "Adicionar/Editar Reserva")
        self.transient(parent)
        self.grab_set()

        self.fachada = fachada
        self.reserva_id = reserva_id
        self.result = False

        self._load_student_cache()
        self._create_widgets()

        if self.reserva_id:
            self._load_reserva_data()

        if self.winfo_exists():
            self.protocol("WM_DELETE_WINDOW", self._on_cancel)
            self.wait_window(self)

    def _load_student_cache(self):
        try:
            self.student_cache = self.fachada.listar_estudantes()
            self.student_display_list = [
                f"{s['prontuario']} - {s['nome']}" for s in self.student_cache
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

        ttk.Label(main_frame, text="Aluno (digite para buscar):").grid(
            row=0, column=0, columnspan=2, sticky=W, pady=(0, 5)
        )
        self.aluno_combobox = ttk.Combobox(main_frame, values=self.student_display_list)
        self.aluno_combobox.grid(row=1, column=0, columnspan=2, sticky=EW, pady=(0, 10))
        self.aluno_combobox.bind("<KeyRelease>", self._on_student_search)

        ttk.Label(main_frame, text="Data:").grid(row=2, column=0, sticky=W, pady=(0, 5))
        self.data_entry = DateEntry(
            main_frame, bootstyle="primary", dateformat="%Y-%m-%d"
        )
        self.data_entry.grid(row=3, column=0, sticky=EW, pady=(0, 10), padx=(0, 5))

        ttk.Label(main_frame, text="Prato:").grid(
            row=2, column=1, sticky=W, pady=(0, 5)
        )
        self.prato_combobox = ttk.Combobox(
            main_frame, values=["Tradicional", "Vegetariano"], state="readonly"
        )
        self.prato_combobox.grid(row=3, column=1, sticky=EW, pady=(0, 10), padx=(5, 0))
        self.prato_combobox.set("Tradicional")

        self.cancelada_var = tk.BooleanVar()
        ttk.Checkbutton(
            main_frame,
            text="Reserva Cancelada",
            variable=self.cancelada_var,
            bootstyle="danger-round-toggle",
        ).grid(row=4, column=0, columnspan=2, sticky=W, pady=5)

        main_frame.columnconfigure((0, 1), weight=1)
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=5, column=0, columnspan=2, sticky=EW, pady=(10, 0))
        btn_frame.columnconfigure(1, weight=1)
        ttk.Button(
            btn_frame, text="Cancelar", command=self._on_cancel, bootstyle="outline"
        ).grid(row=0, column=0, sticky=W)
        ttk.Button(
            btn_frame, text="Salvar", command=self._on_save, bootstyle="success"
        ).grid(row=0, column=1, sticky=E)

    def _on_student_search(self, event):
        value = event.widget.get().lower()
        if not value:
            self.aluno_combobox["values"] = self.student_display_list
        else:
            filtered_data = [
                item for item in self.student_display_list if value in item.lower()
            ]
            self.aluno_combobox["values"] = filtered_data

    def _load_reserva_data(self):
        reservas = self.fachada.repo_reserva.ler_filtrado(id=self.reserva_id)
        if not reservas:
            Messagebox.show_error(
                f"Reserva com ID {self.reserva_id} não encontrada.", "Erro"
            )
            self.destroy()
            return

        reserva = reservas[0]
        self.title("Editar Reserva")
        aluno_display = f"{reserva.estudante.prontuario} - {reserva.estudante.nome}"
        self.aluno_combobox.set(aluno_display)
        self.data_entry.entry.delete(0, END)
        self.data_entry.entry.insert(0, reserva.data)
        self.prato_combobox.set(reserva.prato or "Tradicional")
        self.cancelada_var.set(reserva.cancelada)

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
        super().__init__(parent, "Iniciar Sessão de Consumo")
        self.transient(parent)
        self.grab_set()
        self.fachada = fachada
        self.result = None
        self._create_widgets()
        self._load_data()
        self.wait_window(self)

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=BOTH, expand=True)
        new_session_frame = ttk.Labelframe(
            main_frame, text=" ➕ Criar Nova Sessão ", padding=10
        )
        new_session_frame.pack(fill=X, pady=(0, 10))
        self.refeicao_var = tk.StringVar(value="almoço")
        ttk.Radiobutton(
            new_session_frame, text="Almoço", variable=self.refeicao_var, value="almoço"
        ).pack(side=LEFT, padx=5)
        ttk.Radiobutton(
            new_session_frame, text="Lanche", variable=self.refeicao_var, value="lanche"
        ).pack(side=LEFT, padx=5)
        scrolled_frame = ScrolledFrame(new_session_frame, autohide=True, height=150)
        scrolled_frame.pack(fill=X, expand=True, pady=10)
        self.grupos_frame = scrolled_frame.container
        self.grupos_vars = {}
        ttk.Button(
            new_session_frame,
            text="Iniciar Nova Sessão",
            command=self._on_create,
            bootstyle="success",
        ).pack(anchor=E)
        existing_session_frame = ttk.Labelframe(
            main_frame, text=" 📝 Selecionar Sessão Existente ", padding=10
        )
        existing_session_frame.pack(fill=X)
        self.sessoes_combobox = ttk.Combobox(existing_session_frame, state="readonly")
        self.sessoes_combobox.pack(fill=X, expand=True, side=LEFT, padx=(0, 10))
        ttk.Button(
            existing_session_frame,
            text="Definir como Ativa",
            command=self._on_select,
            bootstyle="info",
        ).pack(side=LEFT)

    def _load_data(self):
        try:
            grupos = self.fachada.listar_todos_os_grupos()
            for grupo in sorted(grupos, key=lambda g: g["nome"]):
                var = tk.BooleanVar()
                cb = ttk.Checkbutton(
                    self.grupos_frame,
                    text=grupo["nome"],
                    variable=var,
                    bootstyle="primary",
                )
                cb.pack(anchor=W)
                self.grupos_vars[grupo["nome"]] = var
            sessoes = self.fachada.listar_todas_sessoes()
            sessoes_formatadas = []
            self.sessoes_map = {}
            for sessao in sorted(sessoes, key=lambda s: s["id"], reverse=True):
                texto = f"ID {sessao['id']}: {sessao['data']} {sessao['hora']} - {sessao['refeicao'].capitalize()}"
                sessoes_formatadas.append(texto)
                self.sessoes_map[texto] = sessao["id"]
            self.sessoes_combobox["values"] = sessoes_formatadas
            if sessoes_formatadas:
                self.sessoes_combobox.current(0)
        except Exception:
            Messagebox.show_error(
                "Erro ao carregar dados. Verifique o console.", "Erro"
            )
            traceback.print_exc()

    def _on_create(self):
        grupos_selecionados = [
            nome for nome, var in self.grupos_vars.items() if var.get()
        ]
        dados_sessao: DADOS_SESSAO = {
            "refeicao": self.refeicao_var.get(),
            "periodo": "Integral",
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
        except Exception:
            Messagebox.show_error("Erro ao criar sessão. Verifique o console.", "Erro")
            traceback.print_exc()

    def _on_select(self):
        selecionado = self.sessoes_combobox.get()
        if not selecionado:
            Messagebox.show_warning("Selecione uma sessão.", "Aviso")
            return
        self.result = self.sessoes_map[selecionado]
        self.fachada.definir_sessao_ativa(self.result)
        self.destroy()
