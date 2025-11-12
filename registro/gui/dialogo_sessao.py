# ----------------------------------------------------------------------------
# Arquivo: registro/gui/dialogo_sessao.py (Diálogo de Gerenciamento de Sessão - View)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

import datetime as dt
import logging
import tkinter as tk
from pathlib import Path
from threading import Thread
from typing import TYPE_CHECKING, Callable, Dict, List, Set, Tuple, Union

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox

from registro.gui.constants import (
    CAMINHO_JSON_LANCHES,
    NOME_LANCHE_PADRAO,
    TURMAS_INTEGRADO,
    DadosNovaSessao,
)
from registro.gui.utils import capitalizar, carregar_json, salvar_json
from registro.nucleo.facade import FachadaRegistro

if TYPE_CHECKING:
    from registro.gui.app_registro import AppRegistro

logger = logging.getLogger(__name__)


def criar_secao_checkbox_turmas(
    master: tk.Widget, turmas_disponiveis: List[str]
) -> tuple[List[Tuple[str, tk.BooleanVar, ttk.Checkbutton]], ttk.Labelframe]:
    frame_grupo = ttk.Labelframe(
        master, text="🎟️ Selecione Turmas Participantes", padding=6
    )
    num_cols = 3
    frame_grupo.columnconfigure(tuple(range(num_cols)), weight=1)

    if not turmas_disponiveis:
        ttk.Label(frame_grupo, text="Nenhuma turma encontrada no banco de dados.").grid(
            column=0, row=0, columnspan=num_cols, pady=10
        )
        frame_grupo.rowconfigure(0, weight=1)
        return [], frame_grupo

    num_rows = (len(turmas_disponiveis) + num_cols - 1) // num_cols
    frame_grupo.rowconfigure(tuple(range(num_rows or 1)), weight=1)

    dados_checkbox = []
    for i, nome_turma in enumerate(turmas_disponiveis):
        check_var = tk.BooleanVar(value=False)
        check_btn = ttk.Checkbutton(
            frame_grupo,
            text=nome_turma,
            variable=check_var,
            bootstyle="success-round-toggle",  # type: ignore
        )
        check_btn.grid(
            column=i % num_cols,
            row=i // num_cols,
            sticky="news",
            padx=10,
            pady=5,
        )
        dados_checkbox.append((nome_turma, check_var, check_btn))

    return dados_checkbox, frame_grupo


