# gestao_refeitorio/app_principal.py

import traceback
from typing import Dict
from ttkbootstrap.dialogs import Messagebox

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
        super().__init__(themename="sandstone", title="Sistema de Gestão de Refeitório")
        self.geometry("1280x800")

        if not self._inicializar_fachadas():
            self.destroy()
            return

        self.selected: str
        self.buttons: Dict[str, ttk.Button] = {}
        self._criar_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _inicializar_fachadas(self):
        try:
            self.fachada_nucleo = FachadaRegistro()
            self.fachada_importacao = FachadaImportacao(self.fachada_nucleo)
            return True
        except Exception:
            Messagebox.show_error(
                "Erro Fatal",
                "Não foi possível iniciar o backend. Verifique o console.",
            )
            traceback.print_exc()
            return False

    def _on_closing(self):
        try:
            self.fachada_nucleo.fechar_conexao()
        except Exception:
            pass
        self.destroy()

    def _criar_widgets(self):
        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        navigation_frame = ttk.Frame(
            self,
            bootstyle="dark",
            padding=(5, 0, 0, 5),
        )
        navigation_frame.grid(row=0, column=0, sticky=NSEW)
        navigation_frame.rowconfigure(5, weight=1)
        self.content_frame = ttk.Frame(self, padding=20)
        self.content_frame.grid(row=0, column=1, sticky=NSEW)
        self.content_frame.rowconfigure(0, weight=1)
        self.content_frame.columnconfigure(0, weight=1)
        self.frames: Dict[str, ttk.Frame] = {}
        paginas = {
            "dashboard": (AbaDashboard, "📊"),
            "alunos": (AbaAlunos, "👤"),
            "reservas": (AbaReservas, "📅"),
            "importacao": (AbaImportacao, "🔄"),
        }
        for i, (nome, (FrameClass, texto_botao)) in enumerate(paginas.items()):
            if nome == "importacao":
                frame = FrameClass(
                    self.content_frame, self.fachada_nucleo, self.fachada_importacao
                )
            else:
                frame = FrameClass(self.content_frame, self.fachada_nucleo)

            self.frames[nome] = frame
            btn = ttk.Button(
                navigation_frame,
                text=texto_botao,
                command=lambda n=nome: self.show_frame(n),
                bootstyle="dark",
                padding=(3, 6),
            )
            btn.grid(row=i, column=0, sticky=EW, pady=2)
            self.buttons[nome] = btn

        self.selected = "dashboard"
        self.buttons[self.selected].config(bootstyle="light")

        self.frames[self.selected].grid(row=0, column=0, sticky=NSEW)

        btn_sair = ttk.Button(
            navigation_frame,
            text="❌",
            command=self._on_closing,
            bootstyle="dark",
        )
        btn_sair.grid(row=6, column=0, sticky=EW, pady=10, padx=(0, 5))
        self.show_frame("dashboard")

    def show_frame(self, nome_pagina):
        """Esconde tod os os frames e mostra apenas o selecionado."""
        if self.selected == nome_pagina:
            frame_ativo = self.frames[nome_pagina]
            frame_ativo.focus()
            return

        for frame in self.frames.values():
            frame.grid_remove()

        self.buttons[self.selected].config(bootstyle="dark")
        self.buttons[nome_pagina].config(bootstyle="light")
        self.selected = nome_pagina
        frame_ativo = self.frames[nome_pagina]

        frame_ativo.grid(row=0, column=0, sticky=NSEW)
        self.after(10, frame_ativo.focus)


if __name__ == "__main__":
    app = App()
    app.mainloop()
