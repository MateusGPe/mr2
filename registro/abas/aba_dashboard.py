# gestao_refeitorio/abas/aba_dashboard.py

import ttkbootstrap as ttk
from ttkbootstrap.constants import HORIZONTAL, NSEW, X


class AbaDashboard(ttk.Frame):
    def __init__(self, parent, fachada_nucleo):
        super().__init__(parent)
        self.fachada_nucleo = fachada_nucleo
        self._criar_widgets()
        self._carregar_estatisticas()

    def _criar_widgets(self):
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=X, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text="Bem-vindo ao Sistema de Gestão de Refeitório!",
            font=("Helvetica", 24, "bold"),
            bootstyle="primary",
        ).pack(pady=(0, 5), anchor="w")
        ttk.Label(
            header_frame,
            text="Gerencie alunos, reservas e consumo com facilidade.",
            font=("Helvetica", 12),
            bootstyle="secondary",
        ).pack(pady=0, anchor="w")

        ttk.Separator(self, orient=HORIZONTAL).pack(fill=X, padx=10, pady=15)

        stats_frame = ttk.Frame(self)
        stats_frame.pack(fill=X, expand=True, padx=10, pady=10)
        stats_frame.columnconfigure((0, 1, 2), weight=1)

        self.card_alunos_ativos = self._criar_stat_card(
            stats_frame, 0, "Alunos Ativos", "0", "success"
        )
        self.card_reservas_hoje = self._criar_stat_card(
            stats_frame, 1, "Reservas Hoje", "0", "info"
        )
        self.card_consumo_ontem = self._criar_stat_card(
            stats_frame, 2, "Consumo Ontem", "0", "warning"
        )

    def _criar_stat_card(self, parent, column, label, value, style):
        card = ttk.Frame(parent, padding=20, bootstyle=style)
        card.grid(row=0, column=column, sticky=NSEW, padx=10, pady=10)
        card.columnconfigure(0, weight=1)

        value_label = ttk.Label(
            card,
            text=value,
            font=("Helvetica", 36, "bold"),
            bootstyle=f"inverse-{style}",
        )
        value_label.grid(row=0, column=0, sticky="nsew")

        label_text = ttk.Label(
            card, text=label, font=("Helvetica", 12), bootstyle=f"inverse-{style}"
        )
        label_text.grid(row=1, column=0, sticky="nsew")

        return card

    def _carregar_estatisticas(self):
        # TODO: Implementar a lógica real para buscar e exibir estatísticas
        try:
            # Exemplo de como poderia ser:
            # num_alunos_ativos = self.fachada_nucleo.contar_alunos_ativos()
            # num_reservas_hoje = self.fachada_nucleo.contar_reservas_hoje()
            # num_consumo_ontem = self.fachada_nucleo.contar_consumo_ontem()

            # Atualizar os cards
            # value_label = self.card_alunos_ativos.winfo_children()[0]
            # value_label.config(text=str(num_alunos_ativos))
            pass
        except Exception:
            # Em caso de erro, os placeholders (0) permanecerão visíveis
            pass
