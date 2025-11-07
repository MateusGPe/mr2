# gestao_refeitorio/abas/aba_dashboard.py

import ttkbootstrap as ttk
from ttkbootstrap.constants import *


class AbaDashboard(ttk.Frame):
    def __init__(self, parent, fachada_nucleo):
        super().__init__(parent, padding=20)
        self.fachada_nucleo = fachada_nucleo
        self._criar_widgets()

    def _criar_widgets(self):
        ttk.Label(
            self,
            text="Bem-vindo, Administrador!",
            font=("Helvetica", 24, "bold"),
            bootstyle="primary",
        ).pack(pady=10)
        ttk.Label(
            self,
            text="Utilize as abas para navegar.",
            font=("Helvetica", 12),
            bootstyle="secondary",
        ).pack(pady=(0, 20))

        stats_frame = ttk.Frame(self)
        stats_frame.pack(fill=X, expand=True, pady=20)
        stats_frame.columnconfigure((0, 1, 2), weight=1)

        self._criar_stat_card(stats_frame, 0, "Alunos Ativos", "N/A", "success")
        self._criar_stat_card(stats_frame, 1, "Reservas Hoje", "N/A", "info")
        self._criar_stat_card(stats_frame, 2, "Consumo Ontem", "N/A", "warning")

    def _criar_stat_card(self, parent, column, label, value, style):
        card = ttk.Frame(parent, padding=20, bootstyle=style)
        card.grid(row=0, column=column, sticky=NSEW, padx=10)
        ttk.Label(
            card,
            text=value,
            font=("Helvetica", 30, "bold"),
            bootstyle=f"{style}-inverse",
        ).pack()
        ttk.Label(
            card, text=label, font=("Helvetica", 12), bootstyle=f"{style}-inverse"
        ).pack()
