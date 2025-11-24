# gestao_refeitorio/abas/aba_importacao.py

"""
Módulo de interface gráfica para importação de dados.
Implementa um Wizard de 4 passos: Seleção, Revisão, Preview e Confirmação.
"""

import csv
import tkinter as tk
from tkinter import filedialog
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, E, EW, LEFT, NSEW, RIGHT, W, X
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.scrolled import ScrolledFrame
from ttkbootstrap.widgets import DateEntry

from registro.controles.rounded_button import RoundedButton
from registro.controles.treeview_simples import TreeviewSimples
from registro.importar.definitions import ItemRevisao, ResumoImportacao
from registro.importar.facade import FachadaImportacao
from registro.nucleo.exceptions import ErroSessaoNaoAtiva
from registro.nucleo.facade import FachadaRegistro


class RowItemRevisao(ttk.Frame):
    """
    Componente visual que representa uma linha de revisão na interface.
    Permite ao usuário escolher a ação e o candidato (se houver).
    """

    def __init__(self, parent, item: ItemRevisao, *args, **kwargs):
        super().__init__(parent, padding=5, bootstyle="light", *args, **kwargs)
        self.item = item
        self.pack(fill=X, pady=2, padx=5)

        # 1. Dados Originais (Esquerda)
        info_frame = ttk.Frame(self, bootstyle="light")
        info_frame.pack(side=LEFT, fill=X, expand=True)

        nome_csv = item["dados_csv"].get("nome", "Sem Nome")
        pront_csv = item["dados_csv"].get("prontuario", "")
        dados_txt = f"{nome_csv} ({pront_csv})" if pront_csv else nome_csv

        lbl_dados = ttk.Label(
            info_frame, text=dados_txt, font="-weight bold", bootstyle="inverse-light"
        )
        lbl_dados.pack(anchor=W)

        detalhe_txt = item["tipo_conflito"].replace("_", " ").title()
        lbl_detalhe = ttk.Label(
            info_frame,
            text=f"Status: {detalhe_txt}",
            font="-size 8",
            bootstyle="light-inverse",
        )
        lbl_detalhe.pack(anchor=W)

        # 2. Controles de Ação (Direita)
        ctrl_frame = ttk.Frame(self, bootstyle="light")
        ctrl_frame.pack(side=RIGHT, padx=(0, 5))

        # Combobox de Candidatos (Só aparece se houver candidatos)
        self.cbo_candidatos = ttk.Combobox(
            ctrl_frame, state="readonly", width=30, bootstyle="info"
        )
        self.mapa_candidatos = {}  # Mapa "Texto Combobox -> ID Banco"

        if item["candidatos"]:
            opcoes = []
            for cand in item["candidatos"]:
                texto = f"{cand['nome']} ({cand['score']}%) - {cand['turma']}"
                opcoes.append(texto)
                self.mapa_candidatos[texto] = cand["id"]

            self.cbo_candidatos["values"] = opcoes
            # Seleciona o primeiro (melhor match) por padrão
            if opcoes:
                self.cbo_candidatos.current(0)

            self.cbo_candidatos.pack(side=LEFT, padx=5)
            self.cbo_candidatos.bind(
                "<<ComboboxSelected>>", self._ao_selecionar_candidato
            )

        # Combobox de Ação
        self.var_acao = tk.StringVar(value=item["resolucao_escolhida"])
        cbo_acao = ttk.Combobox(
            ctrl_frame,
            textvariable=self.var_acao,
            values=["CRIAR_NOVO", "VINCULAR", "IGNORAR"],
            state="readonly",
            width=12,
            bootstyle="info",
        )
        cbo_acao.pack(side=LEFT, padx=5)
        cbo_acao.bind("<<ComboboxSelected>>", self._ao_mudar_acao)

        # Estado inicial visual
        self._atualizar_estado_visual()

    def _ao_mudar_acao(self, _event):
        """Atualiza o item de dados e a visibilidade dos widgets."""
        nova_acao = self.var_acao.get()
        self.item["resolucao_escolhida"] = nova_acao  # type: ignore
        self._atualizar_estado_visual()

    def _ao_selecionar_candidato(self, _event):
        """Atualiza o ID de vínculo no item de dados."""
        texto_sel = self.cbo_candidatos.get()
        if texto_sel in self.mapa_candidatos:
            self.item["id_estudante_vinculo"] = self.mapa_candidatos[texto_sel]

    def _atualizar_estado_visual(self):
        """Habilita/Desabilita combobox de candidatos dependendo da ação."""
        acao = self.var_acao.get()
        if acao == "VINCULAR" and self.mapa_candidatos:
            self.cbo_candidatos.configure(state="readonly")
            # Garante que o ID está setado com o valor atual do combo
            self._ao_selecionar_candidato(None)
        else:
            self.cbo_candidatos.configure(state="disabled")
            if acao == "CRIAR_NOVO":
                self.item["id_estudante_vinculo"] = None


