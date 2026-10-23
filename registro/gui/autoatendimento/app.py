# ----------------------------------------------------------------------------
# Arquivo: registro/gui/autoatendimento/app.py (Aplicação Autônoma de Autoatendimento)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Módulo principal da interface autônoma de autoatendimento para totens.
Orquestra navegação entre telas, atalhos globais, menu de contexto do operador
e ciclo de vida da aplicação.
"""

import datetime as dt
import logging
import traceback
import tkinter as tk
from typing import Any, Dict, List, Optional, Tuple, Union

import ttkbootstrap as ttk
from ttkbootstrap.constants import NSEW
from ttkbootstrap.dialogs import Messagebox

from registro.gui.autoatendimento.consumos import AbaConsumos
from registro.gui.autoatendimento.dashboard import AbaDashboard
from registro.gui.autoatendimento.totem import FrameSelfService
from registro.gui.comum.dialogo_pin import solicitar_pin
from registro.gui.registrar.dialogo_filtro_turmas import DialogoFiltroTurmas
from registro.gui.registrar.dialogo_sessao import DialogoSessao
from registro.nucleo.config_service import obter_config_totem, tem_pin_configurado
from registro.nucleo.facade import FachadaRegistro

logger = logging.getLogger(__name__)

__all__ = [
    "AbaConsumos",
    "AbaDashboard",
    "AppSelfService",
    "FrameSelfService",
    "main",
]


class AppSelfService(ttk.Window):
    """
    Aplicação 100% autônoma de autoatendimento para totens ou terminais dedicados.
    Permite gerenciar sessões e filtros de turma on-the-fly via menu de contexto.
    """

    def __init__(self):
        super().__init__(themename="sandstone", title="🍽️ Totem de Autoatendimento")
        self.geometry("1280x800")
        self.minsize(960, 620)

        try:
            self.fachada_nucleo = FachadaRegistro()
        except Exception:
            Messagebox.show_error(
                "Erro Fatal", "Não foi possível iniciar o backend. Verifique o console."
            )
            traceback.print_exc()
            self.destroy()
            return

        self.id_sessao_ativa: Optional[int] = None
        self._fullscreen: bool = False
        self.selected_frame_name: str = ""
        self.frames: Dict[str, ttk.Frame] = {}

        # Identificação e Inicialização de Sessão
        self._detectar_e_carregar_sessao_inicial()

        self._criar_widgets()
        self._configurar_atalhos_teclado()
        self.totem_cfg = obter_config_totem()
        if self.totem_cfg.get("fullscreen", False):
            self.after(100, lambda: self._definir_fullscreen(True))

        # Se após a inicialização não houver sessão ativa, abre o diálogo de sessão
        if not self.id_sessao_ativa:
            self.after(300, self._abrir_dialogo_sessao)

    def get_fachada(self) -> FachadaRegistro:
        """Compatibilidade para componentes que requisitam a fachada."""
        return self.fachada_nucleo

    def mostrar_barra_progresso(self, iniciar: bool, texto: Optional[str] = None):
        """Suporte a diálogos que notificam progresso."""
        pass

    def _configurar_atalhos_teclado(self):
        """Configura atalhos de tela cheia, menu de contexto e captura inteligente de teclas."""
        self.bind("<F11>", lambda e: self._toggle_fullscreen())
        self.bind("<Escape>", lambda e: self._definir_fullscreen(False))
        self.bind("<F2>", lambda e: self.exibir_menu_contexto())
        self.bind("<Control-m>", lambda e: self.exibir_menu_contexto())
        self.bind_all("<Button-3>", self._ao_clique_botao_direito_global, add="+")

        # Redireciona teclas alfanuméricas para a entrada manual se o foco estiver perdido
        self.bind("<Key>", self._ao_pressionar_tecla_global, add="+")

    def _ao_clique_botao_direito_global(self, event):
        """Exibe o menu de contexto nativo ao clicar com o botão direito em qualquer área."""
        self.exibir_menu_contexto(event=event)

    def _ao_pressionar_tecla_global(self, event):
        """
        Redireciona digitações para o campo do scanner caso o usuário tenha clicado fora.
        Evita que scanners USB de código de barras ou RFID percam a leitura.
        """
        widget = event.widget
        if isinstance(widget, (ttk.Entry, tk.Entry, ttk.Combobox, tk.Text)):
            return

        # Teclas de controle (F1-F12, Escape, Alt, Tab, etc.) não são redirecionadas
        if event.keysym in (
            "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
            "Escape", "Alt_L", "Alt_R", "Control_L", "Control_R", "Shift_L", "Shift_R", "Tab"
        ):
            return

        if "selfservice" in self.frames and hasattr(self.frames["selfservice"], "_entrada_manual"):
            frame_ss = self.frames["selfservice"]
            if hasattr(frame_ss, "focar_entrada"):
                frame_ss.focar_entrada()
                if event.char and event.char.isprintable():
                    frame_ss._entrada_manual.insert(tk.END, event.char)

    def _toggle_fullscreen(self):
        """Alterna entre tela cheia e modo janela."""
        self._definir_fullscreen(not self._fullscreen)

    def _definir_fullscreen(self, ativo: bool):
        """Define o estado de tela cheia com proteção por PIN caso configurado."""
        if (
            not ativo
            and self._fullscreen
            and self.totem_cfg.get("require_pin_to_exit", True)
            and tem_pin_configurado()
        ):
            if not solicitar_pin(
                parent=self,
                titulo="🔒 Modo Janela",
                mensagem="Digite o PIN de operador para sair da tela cheia:",
            ):
                return

        self._fullscreen = ativo
        self.attributes("-fullscreen", self._fullscreen)

    def _detectar_e_carregar_sessao_inicial(self):
        """
        Detecta sessão ativa persistida ou seleciona automaticamente a sessão mais
        recente de hoje, garantindo inicialização autônoma sem cliques desnecessários.
        """
        try:
            # 1. Tenta carregar sessão salva em session.json
            self.fachada_nucleo.carregar_estado_sessao()
            if self.fachada_nucleo.id_sessao_ativa:
                self.id_sessao_ativa = self.fachada_nucleo.id_sessao_ativa
                logger.info("Sessão persistida carregada: ID %s", self.id_sessao_ativa)
                return

            # 2. Se não houver, busca se existe sessão criada para a data de hoje
            hoje_str = dt.date.today().strftime("%d/%m/%Y")
            sessoes = self.fachada_nucleo.listar_todas_sessoes()
            sessoes_hoje = [s for s in sessoes if s.get("data") == hoje_str]
            if sessoes_hoje:
                sessoes_hoje.sort(key=lambda s: s.get("hora", ""), reverse=True)
                sessao_recente = sessoes_hoje[0]
                self.fachada_nucleo.definir_sessao_ativa(sessao_recente["id"])
                self.fachada_nucleo.salvar_estado_sessao(sessao_recente["id"])
                self.id_sessao_ativa = sessao_recente["id"]
                logger.info(
                    "Sessão de hoje detectada automaticamente: ID %s", self.id_sessao_ativa
                )
        except Exception as e:
            logger.error("Erro na detecção inicial de sessão: %s", e)

    def exibir_menu_contexto(
        self,
        *args,
        widget: Optional[tk.Widget] = None,
        event: Optional[Any] = None,
        **kwargs,
    ):
        """Exibe o menu de contexto nativo com os controles do operador protegido por PIN."""
        if tem_pin_configurado():
            if not solicitar_pin(
                parent=self,
                titulo="🔒 Autenticação do Operador",
                mensagem="Digite o PIN de operador para acessar as opções do Totem:",
            ):
                return

        if args:
            if isinstance(args[0], tk.Event):
                event = args[0]
            elif isinstance(args[0], tk.Widget):
                widget = args[0]

        menu = tk.Menu(self, tearoff=False, font=("Segoe UI", 10))

        # Modos de Visualização
        menu.add_command(
            label="📷  Autoatendimento (Totem)",
            command=lambda: self.show_frame("selfservice"),
        )
        menu.add_command(
            label="📊  Dashboard da Sessão",
            command=lambda: self.show_frame("dashboard"),
        )
        menu.add_command(
            label="📋  Registros de Consumo",
            command=lambda: self.show_frame("consumos"),
        )
        menu.add_separator()

        # Ações de Sessão e Filtros
        menu.add_command(
            label="🔄  Gerenciar / Criar Sessão",
            command=self._abrir_dialogo_sessao,
        )
        menu.add_command(
            label="🎯  Filtros de Turmas e Exceções",
            command=self._abrir_dialogo_filtro_turmas,
        )
        menu.add_separator()

        # Sistema
        label_fs = (
            "🗗  Janela Normal" if self._fullscreen else "⛶  Tela Cheia (F11)"
        )
        menu.add_command(
            label=label_fs,
            command=self._toggle_fullscreen,
        )
        menu.add_command(
            label="❌  Sair do Totem",
            command=self._on_closing,
        )

        # Determina a posição de exibição do menu de contexto
        if event and hasattr(event, "x_root") and hasattr(event, "y_root"):
            x, y = event.x_root, event.y_root
        elif widget:
            try:
                widget.update_idletasks()
                if widget.winfo_rooty() > self.winfo_screenheight() // 2:
                    x = widget.winfo_rootx()
                    y = max(10, widget.winfo_rooty() - 250)
                else:
                    x = widget.winfo_rootx()
                    y = widget.winfo_rooty() + widget.winfo_height() + 2
            except Exception:
                x = widget.winfo_rootx()
                y = widget.winfo_rooty()
        else:
            x = self.winfo_rootx() + 30
            y = max(10, self.winfo_rooty() + self.winfo_height() - 260)

        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _criar_widgets(self):
        """Constrói a interface limpa sem barras laterais, com tela cheia para o totem e controles via menu de contexto."""
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.content_frame = ttk.Frame(self, padding=0)
        self.content_frame.grid(row=0, column=0, sticky=NSEW)
        self.content_frame.rowconfigure(0, weight=1)
        self.content_frame.columnconfigure(0, weight=1)

        # Criação das Abas
        self.frames["selfservice"] = FrameSelfService(
            self.content_frame,
            self.fachada_nucleo,
            self.notificar_sucesso_registro,
            abrir_controles_callback=self.exibir_menu_contexto,
        )
        self.frames["dashboard"] = AbaDashboard(
            self.content_frame,
            self.fachada_nucleo,
            self.id_sessao_ativa,
            voltar_callback=lambda: self.show_frame("selfservice"),
            abrir_controles_callback=self.exibir_menu_contexto,
            navegar_callback=self.show_frame,
        )
        self.frames["consumos"] = AbaConsumos(
            self.content_frame,
            self.fachada_nucleo,
            self.id_sessao_ativa,
            voltar_callback=lambda: self.show_frame("selfservice"),
            abrir_controles_callback=self.exibir_menu_contexto,
            navegar_callback=self.show_frame,
            notificar_mudanca_callback=self._ao_alterar_consumo,
        )

        self.show_frame("selfservice")

    def _ao_alterar_consumo(self):
        """Notificação de que registros foram adicionados, editados ou excluídos."""
        self._atualizar_barra_sessao()

    def show_frame(self, nome_pagina: str):
        """Alterna a página em exibição."""
        if self.selected_frame_name == nome_pagina:
            return

        if self.selected_frame_name and self.selected_frame_name in self.frames:
            self.frames[self.selected_frame_name].grid_remove()

        self.selected_frame_name = nome_pagina
        frame_ativo = self.frames[nome_pagina]
        frame_ativo.grid(row=0, column=0, sticky=NSEW)

        if nome_pagina == "selfservice" and hasattr(frame_ativo, "focar_entrada"):
            frame_ativo.focar_entrada()

    def _abrir_dialogo_sessao(self):
        """Abre o diálogo de gerenciamento completo de sessões (criar nova ou carregar existente)."""
        logger.info("Abrindo gerenciamento de sessão on-the-fly.")
        DialogoSessao(
            title="Gerenciar Sessão de Refeição",
            callback=self.tratar_resultado_dialogo_sessao,
            parente_app=self,
        )

    def tratar_resultado_dialogo_sessao(
        self, resultado: Union[Dict[str, Any], int, None]
    ) -> bool:
        """Trata a escolha de carregar ou criar sessão vinda do DialogoSessao."""
        if resultado is None:
            logger.info("Diálogo de sessão fechado sem alteração.")
            return True

        sucesso = False
        desc_acao = ""
        try:
            if isinstance(resultado, int):
                id_sessao = resultado
                desc_acao = f"carregar sessão ID: {id_sessao}"
                self.fachada_nucleo.definir_sessao_ativa(id_sessao)
                self.fachada_nucleo.salvar_estado_sessao(id_sessao)
                sucesso = True
            elif isinstance(resultado, dict):
                desc_acao = f"criar nova sessão: {resultado.get('refeicao')}"
                id_sessao = self.fachada_nucleo.iniciar_nova_sessao(resultado)
                if id_sessao is None:
                    Messagebox.show_warning(
                        "Sessão Vazia",
                        "Não foi possível iniciar a sessão sem reservas ativas.",
                        parent=self,
                    )
                    return False
                self.fachada_nucleo.salvar_estado_sessao(id_sessao)
                sucesso = True
        except Exception as e:
            logger.exception("Falha ao %s: %s", desc_acao, e)
            Messagebox.show_error(
                "Falha na Sessão",
                f"Não foi possível {desc_acao}.\nErro: {e}",
                parent=self,
            )
            return False

        if sucesso:
            self.id_sessao_ativa = self.fachada_nucleo.id_sessao_ativa
            logger.info("Sessão ativada com sucesso: ID %s", self.id_sessao_ativa)
            self._atualizar_apos_mudanca_sessao()
        return sucesso

    def _abrir_dialogo_filtro_turmas(self):
        """Abre o diálogo de filtros de turma on-the-fly."""
        if not self.fachada_nucleo or self.fachada_nucleo.id_sessao_ativa is None:
            Messagebox.show_warning(
                "Nenhuma Sessão Ativa",
                "É necessário iniciar ou selecionar uma sessão antes de ajustar os filtros.",
                parent=self,
            )
            return

        logger.info("Abrindo diálogo de filtros de turma.")
        DialogoFiltroTurmas(
            parent=self,
            fachada_nucleo=self.fachada_nucleo,
            callback_aplicar=self.ao_aplicar_filtro_turmas,
        )

    def ao_aplicar_filtro_turmas(self, identificadores: List[str]):
        """Aplica os novos filtros de turmas e exceções em tempo real."""
        logger.info("Aplicando filtros de turmas on-the-fly: %s", identificadores)
        try:
            grupos_normais = [
                ident for ident in identificadores if not ident.startswith("#")
            ]
            grupos_excecao = {
                ident.lstrip("#") for ident in identificadores if ident.startswith("#")
            }

            self.fachada_nucleo.atualizar_grupos_sessao_ativa(grupos_normais)
            self.fachada_nucleo.excecao_grupos = grupos_excecao

            self._atualizar_barra_sessao()
            if "dashboard" in self.frames:
                self.frames["dashboard"].atualizar_dados()

            Messagebox.show_info(
                "Filtros Atualizados",
                "Os filtros de turma e exceções foram aplicados com sucesso à sessão ativa.",
                parent=self,
            )
        except Exception as e:
            logger.exception("Erro ao aplicar filtros de turma: %s", e)
            Messagebox.show_error(
                "Erro ao Filtrar", f"Não foi possível aplicar filtros:\n{e}", parent=self
            )

    def _atualizar_apos_mudanca_sessao(self):
        """Propaga a nova sessão ativa para todos os frames e atualiza o cabeçalho."""
        self._atualizar_barra_sessao()

        if "selfservice" in self.frames:
            self.frames["selfservice"].recarregar_sessao()

        if "dashboard" in self.frames:
            self.frames["dashboard"].definir_sessao(self.id_sessao_ativa)

        if "consumos" in self.frames:
            self.frames["consumos"].definir_sessao(self.id_sessao_ativa)

    def _atualizar_barra_sessao(self):
        """Atualiza a exibição da sessão ativa em todos os componentes."""
        if "selfservice" in self.frames:
            self.frames["selfservice"].recarregar_sessao()
        if "dashboard" in self.frames:
            self.frames["dashboard"].atualizar_dados()
        if "consumos" in self.frames:
            self.frames["consumos"].carregar_consumos()

    def notificar_sucesso_registro(self, dados_estudante: Tuple[str, ...]):
        """Notificação de registro executado com sucesso."""
        if "consumos" in self.frames:
            self.frames["consumos"].adicionar_consumo(dados_estudante)
        if "dashboard" in self.frames:
            self.frames["dashboard"].atualizar_dados(ultimo_consumo=dados_estudante)

    def _on_closing(self):
        """Encerramento seguro de recursos com proteção por PIN."""
        if (
            self.totem_cfg.get("require_pin_to_exit", True)
            and tem_pin_configurado()
        ):
            if not solicitar_pin(
                parent=self,
                titulo="🔒 Sair do Totem",
                mensagem="Digite o PIN de operador para encerrar o Totem:",
            ):
                return

        logger.info("Encerrando aplicação de autoatendimento...")
        if "selfservice" in self.frames:
            self.frames["selfservice"].stop()
        try:
            self.fachada_nucleo.fechar_conexao()
        except Exception as e:
            logger.warning("Erro ao fechar conexão com DB: %s", e)
        self.destroy()


def main():
    """Ponto de entrada para a aplicação autônoma de autoatendimento."""
    log_format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_format)
    logging.getLogger().setLevel(logging.INFO)

    try:
        app = AppSelfService()
        app.mainloop()
    except Exception:
        logger.critical("Erro fatal ao iniciar a aplicação de autoatendimento.")
        logger.critical(traceback.format_exc())
        Messagebox.show_error(
            "Erro Crítico",
            "A aplicação encontrou um erro irrecuperável e será fechada. "
            "Verifique os logs para mais detalhes.",
        )


if __name__ == "__main__":
    main()
