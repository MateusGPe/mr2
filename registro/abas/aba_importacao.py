# gestao_refeitorio/abas/aba_importacao.py

import csv
import tkinter as tk
import traceback
from tkinter import filedialog

import ttkbootstrap as ttk
from ttkbootstrap.constants import HORIZONTAL, RIGHT, LEFT, NSEW, X, EW, W, E
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.tableview import Tableview

from registro.nucleo.exceptions import ErroSessaoNaoAtiva


class AbaImportacao(ttk.Frame):
    def __init__(self, parent, fachada_nucleo, fachada_importacao):
        super().__init__(parent)
        self.fachada_nucleo = fachada_nucleo
        self.fachada_importacao = fachada_importacao
        self.linhas_analisadas = []
        self._criar_widgets()

    def _criar_widgets(self):
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        paned = ttk.PanedWindow(self, orient=HORIZONTAL)
        paned.grid(row=0, column=0, sticky=NSEW, padx=10, pady=10)

        import_frame = self._criar_painel_importacao(paned)
        paned.add(import_frame, weight=2)

        export_frame = self._criar_painel_exportacao(paned)
        paned.add(export_frame, weight=1)

    def _criar_painel_importacao(self, parent):
        frame = ttk.Labelframe(parent, text=" 📥 Assistente de Importação ", padding=10)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.import_notebook = ttk.Notebook(frame)
        self.import_notebook.grid(row=0, column=0, sticky=NSEW)

        self._criar_passo_1_importacao()
        self._criar_passo_2_revisao()
        self._criar_passo_3_sumario()

        return frame

    def _criar_painel_exportacao(self, parent):
        frame = ttk.Labelframe(parent, text=" 📤 Exportar Relatórios ", padding=10)
        ttk.Button(
            frame,
            text="Exportar Alunos (CSV)",
            command=lambda: self._exportar_dados("alunos"),
        ).pack(fill=X, pady=5)
        ttk.Button(
            frame,
            text="Exportar Reservas (CSV)",
            command=lambda: self._exportar_dados("reservas"),
        ).pack(fill=X, pady=5)
        ttk.Button(
            frame,
            text="Exportar Consumo (XLSX)",
            command=lambda: self._exportar_dados("consumo"),
        ).pack(fill=X, pady=5)
        return frame

    def _criar_passo_1_importacao(self):
        step1 = ttk.Frame(self.import_notebook, padding=10)
        self.import_notebook.add(step1, text=" 1. Fonte ")

        self.import_type_var = tk.StringVar(value="detalhado")
        ttk.Radiobutton(
            step1,
            text="CSV Detalhado",
            variable=self.import_type_var,
            value="detalhado",
        ).pack(anchor=W)
        ttk.Radiobutton(
            step1, text="Lista Simples", variable=self.import_type_var, value="simples"
        ).pack(anchor=W)

        file_frame = ttk.Frame(step1)
        file_frame.pack(fill=X, pady=10)
        self.file_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.file_path_var, state="readonly").pack(
            side=LEFT, fill=X, expand=True
        )
        ttk.Button(
            file_frame, text="Procurar...", command=self._selecionar_arquivo_importacao
        ).pack(side=LEFT, padx=5)

        ttk.Button(
            step1, text="Analisar ➡️", command=self._iniciar_analise, bootstyle="primary"
        ).pack(anchor=E, pady=10)

    def _selecionar_arquivo_importacao(self):
        filepath = filedialog.askopenfilename(
            filetypes=(("CSV/TXT", "*.csv *.txt"), ("Todos", "*.*"))
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
            self.import_notebook.select(1)
        except Exception:
            Messagebox.show_error(
                "Falha ao analisar arquivo. Verifique o console.", "Erro"
            )
            traceback.print_exc()

    def _criar_passo_2_revisao(self):
        step2 = ttk.Frame(self.import_notebook, padding=10)
        step2.rowconfigure(0, weight=1)
        step2.columnconfigure(0, weight=1)
        self.import_notebook.add(step2, text=" 2. Revisão ", state="disabled")

        self.review_coldata = [
            {"text": "Linha", "width": 50},
            {"text": "Dados", "stretch": True},
            {"text": "Status"},
            {"text": "Ação"},
            {"text": "Sugestão", "stretch": True},
        ]
        self.review_table = Tableview(
            step2, coldata=self.review_coldata, bootstyle="info"
        )
        self.review_table.grid(row=0, column=0, sticky=NSEW, pady=5)

        btn_frame = ttk.Frame(step2)
        btn_frame.grid(row=1, column=0, sticky=EW)
        ttk.Button(
            btn_frame, text="⬅️ Voltar", command=lambda: self.import_notebook.select(0)
        ).pack(side=LEFT)
        ttk.Button(
            btn_frame,
            text="Confirmar e Importar ✔️",
            command=self._executar_importacao,
            bootstyle="success",
        ).pack(side=RIGHT)

    def _carregar_dados_revisao(self):
        self.import_notebook.tab(1, state="normal")
        dados = []
        for linha in self.linhas_analisadas:
            dados_str = ", ".join(
                f"{k}: {v}" for k, v in linha["dados_originais"].items()
            )
            sug = linha["sugestoes"][0] if linha["sugestoes"] else {}
            sug_txt = f"{sug.get('nome', 'N/A')} ({sug.get('pontuacao', 0)}%)"
            dados.append(
                (
                    linha["id_linha"],
                    dados_str,
                    linha["status"],
                    linha["acao_final_sugerida"],
                    sug_txt,
                )
            )
        self.review_table.build_table_data(self.review_coldata, dados)

    def _executar_importacao(self):
        if not self.linhas_analisadas:
            return
        if not Messagebox.okcancel(
            "Confirmar?", "Esta ação irá modificar o banco de dados."
        ):
            return
        try:
            resumo = self.fachada_importacao.executar()
            self._mostrar_sumario_importacao(resumo)
            self.import_notebook.select(2)
            # Idealmente, a atualização da aba de alunos seria feita via um callback.
        except Exception:
            Messagebox.show_error(
                "Erro ao executar importação. Verifique o console.", "Erro"
            )
            traceback.print_exc()

    def _criar_passo_3_sumario(self):
        step3 = ttk.Frame(self.import_notebook, padding=20)
        self.import_notebook.add(step3, text=" 3. Sumário ", state="disabled")
        self.sumario_label = ttk.Label(step3, text="", font=("Helvetica", 12))
        self.sumario_label.pack(pady=10)
        ttk.Button(
            step3, text="Nova Importação", command=self._resetar_importacao
        ).pack(pady=20)

    def _mostrar_sumario_importacao(self, resumo):
        self.import_notebook.tab(2, state="normal")
        texto = (
            f"✅ Importação Concluída!\n\n"
            f"Alunos criados: {resumo.get('alunos_criados', 0)}\n"
            f"Reservas criadas: {resumo.get('reservas_criadas', 0)}"
        )
        self.sumario_label.config(text=texto)

    def _resetar_importacao(self):
        self.file_path_var.set("")
        self.review_table.delete_rows()
        self.import_notebook.tab(1, state="disabled")
        self.import_notebook.tab(2, state="disabled")
        self.import_notebook.select(0)
        self.linhas_analisadas = []

    def _exportar_dados(self, tipo: str):
        try:
            if tipo == "consumo":
                caminho = self.fachada_nucleo.exportar_sessao_para_xlsx()
                Messagebox.show_info("Sucesso", f"Relatório exportado para:\n{caminho}")
                return

            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv", filetypes=[("CSV files", "*.csv")]
            )
            if not filepath:
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
            Messagebox.show_info("Sucesso", f"Dados exportados para:\n{filepath}")
        except ErroSessaoNaoAtiva:
            Messagebox.show_warning(
                "Nenhuma sessão ativa para exportar o consumo.", "Aviso"
            )
        except Exception:
            Messagebox.show_error("Falha na exportação. Verifique o console.", "Erro")
            traceback.print_exc()
