# ----------------------------------------------------------------------------
# Arquivo: registro/gui/autoatendimento/dialogos.py (Diálogos do Autoatendimento)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Diálogos interativos para operações de CRUD nos registros de consumo do autoatendimento:
- DialogoNovoConsumo: Criação de novo consumo manual
- DialogoEditarConsumo: Edição de horário e prato de consumo existente
- DialogoDetalhesConsumo: Visualização completa dos detalhes de um atendimento
"""

import datetime as dt
import logging
import re
import tkinter as tk
from typing import Any, Callable, Dict, List, Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, CENTER, EW, HORIZONTAL, LEFT, NSEW, RIGHT, VERTICAL, W, X
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.localization.msgcat import MessageCatalog

from registro.gui.comum.constants import REGEX_LIMPEZA_PRONTUARIO
from registro.nucleo.facade import FachadaRegistro

logger = logging.getLogger(__name__)


class DialogoNovoConsumo(ttk.Toplevel):
    """
    Diálogo para adicionar manualmente um novo registro de consumo na sessão ativa.
    Permite busca rápida de alunos, escolha de prato, horário e liberação avulsa.
    """

    def __init__(
        self,
        parent: tk.Widget,
        fachada: FachadaRegistro,
        on_sucesso: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title("➕ Novo Registro de Consumo Manual")
        self.geometry("640x580")
        self.minsize(560, 500)

        self.fachada = fachada
        self.on_sucesso = on_sucesso
        self.sucesso = False

        self._alunos_cache: List[Dict[str, Any]] = []
        self._candidatos_filtrados: List[Dict[str, Any]] = []

        self._criar_widgets()
        self._carregar_alunos()
        self._centralizar(parent)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.wait_window(self)

    def _centralizar(self, parent: tk.Widget):
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            w = self.winfo_width()
            h = self.winfo_height()
            x = max(10, px + (pw - w) // 2)
            y = max(10, py + (ph - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def _criar_widgets(self):
        container = ttk.Frame(self, padding=16)
        container.pack(fill=BOTH, expand=True)
        container.rowconfigure(2, weight=1)
        container.columnconfigure(0, weight=1)

        # Cabeçalho
        frame_cabecalho = ttk.Frame(container)
        frame_cabecalho.grid(row=0, column=0, sticky=EW, pady=(0, 10))
        ttk.Label(
            frame_cabecalho,
            text="➕ Registrar Consumo Manual",
            font=("Segoe UI", 16, "bold"),
            bootstyle="primary",
        ).pack(anchor=W)
        ttk.Label(
            frame_cabecalho,
            text="Localize o estudante por nome ou prontuário para efetuar o registro na sessão ativa.",
            font=("Segoe UI", 9),
            bootstyle="secondary",
        ).pack(anchor=W)

        # Campo de busca
        frame_busca = ttk.Frame(container)
        frame_busca.grid(row=1, column=0, sticky=EW, pady=(0, 8))
        frame_busca.columnconfigure(1, weight=1)

        ttk.Label(frame_busca, text="🔍 Buscar Aluno:", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky=W, padx=(0, 8)
        )
        self.var_busca = tk.StringVar()
        self.var_busca.trace_add("write", lambda *_: self._ao_digitar_busca())
        self.entry_busca = ttk.Entry(frame_busca, textvariable=self.var_busca, font=("Segoe UI", 10))
        self.entry_busca.grid(row=0, column=1, sticky=EW)
        self.entry_busca.focus_set()

        # Lista de candidatos (Treeview)
        frame_lista = ttk.Frame(container)
        frame_lista.grid(row=2, column=0, sticky=NSEW, pady=(0, 12))
        frame_lista.rowconfigure(0, weight=1)
        frame_lista.columnconfigure(0, weight=1)

        colunas = ("pront", "nome", "turma", "status_reserva")
        self.tree_candidatos = ttk.Treeview(
            frame_lista, columns=colunas, show="headings", height=6, selectmode="browse"
        )
        self.tree_candidatos.heading("pront", text="Prontuário", anchor=W)
        self.tree_candidatos.heading("nome", text="Nome", anchor=W)
        self.tree_candidatos.heading("turma", text="Turma", anchor=W)
        self.tree_candidatos.heading("status_reserva", text="Reserva / Prato", anchor=W)

        self.tree_candidatos.column("pront", width=110, stretch=False)
        self.tree_candidatos.column("nome", width=200, stretch=True)
        self.tree_candidatos.column("turma", width=120, stretch=False)
        self.tree_candidatos.column("status_reserva", width=130, stretch=False)

        sb_v = ttk.Scrollbar(frame_lista, orient=VERTICAL, command=self.tree_candidatos.yview)
        self.tree_candidatos.configure(yscrollcommand=sb_v.set)

        self.tree_candidatos.grid(row=0, column=0, sticky=NSEW)
        sb_v.grid(row=0, column=1, sticky="ns")
        self.tree_candidatos.bind("<<TreeviewSelect>>", self._ao_selecionar_candidato)
        self.tree_candidatos.bind("<Double-1>", lambda _: self._confirmar_registro())

        # Painel com os dados do registro selecionado
        frame_dados = ttk.LabelFrame(container, text=" Detalhes do Atendimento ", padding=12)
        frame_dados.grid(row=3, column=0, sticky=EW, pady=(0, 12))
        frame_dados.columnconfigure(1, weight=1)
        frame_dados.columnconfigure(3, weight=1)

        # Linha 1: Prontuário e Nome
        ttk.Label(frame_dados, text="Prontuário:", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, sticky=W, padx=(0, 6), pady=4
        )
        self.var_prontuario = tk.StringVar()
        self.entry_pront = ttk.Entry(frame_dados, textvariable=self.var_prontuario, font=("Segoe UI", 9))
        self.entry_pront.grid(row=0, column=1, sticky=EW, padx=(0, 12), pady=4)

        ttk.Label(frame_dados, text="Nome:", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=2, sticky=W, padx=(0, 6), pady=4
        )
        self.var_nome = tk.StringVar()
        self.entry_nome = ttk.Entry(
            frame_dados, textvariable=self.var_nome, state="readonly", font=("Segoe UI", 9)
        )
        self.entry_nome.grid(row=0, column=3, sticky=EW, pady=4)

        # Linha 2: Turma e Prato
        ttk.Label(frame_dados, text="Turma:", font=("Segoe UI", 9, "bold")).grid(
            row=1, column=0, sticky=W, padx=(0, 6), pady=4
        )
        self.var_turma = tk.StringVar()
        self.entry_turma = ttk.Entry(
            frame_dados, textvariable=self.var_turma, state="readonly", font=("Segoe UI", 9)
        )
        self.entry_turma.grid(row=1, column=1, sticky=EW, padx=(0, 12), pady=4)

        ttk.Label(frame_dados, text="Prato/Item:", font=("Segoe UI", 9, "bold")).grid(
            row=1, column=2, sticky=W, padx=(0, 6), pady=4
        )
        self.var_prato = tk.StringVar(value="Almoço")
        self.combo_prato = ttk.Combobox(
            frame_dados,
            textvariable=self.var_prato,
            values=["Almoço", "Padrão", "Vegetariano", "Vegano", "Lanche", "Sem Reserva"],
            font=("Segoe UI", 9),
        )
        self.combo_prato.grid(row=1, column=3, sticky=EW, pady=4)

        # Linha 3: Horário e Exceção
        ttk.Label(frame_dados, text="Horário:", font=("Segoe UI", 9, "bold")).grid(
            row=2, column=0, sticky=W, padx=(0, 6), pady=4
        )
        self.var_hora = tk.StringVar(value=dt.datetime.now().strftime("%H:%M:%S"))
        self.entry_hora = ttk.Entry(frame_dados, textvariable=self.var_hora, font=("Segoe UI", 9))
        self.entry_hora.grid(row=2, column=1, sticky=EW, padx=(0, 12), pady=4)

        self.var_pular_grupos = tk.BooleanVar(value=True)
        chk_pular = ttk.Checkbutton(
            frame_dados,
            text="Liberar registro avulso / exceção de turma",
            variable=self.var_pular_grupos,
            bootstyle="round-toggle",
        )
        chk_pular.grid(row=2, column=2, columnspan=2, sticky=W, pady=4)

        # Rodapé com Botões de Ação
        frame_rodape = ttk.Frame(container)
        frame_rodape.grid(row=4, column=0, sticky=EW)

        ttk.Button(
            frame_rodape,
            text="❌ Cancelar",
            command=self.destroy,
            bootstyle="secondary-outline",
            padding=(12, 6),
        ).pack(side=RIGHT, padx=(8, 0))

        ttk.Button(
            frame_rodape,
            text="✔️ Confirmar Registro",
            command=self._confirmar_registro,
            bootstyle="success",
            padding=(16, 6),
        ).pack(side=RIGHT)

    def _carregar_alunos(self):
        """Carrega os alunos elegíveis e os demais alunos da base para pesquisa rápida."""
        try:
            # 1. Alunos elegíveis para a sessão que ainda não consumiram
            elegiveis = self.fachada.obter_estudantes_para_sessao(consumido=False)
            self._alunos_cache = list(elegiveis)

            # Se a lista de elegíveis estiver vazia, busca todos os alunos cadastrados
            if not self._alunos_cache:
                todos = self.fachada.listar_todos_os_estudantes()
                for est in todos:
                    self._alunos_cache.append(
                        {
                            "pront": est.get("prontuario") or est.get("pront"),
                            "nome": est.get("nome"),
                            "turma": ", ".join(est.get("grupos", [])) or "Geral",
                            "prato": "Sem Reserva",
                        }
                    )
            self._atualizar_tabela_candidatos(self._alunos_cache[:50])
        except Exception as e:
            logger.error("Erro ao carregar lista de alunos no diálogo: %s", e)

    def _ao_digitar_busca(self):
        termo = self.var_busca.get().strip().lower()
        if not termo:
            self._atualizar_tabela_candidatos(self._alunos_cache[:50])
            return

        filtrados = []
        for aluno in self._alunos_cache:
            pront = str(aluno.get("pront", "")).lower()
            nome = str(aluno.get("nome", "")).lower()
            turma = str(aluno.get("turma", "")).lower()
            if termo in pront or termo in nome or termo in turma:
                filtrados.append(aluno)

        self._atualizar_tabela_candidatos(filtrados[:50])

    def _atualizar_tabela_candidatos(self, lista: List[Dict[str, Any]]):
        self._candidatos_filtrados = lista
        self.tree_candidatos.delete(*self.tree_candidatos.get_children())
        for aluno in lista:
            pront = aluno.get("pront", "")
            nome = aluno.get("nome", "")
            turma = aluno.get("turma", "")
            prato = aluno.get("prato") or "Sem Reserva"
            self.tree_candidatos.insert("", "end", values=(pront, nome, turma, prato))

    def _ao_selecionar_candidato(self, _event=None):
        sel = self.tree_candidatos.selection()
        if not sel:
            return
        item = self.tree_candidatos.item(sel[0])
        vals = item.get("values", [])
        if len(vals) >= 4:
            self.var_prontuario.set(str(vals[0]))
            self.var_nome.set(str(vals[1]))
            self.var_turma.set(str(vals[2]))
            prato_val = str(vals[3]) if str(vals[3]) != "Sem Reserva" else "Almoço"
            self.var_prato.set(prato_val)

    def _confirmar_registro(self):
        pront = self.var_prontuario.get().strip()
        if not pront:
            Messagebox.show_warning(
                "Atenção", "Selecione um estudante ou digite o prontuário.", parent=self
            )
            return

        hora = self.var_hora.get().strip() or dt.datetime.now().strftime("%H:%M:%S")
        prato = self.var_prato.get().strip() or "Almoço"
        pular_grupos = self.var_pular_grupos.get()

        try:
            resultado = self.fachada.registrar_consumo(
                prontuario=pront,
                pular_grupos=pular_grupos,
            )
            autorizado = resultado.get("autorizado", resultado.get("sucesso", True))
            if not autorizado:
                msg = resultado.get("motivo") or resultado.get("mensagem") or "Não autorizado para esta sessão."
                Messagebox.show_warning("Não Autorizado", msg, parent=self)
                return

            id_consumo = resultado.get("id_consumo")
            if not id_consumo and self.fachada.id_sessao_ativa:
                try:
                    c_db = self.fachada.repo_consumo.por_prontuario_e_sessao(
                        pront, self.fachada.id_sessao_ativa
                    )
                    if c_db:
                        id_consumo = c_db.id
                except Exception:
                    pass

            if id_consumo:
                self.fachada.atualizar_consumo(
                    id_consumo=id_consumo,
                    hora_consumo=hora,
                    prato=prato,
                )

            self.sucesso = True
            logger.info("Consumo registrado com sucesso via diálogo para: %s", pront)

            if self.on_sucesso:
                resultado["hora_consumo"] = hora
                resultado["prato"] = prato
                self.on_sucesso(resultado)

            Messagebox.show_info(
                "Sucesso",
                f"Consumo registrado com sucesso para:\n{self.var_nome.get() or pront}",
                parent=self,
            )
            self.destroy()
        except Exception as e:
            logger.exception("Falha ao registrar consumo manual: %s", e)
            Messagebox.show_error(
                "Erro no Registro",
                f"Não foi possível registrar o consumo:\n{e}",
                parent=self,
            )


class DialogoEditarConsumo(ttk.Toplevel):
    """
    Diálogo para editar um registro de consumo existente (horário e prato/status).
    """

    def __init__(
        self,
        parent: tk.Widget,
        fachada: FachadaRegistro,
        id_consumo: int,
        dados_consumo: Dict[str, Any],
        on_sucesso: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title("✏️ Editar Registro de Consumo")
        self.geometry("480x360")
        self.resizable(False, False)

        self.fachada = fachada
        self.id_consumo = id_consumo
        self.dados_consumo = dados_consumo
        self.on_sucesso = on_sucesso
        self.sucesso = False

        self._criar_widgets()
        self._centralizar(parent)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.wait_window(self)

    def _centralizar(self, parent: tk.Widget):
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            w = self.winfo_width()
            h = self.winfo_height()
            x = max(10, px + (pw - w) // 2)
            y = max(10, py + (ph - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def _criar_widgets(self):
        container = ttk.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        ttk.Label(
            container,
            text="✏️ Editar Atendimento",
            font=("Segoe UI", 16, "bold"),
            bootstyle="primary",
        ).pack(anchor=W, pady=(0, 4))

        pront = self.dados_consumo.get("pront", "")
        nome = self.dados_consumo.get("nome", "")
        turma = self.dados_consumo.get("turma", "")
        hora = self.dados_consumo.get("hora_consumo", "")
        prato = self.dados_consumo.get("prato", "Almoço")

        ttk.Label(
            container,
            text=f"Estudante: {nome} ({pront}) • Turma: {turma}",
            font=("Segoe UI", 10),
            bootstyle="secondary",
        ).pack(anchor=W, pady=(0, 16))

        # Formulário de edição
        form = ttk.Frame(container)
        form.pack(fill=X, pady=(0, 20))
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Horário de Consumo:", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky=W, padx=(0, 10), pady=8
        )
        self.var_hora = tk.StringVar(value=hora)
        entry_hora = ttk.Entry(form, textvariable=self.var_hora, font=("Segoe UI", 10))
        entry_hora.grid(row=0, column=1, sticky=EW, pady=8)

        ttk.Label(form, text="Prato / Cardápio:", font=("Segoe UI", 10, "bold")).grid(
            row=1, column=0, sticky=W, padx=(0, 10), pady=8
        )
        self.var_prato = tk.StringVar(value=prato)
        combo_prato = ttk.Combobox(
            form,
            textvariable=self.var_prato,
            values=["Almoço", "Padrão", "Vegetariano", "Vegano", "Lanche", "Sem Reserva"],
            font=("Segoe UI", 10),
        )
        combo_prato.grid(row=1, column=1, sticky=EW, pady=8)

        # Botões
        frame_botoes = ttk.Frame(container)
        frame_botoes.pack(fill=X, side="bottom")

        ttk.Button(
            frame_botoes,
            text="❌ Cancelar",
            command=self.destroy,
            bootstyle="secondary-outline",
            padding=(12, 6),
        ).pack(side=RIGHT, padx=(8, 0))

        ttk.Button(
            frame_botoes,
            text="💾 Salvar Alterações",
            command=self._salvar,
            bootstyle="primary",
            padding=(16, 6),
        ).pack(side=RIGHT)

    def _salvar(self):
        nova_hora = self.var_hora.get().strip()
        novo_prato = self.var_prato.get().strip()

        if not nova_hora:
            Messagebox.show_warning("Horário Inválido", "O horário não pode estar vazio.", parent=self)
            return

        try:
            ok = self.fachada.atualizar_consumo(
                id_consumo=self.id_consumo,
                hora_consumo=nova_hora,
                prato=novo_prato,
            )
            if ok:
                self.sucesso = True
                if self.on_sucesso:
                    self.on_sucesso({"hora_consumo": nova_hora, "prato": novo_prato})
                Messagebox.show_info("Atualizado", "Registro atualizado com sucesso!", parent=self)
                self.destroy()
            else:
                Messagebox.show_error("Erro", "Não foi possível encontrar o registro para atualizar.", parent=self)
        except Exception as e:
            logger.exception("Erro ao salvar atualização de consumo: %s", e)
            Messagebox.show_error("Erro", f"Falha ao salvar:\n{e}", parent=self)


class DialogoDetalhesConsumo(ttk.Toplevel):
    """
    Diálogo para exibição detalhada de um registro de consumo e atalhos para edição/exclusão.
    """

    def __init__(
        self,
        parent: tk.Widget,
        dados_consumo: Dict[str, Any],
        on_editar: Optional[Callable[[], None]] = None,
        on_excluir: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title("🔍 Detalhes do Registro de Consumo")
        self.geometry("520x420")
        self.resizable(False, False)

        self.dados = dados_consumo
        self.on_editar = on_editar
        self.on_excluir = on_excluir

        self._criar_widgets()
        self._centralizar(parent)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.wait_window(self)

    def _centralizar(self, parent: tk.Widget):
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            w = self.winfo_width()
            h = self.winfo_height()
            x = max(10, px + (pw - w) // 2)
            y = max(10, py + (ph - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def _criar_widgets(self):
        container = ttk.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        ttk.Label(
            container,
            text="📋 Detalhes do Atendimento",
            font=("Segoe UI", 16, "bold"),
            bootstyle="primary",
        ).pack(anchor=W, pady=(0, 12))

        card = ttk.Frame(container, padding=16, bootstyle="secondary")
        card.pack(fill=BOTH, expand=True, pady=(0, 16))
        card.columnconfigure(1, weight=1)

        campos = [
            ("🆔 Prontuário:", self.dados.get("pront", "--")),
            ("👤 Nome:", self.dados.get("nome", "--")),
            ("👥 Turma:", self.dados.get("turma", "--")),
            ("⏱️ Horário de Consumo:", self.dados.get("hora_consumo", "--")),
            ("🍽️ Prato / Status:", self.dados.get("prato", "--")),
            ("🔑 ID do Registro:", str(self.dados.get("id_consumo", "--"))),
        ]

        for i, (label, valor) in enumerate(campos):
            ttk.Label(
                card, text=label, font=("Segoe UI", 10, "bold"), bootstyle="@secondary"
            ).grid(row=i, column=0, sticky=W, padx=(0, 12), pady=6)
            ttk.Label(
                card, text=str(valor), font=("Segoe UI", 10), bootstyle="@secondary"
            ).grid(row=i, column=1, sticky=W, pady=6)

        # Rodapé
        rodape = ttk.Frame(container)
        rodape.pack(fill=X, side="bottom")

        if self.on_excluir:
            ttk.Button(
                rodape,
                text="🗑️ Excluir",
                command=self._ao_clicar_excluir,
                bootstyle="danger-outline",
                padding=(12, 6),
            ).pack(side=LEFT)

        if self.on_editar:
            ttk.Button(
                rodape,
                text="✏️ Editar",
                command=self._ao_clicar_editar,
                bootstyle="primary-outline",
                padding=(12, 6),
            ).pack(side=LEFT, padx=(8, 0))

        ttk.Button(
            rodape,
            text="Fechar",
            command=self.destroy,
            bootstyle="secondary",
            padding=(16, 6),
        ).pack(side=RIGHT)

    def _ao_clicar_editar(self):
        self.destroy()
        if self.on_editar:
            self.on_editar()

    def _ao_clicar_excluir(self):
        self.destroy()
        if self.on_excluir:
            self.on_excluir()
