# ----------------------------------------------------------------------------
# File: registro/view/status_registered_panel.py (Painel de Status/Registrados)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>
"""
Define o painel direito da interface, exibindo contadores e a lista
de alunos já registrados, com funcionalidade de remoção.
"""
import logging
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import CENTER, PRIMARY, WARNING  # Importa constantes usadas

from registro.view.constants import UI_TEXTS
from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.exceptions import ErroSessaoNaoAtiva
from registro.view.simple_treeview import SimpleTreeView

# Evita importação circular para type hinting
if TYPE_CHECKING:
    from registro.view.registration_app import RegistrationApp

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# Painel de Status e Registrados (Direita)
# ----------------------------------------------------------------------------


class StatusRegisteredPanel(ttk.Frame):
    """
    Painel exibindo contadores (Registrados/Restantes) e a tabela de
    alunos já registrados na sessão atual, com opção de remoção.
    """

    ACTION_COLUMN_ID = "action_col"  # ID interno para a coluna de ação
    ACTION_COLUMN_TEXT = UI_TEXTS.get(
        "col_action", "❌"
    )  # Texto/ícone do cabeçalho da coluna

    def __init__(
        self,
        master: tk.Widget,
        app: "RegistrationApp",  # Usa type hint
        fachada_nucleo: "FachadaRegistro",
    ):
        """
        Inicializa o painel de Status/Registrados.

        Args:
            master: O widget pai (geralmente o PanedWindow).
            app: Referência à instância principal da RegistrationApp.
            fachada_nucleo: Instância da FachadaRegistro para acesso aos dados.
        """
        super().__init__(master, padding=(10, 10, 10, 0))  # Padding ajustado
        self._app = app
        self._fachada: FachadaRegistro = fachada_nucleo

        # --- Atributos de Widgets Internos ---
        self._registered_count_label: Optional[ttk.Label] = None
        self._remaining_count_label: Optional[ttk.Label] = None
        self._registered_students_table: Optional[SimpleTreeView] = None

        # Configuração do Grid interno
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._registered_cols_definition: List[Dict[str, Any]] = []

        self._create_registered_table()
        self._create_counters_area()

        if self._registered_students_table:
            self._registered_students_table.view.bind(
                "<Button-1>", self._on_registered_table_click
            )
            self._registered_students_table.view.bind(
                "<Delete>", self._on_table_delete_key
            )
            self._registered_students_table.view.bind(
                "<BackSpace>", self._on_table_delete_key
            )

    def _get_registered_cols_definition(self) -> List[Dict[str, Any]]:
        """Retorna a definição das colunas para a tabela de registrados."""
        return [
            {
                "text": UI_TEXTS.get("col_prontuario", "🆔 Pront."),
                "stretch": False,
                "width": 100,
                "iid": "pront",
                "minwidth": 80,
            },
            {
                "text": UI_TEXTS.get("col_nome", "✍️ Nome"),
                "stretch": True,
                "iid": "nome",
                "minwidth": 150,
            },
            {
                "text": UI_TEXTS.get("col_turma", "👥 Turma"),
                "stretch": False,
                "width": 150,
                "iid": "turma",
                "minwidth": 100,
            },
            {
                "text": UI_TEXTS.get("col_hora", "⏱️ Hora"),
                "stretch": False,
                "width": 70,
                "anchor": CENTER,
                "iid": "hora",
                "minwidth": 60,
            },
            {
                "text": UI_TEXTS.get("col_prato_status", "🍽️ Prato/Status"),
                "stretch": True,
                "width": 150,
                "iid": "prato",
                "minwidth": 100,
            },
            {
                "text": self.ACTION_COLUMN_TEXT,
                "stretch": False,
                "width": 40,
                "anchor": CENTER,
                "iid": self.ACTION_COLUMN_ID,
                "minwidth": 30,
            },
        ]

    def _create_counters_area(self):
        """Cria a área inferior com os labels de contagem."""
        counters_frame = ttk.Frame(self, padding=(0, 5))
        counters_frame.grid(row=1, column=0, sticky="ew")
        counters_frame.columnconfigure(0, weight=1)
        counters_frame.columnconfigure(1, weight=1)

        self._registered_count_label = ttk.Label(
            counters_frame,
            text=UI_TEXTS.get("registered_count_label", "Registrados: -"),
            bootstyle="secondary",
            font=("Helvetica", 10, "bold"),
            padding=(5, 2),
            anchor=CENTER,  # type: ignore
        )
        self._registered_count_label.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self._remaining_count_label = ttk.Label(
            counters_frame,
            text=UI_TEXTS.get("remaining_count_label", "Elegíveis: - / Restantes: -"),
            bootstyle="secondary",
            font=("Helvetica", 10, "bold"),
            padding=(5, 2),
            anchor=CENTER,  # type: ignore
        )
        self._remaining_count_label.grid(row=0, column=1, sticky="ew", padx=(5, 0))

    def _create_registered_table(self):
        """Cria a tabela para exibir os alunos registrados."""
        reg_frame = ttk.Labelframe(
            self,
            text=UI_TEXTS.get(
                "registered_students_label",
                "✅ Alunos Registrados (Clique ❌ para Remover)",
            ),
            padding=(5, 5),
        )
        reg_frame.grid(row=0, column=0, sticky="nsew")
        reg_frame.rowconfigure(0, weight=1)
        reg_frame.columnconfigure(0, weight=1)

        self._registered_cols_definition = self._get_registered_cols_definition()
        self._registered_students_table = SimpleTreeView(
            master=reg_frame, coldata=self._registered_cols_definition, height=15
        )
        self._registered_students_table.grid(row=0, column=0, sticky="nsew")

        sortable_cols = [
            str(cd.get("iid"))
            for cd in self._registered_cols_definition
            if cd.get("iid") and cd.get("iid") != self.ACTION_COLUMN_ID
        ]
        self._registered_students_table.setup_sorting(
            sortable_columns=sortable_cols or None
        )

    def load_registered_students(self):
        """Carrega ou recarrega os dados na tabela de alunos registrados."""
        if not self._registered_students_table:
            return
        logger.debug("Carregando tabela de registrados...")
        try:
            # Usa a fachada para obter os alunos que já consumiram
            served_data = self._fachada.obter_estudantes_para_sessao(consumido=True)
            if served_data:
                rows_with_action = []
                # A fachada retorna dicts: pront, nome, turma, hora_consumo, prato
                for student in served_data:
                    display_prato = student.get("prato") or UI_TEXTS.get(
                        "no_reservation_status", "Sem Reserva"
                    )
                    row = (
                        student.get("pront", ""),
                        student.get("nome", ""),
                        student.get("turma", ""),
                        student.get("hora_consumo", ""),
                        display_prato,
                    )
                    final_row = tuple(map(str, row)) + (self.ACTION_COLUMN_TEXT,)
                    rows_with_action.append(final_row)

                self._registered_students_table.build_table_data(
                    rowdata=rows_with_action
                )
                logger.info(
                    "Carregados %d alunos registrados na tabela.", len(rows_with_action)
                )
            else:
                self._registered_students_table.delete_rows()
                logger.info("Nenhum aluno registrado para exibir.")

            self.update_counters()
        except ErroSessaoNaoAtiva:
            logger.warning("Tentativa de carregar registrados sem sessão ativa.")
            self._registered_students_table.delete_rows()
            self.update_counters()
        except Exception as e:
            logger.exception("Erro ao carregar tabela de registrados: %s", e)
            messagebox.showerror(
                "Erro",
                "Não foi possível carregar a lista de registrados.",
                parent=self._app,
            )
            if self._registered_students_table:
                self._registered_students_table.delete_rows()
            self.update_counters()

    def update_counters(self):
        """Atualiza os labels dos contadores."""
        if not self._registered_count_label or not self._remaining_count_label:
            return

        reg_text = UI_TEXTS.get("registered_count_label", "Registrados: -")
        rem_text = UI_TEXTS.get("remaining_count_label", "Elegíveis: - / Restantes: -")
        reg_style, rem_style = "secondary", "secondary"

        try:
            # TODO: A fachada não tem métodos otimizados para contagem.
            # Os métodos `obter_estudantes_para_sessao` retornam listas
            # completas, cujo `len()` pode ser usado, mas é menos eficiente
            # que uma contagem direta no banco.
            registered_list = self._fachada.obter_estudantes_para_sessao(consumido=True)
            eligible_not_served_list = self._fachada.obter_estudantes_para_sessao(
                consumido=False
            )

            registered_count = len(registered_list)
            remaining_count = len(eligible_not_served_list)
            total_eligible_count = registered_count + remaining_count

            reg_text = UI_TEXTS.get(
                "registered_count_label", "Registrados: {count}"
            ).format(count=registered_count)
            rem_text = UI_TEXTS.get(
                "remaining_count_label",
                "Elegíveis: {eligible_count} / Restantes: {remaining_count}",
            ).format(
                eligible_count=total_eligible_count, remaining_count=remaining_count
            )
            reg_style = PRIMARY
            rem_style = PRIMARY

        except ErroSessaoNaoAtiva:
            # Estado sem sessão, os valores padrão já estão corretos.
            pass
        except Exception as e:
            logger.exception("Erro ao calcular/atualizar contadores: %s", e)
            reg_text = "Registrados: Erro"
            rem_text = "Elegíveis: Erro / Restantes: Erro"
            reg_style = "danger"
            rem_style = "danger"

        self._registered_count_label.config(text=reg_text, bootstyle=reg_style)  # type: ignore
        self._remaining_count_label.config(text=rem_text, bootstyle=rem_style)  # type: ignore

    def clear_table(self):
        """Limpa a tabela e reseta contadores."""
        logger.debug("Limpando tabela de registrados e contadores.")
        if self._registered_students_table:
            self._registered_students_table.delete_rows()
        self.update_counters()

    def remove_row_from_table(self, iid_to_delete: str):
        """Remove uma linha da tabela e atualiza contadores."""
        if not self._registered_students_table:
            return
        try:
            if self._registered_students_table.view.exists(iid_to_delete):
                self._registered_students_table.delete_rows([iid_to_delete])
                logger.debug("Linha %s removida da tabela UI.", iid_to_delete)
                self.update_counters()
            else:
                logger.warning(
                    "Tentativa de remover IID %s que não existe.", iid_to_delete
                )
                self.load_registered_students()
        except Exception as e:
            logger.exception("Erro ao remover linha %s da UI: %s", iid_to_delete, e)
            self.load_registered_students()

    def _on_registered_table_click(self, event: tk.Event):
        """Handler para cliques na tabela."""
        if not self._registered_students_table:
            return
        iid, col_id = self._registered_students_table.identify_clicked_cell(event)

        if iid and col_id == self.ACTION_COLUMN_ID:
            logger.debug("Coluna de ação clicada para a linha iid: %s", iid)
            self._confirm_and_delete_consumption(iid)
        elif iid and self._registered_students_table.view.exists(iid):
            if col_id != self.ACTION_COLUMN_ID:
                try:
                    self._registered_students_table.view.focus(iid)
                    if self._registered_students_table.get_selected_iid() != iid:
                        self._registered_students_table.view.selection_set(iid)
                except tk.TclError as e:
                    logger.warning("Erro Tcl ao focar/selecionar linha %s: %s", iid, e)

    def _on_table_delete_key(self, _=None):
        """Handler para tecla Delete/Backspace."""
        if not self._registered_students_table:
            return
        selected_iid = self._registered_students_table.get_selected_iid()
        if selected_iid:
            logger.debug("Tecla Delete pressionada para iid: %s", selected_iid)
            self._confirm_and_delete_consumption(selected_iid)

    def _confirm_and_delete_consumption(self, iid_to_delete: str):
        """Pede confirmação e chama a App principal para deletar."""
        if not self._registered_students_table:
            return

        row_values_full = self._registered_students_table.get_row_values(iid_to_delete)
        if not row_values_full or len(row_values_full) != len(
            self._registered_cols_definition
        ):
            logger.error(
                "Não foi possível obter valores válidos para iid %s.", iid_to_delete
            )
            messagebox.showerror(
                "Erro Interno", "Erro ao obter dados da linha.", parent=self._app
            )
            return

        try:
            # A fachada não precisa de todos os dados, mas usamos para a msg de confirmação
            data_for_logic = tuple(row_values_full[:5])
            pront, nome = data_for_logic[0], data_for_logic[1]
            if not pront:
                raise ValueError("Prontuário vazio.")
        except (IndexError, ValueError) as e:
            logger.error("Erro ao extrair dados da linha %s: %s.", iid_to_delete, e)
            messagebox.showerror(
                "Erro de Dados", "Erro ao processar dados da linha.", parent=self._app
            )
            return

        confirm_msg = UI_TEXTS.get(
            "confirm_deletion_message",
            "Tem certeza que deseja remover o registro para:\n\nProntuário: {pront}\nNome: {nome}?",
        ).format(pront=pront, nome=nome)

        if messagebox.askyesno(
            "Confirmar Remoção", confirm_msg, icon=WARNING, parent=self._app
        ):
            logger.info(
                "Confirmada exclusão para %s (iid UI: %s).", pront, iid_to_delete
            )
            self._app.handle_consumption_deletion(data_for_logic, iid_to_delete)
        else:
            logger.debug("Exclusão de %s cancelada.", pront)
