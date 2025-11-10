# gestao_refeitorio/app_principal.py

import traceback
from tkinter import messagebox
import tkinter as tk

import ttkbootstrap as ttk
from ttkbootstrap.constants import EW, NSEW

from registro.abas.aba_alunos import AbaAlunos
from registro.abas.aba_dashboard import AbaDashboard
from registro.abas.aba_importacao import AbaImportacao
from registro.abas.aba_reservas import AbaReservas
from registro.importar.facade import FachadaImportacao
from registro.nucleo.facade import FachadaRegistro


class App(ttk.Window):
    def __init__(self):
        super().__init__(themename="litera", title="Sistema de Gestão de Refeitório")
        self.geometry("1280x800")

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
            messagebox.showerror(
                "Erro Fatal", "Não foi possível iniciar o backend. Verifique o console."
            )
            traceback.print_exc()
            return False

    def _on_closing(self):
        # if messagebox.askokcancel("Sair", "Deseja realmente sair?"):
        try:
            self.fachada_nucleo.fechar_conexao()
        except Exception:
            pass
        self.destroy()

    def _criar_widgets(self):
        # Configuração do grid principal da janela
        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        style = ttk.Style()
        style.configure("Nav.TFrame", background="#f0f0f0")
        # --- Frame de Navegação (Sidebar) ---
        navigation_frame = ttk.Frame(
            self,
            # bootstyle="secondary",
            style="Nav.TFrame",
            padding=10,
        )
        navigation_frame.grid(row=0, column=0, sticky=NSEW)
        navigation_frame.rowconfigure(
            5, weight=1
        )  # Espaço para empurrar o botão de sair para baixo

        # --- Container de Conteúdo ---
        self.content_frame = ttk.Frame(self, padding=20)
        self.content_frame.grid(row=0, column=1, sticky=NSEW)
        self.content_frame.rowconfigure(0, weight=1)
        self.content_frame.columnconfigure(0, weight=1)

        # --- Dicionário para armazenar os frames (antigas abas) ---
        self.frames = {}

        # --- Páginas (Frames) ---
        paginas = {
            "dashboard": (AbaDashboard, "📊"),
            "alunos": (AbaAlunos, "👤"),
            "reservas": (AbaReservas, "📅"),
            "importacao": (AbaImportacao, "🔄"),
        }
        style = ttk.Style()
        style.configure(
            "Custom.TButton",
            background="#f0f0f0",
            foreground="#000000",
            relief="flat",
            padding=4,
        )
        style.map(
            "Custom.TButton",
            background=[("active", "#ebebeb")],
            foreground=[("active", "red")],
        )
        # --- Criação dos botões de navegação e dos frames de conteúdo ---
        for i, (nome, (FrameClass, texto_botao)) in enumerate(paginas.items()):
            # Cria o frame
            if nome == "importacao":
                frame = FrameClass(
                    self.content_frame, self.fachada_nucleo, self.fachada_importacao
                )
            else:
                frame = FrameClass(self.content_frame, self.fachada_nucleo)

            self.frames[nome] = frame
            frame.grid(row=0, column=0, sticky=NSEW)

            # Cria o botão de navegação
            btn = ttk.Button(
                navigation_frame,
                text=texto_botao,
                command=lambda n=nome: self.show_frame(n),
                # bootstyle="outline-secondary",
                style="Custom.TButton",
            )
            btn.grid(row=i, column=0, sticky=EW, pady=5)

        # Botão de sair no final da sidebar
        btn_sair = ttk.Button(
            navigation_frame,
            text="❌",
            command=self._on_closing,
            style="Custom.TButton",
        )
        btn_sair.grid(row=6, column=0, sticky=EW, pady=10)

        # Mostra a página inicial
        self.show_frame("dashboard")

    def show_frame(self, nome_pagina):
        """Esconde todos os frames e mostra apenas o selecionado."""
        for frame in self.frames.values():
            frame.grid_remove()  # Usa grid_remove para não perder a configuração do grid

        frame_ativo = self.frames[nome_pagina]
        frame_ativo.grid()


if __name__ == "__main__":
    app = App()
    app.mainloop()
