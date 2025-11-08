# ----------------------------------------------------------------------------
# File: registro/view/registration_app.py (Aplicação Principal da UI)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>
"""
Fornece a classe principal da aplicação (`RegistrationApp`) para o sistema de
registro de refeições. Orquestra os painéis de UI, gerencia a sessão e
lida com ações globais como sincronização, exportação e troca de sessão.
"""
import json
import logging
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from threading import Thread
from tkinter import CENTER, TclError, messagebox
from typing import Any, List, Optional, Tuple, Union, Dict

import ttkbootstrap as ttk
from ttkbootstrap.constants import HORIZONTAL, LEFT, LIGHT, RIGHT, VERTICAL, X

from registro.view.constants import SESSION_PATH, UI_TEXTS, NewSessionData
from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.exceptions import ErroSessaoNaoAtiva, ErroEstudanteJaConsumiu
from registro.view.utils import capitalize

from registro.view.action_search_panel import ActionSearchPanel
from registro.view.class_filter_dialog import ClassFilterDialog
from registro.view.session_dialog import SessionDialog
from registro.view.status_registered_panel import StatusRegisteredPanel

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# Classe Principal da Aplicação (GUI)
# ----------------------------------------------------------------------------


class RegistrationApp(tk.Tk):
    """Janela principal da aplicação de registro de refeições."""

    def __init__(
        self, title: str = UI_TEXTS.get("app_title", "RU IFSP - Registro de Refeições")
    ):
        """
        Inicializa a janela principal, a Fachada e constrói a UI.
        """
        super().__init__()
        self.title(title)
        self.protocol("WM_DELETE_WINDOW", self.on_close_app)
        self.minsize(1152, 648)

        self._fachada: Optional[FachadaRegistro] = None
        try:
            self._fachada = FachadaRegistro()
        except Exception as e:
            self._handle_initialization_error("Fachada do Núcleo", e)
            return

        # --- Inicialização dos Atributos da UI ---
        self._top_bar: Optional[ttk.Frame] = None
        self._main_paned_window: Optional[ttk.PanedWindow] = None
        self._status_bar: Optional[ttk.Frame] = None
        self._action_panel: Optional[ActionSearchPanel] = None
        self._status_panel: Optional[StatusRegisteredPanel] = None
        self._session_info_label: Optional[ttk.Label] = None
        self._status_bar_label: Optional[ttk.Label] = None
        self._progress_bar: Optional[ttk.Progressbar] = None
        self.style: Optional[ttk.Style] = None
        self.colors: Optional[Any] = None

        # --- Construção da UI ---
        try:
            self._configure_style()
            self._configure_grid_layout()
            self._create_top_bar()
            self._create_main_panels(self._fachada)
            self._create_status_bar()
        except Exception as e:
            self._handle_initialization_error(
                UI_TEXTS.get("ui_construction", "Construção da UI"), e
            )
            return

        self._load_initial_session()

    def get_fachada(self) -> FachadaRegistro:
        """Retorna a instância da Fachada, levantando erro se não inicializada."""
        if self._fachada is None:
            logger.critical("Tentativa de acessar Fachada não inicializada.")
            raise RuntimeError("FachadaRegistro não foi inicializada corretamente.")
        return self._fachada

    def _handle_initialization_error(self, component: str, error: Exception):
        """Exibe erro crítico e tenta fechar a aplicação de forma limpa."""
        logger.critical(
            "Erro Crítico de Inicialização - Componente: %s | Erro: %s",
            component,
            error,
            exc_info=True,
        )
        try:
            temp_root = None
            if not hasattr(tk, "_default_root") or not tk._default_root:  # type: ignore
                temp_root = tk.Tk()
                temp_root.withdraw()

            messagebox.showerror(
                UI_TEXTS.get(
                    "initialization_error_title", "Erro Fatal na Inicialização"
                ),
                UI_TEXTS.get(
                    "initialization_error_message",
                    "Falha crítica ao inicializar o componente: {component}\n\n"
                    "Erro: {error}\n\nA aplicação será encerrada.",
                ).format(component=component, error=error),
                parent=(self if self.winfo_exists() else None),
            )
            if temp_root:
                temp_root.destroy()
        except Exception as mb_error:
            print(
                f"ERRO CRÍTICO DE INICIALIZAÇÃO ({component}): {error}", file=sys.stderr
            )
            print(f"(Erro ao exibir messagebox: {mb_error})", file=sys.stderr)

        if self.winfo_exists():
            try:
                self.destroy()
            except tk.TclError:
                pass
        sys.exit(1)

    def _configure_style(self):
        """Configura o tema ttkbootstrap e estilos customizados para widgets."""
        try:
            self.style = ttk.Style(theme="minty")
            default_font = ("Segoe UI", 12)
            heading_font = (default_font[0], 10, "bold")
            label_font = (default_font[0], 11, "bold")
            small_font = (default_font[0], 9)
            self.style.configure(
                "Custom.Treeview", font=(default_font[0], 9), rowheight=30
            )
            self.style.configure(
                "Custom.Treeview.Heading",
                font=heading_font,
                background=self.style.colors.light,
                foreground=self.style.colors.get_foreground("light"),
            )
            self.style.configure("TLabelframe.Label", font=label_font)
            self.style.configure("Status.TLabel", font=small_font)
            self.style.configure("Feedback.TLabel", font=small_font)
            self.style.configure("Preview.TLabel", font=small_font, justify=LEFT)
            self.style.configure("Count.TLabel", font=heading_font, anchor=CENTER)
            self.colors = self.style.colors
        except (TclError, AttributeError) as e:
            logger.warning("Erro ao configurar estilo ttkbootstrap: %s.", e)
            self.style = ttk.Style()
            self.colors = getattr(self.style, "colors", {})

    def _configure_grid_layout(self):
        """Configura o grid da janela principal (Tk)."""
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

    def _create_top_bar(self):
        """Cria a barra superior com informações da sessão e botões globais."""
        self._top_bar = ttk.Frame(self, padding=(10, 5), bootstyle=LIGHT)  # type: ignore
        self._top_bar.grid(row=0, column=0, sticky="ew")

        self._session_info_label = ttk.Label(
            self._top_bar,
            text=UI_TEXTS.get("loading_session", "Carregando Sessão..."),
            font="-size 14 -weight bold",
            bootstyle="inverse-light",  # type: ignore
        )
        self._session_info_label.pack(side=LEFT, padx=(0, 20), anchor="w")

        buttons_frame = ttk.Frame(self._top_bar, bootstyle=LIGHT)  # type: ignore
        buttons_frame.pack(side=RIGHT, anchor="e")

        ttk.Button(
            buttons_frame,
            text=UI_TEXTS.get("export_end_button", "💾 Exportar & Encerrar"),
            command=self.export_and_end_session,
            bootstyle="light",  # type: ignore
        ).pack(side=RIGHT, padx=(10, 0))

        ttk.Button(
            buttons_frame,
            text=UI_TEXTS.get("sync_served_button", "📤 Sync Servidos"),
            command=self.sync_session_with_spreadsheet,
            bootstyle="light",  # type: ignore
        ).pack(side=RIGHT, padx=3)

        ttk.Button(
            buttons_frame,
            text=UI_TEXTS.get("sync_master_button", "🔄 Sync Cadastros"),
            command=self._sync_master_data,
            bootstyle="light",  # type: ignore
        ).pack(side=RIGHT, padx=3)

        ttk.Separator(buttons_frame, orient=VERTICAL).pack(
            side=RIGHT, padx=8, fill="y", pady=3
        )

        ttk.Button(
            buttons_frame,
            text=UI_TEXTS.get("filter_classes_button", "📊 Filtrar Turmas"),
            command=self._open_class_filter_dialog,
            bootstyle="light",  # type: ignore
        ).pack(side=RIGHT, padx=3)

        ttk.Button(
            buttons_frame,
            text=UI_TEXTS.get("change_session_button", "⚙️ Alterar Sessão"),
            command=self._open_session_dialog,
            bootstyle="light",  # type: ignore
        ).pack(side=RIGHT, padx=3)

    def _create_main_panels(self, fachada: FachadaRegistro):
        """Cria o PanedWindow e instancia os painéis."""
        self._main_paned_window = ttk.PanedWindow(self, orient=HORIZONTAL, bootstyle="light")  # type: ignore
        self._main_paned_window.grid(
            row=1, column=0, sticky="nsew", padx=10, pady=(5, 0)
        )

        self._action_panel = ActionSearchPanel(self._main_paned_window, self, fachada)
        self._main_paned_window.add(self._action_panel, weight=1)

        self._status_panel = StatusRegisteredPanel(
            self._main_paned_window, self, fachada
        )
        self._main_paned_window.add(self._status_panel, weight=2)

    def _create_status_bar(self):
        """Cria a barra de status inferior."""
        self._status_bar = ttk.Frame(
            self, padding=(5, 3), bootstyle=LIGHT, name="statusBarFrame"  # type: ignore
        )
        self._status_bar.grid(row=2, column=0, sticky="ew")

        self._status_bar_label = ttk.Label(
            self._status_bar,
            text=UI_TEXTS.get("status_ready", "Pronto."),
            bootstyle="inverse-light",  # type: ignore
            font=("-size 10"),
        )
        self._status_bar_label.pack(side=LEFT, padx=5, anchor="w")

        self._progress_bar = ttk.Progressbar(
            self._status_bar, mode="indeterminate", bootstyle="striped-info", length=200  # type: ignore
        )

    def _load_session_state_file(self) -> Optional[Dict[str, Any]]:
        """Carrega o estado da sessão de um arquivo JSON, se existir."""
        if not SESSION_PATH.exists():
            logger.info("Arquivo de estado da sessão não encontrado: %s", SESSION_PATH)
            return None

        try:
            with open(SESSION_PATH, "r", encoding="utf-8") as f:
                session_data = json.load(f)
            logger.info("Estado da sessão carregado do arquivo: %s", SESSION_PATH)

            assert self._fachada is not None
            self._fachada.definir_sessao_ativa(session_data.get("id_sessao"))

            return session_data
        except Exception as e:
            logger.error(
                "Erro ao carregar estado da sessão do arquivo %s: %s",
                SESSION_PATH,
                e,
            )
            return None

    def _load_initial_session(self):
        """Tenta carregar a última sessão ativa ou abre o diálogo de sessão."""
        logger.info("Tentando carregar estado inicial da sessão...")
        session_info = self._load_session_state_file()
        if session_info:
            self._setup_ui_for_loaded_session()
        else:
            self.after(100, self._open_session_dialog)

    def handle_session_dialog_result(self, result: Union[Dict, int, None]) -> bool:
        """Callback chamado pelo SessionDialog."""
        if result is None:
            logger.info("Diálogo de sessão cancelado.")
            if not self._fachada or self._fachada.id_sessao_ativa is None:
                logger.warning("Diálogo cancelado sem sessão ativa.")
            return True

        success = False
        action_desc = ""
        if not self._fachada:
            messagebox.showerror("Erro Interno", "Fachada não encontrada.", parent=self)
            return False

        try:
            if isinstance(result, int):
                session_id = result
                action_desc = f"carregar sessão ID: {session_id}"
                self._fachada.definir_sessao_ativa(session_id)
                success = True

            elif isinstance(result, dict):
                new_session_data = result
                action_desc = f"criar nova sessão: {new_session_data.get('refeicao')}"
                id_sessao = self._fachada.iniciar_nova_sessao(new_session_data)  # type: ignore
                logger.info("Nova sessão criada com ID: %s", id_sessao)

                if id_sessao:
                    if SESSION_PATH.exists():
                        SESSION_PATH.unlink()
                    SESSION_PATH.write_text(
                        f'{{"id_sessao": {id_sessao}}}', encoding="utf-8"
                    )
                    success = True
        except Exception as e:
            logger.exception("Falha ao %s: %s", action_desc, e)
            messagebox.showerror(
                "Operação Falhou",
                f"Não foi possível {action_desc}.\nErro: {e}",
                parent=self,
            )
            return False

        if success:
            logger.info("Sucesso ao %s.", action_desc)
            self._setup_ui_for_loaded_session()
            return True
        else:
            return False

    def _setup_ui_for_loaded_session(self):
        """Configura a UI para a sessão ativa."""
        logger.debug("Configurando UI para sessão ativa...")
        if not self._fachada:
            return

        try:
            session_details = self._fachada.obter_detalhes_sessao_ativa()
        except ErroSessaoNaoAtiva:
            logger.error("Não é possível configurar UI: Nenhuma sessão ativa.")
            self.title(UI_TEXTS.get("app_title_no_session", "Registro [Sem Sessão]"))
            if self._session_info_label:
                self._session_info_label.config(
                    text="Erro: Nenhuma Sessão Ativa",
                    bootstyle="inverse-danger",  # type: ignore
                )
            if self._action_panel:
                self._action_panel.disable_controls()
            if self._status_panel:
                self._status_panel.clear_table()
            return

        if not all(
            [
                session_details,
                self._session_info_label,
                self._action_panel,
                self._status_panel,
            ]
        ):
            logger.error("Componentes da UI ou detalhes da sessão ausentes.")
            return

        try:
            meal_display = capitalize(session_details.get("refeicao", "?"))
            time_display = session_details.get("hora", "??")
            date_raw = session_details.get("data", "")
            display_date = (
                # datetime.strptime(date_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
                # if date_raw
                # else ""
                date_raw
            )
            session_id = session_details.get("id")

            title = UI_TEXTS.get(
                "app_title_active_session", "Registro: {meal} - {date} {time} [ID:{id}]"
            ).format(
                meal=meal_display, date=display_date, time=time_display, id=session_id
            )
            self.title(title)
            self._session_info_label.config(text=title, bootstyle="inverse-light")  # type: ignore

        except Exception as e:
            logger.exception("Erro ao formatar detalhes da sessão para UI: %s", e)
            self.title("RU Registro [Erro na Sessão]")
            if self._session_info_label:
                self._session_info_label.config(
                    text="Erro ao carregar detalhes",
                    bootstyle="inverse-danger",  # type: ignore
                )
            return

        logger.debug("Habilitando painéis e carregando dados...")
        if self._action_panel:
            self._action_panel.enable_controls()
        if self._status_panel:
            self._status_panel.load_registered_students()
        if self._action_panel:
            self._action_panel.refresh_results()

        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            if self._action_panel:
                self._action_panel.focus_entry()
        except tk.TclError as e:
            logger.warning("Erro Tcl ao focar/levantar janela: %s", e)

        logger.info("UI configurada para sessão ID: %s", session_details.get("id"))

    def _refresh_ui_after_data_change(self):
        """Atualiza os componentes da UI que dependem dos dados da sessão."""
        logger.info("Atualizando UI após mudança nos dados da sessão...")
        if not self._fachada or self._fachada.id_sessao_ativa is None:
            logger.warning("Nenhuma sessão ativa para atualizar a UI.")
            return

        if self._status_panel:
            self._status_panel.update_counters()
        if self._action_panel:
            self._action_panel.refresh_results()
        logger.debug("Refresh da UI concluído.")

    def notify_registration_success(self, student_data: Tuple):
        """Chamado pelo ActionSearchPanel após um registro bem-sucedido."""
        logger.debug("Notificação de registro recebida para: %s", student_data[0])
        if self._status_panel:
            self._status_panel.load_registered_students()

    def handle_consumption_deletion(self, data_for_logic: Tuple, _iid_to_delete: str):
        """Processa a exclusão de um registro."""
        pront = data_for_logic[0] if data_for_logic else None
        nome = data_for_logic[1] if len(data_for_logic) > 1 else "N/A"

        logger.info("Solicitação para desfazer consumo: %s (%s)", pront or "?", nome)

        if pront and self._fachada:
            self._fachada.desfazer_consumo_por_prontuario(pront)
            self._status_panel.load_registered_students()
            self._refresh_ui_after_data_change()

    def _open_session_dialog(self: "RegistrationApp"):
        """Abre o diálogo para selecionar/criar uma sessão."""
        logger.info("Abrindo diálogo de sessão.")
        SessionDialog(
            title=UI_TEXTS.get("session_dialog_title", "Selecionar ou Criar Sessão"),
            callback=self.handle_session_dialog_result,  # type: ignore
            parent_app=self,
        )

    def _open_class_filter_dialog(self):
        """Abre o diálogo para filtrar turmas visíveis."""
        if not self._fachada or self._fachada.id_sessao_ativa is None:
            messagebox.showwarning(
                "Nenhuma Sessão Ativa", "É necessário iniciar uma sessão.", parent=self
            )
            return
        logger.info("Abrindo diálogo de filtro de turmas.")
        ClassFilterDialog(
            parent=self,
            fachada_nucleo=self._fachada,
            apply_callback=self.on_class_filter_apply,
        )  # type: ignore

    def on_class_filter_apply(self, selected_identifiers: List[str]):
        """Callback chamado pelo ClassFilterDialog."""
        logger.info("Aplicando filtros de turma: %s", selected_identifiers)
        if not self._fachada:
            return

        try:
            selected_groups = [
                ident for ident in selected_identifiers if not ident.startswith("#")
            ]
            excluded_groups = [
                ident[1:] for ident in selected_identifiers if ident.startswith("#")
            ]
            self._fachada.atualizar_grupos_sessao(selected_groups, excluded_groups)

            logger.info("Filtros de turma aplicados com sucesso no backend.")
            self._refresh_ui_after_data_change()
        except Exception as e:
            logger.exception("Falha ao aplicar filtros de turma via fachada: %s", e)
            messagebox.showerror(
                "Erro ao Filtrar",
                f"Não foi possível aplicar os filtros.\nErro: {e}",
                parent=self,
            )

    def show_progress_bar(self, start: bool, text: Optional[str] = None):
        """Mostra ou esconde a barra de progresso."""
        if not self._progress_bar or not self._status_bar_label:
            return
        try:
            if start:
                progress_text = text or UI_TEXTS.get(
                    "status_processing", "Processando..."
                )
                self._status_bar_label.config(text=progress_text)
                if not self._progress_bar.winfo_ismapped():
                    self._progress_bar.pack(
                        side=RIGHT, padx=5, pady=0, fill=X, expand=False
                    )
                self._progress_bar.start(10)
            else:
                if self._progress_bar.winfo_ismapped():
                    self._progress_bar.stop()
                    self._progress_bar.pack_forget()
                self._status_bar_label.config(
                    text=UI_TEXTS.get("status_ready", "Pronto.")
                )
        except tk.TclError as e:
            logger.error("Erro Tcl ao manipular barra de progresso: %s", e)

    def _sync_master_data(self):
        """Inicia a sincronização dos dados mestre."""
        if not self._fachada:
            return
        if not messagebox.askyesno(
            "Confirmar Sincronização",
            "Deseja sincronizar os dados mestre?",
            parent=self,
        ):
            return
        self.show_progress_bar(True, "Sincronizando cadastros...")
        self._start_sync_thread(
            self._fachada.sincronizar_do_google_sheets, "Sincronização de Cadastros"
        )

    def sync_session_with_spreadsheet(self):
        """Inicia a sincronização dos registros servidos."""
        if not self._fachada or self._fachada.id_sessao_ativa is None:
            messagebox.showwarning(
                "Nenhuma Sessão Ativa",
                "É necessário ter uma sessão ativa para sincronizar.",
                parent=self,
            )
            return
        self.show_progress_bar(True, "Sincronizando servidos para planilha...")
        self._start_sync_thread(
            self._fachada.sincronizar_para_google_sheets, "Sincronização de Servidos"
        )

    def _start_sync_thread(self, sync_function: callable, task_name: str):
        """Cria e monitora uma thread para uma função de sincronização da fachada."""

        def sync_action():
            thread.error = None
            thread.success = False
            try:
                sync_function()
                thread.success = True
            except Exception as e:
                thread.error = e

        thread = Thread(target=sync_action, daemon=True)
        thread.error = None  # type: ignore
        thread.success = False  # type: ignore
        thread.start()
        self._monitor_sync_thread(thread, task_name)

    def _monitor_sync_thread(self, thread: Thread, task_name: str):
        """Verifica periodicamente se uma thread terminou e atualiza a UI."""
        if thread.is_alive():
            self.after(150, lambda: self._monitor_sync_thread(thread, task_name))
            return

        self.show_progress_bar(False)
        error = getattr(thread, "error", None)
        success = getattr(thread, "success", False)

        if error:
            logger.error("%s falhou: %s", task_name, error)
            messagebox.showerror(
                "Erro na Sincronização", f"{task_name} falhou:\n{error}", parent=self
            )
        elif success:
            logger.info("%s concluída com sucesso.", task_name)
            messagebox.showinfo(
                "Sincronização Concluída",
                f"{task_name} concluída com sucesso.",
                parent=self,
            )
            self._refresh_ui_after_data_change()
        else:
            logger.warning("%s finalizada com estado indeterminado.", task_name)
            messagebox.showwarning(
                "Status Desconhecido",
                f"{task_name} finalizada, mas o status é incerto.",
                parent=self,
            )

    def export_session_to_excel(self) -> bool:
        """Exporta os dados da sessão atual para um arquivo Excel."""
        if not self._fachada:
            return False
        try:
            file_path = self._fachada.exportar_sessao_para_xlsx()
            logger.info("Dados da sessão exportados para: %s", file_path)
            messagebox.showinfo(
                "Exportação Concluída",
                f"Dados exportados com sucesso para:\n{file_path}",
                parent=self,
            )
            return True
        except ErroSessaoNaoAtiva:
            messagebox.showwarning(
                "Nenhuma Sessão Ativa",
                "Não há sessão ativa para exportar.",
                parent=self,
            )
        except ValueError as ve:  # Ex: Ninguém consumiu
            messagebox.showwarning("Nada para Exportar", str(ve), parent=self)
        except Exception as e:
            logger.exception("Erro inesperado durante a exportação para Excel.")
            messagebox.showerror(
                "Erro na Exportação", f"Ocorreu um erro ao exportar:\n{e}", parent=self
            )
        return False

    def export_and_end_session(self):
        """Exporta dados, limpa o estado da sessão e fecha a aplicação."""
        if not self._fachada or self._fachada.id_sessao_ativa is None:
            messagebox.showwarning(
                "Nenhuma Sessão Ativa",
                "Não há sessão ativa para encerrar.",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "Confirmar Encerramento",
            "Deseja exportar os dados e encerrar esta sessão?",
            icon="warning",
            parent=self,
        ):
            return

        export_successful = self.export_session_to_excel()
        if not export_successful:
            if not messagebox.askyesno(
                "Falha na Exportação",
                "A exportação falhou. Deseja encerrar mesmo assim?",
                icon="error",
                parent=self,
            ):
                return

        SESSION_PATH.unlink(missing_ok=True)

        self.on_close_app(triggered_by_end_session=True)

    def on_close_app(self, triggered_by_end_session: bool = False):
        """Ações ao fechar a janela."""
        logger.info("Sequência de fechamento da aplicação iniciada...")

        if self._action_panel and self._action_panel.search_after_id is not None:
            try:
                self._action_panel.after_cancel(self._action_panel.search_after_id)
            except Exception:
                pass

        if self._fachada:
            id_sessao = self._fachada.id_sessao_ativa
            if not triggered_by_end_session and id_sessao:
                if SESSION_PATH.exists():
                    SESSION_PATH.unlink()
                SESSION_PATH.write_text(
                    f'{{"id_sessao": {id_sessao}}}', encoding="utf-8"
                )
                logger.info(
                    "Estado da sessão salvo pela fachada. Salvo localmente em %s.",
                    str(SESSION_PATH),
                )
            logger.info("Fechando recursos da fachada (conexão com DB)...")
            self._fachada.fechar_conexao()

        logger.debug("Destruindo janela principal Tkinter...")
        try:
            self.destroy()
        except tk.TclError:
            pass
        logger.info("Aplicação finalizada.")


app = RegistrationApp()
app.mainloop()
