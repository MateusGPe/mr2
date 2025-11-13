# ----------------------------------------------------------------------------
# Arquivo: registro/gui/dialogo_sessao.py (Diálogo de Gerenciamento de Sessão - View)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

import datetime as dt
import logging
import threading
import tkinter as tk
from pathlib import Path
from threading import Thread
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Set, Tuple, Union

import ttkbootstrap as ttk
from ttkbootstrap.constants import EW, E, HORIZONTAL, NSEW, W, X
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.scrolled import ScrolledFrame

from registro.controles.treeview_simples import TreeviewSimples
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
        self._conjunto_opcoes_lanche: Set[str] = set()

        # Atributos de widget para acesso posterior
        self._notebook: ttk.Notebook
        self._entrada_hora: ttk.Entry
        self._entrada_data: ttk.DateEntry
        self._combobox_refeicao: ttk.Combobox
        self._combobox_lanche: ttk.Combobox
        self._treeview_sessoes: Optional[TreeviewSimples] = None

        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)

        self._criar_widgets()

        self.update_idletasks()
        self._centralizar_janela()
        self.resizable(True, True)
        self.deiconify()

    def _criar_widgets(self):
        """Cria e organiza todos os widgets na janela de diálogo."""
        main_frame = ttk.Frame(self, padding=15)
        main_frame.grid(row=0, column=0, sticky=NSEW)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        self._notebook = ttk.Notebook(main_frame, bootstyle="primary")
        self._notebook.grid(row=0, column=0, sticky=NSEW)

        tab_criar = ttk.Frame(self._notebook, padding=(10, 15))
        tab_criar.columnconfigure(0, weight=1)
        tab_criar.rowconfigure(1, weight=1)
        self._notebook.add(tab_criar, text="  ➕ Criar Nova Sessão  ")
        self._criar_aba_nova_sessao(tab_criar)

        tab_carregar = ttk.Frame(self._notebook, padding=(10, 15))
        tab_carregar.columnconfigure(0, weight=1)
        tab_carregar.rowconfigure(1, weight=1)
        self._notebook.add(tab_carregar, text="  📝 Carregar Sessão Existente  ")
        self._criar_aba_carregar_sessao(tab_carregar)

        botoes_frame = self._criar_secao_botoes_principais(main_frame)
        botoes_frame.grid(row=1, column=0, sticky=EW, pady=(15, 0))

    def _criar_aba_nova_sessao(self, parent: ttk.Frame):
        """Popula a aba de criação de nova sessão."""
        frame_detalhes = self._criar_secao_nova_sessao(parent)
        frame_detalhes.grid(row=0, column=0, sticky=EW, pady=(0, 20))

        frame_turmas = ttk.Frame(parent)
        frame_turmas.grid(row=1, column=0, sticky=NSEW)
        frame_turmas.columnconfigure(0, weight=1)
        frame_turmas.rowconfigure(2, weight=1)

        ttk.Label(
            frame_turmas,
            text="🎟️ Selecione Turmas Participantes",
            font=("-size 12 -weight bold"),
        ).grid(row=0, column=0, sticky=W, pady=(0, 5))
        ttk.Separator(frame_turmas, orient=HORIZONTAL).grid(
            row=1, column=0, sticky=EW, pady=(0, 15)
        )

        turmas_disponiveis = self._buscar_turmas_disponiveis()
        self._dados_checkbox_turmas, frame_checkboxes = (
            self._criar_secao_checkbox_turmas(frame_turmas, turmas_disponiveis)
        )
        frame_checkboxes.grid(row=2, column=0, sticky=NSEW)

        frame_botoes_turmas = self._criar_secao_botoes_turmas(frame_turmas)
        frame_botoes_turmas.grid(row=3, column=0, sticky=EW, pady=(10, 0))

    def _criar_aba_carregar_sessao(self, parent: ttk.Frame):
        """Popula a aba de carregamento com uma Treeview de sessões."""
        ttk.Label(
            parent, text="Selecione uma Sessão Anterior", font=("-size 12 -weight bold")
        ).grid(row=0, column=0, sticky=W, pady=(0, 5))
        ttk.Separator(parent, orient=HORIZONTAL).grid(
            row=1, column=0, sticky=EW, pady=(0, 15)
        )

        sessoes_data = self._carregar_sessoes_existentes()

        if not sessoes_data:
            ttk.Label(
                parent, text="Nenhuma sessão anterior encontrada.", anchor="center"
            ).grid(row=1, column=0, sticky=NSEW, pady=20)
            return

        cols = [
            {"text": "ID", "stretch": False, "width": 50},
            {"text": "Data", "stretch": False, "width": 100},
            {"text": "Hora", "stretch": False, "width": 80},
            {"text": "Refeição", "stretch": True},
        ]

        self._treeview_sessoes = TreeviewSimples(
            master=parent,
            dados_colunas=cols,
            height=10,
            select_bootstyle="info",
            enable_hover=True,
        )
        self._treeview_sessoes.view.bind(
            "<Double-1>",
            lambda _: (
                self._ao_ok()
                if self._treeview_sessoes.obter_iid_selecionado()
                else None
            ),
        )
        self._treeview_sessoes.grid(row=1, column=0, sticky=NSEW)
        self._treeview_sessoes.construir_dados_tabela(sessoes_data)

    def _criar_secao_nova_sessao(self, parent: tk.Widget) -> ttk.Frame:
        frame = ttk.Frame(parent)
        frame.columnconfigure((1, 3), weight=1)

        ttk.Label(
            frame, text="Detalhes da Sessão", font=("-size 12 -weight bold")
        ).grid(row=0, column=0, columnspan=4, sticky=W, pady=(0, 5))
        ttk.Separator(frame, orient=HORIZONTAL).grid(
            row=1, column=0, columnspan=4, sticky=EW, pady=(0, 15)
        )

        ttk.Label(frame, text="Horário:").grid(row=2, column=0, sticky=W, padx=(0, 5))
        self._entrada_hora = ttk.Entry(frame, width=10)
        self._entrada_hora.insert(0, dt.datetime.now().strftime("%H:%M"))
        self._entrada_hora.grid(row=2, column=1, sticky=EW, pady=(0, 8))

        ttk.Label(frame, text="Data:").grid(row=2, column=2, sticky=W, padx=(15, 5))
        self._entrada_data = ttk.DateEntry(
            frame, width=12, bootstyle="primary", dateformat="%d/%m/%Y"
        )
        self._entrada_data.grid(row=2, column=3, sticky=EW, pady=(0, 8))

        ttk.Label(frame, text="Refeição:").grid(row=3, column=0, sticky=W, padx=(0, 5))
        hora_agora = dt.datetime.now().time()
        eh_hora_almoco = dt.time(11, 00) <= hora_agora <= dt.time(13, 30)
        self._combobox_refeicao = ttk.Combobox(
            frame, values=["Lanche", "Almoço"], state="readonly"
        )
        self._combobox_refeicao.current(1 if eh_hora_almoco else 0)
        self._combobox_refeicao.grid(
            row=3, column=1, columnspan=3, sticky=EW, pady=(0, 8)
        )
        self._combobox_refeicao.bind(
            "<<ComboboxSelected>>", self._ao_selecionar_refeicao
        )

        ttk.Label(frame, text="Item Servido:").grid(
            row=4, column=0, sticky=W, padx=(0, 5)
        )
        self._conjunto_opcoes_lanche, lista_exibicao_lanches = (
            self._carregar_opcoes_lanche()
        )
        self._combobox_lanche = ttk.Combobox(
            frame, values=lista_exibicao_lanches, bootstyle="info"
        )
        self._combobox_lanche.grid(
            row=4, column=1, columnspan=3, sticky=EW, pady=(0, 8)
        )
        self._ao_selecionar_refeicao()

        return frame

    def _criar_secao_checkbox_turmas(
        self, master: tk.Widget, turmas: List[str]
    ) -> Tuple[List[Tuple[str, tk.BooleanVar, ttk.Checkbutton]], ScrolledFrame]:
        container = ScrolledFrame(
            master,
            autohide=True,
            bootstyle="round",
            padding=(0, 0, 20, 0),
            height=100,
            width=500,
        )
        dados_checkbox = []

        if not turmas:
            ttk.Label(container, text="Nenhuma turma disponível.").pack(pady=10)
            return [], container

        num_cols = 3
        container.columnconfigure(list(range(num_cols)), weight=1)
        for i, nome_turma in enumerate(turmas):
            var = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(
                container,
                text=nome_turma,
                variable=var,
                bootstyle="primary-round-toggle",
            )
            cb.grid(
                row=i // num_cols,
                column=i % num_cols,
                sticky=W,
                padx=10,
                pady=4,
            )
            dados_checkbox.append((nome_turma, var, cb))

        return dados_checkbox, container

    def _criar_secao_botoes_turmas(self, parent: tk.Widget) -> ttk.Frame:
        frame_botoes = ttk.Frame(parent)
        frame_botoes.columnconfigure(tuple(range(4)), weight=1)

        botoes = [
            ("⚪ Limpar", self._ao_limpar_turmas, "secondary-outline"),
            ("🔗 Integrado", self._ao_selecionar_integral, "info-outline"),
            ("📚 Outros", self._ao_selecionar_outros, "info-outline"),
            ("🔄 Inverter", self._ao_inverter_turmas, "secondary-outline"),
        ]

        for i, (texto, cmd, estilo) in enumerate(botoes):
            ttk.Button(frame_botoes, text=texto, command=cmd, bootstyle=estilo).grid(
                row=0, column=i, sticky=EW, padx=2
            )
        return frame_botoes

    def _criar_secao_botoes_principais(self, parent: tk.Widget) -> ttk.Frame:
        frame_botoes = ttk.Frame(parent)
        frame_botoes.columnconfigure(0, weight=1)

        ttk.Button(
            frame_botoes,
            text="📥 Sincronizar Reservas",
            command=self._ao_sincronizar_reservas,
            bootstyle="warning-outline",
        ).grid(row=0, column=0, sticky=W)

        ttk.Button(
            frame_botoes,
            text="❌ Cancelar",
            command=self._ao_fechar,
            bootstyle="danger",
        ).grid(row=0, column=1, sticky=E, padx=5)

        ttk.Button(
            frame_botoes, text="✔️ Iniciar", command=self._ao_ok, bootstyle="success"
        ).grid(row=0, column=2, sticky=E)

        return frame_botoes

    def _ao_ok(self):
        aba_selecionada = self._notebook.index(self._notebook.select())

        if aba_selecionada == 1:
            if not self._treeview_sessoes:
                Messagebox.show_warning("Nenhuma sessão para carregar.", parent=self)
                return

            linha_selecionada = self._treeview_sessoes.obter_linha_selecionada()

            if not linha_selecionada:
                Messagebox.show_warning(
                    "Nenhuma Sessão Selecionada",
                    "Por favor, selecione uma sessão da tabela para carregar.",
                    parent=self,
                )
                return

            id_sessao_para_carregar = int(linha_selecionada[0])
            logger.info(
                "Requisitando carregamento da sessão ID %s", id_sessao_para_carregar
            )
            if self._callback(id_sessao_para_carregar):
                self.grab_release()
                self.destroy()
        else:
            if not self._validar_entrada_nova_sessao():
                return

            turmas = [txt for txt, var, _ in self._dados_checkbox_turmas if var.get()]
            refeicao = self._combobox_refeicao.get().lower()
            item = self._combobox_lanche.get().strip() if refeicao == "lanche" else None

            if item:
                self._salvar_nova_opcao_lanche(item)
                item = self._combobox_lanche.get().strip()

            try:
                data_ui = self._entrada_data.entry.get()
                data_backend = dt.datetime.strptime(data_ui, "%d/%m/%Y").strftime(
                    "%Y-%m-%d"
                )
            except (ValueError, AttributeError) as e:
                logger.error("Erro ao converter data: %s", e)
                Messagebox.show_error("Erro Interno", "Data inválida.", parent=self)
                return

            dados_nova_sessao: Dict[str, Union[str, List[str], None]] = {
                "refeicao": refeicao,
                "item_servido": item,
                "periodo": "Integral",
                "data": data_backend,
                "hora": self._entrada_hora.get(),
                "grupos": turmas,
            }

            logger.info("Tentando criar uma nova sessão.")
            if self._callback(dados_nova_sessao):
                self.grab_release()
                self.destroy()

    def _buscar_turmas_disponiveis(self) -> List[str]:
        try:
            grupos = self._fachada.listar_todos_os_grupos()
            return sorted(g.get("nome", "") for g in grupos if g.get("nome"))
        except Exception as e:
            logger.exception("Erro ao buscar turmas: %s", e)
            Messagebox.show_error("Não foi possível buscar as turmas.", parent=self)
            return []

    def _centralizar_janela(self):
        self.update_idletasks()
        parente = self._parente_app
        pos_x = (
            parente.winfo_x() + (parente.winfo_width() // 2) - (self.winfo_width() // 2)
        )
        pos_y = (
            parente.winfo_y()
            + (parente.winfo_height() // 2)
            - (self.winfo_height() // 2)
        )
        self.geometry(f"+{pos_x}+{pos_y}")

    def _ao_fechar(self):
        self.grab_release()
        self.destroy()
        try:
            self._callback(None)
        except Exception as e:
            logger.exception("Erro no callback de fechamento: %s", e)

    def _carregar_opcoes_lanche(self) -> Tuple[Set[str], List[str]]:
        caminho = Path(CAMINHO_JSON_LANCHES)
        padrao = [NOME_LANCHE_PADRAO]
        try:
            opcoes = carregar_json(str(caminho))
            if not isinstance(opcoes, list) or not all(
                isinstance(s, str) for s in opcoes
            ):
                raise TypeError("Conteúdo do JSON de lanches é inválido.")
            return set(opcoes) if opcoes else set(padrao), (
                sorted(opcoes) if opcoes else padrao
            )
        except (FileNotFoundError, TypeError) as e:
            logger.warning(
                "Arquivo de lanches não encontrado ou inválido ('%s'): %s. Usando padrão.",
                caminho,
                e,
            )
            salvar_json(str(caminho), padrao)
            return set(padrao), padrao
        except Exception as e:
            logger.exception("Erro ao carregar lanches de '%s': %s", caminho, e)
            return set(), [f"Erro ao carregar {caminho.name}"]

    def _carregar_sessoes_existentes(self) -> List[Tuple]:
        try:
            sessoes = self._fachada.listar_todas_sessoes()

            def sort_key(s):
                try:
                    # O formato no banco é 'DD/MM/YYYY', precisa converter para ordenar
                    return dt.datetime.strptime(
                        s.get("data", "01/01/1900") + " " + s.get("hora", "00:00"),
                        "%d/%m/%Y %H:%M",
                    )
                except ValueError:
                    return dt.datetime.min  # Põe datas mal formatadas no final

            dados_tabela = []
            for s in sorted(sessoes, key=sort_key, reverse=True):
                linha = (
                    s.get("id"),
                    s.get("data"),
                    s.get("hora"),
                    capitalizar(s.get("refeicao", "")),
                )
                dados_tabela.append(linha)
            return dados_tabela
        except Exception as e:
            logger.exception("Erro ao buscar sessões: %s", e)
            # Retorna lista vazia em caso de erro, a UI mostrará a mensagem
            return []

    def _ao_selecionar_refeicao(self, _=None):
        eh_almoco = self._combobox_refeicao.get() == "Almoço"
        self._combobox_lanche.config(state="disabled" if eh_almoco else "normal")
        if eh_almoco:
            self._combobox_lanche.set("")
        elif NOME_LANCHE_PADRAO in self._conjunto_opcoes_lanche:
            self._combobox_lanche.set(NOME_LANCHE_PADRAO)

    def _ao_limpar_turmas(self):
        self._definir_checkboxes_turmas(lambda n, v: False)

    def _ao_selecionar_integral(self):
        self._definir_checkboxes_turmas(lambda n, v: n in TURMAS_INTEGRADO)

    def _ao_selecionar_outros(self):
        self._definir_checkboxes_turmas(lambda n, v: n not in TURMAS_INTEGRADO)

    def _ao_inverter_turmas(self):
        self._definir_checkboxes_turmas(lambda n, v: not v.get())

    def _definir_checkboxes_turmas(
        self, condicao: Callable[[str, tk.BooleanVar], bool]
    ):
        for nome, var, _ in self._dados_checkbox_turmas:
            var.set(condicao(nome, var))

    def _validar_entrada_nova_sessao(self) -> bool:
        try:
            dt.datetime.strptime(self._entrada_hora.get(), "%H:%M")
        except ValueError:
            Messagebox.show_warning("Hora inválida. Use o formato HH:MM.", parent=self)
            return False
        if not self._entrada_data.entry.get():
            Messagebox.show_warning("Data é obrigatória.", parent=self)
            return False
        if not any(v.get() for n, v, c in self._dados_checkbox_turmas):
            Messagebox.show_warning("Selecione pelo menos uma turma.", parent=self)
            return False
        if (
            self._combobox_refeicao.get() == "Lanche"
            and not self._combobox_lanche.get().strip()
        ):
            Messagebox.show_warning(
                "Especifique o item servido para o lanche.", parent=self
            )
            return False
        return True

    def _salvar_nova_opcao_lanche(self, selecao: str):
        if (
            selecao
            and selecao not in self._conjunto_opcoes_lanche
            and "Erro" not in selecao
        ):
            normalizado = capitalizar(selecao)
            self._conjunto_opcoes_lanche.add(normalizado)
            caminho = Path(CAMINHO_JSON_LANCHES)
            try:
                if salvar_json(
                    str(caminho), sorted(list(self._conjunto_opcoes_lanche))
                ):
                    self._combobox_lanche["values"] = sorted(
                        list(self._conjunto_opcoes_lanche)
                    )
                    self._combobox_lanche.set(normalizado)
            except Exception:
                Messagebox.show_error(
                    "Não foi possível salvar a nova opção de lanche.", parent=self
                )

    def _ao_sincronizar_reservas(self):
        self._parente_app.mostrar_barra_progresso(True, "Sincronizando reservas...")
        self.update_idletasks()

        thread = Thread(target=self._acao_sincronizacao, daemon=True)
        thread.start()
        self._monitorar_sincronizacao(thread)

    def _acao_sincronizacao(self):
        thread = threading.current_thread()
        thread.error = None
        try:
            self._fachada.sincronizar_do_google_sheets()
        except Exception as e:
            thread.error = e

    def _monitorar_sincronizacao(self, thread: Thread):
        if thread.is_alive():
            self.after(150, lambda: self._monitorar_sincronizacao(thread))
            return

        self._parente_app.mostrar_barra_progresso(False)
        erro = getattr(thread, "error", None)
        if erro:
            Messagebox.show_error(
                f"Falha ao sincronizar reservas:\n{erro}", parent=self
            )
        else:
            Messagebox.show_info("Reservas sincronizadas com sucesso.", parent=self)
            self._atualizar_treeview_sessoes_existentes()

    def _atualizar_treeview_sessoes_existentes(self):
        if not self._treeview_sessoes:
            return

        novos_dados = self._carregar_sessoes_existentes()
        self._treeview_sessoes.construir_dados_tabela(novos_dados)
