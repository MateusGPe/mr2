import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Optional, List, Dict

# Importa a biblioteca de busca
from fuzzywuzzy import process

# Importa a sua camada de negócio
from registro.nucleo.facade import RegistroFacade
from registro.nucleo.exceptions import NoActiveSessionError, RegistrationCoreError

# Configurações visuais
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class AutocompleteEntry(ctk.CTkEntry):
    """
    Um widget CTkEntry com uma Listbox de sugestões, busca fuzzy e
    navegação por teclado.
    """

    def __init__(self, master, register_callback, **kwargs):
        super().__init__(master, **kwargs)

        self.register_callback = register_callback
        self._display_map: Dict[str, str] = {}

        self.suggestions_listbox = tk.Listbox(
            master,
            background="#2a2d2e",
            foreground="white",
            selectbackground="#24527d",
            selectforeground="white",
            highlightthickness=0,
            borderwidth=0,
            font=("Arial", 12),
        )

        # --- Eventos ---
        self.bind("<KeyRelease>", self._on_key_release)
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<Down>", self._move_selection)
        self.bind("<Up>", self._move_selection)
        self.bind("<Return>", self._on_enter_key)
        self.suggestions_listbox.bind("<ButtonRelease-1>", self._on_suggestion_click)

    def set_data(self, data_list: List[Dict[str, str]]):
        """Define a lista de dados (dicionários de estudantes) para a busca."""
        self._display_map = {
            f"{s['pront']} - {s['nome']}": s["pront"] for s in data_list
        }

    def _on_key_release(self, event):
        """Atualiza a lista de sugestões a cada tecla pressionada."""
        # Ignora teclas de navegação para não re-filtrar a lista desnecessariamente
        if event.keysym in ("Up", "Down", "Return", "Enter"):
            return

        query = self.get().strip()
        if not query:
            self.suggestions_listbox.place_forget()
            return

        self.suggestions_listbox.delete(0, tk.END)
        choices = self._display_map.keys()
        matches = process.extract(query, choices, limit=5)

        found = False
        for match, score in matches:
            if score > 65:  # Limite de confiança um pouco mais permissivo
                self.suggestions_listbox.insert(tk.END, match)
                found = True

        if found:
            self.suggestions_listbox.place(
                x=self.winfo_x(),
                y=self.winfo_y() + self.winfo_height(),
                width=self.winfo_width(),
            )
            self.suggestions_listbox.lift()
        else:
            self.suggestions_listbox.place_forget()

    def _move_selection(self, event):
        """Move a seleção na listbox com as setas do teclado."""
        if not self.suggestions_listbox.winfo_viewable():
            return

        current_selection_index = self.suggestions_listbox.curselection()
        new_index = 0

        if current_selection_index:
            current_index = current_selection_index[0]
            if event.keysym == "Down":
                new_index = current_index + 1
            elif event.keysym == "Up":
                new_index = current_index - 1

        # Garante que o novo índice está dentro dos limites da lista
        if 0 <= new_index < self.suggestions_listbox.size():
            self.suggestions_listbox.selection_clear(0, tk.END)
            self.suggestions_listbox.selection_set(new_index)
            self.suggestions_listbox.activate(new_index)

    def _on_enter_key(self, event):
        """Confirma a seleção ou o registro ao pressionar Enter."""
        if (
            self.suggestions_listbox.winfo_viewable()
            and self.suggestions_listbox.curselection()
        ):
            self._confirm_selection()
        else:
            self.register_callback()

    def _on_suggestion_click(self, event):
        """Confirma a seleção ao clicar em um item."""
        if self.suggestions_listbox.curselection():
            self._confirm_selection()

    def _confirm_selection(self):
        """Preenche o campo com a seleção e executa o registro."""
        if not self.suggestions_listbox.curselection():
            return

        selected_display_text = self.suggestions_listbox.get(
            self.suggestions_listbox.curselection()
        )
        prontuario = self._display_map.get(selected_display_text)

        if prontuario:
            self.delete(0, tk.END)
            self.insert(0, prontuario)
            self.suggestions_listbox.place_forget()
            self.focus()
            self.register_callback()

    def _on_focus_out(self, event):
        """Esconde a lista de sugestões quando o widget perde o foco."""
        self.after(200, self.suggestions_listbox.place_forget)