class DialogoSessao(tk.Toplevel):
    def __init__(
        self,
        title: str,
        callback: Callable[[Union[DadosNovaSessao, int, None]], bool],
        parente_app: "AppRegistro",
    ):
        super().__init__(parente_app)
        self.withdraw()

        self.title(title)
        self.transient(parente_app)
        self.grab_set()

        self._callback = callback
        self._parente_app = parente_app
        self._fachada: "FachadaRegistro" = parente_app.get_fachada()
        self._dados_checkbox_turmas: List[
            Tuple[str, tk.BooleanVar, ttk.Checkbutton]
        ] = []
        self._mapa_sessoes: Dict[str, int] = {}
        self._conjunto_opcoes_lanche: Set[str] = set()

        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)

        self._frame_nova_sessao = self._criar_secao_nova_sessao()
        self._frame_nova_sessao.grid(
            column=0, row=0, padx=10, pady=(10, 5), sticky="ew"
        )

        turmas_disponiveis = self._buscar_turmas_disponiveis()
        self._dados_checkbox_turmas, self._frame_selecao_turmas = (
            criar_secao_checkbox_turmas(self, turmas_disponiveis)  # type: ignore
        )
        self._frame_selecao_turmas.grid(column=0, row=1, padx=10, pady=5, sticky="nsew")
        self.rowconfigure(1, weight=1)

        self._criar_secao_botoes_turmas().grid(
            column=0, row=2, padx=10, pady=5, sticky="ew"
        )
        self._frame_editar_sessao = self._criar_secao_editar_sessao()
        self._frame_editar_sessao.grid(column=0, row=3, padx=10, pady=5, sticky="ew")

        self._frame_botoes_principais = self._criar_secao_botoes_principais()
        self._frame_botoes_principais.grid(
            column=0, row=4, padx=10, pady=(5, 10), sticky="ew"
        )

        self.update_idletasks()
        self._centralizar_janela()
        self.resizable(False, True)
        self.deiconify()

    def _buscar_turmas_disponiveis(self) -> List[str]:
        try:
            grupos = self._fachada.listar_todos_os_grupos()
            turmas = sorted(g.get("nome", "") for g in grupos if g.get("nome"))
            return turmas
        except Exception as e:
            logger.exception(
                "Erro ao buscar turmas disponíveis da fachada. %s: %s",
                type(e).__name__,
                e,
            )
            Messagebox.show_error(
                "Erro de Banco de Dados",
                "Não foi possível buscar as turmas.",
                parent=self,
            )
            return []

    def _centralizar_janela(self):
        self.update_idletasks()
        parente = self._parente_app
        parente_x, parente_y = parente.winfo_x(), parente.winfo_y()
        parente_w, parente_h = parente.winfo_width(), parente.winfo_height()
        dialog_w, dialog_h = self.winfo_width(), self.winfo_height()
        pos_x = parente_x + (parente_w // 2) - (dialog_w // 2)
        pos_y = parente_y + (parente_h // 2) - (dialog_h // 2)
        self.geometry(f"+{pos_x}+{pos_y}")

    def _ao_fechar(self):
        logger.info("Diálogo de sessão fechado pelo usuário.")
        self.grab_release()
        self.destroy()
        try:
            self._callback(None)
        except Exception as e:
            logger.exception("Erro no callback de fechamento do diálogo: %s", e)

    def _criar_secao_nova_sessao(self) -> ttk.Labelframe:
        frame = ttk.Labelframe(self, text="➕ Detalhes da Nova Sessão", padding=10)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        ttk.Label(master=frame, text="⏰ Horário:").grid(
            row=0, column=0, sticky="w", padx=(0, 5), pady=3
        )
        self._entrada_hora = ttk.Entry(frame, width=8)
        self._entrada_hora.insert(0, dt.datetime.now().strftime("%H:%M"))
        self._entrada_hora.grid(row=0, column=1, sticky="w", padx=5, pady=3)

        ttk.Label(master=frame, text="📅 Data:").grid(
            row=0, column=2, sticky="w", padx=(10, 5), pady=3
        )
        self._entrada_data = ttk.DateEntry(
            frame, width=12, bootstyle="primary", dateformat="%d/%m/%Y"
        )
        self._entrada_data.grid(row=0, column=3, sticky="ew", padx=(0, 5), pady=3)

        ttk.Label(master=frame, text="🍽️ Refeição:").grid(
            row=1, column=0, sticky="w", padx=(0, 5), pady=3
        )
        hora_agora = dt.datetime.now().time()
        eh_hora_almoco = dt.time(11, 00) <= hora_agora <= dt.time(13, 30)
        opcoes_refeicao = ["Lanche", "Almoço"]
        self._combobox_refeicao = ttk.Combobox(
            master=frame, values=opcoes_refeicao, state="readonly", bootstyle="info"  # type: ignore
        )
        self._combobox_refeicao.current(1 if eh_hora_almoco else 0)
        self._combobox_refeicao.grid(
            row=1, column=1, columnspan=3, sticky="ew", padx=5, pady=3
        )
        self._combobox_refeicao.bind(
            "<<ComboboxSelected>>", self._ao_selecionar_refeicao
        )

        ttk.Label(master=frame, text="🥪 Lanche Específico:").grid(
            row=2, column=0, sticky="w", padx=(0, 5), pady=3
        )
        self._conjunto_opcoes_lanche, lista_exibicao_lanches = (
            self._carregar_opcoes_lanche()
        )
        self._combobox_lanche = ttk.Combobox(
            master=frame, values=lista_exibicao_lanches, bootstyle="warning"  # type: ignore
        )
        self._combobox_lanche.config(
            state=(
                "disabled" if self._combobox_refeicao.get() == "Almoço" else "normal"
            )
        )
        if lista_exibicao_lanches and "Erro" not in lista_exibicao_lanches[0]:
            self._combobox_lanche.current(0)
        self._combobox_lanche.grid(
            row=2, column=1, columnspan=3, sticky="ew", padx=5, pady=3
        )
        return frame

    def _carregar_opcoes_lanche(self) -> Tuple[Set[str], List[str]]:
        caminho_lanches = Path(CAMINHO_JSON_LANCHES)
        opcoes_padrao = [NOME_LANCHE_PADRAO]
        try:
            opcoes_lanche = carregar_json(str(caminho_lanches))
            if not isinstance(opcoes_lanche, list) or not all(
                (isinstance(s, str) for s in opcoes_lanche)
            ):
                logger.error(
                    "Conteúdo inválido em '%s'. Esperada lista de strings.",
                    caminho_lanches,
                )
                msg_erro = f"Erro: Conteúdo inválido em {caminho_lanches.name}"
                return set(), [msg_erro]
            if not opcoes_lanche:
                return set(opcoes_padrao), opcoes_padrao
            return set(opcoes_lanche), sorted(opcoes_lanche)
        except FileNotFoundError:
            logger.warning(
                "Arquivo de opções de lanche '%s' não encontrado. Usando padrão.",
                caminho_lanches,
            )
            salvar_json(str(caminho_lanches), opcoes_padrao)
            return set(opcoes_padrao), opcoes_padrao
        except Exception as e:
            logger.exception(
                "Erro ao carregar opções de lanche de '%s'. %s: %s",
                caminho_lanches,
                type(e).__name__,
                e,
            )
            return (set(), [f"Erro ao carregar {caminho_lanches.name}"])

    def _criar_secao_botoes_turmas(self) -> ttk.Frame:
        frame_botoes = ttk.Frame(self)
        frame_botoes.columnconfigure(tuple(range(4)), weight=1)
        config_botoes = [
            ("⚪ Limpar", self._ao_limpar_turmas, "outline-secondary"),
            ("🔗 Integrado", self._ao_selecionar_integral, "outline-info"),
            ("📚 Outros", self._ao_selecionar_outros, "outline-info"),
            ("🔄 Inverter", self._ao_inverter_turmas, "outline-secondary"),
        ]
        for i, (texto, cmd, estilo) in enumerate(config_botoes):
            ttk.Button(
                master=frame_botoes,
                text=texto,
                command=cmd,
                bootstyle=estilo,  # type: ignore
                width=15,
            ).grid(row=0, column=i, padx=2, pady=2, sticky="ew")
        return frame_botoes

    def _criar_secao_editar_sessao(self) -> ttk.Labelframe:
        frame = ttk.Labelframe(
            self, text="📝 Selecionar Sessão Existente para Editar", padding=10
        )
        frame.columnconfigure(0, weight=1)

        self._mapa_sessoes, lista_exibicao_sessoes = self._carregar_sessoes_existentes()

        self._combobox_sessoes = ttk.Combobox(
            master=frame,
            values=lista_exibicao_sessoes,
            state="readonly",
            bootstyle="dark",  # type: ignore
        )
        placeholder = "Selecione uma sessão existente para carregar..."
        if lista_exibicao_sessoes and "Erro" not in lista_exibicao_sessoes[0]:
            self._combobox_sessoes.set(placeholder)
        elif lista_exibicao_sessoes:
            self._combobox_sessoes.current(0)
            self._combobox_sessoes.config(state="disabled")
        else:
            self._combobox_sessoes.set("Nenhuma sessão existente encontrada.")
            self._combobox_sessoes.config(state="disabled")

        self._combobox_sessoes.grid(row=0, column=0, sticky="ew", padx=3, pady=3)
        return frame

    def _carregar_sessoes_existentes(self) -> Tuple[Dict[str, int], List[str]]:
        try:
            sessoes: List[Dict] = self._fachada.listar_todas_sessoes()
            mapa_sessoes = {}
            for s in sessoes:
                try:
                    data_exibicao = dt.datetime.strptime(
                        s["data"], "%Y-%m-%d"
                    ).strftime("%d/%m/%Y")
                except (ValueError, KeyError):
                    data_exibicao = s.get("data", "Data Inválida")

                s_id = s.get("id")
                s_hora = s.get("hora", "Hora")
                s_refeicao = s.get("refeicao", "Refeição")

                texto_exibicao = (
                    f"{data_exibicao} {s_hora} - "
                    f"{capitalizar(s_refeicao)} (ID: {s_id})"
                )
                mapa_sessoes[texto_exibicao] = s_id

            return mapa_sessoes, list(mapa_sessoes.keys())
        except Exception as e:
            logger.exception(
                "Erro ao buscar sessões existentes da fachada. %s: %s",
                type(e).__name__,
                e,
            )
            msg_erro = "Erro ao carregar sessões"
            return {msg_erro: -1}, [msg_erro]

    def _criar_secao_botoes_principais(self) -> ttk.Frame:
        frame_botoes = ttk.Frame(self)
        frame_botoes.columnconfigure(0, weight=1)
        frame_botoes.columnconfigure(4, weight=1)

        ttk.Button(
            master=frame_botoes,
            text="📥 Sincronizar Reservas",
            command=self._ao_sincronizar_reservas,
            bootstyle="outline-warning",  # type: ignore
        ).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(
            master=frame_botoes,
            text="❌ Cancelar",
            command=self._ao_fechar,
            bootstyle="danger",  # type: ignore
        ).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(
            master=frame_botoes,
            text="✔️ OK",
            command=self._ao_ok,
            bootstyle="success",  # type: ignore
        ).grid(row=0, column=3, padx=5, pady=5)
        return frame_botoes

    def _ao_selecionar_refeicao(self, _=None):
        eh_almoco = self._combobox_refeicao.get() == "Almoço"
        novo_estado = "disabled" if eh_almoco else "normal"
        self._combobox_lanche.config(state=novo_estado)
        if eh_almoco:
            self._combobox_lanche.set("")

    def _ao_limpar_turmas(self):
        self._definir_checkboxes_turmas(lambda nome, var: False)

    def _ao_selecionar_integral(self):
        self._definir_checkboxes_turmas(lambda nome, var: nome in TURMAS_INTEGRADO)

    def _ao_selecionar_outros(self):
        self._definir_checkboxes_turmas(lambda nome, var: nome not in TURMAS_INTEGRADO)

    def _ao_inverter_turmas(self):
        self._definir_checkboxes_turmas(lambda nome, var: not var.get())

    def _definir_checkboxes_turmas(
        self, funcao_condicao: Callable[[str, tk.BooleanVar], bool]
    ):
        if not self._dados_checkbox_turmas:
            logger.warning(
                "Tentativa de definir checkboxes de turma sem dados disponíveis."
            )
            return
        for nome_turma, check_var, _ in self._dados_checkbox_turmas:
            check_var.set(funcao_condicao(nome_turma, check_var))

    def _validar_entrada_nova_sessao(self) -> bool:
        try:
            dt.datetime.strptime(self._entrada_hora.get(), "%H:%M")
        except ValueError:
            Messagebox.show_warning(
                "Entrada Inválida",
                "Formato de hora inválido. Use HH:MM.",
                parent=self,
            )
            self._entrada_hora.focus_set()
            return False

        try:
            data_str = self._entrada_data.entry.get()
            dt.datetime.strptime(data_str, "%d/%m/%Y")
        except ValueError:
            Messagebox.show_warning(
                "Entrada Inválida",
                "Formato de data inválido. Use DD/MM/YYYY.",
                parent=self,
            )
            self._entrada_data.focus_set()
            return False
        except AttributeError:
            logger.warning(
                "Não foi possível acessar widget de DateEntry para validação."
            )

        if self._combobox_refeicao.get() not in ["Lanche", "Almoço"]:
            Messagebox.show_warning(
                "Entrada Inválida",
                "Selecione um Tipo de Refeição válido.",
                parent=self,
            )
            return False

        tipo_refeicao = self._combobox_refeicao.get()
        selecao_lanche = self._combobox_lanche.get().strip()
        if tipo_refeicao == "Lanche" and not selecao_lanche:
            Messagebox.show_warning(
                "Entrada Inválida",
                "Especifique o nome do lanche para 'Lanche'.",
                parent=self,
            )
            self._combobox_lanche.focus_set()
            return False

        if not any(var.get() for _, var, _ in self._dados_checkbox_turmas):
            Messagebox.show_warning(
                "Seleção Inválida",
                "Selecione pelo menos uma turma participante.",
                parent=self,
            )
            return False

        return True

    def _salvar_nova_opcao_lanche(self, selecao_lanche: str):
        if (
            selecao_lanche
            and selecao_lanche not in self._conjunto_opcoes_lanche
            and "Erro" not in selecao_lanche
        ):
            lanche_normalizado = capitalizar(selecao_lanche)
            logger.info(
                "Nova opção de lanche digitada: '%s'. Adicionando à lista.",
                lanche_normalizado,
            )
            self._conjunto_opcoes_lanche.add(lanche_normalizado)
            caminho_lanches = Path(CAMINHO_JSON_LANCHES)
            try:
                if salvar_json(
                    str(caminho_lanches), sorted(list(self._conjunto_opcoes_lanche))
                ):
                    logger.info("Opções de lanche salvas em '%s'.", caminho_lanches)
                    self._combobox_lanche["values"] = sorted(
                        list(self._conjunto_opcoes_lanche)
                    )
                    self._combobox_lanche.set(lanche_normalizado)
                else:
                    Messagebox.show_error(
                        "Erro ao Salvar",
                        "Não foi possível salvar a nova opção de lanche.",
                        parent=self,
                    )
            except Exception as e:
                logger.exception(
                    "Erro ao salvar nova opção de lanche '%s'. %s: %s",
                    lanche_normalizado,
                    type(e).__name__,
                    e,
                )
                Messagebox.show_error(
                    "Erro ao Salvar",
                    "Erro inesperado ao salvar lista de lanches.",
                    parent=self,
                )

    def _ao_ok(self):
        exibicao_sessao_selecionada = self._combobox_sessoes.get()
        id_sessao_para_carregar = None

        eh_placeholder = any(
            ph in exibicao_sessao_selecionada for ph in ["Selecione", "Erro", "Nenhuma"]
        )
        if exibicao_sessao_selecionada and not eh_placeholder:
            id_sessao_para_carregar = self._mapa_sessoes.get(
                exibicao_sessao_selecionada
            )

        if id_sessao_para_carregar is not None:
            logger.info(
                "Requisitando carregamento da sessão ID %s", id_sessao_para_carregar
            )
            sucesso = self._callback(id_sessao_para_carregar)
            if sucesso:
                logger.info("Sessão existente carregada com sucesso.")
                self.grab_release()
                self.destroy()
            else:
                logger.warning("Falha ao carregar sessão existente.")
        else:
            logger.info("Tentando criar uma nova sessão.")
            if not self._validar_entrada_nova_sessao():
                return

            turmas_selecionadas = [
                txt for txt, var, _ in self._dados_checkbox_turmas if var.get()
            ]
            tipo_refeicao = self._combobox_refeicao.get().lower()

            selecao_lanche = (
                self._combobox_lanche.get().strip()
                if tipo_refeicao == "lanche"
                else None
            )
            if selecao_lanche:
                self._salvar_nova_opcao_lanche(selecao_lanche)
                selecao_lanche = self._combobox_lanche.get().strip()

            try:
                data_ui = self._entrada_data.entry.get()
                data_backend = dt.datetime.strptime(data_ui, "%d/%m/%Y").strftime(
                    "%Y-%m-%d"
                )
            except (ValueError, AttributeError) as e:
                logger.error("Erro ao converter data: %s", e)
                Messagebox.show_error(
                    "Erro Interno", "Data inválida.", parent=self, localize=True
                )
                return

            dados_nova_sessao: Dict[str, Union[str, List[str], None]] = {
                "refeicao": tipo_refeicao,
                "item_servido": selecao_lanche,
                "periodo": "",
                "data": data_backend,
                "hora": self._entrada_hora.get(),
                "grupos": turmas_selecionadas,
            }

            sucesso = self._callback(dados_nova_sessao)  # type: ignore
            if sucesso:
                logger.info("Nova sessão criada com sucesso.")
                self.grab_release()
                self.destroy()
            else:
                logger.warning("Falha ao criar nova sessão.")

    def _ao_sincronizar_reservas(self):
        logger.info("Botão Sincronizar Reservas clicado.")
        self._parente_app.mostrar_barra_progresso(True, "Sincronizando reservas...")
        self.update_idletasks()

        class ThreadWithAttrs(Thread):
            error: Exception | None
            success: bool

        thread: ThreadWithAttrs

        def acao_sincronizacao():
            thread.error = None
            thread.success = False
            try:
                self._fachada.sincronizar_do_google_sheets()
                thread.success = True
            except Exception as e:
                thread.error = e

        thread_sinc = ThreadWithAttrs(target=acao_sincronizacao, daemon=True)
        thread = thread_sinc
        thread.error = None  # type: ignore
        thread.success = False  # type: ignore
        thread_sinc.start()

        self._monitorar_sincronizacao(thread_sinc)

    def _monitorar_sincronizacao(self, thread: Thread):
        if thread.is_alive():
            self.after(150, lambda: self._monitorar_sincronizacao(thread))
        else:
            self._parente_app.mostrar_barra_progresso(False)
            erro = getattr(thread, "error", None)
            sucesso = getattr(thread, "success", False)

            if erro:
                logger.error("Sincronização de reservas falhou: %s", erro)
                Messagebox.show_error(
                    "Erro de Sincronização",
                    f"Falha ao sincronizar reservas:\n{erro}",
                    parent=self,
                )
            elif sucesso:
                logger.info("Sincronização de reservas concluída com sucesso.")
                Messagebox.show_info(
                    "Sincronização Concluída",
                    "Reservas sincronizadas com sucesso com o banco de dados.",
                    parent=self,
                )
                self._atualizar_combobox_sessoes_existentes()
            else:
                logger.warning("Thread de sincronização finalizou indeterminada.")
                Messagebox.show_warning(
                    "Status Incerto",
                    "Sincronização finalizada.",
                    parent=self,
                )

    def _atualizar_combobox_sessoes_existentes(self):
        logger.debug("Atualizando combobox de sessões existentes...")
        self._mapa_sessoes, lista_exibicao_sessoes = self._carregar_sessoes_existentes()
        self._combobox_sessoes["values"] = lista_exibicao_sessoes
        placeholder = "Selecione uma sessão existente para carregar..."
        if lista_exibicao_sessoes and "Erro" not in lista_exibicao_sessoes[0]:
            self._combobox_sessoes.set(placeholder)
            self._combobox_sessoes.config(state="readonly")
        elif lista_exibicao_sessoes:
            self._combobox_sessoes.current(0)
            self._combobox_sessoes.config(state="disabled")
        else:
            self._combobox_sessoes.set("Nenhuma sessão existente encontrada.")
            self._combobox_sessoes.config(state="disabled")
