# ----------------------------------------------------------------------------
# Arquivo: registro/gui/dialogo_sessao.py (Diálogo de Gerenciamento de Sessão)
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
from ttkbootstrap.constants import E, EW, HORIZONTAL, NSEW, W
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.localization.msgcat import MessageCatalog
from ttkbootstrap.scrolled import ScrolledFrame

from registro.controles.treeview_simples import TreeviewSimples
from registro.gui.constants import (
    CAMINHO_JSON_LANCHES,
    NOME_LANCHE_PADRAO,
    CAMINHO_JSON_PRESETS_TURMAS,
    TURMAS_INTEGRADO,
    DadosNovaSessao,
)
from registro.gui.utils import capitalizar, carregar_json, salvar_json
from registro.nucleo.facade import FachadaRegistro

if TYPE_CHECKING:
    from registro.gui.app_registro import AppRegistro

logger = logging.getLogger(__name__)


class DialogoSessao(tk.Toplevel):
    """
    Diálogo para criar uma nova sessão de registro ou carregar uma existente.
    """

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
        self._presets_turmas: Dict[str, Dict[str, List[str]]] = {}

        self._notebook: Optional[ttk.Notebook] = None
        self._entrada_hora: Optional[ttk.Entry] = None
        self._entrada_data: Optional[ttk.DateEntry] = None
        self._combobox_refeicao: Optional[ttk.Combobox] = None
        self._combobox_lanche: Optional[ttk.Combobox] = None
        self._treeview_sessoes: Optional[TreeviewSimples] = None

        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)

        self._criar_widgets()
        self._carregar_presets_turmas()
        self._centralizar_janela()
        self.resizable(True, True)
        self.deiconify()

    def _criar_widgets(self):
        """Cria e organiza todos os widgets no diálogo."""
        main_frame = ttk.Frame(self, padding=15)
        main_frame.grid(row=0, column=0, sticky=NSEW)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)

        self._notebook = ttk.Notebook(main_frame, bootstyle="primary")
        self._notebook.grid(row=0, column=0, sticky=NSEW)

        self._criar_aba("➕ Criar Nova Sessão",
                        self._criar_conteudo_aba_nova_sessao)
        self._criar_aba(
            "📝 Carregar Sessão Existente", self._criar_conteudo_aba_carregar_sessao
        )

        botoes_frame = self._criar_secao_botoes_principais(main_frame)
        botoes_frame.grid(row=1, column=0, sticky=EW, pady=(15, 0))

    def _criar_aba(self, texto_aba: str, construtor_conteudo: Callable):
        """Cria uma aba no notebook e a popula usando uma função construtora."""
        frame_aba = ttk.Frame(self._notebook, padding=(10, 15))
        frame_aba.columnconfigure(0, weight=1)
        frame_aba.rowconfigure(1, weight=1)
        self._notebook.add(frame_aba, text=f"  {texto_aba}  ")
        construtor_conteudo(frame_aba)
        return frame_aba

    def _criar_conteudo_aba_nova_sessao(self, parent: ttk.Frame):
        """Popula a aba de criação de nova sessão."""
        frame_detalhes = self._criar_secao_detalhes_sessao(parent)
        frame_detalhes.grid(row=0, column=0, sticky=EW, pady=(0, 20))

        frame_turmas = self._criar_secao_selecao_turmas(parent)
        frame_turmas.grid(row=1, column=0, sticky=NSEW)

    def _criar_conteudo_aba_carregar_sessao(self, parent: ttk.Frame):
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
        self._treeview_sessoes.view.bind("<Double-1>", lambda _: self._ao_ok())
        self._treeview_sessoes.grid(row=2, column=0, sticky=NSEW)
        self._treeview_sessoes.construir_dados_tabela(sessoes_data)

    def _criar_secao_detalhes_sessao(self, parent: ttk.Frame) -> ttk.Frame:
        """Cria os campos de entrada para os detalhes da nova sessão."""
        frame = ttk.Frame(parent)
        frame.columnconfigure((1, 3), weight=1)

        ttk.Label(
            frame, text="Detalhes da Sessão", font=("-size 12 -weight bold")
        ).grid(row=0, column=0, columnspan=4, sticky=W, pady=(0, 5))
        ttk.Separator(frame, orient=HORIZONTAL).grid(
            row=1, column=0, columnspan=4, sticky=EW, pady=(0, 15)
        )

        self._entrada_hora = self._criar_campo_detalhe(
            frame, "Horário:", 2, 0, ttk.Entry, width=10
        )
        self._entrada_hora.insert(0, dt.datetime.now().strftime("%H:%M"))

        self._entrada_data = self._criar_campo_detalhe(
            frame,
            "Data:",
            2,
            2,
            ttk.DateEntry,
            width=12,
            bootstyle="primary",
            dateformat="%d/%m/%Y",
        )
        self._combobox_refeicao = self._criar_campo_detalhe(
            frame,
            "Refeição:",
            3,
            0,
            ttk.Combobox,
            values=["Lanche", "Almoço"],
            state="readonly",
            columnspan=3,
        )
        self._combobox_lanche = self._criar_campo_detalhe(
            frame, "Item Servido:", 4, 0, ttk.Combobox, bootstyle="info", columnspan=3
        )

        hora_agora = dt.datetime.now().time()
        eh_hora_almoco = dt.time(11, 0) <= hora_agora <= dt.time(13, 30)
        self._combobox_refeicao.current(1 if eh_hora_almoco else 0)
        self._combobox_refeicao.bind(
            "<<ComboboxSelected>>", self._ao_selecionar_refeicao
        )

        opcoes_lanche, lista_exibicao = self._carregar_opcoes_lanche()
        self._conjunto_opcoes_lanche = opcoes_lanche
        self._combobox_lanche["values"] = lista_exibicao
        self._ao_selecionar_refeicao()

        return frame

    def _criar_campo_detalhe(
        self, parent, label, row, col, widget_class, columnspan=1, **kwargs
    ):
        """Helper para criar um par Label-Widget."""
        ttk.Label(parent, text=label).grid(
            row=row, column=col, sticky=W, padx=(col > 0) * 15 + 5
        )
        widget = widget_class(parent, **kwargs)
        widget.grid(
            row=row, column=col + 1, columnspan=columnspan, sticky=EW, pady=(0, 8)
        )
        return widget

    def _criar_secao_selecao_turmas(self, parent: ttk.Frame) -> ttk.Frame:
        """Cria a seção para selecionar as turmas participantes."""
        frame = ttk.Frame(parent)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        ttk.Label(
            frame,
            text="🎟️ Selecione Turmas Participantes",
            font=("-size 12 -weight bold"),
        ).grid(row=0, column=0, sticky=W, pady=(0, 5))
        ttk.Separator(frame, orient=HORIZONTAL).grid(
            row=1, column=0, sticky=EW, pady=(0, 15)
        )

        turmas_disponiveis = self._buscar_turmas_disponiveis()
        self._dados_checkbox_turmas, frame_checkboxes = self._criar_checkboxes_turmas(
            frame, turmas_disponiveis
        )
        frame_checkboxes.grid(row=2, column=0, sticky=NSEW)

        frame_botoes = self._criar_secao_botoes_turmas(frame)
        frame_botoes.grid(row=3, column=0, sticky=EW, pady=(10, 0))

        frame_presets = self._criar_secao_botoes_presets(frame)
        frame_presets.grid(row=4, column=0, sticky=EW, pady=(10, 0))
        return frame

    def _criar_checkboxes_turmas(self, master, turmas):
        """Cria os checkboxes para cada turma dentro de um ScrolledFrame."""
        container = ScrolledFrame(
            master, autohide=True, bootstyle="round", height=100, width=500
        )
        dados = []
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
            cb.grid(row=i // num_cols, column=i %
                    num_cols, sticky=W, padx=10, pady=4)
            dados.append((nome_turma, var, cb))

        return dados, container

    def _criar_secao_botoes_turmas(self, parent: tk.Widget) -> ttk.Frame:
        """Cria os botões de ação para seleção de turmas (Limpar, Integrado, etc.)."""
        frame = ttk.Frame(parent)
        frame.columnconfigure(tuple(range(4)), weight=1)
        botoes = [
            ("⚪ Limpar", self._ao_limpar_turmas, "secondary-outline"),
            ("🔗 Integrado", self._ao_selecionar_integral, "info-outline"),
            ("📚 Outros", self._ao_selecionar_outros, "info-outline"),
            ("🔄 Inverter", self._ao_inverter_turmas, "secondary-outline"),
        ]
        for i, (texto, cmd, estilo) in enumerate(botoes):
            ttk.Button(frame, text=texto, command=cmd, bootstyle=estilo).grid(
                row=0, column=i, sticky=EW, padx=2
            )
        return frame

    def _criar_secao_botoes_presets(self, parent: tk.Widget) -> ttk.Frame:
        """Cria os botões de preset de seleção de turmas."""
        frame = ttk.Frame(parent)
        frame.columnconfigure(tuple(range(1, 6)), weight=1)

        dias_semana = [
            ("Seg", "seg"), ("Ter", "ter"), ("Qua", "qua"), ("Qui", "qui"), ("Sex", "sex")
        ]
        periodos = [("Manhã", "manha"), ("Tarde", "tarde")]

        for row_offset, (periodo_label, periodo_key) in enumerate(periodos):
            ttk.Label(frame, text=f"{periodo_label}:").grid(row=row_offset, column=0, sticky=E, padx=(0, 5))
            for col, (dia_label, dia_key) in enumerate(dias_semana, start=1):
                btn = ttk.Button(
                    frame,
                    text=dia_label,
                    command=lambda p=periodo_key, d=dia_key: self._ao_selecionar_preset(p, d),
                    bootstyle="primary-outline"
                )
                btn.grid(row=row_offset, column=col, sticky=EW, padx=2, pady=2)
                btn.bind("<Button-3>", lambda e, p=periodo_key, d=dia_key: self._ao_salvar_preset(e, p, d))
        return frame

    def _criar_secao_botoes_principais(self, parent: tk.Widget) -> ttk.Frame:
        """Cria os botões principais na parte inferior do diálogo (Sincronizar, Cancelar, Iniciar)."""
        frame = ttk.Frame(parent)
        frame.columnconfigure(0, weight=1)

        ttk.Button(
            frame,
            text="📥 Sincronizar Reservas",
            command=self._ao_sincronizar_reservas,
            bootstyle="warning-outline",
        ).grid(row=0, column=0, sticky=W)
        ttk.Button(
            frame, text="❌ Cancelar", command=self._ao_fechar, bootstyle="danger"
        ).grid(row=0, column=1, sticky=E, padx=5)
        ttk.Button(
            frame, text="✔️ Iniciar", command=self._ao_ok, bootstyle="success"
        ).grid(row=0, column=2, sticky=E)

        return frame

    def _ao_ok(self):
        """Callback do botão 'Iniciar'. Processa a criação ou carregamento de uma sessão."""
        if self._notebook.index(self._notebook.select()) == 1:
            self._processar_carregar_sessao()
        else:
            self._processar_criar_sessao()

    def _ao_fechar(self):
        """Callback para fechar o diálogo, notificando a aplicação principal."""
        self.grab_release()
        self.destroy()
        self._callback(None)

    def _ao_selecionar_refeicao(self, _=None):
        """Habilita/desabilita o campo de lanche com base na refeição selecionada."""
        if not self._combobox_refeicao or not self._combobox_lanche:
            return
        eh_almoco = self._combobox_refeicao.get() == "Almoço"
        self._combobox_lanche.config(
            state="disabled" if eh_almoco else "normal")
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

    def _processar_carregar_sessao(self):
        """Valida e envia o ID da sessão selecionada para a aplicação principal."""
        if not self._treeview_sessoes:
            return
        linha = self._treeview_sessoes.obter_linha_selecionada()
        if not linha:
            Messagebox.show_warning(
                "Nenhuma Sessão Selecionada",
                "Selecione uma sessão para carregar.",
                parent=self,
            )
            return

        id_sessao = int(linha[0])
        logger.info("Requisitando carregamento da sessão ID %s", id_sessao)
        if self._callback(id_sessao):
            self.grab_release()
            self.destroy()

    def _processar_criar_sessao(self):
        """Valida os dados e envia as informações da nova sessão para a aplicação principal."""
        if not self._validar_entrada_nova_sessao():
            return

        turmas = [txt for txt, var,
                  _ in self._dados_checkbox_turmas if var.get()]
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
            Messagebox.show_error(
                "Erro Interno", "Data inválida.", parent=self)
            return

        dados_nova_sessao: DadosNovaSessao = {
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

    def _validar_entrada_nova_sessao(self) -> bool:
        """Verifica se os campos para criar uma nova sessão foram preenchidos corretamente."""
        try:
            dt.datetime.strptime(self._entrada_hora.get(), "%H:%M")
        except ValueError:
            Messagebox.show_warning(
                "Hora inválida. Use o formato HH:MM.", parent=self)
            return False

        if not self._entrada_data.entry.get():
            Messagebox.show_warning("Data é obrigatória.", parent=self)
            return False

        if not any(v.get() for n, v, c in self._dados_checkbox_turmas):
            Messagebox.show_warning(
                "Selecione pelo menos uma turma.", parent=self)
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

    def _buscar_turmas_disponiveis(self) -> List[str]:
        """Busca a lista de turmas/grupos da camada de negócio."""
        try:
            grupos = self._fachada.listar_todos_os_grupos()
            return sorted(g.get("nome", "") for g in grupos if g.get("nome"))
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Erro ao buscar turmas: %s", e)
            Messagebox.show_error(
                "Não foi possível buscar as turmas.", parent=self)
            return []

    def _carregar_presets_turmas(self):
        """Carrega os presets de seleção de turmas de um arquivo JSON."""
        presets = carregar_json(str(CAMINHO_JSON_PRESETS_TURMAS))
        default_presets = {
            "manha": {"seg": [], "ter": [], "qua": [], "qui": [], "sex": []},
            "tarde": {"seg": [], "ter": [], "qua": [], "qui": [], "sex": []},
        }
        if not isinstance(presets, dict) or "manha" not in presets or "tarde" not in presets:
            logger.warning("Arquivo de presets de turmas não encontrado ou inválido. Criando um padrão.")
            self._presets_turmas = default_presets
            salvar_json(str(CAMINHO_JSON_PRESETS_TURMAS), self._presets_turmas)
        else:
            self._presets_turmas = presets

    def _ao_selecionar_preset(self, periodo: str, dia: str):
        """Seleciona as turmas de um preset."""
        turmas_preset = self._presets_turmas.get(periodo, {}).get(dia, [])
        if not turmas_preset:
            Messagebox.show_info(
                "Preset Vazio",
                f"O preset para {periodo.capitalize()} - {dia.capitalize()} está vazio.\n"
                "Para definir, selecione as turmas e clique com o botão direito no botão do preset.",
                parent=self
            )
            return
        self._definir_checkboxes_turmas(lambda nome, var: nome in turmas_preset)

    def _ao_salvar_preset(self, event: tk.Event, periodo: str, dia: str):
        """Salva a seleção atual de turmas em um preset."""
        turmas_selecionadas = [
            nome for nome, var, _ in self._dados_checkbox_turmas if var.get()
        ]

        if not turmas_selecionadas:
            msg = "Nenhuma turma selecionada. Deseja salvar este preset como vazio?"
        else:
            msg = (
                f"Salvar a seleção atual ({len(turmas_selecionadas)} turmas) como o preset para "
                f"{periodo.capitalize()} - {dia.capitalize()}?"
            )

        if Messagebox.yesno("Salvar Preset", msg, parent=self) == MessageCatalog.translate("Yes"):
            self._presets_turmas[periodo][dia] = turmas_selecionadas
            if salvar_json(str(CAMINHO_JSON_PRESETS_TURMAS), self._presets_turmas):
                Messagebox.show_info("Preset Salvo", "O preset foi salvo com sucesso.", parent=self)
            else:
                Messagebox.show_error("Erro ao Salvar", "Não foi possível salvar o arquivo de presets.", parent=self)

    def _carregar_opcoes_lanche(self) -> Tuple[Set[str], List[str]]:
        """Carrega as opções de lanche a partir de um arquivo JSON."""
        caminho = Path(CAMINHO_JSON_LANCHES)
        padrao = [NOME_LANCHE_PADRAO]
        try:
            opcoes = carregar_json(str(caminho))
            if not isinstance(opcoes, list) or not all(
                isinstance(s, str) for s in opcoes
            ):
                raise TypeError("Conteúdo do JSON de lanches é inválido.")
            return set(opcoes) or set(padrao), sorted(opcoes) or padrao
        except (FileNotFoundError, TypeError) as e:
            logger.warning(
                "Arquivo de lanches não encontrado ou inválido: %s. Usando padrão.", e
            )
            salvar_json(str(caminho), padrao)
            return set(padrao), padrao
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception(
                "Erro ao carregar lanches de '%s': %s", caminho, e)
            return set(), [f"Erro ao carregar {caminho.name}"]

    def _carregar_sessoes_existentes(self) -> List[Tuple]:
        """Busca e formata as sessões existentes para exibição na Treeview."""
        try:
            sessoes = self._fachada.listar_todas_sessoes()
            sessoes_ordenadas = sorted(
                sessoes, key=self._chave_ordenacao_sessao, reverse=True
            )
            return [
                (
                    s.get("id"),
                    s.get("data"),
                    s.get("hora"),
                    capitalizar(s.get("refeicao", "")),
                )
                for s in sessoes_ordenadas
            ]
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Erro ao buscar sessões: %s", e)
            return []

    def _salvar_nova_opcao_lanche(self, selecao: str):
        """Salva uma nova opção de lanche no arquivo JSON se ela for nova."""
        if not selecao or selecao in self._conjunto_opcoes_lanche or "Erro" in selecao:
            return

        normalizado = capitalizar(selecao)
        self._conjunto_opcoes_lanche.add(normalizado)
        try:
            if salvar_json(
                str(CAMINHO_JSON_LANCHES), sorted(
                    list(self._conjunto_opcoes_lanche))
            ):
                self._combobox_lanche["values"] = sorted(
                    list(self._conjunto_opcoes_lanche)
                )
                self._combobox_lanche.set(normalizado)
        except Exception:  # pylint: disable=broad-exception-caught
            Messagebox.show_error(
                "Não foi possível salvar a nova opção de lanche.", parent=self
            )

    def _ao_sincronizar_reservas(self):
        """Inicia o processo de sincronização de reservas em uma thread."""
        self._parente_app.mostrar_barra_progresso(
            True, "Sincronizando reservas...")
        self.update_idletasks()

        thread = Thread(target=self._acao_sincronizacao, daemon=True)
        thread.start()
        self._monitorar_sincronizacao(thread)

    def _acao_sincronizacao(self):
        """Wrapper para a chamada de sincronização, capturando exceções."""
        thread = threading.current_thread()
        setattr(thread, "error", None)
        try:
            self._fachada.sincronizar_do_google_sheets()
        except Exception as e:  # pylint: disable=broad-exception-caught
            setattr(thread, "error", e)

    def _monitorar_sincronizacao(self, thread: Thread):
        """Verifica o status da thread e exibe o resultado ao final."""
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
            Messagebox.show_info(
                "Reservas sincronizadas com sucesso.", parent=self)
            self._atualizar_treeview_sessoes_existentes()

    def _centralizar_janela(self):
        """Centraliza o diálogo em relação à janela principal."""
        self.update_idletasks()
        px, py = self._parente_app.winfo_x(), self._parente_app.winfo_y()
        pw, ph = self._parente_app.winfo_width(), self._parente_app.winfo_height()
        sw, sh = self.winfo_width(), self.winfo_height()
        self.geometry(
            f"+{px + (pw // 2) - (sw // 2)}+{py + (ph // 2) - (sh // 2)}")

    def _definir_checkboxes_turmas(
        self, condicao: Callable[[str, tk.BooleanVar], bool]
    ):
        """Aplica uma condição a todos os checkboxes de turmas."""
        for nome, var, _ in self._dados_checkbox_turmas:
            var.set(condicao(nome, var))

    def _chave_ordenacao_sessao(self, sessao: Dict) -> dt.datetime:
        """Chave de ordenação para as sessões, tratando datas mal formatadas."""
        try:
            return dt.datetime.strptime(
                sessao.get("data", "01/01/1900") + " " +
                sessao.get("hora", "00:00"),
                "%d/%m/%Y %H:%M",
            )
        except ValueError:
            return dt.datetime.min

    def _atualizar_treeview_sessoes_existentes(self):
        """Recarrega os dados na tabela de sessões existentes."""
        if self._treeview_sessoes:
            novos_dados = self._carregar_sessoes_existentes()
            self._treeview_sessoes.construir_dados_tabela(novos_dados)
