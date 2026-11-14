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
import threading
from pathlib import Path
from tkinter import filedialog
from typing import Dict, List, Tuple

import ttkbootstrap as ttk
from ttkbootstrap.constants import (
    BOTH,
    DISABLED,
    END,
    LEFT,
    NORMAL,
    RIGHT,
    X,
)
from ttkbootstrap.dialogs import Messagebox

from registro.gui.comum.dialogo_pin import solicitar_pin
from registro.gui.setup import actions as setup_actions
from registro.gui.setup._tabs import _SetupTabsMixin
from registro.nucleo import backup_service, config_service
from registro.nucleo.constants import (
    CAMINHO_TOKEN,
    DIRETORIO_BACKUPS,
)
from registro.nucleo.services import grade_horarios_service

logger = logging.getLogger(__name__)


class AppSetup(ttk.Window, _SetupTabsMixin):
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

        lbl_icone = ttk.Label(frame_topo, text="⚙️", font=("Segoe UI", 24))
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
                    "Não foi possível copiar o arquivo selecionado.",
                    "Erro",
                    parent=self,
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
                "Por favor, digite ou cole o ID ou link da planilha.",
                "Atenção",
                parent=self,
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
                text="❌ Falha na conexão. Clique para ver detalhes.",
                bootstyle="danger",
            )
            Messagebox.show_error(msg, "Diagnóstico de Conexão", parent=self)

    def _criar_abas_em_thread(self):
        self.btn_criar_abas.config(state=DISABLED)
        self.btn_testar_conexao.config(state=DISABLED)
        self.lbl_teste_resultado.config(
            text="⏳ Verificando e estruturando abas na planilha...", bootstyle="info"
        )

        def _rodar():
            sucesso, msg, detalhes = config_service.inicializar_estrutura_planilha()
            self.after(0, lambda: self._finalizar_criacao_abas(sucesso, msg, detalhes))

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
            Messagebox.show_error(msg, "Erro ao Criar Abas", parent=self)

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
                "Os valores digitados nos dois campos de PIN não coincidem.",
                "Divergência",
                parent=self,
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
        Messagebox.show_info(
            "Novo PIN configurado com sucesso!", "Sucesso", parent=self
        )
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
            self.tree_grade.insert(
                "", "end", iid=str(idx), values=(ini, fim, turmas, cats)
            )

    def _adicionar_regra_grade(self):
        """Adiciona um novo intervalo de horário ao dia e refeição selecionados."""
        ok, err_msg, nova_regra = setup_actions.validar_e_montar_regra_grade(
            self.entry_grade_inicio.get(),
            self.entry_grade_fim.get(),
            self.entry_grade_turmas.get(),
            self.entry_grade_cats.get(),
        )
        if not ok or not nova_regra:
            titulo = "Validação" if "obrigatórios" in err_msg else "Erro de Formatação"
            Messagebox.show_warning(err_msg, titulo, parent=self)
            return

        dia_chave, ref_chave = self._obter_chaves_dia_refeicao()
        setup_actions.adicionar_regra_grade(
            self._grade_atual, dia_chave, ref_chave, nova_regra
        )
        self._carregar_regras_grade()

    def _remover_regra_grade(self):
        """Remove o intervalo selecionado no Treeview."""
        selecionados = self.tree_grade.selection()
        if not selecionados:
            Messagebox.show_warning(
                "Selecione um intervalo para remover.", "Aviso", parent=self
            )
            return

        dia_chave, ref_chave = self._obter_chaves_dia_refeicao()
        if setup_actions.remover_regra_grade(
            self._grade_atual, dia_chave, ref_chave, int(selecionados[0])
        ):
            self._carregar_regras_grade()

    def _salvar_grade_horarios(self):
        """Persiste a grade semanal no arquivo JSON."""
        sucesso = grade_horarios_service.salvar_grade_horarios(self._grade_atual)
        if sucesso:
            Messagebox.show_info(
                "Grade horária semanal salva com sucesso!", "Grade Salva", parent=self
            )
        else:
            Messagebox.show_error(
                "Não foi possível salvar o arquivo grade_horarios.json.",
                "Erro ao Salvar",
                parent=self,
            )

    def _restaurar_grade_padrao(self):
        """Restaura a grade horária semanal para a matriz padrão."""
        import copy

        from ttkbootstrap.localization import MessageCatalog

        resp = Messagebox.yesno(
            "Deseja realmente restaurar a grade horária para a configuração padrão?",
            "Restaurar Padrão",
            parent=self,
        )
        if resp == MessageCatalog.translate("Yes"):
            self._grade_atual = copy.deepcopy(grade_horarios_service.GRADE_PADRAO)
            grade_horarios_service.salvar_grade_horarios(self._grade_atual)
            self._carregar_regras_grade()
            Messagebox.show_info(
                "Grade horária padrão restaurada!", "Restaurado", parent=self
            )

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
        except (OSError, RuntimeError, ValueError) as e:
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
            except (OSError, RuntimeError, ValueError) as e:
                Messagebox.show_error(
                    f"Falha ao salvar backup no destino:\n{e}", "Erro", parent=self
                )

    def _abrir_pasta_backups(self):
        DIRETORIO_BACKUPS.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(DIRETORIO_BACKUPS))
        except OSError as e:
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

    def _abrir_pasta(self, pasta: Path):
        pasta.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(pasta))
        except OSError as e:
            Messagebox.show_error(
                f"Não foi possível abrir a pasta:\n{e}", "Erro", parent=self
            )

    def _adicionar_lanche(self):
        item = self.var_novo_lanche.get().strip()
        if not item:
            return

        lanches = config_service.obter_lanches()
        if item in lanches:
            Messagebox.show_warning(
                "Este item já está cadastrado.", "Item Existente", parent=self
            )
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
            lanches.pop(idx)
            config_service.salvar_lanches(lanches)
            self._carregar_lanches()

    def _carregar_lanches(self):
        self.listbox_lanches.delete(0, END)
        lanches = config_service.obter_lanches()
        for item in lanches:
            self.listbox_lanches.insert(END, item)

    def _criar_atalhos_desktop(self):
        """Cria scripts de inicialização rápida na Área de Trabalho do Windows."""
        sucesso, msg = setup_actions.criar_atalhos_desktop()
        if sucesso:
            Messagebox.show_info(msg, "Atalhos Criados", parent=self)
        else:
            Messagebox.show_error(msg, "Erro", parent=self)

    def _redefinir_banco_dados(self):
        if config_service.tem_pin_configurado():
            if not solicitar_pin(
                parent=self,
                titulo="🔒 Confirmação com PIN",
                mensagem="Digite o PIN de segurança para zerar o banco de dados:",
            ):
                return

        confirma = Messagebox.show_question(
            "ATENÇÃO: Todos os dados serão limpos e o banco recriado.\nDeseja realmente continuar?",
            "Confirmação Extrema",
            parent=self,
        )
        if confirma == "Yes" or confirma is True:
            sucesso, msg = backup_service.redefinir_banco_dados(
                criar_backup_previo=True
            )
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
        cards = setup_actions.formatar_status_cards(status)

        self.card_db["label"].config(text=cards["db"][0])
        self.card_gcp["label"].config(text=cards["gcp"][0])
        self.lbl_cred_status.config(text=cards["cred"][0], bootstyle=cards["cred"][1])
        self.card_sheet["label"].config(text=cards["sheet"][0])
        self.var_planilha_input.set(cards["sheet"][1])
        self.card_pin["label"].config(text=cards["pin_card"][0])
        self.lbl_pin_status.config(
            text=cards["pin_lbl"][0], bootstyle=cards["pin_lbl"][1]
        )

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

    configurar_logging("setup")
    app = AppSetup()
    app.mainloop()


if __name__ == "__main__":
    main()