class AbaImportacao(ttk.Frame):
    """
    Aba principal de importação de dados.
    Gerencia o fluxo do wizard de 4 passos.
    """

    def __init__(
        self,
        parent,
        fachada_nucleo: FachadaRegistro,
        fachada_importacao: FachadaImportacao,
    ):
        super().__init__(parent)
        self.fachada_nucleo = fachada_nucleo
        self.fachada_importacao = fachada_importacao

        # Estado da Sessão
        self.itens_revisao: List[ItemRevisao] = []
        self.resumo_analise: Optional[ResumoImportacao] = None
        self.preview_dados: Dict[str, List[Dict]] = {}

        # Widgets Variáveis
        self.file_path_var: tk.StringVar
        self.import_type_var: tk.StringVar
        self.default_prato_var: tk.StringVar = tk.StringVar(value="Almoço")
        self.entry_data_default: DateEntry

        # Componentes UI
        self.wizard_container: ttk.Frame
        self.step1_frame: ttk.Frame
        self.step2_frame: ttk.Frame
        self.step3_frame: ttk.Frame
        self.step4_frame: ttk.Frame
        self.lista_revisao_frame: ScrolledFrame
        self.tree_novos: TreeviewSimples
        self.tree_reservas: TreeviewSimples
        self.lbl_titulo: ttk.Label
        self.lbl_resumo_topo: ttk.Label
        self.lbl_msg_sucesso: ttk.Label
        self.btn_confirmar_final: RoundedButton

        self._criar_layout_principal()

    def _criar_layout_principal(self):
        """Configura o Grid principal da aba."""
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)  # Wizard Area
        self.rowconfigure(2, weight=0)  # Export Area

        # Área do Wizard (Passos 1, 2, 3, 4)
        self.wizard_container = ttk.Frame(self, padding=(10, 10, 10, 0))
        self.wizard_container.grid(row=0, column=0, sticky=NSEW)
        self.wizard_container.columnconfigure(0, weight=1)
        self.wizard_container.rowconfigure(1, weight=1)

        # Título dinâmico do passo
        self.lbl_titulo = ttk.Label(
            self.wizard_container,
            text="📥 Importação - Passo 1",
            font="-size 16 -weight bold",
            bootstyle="primary",
        )
        self.lbl_titulo.grid(row=0, column=0, sticky=W, pady=(0, 15))

        # Inicializa os Frames dos Passos (mas não mostra ainda)
        self.step1_frame = self._criar_passo_1(self.wizard_container)
        self.step2_frame = self._criar_passo_2(self.wizard_container)
        self.step3_frame = self._criar_passo_3_preview(self.wizard_container)
        self.step4_frame = self._criar_passo_4_sucesso(self.wizard_container)

        # Inicia no Passo 1
        self.step1_frame.grid(row=1, column=0, sticky=NSEW)

        # Separator
        ttk.Separator(self).grid(row=1, column=0, sticky=EW, pady=10)

        # Área de Exportação (Rodapé)
        export_frame = self._criar_painel_exportacao(self)
        export_frame.grid(row=2, column=0, sticky=NSEW, padx=10, pady=(0, 10))

    def _navegar(self, de_frame: ttk.Frame, para_frame: ttk.Frame, titulo: str):
        """Utilitário para transição entre frames do wizard."""
        de_frame.grid_forget()
        para_frame.grid(row=1, column=0, sticky=NSEW)
        self.lbl_titulo.config(text=titulo)

    # --- PASSO 1: SELEÇÃO ---
    def _criar_passo_1(self, parent):
        frame = ttk.Frame(parent)

        # Opções de Estratégia
        lbl = ttk.Label(frame, text="1. Configuração da Fonte", font="-weight bold")
        lbl.pack(anchor=W, pady=(0, 10))

        opts_frame = ttk.Labelframe(frame, text="Tipo de Arquivo", padding=10)
        opts_frame.pack(fill=X, pady=(0, 10))

        self.import_type_var = tk.StringVar(value="auto")

        # Seleção de Arquivo
        file_frame = ttk.Labelframe(frame, text="Arquivo/ID", padding=10)
        file_frame.pack(fill=X, pady=10)

        self.file_path_var = tk.StringVar()
        entry_path = ttk.Entry(
            file_frame, textvariable=self.file_path_var, state="readonly"
        )
        entry_path.pack(side=LEFT, fill=X, expand=True, padx=(0, 5))

        search_btn = RoundedButton(
            file_frame, text="Buscar...", command=self._selecionar_arquivo
        )
        search_btn.pack(side=LEFT)

        def mudar_estado(ativo: bool):
            entry_path.configure(state="readonly" if ativo else "normal")
            search_btn.configure(state="normal" if ativo else "disabled")

        # Botão Avançar
        RoundedButton(
            frame,
            text="Analisar Dados >",
            bootstyle="primary",
            command=self._iniciar_analise,
        ).pack(anchor=E, pady=20)

        ttk.Radiobutton(
            opts_frame,
            text="Automático (Detectar colunas)",
            variable=self.import_type_var,
            value="auto",
            command=lambda: mudar_estado(True),
        ).pack(anchor=W, pady=2)

        ttk.Radiobutton(
            opts_frame,
            text="Lista Simples (Apenas Nomes/Prontuários)",
            variable=self.import_type_var,
            value="simples",
            command=lambda: mudar_estado(True),
        ).pack(anchor=W, pady=2)

        ttk.Radiobutton(
            opts_frame,
            text="CSV com Cabeçalho (Padrão)",
            variable=self.import_type_var,
            value="header",
            command=lambda: mudar_estado(True),
        ).pack(anchor=W, pady=2)

        ttk.Radiobutton(
            opts_frame,
            text="Google Spreadsheets (IDPlanilha:NomeDaAba)",
            variable=self.import_type_var,
            value="sheets",
            command=lambda: mudar_estado(False),
        ).pack(anchor=W, pady=2)
        return frame

    def _selecionar_arquivo(self):
        path = filedialog.askopenfilename(
            filetypes=[("Arquivos de Texto", "*.csv *.txt"), ("Todos", "*.*")]
        )
        if path:
            self.file_path_var.set(path)

    def _iniciar_analise(self):
        path = self.file_path_var.get()
        tipo = self.import_type_var.get()

        if not path:
            Messagebox.show_warning("Selecione um arquivo primeiro.")
            return

        try:
            resultado = self.fachada_importacao.analisar_arquivo(path, tipo)

            self.resumo_analise = resultado["resumo"]
            self.itens_revisao = resultado["itens_revisao"]

            self._preencher_passo_2()
            self._navegar(
                self.step1_frame,
                self.step2_frame,
                "📥 Importação - Passo 2 (Revisão)",
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            traceback.print_exc()
            Messagebox.show_error(f"Erro na análise: {e}")

    # --- PASSO 2: REVISÃO ---
    def _criar_passo_2(self, parent):
        frame = ttk.Frame(parent)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)  # Lista cresce

        # Cabeçalho Resumo
        self.lbl_resumo_topo = ttk.Label(frame, text="", bootstyle="info")
        self.lbl_resumo_topo.grid(row=0, column=0, sticky=EW, pady=(0, 10))

        # Painel de Defaults (Valores Padrão)
        def_frame = ttk.Labelframe(
            frame, text="Valores Padrão (Para campos vazios)", padding=10
        )
        def_frame.grid(row=1, column=0, sticky=EW, pady=(0, 10))

        ttk.Label(def_frame, text="Data:").pack(side=LEFT)
        self.entry_data_default = DateEntry(
            def_frame, dateformat="%d/%m/%Y", bootstyle="primary", width=12
        )
        self.entry_data_default.pack(side=LEFT, padx=(5, 15))

        ttk.Label(def_frame, text="Refeição:").pack(side=LEFT)
        ttk.Combobox(
            def_frame,
            textvariable=self.default_prato_var,
            values=["Almoço", "Jantar", "Lanche"],
            width=15,
        ).pack(side=LEFT, padx=5)

        # Lista de Revisão
        list_container = ttk.Labelframe(frame, text="Revisão de Conflitos", padding=0)
        list_container.grid(row=2, column=0, sticky=NSEW)

        self.lista_revisao_frame = ScrolledFrame(list_container, autohide=True)
        self.lista_revisao_frame.pack(fill=BOTH, expand=True)

        # Botões Ação
        btn_frame = ttk.Frame(frame, padding=(0, 10))
        btn_frame.grid(row=3, column=0, sticky=EW)

        RoundedButton(
            btn_frame,
            text="Voltar",
            bootstyle="secondary-outline",
            command=lambda: self._navegar(
                self.step2_frame, self.step1_frame, "📥 Importação - Passo 1"
            ),
        ).pack(side=LEFT)

        RoundedButton(
            btn_frame,
            text="Verificar Dados >",
            bootstyle="info",
            command=self._ir_para_preview,
        ).pack(side=RIGHT)

        return frame

    def _preencher_passo_2(self):
        if not self.resumo_analise:
            return

        res = self.resumo_analise
        txt = (
            f"✅ {res['automaticos']} Automáticos  |  "
            f"⚠️ {res['para_revisao']} Para Revisão  |  "
            f"❌ {res['invalidos']} Ignorados"
        )
        self.lbl_resumo_topo.config(text=txt)

        for widget in self.lista_revisao_frame.winfo_children():
            widget.destroy()

        if not self.itens_revisao:
            ttk.Label(
                self.lista_revisao_frame,
                text="Tudo certo! Nenhum conflito encontrado.",
                font="-size 12",
            ).pack(pady=20)
        else:
            for item in self.itens_revisao:
                RowItemRevisao(self.lista_revisao_frame, item)

    def _obter_defaults(self) -> Dict[str, Any]:
        """Captura os valores padrão definidos na UI."""
        d = {}
        if val := self.entry_data_default.entry.get():
            d["data"] = val
        if val := self.default_prato_var.get():
            d["prato"] = val
        return d

    def _ir_para_preview(self):
        """Passo 2 -> Passo 3: Gera simulação."""
        defaults = self._obter_defaults()

        try:
            self.preview_dados = self.fachada_importacao.simular_importacao(
                self.itens_revisao, defaults
            )

            # Popula Tabelas
            novos = self.preview_dados.get("novos_estudantes", [])
            reservas = self.preview_dados.get("reservas", [])

            dados_novos = [(n["prontuario"], n["nome"]) for n in novos]
            dados_res = [
                (r["data"], r["prontuario"], r["aluno"], r["prato"]) for r in reservas
            ]

            self.tree_novos.construir_dados_tabela(dados_novos)
            self.tree_reservas.construir_dados_tabela(dados_res)

            # Atualiza botão
            total_ops = len(novos) + len(reservas)
            self.btn_confirmar_final.configure(
                text=f"CONFIRMAR E SALVAR ({total_ops} operações)"
            )

            self._navegar(
                self.step2_frame,
                self.step3_frame,
                "📥 Importação - Passo 3 (Confirmação)",
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            traceback.print_exc()
            Messagebox.show_error(f"Erro ao gerar preview: {e}")

    # --- PASSO 3: PREVIEW ---
    def _criar_passo_3_preview(self, parent):
        frame = ttk.Frame(parent)
        frame.columnconfigure((0, 1), weight=1)
        frame.rowconfigure(1, weight=1)

        ttk.Label(
            frame,
            text="Verifique os dados abaixo antes de salvar definitivamente.",
            font="-size 11",
        ).grid(row=0, column=0, columnspan=2, sticky=W, pady=(0, 10))

        # Tabela 1: Novos Alunos
        fr_novos = ttk.Labelframe(
            frame, text="🆕 Novos Estudantes a Cadastrar", padding=5
        )
        fr_novos.grid(row=1, column=0, sticky=NSEW, padx=(0, 5))

        self.tree_novos = TreeviewSimples(
            fr_novos,
            dados_colunas=[
                {"text": "Prontuário", "width": 80},
                {"text": "Nome", "stretch": True},
            ],
            height=10,
        )
        self.tree_novos.pack(fill=BOTH, expand=True)

        # Tabela 2: Reservas
        fr_res = ttk.Labelframe(frame, text="📅 Reservas a Gerar", padding=5)
        fr_res.grid(row=1, column=1, sticky=NSEW, padx=(5, 0))

        self.tree_reservas = TreeviewSimples(
            fr_res,
            dados_colunas=[
                {"text": "Data", "width": 80},
                {"text": "Prontuário", "width": 80},
                {"text": "Nome", "stretch": True},
                {"text": "Prato", "width": 100},
            ],
            height=10,
        )
        self.tree_reservas.pack(fill=BOTH, expand=True)

        # Botões
        btn_frame = ttk.Frame(frame, padding=(0, 10))
        btn_frame.grid(row=2, column=0, columnspan=2, sticky=EW)

        RoundedButton(
            btn_frame,
            text="< Voltar e Editar",
            bootstyle="secondary-outline",
            command=lambda: self._navegar(
                self.step3_frame,
                self.step2_frame,
                "📥 Importação - Passo 2 (Revisão)",
            ),
        ).pack(side=LEFT)

        self.btn_confirmar_final = RoundedButton(
            btn_frame,
            text="CONFIRMAR E SALVAR",
            bootstyle="success",
            command=self._executar_salvamento,
        )
        self.btn_confirmar_final.pack(side=RIGHT)

        return frame

    def _executar_salvamento(self):
        if (
            Messagebox.yesno(
                "Tem certeza que deseja aplicar estas alterações no banco de dados?",
                "Confirmação Final",
            )
            != "Yes"
        ):
            return

        try:
            defaults = self._obter_defaults()
            resultado = self.fachada_importacao.confirmar_importacao(
                self.itens_revisao, defaults
            )

            self._mostrar_sucesso_final(resultado)
            self._navegar(self.step3_frame, self.step4_frame, "✅ Importação Concluída")

        except Exception as e:  # pylint: disable=broad-exception-caught
            traceback.print_exc()
            Messagebox.show_error(f"Erro fatal ao salvar: {e}")

    # --- PASSO 4: SUCESSO ---
    def _criar_passo_4_sucesso(self, parent):
        frame = ttk.Frame(parent)
        # REMOVIDO: frame.place(...) - Isso causava a sobreposição imediata

        # Criamos um container interno para centralizar o conteúdo dentro do frame
        # O 'frame' será gerenciado pelo grid do wizard, e este 'container' ficará no meio dele

        self.lbl_msg_sucesso = ttk.Label(frame, text="", font="-size 12", justify=LEFT)
        self.lbl_msg_sucesso.pack(pady=20)

        RoundedButton(
            frame,  # Note que o pai agora é o container, não o frame
            text="Realizar Nova Importação",
            bootstyle="primary",
            command=self._resetar_tudo,
        ).pack()

        return frame

    def _mostrar_sucesso_final(self, resultado):
        txt = (
            "🎉 Dados salvos com sucesso!\n\n"
            f"• Estudantes Cadastrados: {resultado.get('estudantes_criados', 0)}\n"
            f"• Reservas Geradas: {resultado.get('reservas_criadas', 0)}\n"
        )
        self.lbl_msg_sucesso.config(text=txt)

    def _resetar_tudo(self):
        self.file_path_var.set("")
        # Reseta e volta para o início, garantindo que o layout de grid seja restaurado
        # self.step4_frame.place_forget()
        self._navegar(self.step4_frame, self.step1_frame, "📥 Importação - Passo 1")

    # --- EXPORTAÇÃO ---
    def _criar_painel_exportacao(self, parent):
        container = ttk.Frame(parent, padding=10, bootstyle="light")
        container.columnconfigure((0, 1, 2), weight=1)

        ttk.Label(
            container,
            text="📤 Exportar Dados",
            font="-weight bold",
            bootstyle="inverse-light",
        ).grid(row=0, column=0, columnspan=3, sticky=W, pady=(0, 5))

        RoundedButton(
            container,
            text="Alunos (CSV)",
            bootstyle="secondary-outline",
            command=lambda: self._exportar_dados("alunos"),
        ).grid(row=1, column=0, sticky=EW, padx=2)

        RoundedButton(
            container,
            text="Reservas (CSV)",
            bootstyle="secondary-outline",
            command=lambda: self._exportar_dados("reservas"),
        ).grid(row=1, column=1, sticky=EW, padx=2)

        RoundedButton(
            container,
            text="Consumos (XLSX)",
            bootstyle="success-outline",
            command=lambda: self._exportar_dados("consumo"),
        ).grid(row=1, column=2, sticky=EW, padx=2)

        return container

    def _exportar_dados(self, tipo: Literal["alunos", "reservas", "consumo"]):
        try:
            default_filename = f"export_{tipo}_{datetime.now().strftime('%Y%m%d')}"
            ext = ".xlsx" if tipo == "consumo" else ".csv"
            ftypes = [("Excel", "*.xlsx")] if tipo == "consumo" else [("CSV", "*.csv")]

            filepath = filedialog.asksaveasfilename(
                initialfile=default_filename,
                defaultextension=ext,
                filetypes=ftypes,
            )
            if not filepath:
                return

            if tipo == "consumo":
                self.fachada_nucleo.exportar_consumos_para_xlsx(Path(filepath))
            else:
                if tipo == "alunos":
                    dados = self.fachada_nucleo.listar_todos_os_estudantes()
                else:
                    # Reservas
                    dados = self.fachada_nucleo.listar_reservas()
                keys = dados[0].keys() if dados else []
                with open(filepath, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=keys)
                    writer.writeheader()
                    # Normaliza listas (grupos) para string no CSV
                    for d in dados:
                        if "grupos" in d and isinstance(d["grupos"], list):
                            d["grupos"] = ", ".join(d["grupos"])
                    writer.writerows(dados)

            Messagebox.show_info(f"Arquivo salvo em:\n{filepath}", "Sucesso")

        except ErroSessaoNaoAtiva:
            Messagebox.show_warning("Nenhuma sessão ativa para exportar consumo.")
        except Exception as e:  # pylint: disable=broad-exception-caught
            Messagebox.show_error(f"Falha na exportação: {e}")
