# --- Arquivo: gui.py ---

import re
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Dict, List, Optional

import customtkinter as ctk
from fuzzywuzzy import process

from registro.nucleo.exceptions import ErroNucleoRegistro, ErroSessaoNaoAtiva
from registro.nucleo.facade import FachadaRegistro

# Configurações visuais
ctk.set_appearance_mode("Light") # "System" | "Dark" | "Light"
ctk.set_default_color_theme("blue")


class CampoBuscaAutocomplete(ctk.CTkEntry):
    """
    Uma versão otimizada do widget de Autocomplete.
    Pré-processa os dados para uma busca fuzzy instantânea e inteligente.
    """

    def __init__(self, master, callback_registro, **kwargs):
        super().__init__(master, **kwargs)

        self.callback_registro = callback_registro
        self._padrao_prontuario = re.compile(r"^[A-Za-z]{0,2}\d{0,8}$")
        self._padrao_prontuario_limpo = re.compile(r"^[A-Za-z]{0,2}\d0*")

        self._lista_prontuarios: List[str] = []
        self._lista_nomes: List[str] = []
        self._mapa_prontuarios: Dict[str, Dict] = {}
        self._mapa_nomes: Dict[str, Dict] = {}
        self._mapa_exibicao: Dict[str, str] = {}

        self.caixa_sugestoes = tk.Listbox(
            master,
            background="white",
            foreground="#2a2d2e",
            selectbackground="white",
            selectforeground="#24527d",
            highlightthickness=0,
            borderwidth=0,
            font=("Arial", 12),
        )

        self.bind("<KeyRelease>", self._ao_liberar_tecla)
        self.bind("<FocusOut>", self._ao_perder_foco)
        self.bind("<Down>", self._mover_selecao)
        self.bind("<Up>", self._mover_selecao)
        self.bind("<Return>", self._ao_teclar_enter)
        self.caixa_sugestoes.bind("<ButtonRelease-1>", self._ao_clicar_sugestao)

    def definir_dados(self, lista_dados: List[Dict[str, str]]):
        self._lista_prontuarios.clear()
        self._lista_nomes.clear()
        self._mapa_prontuarios.clear()
        self._mapa_nomes.clear()
        self._mapa_exibicao.clear()

        for estudante in lista_dados:
            pront = self._padrao_prontuario_limpo.sub("", estudante["pront"])
            nome = estudante["nome"]

            self._lista_prontuarios.append(pront)
            self._lista_nomes.append(nome)
            self._mapa_prontuarios[pront] = estudante
            self._mapa_nomes[nome] = estudante

            texto_exibicao = f"{estudante['pront']} - {nome}"
            self._mapa_exibicao[texto_exibicao] = estudante["pront"]

    def _ao_liberar_tecla(self, event):
        if event.keysym in ("Up", "Down", "Return", "Enter"):
            return

        consulta = self.get().strip()
        if not consulta:
            self.caixa_sugestoes.place_forget()
            return

        self.caixa_sugestoes.delete(0, tk.END)
        estudantes_encontrados = []

        if self._padrao_prontuario.fullmatch(consulta.upper()):
            matches = process.extract(
                consulta.upper(), self._lista_prontuarios, limit=5
            )
            for pront, pontuacao in matches:
                if pontuacao > 70:
                    estudantes_encontrados.append(self._mapa_prontuarios[pront])
        else:
            matches = process.extract(consulta, self._lista_nomes, limit=5)
            for nome, pontuacao in matches:
                if pontuacao > 70:
                    estudantes_encontrados.append(self._mapa_nomes[nome])

        if estudantes_encontrados:
            for estudante in estudantes_encontrados:
                texto_exibicao = f"{estudante['pront']} - {estudante['nome']}"
                self.caixa_sugestoes.insert(tk.END, texto_exibicao)

            self.caixa_sugestoes.place(
                x=self.winfo_x(),
                y=self.winfo_y() + self.winfo_height(),
                width=self.winfo_width(),
            )
            self.caixa_sugestoes.lift()
        else:
            self.caixa_sugestoes.place_forget()

    def _mover_selecao(self, event):
        if not self.caixa_sugestoes.winfo_viewable():
            return

        indice_atual_selecao = self.caixa_sugestoes.curselection()
        novo_indice = 0

        if indice_atual_selecao:
            indice_atual = indice_atual_selecao[0]
            if event.keysym == "Down":
                novo_indice = indice_atual + 1
            elif event.keysym == "Up":
                novo_indice = indice_atual - 1

        if 0 <= novo_indice < self.caixa_sugestoes.size():
            self.caixa_sugestoes.selection_clear(0, tk.END)
            self.caixa_sugestoes.selection_set(novo_indice)
            self.caixa_sugestoes.activate(novo_indice)

    def _ao_teclar_enter(self, event):
        if (
            self.caixa_sugestoes.winfo_viewable()
            and self.caixa_sugestoes.curselection()
        ):
            self._confirmar_selecao()
        else:
            self.callback_registro()

    def _ao_clicar_sugestao(self, event):
        if self.caixa_sugestoes.curselection():
            self._confirmar_selecao()

    def _confirmar_selecao(self):
        if not self.caixa_sugestoes.curselection():
            return

        texto_exibicao_selecionado = self.caixa_sugestoes.get(
            self.caixa_sugestoes.curselection()
        )
        prontuario = self._mapa_exibicao.get(texto_exibicao_selecionado)

        if prontuario:
            self.delete(0, tk.END)
            self.insert(0, prontuario)
            self.caixa_sugestoes.place_forget()
            self.focus()
            self.callback_registro()

    def _ao_perder_foco(self, event):
        self.after(200, self.caixa_sugestoes.place_forget)


