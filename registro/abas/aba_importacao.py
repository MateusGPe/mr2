# gestao_refeitorio/abas/aba_importacao.py

import csv
import tkinter as tk
import traceback
from datetime import datetime
from tkinter import filedialog

import ttkbootstrap as ttk
from ttkbootstrap.constants import EW, LEFT, NSEW, E, W, X
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.localization.msgcat import MessageCatalog

from registro.controles.rounded_button import RoundedButton
from registro.controles.treeview_simples import TreeviewSimples
from registro.nucleo.exceptions import ErroSessaoNaoAtiva


class AbaImportacao(ttk.Frame):
    def __init__(self, parent, fachada_nucleo, fachada_importacao):
        super().__init__(parent)
        self.fachada_nucleo = fachada_nucleo
        self.fachada_importacao = fachada_importacao
        self.linhas_analisadas = []

        self.sumario_label: ttk.Label
        self.review_table: TreeviewSimples
        self.file_path_var: tk.StringVar
        self.import_type_var: tk.StringVar
        self.step1_frame: ttk.Frame
        self.step2_frame: ttk.Frame
        self.step3_frame: ttk.Frame

        self.review_coldata = [
            {"text": "Linha", "width": 50},
            {"text": "Dados do Arquivo", "stretch": True},
            {"text": "Status", "width": 100},
            {"text": "Ação Sugerida", "width": 120},
            {"text": "Sugestão (Similaridade)", "stretch": True},
        ]
        self._criar_widgets()

    def _criar_widgets(self):
        """
        Método revisado para usar um layout de grid para os painéis principais
        e um layout de wizard para a importação.
        """
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)
        self.rowconfigure(2, weight=0)

        import_frame = self._criar_painel_importacao(self)
        import_frame.grid(row=0, column=0, sticky=NSEW, padx=(0, 5))

        ttk.Separator(self, orient="horizontal").grid(
            row=1, column=0, sticky="ew", padx=5, pady=10
        )

        export_frame = self._criar_painel_exportacao(self)
        export_frame.grid(row=2, column=0, sticky=NSEW, padx=(5, 0), pady=(0, 10))

    def _toggle_widgets_state(self, parent_widget, state: str):
        """Habilita ou desabilita recursivamente todos os widgets filhos."""
        for widget in parent_widget.winfo_children():
            try:
                if isinstance(widget, RoundedButton) and "DateEntry" in str(
                    widget.master
                ):
                    continue
                widget.config(state=state)
            except (tk.TclError, AttributeError):
                pass
            self._toggle_widgets_state(widget, state)

    def _criar_painel_importacao(self, parent):
        container = ttk.Frame(parent, padding=0)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        ttk.Label(
            container,
            text="📥 Assistente de Importação",
            font=("-size 14 -weight bold"),
        ).grid(row=0, column=0, sticky=EW, padx=(5, 20), pady=(0, 10))

        wizard_area = ttk.Frame(container, padding=(5, 15, 20, 15))
        wizard_area.grid(row=1, column=0, sticky=NSEW)
        wizard_area.rowconfigure(0, weight=1)
        wizard_area.columnconfigure(0, weight=1)

        self.step1_frame = self._criar_passo_1_selecao(wizard_area)
        self.step2_frame = self._criar_passo_2_revisao(wizard_area)
        self.step3_frame = self._criar_passo_3_sumario(wizard_area)

        self.step1_frame.grid(row=0, column=0, sticky="NEW")

        return container

    def _criar_passo_1_selecao(self, parent):
        step1 = ttk.Frame(parent)

        ttk.Label(step1, text="Passo 1: Selecionar Arquivo", font="-weight bold").pack(
            fill=X
        )
        ttk.Separator(step1).pack(fill="both", pady=(5, 15))

        content = ttk.Frame(step1)
        content.pack(fill=X, expand=True)
        content.columnconfigure(1, weight=1)

        type_frame = ttk.Frame(content)
        type_frame.grid(row=0, column=0, columnspan=2, sticky="NEW", pady=(0, 15))
        ttk.Label(type_frame, text="Tipo de Arquivo:").pack(side=LEFT, padx=(0, 10))
        self.import_type_var = tk.StringVar(value="detalhado")
        ttk.Radiobutton(
            type_frame,
            text="CSV Detalhado (com reservas)",
            variable=self.import_type_var,
            value="detalhado",
        ).pack(side=LEFT, padx=(0, 10))
        ttk.Radiobutton(
            type_frame,
            text="Lista Simples (apenas alunos)",
            variable=self.import_type_var,
            value="simples",
        ).pack(side=LEFT)

        ttk.Label(content, text="Fonte dos Dados:").grid(
            row=1, column=0, sticky=W, padx=(0, 10)
        )
        file_frame = ttk.Frame(content)
        file_frame.grid(row=1, column=1, sticky=EW)
        self.file_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.file_path_var, state="readonly").pack(
            side=LEFT, fill=X, expand=True
        )
        RoundedButton(
            file_frame, text="Procurar...", command=self._selecionar_arquivo_importacao
        ).pack(side=LEFT, padx=5)

        RoundedButton(
            step1,
            text="Analisar Arquivo",
            command=self._iniciar_analise,
            bootstyle="primary",
        ).pack(anchor=E, pady=(25, 0))

        return step1

    def _criar_passo_2_revisao(self, parent):
        step2 = ttk.Frame(parent)
        step2.columnconfigure(0, weight=1)
        step2.rowconfigure(2, weight=1)

        ttk.Label(step2, text="Passo 2: Revisar Dados", font="-weight bold").grid(
            row=0, column=0, sticky=EW
        )
        ttk.Separator(step2).grid(row=1, column=0, sticky=EW, pady=(5, 15))

        self.review_table = TreeviewSimples(
            step2,
            dados_colunas=self.review_coldata,
            header_bootstyle="info",
            select_bootstyle="info",
            height=12,
        )
        self.review_table.grid(row=2, column=0, sticky=NSEW)

        btn_frame = ttk.Frame(step2)
        btn_frame.grid(row=3, column=0, sticky=EW, pady=(15, 0))
        btn_frame.columnconfigure(1, weight=1)
        RoundedButton(
            btn_frame,
            text="Voltar",
            command=self._voltar_para_passo_1,
            bootstyle="outline-secondary",
        ).grid(row=0, column=0, sticky=W)
        RoundedButton(
            btn_frame,
            text="Confirmar e Importar",
            command=self._executar_importacao,
            bootstyle="success",
        ).grid(row=0, column=2, sticky=E)

        return step2

    def _criar_passo_3_sumario(self, parent):
        step3 = ttk.Frame(parent)
        step3.columnconfigure(0, weight=1)

        ttk.Label(
            step3, text="Passo 3: Sumário da Importação", font="-weight bold"
        ).grid(row=0, column=0, sticky=EW)
        ttk.Separator(step3).grid(row=1, column=0, sticky=EW, pady=(5, 15))

        sumario_frame = ttk.Frame(step3)
        sumario_frame.grid(row=2, column=0, sticky=EW)
        self.sumario_label = ttk.Label(
            sumario_frame, text="", font="-size 12", justify="left"
        )
        self.sumario_label.pack(pady=10, fill=X, expand=True)

        RoundedButton(
            sumario_frame,
            text="Nova Importação",
            command=self._resetar_importacao,
            bootstyle="primary",
        ).pack(pady=10)

        return step3

    def _selecionar_arquivo_importacao(self):
        filepath = filedialog.askopenfilename(
            title="Selecione o arquivo para importação",
            filetypes=(
                ("Arquivos CSV/TXT", "*.csv *.txt"),
                ("Todos os arquivos", "*.*"),
            ),
        )
        if filepath:
            self.file_path_var.set(filepath)

    def _iniciar_analise(self):
        caminho = self.file_path_var.get()
        if not caminho:
            Messagebox.show_warning("Selecione um arquivo para análise.", "Aviso")
            return
        try:
            detalhado = self.import_type_var.get() == "detalhado"
            self.linhas_analisadas = self.fachada_importacao.analisar_arquivo_csv(
                caminho, detalhado
            )
            self._carregar_dados_revisao()

            self.step1_frame.grid_forget()
            self.step2_frame.grid(row=0, column=0, sticky=NSEW)
        except Exception:  # pylint: disable=broad-exception-caught
            Messagebox.show_error(
                "Falha ao analisar arquivo. Verifique o console.", "Erro"
            )
            traceback.print_exc()

    def _voltar_para_passo_1(self):
        self.step2_frame.grid_forget()
        self.step1_frame.grid(row=0, column=0, sticky="NEW")
        self._toggle_widgets_state(self.step1_frame, "normal")

    def _carregar_dados_revisao(self):
        dados = []
        for linha in self.linhas_analisadas:
            dados_str = ", ".join(
                f"{k}: {v}" for k, v in linha["dados_originais"].items()
            )
            sug = linha["sugestoes"][0] if linha["sugestoes"] else {}
            sug_txt = (
                f"{sug.get('nome', 'N/A')} ({sug.get('pontuacao', 0):.2f}%)"
                if sug
                else "Nenhuma"
            )
            dados.append(
                (
                    linha["id_linha"],
                    dados_str,
                    linha["status"],
                    linha["acao_final_sugerida"],
                    sug_txt,
                )
            )
        self.review_table.construir_dados_tabela(dados)

    def _executar_importacao(self):
        if not self.linhas_analisadas or Messagebox.okcancel(
            "Confirmar Importação",
            "Esta ação irá modificar o banco de dados. Deseja continuar?",
        ) != MessageCatalog.translate("OK"):
            return
        try:
            resumo = self.fachada_importacao.executar()

            self.step2_frame.grid_forget()
            self._mostrar_sumario_importacao(resumo)
            self.step3_frame.grid(row=0, column=0, sticky=NSEW)
        except Exception:  # pylint: disable=broad-exception-caught
            Messagebox.show_error(
                "Erro ao executar importação. Verifique o console.", "Erro"
            )
            traceback.print_exc()

    def _mostrar_sumario_importacao(self, resumo):
        texto = (
            "✅ Importação Concluída com Sucesso!\n\n"
            f"  • Registros processados: {resumo.get('total_processados', 0)}\n"
            f"  • Alunos criados/atualizados: {resumo.get('alunos_processados', 0)}\n"
            f"  • Reservas criadas/atualizadas: {resumo.get('reservas_processadas', 0)}\n"
            f"  • Erros encontrados: {resumo.get('erros', 0)}"
        )
        self.sumario_label.config(text=texto)

    def _resetar_importacao(self):
        # Limpa os dados
        self.file_path_var.set("")
        self.review_table.deletar_linhas()
        self.linhas_analisadas = []

        self.step2_frame.grid_forget()
        self.step3_frame.grid_forget()
        self.step1_frame.grid(row=0, column=0, sticky="NEW")

        self._toggle_widgets_state(self.step1_frame, "normal")
        self._toggle_widgets_state(self.step2_frame, "normal")

    def _criar_painel_exportacao(self, parent):
        container = ttk.Frame(parent, padding=10)
        container.columnconfigure((0, 1, 2), weight=1)

        ttk.Label(
            container, text="📤 Exportar Relatórios", font=("-size 14 -weight bold")
        ).grid(row=0, column=0, columnspan=3, sticky=W, pady=(0, 10))

        ttk.Label(
            container, text="Exporte os dados do sistema para arquivos CSV ou XLSX."
        ).grid(row=1, column=0, columnspan=3, sticky=W, pady=(0, 15))

        RoundedButton(
            container,
            text="Exportar Alunos (CSV)",
            command=lambda: self._exportar_dados("alunos"),
            bootstyle="primary-outline",
        ).grid(row=2, column=0, sticky=EW, padx=(0, 5))

        RoundedButton(
            container,
            text="Exportar Reservas (CSV)",
            command=lambda: self._exportar_dados("reservas"),
            bootstyle="primary-outline",
        ).grid(row=2, column=1, sticky=EW, padx=5)

        RoundedButton(
            container,
            text="Exportar Consumo da Sessão (XLSX)",
            command=lambda: self._exportar_dados("consumo"),
            bootstyle="primary-outline",
        ).grid(row=2, column=2, sticky=EW, padx=(5, 0))

        return container

    def _exportar_dados(self, tipo: str):
        try:
            default_filename, extension, filetypes = (
                f"export_{tipo}_{datetime.now().strftime('%Y%m%d')}",
                ".csv",
                [("CSV files", "*.csv")],
            )
            if tipo == "consumo":
                extension, filetypes = ".xlsx", [("Excel files", "*.xlsx")]

            filepath = filedialog.asksaveasfilename(
                defaultextension=extension,
                filetypes=filetypes,
                initialfile=default_filename,
            )
            if not filepath:
                return

            if tipo == "consumo":
                caminho = self.fachada_nucleo.exportar_sessao_para_xlsx(filepath)
                Messagebox.show_info(
                    "Sucesso", f"Relatório de consumo exportado para:\n{caminho}"
                )
                return

            headers_map = {
                "alunos": ["id", "prontuario", "nome", "ativo", "grupos"],
                "reservas": [
                    "id",
                    "prontuario_estudante",
                    "nome_estudante",
                    "prato",
                    "data",
                    "cancelada",
                ],
            }
            dados = getattr(self.fachada_nucleo, f"listar_{tipo}")()
            headers = headers_map.get(tipo, [])

            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                for d in dados:
                    if "grupos" in d and isinstance(d.get("grupos"), list):
                        d["grupos"] = ", ".join(d["grupos"])
                writer.writerows(dados)
            Messagebox.show_info(
                "Sucesso",
                f"Dados de {tipo} exportados para:\n{filepath}",
            )
        except ErroSessaoNaoAtiva:
            Messagebox.show_warning(
                "Nenhuma sessão ativa para exportar o consumo.",
                "Aviso",
            )
        except Exception:  # pylint: disable=broad-exception-caught
            Messagebox.show_error(
                "Falha na exportação. Verifique o console.",
                "Erro",
            )
            traceback.print_exc()
