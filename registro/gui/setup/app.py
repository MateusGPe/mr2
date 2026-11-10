# ----------------------------------------------------------------------------
# Arquivo: registro/gui/setup/app.py (Central de Início Rápido e Configurações)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Interface gráfica da Central de Início Rápido e Configurações do Sistema.
Reúne guias para o Google Cloud, diagnóstico em tempo real, proteção por PIN,
gerenciamento de backups, atalhos do Windows e preferências gerais.
"""

import logging
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import ttkbootstrap as ttk
from ttkbootstrap.constants import (
    BOTH,
    CENTER,
    DISABLED,
    END,
    EW,
    LEFT,
    NORMAL,
    NSEW,
    RIGHT,
    TOP,
    X,
    Y,
)
from ttkbootstrap.dialogs import Messagebox

from registro.gui.comum.dialogo_pin import solicitar_pin
from registro.nucleo import backup_service, config_service
from registro.nucleo.services import grade_horarios_service
from registro.nucleo.constants import (
    CAMINHO_CREDENCIAS,
    CAMINHO_TOKEN,
    DIRETORIO_APP,
    DIRETORIO_BACKUPS,
    DIRETORIO_CONFIG,
    DIRETORIO_LOG,
)

logger = logging.getLogger(__name__)


class AppSetup(ttk.Window):
    """
    Aplicação gráfica principal da Central de Configurações e Início Rápido.
    """

    def __init__(self):
        super().__init__(
            title="⚙️ Central de Configurações & Início Rápido",
            themename="sandstone",
            resizable=(True, True),
        )
        self.geometry("980x700")
        self.minsize(820, 580)
        self._centralizar_janela()

        self._construir_interface()
        self._carregar_dados_iniciais()

    def _centralizar_janela(self):
        self.update_idletasks()
        largura = 980
        altura = 700
        x = max(0, (self.winfo_screenwidth() // 2) - (largura // 2))
        y = max(0, (self.winfo_screenheight() // 2) - (altura // 2))
        self.geometry(f"{largura}x{altura}+{x}+{y}")

    def _construir_interface(self):
        # Cabeçalho Superior
        frame_topo = ttk.Frame(self, padding=(20, 15, 20, 10))
        frame_topo.pack(fill=X)

        lbl_icone = ttk.Label(
            frame_topo, text="⚙️", font=("Segoe UI", 24)
        )
        lbl_icone.pack(side=LEFT, padx=(0, 12))

        frame_titulos = ttk.Frame(frame_topo)
        frame_titulos.pack(side=LEFT, fill=X, expand=True)

        lbl_titulo = ttk.Label(
            frame_titulos,
            text="Central de Configurações & Início Rápido",
            font=("Segoe UI", 16, "bold"),
        )
        lbl_titulo.pack(anchor="w")

        lbl_subtitulo = ttk.Label(
            frame_titulos,
            text="Configure o Google Cloud, personalize a segurança do Totem, gerencie backups e atalhos.",
            font=("Segoe UI", 9),
            bootstyle="secondary",
        )
        lbl_subtitulo.pack(anchor="w")

        btn_atualizar = ttk.Button(
            frame_topo,
            text="🔄 Atualizar Status",
            bootstyle="secondary-outline",
            command=self._carregar_dados_iniciais,
            cursor="hand2",
        )
        btn_atualizar.pack(side=RIGHT, pady=5)

        # Notebook / Abas
        self.notebook = ttk.Notebook(self, bootstyle="primary", padding=10)
        self.notebook.pack(fill=BOTH, expand=True, padx=15, pady=(5, 15))

        self.aba_status = ttk.Frame(self.notebook, padding=15)
        self.aba_google = ttk.Frame(self.notebook, padding=15)
        self.aba_totem = ttk.Frame(self.notebook, padding=15)
        self.aba_grade = ttk.Frame(self.notebook, padding=15)
        self.aba_backup = ttk.Frame(self.notebook, padding=15)
        self.aba_geral = ttk.Frame(self.notebook, padding=15)

        self.notebook.add(self.aba_status, text="  📋 Checklist & Início  ")
        self.notebook.add(self.aba_google, text="  ☁️ Google Cloud & Planilha  ")
        self.notebook.add(self.aba_totem, text="  🔒 Totem & Segurança  ")
        self.notebook.add(self.aba_grade, text="  📅 Grade de Horários  ")
        self.notebook.add(self.aba_backup, text="  💾 Backups & Restauração  ")
        self.notebook.add(self.aba_geral, text="  🛠️ Geral & Utilitários  ")

        self._construir_aba_status()
        self._construir_aba_google()
        self._construir_aba_totem()
        self._construir_aba_grade()
        self._construir_aba_backup()
        self._construir_aba_geral()

    # ------------------------------------------------------------------------
    # ABA 1: Checklist & Início Rápido
    # ------------------------------------------------------------------------

    def _construir_aba_status(self):
        lbl_intro = ttk.Label(
            self.aba_status,
            text="Visão geral e diagnóstico de saúde do sistema:",
            font=("Segoe UI", 11, "bold"),
        )
        lbl_intro.pack(anchor="w", pady=(0, 15))

        # Grade de Cartões de Status
        self.frame_cards = ttk.Frame(self.aba_status)
        self.frame_cards.pack(fill=X, pady=(0, 20))

        for c in range(2):
            self.frame_cards.columnconfigure(c, weight=1, uniform="card")

        # Cartão 1: Banco de Dados
        self.card_db = self._criar_card(
            self.frame_cards, 0, 0, "📦 Banco de Dados SQLite", "Carregando..."
        )
        # Cartão 2: Credenciais Google
        self.card_gcp = self._criar_card(
            self.frame_cards, 0, 1, "☁️ Google Cloud API", "Carregando..."
        )
        # Cartão 3: Planilha Vinculada
        self.card_sheet = self._criar_card(
            self.frame_cards, 1, 0, "📊 Planilha do Sheets", "Carregando..."
        )
        # Cartão 4: Segurança / PIN
        self.card_pin = self._criar_card(
            self.frame_cards, 1, 1, "🔒 Segurança do Totem (PIN)", "Carregando..."
        )

        # Seção de Lançamento de Módulos
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
        self, parent: ttk.Frame, row: int, col: int, titulo: str, texto_inicial: str
    ) -> Dict[str, Any]:
        frame = ttk.Labelframe(parent, text=f" {titulo} ", padding=12)
        frame.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

        lbl_status = ttk.Label(
            frame, text=texto_inicial, font=("Segoe UI", 9), wraplength=400
        )
        lbl_status.pack(anchor="w", fill=X)

        return {"frame": frame, "label": lbl_status}

    # ------------------------------------------------------------------------
    # ABA 2: Google Cloud & Planilhas
    # ------------------------------------------------------------------------

    def _construir_aba_google(self):
        # Passo a Passo com links
        lf_guia = ttk.Labelframe(
            self.aba_google, text=" 📖 Guia de Configuração no Google Cloud ", padding=12
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

        # Arquivo de Credenciais
        lf_cred = ttk.Labelframe(
            self.aba_google, text=" 📂 Arquivo de Credenciais (credentials.json) ", padding=12
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

        # Planilha do Google Sheets
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

        # Testar Conexão
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

    def _importar_credenciais(self):
        arquivo = filedialog.askopenfilename(
            title="Selecione o arquivo de credenciais JSON",
            filetypes=[("Arquivos JSON", "*.json"), ("Todos os arquivos", "*.*")],
            parent=self,
        )
        if arquivo:
            if config_service.salvar_arquivo_credenciais(arquivo):
                Messagebox.show_info(
                    "Arquivo salvo com sucesso em 'config/credentials.json'!",
                    "Credenciais Importadas",
                    parent=self,
                )
                self._carregar_dados_iniciais()
            else:
                Messagebox.show_error(
                    "Não foi possível copiar o arquivo selecionado.", "Erro", parent=self
                )

    def _limpar_token(self):
        if not CAMINHO_TOKEN.exists():
            Messagebox.show_info(
                "Nenhum arquivo de token ativo encontrado.", "Token", parent=self
            )
            return

        confirma = Messagebox.show_question(
            "Deseja remover o token de autenticação atual? Isso exigirá novo login na próxima sincronização.",
            "Limpar Token",
            parent=self,
        )
        if confirma == "Yes" or confirma is True:
            config_service.limpar_token()
            Messagebox.show_info(
                "Token de autenticação removido com sucesso.", "Sucesso", parent=self
            )
            self._carregar_dados_iniciais()

    def _salvar_id_planilha(self):
        valor = self.var_planilha_input.get().strip()
        if not valor:
            Messagebox.show_warning(
                "Por favor, digite ou cole o ID ou link da planilha.", "Atenção", parent=self
            )
            return

        id_extraido = config_service.salvar_id_planilha(valor)
        self.var_planilha_input.set(id_extraido)
        Messagebox.show_info(
            f"ID da planilha configurado com sucesso:\n{id_extraido}",
            "Planilha Salva",
            parent=self,
        )
        self._carregar_dados_iniciais()

    def _testar_conexao_em_thread(self):
        self.btn_testar_conexao.config(state=DISABLED)
        self.btn_criar_abas.config(state=DISABLED)
        self.lbl_teste_resultado.config(
            text="⏳ Testando conexão e autenticação...", bootstyle="info"
        )

        def _rodar():
            sucesso, msg = config_service.testar_conexao_google_sheets()
            self.after(0, lambda: self._finalizar_teste_conexao(sucesso, msg))

        threading.Thread(target=_rodar, daemon=True).start()

    def _finalizar_teste_conexao(self, sucesso: bool, msg: str):
        self.btn_testar_conexao.config(state=NORMAL)
        self.btn_criar_abas.config(state=NORMAL)
        if sucesso:
            self.lbl_teste_resultado.config(text="✅ " + msg, bootstyle="success")
        else:
            self.lbl_teste_resultado.config(
                text="❌ Falha na conexão. Clique para ver detalhes.", bootstyle="danger"
            )
            Messagebox.show_error(
                msg, "Diagnóstico de Conexão", parent=self
            )

    def _criar_abas_em_thread(self):
        self.btn_criar_abas.config(state=DISABLED)
        self.btn_testar_conexao.config(state=DISABLED)
        self.lbl_teste_resultado.config(
            text="⏳ Verificando e estruturando abas na planilha...", bootstyle="info"
        )

        def _rodar():
            sucesso, msg, detalhes = config_service.inicializar_estrutura_planilha()
            self.after(
                0, lambda: self._finalizar_criacao_abas(sucesso, msg, detalhes)
            )

        threading.Thread(target=_rodar, daemon=True).start()

    def _finalizar_criacao_abas(
        self, sucesso: bool, msg: str, detalhes: Dict[str, List[str]]
    ):
        self.btn_criar_abas.config(state=NORMAL)
        self.btn_testar_conexao.config(state=NORMAL)
        if sucesso:
            self.lbl_teste_resultado.config(
                text="✅ Estrutura de abas concluída com sucesso!", bootstyle="success"
            )
            Messagebox.show_info(
                title="Estrutura de Abas",
                message=f"Processamento concluído com sucesso:\n\n{msg}",
                parent=self,
            )
        else:
            self.lbl_teste_resultado.config(
                text="❌ Falha ao criar abas na planilha.", bootstyle="danger"
            )
            Messagebox.show_error(
                msg, "Erro ao Criar Abas", parent=self
            )

    # ------------------------------------------------------------------------
    # ABA 3: Totem & Segurança (PIN)
    # ------------------------------------------------------------------------

    def _construir_aba_totem(self):
        # Grupo de PIN
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

        # Grupo de Preferências do Totem
        lf_pref = ttk.Labelframe(
            self.aba_totem, text=" ⚙️ Preferências do Totem de Autoatendimento ", padding=12
        )
        lf_pref.pack(fill=X, pady=(0, 10))

        self.var_fullscreen = tk.BooleanVar()
        chk_fullscreen = ttk.Checkbutton(
            lf_pref,
            text="Iniciar automaticamente em Tela Cheia (F11)",
            variable=self.var_fullscreen,
        )
        chk_fullscreen.pack(anchor="w", pady=4)

        self.var_camera_start = tk.BooleanVar()
        chk_camera = ttk.Checkbutton(
            lf_pref,
            text="Ativar câmera / webcam automaticamente ao abrir o Totem",
            variable=self.var_camera_start,
        )
        chk_camera.pack(anchor="w", pady=4)

        self.var_require_pin_exit = tk.BooleanVar()
        chk_pin_exit = ttk.Checkbutton(
            lf_pref,
            text="Exigir PIN para sair do Totem ou fechar a janela",
            variable=self.var_require_pin_exit,
        )
        chk_pin_exit.pack(anchor="w", pady=4)

        frame_delay = ttk.Frame(lf_pref)
        frame_delay.pack(anchor="w", pady=6)

        lbl_delay = ttk.Label(
            frame_delay,
            text="Tempo de exibição da confirmação verde na tela (ms):",
            font=("Segoe UI", 9),
        )
        lbl_delay.pack(side=LEFT, padx=(0, 8))

        self.var_delay_ms = tk.StringVar(value="1500")
        entry_delay = ttk.Entry(frame_delay, textvariable=self.var_delay_ms, width=8)
        entry_delay.pack(side=LEFT)

        btn_salvar_totem = ttk.Button(
            lf_pref,
            text="💾 Salvar Preferências do Totem",
            bootstyle="primary",
            command=self._salvar_preferencias_totem,
            cursor="hand2",
        )
        btn_salvar_totem.pack(anchor="w", pady=(12, 0))

    def _alternar_visibilidade_pin(self):
        caractere = "" if self.var_mostrar_pin.get() else "●"
        self.entry_novo_pin.config(show=caractere)
        self.entry_confirma_pin.config(show=caractere)

    def _salvar_pin(self):
        novo = self.var_novo_pin.get().strip()
        confirma = self.var_confirma_pin.get().strip()

        if not novo:
            Messagebox.show_warning(
                "Por favor, digite um PIN numérico.", "PIN Vazio", parent=self
            )
            return

        if not novo.isdigit():
            Messagebox.show_warning(
                "O PIN deve conter apenas números.", "Formato Inválido", parent=self
            )
            return

        if len(novo) < 4:
            Messagebox.show_warning(
                "O PIN deve ter no mínimo 4 dígitos.", "PIN Muito Curto", parent=self
            )
            return

        if novo != confirma:
            Messagebox.show_error(
                "Os valores digitados nos dois campos de PIN não coincidem.", "Divergência", parent=self
            )
            return

        if config_service.tem_pin_configurado():
            if not solicitar_pin(
                parent=self,
                titulo="🔒 Confirmar Alteração",
                mensagem="Digite o PIN atual para autorizar a alteração:",
            ):
                return

        config_service.definir_pin(novo)
        self.var_novo_pin.set("")
        self.var_confirma_pin.set("")
        Messagebox.show_info("Novo PIN configurado com sucesso!", "Sucesso", parent=self)
        self._carregar_dados_iniciais()

    def _remover_pin(self):
        if not config_service.tem_pin_configurado():
            Messagebox.show_info(
                "Nenhum PIN está configurado no momento.", "Aviso", parent=self
            )
            return

        if not solicitar_pin(
            parent=self,
            titulo="🔒 Remover PIN",
            mensagem="Digite o PIN de operador para confirmar a remoção:",
        ):
            return

        config_service.remover_pin()
        Messagebox.show_info(
            "O PIN de segurança foi desativado.", "PIN Removido", parent=self
        )
        self._carregar_dados_iniciais()

    def _salvar_preferencias_totem(self):
        try:
            delay = int(self.var_delay_ms.get().strip())
        except ValueError:
            Messagebox.show_warning(
                "O tempo de confirmação deve ser um número inteiro em milissegundos (ex: 1500).",
                "Valor Inválido",
                parent=self,
            )
            return

        config = config_service.obter_configuracoes()
        totem = config.get("totem", {})
        totem["fullscreen"] = self.var_fullscreen.get()
        totem["camera_on_start"] = self.var_camera_start.get()
        totem["require_pin_to_exit"] = self.var_require_pin_exit.get()
        totem["feedback_delay_ms"] = max(500, delay)

        config["totem"] = totem
        config_service.salvar_configuracoes(config)

        Messagebox.show_info(
            "Preferências do Totem salvas com sucesso!", "Salvo", parent=self
        )
        self._carregar_dados_iniciais()

    # ------------------------------------------------------------------------
    # ABA: Grade de Horários Semanal
    # ------------------------------------------------------------------------

    def _construir_aba_grade(self):
        lbl_intro = ttk.Label(
            self.aba_grade,
            text="Configuração e Escalonamento da Grade Horária Semanal (grade_horarios.json):",
            font=("Segoe UI", 11, "bold"),
        )
        lbl_intro.pack(anchor="w", pady=(0, 5))

        lbl_desc = ttk.Label(
            self.aba_grade,
            text="Defina os horários de início/fim e turmas/categorias autorizadas para cada dia e refeição.",
            bootstyle="secondary",
        )
        lbl_desc.pack(anchor="w", pady=(0, 15))

        # Barra de Seleção de Dia e Refeição
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
        self.cbo_grade_dia.bind("<<ComboboxSelected>>", lambda *_: self._carregar_regras_grade())

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
        self.cbo_grade_refeicao.bind("<<ComboboxSelected>>", lambda *_: self._carregar_regras_grade())

        # Tabela de Regras de Horário
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

        # Formulário para Adicionar Intervalo
        lf_add = ttk.Labelframe(self.aba_grade, text=" ➕ Novo Intervalo ", padding=10)
        lf_add.pack(fill=X, pady=(0, 10))

        f_inputs = ttk.Frame(lf_add)
        f_inputs.pack(fill=X, pady=(0, 5))

        ttk.Label(f_inputs, text="Início (HH:MM):").grid(row=0, column=0, sticky="w", padx=5)
        self.entry_grade_inicio = ttk.Entry(f_inputs, width=10)
        self.entry_grade_inicio.insert(0, "11:30")
        self.entry_grade_inicio.grid(row=1, column=0, sticky="ew", padx=5)

        ttk.Label(f_inputs, text="Fim (HH:MM):").grid(row=0, column=1, sticky="w", padx=5)
        self.entry_grade_fim = ttk.Entry(f_inputs, width=10)
        self.entry_grade_fim.insert(0, "12:15")
        self.entry_grade_fim.grid(row=1, column=1, sticky="ew", padx=5)

        ttk.Label(f_inputs, text="Turmas (ex.: 1º A, 1º B ou *):").grid(row=0, column=2, sticky="w", padx=5)
        self.entry_grade_turmas = ttk.Entry(f_inputs, width=28)
        self.entry_grade_turmas.insert(0, "*")
        self.entry_grade_turmas.grid(row=1, column=2, sticky="ew", padx=5)

        ttk.Label(f_inputs, text="Categorias (*, REGULAR, PAP):").grid(row=0, column=3, sticky="w", padx=5)
        self.entry_grade_cats = ttk.Entry(f_inputs, width=22)
        self.entry_grade_cats.insert(0, "*")
        self.entry_grade_cats.grid(row=1, column=3, sticky="ew", padx=5)

        f_inputs.columnconfigure(2, weight=1)

        f_btns_regras = ttk.Frame(lf_add)
        f_btns_regras.pack(fill=X, pady=(8, 0))

        btn_add_regra = ttk.Button(
            f_btns_regras,
            text="Adicionar Intervalo",
            bootstyle="primary",
            command=self._adicionar_regra_grade,
        )
        btn_add_regra.pack(side=LEFT, padx=(0, 8))

        btn_del_regra = ttk.Button(
            f_btns_regras,
            text="Remover Intervalo Selecionado",
            bootstyle="danger-outline",
            command=self._remover_regra_grade,
        )
        btn_del_regra.pack(side=LEFT)

        # Barra de Ações Gerais da Grade
        frame_rodape_grade = ttk.Frame(self.aba_grade)
        frame_rodape_grade.pack(fill=X, pady=(5, 0))

        btn_salvar = ttk.Button(
            frame_rodape_grade,
            text="💾 Salvar Alterações da Grade",
            bootstyle="success",
            command=self._salvar_grade_horarios,
        )
        btn_salvar.pack(side=LEFT, padx=(0, 8))

        btn_restaurar = ttk.Button(
            frame_rodape_grade,
            text="🔄 Restaurar Grade Padrão",
            bootstyle="secondary-outline",
            command=self._restaurar_grade_padrao,
        )
        btn_restaurar.pack(side=LEFT)

        self._grade_atual: Dict[str, Any] = {}

    def _carregar_grade_horarios(self):
        """Carrega a grade de horários do disco e atualiza a interface."""
        self._grade_atual = grade_horarios_service.carregar_grade_horarios()
        self._carregar_regras_grade()

    def _obter_chaves_dia_refeicao(self) -> Tuple[str, str]:
        dia_texto = self.cbo_grade_dia.get()
        ref_texto = self.cbo_grade_refeicao.get()
        dia_chave = self.dias_grade_map.get(dia_texto, "segunda")
        ref_chave = self.refeicoes_grade_map.get(ref_texto, "almoco")
        return dia_chave, ref_chave

    def _carregar_regras_grade(self):
        """Preenche o treeview com as regras do dia e refeição selecionados."""
        for item in self.tree_grade.get_children():
            self.tree_grade.delete(item)

        dia_chave, ref_chave = self._obter_chaves_dia_refeicao()
        regras = (
            self._grade_atual.get(dia_chave, {}).get(ref_chave, [])
            if self._grade_atual
            else []
        )

        for idx, regra in enumerate(regras):
            ini = regra.get("inicio", "")
            fim = regra.get("fim", "")
            turmas = ", ".join(regra.get("turmas", [])) or "*"
            cats = ", ".join(regra.get("categorias", [])) or "*"
            self.tree_grade.insert("", "end", iid=str(idx), values=(ini, fim, turmas, cats))

    def _adicionar_regra_grade(self):
        """Adiciona um novo intervalo de horário ao dia e refeição selecionados."""
        ini = self.entry_grade_inicio.get().strip()
        fim = self.entry_grade_fim.get().strip()
        turmas_str = self.entry_grade_turmas.get().strip()
        cats_str = self.entry_grade_cats.get().strip()

        if not ini or not fim:
            Messagebox.show_warning("Horários de início e fim são obrigatórios.", "Validação", parent=self)
            return

        try:
            grade_horarios_service._hora_para_minutos(ini)
            grade_horarios_service._hora_para_minutos(fim)
        except Exception as e:
            Messagebox.show_error(f"Formato de horário inválido: {e}", "Erro de Formatação", parent=self)
            return

        turmas = (
            [t.strip() for t in turmas_str.split(",") if t.strip()]
            if turmas_str and turmas_str != "*"
            else ["*"]
        )
        cats = (
            [c.strip().upper() for c in cats_str.split(",") if c.strip()]
            if cats_str and cats_str != "*"
            else ["*"]
        )

        dia_chave, ref_chave = self._obter_chaves_dia_refeicao()
        if dia_chave not in self._grade_atual:
            self._grade_atual[dia_chave] = {"almoco": [], "jantar": [], "lanche": []}
        if ref_chave not in self._grade_atual[dia_chave]:
            self._grade_atual[dia_chave][ref_chave] = []

        nova_regra = {
            "inicio": ini,
            "fim": fim,
            "turmas": turmas,
            "categorias": cats,
        }
        self._grade_atual[dia_chave][ref_chave].append(nova_regra)
        self._carregar_regras_grade()

    def _remover_regra_grade(self):
        """Remove o intervalo selecionado no Treeview."""
        selecionados = self.tree_grade.selection()
        if not selecionados:
            Messagebox.show_warning("Selecione um intervalo para remover.", "Aviso", parent=self)
            return

        dia_chave, ref_chave = self._obter_chaves_dia_refeicao()
        regras = self._grade_atual.get(dia_chave, {}).get(ref_chave, [])

        idx = int(selecionados[0])
        if 0 <= idx < len(regras):
            regras.pop(idx)
            self._carregar_regras_grade()

    def _salvar_grade_horarios(self):
        """Persiste a grade semanal no arquivo JSON."""
        sucesso = grade_horarios_service.salvar_grade_horarios(self._grade_atual)
        if sucesso:
            Messagebox.show_info("Grade horária semanal salva com sucesso!", "Grade Salva", parent=self)
        else:
            Messagebox.show_error("Não foi possível salvar o arquivo grade_horarios.json.", "Erro ao Salvar", parent=self)

    def _restaurar_grade_padrao(self):
        """Restaura a grade horária semanal para a matriz padrão."""
        import copy
        from ttkbootstrap.dialogs import MessageCatalog

        resp = Messagebox.yesno(
            "Deseja realmente restaurar a grade horária para a configuração padrão?",
            "Restaurar Padrão",
            parent=self,
        )
        if resp == MessageCatalog.translate("Yes"):
            self._grade_atual = copy.deepcopy(grade_horarios_service.GRADE_PADRAO)
            grade_horarios_service.salvar_grade_horarios(self._grade_atual)
            self._carregar_regras_grade()
            Messagebox.show_info("Grade horária padrão restaurada!", "Restaurado", parent=self)

    # ------------------------------------------------------------------------
    # ABA 4: Backups & Restauração
    # ------------------------------------------------------------------------

    def _construir_aba_backup(self):
        frame_acoes = ttk.Frame(self.aba_backup)
        frame_acoes.pack(fill=X, pady=(0, 10))

        btn_criar_padrao = ttk.Button(
            frame_acoes,
            text="⚡ Criar Backup Agora",
            bootstyle="success",
            command=self._criar_backup_padrao,
            cursor="hand2",
        )
        btn_criar_padrao.pack(side=LEFT, padx=(0, 8))

        btn_criar_custom = ttk.Button(
            frame_acoes,
            text="📂 Salvar Backup em Outro Local...",
            bootstyle="primary-outline",
            command=self._criar_backup_personalizado,
            cursor="hand2",
        )
        btn_criar_custom.pack(side=LEFT, padx=(0, 8))

        btn_abrir_pasta = ttk.Button(
            frame_acoes,
            text="📁 Abrir Pasta de Backups",
            bootstyle="secondary-outline",
            command=self._abrir_pasta_backups,
            cursor="hand2",
        )
        btn_abrir_pasta.pack(side=LEFT)

        # Tabela de Backups Existentes
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

        btn_restaurar = ttk.Button(
            frame_botoes_tabela,
            text="🔄 Restaurar Backup Selecionado",
            bootstyle="warning",
            command=self._restaurar_backup_selecionado,
            cursor="hand2",
        )
        btn_restaurar.pack(side=LEFT, padx=(0, 8))

        btn_excluir = ttk.Button(
            frame_botoes_tabela,
            text="❌ Excluir Backup Selecionado",
            bootstyle="danger-outline",
            command=self._excluir_backup_selecionado,
            cursor="hand2",
        )
        btn_excluir.pack(side=LEFT)

    def _atualizar_lista_backups(self):
        for item in self.tree_backups.get_children():
            self.tree_backups.delete(item)

        backups = backup_service.listar_backups()
        for b in backups:
            self.tree_backups.insert(
                "",
                END,
                iid=str(b["caminho"]),
                values=(b["nome"], b["data"], b["tamanho"]),
            )

    def _criar_backup_padrao(self):
        try:
            zip_criado = backup_service.criar_backup()
            Messagebox.show_info(
                f"Backup gerado com sucesso em:\n{zip_criado.name}",
                "Backup Realizado",
                parent=self,
            )
            self._atualizar_lista_backups()
            self._carregar_dados_iniciais()
        except Exception as e:
            Messagebox.show_error(
                f"Não foi possível criar o backup:\n{e}", "Erro no Backup", parent=self
            )

    def _criar_backup_personalizado(self):
        pasta = filedialog.askdirectory(
            title="Selecione o diretório ou pen drive de destino", parent=self
        )
        if pasta:
            try:
                zip_criado = backup_service.criar_backup(destino_personalizado=pasta)
                Messagebox.show_info(
                    f"Backup salvo com sucesso em:\n{zip_criado}",
                    "Backup Concluído",
                    parent=self,
                )
                self._atualizar_lista_backups()
                self._carregar_dados_iniciais()
            except Exception as e:
                Messagebox.show_error(
                    f"Falha ao salvar backup no destino:\n{e}", "Erro", parent=self
                )

    def _abrir_pasta_backups(self):
        DIRETORIO_BACKUPS.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(DIRETORIO_BACKUPS))
        except Exception as e:
            Messagebox.show_error(
                f"Não foi possível abrir o Explorer:\n{e}", "Erro", parent=self
            )

    def _restaurar_backup_selecionado(self):
        sel = self.tree_backups.selection()
        if not sel:
            Messagebox.show_warning(
                "Selecione um arquivo de backup na lista para restaurar.",
                "Seleção Obrigatória",
                parent=self,
            )
            return

        caminho_zip = Path(sel[0])

        if config_service.tem_pin_configurado():
            if not solicitar_pin(
                parent=self,
                titulo="🔒 Autorização de Restauração",
                mensagem="Digite o PIN de operador para autorizar a restauração:",
            ):
                return

        confirma = Messagebox.show_question(
            f"Tem certeza de que deseja restaurar o backup '{caminho_zip.name}'?\n\n"
            "Os arquivos atuais de configuração e banco de dados serão substituídos "
            "(uma salvaguarda prévia será criada automaticamente).",
            "Confirmar Restauração",
            parent=self,
        )
        if confirma == "Yes" or confirma is True:
            sucesso, msg = backup_service.restaurar_backup(caminho_zip)
            if sucesso:
                Messagebox.show_info(msg, "Restauração Concluída", parent=self)
                self._atualizar_lista_backups()
                self._carregar_dados_iniciais()
            else:
                Messagebox.show_error(msg, "Falha na Restauração", parent=self)

    def _excluir_backup_selecionado(self):
        sel = self.tree_backups.selection()
        if not sel:
            Messagebox.show_warning(
                "Selecione um arquivo de backup para excluir.",
                "Seleção Obrigatória",
                parent=self,
            )
            return

        caminho_zip = Path(sel[0])
        confirma = Messagebox.show_question(
            f"Deseja realmente excluir permanentemente o arquivo '{caminho_zip.name}'?",
            "Excluir Backup",
            parent=self,
        )
        if confirma == "Yes" or confirma is True:
            if backup_service.excluir_backup(caminho_zip):
                self._atualizar_lista_backups()
                self._carregar_dados_iniciais()
            else:
                Messagebox.show_error(
                    "Não foi possível excluir o arquivo.", "Erro", parent=self
                )

    # ------------------------------------------------------------------------
    # ABA 5: Geral & Utilitários
    # ------------------------------------------------------------------------

    def _construir_aba_geral(self):
        # Atalhos do Windows
        lf_atalhos = ttk.Labelframe(
            self.aba_geral, text=" 🖥️ Atalhos Rápidos & Pastas do Sistema ", padding=12
        )
        lf_atalhos.pack(fill=X, pady=(0, 15))

        frame_botoes_atalhos = ttk.Frame(lf_atalhos)
        frame_botoes_atalhos.pack(fill=X)

        btn_desktop = ttk.Button(
            frame_botoes_atalhos,
            text="📌 Criar Atalhos na Área de Trabalho",
            bootstyle="primary-outline",
            command=self._criar_atalhos_desktop,
            cursor="hand2",
        )
        btn_desktop.pack(side=LEFT, padx=(0, 8))

        btn_pasta_config = ttk.Button(
            frame_botoes_atalhos,
            text="📁 Abrir Pasta config",
            bootstyle="secondary-outline",
            command=lambda: self._abrir_pasta(DIRETORIO_CONFIG),
            cursor="hand2",
        )
        btn_pasta_config.pack(side=LEFT, padx=(0, 8))

        btn_pasta_logs = ttk.Button(
            frame_botoes_atalhos,
            text="📜 Abrir Pasta de Logs",
            bootstyle="secondary-outline",
            command=lambda: self._abrir_pasta(DIRETORIO_LOG),
            cursor="hand2",
        )
        btn_pasta_logs.pack(side=LEFT)

        # Gestão de Itens de Refeição (Lanches)
        lf_lanches = ttk.Labelframe(
            self.aba_geral, text=" 🥪 Gestão de Itens de Refeição (lanches.json) ", padding=12
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
            frame_conteudo_lanches, orient="vertical", command=self.listbox_lanches.yview
        )
        self.listbox_lanches.configure(yscrollcommand=scroll_lanches.set)

        self.listbox_lanches.pack(side=LEFT, fill=BOTH, expand=True)
        scroll_lanches.pack(side=RIGHT, fill=Y)

        frame_acoes_lanches = ttk.Frame(lf_lanches)
        frame_acoes_lanches.pack(fill=X, pady=(8, 0))

        self.var_novo_lanche = tk.StringVar()
        entry_lanche = ttk.Entry(
            frame_acoes_lanches,
            textvariable=self.var_novo_lanche,
            font=("Segoe UI", 9),
        )
        entry_lanche.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))

        btn_add_lanche = ttk.Button(
            frame_acoes_lanches,
            text="➕ Adicionar",
            bootstyle="success",
            command=self._adicionar_lanche,
            cursor="hand2",
        )
        btn_add_lanche.pack(side=LEFT, padx=(0, 6))

        btn_rem_lanche = ttk.Button(
            frame_acoes_lanches,
            text="➖ Remover Selecionado",
            bootstyle="danger-outline",
            command=self._remover_lanche,
            cursor="hand2",
        )
        btn_rem_lanche.pack(side=LEFT)

        # Zona de Perigo
        lf_perigo = ttk.Labelframe(
            self.aba_geral, text=" ⚠️ Zona de Perigo ", padding=12, bootstyle="danger"
        )
        lf_perigo.pack(fill=X)

        lbl_perigo_desc = ttk.Label(
            lf_perigo,
            text="Atenção: A redefinição apagará todas as presenças, alunos e turmas do banco local. Um backup será gerado antes.",
            font=("Segoe UI", 8),
            bootstyle="secondary",
        )
        lbl_perigo_desc.pack(anchor="w", pady=(0, 6))

        btn_reset_db = ttk.Button(
            lf_perigo,
            text="⚠️ Redefinir / Zerar Banco de Dados",
            bootstyle="danger",
            command=self._redefinir_banco_dados,
            cursor="hand2",
        )
        btn_reset_db.pack(anchor="w")

    def _abrir_pasta(self, pasta: Path):
        pasta.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(pasta))
        except Exception as e:
            Messagebox.show_error(
                f"Não foi possível abrir a pasta:\n{e}", "Erro", parent=self
            )

    def _adicionar_lanche(self):
        item = self.var_novo_lanche.get().strip()
        if not item:
            return

        lanches = config_service.obter_lanches()
        if item in lanches:
            Messagebox.show_warning("Este item já está cadastrado.", "Item Existente", parent=self)
            return

        lanches.append(item)
        config_service.salvar_lanches(lanches)
        self.var_novo_lanche.set("")
        self._carregar_lanches()

    def _remover_lanche(self):
        sel = self.listbox_lanches.curselection()
        if not sel:
            return

        idx = sel[0]
        lanches = config_service.obter_lanches()
        if 0 <= idx < len(lanches):
            item = lanches.pop(idx)
            config_service.salvar_lanches(lanches)
            self._carregar_lanches()

    def _carregar_lanches(self):
        self.listbox_lanches.delete(0, END)
        lanches = config_service.obter_lanches()
        for item in lanches:
            self.listbox_lanches.insert(END, item)

    def _criar_atalhos_desktop(self):
        """Cria scripts de inicialização rápida na Área de Trabalho do Windows."""
        try:
            desktop = Path.home() / "Desktop"
            if not desktop.exists():
                desktop = Path.home() / "Área de Trabalho"

            if getattr(sys, "frozen", False):
                exe_path = Path(sys.executable).resolve()
                atalho_totem = f'@echo off\nstart "" "{exe_path}" --auto\n'
                atalho_reg = f'@echo off\nstart "" "{exe_path}" --reg\n'
                atalho_painel = f'@echo off\nstart "" "{exe_path}" --painel\n'
            else:
                dir_proj = DIRETORIO_APP.resolve()
                atalho_totem = f'@echo off\ncd /d "{dir_proj}"\ncall uv run autoatendimento\n'
                atalho_reg = f'@echo off\ncd /d "{dir_proj}"\ncall uv run registrar\n'
                atalho_painel = f'@echo off\ncd /d "{dir_proj}"\ncall uv run painel\n'

            (desktop / "Totem Autoatendimento.bat").write_text(atalho_totem, encoding="utf-8")
            (desktop / "Registro de Refeicoes.bat").write_text(atalho_reg, encoding="utf-8")
            (desktop / "Painel Administrativo.bat").write_text(atalho_painel, encoding="utf-8")

            Messagebox.show_info(
                "Atalhos gerados com sucesso na sua Área de Trabalho!",
                "Atalhos Criados",
                parent=self,
            )
        except Exception as e:
            Messagebox.show_error(
                f"Não foi possível criar os atalhos:\n{e}", "Erro", parent=self
            )

    def _redefinir_banco_dados(self):
        if config_service.tem_pin_configurado():
            if not solicitar_pin(
                parent=self,
                titulo="🔒 Confirmação com PIN",
                mensagem="Digite o PIN de segurança para zerar o banco de dados:",
            ):
                return

        confirma = Messagebox.show_question(
            "ATENÇÃO: Todos os dados serão limpos e o banco recriado.\n"
            "Deseja realmente continuar?",
            "Confirmação Extrema",
            parent=self,
        )
        if confirma == "Yes" or confirma is True:
            sucesso, msg = backup_service.redefinir_banco_dados(criar_backup_previo=True)
            if sucesso:
                Messagebox.show_info(msg, "Concluído", parent=self)
                self._carregar_dados_iniciais()
            else:
                Messagebox.show_error(msg, "Erro", parent=self)

    # ------------------------------------------------------------------------
    # Carregamento e Atualização de Dados Gerais
    # ------------------------------------------------------------------------

    def _carregar_dados_iniciais(self):
        status = config_service.obter_status_sistema()

        # 1. Card DB
        db = status["banco_dados"]
        if db["existe"]:
            txt_db = (
                f"✅ Conectado ({db['tamanho_kb']} KB)\n"
                f"Estudantes: {db['total_alunos']}  |  Registros de Consumo: {db['total_consumos']}"
            )
        else:
            txt_db = "⚠️ Banco de dados local ainda não criado."
        self.card_db["label"].config(text=txt_db)

        # 2. Card GCP
        gcp = status["google_cloud"]
        if gcp["credenciais_ok"]:
            txt_gcp = "✅ credentials.json detectado"
            txt_gcp += "  |  Token ativo" if gcp["token_ok"] else "  |  Token pendente"
            self.lbl_cred_status.config(
                text="✅ Arquivo 'credentials.json' presente e configurado.",
                bootstyle="success",
            )
        else:
            txt_gcp = "❌ credentials.json não encontrado"
            self.lbl_cred_status.config(
                text="⚠️ Arquivo 'credentials.json' ausente. Importe o arquivo JSON gerado no GCP.",
                bootstyle="warning",
            )
        self.card_gcp["label"].config(text=txt_gcp)

        # 3. Card Planilha
        p_id = gcp["planilha_id"]
        if p_id:
            txt_sheet = f"✅ Planilha Vinculada\nID: {p_id}"
            self.var_planilha_input.set(p_id)
        else:
            txt_sheet = "⚠️ Nenhuma planilha vinculada em spreadsheet.json"
            self.var_planilha_input.set("")
        self.card_sheet["label"].config(text=txt_sheet)

        # 4. Card PIN
        tem_pin = status["totem"]["pin_ativo"]
        if tem_pin:
            txt_pin = "✅ PIN do Operador ATIVO e protegido"
            self.lbl_pin_status.config(
                text="Status: ✅ PIN de operador configurado e ativo.",
                bootstyle="success",
            )
        else:
            txt_pin = "⚠️ Nenhum PIN configurado (Menu e saída livres)"
            self.lbl_pin_status.config(
                text="Status: ⚠️ Nenhum PIN definido. O Totem opera sem restrição de acesso.",
                bootstyle="warning",
            )
        self.card_pin["label"].config(text=txt_pin)

        # Preferências do Totem
        totem_cfg = config_service.obter_config_totem()
        self.var_fullscreen.set(totem_cfg.get("fullscreen", False))
        self.var_camera_start.set(totem_cfg.get("camera_on_start", True))
        self.var_require_pin_exit.set(totem_cfg.get("require_pin_to_exit", True))
        self.var_delay_ms.set(str(totem_cfg.get("feedback_delay_ms", 1500)))

        # Backups
        self._atualizar_lista_backups()

        # Lanches
        self._carregar_lanches()

        # Grade de Horários
        self._carregar_grade_horarios()

    # ------------------------------------------------------------------------
    # Inicialização de Módulos
    # ------------------------------------------------------------------------

    def _iniciar_modulo_totem(self):
        from registro.launcher import executar_autoatendimento

        self.destroy()
        executar_autoatendimento()

    def _iniciar_modulo_registrar(self):
        from registro.launcher import executar_registrar

        self.destroy()
        executar_registrar()

    def _iniciar_modulo_painel(self):
        from registro.launcher import executar_painel

        self.destroy()
        executar_painel()


def main():
    """Ponto de entrada para a Central de Configurações & Início Rápido."""
    from registro.nucleo.logging_config import configurar_logging
    from registro.launcher import verificar_e_migrar_banco_se_necessario

    configurar_logging("setup")
    verificar_e_migrar_banco_se_necessario()
    app = AppSetup()
    app.mainloop()


if __name__ == "__main__":
    main()
