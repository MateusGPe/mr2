# gestao_refeitorio/abas/aba_reservas.py

import traceback
from datetime import datetime

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, END, EW, LEFT, NSEW, W, X
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.localization import MessageCatalog
from ttkbootstrap.widgets import DateEntry

from registro.controles.rounded_button import RoundedButton
from registro.dialogos import ReservaDialog
from registro.controles.treeview_simples import TreeviewSimples


class AbaReservas(ttk.Frame):
    def __init__(self, parent, fachada_nucleo):
        super().__init__(parent)
        self.fachada_nucleo = fachada_nucleo
        self.filtro = {}
        self._criar_widgets()
        self._carregar_reservas()

    def _criar_widgets(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Painel superior unificado para filtros e ações
        top_panel = ttk.Frame(self)
        top_panel.grid(row=0, column=0, sticky=EW, pady=(0, 10))
        top_panel.columnconfigure(1, weight=1)

        # Ações à esquerda
        actions_frame = ttk.Frame(top_panel)
        actions_frame.grid(row=0, column=0, sticky=W, padx=(0, 10))
        self.fitro = {}

        RoundedButton(
            actions_frame,
            text="Adicionar Reserva",
            command=self._adicionar_reserva,
        ).pack(side=LEFT, padx=(0, 5))

        self.btn_edit_reserva = RoundedButton(
            actions_frame,
            text="Editar",
            command=self._editar_reserva,
            state="disabled",
        )
        self.btn_edit_reserva.pack(side=LEFT, padx=5)

        self.btn_delete_reserva = RoundedButton(
            actions_frame,
            text="Excluir",
            command=self._deletar_reserva,
            bootstyle="danger",
            state="disabled",
        )
        self.btn_delete_reserva.pack(side=LEFT, padx=5)

        # Filtros à direita
        filter_frame = ttk.Frame(top_panel)
        filter_frame.grid(row=0, column=1, sticky=EW)

        ttk.Label(filter_frame, text="Filtrar por Data:").pack(side=LEFT, padx=(0, 5))
        self.filter_date_entry = DateEntry(
            filter_frame,
            dateformat=r"%d/%m/%Y",
            width=12,
        )
        self.filter_date_entry.pack(side=LEFT, padx=5)
        self.filter_date_entry.bind("<<DateEntrySelected>>", self._filtrar_reservas)
        # Adiciona um botão para limpar o filtro de data
        RoundedButton(
            filter_frame,
            text="Limpar",
            bootstyle="light",
            command=self._limpar_filtro_data,
        ).pack(side=LEFT, padx=(0, 10))

        ttk.Label(filter_frame, text="Filtrar por Turma:").pack(side=LEFT, padx=(15, 5))
        self.filter_turma_combobox = ttk.Combobox(
            filter_frame,
            values=["Todas"] + self._get_grupos_disponiveis(),
            state="readonly",
            width=25,
        )
        self.filter_turma_combobox.set("Todas")
        self.filter_turma_combobox.pack(side=LEFT, padx=5, fill=X, expand=True)
        self.filter_turma_combobox.bind("<<ComboboxSelected>>", self._filtrar_reservas)

        # Tabela de Reservas
        container = ttk.Frame(self)
        container.grid(row=1, column=0, sticky=NSEW)

        self.reservas_coldata = [
            {"text": "ID", "width": 60},
            {"text": "Data", "width": 120},
            {"text": "Aluno", "stretch": True},
            {"text": "Prontuário", "width": 150},
            {"text": "Prato", "width": 120},
            {"text": "Status", "width": 100},
        ]
        self.reservas_table = TreeviewSimples(
            master=container,
            dados_colunas=self.reservas_coldata,
            height=15,
            header_bootstyle="info",
            select_bootstyle="info",
            enable_hover=True,
        )
        self.reservas_table.pack(expand=True, fill=BOTH)
        self.reservas_table.view.bind("<<TreeviewSelect>>", self._on_reserva_select)

    def _limpar_filtro_data(self):
        self.filter_date_entry.entry.delete(0, END)
        self._filtrar_reservas(cmp_filtros=True)

    def _get_dados_linha_selecionada(self):
        """Retorna os dados da linha selecionada na tabela."""
        return self.reservas_table.obter_linha_selecionada()

    def _on_reserva_select(self, _=None):
        is_selected = bool(self._get_dados_linha_selecionada())
        self.btn_edit_reserva.configure(state="normal" if is_selected else "disabled")
        self.btn_delete_reserva.configure(state="normal" if is_selected else "disabled")

    def _get_grupos_disponiveis(self):
        try:
            return sorted(
                [g["nome"] for g in self.fachada_nucleo.listar_todos_os_grupos()]
            )
        except Exception:
            return []

    def _filtrar_reservas(self, event=None, cmp_filtros=False):
        filtro_ant = self.filtro
        self.filtro = {}
        data_filtro = self.filter_date_entry.entry.get()

        if data_filtro:
            self.filtro["data"] = data_filtro

        turma_filtro = self.filter_turma_combobox.get()

        # Converte "Todas" para None para a chamada da fachada
        if turma_filtro == "Todas":
            turma_filtro = None

        if turma_filtro:
            self.filtro["grupos"] = [
                turma_filtro,
            ]

        if cmp_filtros and self.filtro == filtro_ant:
            return

        try:
            reservas = self.fachada_nucleo.listar_reservas(filtros=self.filtro)
            dados = [
                (
                    r["id"],
                    r["data"],
                    r["nome_estudante"],
                    r["prontuario_estudante"],
                    r["prato"],
                    "Cancelada" if r["cancelada"] else "Ativa",
                )
                for r in reservas
            ]
            self.reservas_table.construir_dados_tabela(dados)
        except Exception:
            Messagebox.show_error(
                "Erro ao carregar reservas. Verifique o console.",
                "Erro",
            )
            traceback.print_exc()
        self._on_reserva_select()

    def _carregar_reservas(self):
        # Define a data atual como padrão para o filtro de data ao carregar
        date_str = datetime.now().strftime(r"%d/%m/%Y")
        self.filter_date_entry.entry.delete(0, END)
        self.filter_date_entry.entry.insert(0, date_str)

        self._filtrar_reservas()

    def _adicionar_reserva(self):
        dialog = ReservaDialog(self, self.fachada_nucleo)
        if dialog.result:
            self._filtrar_reservas()

    def _get_reserva_selecionada_id(self):
        selecionado = self._get_dados_linha_selecionada()
        return selecionado[0] if selecionado else None

    def _editar_reserva(self):
        reserva_id = self._get_reserva_selecionada_id()
        if not reserva_id:
            return
        dialog = ReservaDialog(self, self.fachada_nucleo, reserva_id=reserva_id)
        if dialog.result:
            self._filtrar_reservas()

    def _deletar_reserva(self):
        reserva_id = self._get_reserva_selecionada_id()
        if not reserva_id:
            return

        confirmado = Messagebox.okcancel(
            f"Deseja excluir a reserva com ID {reserva_id}?",
            "Confirmar Exclusão",
        ) == MessageCatalog.translate("OK")
        if confirmado:
            try:
                self.fachada_nucleo.deletar_reserva(reserva_id)
                self._filtrar_reservas()
            except Exception as e:
                Messagebox.show_error(
                    f"Erro ao excluir reserva: {e}",
                    "Erro",
                )
                traceback.print_exc()
