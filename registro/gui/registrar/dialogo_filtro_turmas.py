# ----------------------------------------------------------------------------
# Arquivo: registro/gui/registrar/dialogo_filtro_turmas.py (Diálogo de Filtro de Turmas)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

import logging
import tkinter as tk
from tkinter import BOTH, EW, HORIZONTAL, NSEW, YES, W, E
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap import ScrolledFrame

from registro.gui.registrar.constants import TURMAS_INTEGRADO, obter_turmas_integrado
from registro.nucleo.facade import FachadaRegistro

if TYPE_CHECKING:
    from registro.gui.registrar.app import AppRegistro

logger = logging.getLogger(__name__)


def _toggle_selecao_coluna(vars_coluna: List[tk.BooleanVar]):
    """
    Alterna o estado de uma lista de BooleanVars. Se algum estiver True,
    todos se tornam False; se todos estiverem False, todos se tornam True.
    """
    if not vars_coluna:
        return
    novo_estado = not any(var.get() for var in vars_coluna)
    for var in vars_coluna:
        var.set(novo_estado)


class DialogoFiltroTurmas(tk.Toplevel):
    """
    Diálogo moderno para permitir que o operador filtre as turmas e categorias
    que participam da sessão ativa, com busca instantânea e atalhos rápidos.
    """

    def __init__(
        self,
        parent: Any,
        fachada_nucleo: "FachadaRegistro",
        callback_aplicar: Callable[[List[str]], None],
    ):
        super().__init__(parent)
        self.withdraw()
        self.title("📊 Filtrar Turmas e Categorias da Sessão")
        self.transient(parent)
        self.grab_set()

        self._fachada = fachada_nucleo
        self._callback_aplicar = callback_aplicar
        self._app_parente = parent
        self._dados_checkbox: List[Tuple[str, tk.BooleanVar, ttk.Checkbutton]] = []
        self._mapa_widgets_turma: Dict[str, Dict[str, tk.Widget]] = {}
        self._vars_com_reserva: List[tk.BooleanVar] = []
        self._vars_sem_reserva: List[tk.BooleanVar] = []

        self._entrada_busca: Optional[ttk.Entry] = None
        self._var_ignorar_horario = tk.BooleanVar(value=False)
        self._label_contador: Optional[ttk.Label] = None

        self._criar_widgets()
        self._inicializar_estados()

        self.protocol("WM_DELETE_WINDOW", self._ao_cancelar)
        self._centralizar_janela()
        self.resizable(True, True)
        self.deiconify()

    def _criar_widgets(self):
        """Cria e organiza os widgets no diálogo."""
        frame_principal = ttk.Frame(self, padding=15)
        frame_principal.pack(fill=BOTH, expand=YES)
        frame_principal.rowconfigure(2, weight=1)
        frame_principal.columnconfigure(0, weight=1)

        # 1. Barra de Busca e Filtro de Categoria
        frame_topo = ttk.Frame(frame_principal)
        frame_topo.grid(row=0, column=0, sticky=EW, pady=(0, 10))
        frame_topo.columnconfigure(0, weight=1)

        # Busca textual
        frame_busca = ttk.Frame(frame_topo)
        frame_busca.grid(row=0, column=0, sticky=EW)
        frame_busca.columnconfigure(1, weight=1)

        ttk.Label(frame_busca, text="🔍 Buscar:", font="-weight bold").grid(
            row=0, column=0, sticky=W, padx=(0, 8)
        )
        self._entrada_busca = ttk.Entry(frame_busca)
        self._entrada_busca.grid(row=0, column=1, sticky=EW)
        self._entrada_busca.bind("<KeyRelease>", self._ao_digitar_busca)

        # Opção de Horário Livre (bypass de trava de hora da grade)
        frame_horario = ttk.Frame(frame_topo)
        frame_horario.grid(row=1, column=0, sticky=EW, pady=(8, 0))
        self._var_ignorar_horario.set(
            getattr(self._fachada, "ignorar_horario_grade", False) is True
        )
        ttk.Checkbutton(
            frame_horario,
            text="🕒 Horário Livre — Ignorar trava de horário da grade (mantém validação das turmas do dia)",
            variable=self._var_ignorar_horario,
            bootstyle="warning-round-toggle",
        ).pack(side=tk.LEFT, padx=2)

        # 2. Barra de Botões Inteligentes (Grade, Integrado, Inverter, Limpar)
        frame_atalhos = ttk.Frame(frame_principal)
        frame_atalhos.grid(row=1, column=0, sticky=EW, pady=(0, 10))
        frame_atalhos.columnconfigure(tuple(range(5)), weight=1)

        botoes_atalho = [
            ("🕒 Grade do Dia", self._ao_selecionar_grade, "success-outline"),
            ("🔗 Integrado", self._ao_selecionar_integrado, "info-outline"),
            ("🔄 Inverter", self._ao_inverter_selecoes, "secondary-outline"),
            ("✅ Marcar Todas", self._ao_marcar_todas, "secondary-outline"),
            ("⚪ Limpar", self._ao_limpar_todas, "secondary-outline"),
        ]
        for i, (txt, cmd, estilo) in enumerate(botoes_atalho):
            ttk.Button(frame_atalhos, text=txt, command=cmd, bootstyle=estilo).grid(
                row=0, column=i, padx=2, sticky=EW
            )

        # 3. Lista de Turmas e Categorias com Rolagem e Toggles de Coluna
        try:
            grupos = self._fachada.listar_todos_os_grupos()
            turmas = sorted(
                g["nome"] for g in grupos if g.get("tipo") != "categoria"
            )
            categorias = sorted(
                g["nome"] for g in grupos if g.get("tipo") == "categoria"
            )
        except Exception as e:
            logger.exception("Erro ao buscar turmas e categorias: %s", e)
            turmas = []
            categorias = []

        frame_secao_turmas = self._criar_secao_turmas(
            frame_principal, turmas, categorias
        )
        frame_secao_turmas.grid(row=2, column=0, sticky=NSEW, pady=(0, 10))

        # 4. Rodapé com Contador e Botões de Ação
        frame_rodape = ttk.Frame(frame_principal)
        frame_rodape.grid(row=3, column=0, sticky=EW)
        frame_rodape.columnconfigure(0, weight=1)

        self._label_contador = ttk.Label(
            frame_rodape,
            text="📊 0 turmas selecionadas",
            font="-size 10 -weight bold",
            bootstyle="primary",
        )
        self._label_contador.grid(row=0, column=0, sticky=W)

        frame_botoes = ttk.Frame(frame_rodape)
        frame_botoes.grid(row=0, column=1, sticky=E)

        ttk.Button(
            frame_botoes, text="❌ Cancelar", command=self._ao_cancelar, bootstyle="danger"
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            frame_botoes, text="✔️ Aplicar Filtros", command=self._ao_aplicar, bootstyle="success"
        ).pack(side=tk.LEFT)

    def _criar_secao_turmas(
        self,
        master: tk.Widget,
        turmas: List[str],
        categorias: Optional[List[str]] = None,
    ) -> ttk.Frame:
        """Cria o cabeçalho e a lista rolável separada em Turmas e Categorias."""
        frame = ttk.Frame(master)
        frame.columnconfigure(0, weight=2)
        frame.columnconfigure((1, 2), weight=1)
        frame.rowconfigure(2, weight=1)

        categorias = categorias or []
        if not turmas and not categorias:
            ttk.Label(frame, text="Nenhuma turma ou categoria disponível.").grid(row=0, column=0)
            return frame

        self._vars_com_reserva.clear()
        self._vars_sem_reserva.clear()

        ttk.Label(frame, text="Turma / Categoria", font="-weight bold", anchor=W).grid(
            row=0, column=0, sticky=EW, padx=5
        )
        ttk.Button(
            frame,
            text="COM Reserva",
            bootstyle="success-outline",
            command=self._toggle_coluna_com,
        ).grid(row=0, column=1, sticky=EW, padx=5)
        ttk.Button(
            frame,
            text="SEM Reserva (#)",
            bootstyle="warning-outline",
            command=self._toggle_coluna_sem,
        ).grid(row=0, column=2, sticky=EW, padx=5)

        ttk.Separator(frame, orient=HORIZONTAL).grid(
            row=1, column=0, columnspan=3, sticky=EW, pady=5
        )

        frame_rolavel = ScrolledFrame(frame, padding=5, auto_hide=True)
        frame_rolavel.grid(row=2, column=0, columnspan=3, sticky=NSEW)
        frame_rolavel.columnconfigure(0, weight=2)
        frame_rolavel.columnconfigure((1, 2), weight=1)

        self._dados_checkbox.clear()
        self._mapa_widgets_turma.clear()

        def _adicionar_secao(titulo: str, itens: List[str], row_idx: int) -> int:
            if not itens:
                return row_idx
            ttk.Label(
                frame_rolavel,
                text=titulo,
                font="-size 9 -weight bold",
                bootstyle="info",
                anchor=W,
            ).grid(row=row_idx, column=0, columnspan=3, sticky=EW, padx=6, pady=(6, 3))
            row_idx += 1

            for nome_grupo in itens:
                var_com = tk.BooleanVar(value=False)
                var_sem = tk.BooleanVar(value=False)
                self._vars_com_reserva.append(var_com)
                self._vars_sem_reserva.append(var_sem)

                lbl = ttk.Label(frame_rolavel, text=nome_grupo, anchor=W)
                lbl.grid(row=row_idx, column=0, sticky="ew", padx=(14, 5), pady=2)

                cb_com = ttk.Checkbutton(
                    frame_rolavel,
                    variable=var_com,
                    bootstyle="success-square-toggle",
                    command=self._ao_mudar_checkbox,
                )
                cb_com.grid(row=row_idx, column=1, pady=2)

                cb_sem = ttk.Checkbutton(
                    frame_rolavel,
                    variable=var_sem,
                    bootstyle="warning-square-toggle",
                    command=self._ao_mudar_checkbox,
                )
                cb_sem.grid(row=row_idx, column=2, pady=2)

                self._dados_checkbox.extend(
                    [
                        (nome_grupo, var_com, cb_com),
                        (f"#{nome_grupo}", var_sem, cb_sem),
                    ]
                )
                self._mapa_widgets_turma[nome_grupo] = {
                    "label": lbl,
                    "cb_com": cb_com,
                    "cb_sem": cb_sem,
                }
                row_idx += 1
            return row_idx

        prox_row = _adicionar_secao("🏫 Turmas", turmas, 0)
        if turmas and categorias:
            ttk.Separator(frame_rolavel, orient=HORIZONTAL).grid(
                row=prox_row, column=0, columnspan=3, sticky=EW, pady=6
            )
            prox_row += 1
        _adicionar_secao("🏷️ Categorias (PAP, ESP1, LIB0...)", categorias, prox_row)

        return frame

    def _ao_digitar_busca(self, _=None):
        """Filtra visualmente as turmas conforme o texto digitado."""
        if not self._entrada_busca:
            return
        termo = self._entrada_busca.get().strip().lower()
        for nome_turma, widgets in self._mapa_widgets_turma.items():
            visivel = (not termo) or (termo in nome_turma.lower())
            if visivel:
                widgets["label"].grid()
                widgets["cb_com"].grid()
                widgets["cb_sem"].grid()
            else:
                widgets["label"].grid_remove()
                widgets["cb_com"].grid_remove()
                widgets["cb_sem"].grid_remove()

    def _ao_mudar_checkbox(self):
        """Atualiza o contador sempre que houver alteração em um checkbox."""
        self._atualizar_contador()

    def _atualizar_contador(self):
        """Atualiza a contagem exibida no rodapé."""
        if not self._label_contador:
            return
        total_com = sum(1 for ident, var, _ in self._dados_checkbox if var.get() and not ident.startswith("#"))
        total_sem = sum(1 for ident, var, _ in self._dados_checkbox if var.get() and ident.startswith("#"))
        texto = f"📊 Selecionadas: {total_com} com reserva"
        if total_sem > 0:
            texto += f" | {total_sem} sem reserva (#)"
        self._label_contador.config(text=texto)

    def _toggle_coluna_com(self):
        _toggle_selecao_coluna(self._vars_com_reserva)
        self._atualizar_contador()

    def _toggle_coluna_sem(self):
        _toggle_selecao_coluna(self._vars_sem_reserva)
        self._atualizar_contador()

    def _ao_selecionar_grade(self):
        """Marca as turmas previstas na grade horária para o dia e refeição da sessão ativa."""
        try:
            detalhes = self._fachada.obter_detalhes_sessao_ativa()
            refeicao = detalhes.get("refeicao", "lanche")
        except Exception:
            refeicao = "lanche"

        dia_atual = self._fachada.obter_dia_semana_atual()
        turmas_grade = set(
            self._fachada.obter_turmas_previstas_para_refeicao(
                dia_semana=dia_atual, refeicao=refeicao, incluir_categorias=True
            )
        )
        if not turmas_grade:
            Messagebox.show_info(
                f"Nenhuma turma prevista na grade para {refeicao.capitalize()} na {dia_atual.capitalize()}.",
                "Grade de Horários",
                parent=self,
            )
            return

        for ident, var, _ in self._dados_checkbox:
            if not ident.startswith("#"):
                var.set(ident in turmas_grade)
        self._atualizar_contador()

    def _ao_selecionar_integrado(self):
        """Marca apenas as turmas do integrado na coluna com reserva."""
        turmas_integrado = set(obter_turmas_integrado())
        for ident, var, _ in self._dados_checkbox:
            if not ident.startswith("#"):
                var.set(ident in turmas_integrado)
        self._atualizar_contador()

    def _ao_inverter_selecoes(self):
        """Inverte todas as seleções de turmas."""
        for _, var, _ in self._dados_checkbox:
            var.set(not var.get())
        self._atualizar_contador()

    def _ao_marcar_todas(self):
        """Marca todas as turmas na coluna com reserva."""
        for ident, var, _ in self._dados_checkbox:
            if not ident.startswith("#"):
                var.set(True)
        self._atualizar_contador()

    def _ao_limpar_todas(self):
        """Desmarca todas as turmas."""
        for _, var, _ in self._dados_checkbox:
            var.set(False)
        self._atualizar_contador()

    def _inicializar_estados(self):
        """Inicializa o estado dos checkboxes com base nos filtros da sessão ativa."""
        try:
            detalhes_sessao = self._fachada.obter_detalhes_sessao_ativa()
            grupos_ativos = detalhes_sessao.get("grupos", set())
            grupos_excluidos = {f"#{eg}" for eg in self._fachada.excecao_grupos}
            selecionados = set(grupos_ativos) | set(grupos_excluidos)

            for identificador, var, _ in self._dados_checkbox:
                var.set(identificador in selecionados)
        except Exception as e:
            logger.error("Erro ao inicializar estados do filtro: %s", e)

        self._atualizar_contador()

    def _ao_cancelar(self):
        """Fecha o diálogo sem aplicar as alterações."""
        self.grab_release()
        self.destroy()

    def _ao_aplicar(self):
        """Aplica os filtros de turma e categoria selecionados."""
        if not self._dados_checkbox:
            self._ao_cancelar()
            return

        selecionados = [ident for ident, var, _ in self._dados_checkbox if var.get()]
        ignorar_horario = bool(self._var_ignorar_horario.get())
        if hasattr(self._fachada, "definir_ignorar_horario_grade"):
            self._fachada.definir_ignorar_horario_grade(ignorar_horario)

        logger.info(
            "Aplicando filtros: grupos=%s, ignorar_horario=%s",
            selecionados,
            ignorar_horario,
        )
        try:
            self._callback_aplicar(selecionados)
            self.grab_release()
            self.destroy()
        except Exception as e:
            logger.exception("Erro ao aplicar filtros: %s", e)
            Messagebox.show_error(
                f"Falha ao aplicar filtros:\n{e}", "Erro", parent=self
            )

    def _centralizar_janela(self):
        """Centraliza o diálogo em relação à janela principal."""
        self.update_idletasks()
        if not self._app_parente:
            return

        px, py = self._app_parente.winfo_x(), self._app_parente.winfo_y()
        pw, ph = self._app_parente.winfo_width(), self._app_parente.winfo_height()
        dw, dh = self.winfo_width(), self.winfo_height()

        pos_x = px + (pw // 2) - (dw // 2)
        pos_y = py + (ph // 2) - (dh // 2)
        self.geometry(f"+{pos_x}+{pos_y}")