class JanelaNovaSessao(ctk.CTkToplevel):
    """
    Janela para criar uma nova sessão de refeição, com checkboxes para seleção de grupos.
    """

    def __init__(self, master, fachada: FachadaRegistro):
        super().__init__(master)
        self.master = master
        self.fachada = fachada
        self.title("Nova Sessão de Refeição")
        self.geometry("450x550")
        self.transient(master)
        self.after(100, self.grab_set)
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Refeição:").grid(
            row=0, column=0, padx=20, pady=10, sticky="w"
        )
        self.var_refeicao = ctk.StringVar(value="almoço")
        self.menu_refeicao = ctk.CTkOptionMenu(
            self, variable=self.var_refeicao, values=["almoço", "lanche"]
        )
        self.menu_refeicao.grid(row=0, column=1, padx=20, pady=10, sticky="ew")

        ctk.CTkLabel(self, text="Período:").grid(
            row=1, column=0, padx=20, pady=10, sticky="w"
        )
        self.var_periodo = ctk.StringVar(value="Integral")
        self.menu_periodo = ctk.CTkOptionMenu(
            self,
            variable=self.var_periodo,
            values=["Integral", "Matutino", "Vespertino", "Noturno"],
        )
        self.menu_periodo.grid(row=1, column=1, padx=20, pady=10, sticky="ew")

        ctk.CTkLabel(self, text="Item Servido (Lanche):").grid(
            row=2, column=0, padx=20, pady=10, sticky="w"
        )
        self.campo_item_servido = ctk.CTkEntry(self, placeholder_text="Opcional")
        self.campo_item_servido.grid(row=2, column=1, padx=20, pady=10, sticky="ew")

        ctk.CTkLabel(self, text="Data (dd/mm/aaaa):").grid(
            row=3, column=0, padx=20, pady=10, sticky="w"
        )
        self.campo_data = ctk.CTkEntry(self)
        self.campo_data.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.campo_data.grid(row=3, column=1, padx=20, pady=10, sticky="ew")

        ctk.CTkLabel(self, text="Hora (hh:mm):").grid(
            row=4, column=0, padx=20, pady=10, sticky="w"
        )
        self.campo_hora = ctk.CTkEntry(self)
        self.campo_hora.insert(0, datetime.now().strftime("%H:%M"))
        self.campo_hora.grid(row=4, column=1, padx=20, pady=10, sticky="ew")

        ctk.CTkLabel(self, text="Grupos Autorizados:").grid(
            row=5, column=0, padx=20, pady=10, sticky="nw"
        )
        self.frame_grupos = ctk.CTkScrollableFrame(
            self, label_text="Selecione os grupos"
        )
        self.frame_grupos.grid(row=5, column=1, padx=20, pady=10, sticky="nsew")
        self.grid_rowconfigure(5, weight=1)
        self.vars_grupos = {}
        self.carregar_grupos()

        frame_botoes = ctk.CTkFrame(self, fg_color="transparent")
        frame_botoes.grid(row=6, column=0, columnspan=2, padx=20, pady=20, sticky="e")
        self.botao_cancelar = ctk.CTkButton(
            frame_botoes, text="Cancelar", command=self.destroy, fg_color="gray"
        )
        self.botao_cancelar.pack(side="left", padx=10)
        self.botao_criar = ctk.CTkButton(
            frame_botoes, text="Criar Sessão", command=self.criar_sessao
        )
        self.botao_criar.pack(side="left")

    def carregar_grupos(self):
        try:
            grupos = self.fachada.listar_todos_os_grupos()
            for nome_grupo in sorted(g["nome"] for g in grupos):
                var = ctk.StringVar(value="off")
                checkbox = ctk.CTkCheckBox(
                    self.frame_grupos,
                    text=nome_grupo,
                    variable=var,
                    onvalue="on",
                    offvalue="off",
                )
                checkbox.pack(anchor="w", padx=10)
                self.vars_grupos[nome_grupo] = var
        except Exception as e:
            messagebox.showerror(
                "Erro",
                f"Não foi possível carregar a lista de grupos:\n{e}",
                parent=self,
            )

    def criar_sessao(self):
        grupos_selecionados = [
            nome for nome, var in self.vars_grupos.items() if var.get() == "on"
        ]
        dados_sessao = {
            "refeicao": self.var_refeicao.get(),
            "periodo": self.var_periodo.get(),
            "item_servido": self.campo_item_servido.get() or None,
            "data": self.campo_data.get(),
            "hora": self.campo_hora.get(),
            "grupos": grupos_selecionados,
        }
        try:
            self.master.fachada.iniciar_nova_sessao(dados_sessao)
            messagebox.showinfo(
                "Sucesso", "Nova sessão criada com sucesso!", parent=self
            )
            self.master.atualizar_lista_sessoes()
            self.destroy()
        except Exception as e:
            messagebox.showerror(
                "Erro", f"Não foi possível criar a sessão:\n{e}", parent=self
            )


