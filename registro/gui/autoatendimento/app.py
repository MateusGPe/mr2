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
import threading
import time
import traceback
import tkinter as tk
from threading import Thread
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import ttkbootstrap as ttk
from ttkbootstrap.constants import LEFT, NSEW, X
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
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

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

        # Sincronização automática em segundo plano na inicialização (resiliente/offline)
        self.after(500, lambda: self._sincronizar_dados_mestre(automatico=True))

    def get_fachada(self) -> FachadaRegistro:
        """Compatibilidade para componentes que requisitam a fachada."""
        return self.fachada_nucleo

    def mostrar_barra_progresso(self, iniciar: bool, texto: Optional[str] = None):
        """Exibe ou oculta barra de progresso discreta no rodapé."""
        if not hasattr(self, "_frame_progresso") or not hasattr(self, "_barra_progresso"):
            return

        def _atualizar():
            if iniciar:
                if texto and hasattr(self, "_label_progresso"):
                    self._label_progresso.config(text=f"🔄 {texto}")
                self._frame_progresso.grid(row=1, column=0, sticky="ew")
                self._barra_progresso.start(10)
            else:
                self._barra_progresso.stop()
                self._frame_progresso.grid_remove()

        if threading.current_thread() is threading.main_thread():
            _atualizar()
        else:
            self.after(0, _atualizar)

    def _logar_sincronizacao(
        self,
        direction: str,
        status: str,
        message: Optional[str] = None,
        records_affected: Optional[int] = None,
    ):
        """Registra um evento de sincronização no banco de dados através da fachada."""
        logger.info(
            "Logando sincronização: direction=%s, status=%s, records=%s",
            direction,
            status,
            records_affected,
        )
        if self.fachada_nucleo:
            try:
                self.fachada_nucleo.registrar_log_sincronizacao(
                    direction=direction,
                    status=status,
                    message=message,
                    records_affected=records_affected,
                )
            except Exception as e:
                logger.warning("Erro ao gravar log de sincronização no BD: %s", e)

    def _sincronizar_dados_mestre(self, automatico: bool = False):
        """Inicia a sincronização dos dados mestre (cadastros e reservas)."""
        if not automatico:
            if not Messagebox.yesno(
                "Deseja sincronizar os dados mestre do Google Sheets?\nIsso pode levar alguns segundos.",
                "Confirmar Sincronização",
                parent=self,
            ):
                return
            logger.info("Iniciando sincronização manual de cadastros.")
        else:
            logger.info("Iniciando sincronização automática de cadastros ao entrar.")

        self.mostrar_barra_progresso(True, "Sincronizando cadastros...")
        self._iniciar_thread_sinc(
            self.fachada_nucleo.sincronizar_do_google_sheets,
            "Sincronização de Cadastros",
            automatico=automatico,
        )

    def sincronizar_sessao_com_planilha(self, automatico: bool = False):
        """Inicia a sincronização dos dados de todas as sessões para a planilha."""
        if not automatico:
            if not Messagebox.yesno(
                "Deseja enviar os registros de consumo para a planilha?\nIsso pode levar alguns segundos.",
                "Confirmar Sincronização",
                parent=self,
            ):
                return
            logger.info("Iniciando sincronização manual de consumos para planilha.")
        else:
            logger.info("Iniciando sincronização automática de consumos para planilha.")

        self.mostrar_barra_progresso(
            True, "Sincronizando servidos para planilha..."
        )
        self._iniciar_thread_sinc(
            self.fachada_nucleo.sincronizar_todas_sessoes_para_google_sheets,
            "Sincronização de Servidos",
            automatico=automatico,
        )

    def _iniciar_thread_sinc(
        self,
        funcao_sinc: Callable,
        nome_tarefa: str,
        automatico: bool = False,
    ):
        """Inicia uma função de sincronização em uma thread separada para não bloquear a UI."""
        thread = Thread(
            target=self._acao_sinc_wrapper, args=(funcao_sinc,), daemon=True
        )
        thread.start()
        self._monitorar_thread_sinc(thread, nome_tarefa, automatico)

    def _executar_sinc_bloqueante(
        self,
        funcao_sinc: Callable,
        nome_tarefa: str,
        timeout: float = 8.0,
    ):
        """Executa sincronização no encerramento, bombeando eventos da UI e com timeout."""
        logger.info("Executando sincronização de fechamento: %s", nome_tarefa)
        self.mostrar_barra_progresso(True, f"Enviando dados: {nome_tarefa}...")
        thread = Thread(
            target=self._acao_sinc_wrapper, args=(funcao_sinc,), daemon=False
        )
        thread.start()

        inicio = time.time()
        while thread.is_alive():
            try:
                self.update()
            except Exception:
                pass
            thread.join(0.1)
            if time.time() - inicio > timeout:
                logger.warning(
                    "Tempo limite atingido para %s no fechamento (%.1fs). Continuando encerramento.",
                    nome_tarefa,
                    timeout,
                )
                break

        self._monitorar_thread_sinc(thread, nome_tarefa, automatico=True)

    def _acao_sinc_wrapper(self, funcao_sinc: Callable):
        """Wrapper que executa a função de sincronização e captura exceções na thread."""
        thread = threading.current_thread()
        setattr(thread, "error", None)
        setattr(thread, "success", False)
        setattr(thread, "records_affected", 0)

        try:
            records_affected = funcao_sinc()
            setattr(thread, "success", True)
            setattr(thread, "records_affected", records_affected or 0)
        except Exception as e:  # pylint: disable=broad-exception-caught
            setattr(thread, "error", e)

    def _monitorar_thread_sinc(
        self, thread: Thread, nome_tarefa: str, automatico: bool = False
    ):
        """Verifica o status da thread de sincronização e exibe o resultado ao final."""
        if thread.is_alive():
            self.after(
                150,
                lambda: self._monitorar_thread_sinc(
                    thread, nome_tarefa, automatico
                ),
            )
            return

        self.mostrar_barra_progresso(False)
        erro = getattr(thread, "error", None)
        sucesso = getattr(thread, "success", False)
        records_affected = getattr(thread, "records_affected", 0)

        direction = "download" if "Cadastros" in nome_tarefa else "upload"

        if erro:
            logger.error("%s falhou: %s", nome_tarefa, erro)
            self._logar_sincronizacao(
                direction=direction,
                status="failure",
                message=str(erro),
                records_affected=0,
            )
            if not automatico:
                Messagebox.show_error(
                    f"{nome_tarefa} falhou:\n{erro}",
                    "Erro na Sincronização",
                    parent=self,
                )
        elif sucesso:
            logger.info(
                "%s concluída com sucesso. Registros afetados: %s",
                nome_tarefa,
                records_affected,
            )
            self._logar_sincronizacao(
                direction=direction,
                status="success",
                message=f"{nome_tarefa} concluída com sucesso.",
                records_affected=records_affected,
            )
            if not automatico:
                Messagebox.show_info(
                    f"{nome_tarefa} concluída com sucesso.",
                    "Sincronização Concluída",
                    parent=self,
                )
            self._atualizar_barra_sessao()
        else:
            logger.warning(
                "%s finalizada com estado indeterminado.", nome_tarefa
            )
            self._logar_sincronizacao(
                direction=direction,
                status="unknown",
                message=f"{nome_tarefa} finalizada com estado indeterminado.",
                records_affected=0,
            )
            if not automatico:
                Messagebox.show_warning(
                    f"{nome_tarefa} finalizada sem confirmação explícita de sucesso ou erro.",
                    "Sincronização Indeterminada",
                    parent=self,
                )

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
        # Se a página atual não for selfservice, não redireciona
        if getattr(self, "selected_frame_name", "") != "selfservice":
            return

        # Se houver diálogo Toplevel aberto e visível, não interfere nas digitações do usuário
        try:
            for w in self.winfo_children():
                if isinstance(w, tk.Toplevel) and w.winfo_exists() and w.winfo_viewable():
                    return
        except Exception:
            pass

        widget = getattr(event, "widget", None)
        try:
            if widget and widget.winfo_toplevel() != self:
                return
        except Exception:
            pass

        if isinstance(
            widget,
            (
                ttk.Entry,
                tk.Entry,
                ttk.Combobox,
                tk.Text,
                ttk.Checkbutton,
                tk.Checkbutton,
                ttk.Radiobutton,
                tk.Radiobutton,
                ttk.Treeview,
                tk.Listbox,
            ),
        ):
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

        # Sincronização com Google Sheets
        menu.add_command(
            label="📥  Sincronizar Cadastros (Download)",
            command=lambda: self._sincronizar_dados_mestre(automatico=False),
        )
        menu.add_command(
            label="📤  Enviar Registros para Planilha (Upload)",
            command=lambda: self.sincronizar_sessao_com_planilha(automatico=False),
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
        self.rowconfigure(1, weight=0)
        self.columnconfigure(0, weight=1)

        self.content_frame = ttk.Frame(self, padding=0)
        self.content_frame.grid(row=0, column=0, sticky=NSEW)
        self.content_frame.rowconfigure(0, weight=1)
        self.content_frame.columnconfigure(0, weight=1)

        # Barra inferior discreta para feedback de sincronização / operações em segundo plano
        self._frame_progresso = ttk.Frame(self, padding=(12, 4), bootstyle="secondary")
        self._label_progresso = ttk.Label(
            self._frame_progresso,
            text="",
            font=("Segoe UI", 9, "bold"),
            bootstyle="secondary",
        )
        self._label_progresso.pack(side=LEFT, padx=(0, 10))
        self._barra_progresso = ttk.Progressbar(
            self._frame_progresso,
            mode="indeterminate",
            bootstyle="info-striped",
            length=180,
        )
        self._barra_progresso.pack(side=LEFT, fill=X, expand=True)

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
            if getattr(self, "selected_frame_name", "") == "selfservice" and "selfservice" in self.frames:
                self.after(100, self.frames["selfservice"].focar_entrada)
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
        """Encerramento seguro de recursos com proteção por PIN e sincronização final."""
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

        if self.fachada_nucleo:
            try:
                # Sincroniza servidos de todas as sessões para a planilha antes de fechar
                self._executar_sinc_bloqueante(
                    self.fachada_nucleo.sincronizar_todas_sessoes_para_google_sheets,
                    "Sincronização de Servidos",
                    timeout=8.0,
                )
            except Exception as e:
                logger.warning("Falha ao sincronizar antes de fechar: %s", e)

            if self.id_sessao_ativa:
                try:
                    self.fachada_nucleo.salvar_estado_sessao(self.id_sessao_ativa)
                except Exception as e:
                    logger.warning("Erro ao salvar estado da sessão: %s", e)

            try:
                self.fachada_nucleo.fechar_conexao()
            except Exception as e:
                logger.warning("Erro ao fechar conexão com DB: %s", e)

        try:
            self.destroy()
        except tk.TclError:
            pass
        logger.info("Aplicação de autoatendimento finalizada.")


def main():
    """Ponto de entrada para a aplicação autônoma de autoatendimento."""
    from registro.nucleo.logging_config import configurar_logging

    configurar_logging("autoatendimento")

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
