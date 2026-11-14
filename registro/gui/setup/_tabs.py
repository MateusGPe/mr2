# ----------------------------------------------------------------------------
# Arquivo: registro/gui/setup/_tabs.py (Construção das Abas do Setup)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""Mixin de construção das abas de interface gráfica da Central de Configurações."""

import tkinter as tk
import webbrowser
from typing import Any, Dict

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, CENTER, LEFT, RIGHT, X, Y

from registro.nucleo.constants import DIRETORIO_CONFIG, DIRETORIO_LOG


class _SetupTabsMixin:
    """Constrói os widgets das 6 abas do AppSetup."""

    def _construir_aba_status(self: Any):
        lbl_intro = ttk.Label(
            self.aba_status,
            text="Visão geral e diagnóstico de saúde do sistema:",
            font=("Segoe UI", 11, "bold"),
        )
        lbl_intro.pack(anchor="w", pady=(0, 15))

        self.frame_cards = ttk.Frame(self.aba_status)
        self.frame_cards.pack(fill=X, pady=(0, 20))

        for c in range(2):
            self.frame_cards.columnconfigure(c, weight=1, uniform="card")

        self.card_db = self._criar_card(
            self.frame_cards, 0, 0, "📦 Banco de Dados SQLite", "Carregando..."
        )
        self.card_gcp = self._criar_card(
            self.frame_cards, 0, 1, "☁️ Google Cloud API", "Carregando..."
        )
        self.card_sheet = self._criar_card(
            self.frame_cards, 1, 0, "📊 Planilha do Sheets", "Carregando..."
        )
        self.card_pin = self._criar_card(
            self.frame_cards, 1, 1, "🔒 Segurança do Totem (PIN)", "Carregando..."
        )

        lbl_modulos = ttk.Label(
            self.aba_status,
            text="Inicialização Rápida de Módulos:",
            font=("Segoe UI", 11, "bold"),
        )
        lbl_modulos.pack(anchor="w", pady=(10, 8))

        frame_botoes = ttk.Frame(self.aba_status)
        frame_botoes.pack(fill=X, pady=5)

        btn_totem = ttk.Button(
            frame_botoes,
            text="🤖  Iniciar Totem de Autoatendimento",
            bootstyle="success",
            command=self._iniciar_modulo_totem,
            cursor="hand2",
        )
        btn_totem.pack(side=LEFT, expand=True, fill=X, padx=(0, 6), ipady=8)

        btn_reg = ttk.Button(
            frame_botoes,
            text="📝  Iniciar Registro de Refeições",
            bootstyle="primary",
            command=self._iniciar_modulo_registrar,
            cursor="hand2",
        )
        btn_reg.pack(side=LEFT, expand=True, fill=X, padx=3, ipady=8)

        btn_painel = ttk.Button(
            frame_botoes,
            text="📊  Iniciar Painel Administrativo",
            bootstyle="info",
            command=self._iniciar_modulo_painel,
            cursor="hand2",
        )
        btn_painel.pack(side=LEFT, expand=True, fill=X, padx=(6, 0), ipady=8)

    def _criar_card(
        self: Any,
        parent: ttk.Frame,
        row: int,
        col: int,
        titulo: str,
        texto_inicial: str,
    ) -> Dict[str, Any]:
        frame = ttk.Labelframe(parent, text=f" {titulo} ", padding=12)
        frame.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

        lbl_status = ttk.Label(
            frame, text=texto_inicial, font=("Segoe UI", 9), wraplength=400
        )
        lbl_status.pack(anchor="w", fill=X)

        return {"frame": frame, "label": lbl_status}

    def _construir_aba_google(self: Any):
        lf_guia = ttk.Labelframe(
            self.aba_google,
            text=" 📖 Guia de Configuração no Google Cloud ",
            padding=12,
        )
        lf_guia.pack(fill=X, pady=(0, 15))

        passos_texto = (
            "1. Crie um projeto no Google Cloud Console.\n"
            "2. Ative as APIs: 'Google Sheets API' e 'Google Drive API'.\n"
            "3. Em Credenciais, crie uma chave (Conta de Serviço ou ID do Cliente OAuth para App Desktop).\n"
            "4. Baixe o arquivo JSON gerado e carregue-o abaixo. Se usar Conta de Serviço, compartilhe a planilha com o e-mail dela."
        )
        lbl_passos = ttk.Label(
            lf_guia, text=passos_texto, font=("Segoe UI", 9), justify=LEFT
        )
        lbl_passos.pack(anchor="w", pady=(0, 8))

        frame_links = ttk.Frame(lf_guia)
        frame_links.pack(fill=X)

        links = [
            ("🌐 Console GCP", "https://console.cloud.google.com/"),
            (
                "📈 Ativar Sheets API",
                "https://console.cloud.google.com/apis/library/sheets.googleapis.com",
            ),
            (
                "📁 Ativar Drive API",
                "https://console.cloud.google.com/apis/library/drive.googleapis.com",
            ),
            (
                "🔑 Criar Credenciais",
                "https://console.cloud.google.com/apis/credentials",
            ),
        ]
        for texto, url in links:
            btn_link = ttk.Button(
                frame_links,
                text=texto,
                bootstyle="link",
                cursor="hand2",
                command=lambda u=url: webbrowser.open(u),
            )
            btn_link.pack(side=LEFT, padx=(0, 10))

        lf_cred = ttk.Labelframe(
            self.aba_google,
            text=" 📂 Arquivo de Credenciais (credentials.json) ",
            padding=12,
        )
        lf_cred.pack(fill=X, pady=(0, 15))

        self.lbl_cred_status = ttk.Label(
            lf_cred, text="Verificando...", font=("Segoe UI", 9)
        )
        self.lbl_cred_status.pack(anchor="w", pady=(0, 8))

        frame_botoes_cred = ttk.Frame(lf_cred)
        frame_botoes_cred.pack(fill=X)

        btn_importar_cred = ttk.Button(
            frame_botoes_cred,
            text="📥 Carregar Arquivo credentials.json",
            bootstyle="primary-outline",
            command=self._importar_credenciais,
            cursor="hand2",
        )
        btn_importar_cred.pack(side=LEFT, padx=(0, 10))

        btn_limpar_tok = ttk.Button(
            frame_botoes_cred,
            text="🗑️ Redefinir / Limpar Token de Sessão",
            bootstyle="secondary-outline",
            command=self._limpar_token,
            cursor="hand2",
        )
        btn_limpar_tok.pack(side=LEFT)

        lf_planilha = ttk.Labelframe(
            self.aba_google, text=" 📊 ID ou URL da Planilha Google Sheets ", padding=12
        )
        lf_planilha.pack(fill=X, pady=(0, 15))

        lbl_dica_planilha = ttk.Label(
            lf_planilha,
            text="Insira o ID da planilha ou a URL completa (ex: https://docs.google.com/spreadsheets/d/1x78c.../edit):",
            font=("Segoe UI", 9),
            bootstyle="secondary",
        )
        lbl_dica_planilha.pack(anchor="w", pady=(0, 6))

        frame_input_sheet = ttk.Frame(lf_planilha)
        frame_input_sheet.pack(fill=X, pady=(0, 8))

        self.var_planilha_input = tk.StringVar()
        entry_sheet = ttk.Entry(
            frame_input_sheet,
            textvariable=self.var_planilha_input,
            font=("Segoe UI", 9),
        )
        entry_sheet.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))

        btn_salvar_sheet = ttk.Button(
            frame_input_sheet,
            text="💾 Salvar ID",
            bootstyle="success",
            command=self._salvar_id_planilha,
            cursor="hand2",
        )
        btn_salvar_sheet.pack(side=RIGHT)

        frame_teste = ttk.Frame(lf_planilha)
        frame_teste.pack(fill=X, pady=(5, 0))

        self.btn_testar_conexao = ttk.Button(
            frame_teste,
            text="🧪 Testar Conexão com Google Sheets",
            bootstyle="info",
            command=self._testar_conexao_em_thread,
            cursor="hand2",
        )
        self.btn_testar_conexao.pack(side=LEFT, padx=(0, 10))

        self.btn_criar_abas = ttk.Button(
            frame_teste,
            text="📑 Criar Estrutura de Abas",
            bootstyle="primary",
            command=self._criar_abas_em_thread,
            cursor="hand2",
        )
        self.btn_criar_abas.pack(side=LEFT, padx=(0, 10))

        self.lbl_teste_resultado = ttk.Label(
            frame_teste, text="", font=("Segoe UI", 9, "bold")
        )
        self.lbl_teste_resultado.pack(side=LEFT, fill=X, expand=True)

    def _construir_aba_totem(self: Any):
        lf_pin = ttk.Labelframe(
            self.aba_totem, text=" 🔒 PIN de Segurança do Operador ", padding=12
        )
        lf_pin.pack(fill=X, pady=(0, 15))

        self.lbl_pin_status = ttk.Label(
            lf_pin, text="Status do PIN: Verificando...", font=("Segoe UI", 9)
        )
        self.lbl_pin_status.pack(anchor="w", pady=(0, 10))

        frame_inputs_pin = ttk.Frame(lf_pin)
        frame_inputs_pin.pack(fill=X, pady=(0, 10))

        lbl_novo = ttk.Label(
            frame_inputs_pin, text="Novo PIN (somente dígitos):", font=("Segoe UI", 9)
        )
        lbl_novo.grid(row=0, column=0, sticky="w", padx=(0, 10), pady=4)

        self.var_novo_pin = tk.StringVar()
        self.entry_novo_pin = ttk.Entry(
            frame_inputs_pin, textvariable=self.var_novo_pin, show="●", width=18
        )
        self.entry_novo_pin.grid(row=0, column=1, sticky="w", pady=4)

        lbl_confirma = ttk.Label(
            frame_inputs_pin, text="Confirmar Novo PIN:", font=("Segoe UI", 9)
        )
        lbl_confirma.grid(row=1, column=0, sticky="w", padx=(0, 10), pady=4)

        self.var_confirma_pin = tk.StringVar()
        self.entry_confirma_pin = ttk.Entry(
            frame_inputs_pin, textvariable=self.var_confirma_pin, show="●", width=18
        )
        self.entry_confirma_pin.grid(row=1, column=1, sticky="w", pady=4)

        self.var_mostrar_pin = tk.BooleanVar(value=False)
        chk_mostrar = ttk.Checkbutton(
            frame_inputs_pin,
            text="Mostrar dígitos",
            variable=self.var_mostrar_pin,
            command=self._alternar_visibilidade_pin,
        )
        chk_mostrar.grid(row=0, column=2, rowspan=2, padx=15)

        frame_botoes_pin = ttk.Frame(lf_pin)
        frame_botoes_pin.pack(fill=X, pady=(5, 0))

        btn_salvar_pin = ttk.Button(
            frame_botoes_pin,
            text="💾 Salvar / Atualizar PIN",
            bootstyle="success",
            command=self._salvar_pin,
            cursor="hand2",
        )
        btn_salvar_pin.pack(side=LEFT, padx=(0, 10))

        btn_remover_pin = ttk.Button(
            frame_botoes_pin,
            text="🗑️ Remover PIN Ativo",
            bootstyle="danger-outline",
            command=self._remover_pin,
            cursor="hand2",
        )
        btn_remover_pin.pack(side=LEFT)

        lf_pref = ttk.Labelframe(
            self.aba_totem,
            text=" ⚙️ Preferências do Totem de Autoatendimento ",
            padding=12,
        )
        lf_pref.pack(fill=X, pady=(0, 10))

        self.var_fullscreen = tk.BooleanVar()
        ttk.Checkbutton(
            lf_pref,
            text="Iniciar automaticamente em Tela Cheia (F11)",
            variable=self.var_fullscreen,
        ).pack(anchor="w", pady=4)

        self.var_camera_start = tk.BooleanVar()
        ttk.Checkbutton(
            lf_pref,
            text="Ativar câmera / webcam automaticamente ao abrir o Totem",
            variable=self.var_camera_start,
        ).pack(anchor="w", pady=4)

        self.var_require_pin_exit = tk.BooleanVar()
        ttk.Checkbutton(
            lf_pref,
            text="Exigir PIN para sair do Totem ou fechar a janela",
            variable=self.var_require_pin_exit,
        ).pack(anchor="w", pady=4)

        frame_delay = ttk.Frame(lf_pref)
        frame_delay.pack(anchor="w", pady=6)

        ttk.Label(
            frame_delay,
            text="Tempo de exibição da confirmação verde na tela (ms):",
            font=("Segoe UI", 9),
        ).pack(side=LEFT, padx=(0, 8))

        self.var_delay_ms = tk.StringVar(value="1500")
        ttk.Entry(frame_delay, textvariable=self.var_delay_ms, width=8).pack(side=LEFT)

        ttk.Button(
            lf_pref,
            text="💾 Salvar Preferências do Totem",
            bootstyle="primary",
            command=self._salvar_preferencias_totem,
            cursor="hand2",
        ).pack(anchor="w", pady=(12, 0))

    def _construir_aba_grade(self: Any):
        ttk.Label(
            self.aba_grade,
            text="Configuração e Escalonamento da Grade Horária Semanal (grade_horarios.json):",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", pady=(0, 5))

        ttk.Label(
            self.aba_grade,
            text="Defina os horários de início/fim e turmas/categorias autorizadas para cada dia e refeição.",
            bootstyle="secondary",
        ).pack(anchor="w", pady=(0, 15))

        frame_filtros = ttk.Frame(self.aba_grade)
        frame_filtros.pack(fill=X, pady=(0, 10))

        ttk.Label(frame_filtros, text="Dia da Semana:").pack(side=LEFT, padx=(0, 5))
        self.dias_grade_map = {
            "Segunda-feira": "segunda",
            "Terça-feira": "terca",
            "Quarta-feira": "quarta",
            "Quinta-feira": "quinta",
            "Sexta-feira": "sexta",
            "Sábado": "sabado",
            "Domingo": "domingo",
        }
        self.cbo_grade_dia = ttk.Combobox(
            frame_filtros,
            values=list(self.dias_grade_map.keys()),
            state="readonly",
            width=16,
        )
        self.cbo_grade_dia.set("Segunda-feira")
        self.cbo_grade_dia.pack(side=LEFT, padx=(0, 15))
        self.cbo_grade_dia.bind(
            "<<ComboboxSelected>>", lambda *_: self._carregar_regras_grade()
        )

        ttk.Label(frame_filtros, text="Refeição:").pack(side=LEFT, padx=(0, 5))
        self.refeicoes_grade_map = {
            "Almoço": "almoco",
            "Jantar": "jantar",
            "Lanche": "lanche",
        }
        self.cbo_grade_refeicao = ttk.Combobox(
            frame_filtros,
            values=list(self.refeicoes_grade_map.keys()),
            state="readonly",
            width=12,
        )
        self.cbo_grade_refeicao.set("Almoço")
        self.cbo_grade_refeicao.pack(side=LEFT, padx=(0, 15))
        self.cbo_grade_refeicao.bind(
            "<<ComboboxSelected>>", lambda *_: self._carregar_regras_grade()
        )

        frame_tabela = ttk.Frame(self.aba_grade)
        frame_tabela.pack(fill=BOTH, expand=True, pady=(0, 10))

        colunas = ("inicio", "fim", "turmas", "categorias")
        self.tree_grade = ttk.Treeview(
            frame_tabela, columns=colunas, show="headings", height=8
        )
        self.tree_grade.heading("inicio", text="Início")
        self.tree_grade.heading("fim", text="Fim")
        self.tree_grade.heading("turmas", text="Turmas Autorizadas (* = Todas)")
        self.tree_grade.heading("categorias", text="Categorias (* = Todas)")

        self.tree_grade.column("inicio", width=85, anchor=CENTER)
        self.tree_grade.column("fim", width=85, anchor=CENTER)
        self.tree_grade.column("turmas", width=340, stretch=True)
        self.tree_grade.column("categorias", width=160, anchor=CENTER)

        scroll_grade = ttk.Scrollbar(
            frame_tabela, orient="vertical", command=self.tree_grade.yview
        )
        self.tree_grade.configure(yscrollcommand=scroll_grade.set)
        self.tree_grade.pack(side=LEFT, fill=BOTH, expand=True)
        scroll_grade.pack(side=RIGHT, fill=Y)

        lf_add = ttk.Labelframe(self.aba_grade, text=" ➕ Novo Intervalo ", padding=10)
        lf_add.pack(fill=X, pady=(0, 10))

        f_inputs = ttk.Frame(lf_add)
        f_inputs.pack(fill=X, pady=(0, 5))

        ttk.Label(f_inputs, text="Início (HH:MM):").grid(
            row=0, column=0, sticky="w", padx=5
        )
        self.entry_grade_inicio = ttk.Entry(f_inputs, width=10)
        self.entry_grade_inicio.insert(0, "11:30")
        self.entry_grade_inicio.grid(row=1, column=0, sticky="ew", padx=5)

        ttk.Label(f_inputs, text="Fim (HH:MM):").grid(
            row=0, column=1, sticky="w", padx=5
        )
        self.entry_grade_fim = ttk.Entry(f_inputs, width=10)
        self.entry_grade_fim.insert(0, "12:15")
        self.entry_grade_fim.grid(row=1, column=1, sticky="ew", padx=5)

        ttk.Label(f_inputs, text="Turmas (ex.: 1º A, 1º B ou *):").grid(
            row=0, column=2, sticky="w", padx=5
        )
        self.entry_grade_turmas = ttk.Entry(f_inputs, width=28)
        self.entry_grade_turmas.insert(0, "*")
        self.entry_grade_turmas.grid(row=1, column=2, sticky="ew", padx=5)

        ttk.Label(f_inputs, text="Categorias (*, Eventos, Optativas, PAP...):").grid(
            row=0, column=3, sticky="w", padx=5
        )
        self.entry_grade_cats = ttk.Entry(f_inputs, width=22)
        self.entry_grade_cats.insert(0, "*")
        self.entry_grade_cats.grid(row=1, column=3, sticky="ew", padx=5)

        f_inputs.columnconfigure(2, weight=1)

        f_btns_regras = ttk.Frame(lf_add)
        f_btns_regras.pack(fill=X, pady=(8, 0))

        ttk.Button(
            f_btns_regras,
            text="Adicionar Intervalo",
            bootstyle="primary",
            command=self._adicionar_regra_grade,
        ).pack(side=LEFT, padx=(0, 8))

        ttk.Button(
            f_btns_regras,
            text="Remover Intervalo Selecionado",
            bootstyle="danger-outline",
            command=self._remover_regra_grade,
        ).pack(side=LEFT)

        frame_rodape_grade = ttk.Frame(self.aba_grade)
        frame_rodape_grade.pack(fill=X, pady=(5, 0))

        ttk.Button(
            frame_rodape_grade,
            text="💾 Salvar Alterações da Grade",
            bootstyle="success",
            command=self._salvar_grade_horarios,
        ).pack(side=LEFT, padx=(0, 8))

        ttk.Button(
            frame_rodape_grade,
            text="🔄 Restaurar Grade Padrão",
            bootstyle="secondary-outline",
            command=self._restaurar_grade_padrao,
        ).pack(side=LEFT)

        self._grade_atual: Dict[str, Any] = {}

    def _construir_aba_backup(self: Any):
        frame_acoes = ttk.Frame(self.aba_backup)
        frame_acoes.pack(fill=X, pady=(0, 10))

        ttk.Button(
            frame_acoes,
            text="⚡ Criar Backup Agora",
            bootstyle="success",
            command=self._criar_backup_padrao,
            cursor="hand2",
        ).pack(side=LEFT, padx=(0, 8))

        ttk.Button(
            frame_acoes,
            text="📂 Salvar Backup em Outro Local...",
            bootstyle="primary-outline",
            command=self._criar_backup_personalizado,
            cursor="hand2",
        ).pack(side=LEFT, padx=(0, 8))

        ttk.Button(
            frame_acoes,
            text="📁 Abrir Pasta de Backups",
            bootstyle="secondary-outline",
            command=self._abrir_pasta_backups,
            cursor="hand2",
        ).pack(side=LEFT)

        lf_lista = ttk.Labelframe(
            self.aba_backup, text=" 💾 Backups Disponíveis ", padding=8
        )
        lf_lista.pack(fill=BOTH, expand=True, pady=(0, 10))

        colunas = ("arquivo", "data", "tamanho")
        self.tree_backups = ttk.Treeview(
            lf_lista, columns=colunas, show="headings", height=10
        )
        self.tree_backups.heading("arquivo", text="Nome do Arquivo")
        self.tree_backups.heading("data", text="Data e Hora")
        self.tree_backups.heading("tamanho", text="Tamanho")

        self.tree_backups.column("arquivo", width=340)
        self.tree_backups.column("data", width=180)
        self.tree_backups.column("tamanho", width=100)

        scrollbar = ttk.Scrollbar(
            lf_lista, orient="vertical", command=self.tree_backups.yview
        )
        self.tree_backups.configure(yscrollcommand=scrollbar.set)

        self.tree_backups.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        frame_botoes_tabela = ttk.Frame(self.aba_backup)
        frame_botoes_tabela.pack(fill=X)

        ttk.Button(
            frame_botoes_tabela,
            text="🔄 Restaurar Backup Selecionado",
            bootstyle="warning",
            command=self._restaurar_backup_selecionado,
            cursor="hand2",
        ).pack(side=LEFT, padx=(0, 8))

        ttk.Button(
            frame_botoes_tabela,
            text="❌ Excluir Backup Selecionado",
            bootstyle="danger-outline",
            command=self._excluir_backup_selecionado,
            cursor="hand2",
        ).pack(side=LEFT)

    def _construir_aba_geral(self: Any):
        lf_atalhos = ttk.Labelframe(
            self.aba_geral, text=" 🖥️ Atalhos Rápidos & Pastas do Sistema ", padding=12
        )
        lf_atalhos.pack(fill=X, pady=(0, 15))

        frame_botoes_atalhos = ttk.Frame(lf_atalhos)
        frame_botoes_atalhos.pack(fill=X)

        ttk.Button(
            frame_botoes_atalhos,
            text="📌 Criar Atalhos na Área de Trabalho",
            bootstyle="primary-outline",
            command=self._criar_atalhos_desktop,
            cursor="hand2",
        ).pack(side=LEFT, padx=(0, 8))

        ttk.Button(
            frame_botoes_atalhos,
            text="📁 Abrir Pasta config",
            bootstyle="secondary-outline",
            command=lambda: self._abrir_pasta(DIRETORIO_CONFIG),
            cursor="hand2",
        ).pack(side=LEFT, padx=(0, 8))

        ttk.Button(
            frame_botoes_atalhos,
            text="📜 Abrir Pasta de Logs",
            bootstyle="secondary-outline",
            command=lambda: self._abrir_pasta(DIRETORIO_LOG),
            cursor="hand2",
        ).pack(side=LEFT)

        lf_lanches = ttk.Labelframe(
            self.aba_geral,
            text=" 🥪 Gestão de Itens de Refeição (lanches.json) ",
            padding=12,
        )
        lf_lanches.pack(fill=BOTH, expand=True, pady=(0, 15))

        frame_conteudo_lanches = ttk.Frame(lf_lanches)
        frame_conteudo_lanches.pack(fill=BOTH, expand=True)

        self.listbox_lanches = tk.Listbox(
            frame_conteudo_lanches,
            font=("Segoe UI", 9),
            selectmode="single",
            height=6,
        )
        scroll_lanches = ttk.Scrollbar(
            frame_conteudo_lanches,
            orient="vertical",
            command=self.listbox_lanches.yview,
        )
        self.listbox_lanches.configure(yscrollcommand=scroll_lanches.set)

        self.listbox_lanches.pack(side=LEFT, fill=BOTH, expand=True)
        scroll_lanches.pack(side=RIGHT, fill=Y)

        frame_acoes_lanches = ttk.Frame(lf_lanches)
        frame_acoes_lanches.pack(fill=X, pady=(8, 0))

        self.var_novo_lanche = tk.StringVar()
        ttk.Entry(
            frame_acoes_lanches,
            textvariable=self.var_novo_lanche,
            font=("Segoe UI", 9),
        ).pack(side=LEFT, fill=X, expand=True, padx=(0, 8))

        ttk.Button(
            frame_acoes_lanches,
            text="➕ Adicionar",
            bootstyle="success",
            command=self._adicionar_lanche,
            cursor="hand2",
        ).pack(side=LEFT, padx=(0, 6))

        ttk.Button(
            frame_acoes_lanches,
            text="➖ Remover Selecionado",
            bootstyle="danger-outline",
            command=self._remover_lanche,
            cursor="hand2",
        ).pack(side=LEFT)

        lf_perigo = ttk.Labelframe(
            self.aba_geral, text=" ⚠️ Zona de Perigo ", padding=12, bootstyle="danger"
        )
        lf_perigo.pack(fill=X)

        ttk.Label(
            lf_perigo,
            text="Atenção: A redefinição apagará todas as presenças, alunos e turmas do banco local. Um backup será gerado antes.",
            font=("Segoe UI", 8),
            bootstyle="secondary",
        ).pack(anchor="w", pady=(0, 6))

        ttk.Button(
            lf_perigo,
            text="⚠️ Redefinir / Zerar Banco de Dados",
            bootstyle="danger",
            command=self._redefinir_banco_dados,
            cursor="hand2",
        ).pack(anchor="w")
