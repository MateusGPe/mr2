# gestao_refeitorio/abas/aba_reservas.py

import traceback

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, EW, LEFT, NSEW
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.tableview import Tableview

from registro.dialogos import ReservaDialog


class AbaReservas(ttk.Frame):
    def __init__(self, parent, fachada_nucleo):
        super().__init__(parent)
        self.fachada_nucleo = fachada_nucleo
        self._criar_widgets()
        self._carregar_reservas()

    def _criar_widgets(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, padding=(10, 10, 10, 0))
        toolbar.grid(row=0, column=0, sticky=EW)

        ttk.Button(
            toolbar,
            text="Adicionar",
            command=self._adicionar_reserva,
            bootstyle="success",
        ).pack(side=LEFT, padx=5)

        self.btn_edit_reserva = ttk.Button(
            toolbar, text="Editar", command=self._editar_reserva, state="disabled"
        )
        self.btn_edit_reserva.pack(side=LEFT, padx=5)

        self.btn_delete_reserva = ttk.Button(
            toolbar,
            text="Excluir",
            command=self._deletar_reserva,
            bootstyle="danger-outline",
            state="disabled",
        )
        self.btn_delete_reserva.pack(side=LEFT, padx=5)

        container = ttk.Frame(self, padding=(10, 0, 10, 10))
        container.grid(row=1, column=0, sticky=NSEW)

        self.reservas_coldata = [
            {"text": "ID", "width": 60},
            {"text": "Data", "width": 120},
            {"text": "Aluno", "stretch": True},
            {"text": "Prontuário", "width": 150},
            {"text": "Prato", "width": 120},
            {"text": "Status", "width": 100},
        ]
        self.reservas_table = Tableview(
            master=container,
            coldata=self.reservas_coldata,
            paginated=True,
            bootstyle="info",
        )
        self.reservas_table.pack(expand=True, fill=BOTH)
        self.reservas_table.view.bind("<<TreeviewSelect>>", self._on_reserva_select)

    def _get_dados_linha_selecionada(self):
        """Retorna os dados da linha selecionada na tabela."""
        selecao = self.reservas_table.view.selection()
        if not selecao:
            return None
        return self.reservas_table.view.item(selecao[0], "values")

    def _on_reserva_select(self, _=None):
        is_selected = bool(self._get_dados_linha_selecionada())
        self.btn_edit_reserva.config(state="normal" if is_selected else "disabled")
        self.btn_delete_reserva.config(state="normal" if is_selected else "disabled")

    def _carregar_reservas(self):
        try:
            reservas = self.fachada_nucleo.listar_reservas()
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
            self.reservas_table.build_table_data(self.reservas_coldata, dados)
        except Exception:
            Messagebox.show_error(
                "Erro ao carregar reservas. Verifique o console.", "Erro"
            )
            traceback.print_exc()
        self._on_reserva_select()

    def _adicionar_reserva(self):
        dialog = ReservaDialog(self, self.fachada_nucleo)
        if dialog.result:
            self._carregar_reservas()

    def _get_reserva_selecionada_id(self):
        selecionado = self._get_dados_linha_selecionada()
        return selecionado[0] if selecionado else None

    def _editar_reserva(self):
        reserva_id = self._get_reserva_selecionada_id()
        if not reserva_id:
            return
        dialog = ReservaDialog(self, self.fachada_nucleo, reserva_id=reserva_id)
        if dialog.result:
            self._carregar_reservas()

    def _deletar_reserva(self):
        reserva_id = self._get_reserva_selecionada_id()
        if not reserva_id:
            return

        confirmado = Messagebox.okcancel(
            f"Deseja excluir a reserva com ID {reserva_id}?", "Confirmar Exclusão"
        )
        if confirmado:
            try:
                self.fachada_nucleo.deletar_reserva(reserva_id)
                self._carregar_reservas()
            except Exception:
                Messagebox.show_error(
                    "Erro ao excluir reserva. Verifique o console.", "Erro"
                )
                traceback.print_exc()
