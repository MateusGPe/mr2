# gestao_refeitorio/app_principal.py

import traceback
from tkinter import messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from registro.importar.facade import FachadaImportacao
from registro.nucleo.facade import FachadaRegistro

from registro.abas.aba_dashboard import AbaDashboard
from registro.abas.aba_alunos import AbaAlunos
from registro.abas.aba_reservas import AbaReservas
from registro.abas.aba_consumo import AbaConsumo
from registro.abas.aba_importacao import AbaImportacao


class App(ttk.Window):
    def __init__(self):
        super().__init__(themename="litera", title="Sistema de Gestão de Refeitório")

        if not self._inicializar_fachadas():
            self.destroy()
            return

        self._criar_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _inicializar_fachadas(self):
        try:
            self.fachada_nucleo = FachadaRegistro()
            self.fachada_importacao = FachadaImportacao(self.fachada_nucleo)
            return True
        except Exception:
            Messagebox.show_error(
                "Não foi possível iniciar o backend. Verifique o console.", "Erro Fatal"
            )
            traceback.print_exc()
            return False

    def _on_closing(self):
        if messagebox.askokcancel("Sair", "Deseja realmente sair?"):
            self.fachada_nucleo.fechar_conexao()
            self.destroy()

    def _criar_widgets(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(expand=True, fill=BOTH, padx=10, pady=10)
        main_frame.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)

        notebook = ttk.Notebook(main_frame)
        notebook.grid(row=0, column=0, sticky=NSEW)

        aba_dashboard = AbaDashboard(notebook, self.fachada_nucleo)
        aba_alunos = AbaAlunos(notebook, self.fachada_nucleo)
        aba_reservas = AbaReservas(notebook, self.fachada_nucleo)
        aba_consumo = AbaConsumo(notebook, self.fachada_nucleo)
        aba_importacao = AbaImportacao(
            notebook, self.fachada_nucleo, self.fachada_importacao
        )

        notebook.add(aba_dashboard, text=" 📊 Início ")
        notebook.add(aba_consumo, text=" ✅ Registro de Consumo ")
        notebook.add(aba_alunos, text=" 👤 Alunos ")
        notebook.add(aba_reservas, text=" 📅 Reservas ")
        notebook.add(aba_importacao, text=" 🔄 Importar/Exportar ")