class NewSessionWindow(ctk.CTkToplevel):
    """Janela para criar uma nova sessão de refeição."""

    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.title("Nova Sessão de Refeição")
        self.geometry("400x400")
        self.transient(master)
        self.after(100, self.grab_set)

        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Refeição:").grid(
            row=0, column=0, padx=20, pady=10, sticky="w"
        )
        self.refeicao_var = ctk.StringVar(value="almoço")
        self.refeicao_menu = ctk.CTkOptionMenu(
            self, variable=self.refeicao_var, values=["almoço", "lanche"]
        )
        self.refeicao_menu.grid(row=0, column=1, padx=20, pady=10, sticky="ew")

        ctk.CTkLabel(self, text="Período:").grid(
            row=1, column=0, padx=20, pady=10, sticky="w"
        )
        self.periodo_var = ctk.StringVar(value="Integral")
        self.periodo_menu = ctk.CTkOptionMenu(
            self,
            variable=self.periodo_var,
            values=["Integral", "Matutino", "Vespertino", "Noturno"],
        )
        self.periodo_menu.grid(row=1, column=1, padx=20, pady=10, sticky="ew")

        ctk.CTkLabel(self, text="Item Servido (Lanche):").grid(
            row=2, column=0, padx=20, pady=10, sticky="w"
        )
        self.item_servido_entry = ctk.CTkEntry(self, placeholder_text="Opcional")
        self.item_servido_entry.grid(row=2, column=1, padx=20, pady=10, sticky="ew")

        ctk.CTkLabel(self, text="Data (dd/mm/aaaa):").grid(
            row=3, column=0, padx=20, pady=10, sticky="w"
        )
        self.data_entry = ctk.CTkEntry(self)
        self.data_entry.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.data_entry.grid(row=3, column=1, padx=20, pady=10, sticky="ew")

        ctk.CTkLabel(self, text="Hora (hh:mm):").grid(
            row=4, column=0, padx=20, pady=10, sticky="w"
        )
        self.hora_entry = ctk.CTkEntry(self)
        self.hora_entry.insert(0, datetime.now().strftime("%H:%M"))
        self.hora_entry.grid(row=4, column=1, padx=20, pady=10, sticky="ew")

        ctk.CTkLabel(self, text="Grupos de Exceção:").grid(
            row=5, column=0, padx=20, pady=10, sticky="w"
        )
        self.grupos_entry = ctk.CTkEntry(
            self, placeholder_text="Ex: 3A INFO (separados por vírgula)"
        )
        self.grupos_entry.grid(row=5, column=1, padx=20, pady=10, sticky="ew")

        self.create_button = ctk.CTkButton(
            self, text="Criar Sessão", command=self.create_session
        )
        self.create_button.grid(row=6, column=1, padx=20, pady=20, sticky="e")
        self.cancel_button = ctk.CTkButton(
            self, text="Cancelar", command=self.destroy, fg_color="gray"
        )
        self.cancel_button.grid(row=6, column=0, padx=20, pady=20, sticky="w")

    def create_session(self):
        grupos = [g.strip() for g in self.grupos_entry.get().split(",") if g.strip()]
        session_data = {
            "refeicao": self.refeicao_var.get(),
            "periodo": self.periodo_var.get(),
            "item_servido": self.item_servido_entry.get() or None,
            "data": self.data_entry.get(),
            "hora": self.hora_entry.get(),
            "grupos": grupos,
        }
        try:
            self.master.facade.start_new_session(session_data)
            messagebox.showinfo("Sucesso", "Nova sessão criada com sucesso!")
            self.master.refresh_sessions_list()
            self.destroy()
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível criar a sessão:\n{e}")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Registro de Refeições")
        self.geometry("1000x600")

        try:
            self.facade = RegistroFacade()
        except Exception as e:
            messagebox.showerror(
                "Erro Crítico", f"Não foi possível iniciar o back-end:\n{e}"
            )
            self.destroy()
            return

        self.active_session_id: Optional[int] = None
        self.current_student_filter = "Não Consumiram"

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.header_frame = ctk.CTkFrame(self, corner_radius=0, height=40)
        self.header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.header_frame.grid_columnconfigure(0, weight=1)
        self.active_session_label = ctk.CTkLabel(
            self.header_frame,
            text="Nenhuma sessão ativa",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.active_session_label.grid(row=0, column=0, padx=20, pady=10)

        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.tab_view.add("Registro")
        self.tab_view.add("Sessões")
        self.tab_view.add("Administração")

        self.create_registration_tab()
        self.create_sessions_tab()
        self.create_admin_tab()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        if messagebox.askokcancel("Sair", "Deseja fechar a aplicação?"):
            self.facade.close()
            self.destroy()

    def create_registration_tab(self):
        tab = self.tab_view.tab("Registro")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        input_frame = ctk.CTkFrame(tab)
        input_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)

        self.prontuario_entry = AutocompleteEntry(
            input_frame,
            register_callback=self.register_student,
            placeholder_text="Digite nome ou prontuário do estudante...",
            font=ctk.CTkFont(size=14),
        )
        self.prontuario_entry.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.register_button = ctk.CTkButton(
            input_frame, text="Registrar Consumo", command=self.register_student
        )
        self.register_button.grid(row=0, column=1, padx=10, pady=10)

        self.status_label = ctk.CTkLabel(
            input_frame, text="", text_color="green", font=ctk.CTkFont(size=14)
        )
        self.status_label.grid(row=1, column=0, columnspan=2, padx=10, sticky="w")

        list_frame = ctk.CTkFrame(tab)
        list_frame.grid(row=1, column=0, rowspan=2, padx=10, pady=10, sticky="nsew")
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(1, weight=1)

        filter_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        filter_frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(filter_frame, text="Mostrar:").pack(side="left")
        self.filter_segmented_button = ctk.CTkSegmentedButton(
            filter_frame,
            values=["Não Consumiram", "Consumiram", "Todos"],
            command=self.on_filter_change,
        )
        self.filter_segmented_button.set("Não Consumiram")
        self.filter_segmented_button.pack(side="left", padx=10)

        self.undo_button = ctk.CTkButton(
            filter_frame,
            text="Desfazer Registro Selecionado",
            command=self.undo_consumption,
            fg_color="darkred",
        )
        self.undo_button.pack(side="right")

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Treeview",
            background="#2a2d2e",
            foreground="white",
            fieldbackground="#343638",
            borderwidth=0,
        )
        style.map("Treeview", background=[("selected", "#24527d")])

        self.student_tree = ttk.Treeview(
            list_frame,
            columns=("Prontuário", "Nome", "Turma", "Status", "Hora"),
            show="headings",
        )
        self.student_tree.heading("Prontuário", text="Prontuário")
        self.student_tree.heading("Nome", text="Nome")
        self.student_tree.heading("Turma", text="Turma")
        self.student_tree.heading("Status", text="Status")
        self.student_tree.heading("Hora", text="Hora Consumo")
        self.student_tree.column("Prontuário", width=120)
        self.student_tree.column("Nome", width=300)
        self.student_tree.column("Turma", width=150)
        self.student_tree.column("Status", width=150)
        self.student_tree.column("Hora", width=100)
        self.student_tree.grid(row=1, column=0, sticky="nsew")

    def _update_autocomplete_data(self):
        try:
            searchable_students = self.facade.get_searchable_students_for_session()
            self.prontuario_entry.set_data(searchable_students)
        except Exception as e:
            print(f"Erro ao atualizar autocomplete: {e}")
            self.prontuario_entry.set_data([])

    def register_student(self):
        prontuario = self.prontuario_entry.get().strip()
        if not prontuario:
            return

        try:
            result = self.facade.register_consumption(prontuario)
            if result.get("autorizado"):
                self.status_label.configure(
                    text=f"✅ {result.get('aluno')} autorizado(a). Motivo: {result.get('motivo')}",
                    text_color="green",
                )
                self.refresh_student_list()
                self._update_autocomplete_data()
            else:
                self.status_label.configure(
                    text=f"❌ Acesso Negado. Motivo: {result.get('motivo')}",
                    text_color="red",
                )
        except NoActiveSessionError:
            messagebox.showwarning(
                "Aviso",
                "Nenhuma sessão ativa. Por favor, selecione uma na aba 'Sessões'.",
            )
        except Exception as e:
            messagebox.showerror("Erro", f"Ocorreu um erro ao registrar:\n{e}")

        self.prontuario_entry.delete(0, "end")
        self.prontuario_entry.focus()

    def refresh_student_list(self):
        for item in self.student_tree.get_children():
            self.student_tree.delete(item)
        if not self.active_session_id:
            return

        try:
            consumed_map = {"Não Consumiram": False, "Consumiram": True, "Todos": None}
            students = self.facade.get_students_for_session(
                consumed=consumed_map.get(self.current_student_filter)
            )
            for student in students:
                self.student_tree.insert(
                    "",
                    "end",
                    iid=student.get("consumo_id"),
                    values=(
                        student.get("pront"),
                        student.get("nome"),
                        student.get("turma"),
                        student.get("status"),
                        student.get("registro_time"),
                    ),
                )
        except Exception as e:
            messagebox.showerror(
                "Erro", f"Não foi possível carregar a lista de estudantes:\n{e}"
            )

    def on_filter_change(self, value):
        self.current_student_filter = value
        self.refresh_student_list()

    def undo_consumption(self):
        selected_items = self.student_tree.selection()
        if not selected_items:
            messagebox.showwarning(
                "Aviso", "Selecione um registro de consumo na lista para desfazer."
            )
            return

        consumo_id_str = selected_items[0]
        if not consumo_id_str or not consumo_id_str.isdigit():
            messagebox.showwarning(
                "Aviso",
                "Este estudante ainda não consumiu. Não há registro para desfazer.",
            )
            return

        consumo_id = int(consumo_id_str)
        if messagebox.askyesno(
            "Confirmar", "Tem certeza que deseja desfazer este registro de consumo?"
        ):
            try:
                self.facade.undo_consumption(consumo_id)
                self.status_label.configure(
                    text=f"✅ Registro desfeito com sucesso.", text_color="green"
                )
                self.refresh_student_list()
                self._update_autocomplete_data()
            except Exception as e:
                messagebox.showerror(
                    "Erro", f"Não foi possível desfazer o registro:\n{e}"
                )

    def create_sessions_tab(self):
        tab = self.tab_view.tab("Sessões")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        sessions_frame = ctk.CTkFrame(tab)
        sessions_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        sessions_frame.grid_columnconfigure(0, weight=1)
        sessions_frame.grid_rowconfigure(0, weight=1)

        self.sessions_tree = ttk.Treeview(
            sessions_frame,
            columns=("ID", "Refeição", "Data", "Hora", "Item", "Grupos"),
            show="headings",
        )
        self.sessions_tree.heading("ID", text="ID")
        self.sessions_tree.heading("Refeição", text="Refeição")
        self.sessions_tree.heading("Data", text="Data")
        self.sessions_tree.heading("Hora", text="Hora")
        self.sessions_tree.heading("Item", text="Item Servido")
        self.sessions_tree.heading("Grupos", text="Grupos de Exceção")
        self.sessions_tree.column("ID", width=50)
        self.sessions_tree.grid(row=0, column=0, columnspan=2, sticky="nsew")

        buttons_frame = ctk.CTkFrame(tab)
        buttons_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        self.new_session_button = ctk.CTkButton(
            buttons_frame, text="Nova Sessão", command=self.open_new_session_window
        )
        self.new_session_button.pack(side="left", padx=10, pady=10)

        self.set_active_button = ctk.CTkButton(
            buttons_frame,
            text="Definir como Sessão Ativa",
            command=self.set_active_session,
        )
        self.set_active_button.pack(side="left", padx=10, pady=10)

        self.refresh_sessions_button = ctk.CTkButton(
            buttons_frame,
            text="Atualizar Lista",
            command=self.refresh_sessions_list,
            fg_color="gray",
        )
        self.refresh_sessions_button.pack(side="right", padx=10, pady=10)

        self.refresh_sessions_list()

    def refresh_sessions_list(self):
        for item in self.sessions_tree.get_children():
            self.sessions_tree.delete(item)
        try:
            sessions = self.facade.list_all_sessions()
            for session in sorted(
                sessions, key=lambda s: (s["data"], s["hora"]), reverse=True
            ):
                grupos_str = ", ".join(session.get("grupos", []))
                self.sessions_tree.insert(
                    "",
                    "end",
                    iid=session["id"],
                    values=(
                        session["id"],
                        session["refeicao"].capitalize(),
                        session["data"],
                        session["hora"],
                        session.get("item_servido", "N/A"),
                        grupos_str,
                    ),
                )
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível carregar as sessões:\n{e}")

    def set_active_session(self):
        selected_items = self.sessions_tree.selection()
        if not selected_items:
            messagebox.showwarning("Aviso", "Selecione uma sessão na lista.")
            return

        session_id = int(selected_items[0])
        try:
            self.facade.set_active_session(session_id)
            self.active_session_id = session_id
            details = self.facade.get_active_session_details()
            self.active_session_label.configure(
                text=f"Sessão Ativa: {details['refeicao'].capitalize()} de {details['data']} às {details['hora']} (ID: {details['id']})"
            )

            self._update_autocomplete_data()

            messagebox.showinfo("Sucesso", "Sessão definida como ativa!")
            self.refresh_student_list()
            self.tab_view.set("Registro")
        except Exception as e:
            messagebox.showerror(
                "Erro", f"Não foi possível definir a sessão ativa:\n{e}"
            )

    def open_new_session_window(self):
        NewSessionWindow(self)

    def create_admin_tab(self):
        tab = self.tab_view.tab("Administração")
        tab.grid_columnconfigure(0, weight=1)

        google_frame = ctk.CTkFrame(tab)
        google_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        google_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            google_frame,
            text="Sincronização com Google Sheets",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, pady=10)

        self.sync_from_google_button = ctk.CTkButton(
            google_frame,
            text="Baixar Dados (Estudantes e Reservas)",
            command=self.sync_from_google,
        )
        self.sync_from_google_button.grid(
            row=1, column=0, padx=10, pady=10, sticky="ew"
        )
        self.sync_to_google_button = ctk.CTkButton(
            google_frame,
            text="Enviar Consumo da Sessão Ativa",
            command=self.sync_to_google,
        )
        self.sync_to_google_button.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        export_frame = ctk.CTkFrame(tab)
        export_frame.grid(row=1, column=0, padx=20, pady=20, sticky="ew")
        export_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            export_frame,
            text="Exportação Local",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, pady=10)

        self.export_button = ctk.CTkButton(
            export_frame,
            text="Exportar Sessão Ativa para Excel (.xlsx)",
            command=self.export_to_excel,
        )
        self.export_button.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        self.admin_status_label = ctk.CTkLabel(tab, text="")
        self.admin_status_label.grid(row=2, column=0, padx=20, pady=10, sticky="w")

    def sync_from_google(self):
        if not messagebox.askyesno(
            "Confirmar",
            "Isso irá baixar e atualizar os dados de estudantes e reservas. Deseja continuar?",
        ):
            return

        self.admin_status_label.configure(
            text="Sincronizando... Isso pode levar um momento."
        )
        self.update_idletasks()
        try:
            self.facade.sync_from_google_sheets()
            messagebox.showinfo(
                "Sucesso", "Dados baixados e sincronizados com sucesso!"
            )
            self.admin_status_label.configure(text="Sincronização concluída.")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha na sincronização:\n{e}")
            self.admin_status_label.configure(text="Falha na sincronização.")

    def sync_to_google(self):
        if not self.active_session_id:
            messagebox.showwarning(
                "Aviso",
                "Nenhuma sessão ativa. Selecione uma sessão para enviar os dados de consumo.",
            )
            return

        self.admin_status_label.configure(text="Enviando dados para o Google Sheets...")
        self.update_idletasks()
        try:
            self.facade.sync_to_google_sheets()
            messagebox.showinfo(
                "Sucesso", "Dados de consumo da sessão ativa enviados com sucesso!"
            )
            self.admin_status_label.configure(text="Envio concluído.")
        except RegistrationCoreError as e:
            messagebox.showerror("Erro", f"Falha no envio:\n{e}")
            self.admin_status_label.configure(text="Falha no envio.")

    def export_to_excel(self):
        if not self.active_session_id:
            messagebox.showwarning(
                "Aviso", "Nenhuma sessão ativa. Selecione uma sessão para exportar."
            )
            return

        self.admin_status_label.configure(text="Exportando para Excel...")
        self.update_idletasks()
        try:
            filepath = self.facade.export_session_to_xlsx()
            messagebox.showinfo(
                "Sucesso", f"Arquivo Excel salvo com sucesso em:\n{filepath}"
            )
            self.admin_status_label.configure(text="Exportação concluída.")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha na exportação:\n{e}")
            self.admin_status_label.configure(text="Falha na exportação.")


if __name__ == "__main__":
    app = App()
    app.mainloop()