class Aplicativo(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Registro de Refeições")
        self.geometry("1100x700")

        try:
            self.fachada = FachadaRegistro()
        except Exception as e:
            messagebox.showerror(
                "Erro Crítico", f"Não foi possível iniciar o back-end:\n{e}"
            )
            self.destroy()
            return

        self.id_sessao_ativa: Optional[int] = None
        self.filtro_estudante_atual = "Não Consumiram"
        self.todos_os_grupos: List[str] = []
        self.vars_grupos_autorizados: Dict[str, ctk.StringVar] = {}
        self.vars_grupos_excluidos: Dict[str, ctk.StringVar] = {}

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.frame_cabecalho = ctk.CTkFrame(self, corner_radius=0, height=40)
        self.frame_cabecalho.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.frame_cabecalho.grid_columnconfigure(0, weight=1)
        self.rotulo_sessao_ativa = ctk.CTkLabel(
            self.frame_cabecalho,
            text="Nenhuma sessão ativa",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.rotulo_sessao_ativa.grid(row=0, column=0, padx=20, pady=10)

        self.view_abas = ctk.CTkTabview(self)
        self.view_abas.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.view_abas.add("Registro")
        self.view_abas.add("Sessões")
        self.view_abas.add("Administração")

        self.criar_aba_registro()
        self.criar_aba_sessoes()
        self.criar_aba_admin()

        self.protocol("WM_DELETE_WINDOW", self.ao_fechar)
        self.carregar_dados_iniciais()

    def carregar_dados_iniciais(self):
        try:
            self.todos_os_grupos = sorted(
                [g["nome"] for g in self.fachada.listar_todos_os_grupos()]
            )
            self.popular_widgets_de_grupos()
        except Exception as e:
            messagebox.showerror(
                "Erro", f"Não foi possível carregar a lista de grupos: {e}"
            )

    def ao_fechar(self):
        if messagebox.askokcancel("Sair", "Deseja fechar a aplicação?"):
            self.fachada.fechar_conexao()
            self.destroy()

    def criar_aba_registro(self):
        aba = self.view_abas.tab("Registro")
        aba.grid_columnconfigure(0, weight=3)
        aba.grid_columnconfigure(1, weight=1)
        aba.grid_rowconfigure(0, weight=1)

        frame_principal = ctk.CTkFrame(aba)
        frame_principal.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="nsew")
        frame_principal.grid_columnconfigure(0, weight=1)
        frame_principal.grid_rowconfigure(2, weight=1)

        frame_entrada = ctk.CTkFrame(frame_principal)
        frame_entrada.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        frame_entrada.grid_columnconfigure(0, weight=1)

        self.campo_prontuario = CampoBuscaAutocomplete(
            frame_entrada,
            callback_registro=self.registrar_estudante,
            placeholder_text="Digite nome ou prontuário do estudante...",
            font=ctk.CTkFont(size=14),
        )
        self.campo_prontuario.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.botao_registrar = ctk.CTkButton(
            frame_entrada, text="Registrar Consumo", command=self.registrar_estudante
        )
        self.botao_registrar.grid(row=0, column=1, padx=10, pady=10)
        self.rotulo_status = ctk.CTkLabel(
            frame_entrada, text="", text_color="green", font=ctk.CTkFont(size=14)
        )
        self.rotulo_status.grid(row=1, column=0, columnspan=2, padx=10, sticky="w")

        frame_lista = ctk.CTkFrame(frame_principal)
        frame_lista.grid(row=1, column=0, rowspan=2, padx=10, pady=10, sticky="nsew")
        frame_lista.grid_columnconfigure(0, weight=1)
        frame_lista.grid_rowconfigure(1, weight=1)

        frame_filtro_consumo = ctk.CTkFrame(frame_lista, fg_color="transparent")
        frame_filtro_consumo.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(frame_filtro_consumo, text="Mostrar:").pack(side="left")
        self.botao_segmentado_filtro = ctk.CTkSegmentedButton(
            frame_filtro_consumo,
            values=["Não Consumiram", "Consumiram", "Todos"],
            command=self.ao_mudar_filtro,
        )
        self.botao_segmentado_filtro.set("Não Consumiram")
        self.botao_segmentado_filtro.pack(side="left", padx=10)
        self.botao_desfazer = ctk.CTkButton(
            frame_filtro_consumo,
            text="Desfazer Registro",
            command=self.desfazer_consumo,
            fg_color="darkred",
        )
        self.botao_desfazer.pack(side="right")

        estilo = ttk.Style()
        estilo.theme_use("default")
        estilo.configure(
            "Treeview",
            background="white",
            foreground="#2a2d2e",
            fieldbackground="white",#"#343638"
            borderwidth=0,
        )
        estilo.map("Treeview", background=[("selected", "#24527d")])

        self.tabela_estudantes = ttk.Treeview(
            frame_lista,
            columns=("Prontuário", "Nome", "Turma", "Status", "Hora"),
            show="headings",
        )
        self.tabela_estudantes.heading("Prontuário", text="Prontuário")
        self.tabela_estudantes.heading("Nome", text="Nome")
        self.tabela_estudantes.heading("Turma", text="Turma")
        self.tabela_estudantes.heading("Status", text="Status")
        self.tabela_estudantes.heading("Hora", text="Hora Consumo")
        self.tabela_estudantes.column("Prontuário", width=120)
        self.tabela_estudantes.column("Nome", width=300)
        self.tabela_estudantes.column("Turma", width=150)
        self.tabela_estudantes.column("Status", width=150)
        self.tabela_estudantes.column("Hora", width=100)
        self.tabela_estudantes.grid(row=1, column=0, sticky="nsew")

        self.frame_gerenciamento_grupos = ctk.CTkFrame(aba)
        self.frame_gerenciamento_grupos.grid(
            row=0, column=1, padx=(5, 10), pady=10, sticky="nsew"
        )
        self.frame_gerenciamento_grupos.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.frame_gerenciamento_grupos,
            text="Grupos Autorizados na Sessão",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=0, column=0, padx=10, pady=(10, 0))
        self.frame_scroll_grupos_autorizados = ctk.CTkScrollableFrame(
            self.frame_gerenciamento_grupos
        )
        self.frame_scroll_grupos_autorizados.grid(
            row=1, column=0, padx=10, pady=5, sticky="nsew"
        )
        self.botao_atualizar_grupos = ctk.CTkButton(
            self.frame_gerenciamento_grupos,
            text="Atualizar Grupos",
            command=self.atualizar_grupos_da_sessao,
        )
        self.botao_atualizar_grupos.grid(row=2, column=0, padx=10, pady=10)

        self.label_filtro_exclusao = ctk.CTkLabel(
            self.frame_gerenciamento_grupos,
            text="Filtro de Exclusão (Almoço)",
            font=ctk.CTkFont(weight="bold"),
        )
        self.label_filtro_exclusao.grid(row=3, column=0, padx=10, pady=(10, 0))
        ctk.CTkLabel(
            self.frame_gerenciamento_grupos,
            text="(não salva na sessão, só afeta a visualização)",
            font=ctk.CTkFont(size=10),
        ).grid(row=4, column=0, padx=10, pady=(0, 5))
        self.frame_scroll_grupos_excluidos = ctk.CTkScrollableFrame(
            self.frame_gerenciamento_grupos
        )
        self.frame_scroll_grupos_excluidos.grid(
            row=5, column=0, padx=10, pady=5, sticky="nsew"
        )
        self.botao_aplicar_filtro_exclusao = ctk.CTkButton(
            self.frame_gerenciamento_grupos,
            text="Aplicar/Remover Filtro",
            command=lambda: (self.atualizar_lista_estudantes(),
                             self._atualizar_dados_autocomplete()),
        )
        self.botao_aplicar_filtro_exclusao.grid(row=6, column=0, padx=10, pady=10)

        self.frame_gerenciamento_grupos.grid_rowconfigure(1, weight=1)
        self.frame_gerenciamento_grupos.grid_rowconfigure(5, weight=1)
        self.desabilitar_gerenciamento_grupos()

    def popular_widgets_de_grupos(self):
        for widget in self.frame_scroll_grupos_autorizados.winfo_children():
            widget.destroy()
        for widget in self.frame_scroll_grupos_excluidos.winfo_children():
            widget.destroy()
        self.vars_grupos_autorizados.clear()
        self.vars_grupos_excluidos.clear()

        for nome_grupo in self.todos_os_grupos:
            var_auth = ctk.StringVar(value="off")
            ctk.CTkCheckBox(
                self.frame_scroll_grupos_autorizados,
                text=nome_grupo,
                variable=var_auth,
                onvalue="on",
                offvalue="off",
            ).pack(anchor="w", padx=10)
            self.vars_grupos_autorizados[nome_grupo] = var_auth

            var_excl = ctk.StringVar(value="off")
            ctk.CTkCheckBox(
                self.frame_scroll_grupos_excluidos,
                text=nome_grupo,
                variable=var_excl,
                onvalue="on",
                offvalue="off",
            ).pack(anchor="w", padx=10)
            self.vars_grupos_excluidos[nome_grupo] = var_excl

    # NOVO MÉTODO (adicione este método dentro da classe Aplicativo)
    def _alterar_estado_widgets_recursivamente(self, parent_widget, novo_estado: str):
        """
        Percorre recursivamente todos os widgets filhos de um widget pai
        e altera o estado apenas dos que são interativos.
        """
        for child in parent_widget.winfo_children():
            # Verifica se o widget é de um tipo que pode ser desabilitado
            if isinstance(
                child, (ctk.CTkButton, ctk.CTkCheckBox, ctk.CTkEntry, ctk.CTkOptionMenu)
            ):
                child.configure(state=novo_estado)

            # Chama a função recursivamente para os filhos do filho atual
            self._alterar_estado_widgets_recursivamente(child, novo_estado)

    # MÉTODO CORRIGIDO (substitua a versão antiga por esta)
    def habilitar_gerenciamento_grupos(self, tipo_refeicao: str):
        """Habilita os widgets de gerenciamento de grupos e ajusta a visibilidade."""
        self._alterar_estado_widgets_recursivamente(
            self.frame_gerenciamento_grupos, "normal"
        )

        if tipo_refeicao == "almoço":
            self.label_filtro_exclusao.grid()
            self.frame_scroll_grupos_excluidos.grid()
            self.botao_aplicar_filtro_exclusao.grid()
        else:
            self.label_filtro_exclusao.grid_remove()
            self.frame_scroll_grupos_excluidos.grid_remove()
            self.botao_aplicar_filtro_exclusao.grid_remove()

    # MÉTODO CORRIGIDO (substitua a versão antiga por esta)
    def desabilitar_gerenciamento_grupos(self):
        """Desabilita todos os widgets interativos no painel de gerenciamento de grupos."""
        self._alterar_estado_widgets_recursivamente(
            self.frame_gerenciamento_grupos, "disabled"
        )

    def _atualizar_dados_autocomplete(self):
        try:
            grupos_excluidos = {
                nome
                for nome, var in self.vars_grupos_excluidos.items()
                if var.get() == "on"
            }
            estudantes_pesquisaveis = (
                self.fachada.obter_estudantes_pesquisaveis_para_sessao(
                    grupos_excluidos=grupos_excluidos
                )
            )
            self.campo_prontuario.definir_dados(estudantes_pesquisaveis)
        except Exception as e:
            print(f"Erro ao atualizar autocomplete: {e}")
            self.campo_prontuario.definir_dados([])

    def registrar_estudante(self):
        prontuario = self.campo_prontuario.get().strip()
        if not prontuario:
            return

        try:
            resultado = self.fachada.registrar_consumo(prontuario)
            if resultado.get("autorizado"):
                self.rotulo_status.configure(
                    text=f"✅ {resultado.get('aluno')} autorizado(a). Motivo: {resultado.get('motivo')}",
                    text_color="green",
                )
                self.atualizar_lista_estudantes()
                self._atualizar_dados_autocomplete()
            else:
                self.rotulo_status.configure(
                    text=f"❌ Acesso Negado. Motivo: {resultado.get('motivo')}",
                    text_color="red",
                )
        except ErroSessaoNaoAtiva:
            messagebox.showwarning(
                "Aviso",
                "Nenhuma sessão ativa. Por favor, selecione uma na aba 'Sessões'.",
            )
        except Exception as e:
            messagebox.showerror("Erro", f"Ocorreu um erro ao registrar:\n{e}")

        self.campo_prontuario.delete(0, "end")
        self.campo_prontuario.focus()

    def atualizar_lista_estudantes(self):
        for item in self.tabela_estudantes.get_children():
            self.tabela_estudantes.delete(item)
        if not self.id_sessao_ativa:
            return

        try:
            grupos_excluidos = {
                nome
                for nome, var in self.vars_grupos_excluidos.items()
                if var.get() == "on"
            }
            mapa_consumido = {
                "Não Consumiram": False,
                "Consumiram": True,
                "Todos": None,
            }
            estudantes = self.fachada.obter_estudantes_para_sessao(
                consumido=mapa_consumido.get(self.filtro_estudante_atual),
                grupos_excluidos=grupos_excluidos,
            )
            for estudante in estudantes:
                self.tabela_estudantes.insert(
                    "",
                    "end",
                    iid=estudante.get("id_consumo"),
                    values=(
                        estudante.get("pront"),
                        estudante.get("nome"),
                        estudante.get("turma"),
                        estudante.get("status"),
                        estudante.get("hora_registro"),
                    ),
                )
        except Exception as e:
            messagebox.showerror(
                "Erro", f"Não foi possível carregar a lista de estudantes:\n{e}"
            )

    def ao_mudar_filtro(self, valor):
        self.filtro_estudante_atual = valor
        self.atualizar_lista_estudantes()
        self._atualizar_dados_autocomplete()

    def desfazer_consumo(self):
        itens_selecionados = self.tabela_estudantes.selection()
        if not itens_selecionados:
            messagebox.showwarning(
                "Aviso", "Selecione um registro de consumo na lista para desfazer."
            )
            return

        id_consumo_str = itens_selecionados[0]
        if not id_consumo_str or not id_consumo_str.isdigit():
            messagebox.showwarning(
                "Aviso",
                "Este estudante ainda não consumiu. Não há registro para desfazer.",
            )
            return

        id_consumo = int(id_consumo_str)
        if messagebox.askyesno(
            "Confirmar", "Tem certeza que deseja desfazer este registro de consumo?"
        ):
            try:
                self.fachada.desfazer_consumo(id_consumo)
                self.rotulo_status.configure(
                    text="✅ Registro desfeito com sucesso.", text_color="green"
                )
                self.atualizar_lista_estudantes()
                self._atualizar_dados_autocomplete()
            except Exception as e:
                messagebox.showerror(
                    "Erro", f"Não foi possível desfazer o registro:\n{e}"
                )

    def criar_aba_sessoes(self):
        aba = self.view_abas.tab("Sessões")
        aba.grid_columnconfigure(0, weight=1)
        aba.grid_rowconfigure(0, weight=1)

        frame_sessoes = ctk.CTkFrame(aba)
        frame_sessoes.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        frame_sessoes.grid_columnconfigure(0, weight=1)
        frame_sessoes.grid_rowconfigure(0, weight=1)

        self.tabela_sessoes = ttk.Treeview(
            frame_sessoes,
            columns=("ID", "Refeição", "Data", "Hora", "Item", "Grupos"),
            show="headings",
        )
        self.tabela_sessoes.heading("ID", text="ID")
        self.tabela_sessoes.heading("Refeição", text="Refeição")
        self.tabela_sessoes.heading("Data", text="Data")
        self.tabela_sessoes.heading("Hora", text="Hora")
        self.tabela_sessoes.heading("Item", text="Item Servido")
        self.tabela_sessoes.heading("Grupos", text="Grupos de Exceção")
        self.tabela_sessoes.column("ID", width=50)
        self.tabela_sessoes.grid(row=0, column=0, columnspan=2, sticky="nsew")

        frame_botoes = ctk.CTkFrame(aba)
        frame_botoes.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        self.botao_nova_sessao = ctk.CTkButton(
            frame_botoes, text="Nova Sessão", command=self.abrir_janela_nova_sessao
        )
        self.botao_nova_sessao.pack(side="left", padx=10, pady=10)
        self.botao_definir_ativa = ctk.CTkButton(
            frame_botoes,
            text="Definir como Sessão Ativa",
            command=self.definir_sessao_ativa,
        )
        self.botao_definir_ativa.pack(side="left", padx=10, pady=10)
        self.botao_atualizar_sessoes = ctk.CTkButton(
            frame_botoes,
            text="Atualizar Lista",
            command=self.atualizar_lista_sessoes,
            fg_color="gray",
        )
        self.botao_atualizar_sessoes.pack(side="right", padx=10, pady=10)
        self.atualizar_lista_sessoes()

    def atualizar_lista_sessoes(self):
        for item in self.tabela_sessoes.get_children():
            self.tabela_sessoes.delete(item)
        try:
            sessoes = self.fachada.listar_todas_sessoes()
            for sessao in sorted(
                sessoes, key=lambda s: (s["data"], s["hora"]), reverse=True
            ):
                grupos_str = ", ".join(sessao.get("grupos", []))
                self.tabela_sessoes.insert(
                    "",
                    "end",
                    iid=sessao["id"],
                    values=(
                        sessao["id"],
                        sessao["refeicao"].capitalize(),
                        sessao["data"],
                        sessao["hora"],
                        sessao.get("item_servido", "N/A"),
                        grupos_str,
                    ),
                )
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível carregar as sessões:\n{e}")

    def definir_sessao_ativa(self):
        itens_selecionados = self.tabela_sessoes.selection()
        if not itens_selecionados:
            messagebox.showwarning("Aviso", "Selecione uma sessão na lista.")
            return
        id_sessao = int(itens_selecionados[0])
        try:
            self.fachada.definir_sessao_ativa(id_sessao)
            self.id_sessao_ativa = id_sessao
            detalhes = self.fachada.obter_detalhes_sessao_ativa()

            self.rotulo_sessao_ativa.configure(
                text=f"Sessão Ativa: {detalhes['refeicao'].capitalize()} de {detalhes['data']} às {detalhes['hora']} (ID: {detalhes['id']})"
            )

            self.habilitar_gerenciamento_grupos(detalhes["refeicao"])

            grupos_ativos = detalhes.get("grupos", [])
            for nome, var in self.vars_grupos_autorizados.items():
                var.set("on" if nome in grupos_ativos else "off")
            for var in self.vars_grupos_excluidos.values():
                var.set("off")

            self._atualizar_dados_autocomplete()
            messagebox.showinfo("Sucesso", "Sessão definida como ativa!")
            self.atualizar_lista_estudantes()
            self.view_abas.set("Registro")
        except Exception as e:
            messagebox.showerror(
                "Erro", f"Não foi possível definir a sessão ativa:\n{e}"
            )

    def abrir_janela_nova_sessao(self):
        JanelaNovaSessao(self, self.fachada)

    def atualizar_grupos_da_sessao(self):
        if not self.id_sessao_ativa:
            messagebox.showwarning("Aviso", "Nenhuma sessão ativa selecionada.")
            return
        grupos_selecionados = [
            nome
            for nome, var in self.vars_grupos_autorizados.items()
            if var.get() == "on"
        ]
        if messagebox.askyesno(
            "Confirmar",
            "Deseja atualizar a lista de grupos autorizados para esta sessão?",
        ):
            try:
                self.fachada.atualizar_grupos_sessao(grupos_selecionados)
                messagebox.showinfo("Sucesso", "Grupos da sessão atualizados!")
                self.atualizar_lista_estudantes()
                self._atualizar_dados_autocomplete()
            except Exception as e:
                messagebox.showerror(
                    "Erro", f"Não foi possível atualizar os grupos:\n{e}"
                )

    def criar_aba_admin(self):
        aba = self.view_abas.tab("Administração")
        aba.grid_columnconfigure(0, weight=1)

        frame_google = ctk.CTkFrame(aba)
        frame_google.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        frame_google.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            frame_google,
            text="Sincronização com Google Sheets",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, pady=10)
        self.botao_sincronizar_de = ctk.CTkButton(
            frame_google,
            text="Baixar Dados (Estudantes e Reservas)",
            command=self.sincronizar_do_google,
        )
        self.botao_sincronizar_de.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        self.botao_sincronizar_para = ctk.CTkButton(
            frame_google,
            text="Enviar Consumo da Sessão Ativa",
            command=self.sincronizar_para_google,
        )
        self.botao_sincronizar_para.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        frame_exportar = ctk.CTkFrame(aba)
        frame_exportar.grid(row=1, column=0, padx=20, pady=20, sticky="ew")
        frame_exportar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            frame_exportar,
            text="Exportação Local",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, pady=10)
        self.botao_exportar = ctk.CTkButton(
            frame_exportar,
            text="Exportar Sessão Ativa para Excel (.xlsx)",
            command=self.exportar_para_excel,
        )
        self.botao_exportar.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        self.rotulo_status_admin = ctk.CTkLabel(aba, text="")
        self.rotulo_status_admin.grid(row=2, column=0, padx=20, pady=10, sticky="w")

    def sincronizar_do_google(self):
        if not messagebox.askyesno(
            "Confirmar",
            "Isso irá baixar e atualizar os dados de estudantes e reservas. Deseja continuar?",
        ):
            return
        self.rotulo_status_admin.configure(
            text="Sincronizando... Isso pode levar um momento."
        )
        self.update_idletasks()
        try:
            self.fachada.sincronizar_do_google_sheets()
            messagebox.showinfo(
                "Sucesso", "Dados baixados e sincronizados com sucesso!"
            )
            self.rotulo_status_admin.configure(text="Sincronização concluída.")
            self.carregar_dados_iniciais()  # Atualiza a lista de grupos na UI
        except Exception as e:
            messagebox.showerror("Erro", f"Falha na sincronização:\n{e}")
            self.rotulo_status_admin.configure(text="Falha na sincronização.")

    def sincronizar_para_google(self):
        if not self.id_sessao_ativa:
            messagebox.showwarning(
                "Aviso",
                "Nenhuma sessão ativa. Selecione uma sessão para enviar os dados de consumo.",
            )
            return
        self.rotulo_status_admin.configure(
            text="Enviando dados para o Google Sheets..."
        )
        self.update_idletasks()
        try:
            self.fachada.sincronizar_para_google_sheets()
            messagebox.showinfo(
                "Sucesso", "Dados de consumo da sessão ativa enviados com sucesso!"
            )
            self.rotulo_status_admin.configure(text="Envio concluído.")
        except ErroNucleoRegistro as e:
            messagebox.showerror("Erro", f"Falha no envio:\n{e}")
            self.rotulo_status_admin.configure(text="Falha no envio.")

    def exportar_para_excel(self):
        if not self.id_sessao_ativa:
            messagebox.showwarning(
                "Aviso", "Nenhuma sessão ativa. Selecione uma sessão para exportar."
            )
            return
        self.rotulo_status_admin.configure(text="Exportando para Excel...")
        self.update_idletasks()
        try:
            caminho_arquivo = self.fachada.exportar_sessao_para_xlsx()
            messagebox.showinfo(
                "Sucesso", f"Arquivo Excel salvo com sucesso em:\n{caminho_arquivo}"
            )
            self.rotulo_status_admin.configure(text="Exportação concluída.")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha na exportação:\n{e}")
            self.rotulo_status_admin.configure(text="Falha na exportação.")


if __name__ == "__main__":
    app = Aplicativo()
    app.mainloop()
