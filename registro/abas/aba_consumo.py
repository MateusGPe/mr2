# gestao_refeitorio/abas/aba_consumo.py

import tkinter as tk
import traceback

import ttkbootstrap as ttk
from ttkbootstrap.constants import HORIZONTAL, EW, LEFT, X, NSEW
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.tableview import Tableview

from registro.dialogos import SessionDialog
from registro.nucleo.exceptions import ErroSessaoNaoAtiva


class AbaConsumo(ttk.Frame):
    def __init__(self, parent, fachada_nucleo):
        super().__init__(parent)
        self.fachada_nucleo = fachada_nucleo
        self.todos_elegiveis = []

        self.restantes_label: ttk.Label
        self.registrados_label: ttk.Label
        self.search_consumo: ttk.Entry
        self.search_consumo_var: tk.StringVar
        self.btn_registrar_consumo: ttk.Button
        self.elegiveis_table: Tableview
        self.registrados_table: Tableview

        self.elegiveis_coldata = [
            {"text": "Nome", "stretch": True},
            {"text": "Prontuário", "width": 120},
            {"text": "Status", "width": 150},
        ]
        self.registrados_coldata = [
            {"text": "Nome", "stretch": True},
            {"text": "Hora", "width": 80},
            {"text": "Status", "width": 150},
            {"text": "ID", "stretch": False, "width": 0},
        ]

        self._criar_widgets()
        self._atualizar_tela_consumo()

    def _criar_widgets(self):
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        self.consumo_status_label = ttk.Label(
            self, text="", font=("Helvetica", 12, "bold"), padding=(10, 5, 10, 5)
        )
        self.consumo_status_label.grid(row=0, column=0, sticky=EW)

        paned = ttk.PanedWindow(self, orient=HORIZONTAL)
        paned.grid(row=1, column=0, sticky=NSEW, padx=10, pady=(0, 10))

        left_panel = self._criar_painel_esquerdo(paned)
        paned.add(left_panel, weight=3)

        right_panel = self._criar_painel_direito(paned)
        paned.add(right_panel, weight=2)

    def _criar_painel_esquerdo(self, parent):
        panel = ttk.Frame(parent, padding=5)
        panel.rowconfigure(1, weight=1)
        panel.columnconfigure(0, weight=1)

        toolbar = ttk.Frame(panel)
        toolbar.grid(row=0, column=0, sticky=EW, pady=(0, 5))

        self.search_consumo_var = tk.StringVar()
        self.search_consumo_var.trace_add("write", lambda *_: self._filtrar_elegiveis())
        self.search_consumo: ttk.Entry = ttk.Entry(
            toolbar, textvariable=self.search_consumo_var
        )
        self.search_consumo.pack(side=LEFT, fill=X, expand=True)

        self.btn_registrar_consumo = ttk.Button(
            toolbar, text="Registrar", state="disabled", command=self._registrar_consumo
        )
        self.btn_registrar_consumo.pack(side=LEFT, padx=5)

        ttk.Button(
            toolbar,
            text="⚙️ Sessão",
            command=self._abrir_dialogo_sessao,
            bootstyle="info-outline",
        ).pack(side=tk.RIGHT)

        self.elegiveis_table = Tableview(
            panel, coldata=self.elegiveis_coldata, bootstyle="primary"
        )
        self.elegiveis_table.grid(row=1, column=0, sticky=NSEW)
        self.elegiveis_table.view.bind("<<TreeviewSelect>>", self._on_elegivel_select)
        return panel

    def _criar_painel_direito(self, parent):
        panel = ttk.Frame(parent, padding=5)
        panel.rowconfigure(2, weight=1)
        panel.columnconfigure(0, weight=1)

        counters = ttk.Frame(panel)
        counters.grid(row=0, column=0, sticky=EW)

        self.registrados_label = ttk.Label(
            counters, text="Registrados: 0", bootstyle="info"
        )
        self.registrados_label.pack(side=LEFT, fill=X, expand=True)

        self.restantes_label = ttk.Label(
            counters, text="Restantes: 0", bootstyle="success"
        )
        self.restantes_label.pack(side=LEFT, fill=X, expand=True)

        ttk.Button(
            panel,
            text="Desfazer Registro",
            bootstyle="warning-outline",
            command=self._desfazer_consumo,
        ).grid(row=1, column=0, sticky=EW, pady=5)

        self.registrados_table = Tableview(
            panel, coldata=self.registrados_coldata, bootstyle="info"
        )
        self.registrados_table.grid(row=2, column=0, sticky=NSEW)
        return panel

    def _get_dados_linha_selecionada(self, tableview: Tableview):
        """Retorna os dados da linha selecionada em uma Tableview específica."""
        selecao = tableview.view.selection()
        if not selecao:
            return None
        return tableview.view.item(selecao[0], "values")

    def _abrir_dialogo_sessao(self):
        dialog = SessionDialog(self, self.fachada_nucleo)
        if dialog.result:
            self._atualizar_tela_consumo()

    def _atualizar_tela_consumo(self):
        try:
            if self.fachada_nucleo.id_sessao_ativa is None:
                self.consumo_status_label.config(
                    text="Nenhuma sessão ativa. Clique em '⚙️ Sessão' para começar.",
                    bootstyle="warning",
                )
                self.todos_elegiveis, registrados = [], []
            else:
                detalhes = self.fachada_nucleo.obter_detalhes_sessao_ativa()
                self.consumo_status_label.config(
                    text=f"Sessão Ativa (ID {detalhes['id']}): "
                    f"{detalhes['refeicao'].capitalize()} em {detalhes['data']}",
                    bootstyle="success",
                )
                self.todos_elegiveis = self.fachada_nucleo.obter_estudantes_para_sessao(
                    consumido=False
                )
                registrados = self.fachada_nucleo.obter_estudantes_para_sessao(
                    consumido=True
                )
            self._filtrar_elegiveis()
            dados_reg = [
                (r["nome"], r["hora_registro"], r["status"], r["id_consumo"])
                for r in registrados
            ]
            self.registrados_table.build_table_data(self.registrados_coldata, dados_reg)

            total = len(self.todos_elegiveis) + len(registrados)
            self.registrados_label.config(text=f"Registrados: {len(registrados)}")
            self.restantes_label.config(
                text=f"Restantes: {len(self.todos_elegiveis)} de {total}"
            )
        except ErroSessaoNaoAtiva:
            self.fachada_nucleo.id_sessao_ativa = None
            self._atualizar_tela_consumo()
        except Exception:
            Messagebox.show_error(
                "Erro ao atualizar consumo. Verifique o console.", "Erro"
            )
            traceback.print_exc()

    def _filtrar_elegiveis(self):
        termo = self.search_consumo_var.get().lower()
        if not termo:
            filtrados = self.todos_elegiveis
        else:
            filtrados = [
                e
                for e in self.todos_elegiveis
                if termo in e["nome"].lower() or termo in e["pront"].lower()
            ]
        dados = [(e["nome"], e["pront"], e["status"]) for e in filtrados]
        self.elegiveis_table.build_table_data(self.elegiveis_coldata, dados)
        self._on_elegivel_select(None)
        self.search_consumo.focus_set()

    def _on_elegivel_select(self, _=None):
        is_selected = bool(self._get_dados_linha_selecionada(self.elegiveis_table))
        self.btn_registrar_consumo.config(state="normal" if is_selected else "disabled")

    def _registrar_consumo(self):
        selecionado = self._get_dados_linha_selecionada(self.elegiveis_table)
        if not selecionado:
            return
        try:
            prontuario = selecionado[1]
            resultado = self.fachada_nucleo.registrar_consumo(prontuario)
            if not resultado["autorizado"]:
                Messagebox.show_warning(
                    f"Não autorizado: {resultado['motivo']}", "Acesso Negado"
                )
            self.search_consumo_var.set("")
            self._atualizar_tela_consumo()
        except ErroSessaoNaoAtiva:
            Messagebox.show_warning("Sessão expirada. Inicie uma nova.", "Aviso")
            self._atualizar_tela_consumo()
        except Exception:
            Messagebox.show_error("Erro ao registrar. Verifique o console.", "Erro")
            traceback.print_exc()

    def _desfazer_consumo(self):
        selecionado = self._get_dados_linha_selecionada(self.registrados_table)
        if not selecionado:
            Messagebox.show_warning("Selecione um registro para desfazer.", "Aviso")
            return
        try:
            id_consumo = selecionado[3]
            self.fachada_nucleo.desfazer_consumo(id_consumo)
            self._atualizar_tela_consumo()
        except Exception:
            Messagebox.show_error("Erro ao desfazer. Verifique o console.", "Erro")
            traceback.print_exc()
