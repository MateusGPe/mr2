"""Testes funcionais headless para CardsApp."""

import tkinter as tk
from pathlib import Path
from unittest.mock import patch

from ttkbootstrap import Style

from registro.cards.app import CardsApp


def test_cards_app_fluxo_completo(app_root, tmp_path: Path, mock_messagebox):
    estudantes_fake = [
        {"name": "Alice Silva", "register": "IQ3000001", "turma": "1º A"},
        {"name": "Bruno Costa", "register": "IQ3000002", "turma": "1º B"},
    ]
    arq_csv = tmp_path / "alunos.csv"
    arq_csv.write_text("nome,prontuario,turma\n", encoding="utf-8")
    out_pdf = tmp_path / "crachas.pdf"
    out_html = tmp_path / "crachas.html"

    def _fake_window_init(self, *args, **kwargs):
        top = tk.Toplevel(app_root)
        self.__dict__.update(top.__dict__)
        self._style = Style()

    with (
        patch("ttkbootstrap.Window.__init__", _fake_window_init),
        patch.object(CardsApp, "_tentar_carregar_padrao_inicial"),
        patch(
            "registro.cards.app.load_students_from_file",
            return_value=estudantes_fake,
        ),
        patch(
            "registro.cards.app.filedialog.askopenfilename",
            return_value=str(arq_csv),
        ),
        patch("registro.cards.app.generate_cards_pdf") as mock_pdf,
        patch("registro.cards.app.generate_cards_html") as mock_html,
    ):
        app = CardsApp()
        try:
            app._selecionar_arquivo()
            assert len(app.students_raw) == 2
            assert len(app.students_filtered) == 2

            app.busca_var.set("Alice")
            app._filtrar_estudantes()
            assert len(app.students_filtered) == 1

            app.busca_var.set("")
            app._desmarcar_todas_turmas()
            assert len(app.students_filtered) == 0

            app._marcar_todas_turmas()
            assert len(app.students_filtered) == 2

            opcoes = app._obter_opcoes()
            assert opcoes.cols == 3
            assert opcoes.rows == 7

            with patch(
                "registro.cards.app.filedialog.asksaveasfilename",
                return_value=str(out_pdf),
            ):
                app._exportar_pdf()
            mock_pdf.assert_called_once()

            with patch(
                "registro.cards.app.filedialog.asksaveasfilename",
                return_value=str(out_html),
            ):
                app._exportar_html()
            mock_html.assert_called_once()
        finally:
            app.destroy()
