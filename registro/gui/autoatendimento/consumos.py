# ----------------------------------------------------------------------------
# Arquivo: registro/gui/autoatendimento/consumos.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Painel AbaConsumos para gestão completa (CRUD) de registros de consumo da sessão.
Permite adição manual, busca instantânea por múltiplos campos, edição, estorno e exportação.
"""

import logging
import tkinter as tk
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

import ttkbootstrap as ttk
from ttkbootstrap.constants import CENTER, LEFT
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.localization.msgcat import MessageCatalog

from registro.gui.autoatendimento.dialogos import (
    DialogoDetalhesConsumo,
    DialogoEditarConsumo,
    DialogoNovoConsumo,
)
from registro.gui.comum.controles.treeview_simples import TreeviewSimples

if TYPE_CHECKING:
    from registro.nucleo.facade import FachadaRegistro

logger = logging.getLogger(__name__)


class AbaConsumos(ttk.Frame):
    """
    Painel de Gestão Completa (CRUD) dos registros de consumo da sessão:
    - Create: Adicionar novo consumo manual (com ou sem reserva)
    - Read: Pesquisa em tempo real, visualização tabular ordenada e detalhes
    - Update: Edição de horário e prato
    - Delete: Exclusão com confirmação segura e reversão no banco
    """

    ID_COLUNA_ACAO = "coluna_acao"
    TEXTO_COLUNA_ACAO = "❌"

    def __init__(
        self,
        master: tk.Widget,
        fachada: "FachadaRegistro",
        id_sessao: Optional[int],
        voltar_callback: Optional[Callable[[], None]] = None,
        abrir_controles_callback: Optional[Callable[..., None]] = None,
        navegar_callback: Optional[Callable[[str], None]] = None,
        notificar_mudanca_callback: Optional[Callable[[], None]] = None,
    ):
        super().__init__(master, padding=(14, 12))
        self.fachada = fachada
        self.id_sessao = id_sessao
        self.voltar_callback = voltar_callback
        self.abrir_controles_callback = abrir_controles_callback
        self.navegar_callback = navegar_callback
        self.notificar_mudanca_callback = notificar_mudanca_callback

        self._consumos_raw: List[Dict[str, Any]] = []
        self._mapa_iid_para_consumo: Dict[str, Dict[str, Any]] = {}

        self.pack_propagate(False)
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        self._construir_interface()
        self.carregar_consumos()

    def _construir_interface(self):
        """Constrói a barra de ferramentas CRUD, campo de busca e a tabela de registros."""
        # --- Linha 0: Barra Superior de Navegação ---
        frame_topo = ttk.Frame(self)
        frame_topo.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        frame_topo.columnconfigure(1, weight=1)

        frame_nav_esq = ttk.Frame(frame_topo)
        frame_nav_esq.grid(row=0, column=0, sticky="w")

        if self.voltar_callback:
            ttk.Button(
                frame_nav_esq,
                text=" ⬅ Voltar ao Totem ",
                command=self.voltar_callback,
                bootstyle="primary",
                padding=(10, 6),
            ).pack(side=LEFT, padx=(0, 6))

        if self.navegar_callback:
            ttk.Button(
                frame_nav_esq,
                text=" 📊 Ver Dashboard & Estatísticas ",
                command=lambda: self.navegar_callback("dashboard"),
                bootstyle="info-outline",
                padding=(10, 6),
            ).pack(side=LEFT)

        frame_titulo = ttk.Frame(frame_topo)
        frame_titulo.grid(row=0, column=1, sticky="ew")

        ttk.Label(
            frame_titulo,
            text="📋 Gestão de Registros de Consumo",
            font=("Segoe UI", 18, "bold"),
            anchor="center",
        ).pack(side=LEFT, expand=True)

        self.lbl_badge_total = ttk.Label(
            frame_titulo,
            text="0 registros",
            font=("Segoe UI", 9, "bold"),
            bootstyle="secondary",
        )
        self.lbl_badge_total.pack(side=LEFT, padx=(4, 0))

        frame_nav_dir = ttk.Frame(frame_topo)
        frame_nav_dir.grid(row=0, column=2, sticky="e")

        ttk.Button(
            frame_nav_dir,
            text=" 🔄 Atualizar ",
            command=self.carregar_consumos,
            bootstyle="secondary-outline",
            padding=(8, 6),
        ).pack(side=LEFT, padx=(0, 6))

        if self.abrir_controles_callback:
            btn_ctrl = ttk.Button(
                frame_nav_dir,
                text=" ⚙️ Controles ",
                bootstyle="secondary",
                padding=(8, 6),
            )
            btn_ctrl.config(
                command=lambda b=btn_ctrl: self.abrir_controles_callback(widget=b)
            )
            btn_ctrl.pack(side=LEFT)

        # --- Linha 1: Barra de Ações CRUD e Filtro de Pesquisa ---
        frame_toolbar = ttk.Frame(self)
        frame_toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        frame_toolbar.columnconfigure(1, weight=1)

        # Botões de Ação CRUD
        frame_acoes = ttk.Frame(frame_toolbar)
        frame_acoes.grid(row=0, column=0, sticky="w")

        ttk.Button(
            frame_acoes,
            text=" ➕ Novo Registro ",
            command=self.novo_registro,
            bootstyle="success",
            padding=(10, 6),
        ).pack(side=LEFT, padx=(0, 6))

        ttk.Button(
            frame_acoes,
            text=" ✏️ Editar ",
            command=self.editar_registro,
            bootstyle="primary-outline",
            padding=(8, 6),
        ).pack(side=LEFT, padx=(0, 6))

        ttk.Button(
            frame_acoes,
            text=" 🗑️ Excluir ",
            command=self.excluir_registro,
            bootstyle="danger-outline",
            padding=(8, 6),
        ).pack(side=LEFT, padx=(0, 6))

        ttk.Button(
            frame_acoes,
            text=" 🔍 Detalhes ",
            command=self.exibir_detalhes,
            bootstyle="info-outline",
            padding=(8, 6),
        ).pack(side=LEFT, padx=(0, 6))

        ttk.Button(
            frame_acoes,
            text=" 📥 Exportar XLSX ",
            command=self.exportar_xlsx,
            bootstyle="secondary-outline",
            padding=(8, 6),
        ).pack(side=LEFT)

        # Campo de Pesquisa em Tempo Real
        frame_busca = ttk.Frame(frame_toolbar)
        frame_busca.grid(row=0, column=1, sticky="e")

        ttk.Label(frame_busca, text="🔍", font=("Segoe UI", 11)).pack(
            side=LEFT, padx=(0, 4)
        )
        self.var_busca = tk.StringVar()
        self.var_busca.trace_add("write", lambda *_: self._ao_digitar_busca())
        self.entry_busca = ttk.Entry(
            frame_busca,
            textvariable=self.var_busca,
            width=28,
            font=("Segoe UI", 9),
        )
        self.entry_busca.pack(side=LEFT, padx=(0, 6))

        self.var_filtro_tipo = tk.StringVar(value="Todos")
        combo_filtro = ttk.Combobox(
            frame_busca,
            textvariable=self.var_filtro_tipo,
            values=["Todos", "Com Reserva", "Sem Reserva"],
            state="readonly",
            width=14,
            font=("Segoe UI", 9),
        )
        combo_filtro.pack(side=LEFT)
        combo_filtro.bind("<<ComboboxSelected>>", lambda _: self._ao_digitar_busca())

        # --- Linha 2: Tabela de Registros de Consumo (Treeview) ---
        colunas = [
            {"text": "🆔 Prontuário", "iid": "pront", "width": 110, "minwidth": 80},
            {"text": "👤 Nome", "iid": "nome", "width": 280, "stretch": True, "minwidth": 150},
            {"text": "👥 Turma", "iid": "turma", "width": 170, "minwidth": 100},
            {"text": "⏱️ Hora", "iid": "hora", "width": 90, "anchor": CENTER, "minwidth": 70},
            {"text": "🍽️ Prato / Status", "iid": "prato", "width": 140, "minwidth": 90},
            {
                "text": self.TEXTO_COLUNA_ACAO,
                "iid": self.ID_COLUNA_ACAO,
                "width": 45,
                "anchor": CENTER,
                "stretch": False,
            },
        ]
        self.tree = TreeviewSimples(
            self,
            dados_colunas=colunas,
            height=20,
            enable_hover=True,
            enable_sorting=True,
        )
        self.tree.frame.grid(row=2, column=0, sticky="nsew")

        # Vinculações de Eventos na Tabela
        self.tree.view.bind("<Button-1>", self._ao_clicar_tabela)
        self.tree.view.bind("<Double-1>", self._ao_duplo_clique)
        self.tree.view.bind("<Delete>", lambda _: self.excluir_registro())
        self.tree.view.bind("<BackSpace>", lambda _: self.excluir_registro())
        self.tree.view.bind("<Button-3>", self._ao_menu_contexto)

    def definir_sessao(self, id_sessao: Optional[int]):
        """Atualiza a sessão ativa e recarrega a tabela de consumos."""
        self.id_sessao = id_sessao
        self.carregar_consumos()

    def carregar_consumos(self):
        """Carrega a lista completa de estudantes que consumiram na sessão ativa."""
        if not self.id_sessao or not self.fachada or not self.fachada.id_sessao_ativa:
            self._consumos_raw = []
            self._mapa_iid_para_consumo.clear()
            self.tree.construir_dados_tabela([])
            self.lbl_badge_total.config(text="0 registros")
            return

        try:
            consumidos = self.fachada.obter_estudantes_para_sessao(
                consumido=True, pular_grupos=True
            )
            consumidos.sort(
                key=lambda x: str(x.get("hora_consumo", "")), reverse=True
            )
            self._consumos_raw = consumidos
            self._aplicar_filtro_e_renderizar()
        except Exception as e:
            logger.error("Erro ao carregar consumos no painel CRUD: %s", e)

    def _aplicar_filtro_e_renderizar(self):
        """Filtra a lista de consumos em memória e atualiza as linhas da Treeview."""
        termo = self.var_busca.get().strip().lower()
        filtro_tipo = self.var_filtro_tipo.get()

        self._mapa_iid_para_consumo.clear()
        self.tree.deletar_linhas()

        total_filtrados = 0
        for c in self._consumos_raw:
            pront = str(c.get("pront", ""))
            nome = str(c.get("nome", ""))
            turma = str(c.get("turma", ""))
            hora = str(c.get("hora_consumo", ""))
            prato = str(c.get("prato") or "Sem Reserva")

            if filtro_tipo == "Com Reserva" and (
                prato == "Sem Reserva" or c.get("status") == "Sem Reserva"
            ):
                continue
            if filtro_tipo == "Sem Reserva" and not (
                prato == "Sem Reserva" or c.get("status") == "Sem Reserva"
            ):
                continue

            if termo:
                if (
                    termo not in pront.lower()
                    and termo not in nome.lower()
                    and termo not in turma.lower()
                    and termo not in prato.lower()
                ):
                    continue

            valores = (pront, nome, turma, hora, prato, self.TEXTO_COLUNA_ACAO)
            iid = self.tree.view.insert("", "end", values=valores)
            self._mapa_iid_para_consumo[iid] = c
            total_filtrados += 1

        self.tree.apply_zebra_striping()
        total_total = len(self._consumos_raw)
        if total_filtrados == total_total:
            self.lbl_badge_total.config(text=f"{total_total} registros")
        else:
            self.lbl_badge_total.config(
                text=f"{total_filtrados} de {total_total} registros"
            )

    def _ao_digitar_busca(self):
        self._aplicar_filtro_e_renderizar()

    def adicionar_consumo(self, dados_estudante: Tuple[str, ...]):
        """Adiciona imediatamente uma nova linha no topo da tabela de consumos."""
        if len(dados_estudante) >= 5:
            valores = tuple(dados_estudante[:5]) + (self.TEXTO_COLUNA_ACAO,)
        else:
            valores = dados_estudante
        iid = self.tree.view.insert("", 0, values=valores)
        self.tree.apply_zebra_striping()

        novo_dict = {
            "pront": dados_estudante[0] if len(dados_estudante) > 0 else "",
            "nome": dados_estudante[1] if len(dados_estudante) > 1 else "",
            "turma": dados_estudante[2] if len(dados_estudante) > 2 else "",
            "hora_consumo": dados_estudante[3] if len(dados_estudante) > 3 else "",
            "prato": dados_estudante[4] if len(dados_estudante) > 4 else "Almoço",
        }
        self._consumos_raw.insert(0, novo_dict)
        self._mapa_iid_para_consumo[iid] = novo_dict
        self.lbl_badge_total.config(text=f"{len(self._consumos_raw)} registros")

    # --- Operações CRUD ---

    def novo_registro(self):
        """[Create] Abre o diálogo para registrar um novo consumo manualmente."""
        if not self.id_sessao or not self.fachada or not self.fachada.id_sessao_ativa:
            Messagebox.show_warning(
                "Aviso", "Inicie ou selecione uma sessão antes de registrar.", parent=self
            )
            return

        def _ao_sucesso(_res):
            self.carregar_consumos()
            self._notificar_mudanca()

        DialogoNovoConsumo(self, self.fachada, on_sucesso=_ao_sucesso)

    def editar_registro(self, iid: Optional[str] = None):
        """[Update] Abre o diálogo de edição para o registro selecionado."""
        alvo_iid = iid or self.tree.obter_iid_selecionado()
        if not alvo_iid:
            Messagebox.show_warning(
                "Atenção", "Selecione um registro na tabela para editar.", parent=self
            )
            return

        dados = self._obter_dados_de_iid(alvo_iid)
        if not dados:
            return

        id_consumo = dados.get("id_consumo")
        if not id_consumo:
            try:
                c_db = self.fachada.repo_consumo.por_prontuario_e_sessao(
                    dados["pront"], self.id_sessao
                )
                if c_db:
                    id_consumo = c_db.id
            except Exception as e:
                logger.error("Erro ao buscar id_consumo: %s", e)

        if not id_consumo:
            Messagebox.show_error(
                "Erro", "Não foi possível localizar o ID do consumo para edição.", parent=self
            )
            return

        def _ao_sucesso(_res):
            self.carregar_consumos()
            self._notificar_mudanca()

        DialogoEditarConsumo(
            self,
            self.fachada,
            id_consumo=id_consumo,
            dados_consumo=dados,
            on_sucesso=_ao_sucesso,
        )

    def excluir_registro(self, iid: Optional[str] = None):
        """[Delete] Solicita confirmação e remove o registro de consumo."""
        alvo_iid = iid or self.tree.obter_iid_selecionado()
        if not alvo_iid:
            Messagebox.show_warning(
                "Atenção", "Selecione um registro na tabela para excluir.", parent=self
            )
            return

        dados = self._obter_dados_de_iid(alvo_iid)
        if not dados:
            return

        pront = dados.get("pront", "")
        nome = dados.get("nome", "")

        msg = f"Deseja realmente remover o registro de consumo para:\n{pront} - {nome}?"
        resp = Messagebox.yesno(
            "Confirmar Remoção de Consumo", msg, parent=self
        )
        if resp == MessageCatalog.translate("Yes"):
            try:
                id_consumo = dados.get("id_consumo")
                if id_consumo:
                    self.fachada.desfazer_consumo(id_consumo)
                else:
                    self.fachada.desfazer_consumo_por_prontuario(pront)

                logger.info("Consumo de %s removido com sucesso.", pront)
                self.carregar_consumos()
                self._notificar_mudanca()
                Messagebox.show_info(
                    "Removido", f"Registro de {nome} removido com sucesso.", parent=self
                )
            except Exception as e:
                logger.exception("Erro ao excluir consumo: %s", e)
                Messagebox.show_error(
                    "Erro ao Excluir", f"Não foi possível remover:\n{e}", parent=self
                )

    def exibir_detalhes(self, iid: Optional[str] = None):
        """[Read] Exibe os detalhes completos do atendimento selecionado."""
        alvo_iid = iid or self.tree.obter_iid_selecionado()
        if not alvo_iid:
            Messagebox.show_warning(
                "Atenção", "Selecione um registro para ver os detalhes.", parent=self
            )
            return

        dados = self._obter_dados_de_iid(alvo_iid)
        if not dados:
            return

        DialogoDetalhesConsumo(
            self,
            dados_consumo=dados,
            on_editar=lambda: self.editar_registro(alvo_iid),
            on_excluir=lambda: self.excluir_registro(alvo_iid),
        )

    def exportar_xlsx(self):
        """Exporta os registros de consumo atuais para XLSX."""
        if not self.id_sessao or not self.fachada:
            Messagebox.show_warning("Aviso", "Nenhuma sessão ativa para exportar.", parent=self)
            return

        try:
            caminho = self.fachada.exportar_sessao_para_xlsx(self.id_sessao)
            Messagebox.show_info(
                "Exportação Concluída",
                f"Consumos exportados com sucesso para:\n{caminho}",
                parent=self,
            )
        except Exception as e:
            logger.exception("Erro ao exportar consumos: %s", e)
            Messagebox.show_error("Erro na Exportação", f"Falha ao exportar:\n{e}", parent=self)

    # --- Handlers de Eventos ---

    def _obter_dados_de_iid(self, iid: str) -> Optional[Dict[str, Any]]:
        """Recupera o dicionário de dados associado a um IID da Treeview."""
        if iid in self._mapa_iid_para_consumo:
            return dict(self._mapa_iid_para_consumo[iid])

        vals = self.tree.obter_valores_linha(iid)
        if vals and len(vals) >= 5:
            return {
                "pront": vals[0],
                "nome": vals[1],
                "turma": vals[2],
                "hora_consumo": vals[3],
                "prato": vals[4],
            }
        return None

    def _ao_clicar_tabela(self, event: tk.Event):
        """Detecta se a coluna de ação ❌ foi clicada diretamente."""
        iid, id_col = self.tree.identificar_celula_clicada(event)
        if iid and id_col == self.ID_COLUNA_ACAO:
            self.excluir_registro(iid)

    def _ao_duplo_clique(self, event: tk.Event):
        """Abre os detalhes/edição ao dar duplo clique em uma linha."""
        iid, id_col = self.tree.identificar_celula_clicada(event)
        if iid and id_col != self.ID_COLUNA_ACAO:
            self.exibir_detalhes(iid)

    def _ao_menu_contexto(self, event: tk.Event):
        """Exibe menu de contexto com clique com o botão direito na linha."""
        iid = self.tree.view.identify_row(event.y)
        if not iid:
            return

        self.tree.view.selection_set(iid)
        menu = tk.Menu(self, tearoff=False, font=("Segoe UI", 9))
        menu.add_command(
            label="🔍  Ver Detalhes do Registro",
            command=lambda: self.exibir_detalhes(iid),
        )
        menu.add_command(
            label="✏️  Editar Horário / Prato",
            command=lambda: self.editar_registro(iid),
        )
        menu.add_separator()
        menu.add_command(
            label="🗑️  Excluir Registro",
            command=lambda: self.excluir_registro(iid),
        )
        menu.tk_popup(event.x_root, event.y_root)

    def _notificar_mudanca(self):
        """Notifica o App e demais componentes de que houve alteração nos consumos."""
        if self.notificar_mudanca_callback:
            try:
                self.notificar_mudanca_callback()
            except Exception as e:
                logger.error("Erro no callback de notificação de mudança: %s", e)
