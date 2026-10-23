# ----------------------------------------------------------------------------
# Arquivo: registro/cards/app.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Interface gráfica moderna (GUI) para geração de crachás e cartões de identificação.
Permite selecionar arquivos CSV/Excel, pré-visualizar estudantes, customizar leiaute
da folha A4 e exportar diretamente para PDF (vetorial) ou HTML.
"""

from pathlib import Path
import os
import sys
from tkinter import filedialog
from typing import Dict, List

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, END, EW, LEFT, RIGHT, W, X, Y
from ttkbootstrap.dialogs import Messagebox

from registro.cards.generator import (
    CardOptions,
    generate_cards_html,
    generate_cards_pdf,
    load_students_from_file,
)


class CardsApp(ttk.Window):
    """Janela principal da aplicação gráfica de geração de crachás."""

    def __init__(self):
        super().__init__(themename="sandstone", title="Gerador de Crachás e Cartões QR")
        self.geometry("980x700")
        self.minsize(800, 600)

        self.students_raw: List[Dict[str, str]] = []
        self.students_filtered: List[Dict[str, str]] = []

        self._iniciar_variaveis()
        self._criar_widgets()
        self._tentar_carregar_padrao_inicial()

    def _iniciar_variaveis(self):
        """Inicializa variáveis de estado do Tkinter."""
        self.caminho_arquivo_var = ttk.StringVar(value="")
        self.busca_var = ttk.StringVar(value="")
        self.status_var = ttk.StringVar(value="Nenhum arquivo carregado.")
        self.cols_var = ttk.IntVar(value=3)
        self.rows_var = ttk.IntVar(value=7)
        self.linhas_corte_var = ttk.BooleanVar(value=True)
        self.numero_pagina_var = ttk.BooleanVar(value=True)
        self.cabecalho_var = ttk.StringVar(value="")
        self.todas_turmas: List[str] = []
        self.turmas_vars: Dict[str, ttk.BooleanVar] = {}

    def _criar_widgets(self):
        """Monta a estrutura visual da aplicação."""
        # 1. Cabeçalho Principal
        header_frame = ttk.Frame(self, padding=(20, 15, 20, 10))
        header_frame.pack(fill=X)

        titulo = ttk.Label(
            header_frame,
            text="Gerador de Crachás e Cartões com QR Code",
            font=("Helvetica", 16, "bold"),
            bootstyle="primary",
        )
        titulo.pack(anchor=W)

        subtitulo = ttk.Label(
            header_frame,
            text="Importe discentes a partir de CSV ou Excel e exporte em alta precisão para impressão A4.",
            font=("Helvetica", 9),
            bootstyle="secondary",
        )
        subtitulo.pack(anchor=W, pady=(2, 0))

        # 2. Painel Superior: Seleção de Arquivo
        file_frame = ttk.Labelframe(self, text=" Fonte de Dados ", padding=15)
        file_frame.pack(fill=X, padx=20, pady=(5, 10))

        entry_file = ttk.Entry(file_frame, textvariable=self.caminho_arquivo_var, state="readonly")
        entry_file.pack(side=LEFT, fill=X, expand=True, padx=(0, 10))

        btn_selecionar = ttk.Button(
            file_frame,
            text="Selecionar Arquivo...",
            bootstyle="primary",
            command=self._selecionar_arquivo,
        )
        btn_selecionar.pack(side=LEFT, padx=(0, 6))

        btn_padrao = ttk.Button(
            file_frame,
            text="Carregar Padrão",
            bootstyle="secondary-outline",
            command=self._carregar_arquivo_padrao,
        )
        btn_padrao.pack(side=LEFT)

        # 3. Painel Central: Pré-visualização com Busca
        content_frame = ttk.Frame(self, padding=(20, 0, 20, 10))
        content_frame.pack(fill=BOTH, expand=True)

        list_labelframe = ttk.Labelframe(content_frame, text=" Pré-visualização dos Discentes ", padding=10)
        list_labelframe.pack(fill=BOTH, expand=True)

        # Barra de Busca na tabela
        search_bar = ttk.Frame(list_labelframe)
        search_bar.pack(fill=X, pady=(0, 8))

        lbl_busca = ttk.Label(search_bar, text="Buscar:", font=("Helvetica", 9, "bold"))
        lbl_busca.pack(side=LEFT, padx=(0, 6))

        entry_busca = ttk.Entry(search_bar, textvariable=self.busca_var)
        entry_busca.pack(side=LEFT, fill=X, expand=True)
        self.busca_var.trace_add("write", lambda *_: self._filtrar_estudantes())

        btn_limpar_busca = ttk.Button(
            search_bar,
            text="Limpar",
            bootstyle="link",
            command=lambda: self.busca_var.set(""),
        )
        btn_limpar_busca.pack(side=LEFT, padx=(4, 12))

        # Menu suspenso para filtragem múltipla de turmas
        self.btn_turmas = ttk.Menubutton(
            search_bar,
            text="Turmas: Todas",
            bootstyle="outline-primary",
        )
        self.btn_turmas.pack(side=LEFT)
        self.menu_turmas = ttk.Menu(self.btn_turmas, tearoff=0)
        self.btn_turmas.configure(menu=self.menu_turmas)
        self._atualizar_menu_turmas()

        # Tabela Treeview
        tree_container = ttk.Frame(list_labelframe)
        tree_container.pack(fill=BOTH, expand=True)

        colunas = ("index", "register", "name", "turma")
        self.tree = ttk.Treeview(
            tree_container,
            columns=colunas,
            show="headings",
            bootstyle="primary",
            selectmode="extended",
        )
        self.tree.heading("index", text="#", anchor=W)
        self.tree.heading("register", text="Matrícula / Prontuário", anchor=W)
        self.tree.heading("name", text="Nome Completo", anchor=W)
        self.tree.heading("turma", text="Turma / Curso", anchor=W)

        self.tree.column("index", width=50, stretch=False)
        self.tree.column("register", width=180, stretch=False)
        self.tree.column("name", width=360, stretch=True)
        self.tree.column("turma", width=160, stretch=False)

        scroll_y = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        scroll_x = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        tree_container.rowconfigure(0, weight=1)
        tree_container.columnconfigure(0, weight=1)

        # Status Bar da Tabela
        lbl_status = ttk.Label(list_labelframe, textvariable=self.status_var, font=("Helvetica", 8))
        lbl_status.pack(anchor=W, pady=(6, 0))

        # 4. Painel de Opções de Leiaute
        options_frame = ttk.Labelframe(self, text=" Opções do Leiaute A4 ", padding=12)
        options_frame.pack(fill=X, padx=20, pady=(0, 10))

        row1 = ttk.Frame(options_frame)
        row1.pack(fill=X, pady=(0, 6))

        ttk.Label(row1, text="Grade (Colunas x Linhas):", font=("Helvetica", 9, "bold")).pack(side=LEFT, padx=(0, 6))

        combo_cols = ttk.Combobox(
            row1,
            textvariable=self.cols_var,
            values=[2, 3, 4],
            state="readonly",
            width=3,
        )
        combo_cols.pack(side=LEFT, padx=(0, 4))
        combo_cols.bind("<<ComboboxSelected>>", lambda _: self._atualizar_status())

        ttk.Label(row1, text="x").pack(side=LEFT, padx=(0, 4))

        combo_rows = ttk.Combobox(
            row1,
            textvariable=self.rows_var,
            values=[4, 5, 6, 7, 8, 9, 10],
            state="readonly",
            width=3,
        )
        combo_rows.pack(side=LEFT, padx=(0, 15))
        combo_rows.bind("<<ComboboxSelected>>", lambda _: self._atualizar_status())

        check_cortes = ttk.Checkbutton(
            row1,
            text="Linhas de corte",
            variable=self.linhas_corte_var,
            bootstyle="round-toggle",
        )
        check_cortes.pack(side=LEFT, padx=(0, 15))

        check_paginas = ttk.Checkbutton(
            row1,
            text="Número da página",
            variable=self.numero_pagina_var,
            bootstyle="round-toggle",
        )
        check_paginas.pack(side=LEFT)

        row2 = ttk.Frame(options_frame)
        row2.pack(fill=X)

        ttk.Label(row2, text="Cabeçalho no Cartão:", font=("Helvetica", 9)).pack(side=LEFT, padx=(0, 6))
        entry_cabecalho = ttk.Entry(row2, textvariable=self.cabecalho_var)
        entry_cabecalho.pack(side=LEFT, fill=X, expand=True)

        # 5. Barra Inferior de Ações
        action_frame = ttk.Frame(self, padding=(20, 0, 20, 15))
        action_frame.pack(fill=X)

        btn_pdf = ttk.Button(
            action_frame,
            text="Exportar para PDF (.pdf)",
            bootstyle="success",
            command=self._exportar_pdf,
        )
        btn_pdf.pack(side=RIGHT, padx=(6, 0))

        btn_html = ttk.Button(
            action_frame,
            text="Exportar para HTML (.html)",
            bootstyle="info-outline",
            command=self._exportar_html,
        )
        btn_html.pack(side=RIGHT)

    def _tentar_carregar_padrao_inicial(self):
        """Tenta carregar automaticamente o arquivo students.csv padrão ao abrir."""
        candidatos = [
            Path("config/students.csv"),
            Path("students.csv"),
            Path(__file__).resolve().parent.parent.parent / "config" / "students.csv",
        ]
        for c in candidatos:
            if c.exists():
                try:
                    self._carregar_dados_de_caminho(c)
                    return
                except Exception:
                    continue

    def _selecionar_arquivo(self):
        """Abre caixa de diálogo para seleção de CSV ou XLSX."""
        arquivo = filedialog.askopenfilename(
            title="Selecionar Lista de Alunos",
            filetypes=[
                ("Arquivos Suportados", "*.csv *.xlsx *.xls"),
                ("Arquivos CSV", "*.csv"),
                ("Planilhas Excel", "*.xlsx *.xls"),
                ("Todos os Arquivos", "*.*"),
            ],
        )
        if arquivo:
            self._carregar_dados_de_caminho(Path(arquivo))

    def _carregar_arquivo_padrao(self):
        """Carrega explicitamente o arquivo padrão do sistema."""
        candidato = Path("config/students.csv")
        if not candidato.exists():
            candidato = Path("students.csv")

        if not candidato.exists():
            Messagebox.show_warning(
                "Arquivo Não Encontrado",
                "O arquivo padrão 'config/students.csv' não foi localizado.",
            )
            return

        self._carregar_dados_de_caminho(candidato)

    def _atualizar_menu_turmas(self):
        """Reconstrói as opções do menu suspenso de seleção múltipla de turmas."""
        self.menu_turmas.delete(0, END)
        if not self.todas_turmas:
            self.menu_turmas.add_command(label="Nenhuma turma disponível", state="disabled")
            self.btn_turmas.configure(text="Turmas: Nenhuma", state="disabled")
            return

        self.btn_turmas.configure(state="normal")
        self.menu_turmas.add_command(label="Marcar Todas", command=self._marcar_todas_turmas)
        self.menu_turmas.add_command(label="Desmarcar Todas", command=self._desmarcar_todas_turmas)
        self.menu_turmas.add_separator()

        for turma in self.todas_turmas:
            var = self.turmas_vars.get(turma)
            if var is None:
                var = ttk.BooleanVar(value=True)
                self.turmas_vars[turma] = var
            self.menu_turmas.add_checkbutton(
                label=turma,
                variable=var,
                command=self._on_turma_toggle,
            )

        self._atualizar_rotulo_botao_turmas()

    def _marcar_todas_turmas(self):
        """Marca todas as turmas para exibição."""
        for var in self.turmas_vars.values():
            var.set(True)
        self._atualizar_rotulo_botao_turmas()
        self._filtrar_estudantes()

    def _desmarcar_todas_turmas(self):
        """Desmarca todas as turmas da filtragem."""
        for var in self.turmas_vars.values():
            var.set(False)
        self._atualizar_rotulo_botao_turmas()
        self._filtrar_estudantes()

    def _on_turma_toggle(self):
        """Disparado quando uma turma individual é marcada ou desmarcada no menu."""
        self._atualizar_rotulo_botao_turmas()
        self._filtrar_estudantes()

    def _atualizar_rotulo_botao_turmas(self):
        """Atualiza o texto exibido no botão do menu de seleção de turmas."""
        total = len(self.todas_turmas)
        if total == 0:
            self.btn_turmas.configure(text="Turmas: Nenhuma")
            return

        selecionadas = [t for t in self.todas_turmas if self.turmas_vars.get(t) and self.turmas_vars[t].get()]
        qtd = len(selecionadas)
        if qtd == total:
            self.btn_turmas.configure(text="Turmas: Todas")
        elif qtd == 0:
            self.btn_turmas.configure(text="Turmas: Nenhuma (0)")
        elif qtd == 1:
            nome_turma = selecionadas[0]
            if len(nome_turma) > 16:
                nome_turma = nome_turma[:14] + "…"
            self.btn_turmas.configure(text=f"Turma: {nome_turma}")
        else:
            self.btn_turmas.configure(text=f"Turmas: ({qtd}/{total})")

    def _carregar_dados_de_caminho(self, caminho: Path):
        """Carrega e popula a tabela com os dados do arquivo informado."""
        try:
            estudantes = load_students_from_file(caminho)
            self.students_raw = estudantes
            self.caminho_arquivo_var.set(str(caminho.resolve()))

            # Coleta todas as turmas únicas presentes no arquivo
            turmas_set = set()
            for s in estudantes:
                t = s.get("turma", "").strip()
                turmas_set.add(t if t else "(Sem Turma)")

            turmas_ordenadas = sorted([t for t in turmas_set if t != "(Sem Turma)"])
            if "(Sem Turma)" in turmas_set:
                turmas_ordenadas.append("(Sem Turma)")

            self.todas_turmas = turmas_ordenadas
            self.turmas_vars = {t: ttk.BooleanVar(value=True) for t in self.todas_turmas}
            self._atualizar_menu_turmas()
            self._filtrar_estudantes()
        except Exception as e:
            Messagebox.show_error(
                "Erro ao Carregar Arquivo",
                f"Não foi possível processar o arquivo:\n{e}",
            )

    def _filtrar_estudantes(self):
        """Aplica os filtros de turma e busca textual sobre os estudantes carregados."""
        termo = self.busca_var.get().strip().lower()
        turmas_ativas = {t for t in self.todas_turmas if self.turmas_vars.get(t) and self.turmas_vars[t].get()}

        resultado = []
        for s in self.students_raw:
            # 1. Filtro de turma
            turma_aluno = s.get("turma", "").strip() or "(Sem Turma)"
            if self.todas_turmas and turma_aluno not in turmas_ativas:
                continue

            # 2. Filtro de busca textual
            if termo:
                match_termo = (
                    termo in s.get("name", "").lower()
                    or termo in s.get("register", "").lower()
                    or termo in s.get("turma", "").lower()
                )
                if not match_termo:
                    continue

            resultado.append(s)

        self.students_filtered = resultado

        # Atualiza Treeview
        self.tree.delete(*self.tree.get_children())
        for idx, s in enumerate(self.students_filtered, 1):
            self.tree.insert(
                "",
                END,
                values=(
                    idx,
                    s.get("register", ""),
                    s.get("name", ""),
                    s.get("turma", ""),
                ),
            )

        self._atualizar_status()

    def _atualizar_status(self):
        """Atualiza o texto da barra de status."""
        total = len(self.students_raw)
        filtrados = len(self.students_filtered)
        cols = max(1, self.cols_var.get())
        rows = max(1, self.rows_var.get())
        por_pagina = cols * rows

        if total == 0:
            self.status_var.set("Nenhum discente carregado.")
            return

        paginas = (filtrados + por_pagina - 1) // por_pagina
        txt = f"Total: {total} alunos | Exibindo: {filtrados} | Estimativa: {paginas} página(s) A4 ({cols}x{rows} = {por_pagina}/pág)"
        self.status_var.set(txt)

    def _obter_opcoes(self) -> CardOptions:
        """Monta o objeto CardOptions a partir das configurações na tela."""
        return CardOptions(
            cols=max(1, self.cols_var.get()),
            rows=max(1, self.rows_var.get()),
            show_cut_lines=self.linhas_corte_var.get(),
            header_text=self.cabecalho_var.get().strip(),
            show_page_number=self.numero_pagina_var.get(),
        )

    def _perguntar_abrir_arquivo(self, caminho_arquivo: str):
        """Pergunta ao usuário se deseja abrir o arquivo gerado."""
        if hasattr(os, "startfile"):
            resposta = Messagebox.show_question(
                "Exportação Concluída",
                f"Cartões exportados com sucesso!\n\nArquivo:\n{caminho_arquivo}\n\nDeseja abrir o arquivo agora?",
            )
            if resposta == "Yes":
                try:
                    os.startfile(caminho_arquivo)
                except Exception:
                    pass
        else:
            Messagebox.show_info(
                "Exportação Concluída",
                f"Cartões exportados com sucesso em:\n{caminho_arquivo}",
            )

    def _exportar_pdf(self):
        """Gera o arquivo PDF com os estudantes atualmente filtrados/exibidos."""
        if not self.students_filtered:
            Messagebox.show_warning("Aviso", "Não há estudantes para exportar.")
            return

        destino = filedialog.asksaveasfilename(
            title="Salvar Cartões em PDF",
            defaultextension=".pdf",
            filetypes=[("Documento PDF", "*.pdf")],
            initialfile="cartoes_impressao.pdf",
        )
        if not destino:
            return

        try:
            opcoes = self._obter_opcoes()
            total = generate_cards_pdf(self.students_filtered, destino, opcoes)
            self._perguntar_abrir_arquivo(destino)
        except Exception as e:
            Messagebox.show_error("Erro na Exportação", f"Falha ao gerar PDF:\n{e}")

    def _exportar_html(self):
        """Gera o arquivo HTML com os estudantes atualmente filtrados/exibidos."""
        if not self.students_filtered:
            Messagebox.show_warning("Aviso", "Não há estudantes para exportar.")
            return

        destino = filedialog.asksaveasfilename(
            title="Salvar Cartões em HTML",
            defaultextension=".html",
            filetypes=[("Documento HTML", "*.html")],
            initialfile="cartoes_impressao.html",
        )
        if not destino:
            return

        try:
            opcoes = self._obter_opcoes()
            total = generate_cards_html(self.students_filtered, destino, opcoes)
            self._perguntar_abrir_arquivo(destino)
        except Exception as e:
            Messagebox.show_error("Erro na Exportação", f"Falha ao gerar HTML:\n{e}")


def main():
    """Ponto de entrada para a aplicação gráfica de crachás."""
    from registro.nucleo.logging_config import configurar_logging

    configurar_logging("cards")
    app = CardsApp()
    app.mainloop()


if __name__ == "__main__":
    main()
