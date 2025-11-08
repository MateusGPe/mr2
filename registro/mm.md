Olá! Como vai?

Com certeza! Analisei os arquivos e o objetivo de utilizar o padrão Facade para centralizar e simplificar o acesso à lógica de negócio. A `FachadaRegistro` realmente ajuda a desacoplar a UI do núcleo do sistema.

Abaixo estão os arquivos modificados. Onde a fachada (`FachadaRegistro`) não fornecia um método diretamente equivalente à funcionalidade original (principalmente no que diz respeito à persistência de sessão em `session.json` e ao cálculo de métricas), eu comentei o código original com a anotação `TODO` e uma breve descrição, conforme solicitado.

---
### Arquivos Modificados

#### **`registro/view/metrics_dialog.py`**
Nenhuma alteração foi necessária neste arquivo, pois ele apenas instancia o `MetricsPanel`. As modificações relevantes estão no próprio painel.

```python
# registro/view/metrics_dialog.py
import tkinter as tk
from tkinter import ttk
import logging

# TODO: A fachada do núcleo não possui métodos para interagir com o MetricsPanel.
# A referência ao SessionManager foi alterada para FachadaRegistro para consistência,
# mas a funcionalidade de métricas precisaria ser adicionada à fachada.
from registro.nucleo.facade import FachadaRegistro
from registro.view.metrics_panel import MetricsPanel # Re-use the panel logic

logger = logging.getLogger(__name__)

class MetricsDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, fachada_nucleo: FachadaRegistro, **kwargs):
        super().__init__(master, **kwargs)
        self.fachada_nucleo = fachada_nucleo

        self.title("Painel de Métricas")
        # Make the dialog modal (optional, but common for such info dialogs)
        # self.grab_set() # This makes it modal
        self.transient(master) # Makes it appear on top of the master window

        # Set a minsize for better default appearance
        self.minsize(450, 350)

        self._create_widgets()
        self._center_window()

        # Load metrics when the dialog is created
        # The panel itself handles the "Calculando..." state
        self.metrics_panel.load_metrics()

    def _create_widgets(self):
        # Main container frame within the dialog
        container_frame = ttk.Frame(self, padding="10")
        container_frame.pack(fill=tk.BOTH, expand=True)

        # Instantiate the MetricsPanel
        self.metrics_panel = MetricsPanel(container_frame, fachada_nucleo=self.fachada_nucleo)
        self.metrics_panel.pack(fill=tk.BOTH, expand=True, pady=(0, 10)) # Add some padding below panel

        # Close button
        close_button = ttk.Button(container_frame, text="Fechar", command=self.destroy)
        close_button.pack(pady=5)


    def _center_window(self):
        """Centers the dialog on the screen or over its master."""
        self.update_idletasks() # Update geometry
        
        master = self.master
        master_x = master.winfo_x()
        master_y = master.winfo_y()
        master_width = master.winfo_width()
        master_height = master.winfo_height()

        dialog_width = self.winfo_width()
        dialog_height = self.winfo_height()

        # Calculate position to center over master
        # If master is not the root, this will center over the specific master widget
        # If master is root, it centers on screen based on root's position
        position_x = master_x + (master_width // 2) - (dialog_width // 2)
        position_y = master_y + (master_height // 2) - (dialog_height // 2)

        # Ensure it's not off-screen (simple check)
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        if position_x + dialog_width > screen_width:
            position_x = screen_width - dialog_width
        if position_y + dialog_height > screen_height:
            position_y = screen_height - dialog_height
        if position_x < 0:
            position_x = 0
        if position_y < 0:
            position_y = 0
            
        self.geometry(f"{dialog_width}x{dialog_height}+{position_x}+{position_y}")


# --- Example Usage (for testing this dialog standalone) ---
if __name__ == '__main__':
    # This is a MOCK SessionManager for standalone testing.
    # In your app, you'd pass the real one.
    class MockSessionManager:
        def __init__(self):
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from registro.model.tables import Base # Your actual tables
            
            DATABASE_URL = "sqlite:///:memory:"
            # DATABASE_URL = "sqlite:///config/registro.db" # If you have a test db

            engine = create_engine(DATABASE_URL)
            Base.metadata.create_all(engine)
            
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            self.database_session = SessionLocal()
            print("Mock DB Session created.")
            # self._populate_dummy_data() # Optional: Add dummy data for testing

        def _populate_dummy_data(self):
            from registro.model.tables import Student, Reserve, Consumption, Session
            from datetime import datetime, timedelta

            s1 = Student(pront="S1", nome="Alice")
            s2 = Student(pront="S2", nome="Bob")
            self.database_session.add_all([s1, s2])
            self.database_session.commit()

            sess1_data = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            sess1 = Session(refeicao="almoço", data=sess1_data, hora="12:00", groups='["Turma A"]')
            self.database_session.add(sess1)
            self.database_session.commit()

            r1 = Reserve(student_id=s1.id, data=sess1_data, dish="Prato A", snacks=False, canceled=False)
            self.database_session.add(r1)
            self.database_session.commit()
            
            c1 = Consumption(student_id=s1.id, session_id=sess1.id, consumption_time="12:05:00", reserve_id=r1.id, consumed_without_reservation=False)
            c2 = Consumption(student_id=s2.id, session_id=sess1.id, consumption_time="12:10:00", consumed_without_reservation=True)
            self.database_session.add_all([c1,c2])
            self.database_session.commit()
            print("Dummy data populated.")


    logging.basicConfig(level=logging.DEBUG)
    
    root = tk.Tk()
    root.title("Aplicação Principal")
    root.geometry("800x600")

    # This example cannot run standalone anymore as it depends on the facade
    # which is not mocked here.
    # mock_sm = MockSessionManager()

    def open_metrics_dialog():
        # dialog = MetricsDialog(root, session_manager=mock_sm)
        print("TODO: Cannot open dialog without a real facade instance.")

    open_button = ttk.Button(root, text="Abrir Métricas", command=open_metrics_dialog)
    open_button.pack(pady=50)

    # A label to show the main window is active
    ttk.Label(root, text="Esta é a janela principal da aplicação.").pack(pady=20)

    root.mainloop()
```

---
#### **`registro/view/action_search_panel.py`**
As chamadas diretas ao `SessionManager` foram substituídas por chamadas aos métodos da fachada. Foi necessário fazer `TODO` na obtenção da lista de prontuários já servidos.

```python
# ----------------------------------------------------------------------------
# File: registro/view/action_search_panel.py (Painel de Ação/Busca)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>
"""
Define o painel esquerdo da interface, contendo busca, lista de elegíveis,
preview e botão de registro.
"""
import logging
import re
import tkinter as tk
from datetime import datetime
from tkinter import messagebox
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

import ttkbootstrap as ttk
from fuzzywuzzy import fuzz
from ttkbootstrap.constants import (
    DANGER,
    DEFAULT,
    DISABLED,
    INFO,
    LEFT,
    NORMAL,
    SUCCESS,
    WARNING,
    W,
    X,
)

from registro.control.constants import PRONTUARIO_CLEANUP_REGEX, UI_TEXTS
from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.exceptions import ErroSessaoNaoAtiva
from registro.view.simple_treeview import SimpleTreeView

# Evita importação circular para type hinting
if TYPE_CHECKING:
    # Importa apenas para checagem de tipo, não em tempo de execução
    from registro.view.registration_app import RegistrationApp

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# Painel de Ação e Busca (Esquerda)
# ----------------------------------------------------------------------------


class ActionSearchPanel(ttk.Frame):
    """
    Painel contendo a barra de busca, lista de alunos elegíveis, preview
    e botão de registro.
    """

    SEARCH_DEBOUNCE_DELAY = 350  # ms para aguardar antes de buscar

    def __init__(
        self,
        master: tk.Widget,
        app: "RegistrationApp",  # Usa o type hint
        fachada_nucleo: "FachadaRegistro",
    ):
        """
        Inicializa o painel de Ação/Busca.

        Args:
            master: O widget pai (geralmente o PanedWindow).
            app: Referência à instância principal da RegistrationApp.
            fachada_nucleo: Instância da FachadaRegistro para acesso aos dados.
        """
        super().__init__(master, padding=10)
        self._app = app  # Referência à app principal para callbacks/acesso
        self._fachada = fachada_nucleo

        # --- Atributos de Estado e Widgets Internos ---
        self._search_after_id: Optional[str] = None  # ID do timer do debounce
        # Cache dos resultados da busca atual
        self._current_eligible_matches_data: List[Dict[str, Any]] = []
        # Dados do aluno selecionado na lista
        self._selected_eligible_data: Optional[Dict[str, Any]] = None

        # Widgets (inicializados nos métodos _create_*)
        self._search_entry_var: tk.StringVar = tk.StringVar()
        self._search_entry: Optional[ttk.Entry] = None
        self._clear_button: Optional[ttk.Button] = None
        self._eligible_students_tree: Optional[SimpleTreeView] = None
        self._selected_student_label: Optional[ttk.Label] = None
        self._register_button: Optional[ttk.Button] = None
        self._action_feedback_label: Optional[ttk.Label] = None

        # Configuração do Grid interno do painel
        # Área da lista expande verticalmente
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)  # Expansão horizontal

        # Criação dos widgets internos
        self._create_search_bar()
        self._create_eligible_list()
        self._create_preview_area()
        self._create_action_area()

        # Bindings de eventos
        if self._search_entry:
            self._search_entry.bind(
                "<Return>", lambda _: self._register_selected_eligible()
            )
            self._search_entry.bind("<Down>", lambda _: self._select_next_eligible(1))
            self._search_entry.bind("<Up>", lambda _: self._select_next_eligible(-1))
            self._search_entry.bind(
                "<Escape>", lambda _: self._search_entry_var.set("")
            )  # Limpa busca
        if self._eligible_students_tree:
            self._eligible_students_tree.view.bind(
                "<<TreeviewSelect>>", self._on_eligible_student_select
            )
            self._eligible_students_tree.view.bind(
                "<Double-1>", lambda _: self._register_selected_eligible()
            )

    @property
    def search_after_id(self) -> Optional[str]:
        """Retorna o ID do timer de debounce atual."""
        return self._search_after_id

    @search_after_id.setter
    def search_after_id(self, value: Optional[str]):
        """Define o ID do timer de debounce."""
        self._search_after_id = value

    def _create_search_bar(self):
        """Cria a barra de busca com entrada e botão de limpar."""
        search_bar = ttk.Frame(self)
        search_bar.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        search_bar.grid_columnconfigure(0, weight=1)  # Entry expande

        # Campo de entrada da busca
        self._search_entry = ttk.Entry(
            search_bar,
            textvariable=self._search_entry_var,
            font=(None, 12),
            bootstyle=INFO,  # type: ignore
        )
        self._search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        # Associa a função de debounce à mudança no texto
        self._search_entry_var.trace_add("write", self._on_search_entry_change)

        # Botão para limpar a busca
        self._clear_button = ttk.Button(
            search_bar,
            text=UI_TEXTS.get("clear_search_button", "❌"),
            width=3,
            command=self.clear_search,  # Chama método local
            bootstyle="danger-outline",  # type: ignore
        )
        self._clear_button.grid(row=0, column=1)

    def _create_eligible_list(self):
        """Cria a tabela (SimpleTreeView) para exibir os alunos elegíveis."""
        eligible_frame = ttk.Labelframe(
            self, text=UI_TEXTS.get("eligible_students_label", "Alunos Elegíveis"), padding=(5, 5)
        )
        # Posiciona abaixo da busca
        eligible_frame.grid(row=2, column=0, sticky="nsew", pady=(10, 10))
        eligible_frame.grid_rowconfigure(0, weight=1)  # Treeview expande
        eligible_frame.grid_columnconfigure(0, weight=1)

        # Definição das colunas usando UI_TEXTS
        elig_cols = [
            {
                "text": UI_TEXTS.get("col_nome_eligible", "Nome"),
                "stretch": True,
                "iid": "name",
            },
            {
                "text": UI_TEXTS.get("col_info_eligible", "Turma | Pront"),
                "width": 160,
                "anchor": W,
                "iid": "info",
                "minwidth": 100,
            },
            {
                "text": UI_TEXTS.get("col_dish_eligible", "Prato/Status"),
                "width": 130,
                "anchor": W,
                "iid": "dish",
                "minwidth": 80,
            },
        ]
        # Cria a instância da SimpleTreeView
        self._eligible_students_tree = SimpleTreeView(
            master=eligible_frame, coldata=elig_cols, height=10  # Ajustar altura
        )
        self._eligible_students_tree.grid(row=0, column=0, sticky="nsew")

    def _create_preview_area(self):
        """Cria a área para exibir informações do aluno selecionado."""
        preview_frame = ttk.Frame(self, padding=(0, 0))
        # Posiciona abaixo da lista de elegíveis
        preview_frame.grid(row=3, column=0, sticky="ew", pady=(5, 0))
        # Label para o preview
        self._selected_student_label = ttk.Label(
            preview_frame,
            text=UI_TEXTS.get("select_student_preview", "Selecione um aluno da lista."),
            justify=LEFT,
            bootstyle="inverse-info",  # type: ignore
            wraplength=350,  # Quebra linha para nomes/turmas longas
            style="Preview.TLabel"  # Aplica estilo customizado se definido
        )
        self._selected_student_label.pack(fill=X, expand=True)

    def _create_action_area(self):
        """Cria a área com o botão de registrar e o label de feedback."""
        action_frame = ttk.Frame(self)
        # Posiciona *acima* da lista de elegíveis (row=1)
        action_frame.grid(row=1, column=0, sticky="ew", pady=(5, 5))  # Adiciona padding inferior
        action_frame.columnconfigure(1, weight=1)  # Botão registrar expande

        # Botão de Registrar
        self._register_button = ttk.Button(
            action_frame,
            text=UI_TEXTS.get("register_selected_button", "Registrar Selecionado"),
            command=self._register_selected_eligible,  # Chama método local
            bootstyle="success",  # type: ignore
            state=DISABLED,  # Começa desabilitado
        )
        # Coloca o botão à direita
        self._register_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        # Label para feedback da última ação (registro, erro, etc.)
        self._action_feedback_label = ttk.Label(
            action_frame,
            text="",
            # width=35, # Largura pode ser controlada pelo grid/pack
            anchor=W,
            style="Feedback.TLabel",  # Usa estilo customizado
        )
        # Coloca o feedback à esquerda
        self._action_feedback_label.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        action_frame.columnconfigure(0, weight=2)  # Dá mais espaço para o feedback

    # --- Métodos Públicos (Controle Externo) ---

    def clear_search(self, *_):
        """Limpa o campo de busca, a lista de resultados e o estado relacionado."""
        logger.debug("Limpando busca no painel de ação.")
        # Limpa a variável Tk (dispara _on_search_entry_change)
        if self._search_entry:
            self._search_entry_var.set("")
            # _on_search_entry_change cuidará de limpar a tabela e resetar estados
            self.focus_entry()  # Foca de volta no campo após limpar
        else:
            logger.warning("Tentativa de limpar busca com campo não inicializado.")

    def focus_entry(self):
        """Coloca o foco no campo de busca."""
        if self._search_entry:
            # Usa after para garantir que o widget esteja pronto
            self.after(50, self._search_entry.focus_set)
            logger.debug("Foco agendado para o campo de busca.")
        else:
            logger.warning("Tentativa de focar campo de busca não inicializado.")

    def refresh_results(self):
        """Força a re-execução da busca atual."""
        logger.debug("Atualizando resultados da busca.")
        # Cancela qualquer busca pendente antes de forçar uma nova
        if self._search_after_id is not None:
            self.after_cancel(self._search_after_id)
            self._search_after_id = None
        self._perform_actual_search()  # Executa a busca imediatamente

    def disable_controls(self):
        """Desabilita os controles do painel (quando não há sessão ativa)."""
        if self._search_entry:
            self._search_entry.config(state=DISABLED)
            self._search_entry_var.set("")  # Limpa o texto também
        if self._clear_button:
            self._clear_button.config(state=DISABLED)
        if self._register_button:
            self._register_button.config(state=DISABLED)
        if self._eligible_students_tree:
            self._eligible_students_tree.delete_rows()
        self._selected_eligible_data = None
        self._current_eligible_matches_data = []  # Limpa cache
        self._update_preview_label()
        if self._action_feedback_label:
            self._action_feedback_label.config(text="")
        logger.debug("Controles do painel de ação desabilitados.")

    def enable_controls(self):
        """Habilita os controles do painel (quando uma sessão está ativa)."""
        if self._search_entry:
            self._search_entry.config(state=NORMAL)
        if self._clear_button:
            self._clear_button.config(state=NORMAL)
        # Botão de registrar continua DISABLED até selecionar alguém
        if self._register_button:
            self._register_button.config(state=DISABLED)
        logger.debug("Controles do painel de ação habilitados.")
        self.focus_entry()  # Coloca foco na busca ao habilitar

    # --- Métodos Internos (Lógica do Painel) ---

    def _on_search_entry_change(self, *_):
        """Callback chamado quando o texto da busca muda (com debounce)."""
        # Cancela timer anterior se existir
        if self._search_after_id is not None:
            self.after_cancel(self._search_after_id)
            self._search_after_id = None  # Reseta ID do timer

        search_term = self._search_entry_var.get()
        # Se termo curto, limpa tudo e retorna
        if len(search_term) < 2:
            if self._eligible_students_tree:
                self._eligible_students_tree.delete_rows()
            self._selected_eligible_data = None
            self._current_eligible_matches_data = []
            if self._register_button:
                self._register_button.config(state=DISABLED)
            self._update_preview_label()
            if self._action_feedback_label:
                # Mensagem mais clara se o campo estiver vazio
                placeholder = (UI_TEXTS.get("search_placeholder_empty",
                                            "Digite para buscar...") if not search_term else
                               UI_TEXTS.get("search_placeholder_min_chars",
                                            "Mínimo 2 caracteres..."))
                self._action_feedback_label.config(
                    text=placeholder,
                    bootstyle=DEFAULT,
                )  # type: ignore
            return

        # Agenda a busca real após o delay
        self._search_after_id = self.after(
            self.SEARCH_DEBOUNCE_DELAY, self._perform_actual_search
        )

    def _select_next_eligible(self, delta: int = 1):
        """Seleciona o próximo item (ou anterior) na lista de elegíveis."""
        try:
            if (not self._eligible_students_tree or
                    not self._eligible_students_tree.get_children_iids()):
                return  # Sai se a árvore não existe ou está vazia

            selected_iid = self._eligible_students_tree.get_selected_iid()
            iid_list = self._eligible_students_tree.get_children_iids()
            list_len = len(iid_list)

            if not selected_iid:  # Se nada selecionado, seleciona o primeiro/último
                next_index = 0 if delta > 0 else list_len - 1
            else:
                try:
                    current_index = iid_list.index(selected_iid)
                    next_index = current_index + delta
                    # Lógica de 'wrap around' (módulo)
                    next_index %= list_len
                except ValueError:  # Se o IID selecionado não estiver na lista (improvável)
                    next_index = 0 if delta > 0 else list_len - 1

            if 0 <= next_index < list_len:
                next_iid = iid_list[next_index]
                self._eligible_students_tree.view.focus(next_iid)
                self._eligible_students_tree.view.selection_set(next_iid)
                # Garante que o item selecionado esteja visível
                self._eligible_students_tree.view.see(next_iid)
            else:
                logger.warning("Índice calculado para seleção (%d) inválido.", next_index)

        except Exception as e:
            logger.exception("Erro ao selecionar próximo item da busca: %s", e)

    def _perform_actual_search(self):
        """Executa a busca filtrada e atualiza a lista de elegíveis."""
        self._search_after_id = None  # Marca que a busca agendada rodou
        search_term = self._search_entry_var.get()
        # Checagem dupla (caso o usuário apague rápido)
        if len(search_term) < 2:
            if self._action_feedback_label:
                self._action_feedback_label.config(text="")  # Limpa feedback
            # Garante que a lista seja limpa se o termo ficou < 2
            if self._eligible_students_tree:
                self._eligible_students_tree.delete_rows()
            self._selected_eligible_data = None
            self._current_eligible_matches_data = []
            self._update_preview_label()
            if self._register_button:
                self._register_button.config(state=DISABLED)
            return

        logger.debug("Executando busca debounced por: %s", search_term)
        
        try:
            # Busca alunos elegíveis (não consumiram) da fachada
            eligible = self._fachada.obter_estudantes_para_sessao(consumido=False)
        except ErroSessaoNaoAtiva:
            logger.error("Nenhuma sessão ativa para realizar a busca.")
            eligible = []
        except Exception as e:
            logger.exception("Erro ao buscar elegíveis da fachada: %s", e)
            eligible = None

        if eligible is None:
            logger.error("Lista de elegíveis N/A durante a busca.")
            if self._action_feedback_label:
                self._action_feedback_label.config(
                    text=UI_TEXTS.get("error_loading_list", "Erro ao carregar lista"),
                    bootstyle=DANGER,
                )  # type: ignore
            if self._eligible_students_tree:
                self._eligible_students_tree.delete_rows()
            return
        
        # TODO: A fachada não fornece um método otimizado para obter apenas os
        # prontuários dos alunos já servidos (get_served_pronts).
        # Para a busca funcionar, seria necessário obter a lista completa de
        # alunos servidos e extrair os prontuários, o que pode ser ineficiente.
        # Por enquanto, a busca considerará todos os elegíveis como não servidos.
        served_pronts: Set[str] = set()
        # served = self._session_manager.get_served_pronts()

        # Renomeando colunas da fachada para as esperadas pela UI
        # A fachada retorna 'pront', 'nome', 'turma', 'prato'
        eligible_renamed = [
            {
                "Pront": s.get("pront"),
                "Nome": s.get("nome"),
                "Turma": s.get("turma"),
                "Prato": s.get("prato"),
            }
            for s in eligible
        ]


        # Realiza a busca fuzzy
        if search_term in ['todos', '---', '***']:
            matches = self._get_eligible_not_served(
                eligible_renamed, served_pronts, not_served=search_term != '***')
        else:
            matches = self._perform_fuzzy_search(search_term, eligible_renamed, served_pronts)

        # Atualiza a tabela
        if self._eligible_students_tree:
            self._update_eligible_treeview(matches)

        # Atualiza feedback e seleciona primeiro item
        if matches:
            if self._action_feedback_label:
                self._action_feedback_label.config(
                    text=UI_TEXTS.get("matches_found", "{count} resultado(s)").format(
                        count=len(matches)
                    ),
                    bootstyle=INFO,
                )  # type: ignore
            # Tenta focar e selecionar o primeiro item da lista
            try:
                if (
                    self._eligible_students_tree
                    and self._eligible_students_tree.get_children_iids()
                ):
                    first_iid = self._eligible_students_tree.get_children_iids()[0]
                    # Selecionar dispara o evento <<TreeviewSelect>> que
                    # chama _on_eligible_student_select
                    self._eligible_students_tree.view.focus(first_iid)
                    self._eligible_students_tree.view.selection_set(first_iid)
                    self._eligible_students_tree.view.see(first_iid)  # Garante visibilidade
            except Exception as e:
                logger.error("Erro ao auto-selecionar primeiro item da busca: %s", e)
        else:
            # Nenhum resultado encontrado
            if self._action_feedback_label:
                self._action_feedback_label.config(
                    text=UI_TEXTS.get(
                        "no_matches_found", "Nenhum resultado encontrado"
                    ),
                    bootstyle=WARNING,
                )  # type: ignore
            self._selected_eligible_data = None
            self._update_preview_label()
            if self._register_button:
                self._register_button.config(state=DISABLED)

    def _get_eligible_not_served(
        self, eligible_students: List[Dict[str, Any]],
        served_pronts: Set[str],
        not_served: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Filtra a lista de alunos elegíveis, retornando apenas aqueles cujo
        'Pront' não é encontrado no conjunto served_pronts. Também formata
        o campo 'info' para exibição.

        Args:
            eligible_students: Lista de dicionários representando todos os alunos potencialmente elegíveis.
                               Chaves esperadas: 'Pront', 'Nome', 'Turma'.
            served_pronts: Um set contendo as strings 'Pront' dos alunos já servidos.

        Returns:
            Uma lista de dicionários para alunos elegíveis que não foram servidos,
            com uma chave 'info' adicionada/atualizada. Ordenada alfabeticamente por 'Nome'.
        """
        logger.debug("Filtrando %d alunos elegíveis contra %d prontuários servidos.",
                     len(eligible_students), len(served_pronts))

        eligible_not_served = []
        skipped_count = 0

        for student in eligible_students:
            pront = student.get("Pront")

            # Validação básica: Pula se pront está faltando ou é None (opcional mas boa prática)
            if not pront:
                logger.warning("Aluno elegível sem prontuário encontrado, pulando: %s",
                               student.get('Nome', 'Nome Desconhecido'))
                skipped_count += 1
                continue

            # --- Lógica Principal: Verifica se foi servido ---
            if pront in served_pronts and not_served:
                skipped_count += 1
                print(f"Aluno já servido: {pront}")
                continue  # Pula este aluno, ele já foi servido

            # --- Prepara dados para o aluno que NÃO foi servido ---
            student_copy = student.copy()  # Trabalha em uma cópia

            # Formata o campo 'info' para exibição (Turma | Pront)
            display_turma = student_copy.get("Turma", "S/ Turma")  # Fornece um fallback
            # Usa o pront original para exibição, talvez com fallback se fosse None (já tratado acima)
            display_pront = pront

            student_copy["info"] = f"{display_turma} | {display_pront}"
            student_copy["score"] = 100  # Adiciona score padrão (não usado aqui, mas pode ser útil)
            # Adiciona o aluno preparado aos resultados
            eligible_not_served.append(student_copy)

        logger.debug("Filtragem concluída. %d alunos não servidos encontrados, %d pulados (servidos ou inválidos).",
                     len(eligible_not_served), skipped_count)

        # Ordena a lista final alfabeticamente por nome para exibição consistente
        eligible_not_served.sort(key=lambda x: x.get("Nome", "").lower())
        for i, student in enumerate(eligible_not_served):
            # Remove o campo 'score' se não for necessário
            student["score"] = (i*100)//len(eligible_not_served)

        self._current_eligible_matches_data = eligible_not_served
        return eligible_not_served

    def _perform_fuzzy_search(
        self,
        search_term: str,
        eligible_students: List[Dict[str, Any]],
        served_pronts: Set[str],
    ) -> List[Dict[str, Any]]:
        """
        Realiza busca fuzzy na lista de alunos elegíveis.

        Args:
            search_term: O termo a ser buscado.
            eligible_students: Lista de dicionários dos alunos elegíveis.
            served_pronts: Conjunto de prontuários já servidos.

        Returns:
            Lista de dicionários dos alunos que correspondem ao termo,
            ordenada por pontuação (score) descendente.
        """
        term_lower = search_term.lower().strip()
        matches_found = []
        # Detecta se a busca é por prontuário (apenas dígitos, 'x', espaço)
        is_pront_search = bool(re.fullmatch(
            r"(?:[a-z]{2})?[\dx\s]+", term_lower, re.IGNORECASE))

        search_key = "Pront" if is_pront_search else "Nome"
        # Limpa prefixo do prontuário para busca fuzzy apenas no número
        cleaned_search_term = (
            PRONTUARIO_CLEANUP_REGEX.sub("", term_lower)
            if is_pront_search
            else term_lower
        )
        # Define função e limiar de score (pode ser ajustado)
        match_func = fuzz.partial_ratio  # Bom para substrings
        threshold = 85 if is_pront_search else 70

        # Itera sobre alunos elegíveis
        for student in eligible_students:
            pront = student.get("Pront")
            # Pula se já servido (dupla checagem)
            if pront in served_pronts:
                continue

            # Obtém o valor a ser comparado (Nome ou Pront)
            value_to_match_raw = student.get(search_key, "")
            if not value_to_match_raw:
                continue  # Pula se valor vazio

            value_to_match_lower = value_to_match_raw.lower()
            # Limpa prontuário se for busca por prontuário para comparação fuzzy
            if is_pront_search:
                value_to_compare = PRONTUARIO_CLEANUP_REGEX.sub("", value_to_match_lower)
            else:
                value_to_compare = value_to_match_lower

            # Calcula o score de similaridade
            score = match_func(cleaned_search_term, value_to_compare)

            # Condição especial: se for busca exata por prontuário (sem fuzzy), aumenta score
            if is_pront_search and cleaned_search_term == value_to_compare:
                score = 100  # Match exato

            # Se o score for suficiente
            if score >= threshold:
                student_copy = student.copy()  # Cria cópia para não modificar original
                # Formata a coluna 'info' (Turma | Pront)
                display_turma = student.get("Turma", "S/ Turma")  # Fallback
                # Usa o prontuário original (sem limpeza) para exibição
                display_pront = pront or "S/ Pront."
                student_copy["info"] = f"{display_turma} | {display_pront}"
                student_copy["score"] = score  # Adiciona score para ordenação
                matches_found.append(student_copy)

        # Ordena por score descendente, depois alfabeticamente por nome como desempate
        matches_found.sort(key=lambda x: (-x["score"], x.get("Nome", "").lower()))
        # Atualiza o cache interno dos resultados exibidos
        self._current_eligible_matches_data = matches_found
        return matches_found

    def _update_eligible_treeview(self, matches_data: List[Dict[str, Any]]):
        """Popula a SimpleTreeView de elegíveis com os resultados da busca."""
        if not self._eligible_students_tree:
            return  # Sai se a tabela não existe

        self._eligible_students_tree.delete_rows()  # Limpa tabela
        if not matches_data:
            # Mensagem opcional quando não há resultados pode ir no feedback label
            return  # Sai se não há resultados

        # Mapeia os dados do dicionário para as colunas da SimpleTreeView ('name', 'info', 'dish')
        rowdata = []
        for m in matches_data:
            # Garante que os valores sejam strings para o Treeview
            dish_status = m.get("Prato") or UI_TEXTS.get("no_reservation_status", "Sem Reserva")
            row = (
                str(m.get("Nome", "N/A")),
                str(m.get("info", "N/A")),  # 'info' já formatado
                str(dish_status),
            )
            rowdata.append(row)

        try:
            # Constrói a tabela com os novos dados
            self._eligible_students_tree.build_table_data(rowdata=rowdata)
        except Exception as e:
            logger.exception(
                "Erro ao construir tabela de elegíveis (%s): %s", type(e).__name__, e
            )
            messagebox.showerror(
                UI_TEXTS.get("ui_error_title", "Erro de UI"),
                UI_TEXTS.get(
                    "error_display_results", "Não foi possível exibir os resultados."
                ),
                parent=self._app,
            )

    def _on_eligible_student_select(self, _=None):
        """Callback quando uma linha é selecionada na tabela de elegíveis."""
        if not self._eligible_students_tree:
            return

        selected_iid = self._eligible_students_tree.get_selected_iid()
        if selected_iid:
            try:
                # Encontra o índice do IID selecionado na lista de IIDs atual da Treeview
                # Esta abordagem é FRÁGIL se a ordem da Treeview e do cache divergir
                # (ex: por ordenação) É MELHOR obter os valores da linha selecionada e
                # encontrar o dict correspondente no cache
                selected_values = self._eligible_students_tree.get_row_values(selected_iid)
                if not selected_values:
                    raise ValueError("Não foi possível obter valores da linha selecionada.")

                # Assume que a primeira coluna (Nome) e segunda (Info com Pront) são
                # suficientes para identificar
                # Pode ser necessário ajustar se houver duplicatas exatas nesses campos
                selected_name = selected_values[0]
                selected_info = selected_values[1]  # Contém Turma | Pront

                # Encontra o dicionário correspondente no cache
                found_student_data = None
                for student_data in self._current_eligible_matches_data:
                    # Compara nome e info (que já contém prontuário formatado)
                    if (student_data.get("Nome") == selected_name and
                            student_data.get("info") == selected_info):
                        found_student_data = student_data
                        break  # Encontrou

                if found_student_data:
                    self._selected_eligible_data = found_student_data
                    # Atualiza a UI com os dados selecionados
                    self._update_preview_label()
                    if self._register_button:
                        self._register_button.config(state=NORMAL)
                    # Atualiza feedback (opcional)
                    pront = self._selected_eligible_data.get("Pront", "?")
                    if self._action_feedback_label:
                        self._action_feedback_label.config(
                            text=f"Selecionado: {pront}", bootstyle=INFO
                        )  # type: ignore
                else:
                    # Inconsistência entre Treeview e cache de dados
                    logger.error(
                        "Não foi possível encontrar dados no cache para a linha selecionada: %s",
                        selected_values
                    )
                    self._selected_eligible_data = None
                    self._update_preview_label(error=True)
                    if self._register_button:
                        self._register_button.config(state=DISABLED)
                    if self._action_feedback_label:
                        self._action_feedback_label.config(
                            text=UI_TEXTS.get("select_error", "Erro Seleção"),
                            bootstyle=DANGER,
                        )  # type: ignore

            except (ValueError, IndexError, AttributeError, tk.TclError) as e:
                # Erros ao buscar índice, acessar cache ou atualizar UI
                logger.exception(
                    "Erro ao processar seleção de elegível (IID: %s): %s",
                    selected_iid, e
                )
                self._selected_eligible_data = None
                # Mostra erro no preview
                self._update_preview_label(error=True)
                if self._register_button:
                    self._register_button.config(state=DISABLED)
                if self._action_feedback_label:
                    self._action_feedback_label.config(
                        text=UI_TEXTS.get("select_error", "Erro Seleção"),
                        bootstyle=DANGER,
                    )  # type: ignore
        else:
            # Nenhuma linha selecionada (evento de desseleção)
            self._selected_eligible_data = None
            self._update_preview_label()  # Limpa o preview
            if self._register_button:
                self._register_button.config(state=DISABLED)
            # Limpa feedback ou volta para placeholder se a busca estiver vazia
            search_term = self._search_entry_var.get()
            if self._action_feedback_label:
                if len(search_term) < 2:
                    placeholder = (UI_TEXTS.get("search_placeholder_empty",
                                                "Digite para buscar...") if not search_term else
                                   UI_TEXTS.get("search_placeholder_min_chars",
                                                "Mínimo 2 caracteres..."))
                    self._action_feedback_label.config(
                        text=placeholder, bootstyle=DEFAULT)  # type: ignore
                else:
                    # Se havia resultados, apenas limpa o feedback de seleção
                    if self._current_eligible_matches_data:
                        self._action_feedback_label.config(
                            text=UI_TEXTS.get("matches_found", "{count} resultado(s)").format(
                                count=len(self._current_eligible_matches_data)
                            ), bootstyle=INFO)  # type: ignore
                    else:
                        # Se não havia resultados, mantém a mensagem de "não encontrado"
                        self._action_feedback_label.config(
                            text=UI_TEXTS.get("no_matches_found", "Nenhum resultado encontrado"),
                            bootstyle=WARNING)  # type: ignore

    def _update_preview_label(self, error: bool = False):
        """Atualiza o label de preview com informações do aluno selecionado ou mensagens padrão."""
        if not self._selected_student_label:
            return  # Sai se o label não existe

        style = "inverse-secondary"  # Padrão neutro
        if error:
            text = UI_TEXTS.get("error_selecting_data", "Erro ao obter dados do aluno.")
            style = "inverse-danger"
        elif self._selected_eligible_data:
            # Monta o texto com os dados do aluno
            pront = self._selected_eligible_data.get("Pront", "?")
            nome = self._selected_eligible_data.get("Nome", "?")
            turma = self._selected_eligible_data.get("Turma", "S/ Turma")  # Fallback
            prato_raw = self._selected_eligible_data.get("Prato")
            prato = prato_raw if prato_raw is not None else UI_TEXTS.get(
                "no_reservation_status", "Sem Reserva")

            # Usa a string de formatação do UI_TEXTS
            text = UI_TEXTS.get(
                "selected_student_info",
                "Pront: {pront}\nNome: {nome}\nTurma: {turma}\nPrato: {prato}",
            ).format(
                pront=pront,
                nome=nome,
                turma=turma,
                prato=prato,
            )
            style = "inverse-info"
        else:
            # Texto padrão quando nada está selecionado
            text = UI_TEXTS.get(
                "select_student_preview", "Selecione um aluno da lista acima."
            )
            # Mantém o estilo padrão 'inverse-secondary'

        # Atualiza o texto e o estilo do label
        self._selected_student_label.config(text=text, bootstyle=style)  # type: ignore

    def _register_selected_eligible(self):
        """Tenta registrar o aluno atualmente armazenado em _selected_eligible_data."""
        if not self._selected_eligible_data:
            # Log em vez de messagebox, pois o botão deve estar desabilitado
            logger.warning(
                "Tentativa de registro sem aluno selecionado (botão deveria estar DISABLED).")
            # Garantir que o botão esteja desabilitado
            if self._register_button:
                self._register_button.config(state=DISABLED)
            return

        # Extrai dados necessários para o registro
        pront = self._selected_eligible_data.get("Pront")
        nome = self._selected_eligible_data.get("Nome", "?")

        # Validação básica
        if not pront:
            logger.error(
                "Não é possível registrar: Prontuário ausente ou inválido. Dados: %s",
                self._selected_eligible_data,
            )
            messagebox.showerror(
                UI_TEXTS.get("registration_error_title", "Erro no Registro"),
                UI_TEXTS.get(
                    "error_invalid_prontuario",  # Mensagem específica
                    "Prontuário do aluno selecionado está ausente ou inválido.",
                ),
                parent=self._app,
            )
            return

        logger.info("Registrando aluno elegível via painel: %s - %s", pront, nome)
        
        # --- Feedback e Atualização Pós-Registro ---
        try:
            # Chama o método de registro na fachada, que pode levantar exceções
            result = self._fachada.registrar_consumo(pront)
            logger.info("Aluno %s registrado com sucesso pela Fachada. Detalhes: %s", pront, result)
            
            # Monta a tupla de dados para notificar a app principal (para o painel de status)
            # A fachada retorna um dict com os detalhes do consumo
            student_tuple = (
                str(result.get("prontuario", pront)),
                str(result.get("nome", nome)),
                str(result.get("turma", "")),
                str(result.get("hora_consumo", datetime.now().strftime("%H:%M:%S"))),
                str(result.get("prato", "")),
            )
            
            # Notifica a App principal para atualizar o painel de status
            self._app.notify_registration_success(student_tuple)
            # Atualiza o feedback local
            if self._action_feedback_label:
                self._action_feedback_label.config(
                    text=UI_TEXTS.get(
                        "registered_feedback", "Registrado: {pront}"
                    ).format(pront=pront),
                    bootstyle=SUCCESS,
                )  # type: ignore
            # Limpa a busca, foca para o próximo registro e reseta seleção/botão
            self._selected_eligible_data = None
            self._update_preview_label()
            if self._register_button:
                self._register_button.config(state=DISABLED)
            self.clear_search()

        except Exception as e:
            # Falha no registro (já servido, estudante não encontrado, erro DB, etc.)
            logger.warning("Falha ao registrar %s via Fachada: %s", pront, e)
            
            # Verifica se o motivo foi já estar servido
            # A fachada pode levantar uma exceção específica para isso, ex: ValueError
            is_served = "já consumiu" in str(e).lower()
            if is_served:
                messagebox.showwarning(
                    UI_TEXTS.get("already_registered_title", "Já Registrado"),
                    UI_TEXTS.get(
                        "already_registered_message", "{nome} ({pront})\n"
                        "Já consta como registrado nesta sessão."
                    ).format(nome=nome, pront=pront),
                    parent=self._app,
                )
                fb_text = UI_TEXTS.get(
                    "already_registered_feedback", "JÁ REGISTRADO: {pront}"
                ).format(pront=pront)
                fb_style = WARNING
                self._selected_eligible_data = None
                self._update_preview_label()
                if self._register_button:
                    self._register_button.config(state=DISABLED)
                self.clear_search()
            else:
                # Outro erro (DB, estudante não existe, etc.)
                messagebox.showerror(
                    UI_TEXTS.get("registration_error_title", "Erro no Registro"),
                    UI_TEXTS.get(
                        "registration_error_message",
                        "Não foi possível registrar o consumo para:\n{nome} ({pront})\n"
                        "Erro: {error}"
                    ).format(nome=nome, pront=pront, error=e),
                    parent=self._app,
                )
                fb_text = UI_TEXTS.get(
                    "error_registering_feedback", "ERRO registro {pront}"
                ).format(pront=pront)
                fb_style = DANGER

            if self._action_feedback_label:
                self._action_feedback_label.config(text=fb_text, bootstyle=fb_style)  # type: ignore

            if not self._selected_eligible_data and self._register_button:
                self._register_button.config(state=DISABLED)```

---
#### **`registro/view/class_filter_dialog.py`**
A obtenção de turmas foi migrada para a fachada. A obtenção dos filtros de turma *atuais* não possui um método na fachada e foi marcada como `TODO`.

```python
# ----------------------------------------------------------------------------
# File: registro/view/class_filter_dialog.py (Diálogo de Filtro de Turmas - View)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>
"""
Fornece um diálogo modal para filtrar as turmas exibidas na tela principal
com base no status de reserva (mostrar alunos com reserva e/ou sem reserva
para cada turma selecionada).
"""
import logging
import tkinter as tk
from tkinter import BOTH, CENTER, EW, HORIZONTAL, NSEW, YES, messagebox
from typing import List, Tuple, Callable, TYPE_CHECKING, Union

import ttkbootstrap as ttk

# Importações locais
from registro.control.constants import UI_TEXTS  # Centralização de textos
from registro.nucleo.facade import FachadaRegistro

# Type checking para evitar importações circulares
if TYPE_CHECKING:
    from registro.view.registration_app import RegistrationApp  # Classe principal da GUI

logger = logging.getLogger(__name__)


def create_dialog_class_filter_section(
    master: tk.Widget, available_classes: List[str]
) -> Tuple[List[Tuple[str, tk.BooleanVar, ttk.Checkbutton]], ttk.Frame]:
    """
    Cria o frame interno do diálogo contendo os checkbuttons para cada turma,
    separados por status de reserva (com/sem).

    Args:
        master: O widget pai onde o frame será colocado.
        available_classes: Lista dos nomes das turmas disponíveis para seleção.

    Returns:
        Uma tupla contendo:
        - Uma lista de tuplas `(identificador_turma, variavel_tk, widget_checkbutton)`.
          O identificador é o nome da turma ou '#'+nome para "sem reserva".
        - O widget ttk.Frame criado contendo os checkbuttons e labels.
    """
    inner_frame = ttk.Frame(master, padding=5)
    # Configura colunas para expandir igualmente
    inner_frame.columnconfigure((0, 1), weight=1)

    checkbuttons_data = []  # Armazena dados dos checkbuttons criados

    # --- Cabeçalhos ---
    if not available_classes:
        # Mensagem se não houver turmas
        ttk.Label(
            inner_frame,
            text=UI_TEXTS.get("no_classes_available", "Nenhuma turma disponível."),
        ).grid(row=0, column=0, columnspan=2, pady=5)
        return [], inner_frame  # Retorna lista vazia e o frame

    # Labels para as colunas "Com Reserva" e "Sem Reserva"
    ttk.Label(
        inner_frame,
        text=UI_TEXTS.get("show_with_reservation", "Mostrar COM Reserva"),
        bootstyle="success",  # type: ignore
        anchor=CENTER,
    ).grid(row=0, column=0, sticky=EW, padx=5, pady=(0, 5))
    ttk.Label(
        inner_frame,
        text=UI_TEXTS.get("show_without_reservation", "Mostrar SEM Reserva (#)"),
        bootstyle="warning",  # type: ignore
        anchor=CENTER,
    ).grid(row=0, column=1, sticky=EW, padx=5, pady=(0, 5))

    # Separador horizontal
    ttk.Separator(inner_frame, orient=HORIZONTAL).grid(
        row=1, column=0, columnspan=2, sticky=EW, pady=(0, 10)
    )

    # --- Criação dos Checkbuttons ---
    # Itera sobre as turmas disponíveis para criar os pares de checkbuttons
    for i, class_name in enumerate(available_classes):
        row_index = i + 2  # Começa na linha 2, após cabeçalhos e separador

        # Variáveis Tkinter para controlar o estado (marcado/desmarcado)
        var_with_reserve = tk.BooleanVar(value=False)  # Inicialmente desmarcado
        var_without_reserve = tk.BooleanVar(value=False)

        # Checkbutton para "Mostrar COM Reserva"
        btn_with_reserve = ttk.Checkbutton(
            inner_frame,
            text=class_name,  # Texto exibido é o nome da turma
            variable=var_with_reserve,
            bootstyle="success-square-toggle",  # Estilo visual # type: ignore
        )
        # Checkbutton para "Mostrar SEM Reserva"
        btn_without_reserve = ttk.Checkbutton(
            inner_frame,
            text=class_name,  # Texto exibido é o nome da turma
            variable=var_without_reserve,
            bootstyle="warning-square-toggle",  # Estilo visual # type: ignore
        )

        # Posiciona os checkbuttons no grid
        btn_with_reserve.grid(column=0, row=row_index, sticky="ew", padx=10, pady=2)
        btn_without_reserve.grid(column=1, row=row_index, sticky="ew", padx=10, pady=2)

        # Armazena os dados relevantes para cada checkbutton
        # O identificador para "sem reserva" é prefixado com '#'
        checkbuttons_data.extend(
            [
                (class_name, var_with_reserve, btn_with_reserve),
                (f"#{class_name}", var_without_reserve, btn_without_reserve),
            ]
        )

    return checkbuttons_data, inner_frame


class ClassFilterDialog(tk.Toplevel):
    """
    Janela de diálogo modal para permitir ao usuário selecionar quais turmas
    e com qual status de reserva (com/sem) devem ser exibidas na lista de
    alunos elegíveis da aplicação principal.
    """

    def __init__(
        self,
        parent: Union["RegistrationApp", None],
        fachada_nucleo: "FachadaRegistro",
        apply_callback: Callable[[List[str]], None],
    ):
        """
        Inicializa o diálogo de filtro de turmas.

        Args:
            parent: A janela principal da aplicação (RegistrationApp).
            fachada_nucleo: A instância da FachadaRegistro para obter dados
                             das turmas e o estado atual do filtro.
            apply_callback: A função a ser chamada quando o usuário clica em
                            "Aplicar Filtros", passando a lista de
                            identificadores selecionados (ex: ['Turma A', '#Turma B']).
        """
        super().__init__(parent)
        self.withdraw()  # Esconde a janela inicialmente para centralizar depois

        self.title(UI_TEXTS.get("class_filter_dialog_title", "📊 Filtrar Turmas"))
        self.transient(parent)  # Define como janela filha da principal
        self.grab_set()  # Torna a janela modal (bloqueia interação com a janela pai)

        # Referências internas
        self._fachada = fachada_nucleo
        self._apply_callback = apply_callback
        self._parent_app = parent  # Usado para centralização

        # --- Layout Principal ---
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=BOTH, expand=YES)
        main_frame.rowconfigure(0, weight=1)  # Área dos checkboxes expande
        main_frame.columnconfigure(0, weight=1)

        # --- Obtenção de Dados ---
        # Busca todas as turmas cadastradas
        try:
            available_classes = sorted(
                g["nome"] for g in self._fachada.listar_todos_os_grupos()
            )
        except Exception as e:
            logger.exception("Erro ao buscar turmas disponíveis da fachada. %s: %s",
                             type(e).__name__, e)
            messagebox.showerror(
                UI_TEXTS.get("database_error_title", "Erro de Banco de Dados"),
                UI_TEXTS.get(
                    "error_fetching_classes", "Não foi possível buscar as turmas."
                ),
                parent=self,
            )
            available_classes = []  # Continua com lista vazia

        # TODO: A fachada não possui um método para obter os filtros de turma
        # (grupos) atualmente ativos na sessão. O estado inicial dos checkboxes
        # não poderá ser carregado corretamente. O original era:
        # currently_selected_identifiers = self._session_manager.get_session_classes()
        currently_selected_identifiers: List[str] = []
        logger.warning("Fachada não fornece método para obter filtros de turma ativos.")


        # --- Criação da Seção de Checkboxes ---
        # Chama a função auxiliar para criar o frame com os checkbuttons
        # self._checkbox_data armazena [(identificador, var_tk, widget), ...]
        self._checkbox_data, checkbox_frame = create_dialog_class_filter_section(
            main_frame, available_classes
        )
        checkbox_frame.grid(row=0, column=0, sticky=NSEW, pady=(0, 10))

        # Inicializa o estado dos checkboxes com base nos filtros atuais
        self._initialize_checkboxes(currently_selected_identifiers)

        # --- Criação da Seção de Botões de Ação ---
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, sticky=EW)
        # Configura colunas para expandir igualmente
        button_frame.columnconfigure((0, 1, 2, 3), weight=1)

        # Botão Limpar Todos
        ttk.Button(
            button_frame,
            text=UI_TEXTS.get("clear_all_button", "⚪ Limpar Todos"),
            command=self._clear_all,
            bootstyle="secondary-outline",  # type: ignore
        ).grid(row=0, column=0, padx=3, pady=5, sticky=EW)

        # Botão Selecionar Todos
        ttk.Button(
            button_frame,
            text=UI_TEXTS.get("select_all_button", "✅ Selecionar Todos"),
            command=self._select_all,
            bootstyle="secondary-outline",  # type: ignore
        ).grid(row=0, column=1, padx=3, pady=5, sticky=EW)

        # Botão Cancelar
        ttk.Button(
            button_frame,
            text=UI_TEXTS.get("cancel_button", "❌ Cancelar"),
            command=self._on_cancel,
            bootstyle="danger",  # type: ignore
        ).grid(row=0, column=2, padx=3, pady=5, sticky=EW)

        # Botão Aplicar Filtros
        ttk.Button(
            button_frame,
            text=UI_TEXTS.get("apply_filters_button", "✔️ Aplicar Filtros"),
            command=self._on_apply,
            bootstyle="success",  # type: ignore
        ).grid(row=0, column=3, padx=3, pady=5, sticky=EW)

        # --- Configurações Finais da Janela ---
        # Define ação ao clicar no botão de fechar da janela (chama _on_cancel)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self.update_idletasks()  # Garante que dimensões da janela sejam calculadas
        self._center_window()  # Centraliza em relação à janela pai
        self.resizable(True, True)  # Permite redimensionamento
        self.deiconify()  # Exibe a janela que estava escondida

    def _center_window(self):
        """Centraliza o diálogo em relação à janela pai."""
        self.update_idletasks()  # Garante que winfo_width/height retornem valores corretos
        parent = self._parent_app

        if not parent:
            logger.warning("Tentativa de centralizar o diálogo sem janela pai.")
            return

        # Obtém geometria da janela pai
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        # Obtém geometria do diálogo
        dialog_w = self.winfo_width()
        dialog_h = self.winfo_height()
        # Calcula a posição (x, y) para centralizar
        pos_x = parent_x + (parent_w // 2) - (dialog_w // 2)
        pos_y = parent_y + (parent_h // 2) - (dialog_h // 2)
        # Define a geometria do diálogo
        self.geometry(f"+{pos_x}+{pos_y}")

    def _initialize_checkboxes(self, selected_identifiers: List[str]):
        """
        Define o estado inicial (marcado/desmarcado) dos checkbuttons com base
        na lista de identificadores de filtro ativos.

        Args:
            selected_identifiers: Lista de strings (ex: ['Turma A', '#Turma B'])
                                  representando os filtros atualmente selecionados.
        """
        # Se _checkbox_data não foi criado (ex: erro ao buscar turmas), não faz nada
        if not self._checkbox_data:
            return
        # Usa um set para busca rápida dos identificadores selecionados
        selected_set = set(selected_identifiers)
        # Itera sobre os dados dos checkbuttons criados
        for identifier, var_tk, _ in self._checkbox_data:
            # Define o estado da variável Tkinter (True se o identificador estiver no set)
            var_tk.set(identifier in selected_set)

    def _clear_all(self):
        """Desmarca todos os checkbuttons no diálogo."""
        if not self._checkbox_data:
            return
        logger.debug("Limpando todas as seleções do filtro de turmas.")
        for _, var_tk, _ in self._checkbox_data:
            var_tk.set(False)

    def _select_all(self):
        """Marca todos os checkbuttons no diálogo."""
        if not self._checkbox_data:
            return
        logger.debug("Selecionando todas as opções do filtro de turmas.")
        for _, var_tk, _ in self._checkbox_data:
            var_tk.set(True)

    def _on_cancel(self):
        """Ação executada quando o diálogo é cancelado (botão Cancelar ou fechar janela)."""
        logger.debug("Diálogo de filtro de turmas cancelado.")
        self.grab_release()  # Libera o foco modal
        self.destroy()  # Fecha a janela do diálogo

    def _on_apply(self):
        """
        Ação executada quando o botão "Aplicar Filtros" é clicado.
        Coleta os identificadores selecionados e chama o callback fornecido.
        """
        if not self._checkbox_data:
            self._on_cancel()  # Fecha se não há dados
            return

        # Cria a lista de identificadores marcados
        newly_selected_identifiers = [
            identifier for identifier, var_tk, _ in self._checkbox_data if var_tk.get()
        ]
        logger.info("Aplicando filtros de turma: %s", newly_selected_identifiers)

        try:
            # Chama a função de callback passada na inicialização
            self._apply_callback(newly_selected_identifiers)
            # Se o callback foi bem-sucedido, fecha o diálogo
            self.grab_release()
            self.destroy()
        except Exception as e:
            # Se ocorrer erro durante o callback (ex: erro ao aplicar filtro no SessionManager)
            logger.exception(
                "Erro ocorreu durante a execução do callback de aplicação de filtro."
            )
            messagebox.showerror(
                UI_TEXTS.get("callback_error_title", "Erro no Callback"),
                UI_TEXTS.get(
                    "callback_error_message", "Falha ao aplicar filtros:\n{error}"
                ).format(error=e),
                parent=self,  # Define o diálogo como pai da messagebox
            )
            # Não fecha o diálogo se o callback falhar, permitindo ao usuário tentar novamente
```

---
#### **`registro/view/metrics_panel.py`**
A funcionalidade de cálculo de métricas foi totalmente comentada, pois a fachada não oferece nenhum método para isso. O painel agora apenas exibirá o estado de "Calculando..." ou "Erro".

```python
# registro/view/metrics_panel.py
import tkinter as tk
from tkinter import ttk
import logging
from typing import Dict, Any

from registro.nucleo.facade import FachadaRegistro
# TODO: A classe MetricsCalculator interage diretamente com a sessão do banco
# de dados. A fachada não expõe a sessão nem oferece métodos para cálculo de
# métricas, então esta funcionalidade não pode ser portada diretamente.
# from registro.control.metrics_calculator import MetricsCalculator

logger = logging.getLogger(__name__)


class MetricsPanel(ttk.Frame):
    def __init__(self, master: tk.Misc, fachada_nucleo: FachadaRegistro, **kwargs):
        super().__init__(master, **kwargs)
        self.fachada_nucleo = fachada_nucleo
        
        # Defines the order of tabs and the default selected tab
        self.tab_order = ["Almoço", "Lanche", "Global"] 

        # Defines the order and names of metrics to be displayed in each tab
        self.metric_keys_ordered = [
            "Total de Consumos", "Total de Reservas Feitas", 
            "Total de Reservas Ativas (não canceladas)",
            "Consumo com Reserva (%)", "Consumo Walk-in (%)", 
            "Taxa de Cancelamento de Reservas (%)",
            "Taxa de Comparecimento (sobre ativas) (%)", 
            "Taxa de No-Show (sobre ativas) (%)",
            "Consumo Médio por Usuário (que consumiu)", 
            "Contagem de Usuários Únicos (que consumiram)",
            "Consumos por Turma", "Consumos por Dia da Semana", 
            "Consumos por Hora do Dia"
        ]
        
        # Holds StringVars for each metric in each tab
        self.tab_metrics_vars: Dict[str, Dict[str, tk.StringVar]] = {
            tab_name: {key: tk.StringVar(value="Aguardando...") for key in self.metric_keys_ordered}
            for tab_name in self.tab_order
        }

        self._create_widgets()
        # Metrics are loaded by the dialog or explicitly by the refresh button

    def _create_metric_tab(self, parent_notebook: ttk.Notebook, tab_name: str) -> ttk.Frame:
        """Creates a single tab with all metric labels and value entries."""
        tab_frame = ttk.Frame(parent_notebook, padding="10")
        parent_notebook.add(tab_frame, text=tab_name)

        # Ensure StringVars for this tab are pre-initialized (should be by __init__)
        if tab_name not in self.tab_metrics_vars:
            self.tab_metrics_vars[tab_name] = {}

        for i, key in enumerate(self.metric_keys_ordered):
            # Ensure StringVar for this specific key exists
            if key not in self.tab_metrics_vars[tab_name]:
                self.tab_metrics_vars[tab_name][key] = tk.StringVar(value="Aguardando...")

            lbl_name = ttk.Label(tab_frame, text=f"{key}:")
            lbl_name.grid(row=i, column=0, sticky=tk.W, padx=5, pady=(3,2)) # Slightly more top padding

            val_entry = ttk.Entry(
                tab_frame, textvariable=self.tab_metrics_vars[tab_name][key], state='readonly', width=60)
            val_entry.grid(row=i, column=1, sticky=tk.EW, padx=5, pady=(3,2))
        
        tab_frame.columnconfigure(1, weight=1) # Allow value column to expand
        return tab_frame

    def _create_widgets(self):
        """Creates the main notebook and the refresh button."""
        container_frame = ttk.Frame(self)
        container_frame.pack(fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(container_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5,0))

        for tab_name in self.tab_order:
            self._create_metric_tab(self.notebook, tab_name)
        
        # Set "Almoço" as the default selected tab
        try:
            almoco_tab_index = self.tab_order.index("Almoço")
            self.notebook.select(almoco_tab_index)
        except ValueError:
            logger.warning("Aba 'Almoço' não encontrada na ordem de abas. Selecionando a primeira.")
            if self.notebook.tabs(): # Check if there are any tabs
                self.notebook.select(0)


        refresh_button = ttk.Button(
            container_frame, text="Atualizar Todas as Métricas", command=self.load_metrics)
        # Place button below the notebook
        refresh_button.pack(pady=(10,5), padx=5, fill=tk.X, side=tk.BOTTOM)


    def load_metrics(self):
        """Loads metrics from the calculator and updates all tabs."""
        logger.info("Carregando métricas para exibição (todas as abas)...")
        
        # Set all metric fields to "Calculando..."
        for tab_name_iter in self.tab_order:
            if tab_name_iter in self.tab_metrics_vars:
                for key_iter in self.metric_keys_ordered:
                    if key_iter in self.tab_metrics_vars[tab_name_iter]:
                        self.tab_metrics_vars[tab_name_iter][key_iter].set("Calculando...")
        self.update_idletasks() # Ensure UI updates before potentially long calculation

        # TODO: A fachada não fornece métodos para calcular métricas.
        # A lógica original dependia de acesso direto à sessão do banco de dados
        # para a classe MetricsCalculator, o que o padrão Facade visa encapsular.
        # Para que esta funcionalidade volte a operar, seria necessário adicionar
        # métodos de obtenção de métricas à FachadaRegistro.
        error_msg = "Funcionalidade Indisponível"
        logger.error("Cálculo de métricas não suportado pela fachada.")
        for tab_name_iter in self.tab_order:
            if tab_name_iter in self.tab_metrics_vars:
                for key_iter in self.metric_keys_ordered:
                     if key_iter in self.tab_metrics_vars[tab_name_iter]:
                        self.tab_metrics_vars[tab_name_iter][key_iter].set(error_msg)

        # try:
        #     db_session = self.session_manager.turma_crud.get_session()
        #     if not db_session:
        #         logger.error("Sessão do banco de dados não disponível para cálculo de métricas.")
        #         error_msg = "Erro: Sem DB"
        #         for tab_name_iter in self.tab_order:
        #             if tab_name_iter in self.tab_metrics_vars:
        #                 for key_iter in self.metric_keys_ordered:
        #                      if key_iter in self.tab_metrics_vars[tab_name_iter]:
        #                         self.tab_metrics_vars[tab_name_iter][key_iter].set(error_msg)
        #         return

        #     calculator = MetricsCalculator(db_session)
        #     # This call now returns a dict like: {"Global": {...}, "Almoço": {...}, "Lanche": {...}}
        #     all_metrics_data_structured = calculator.calculate_all_metrics() 

        #     self._update_labels(all_metrics_data_structured)
        #     logger.info("Métricas carregadas e exibidas para todas as abas.")

        # except Exception as e:
        #     logger.exception(f"Falha crítica ao carregar ou processar métricas: {e}")
        #     error_msg = "Erro ao carregar"
        #     for tab_name_iter in self.tab_order:
        #         if tab_name_iter in self.tab_metrics_vars:
        #             for key_iter in self.metric_keys_ordered:
        #                 if key_iter in self.tab_metrics_vars[tab_name_iter]:
        #                     self.tab_metrics_vars[tab_name_iter][key_iter].set(error_msg)

    def _format_metric_value(self, value: Any) -> str:
        """ Formats various metric values for display, especially dictionaries. """
        if isinstance(value, dict):
            if not value: return "Nenhum dado"
            # Handle specific error structure from calculator
            if value.get("Erro", None) == -1: return "Erro no cálculo"
            # Generic error check if "Erro" key exists
            if "Erro" in value: return str(value)
            
            try:
                # Attempt to sort items for consistent display
                # For count-like dicts (values are numbers), sort by value descending
                if any(isinstance(v, (int, float)) for v in value.values()):
                    sorted_items = sorted(value.items(), key=lambda item: item[1], reverse=True)
                else: # For other dicts (e.g., day names), sort by key
                    sorted_items = sorted(value.items())
                return ", ".join([f"{k}: {v}" for k, v in sorted_items])
            except TypeError: # Fallback if sorting fails (e.g., mixed types)
                 return ", ".join([f"{str(k)}: {str(v)}" for k, v in value.items()])
        if isinstance(value, float):
            return f"{value:.2f}" # Format floats to 2 decimal places
        return str(value)

    def _update_labels(self, all_metrics_data_structured: Dict[str, Dict[str, Any]]):
        """Updates the StringVars in each tab with formatted metric data."""
        for tab_name, metrics_for_tab in all_metrics_data_structured.items():
            if tab_name not in self.tab_metrics_vars:
                logger.warning(f"Dados de métricas recebidos para aba desconhecida: {tab_name}. Pulando.")
                continue
            
            for key in self.metric_keys_ordered:
                if key in self.tab_metrics_vars[tab_name]:
                    raw_value = metrics_for_tab.get(key, "N/D") # "N/D" for Not Available
                    formatted_value = self._format_metric_value(raw_value)
                    self.tab_metrics_vars[tab_name][key].set(formatted_value)
                else:
                    # This should not happen if metric_keys_ordered is consistent
                    logger.warning(f"Chave de métrica '{key}' não encontrada em StringVars para aba '{tab_name}'.")


# --- Example Usage (for testing this panel standalone) ---
if __name__ == '__main__':
    class MockSessionManager: # Identical to previous, for standalone testing
        def __init__(self):
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from registro.model.tables import Base # Ensure this path is correct
            
            # For testing, point to your development/test database
            DATABASE_URL = "sqlite:///./config/registro.db" 

            engine = create_engine(DATABASE_URL)
            Base.metadata.create_all(engine) # Create tables if they don't exist
            
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            self.db_session = SessionLocal()
            print("Mock DB Session created for testing MetricsPanel.")

            # Mock CRUD for get_session() method used by MetricsPanel
            class MockCRUD:
                def __init__(self, session):
                    self._session = session
                def get_session(self):
                    return self._session
            
            self.turma_crud = MockCRUD(self.db_session)
            # To test with data, uncomment and adapt _populate_dummy_data
            # self._populate_dummy_data() # (definition can be copied from previous examples)

    logging.basicConfig(level=logging.DEBUG)
    
    root = tk.Tk()
    root.title("Painel de Métricas com Abas - Teste")
    root.geometry("850x700") # Adjusted size for better display

    # This example cannot run standalone anymore as it depends on the facade
    # which is not mocked here.
    # mock_sm = MockSessionManager()
    # metrics_p = MetricsPanel(root, fachada_nucleo=mock_sm)
    # metrics_p.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    # metrics_p.load_metrics() # Load metrics on startup for the test

    root.mainloop()

# END OF FILE registro/view/metrics_panel.py
```

---
#### **`registro/view/session_dialog.py`**
As chamadas diretas ao `SessionManager` e seus CRUDs foram substituídas por métodos da fachada. A sincronização foi adaptada para usar o método da fachada dentro de uma thread para não bloquear a UI.

```python
# ----------------------------------------------------------------------------
# File: registro/view/session_dialog.py (Diálogo de Gerenciamento de Sessão - View)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>
"""
Fornece um diálogo modal para criar uma nova sessão de refeição ou carregar
uma sessão existente. Permite também sincronizar os dados de reservas mestre.
"""
import datetime as dt
import logging
import tkinter as tk
from pathlib import Path
from threading import Thread
from tkinter import messagebox
from typing import TYPE_CHECKING, Callable, Dict, List, Sequence, Set, Tuple, Union

import ttkbootstrap as ttk

# Importações locais
from registro.control.constants import (
    INTEGRATED_CLASSES,
    SNACKS_JSON_PATH,
    UI_TEXTS,
    DEFAULT_SNACK_NAME,
    NewSessionData,
)
# A thread de sincronização agora é genérica para chamar a fachada
# from registro.control.sync_thread import SyncReserves 
from registro.control.utils import capitalize, load_json, save_json  # Utilitários
from registro.nucleo.facade import FachadaRegistro

# Type checking para evitar importações circulares
if TYPE_CHECKING:
    from registro.view.registration_app import RegistrationApp

logger = logging.getLogger(__name__)

# --- Funções Auxiliares de Criação de Widgets ---


def create_class_checkbox_section(
    master: tk.Widget, available_classes: List[str]
) -> tuple[List[Tuple[str, tk.BooleanVar, ttk.Checkbutton]], ttk.Labelframe]:
    """
    Cria a seção do diálogo com checkboxes para selecionar as turmas participantes.

    Args:
        master: O widget pai onde o Labelframe será colocado.
        available_classes: Lista dos nomes das turmas disponíveis.

    Returns:
        Uma tupla contendo:
        - Lista de tuplas: `(nome_turma, variavel_tk, widget_checkbutton)`.
        - O widget ttk.Labelframe criado.
    """
    group_frame = ttk.Labelframe(
        master,
        text=UI_TEXTS.get(
            "participating_classes_label", "🎟️ Selecione Turmas Participantes"
        ),
        padding=6,
    )
    num_cols = 3  # Número de colunas para os checkboxes
    group_frame.columnconfigure(tuple(range(num_cols)), weight=1)  # Colunas expansíveis
    if not available_classes:
        # Mensagem se não houver turmas no banco
        ttk.Label(
            group_frame,
            text=UI_TEXTS.get(
                "no_classes_found_db", "Nenhuma turma encontrada no banco de dados."
            ),
        ).grid(column=0, row=0, columnspan=num_cols, pady=10)
        # Ajusta a configuração de linha mesmo sem turmas
        group_frame.rowconfigure(0, weight=1)
        return [], group_frame  # Retorna lista vazia e o frame

    # Calcula o número de linhas necessário
    num_rows = (len(available_classes) + num_cols - 1) // num_cols
    group_frame.rowconfigure(
        tuple(range(num_rows or 1)), weight=1
    )  # Linhas expansíveis

    checkbox_data = []  # Armazena dados dos checkboxes criados
    # Cria um checkbox para cada turma disponível
    for i, class_name in enumerate(available_classes):
        check_var = tk.BooleanVar(value=False)  # Estado inicial desmarcado
        check_btn = ttk.Checkbutton(
            group_frame,
            text=class_name,
            variable=check_var,
            bootstyle="success-round-toggle",  # Estilo visual # type: ignore
        )
        check_btn.grid(
            column=i % num_cols,  # Coluna baseada no índice
            row=i // num_cols,  # Linha baseada no índice
            sticky="news",  # Expande em todas as direções
            padx=10,
            pady=5,
        )
        checkbox_data.append((class_name, check_var, check_btn))

    return checkbox_data, group_frame


# --- Classe Principal do Diálogo ---


class SessionDialog(tk.Toplevel):
    """
    Janela de diálogo para selecionar/criar sessão e sincronizar reservas.
    """

    def __init__(
        self,
        title: str,
        callback: Callable[[Union[NewSessionData, int, None]], bool],
        parent_app: "RegistrationApp",
    ):
        """
        Inicializa o diálogo de sessão.

        Args:
            title: O título da janela do diálogo.
            callback: Função a ser chamada ao clicar em OK. Recebe os dados da nova
                      sessão (dict), o ID da sessão existente (int), ou None se
                      cancelado. Retorna True se a operação foi bem-sucedida na
                      janela principal, False caso contrário (mantém diálogo aberto).
            parent_app: A instância da aplicação principal (RegistrationApp).
        """
        super().__init__(parent_app)
        self.withdraw()  # Esconde inicialmente

        self.title(title)
        self.transient(parent_app)  # Define como filha da janela principal
        self.grab_set()  # Torna modal

        # Referências importantes
        self._callback = callback
        self._parent_app = parent_app
        # Obtém a Fachada da aplicação pai
        self._fachada: "FachadaRegistro" = parent_app.get_fachada()
        # Armazena dados dos checkboxes de turma
        self._classes_checkbox_data: List[
            Tuple[str, tk.BooleanVar, ttk.Checkbutton]
        ] = []
        # Armazena o mapeamento display -> ID das sessões existentes
        self._sessions_map: Dict[str, int] = {}
        # Conjunto para armazenar opções de lanche carregadas/salvas
        self._snack_options_set: Set[str] = set()

        # Define ação para o botão de fechar da janela
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        # --- Criação das Seções do Diálogo ---
        # 1. Nova Sessão
        self._new_session_frame = self._create_section_new_session()
        self._new_session_frame.grid(
            column=0, row=0, padx=10, pady=(10, 5), sticky="ew"
        )

        # 2. Seleção de Turmas
        available_classes = self._fetch_available_classes()
        self._classes_checkbox_data, self._class_selection_frame = (
            create_class_checkbox_section(self, available_classes)  # type: ignore
        )
        self._class_selection_frame.grid(
            column=0, row=1, padx=10, pady=5, sticky="nsew"
        )
        self.rowconfigure(1, weight=1)  # Permite que esta seção expanda verticalmente

        # 3. Botões de Ação para Turmas
        self._create_section_class_buttons().grid(
            column=0, row=2, padx=10, pady=5, sticky="ew"
        )

        # 4. Edição/Seleção de Sessão Existente
        self._edit_session_frame = self._create_section_edit_session()
        self._edit_session_frame.grid(column=0, row=3, padx=10, pady=5, sticky="ew")

        # 5. Botões Principais (OK, Cancelar, Sincronizar)
        self._main_button_frame = self._create_section_main_buttons()
        self._main_button_frame.grid(
            column=0, row=4, padx=10, pady=(5, 10), sticky="ew"
        )

        # --- Finalização ---
        self.update_idletasks()  # Calcula dimensões
        self._center_window()  # Centraliza
        self.resizable(False, True)  # Não redimensionável horizontalmente
        self.deiconify()  # Mostra a janela

    def _fetch_available_classes(self) -> List[str]:
        """Busca as turmas disponíveis no banco de dados."""
        try:
            # Usa a fachada para obter os grupos (turmas)
            grupos = self._fachada.listar_todos_os_grupos()
            classes = sorted(g.get("nome", "") for g in grupos if g.get("nome"))
            return classes
        except Exception as e:
            logger.exception(
                "Erro ao buscar turmas disponíveis da fachada. %s: %s",
                type(e).__name__,
                e,
            )
            messagebox.showerror(
                UI_TEXTS.get("database_error_title", "Erro de Banco de Dados"),
                UI_TEXTS.get(
                    "error_fetching_classes", "Não foi possível buscar as turmas."
                ),
                parent=self,
            )
            return []  # Retorna lista vazia em caso de erro

    def _center_window(self):
        """Centraliza este diálogo em relação à janela pai."""
        self.update_idletasks()
        parent = self._parent_app
        parent_x, parent_y = parent.winfo_x(), parent.winfo_y()
        parent_w, parent_h = parent.winfo_width(), parent.winfo_height()
        dialog_w, dialog_h = self.winfo_width(), self.winfo_height()
        pos_x = parent_x + (parent_w // 2) - (dialog_w // 2)
        pos_y = parent_y + (parent_h // 2) - (dialog_h // 2)
        self.geometry(f"+{pos_x}+{pos_y}")

    def _on_closing(self):
        """Chamado quando o diálogo é fechado pelo botão 'X' ou 'Cancelar'."""
        logger.info("Diálogo de sessão fechado pelo usuário.")
        self.grab_release()  # Libera modalidade
        self.destroy()  # Destroi a janela
        try:
            # Chama o callback com None para indicar cancelamento
            self._callback(None)
        except Exception as e:
            logger.exception("Erro no callback de fechamento do diálogo: %s", e)

    def _create_section_new_session(self) -> ttk.Labelframe:
        """Cria o frame com os campos para definir uma nova sessão."""
        frame = ttk.Labelframe(
            self,
            text=UI_TEXTS.get("new_session_group_label", "➕ Detalhes da Nova Sessão"),
            padding=10,
        )
        # Configura colunas para expandir campos de entrada
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        # Campo Hora
        ttk.Label(master=frame, text=UI_TEXTS.get("time_label", "⏰ Horário:")).grid(
            row=0, column=0, sticky="w", padx=(0, 5), pady=3
        )
        self._time_entry = ttk.Entry(frame, width=8)
        self._time_entry.insert(0, dt.datetime.now().strftime("%H:%M"))  # HH:MM
        self._time_entry.grid(row=0, column=1, sticky="w", padx=5, pady=3)

        # Campo Data
        ttk.Label(master=frame, text=UI_TEXTS.get("date_label", "📅 Data:")).grid(
            row=0, column=2, sticky="w", padx=(10, 5), pady=3
        )
        self._date_entry = ttk.DateEntry(
            frame,
            width=12,
            bootstyle="primary",
            dateformat="%d/%m/%Y",  # Formato de exibição na UI
        )
        self._date_entry.grid(row=0, column=3, sticky="ew", padx=(0, 5), pady=3)

        # Campo Tipo de Refeição
        ttk.Label(
            master=frame, text=UI_TEXTS.get("meal_type_label", "🍽️ Refeição:")
        ).grid(row=1, column=0, sticky="w", padx=(0, 5), pady=3)
        now_time = dt.datetime.now().time()
        # Define Almoço como padrão entre 11:00 e 13:30
        is_lunch_time = dt.time(11, 00) <= now_time <= dt.time(13, 30)
        meal_options = [
            UI_TEXTS.get("meal_snack", "Lanche"),
            UI_TEXTS.get("meal_lunch", "Almoço"),
        ]
        self._meal_combobox = ttk.Combobox(
            master=frame, values=meal_options, state="readonly", bootstyle="info"  # type: ignore
        )
        self._meal_combobox.current(1 if is_lunch_time else 0)  # Define seleção inicial
        self._meal_combobox.grid(
            row=1, column=1, columnspan=3, sticky="ew", padx=5, pady=3
        )
        # Associa evento para habilitar/desabilitar campo de lanche específico
        self._meal_combobox.bind("<<ComboboxSelected>>", self._on_select_meal)

        # Campo Lanche Específico
        ttk.Label(
            master=frame,
            text=UI_TEXTS.get("specific_snack_label", "🥪 Lanche Específico:"),
        ).grid(row=2, column=0, sticky="w", padx=(0, 5), pady=3)
        self._snack_options_set, snack_display_list = self._load_snack_options()
        self._snack_combobox = ttk.Combobox(
            master=frame, values=snack_display_list, bootstyle="warning"  # type: ignore
        )
        # Habilita/desabilita baseado na seleção inicial de refeição
        self._snack_combobox.config(
            state=(
                "disabled"
                if self._meal_combobox.get() == UI_TEXTS.get("meal_lunch", "Almoço")
                else "normal"
            )
        )
        # Define seleção inicial se houver opções válidas
        if snack_display_list and "Error" not in snack_display_list[0]:
            self._snack_combobox.current(0)  # Seleciona o primeiro da lista
        self._snack_combobox.grid(
            row=2, column=1, columnspan=3, sticky="ew", padx=5, pady=3
        )

        return frame

    def _load_snack_options(self) -> Tuple[Set[str], List[str]]:
        """Carrega as opções de lanche do arquivo JSON."""
        snacks_path = Path(SNACKS_JSON_PATH)
        default_options = [DEFAULT_SNACK_NAME]
        try:
            # Usa utilitário load_json
            snack_options = load_json(str(snacks_path))
            # Valida se o conteúdo é uma lista de strings
            if not isinstance(snack_options, list) or not all(
                (isinstance(s, str) for s in snack_options)
            ):
                logger.error(
                    "Conteúdo inválido em '%s'. Esperada lista de strings.", snacks_path
                )
                # Define mensagem de erro para exibição
                error_msg = f"Erro: Conteúdo inválido em {snacks_path.name}"
                return set(), [error_msg]
            # Se a lista estiver vazia no arquivo, usa o padrão
            if not snack_options:
                return set(default_options), default_options
            # Retorna o conjunto (para verificação rápida) e a lista ordenada (para display)
            return set(snack_options), sorted(snack_options)
        except FileNotFoundError:
            logger.warning(
                "Arquivo de opções de lanche '%s' não encontrado. Usando padrão e criando arquivo.",
                snacks_path,
            )
            # Cria o arquivo com a opção padrão se não existir
            save_json(str(snacks_path), default_options)
            return set(default_options), default_options
        except Exception as e:
            logger.exception(
                "Erro ao carregar opções de lanche de '%s'. %s: %s",
                snacks_path,
                type(e).__name__,
                e,
            )
            return (set(), [f"Erro ao carregar {snacks_path.name}"])

    def _create_section_class_buttons(self) -> ttk.Frame:
        """Cria o frame com botões de ação para seleção de turmas."""
        button_frame = ttk.Frame(self)
        button_frame.columnconfigure(tuple(range(4)), weight=1)  # 4 colunas expansíveis
        # Configuração dos botões: (Texto da UI, Comando, Estilo)
        buttons_config = [
            ("clear_all_button", self._on_clear_classes, "outline-secondary"),
            ("select_integrated_button", self._on_select_integral, "outline-info"),
            ("select_others_button", self._on_select_others, "outline-info"),
            ("invert_selection_button", self._on_invert_classes, "outline-secondary"),
        ]
        for i, (text_key, cmd, style) in enumerate(buttons_config):
            ttk.Button(
                master=button_frame,
                text=UI_TEXTS.get(text_key, f"BTN_{i}"),  # Usa chave ou fallback
                command=cmd,
                bootstyle=style,  # type: ignore
                width=15,  # Largura fixa para alinhamento
            ).grid(row=0, column=i, padx=2, pady=2, sticky="ew")
        return button_frame

    def _create_section_edit_session(self) -> ttk.Labelframe:
        """Cria o frame para selecionar uma sessão existente."""
        frame = ttk.Labelframe(
            self,
            text=UI_TEXTS.get(
                "edit_session_group_label", "📝 Selecionar Sessão Existente para Editar"
            ),
            padding=10,
        )
        frame.columnconfigure(0, weight=1)  # Combobox expande horizontalmente

        # Carrega as sessões existentes do banco
        self._sessions_map, session_display_list = self._load_existing_sessions()

        # Cria o Combobox para exibir as sessões
        self._sessions_combobox = ttk.Combobox(
            master=frame,
            values=session_display_list,
            state="readonly",  # Impede digitação
            bootstyle="dark",  # type: ignore
        )
        # Define o texto placeholder ou a primeira opção
        placeholder = UI_TEXTS.get(
            "edit_session_placeholder",
            "Selecione uma sessão existente para carregar...",
        )
        if session_display_list and "Error" not in session_display_list[0]:
            self._sessions_combobox.set(placeholder)  # Define placeholder
        elif session_display_list:  # Caso de erro ao carregar
            self._sessions_combobox.current(0)  # Mostra a mensagem de erro
            self._sessions_combobox.config(state="disabled")
        else:  # Nenhuma sessão encontrada
            self._sessions_combobox.set(
                UI_TEXTS.get(
                    "no_existing_sessions", "Nenhuma sessão existente encontrada."
                )
            )
            self._sessions_combobox.config(state="disabled")

        self._sessions_combobox.grid(row=0, column=0, sticky="ew", padx=3, pady=3)
        return frame

    def _load_existing_sessions(self) -> Tuple[Dict[str, int], List[str]]:
        """Carrega sessões existentes do banco de dados para o combobox."""
        try:
            # Busca sessões da fachada (já vem ordenada)
            sessions: List[Dict] = self._fachada.listar_todas_sessoes()
            
            # Cria o mapa: "DD/MM/YYYY HH:MM - Refeição (ID: id)" -> id
            sessions_map = {}
            for s in sessions:
                # Formata a data para exibição DD/MM/YYYY
                try:
                    display_date = dt.datetime.strptime(s['data'], "%Y-%m-%d").strftime(
                        "%d/%m/%Y"
                    )
                except (ValueError, KeyError):
                    display_date = s.get('data', 'Data Inválida')
                
                s_id = s.get('id')
                s_hora = s.get('hora', 'Hora')
                s_refeicao = s.get('refeicao', 'Refeição')

                # Monta a string de exibição
                display_text = (
                    f"{display_date} {s_hora} - "
                    f"{capitalize(s_refeicao)} (ID: {s_id})"
                )
                sessions_map[display_text] = s_id

            return sessions_map, list(
                sessions_map.keys()
            )
        except Exception as e:
            logger.exception(
                "Erro ao buscar sessões existentes da fachada. %s: %s",
                type(e).__name__,
                e,
            )
            error_msg = UI_TEXTS.get(
                "error_loading_sessions", "Erro ao carregar sessões"
            )
            return {error_msg: -1}, [error_msg]  # Retorna indicando erro

    def _create_section_main_buttons(self) -> ttk.Frame:
        """Cria o frame com os botões principais: OK, Cancelar, Sincronizar."""
        button_frame = ttk.Frame(self)
        # Configura colunas para espaçamento e centralização
        button_frame.columnconfigure(0, weight=1)  # Espaço à esquerda
        button_frame.columnconfigure(4, weight=1)  # Espaço à direita

        # Botão Sincronizar Reservas
        ttk.Button(
            master=button_frame,
            text=UI_TEXTS.get("sync_reservations_button", "📥 Sincronizar Reservas"),
            command=self._on_sync_reserves,
            bootstyle="outline-warning",  # type: ignore
        ).grid(
            row=0, column=1, padx=5, pady=5
        )  # Coluna 1

        # Botão Cancelar
        ttk.Button(
            master=button_frame,
            text=UI_TEXTS.get("cancel_button", "❌ Cancelar"),
            command=self._on_closing,  # Reutiliza a função de fechar
            bootstyle="danger",  # type: ignore
        ).grid(
            row=0, column=2, padx=5, pady=5
        )  # Coluna 2

        # Botão OK
        ttk.Button(
            master=button_frame,
            text=UI_TEXTS.get("ok_button", "✔️ OK"),
            command=self._on_okay,
            bootstyle="success",  # type: ignore
        ).grid(
            row=0, column=3, padx=5, pady=5
        )  # Coluna 3

        return button_frame

    # --- Handlers de Eventos e Ações ---

    def _on_select_meal(self, _=None):
        """Habilita/desabilita campo de lanche específico ao mudar tipo de refeição."""
        is_lunch = self._meal_combobox.get() == UI_TEXTS.get("meal_lunch", "Almoço")
        new_state = "disabled" if is_lunch else "normal"
        self._snack_combobox.config(state=new_state)
        # Limpa o campo se for almoço
        if is_lunch:
            self._snack_combobox.set("")

    def _on_clear_classes(self):
        """Desmarca todos os checkboxes de turma."""
        self._set_class_checkboxes(lambda name, var: False)

    def _on_select_integral(self):
        """Marca apenas os checkboxes das turmas integrais."""
        self._set_class_checkboxes(lambda name, var: name in INTEGRATED_CLASSES)

    def _on_select_others(self):
        """Marca apenas os checkboxes das turmas não integrais."""
        self._set_class_checkboxes(lambda name, var: name not in INTEGRATED_CLASSES)

    def _on_invert_classes(self):
        """Inverte o estado de marcação de todos os checkboxes de turma."""
        self._set_class_checkboxes(lambda name, var: not var.get())

    def _set_class_checkboxes(
        self, condition_func: Callable[[str, tk.BooleanVar], bool]
    ):
        """
        Aplica uma condição para marcar/desmarcar os checkboxes de turma.

        Args:
            condition_func: Função que recebe (nome_turma, var_tk) e retorna
                            True para marcar, False para desmarcar.
        """
        if not self._classes_checkbox_data:  # Verifica se a lista existe
            logger.warning(
                "Tentativa de definir checkboxes de turma,"
                " mas a lista de dados não está disponível."
            )
            return
        for class_name, check_var, _ in self._classes_checkbox_data:
            check_var.set(condition_func(class_name, check_var))

    def _validate_new_session_input(self) -> bool:
        """Valida os campos de entrada para criação de uma nova sessão."""
        # Valida Hora
        try:
            dt.datetime.strptime(self._time_entry.get(), "%H:%M")
        except ValueError:
            messagebox.showwarning(
                UI_TEXTS.get("invalid_input_title", "Entrada Inválida"),
                UI_TEXTS.get(
                    "invalid_time_format", "Formato de hora inválido. Use HH:MM."
                ),
                parent=self,
            )
            self._time_entry.focus_set()  # Foca no campo inválido
            return False

        # Valida Data (formato DD/MM/YYYY da UI)
        try:
            date_str = self._date_entry.entry.get()
            # Valida o formato DD/MM/YYYY que o usuário vê
            dt.datetime.strptime(date_str, "%d/%m/%Y")
        except ValueError:
            messagebox.showwarning(
                UI_TEXTS.get("invalid_input_title", "Entrada Inválida"),
                UI_TEXTS.get(
                    "invalid_date_format",
                    "Formato de data inválido. Use {date_format}.",
                ).format(date_format="DD/MM/YYYY"),
                parent=self,
            )
            self._date_entry.focus_set()  # Foca no campo
            return False
        except AttributeError:
            logger.warning(
                "Não foi possível acessar o widget interno de DateEntry para validação."
            )

        # Valida Tipo de Refeição
        valid_meals = [
            UI_TEXTS.get("meal_snack", "Lanche"),
            UI_TEXTS.get("meal_lunch", "Almoço"),
        ]
        if self._meal_combobox.get() not in valid_meals:
            messagebox.showwarning(
                UI_TEXTS.get("invalid_input_title", "Entrada Inválida"),
                UI_TEXTS.get(
                    "select_meal_type", "Selecione um Tipo de Refeição válido."
                ),
                parent=self,
            )
            return False

        # Valida Lanche Específico (se for lanche)
        meal_type = self._meal_combobox.get()
        snack_selection = self._snack_combobox.get().strip()
        if meal_type == UI_TEXTS.get("meal_snack", "Lanche") and not snack_selection:
            messagebox.showwarning(
                UI_TEXTS.get("invalid_input_title", "Entrada Inválida"),
                UI_TEXTS.get(
                    "specify_snack_name", "Especifique o nome do lanche para 'Lanche'."
                ),
                parent=self,
            )
            self._snack_combobox.focus_set()
            return False

        # Valida Seleção de Turmas
        if not any(var.get() for _, var, _ in self._classes_checkbox_data):
            messagebox.showwarning(
                UI_TEXTS.get("invalid_selection_title", "Seleção Inválida"),
                UI_TEXTS.get(
                    "select_one_class", "Selecione pelo menos uma turma participante."
                ),
                parent=self,
            )
            return False

        return True

    def _save_new_snack_option(self, snack_selection: str):
        """Salva uma nova opção de lanche no arquivo JSON se ela for nova."""
        if (
            snack_selection
            and snack_selection not in self._snack_options_set
            and "Error" not in snack_selection
        ):
            normalized_snack = capitalize(snack_selection)
            logger.info(
                "Nova opção de lanche digitada: '%s'. Adicionando à lista.",
                normalized_snack,
            )
            self._snack_options_set.add(
                normalized_snack
            )
            snacks_path = Path(SNACKS_JSON_PATH)
            try:
                if save_json(str(snacks_path), sorted(list(self._snack_options_set))):
                    logger.info(
                        "Opções de lanche atualizadas e salvas em '%s'.", snacks_path
                    )
                    self._snack_combobox["values"] = sorted(
                        list(self._snack_options_set)
                    )
                    self._snack_combobox.set(normalized_snack)
                else:
                    messagebox.showerror(
                        UI_TEXTS.get("save_error_title", "Erro ao Salvar"),
                        UI_TEXTS.get(
                            "new_snack_save_error",
                            "Não foi possível salvar a nova opção de lanche.",
                        ),
                        parent=self,
                    )
            except Exception as e:
                logger.exception(
                    "Erro ao salvar nova opção de lanche '%s' em '%s'. %s: %s",
                    normalized_snack,
                    snacks_path,
                    type(e).__name__,
                    e,
                )
                messagebox.showerror(
                    UI_TEXTS.get("save_error_title", "Erro ao Salvar"),
                    UI_TEXTS.get(
                        "unexpected_snack_save_error",
                        "Erro inesperado ao salvar lista de lanches.",
                    ),
                    parent=self,
                )

    def _on_okay(self):
        """Ação executada ao clicar no botão OK. Tenta carregar ou criar sessão."""
        selected_session_display = self._sessions_combobox.get()
        session_id_to_load = None

        is_placeholder = any(
            ph in selected_session_display for ph in ["Selecione", "Error", "Nenhuma"]
        )
        if selected_session_display and not is_placeholder:
            session_id_to_load = self._sessions_map.get(selected_session_display)

        if session_id_to_load is not None:
            logger.info(
                "Botão OK: Requisitando carregamento da sessão existente ID %s",
                session_id_to_load,
            )
            success = self._callback(session_id_to_load)
            if success:
                logger.info(
                    "Sessão existente carregada com sucesso pela aplicação principal."
                )
                self.grab_release()
                self.destroy()
            else:
                logger.warning(
                    "Aplicação principal indicou falha ao carregar sessão existente."
                )
        else:
            logger.info("Botão OK: Tentando criar uma nova sessão.")
            if not self._validate_new_session_input():
                return

            selected_classes = [
                txt for txt, var, _ in self._classes_checkbox_data if var.get()
            ]
            meal_type = self._meal_combobox.get().lower() # lanche/almoço
            
            snack_selection = (
                self._snack_combobox.get().strip()
                if meal_type == UI_TEXTS.get("meal_snack", "Lanche").lower()
                else None
            )
            if snack_selection:
                self._save_new_snack_option(snack_selection)
                snack_selection = self._snack_combobox.get().strip()

            try:
                date_ui = self._date_entry.entry.get()
                date_backend = dt.datetime.strptime(date_ui, "%d/%m/%Y").strftime(
                    "%Y-%m-%d"
                )
            except (ValueError, AttributeError) as e:
                logger.error("Erro ao converter data: %s", e)
                messagebox.showerror("Erro Interno", "Data inválida.", parent=self)
                return

            # Monta o dicionário para a fachada (DADOS_SESSAO)
            new_session_data: Dict[str, Union[str, List[str], None]] = {
                "refeicao": meal_type,
                "item_servido": snack_selection,
                "periodo": "", 
                "data": date_backend,
                "hora": self._time_entry.get(),
                "grupos": selected_classes,
            }

            # Chama o callback da janela principal com o novo formato
            success = self._callback(new_session_data) # type: ignore
            if success:
                logger.info("Nova sessão criada com sucesso pela aplicação principal.")
                self.grab_release()
                self.destroy()
            else:
                logger.warning(
                    "Aplicação principal indicou falha ao criar nova sessão."
                )

    def _on_sync_reserves(self):
        """Inicia a thread para sincronizar reservas mestre."""
        logger.info("Botão Sincronizar Reservas clicado.")
        self._parent_app.show_progress_bar(
            True,
            UI_TEXTS.get("status_syncing_reservations", "Sincronizando reservas..."),
        )
        self.update_idletasks()

        # Ação de sincronização
        def sync_action():
            thread.error = None
            thread.success = False
            try:
                self._fachada.sincronizar_do_google_sheets()
                thread.success = True
            except Exception as e:
                thread.error = e
        
        sync_thread = Thread(target=sync_action, daemon=True)
        # Adiciona atributos para o monitoramento
        thread = sync_thread
        thread.error = None # type: ignore
        thread.success = False # type: ignore
        sync_thread.start()

        self._sync_monitor(sync_thread)

    def _sync_monitor(self, thread: Thread):
        """Verifica o estado da thread de sincronização periodicamente."""
        if thread.is_alive():
            self.after(150, lambda: self._sync_monitor(thread))
        else:
            self._parent_app.show_progress_bar(False)
            error = getattr(thread, "error", None)
            success = getattr(thread, "success", False)
            
            if error:
                logger.error("Sincronização de reservas falhou: %s", error)
                messagebox.showerror(
                    UI_TEXTS.get("sync_error_title", "Erro de Sincronização"),
                    UI_TEXTS.get(
                        "sync_reserves_error_message",
                        "Falha ao sincronizar reservas:\n{error}",
                    ).format(error=error),
                    parent=self,
                )
            elif success:
                logger.info("Sincronização de reservas concluída com sucesso.")
                messagebox.showinfo(
                    UI_TEXTS.get("sync_complete_title", "Sincronização Concluída"),
                    UI_TEXTS.get(
                        "sync_reserves_complete_message",
                        "Reservas sincronizadas com sucesso com o banco de dados.",
                    ),
                    parent=self,
                )
                self._update_existing_sessions_combobox()
            else:
                logger.warning("Thread de sincronização finalizou com estado indeterminado.")
                messagebox.showwarning(
                    UI_TEXTS.get("sync_status_unknown_title", "Status Incerto"),
                    UI_TEXTS.get("sync_reserves_unknown_message", "Sincronização finalizada."),
                    parent=self,
                )

    def _update_existing_sessions_combobox(self):
        """Atualiza o conteúdo do combobox de sessões existentes."""
        logger.debug("Atualizando combobox de sessões existentes...")
        self._sessions_map, session_display_list = self._load_existing_sessions()
        self._sessions_combobox["values"] = session_display_list
        placeholder = UI_TEXTS.get(
            "edit_session_placeholder",
            "Selecione uma sessão existente para carregar...",
        )
        if session_display_list and "Error" not in session_display_list[0]:
            self._sessions_combobox.set(placeholder)
            self._sessions_combobox.config(state="readonly")
        elif session_display_list:
            self._sessions_combobox.current(0)
            self._sessions_combobox.config(state="disabled")
        else:
            self._sessions_combobox.set(
                UI_TEXTS.get(
                    "no_existing_sessions", "Nenhuma sessão existente encontrada."
                )
            )
            self._sessions_combobox.config(state="disabled")
```

---
#### **`registro/view/registration_app.py`**
Este foi o arquivo com mais modificações. A classe agora gerencia uma instância de `FachadaRegistro` em vez de `SessionManager`. Muitas funções foram adaptadas para usar a fachada, e várias foram marcadas com `TODO` onde a fachada não oferece a funcionalidade necessária (como carregar/salvar estado da sessão em arquivo ou deletar consumo sem ID).

```python
# ----------------------------------------------------------------------------
# File: registro/view/registration_app.py (Aplicação Principal da UI)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>
"""
Fornece a classe principal da aplicação (`RegistrationApp`) para o sistema de
registro de refeições. Orquestra os painéis de UI, gerencia a sessão e
lida com ações globais como sincronização, exportação e troca de sessão.
"""
import logging
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from threading import Thread
from tkinter import CENTER, TclError, messagebox
from typing import Any, List, Optional, Tuple, Union, Dict

import ttkbootstrap as ttk
from ttkbootstrap.constants import (
    HORIZONTAL, LEFT, LIGHT, RIGHT, VERTICAL, X
)

from registro.control.constants import (
    SESSION_PATH, UI_TEXTS, NewSessionData
)
from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.exceptions import ErroSessaoNaoAtiva, ErroEstudanteJaConsumiu
from registro.control.utils import capitalize

from registro.view.action_search_panel import ActionSearchPanel
from registro.view.class_filter_dialog import ClassFilterDialog
from registro.view.session_dialog import SessionDialog
from registro.view.status_registered_panel import StatusRegisteredPanel

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# Classe Principal da Aplicação (GUI)
# ----------------------------------------------------------------------------

class RegistrationApp(tk.Tk):
    """Janela principal da aplicação de registro de refeições."""

    def __init__(
        self, title: str = UI_TEXTS.get("app_title", "RU IFSP - Registro de Refeições")
    ):
        """
        Inicializa a janela principal, a Fachada e constrói a UI.
        """
        super().__init__()
        self.title(title)
        self.protocol("WM_DELETE_WINDOW", self.on_close_app)
        self.minsize(1152, 648)

        self._fachada: Optional[FachadaRegistro] = None
        try:
            self._fachada = FachadaRegistro()
        except Exception as e:
            self._handle_initialization_error(
                "Fachada do Núcleo", e
            )
            return

        # --- Inicialização dos Atributos da UI ---
        self._top_bar: Optional[ttk.Frame] = None
        self._main_paned_window: Optional[ttk.PanedWindow] = None
        self._status_bar: Optional[ttk.Frame] = None
        self._action_panel: Optional[ActionSearchPanel] = None
        self._status_panel: Optional[StatusRegisteredPanel] = None
        self._session_info_label: Optional[ttk.Label] = None
        self._status_bar_label: Optional[ttk.Label] = None
        self._progress_bar: Optional[ttk.Progressbar] = None
        self.style: Optional[ttk.Style] = None
        self.colors: Optional[Any] = None

        # --- Construção da UI ---
        try:
            self._configure_style()
            self._configure_grid_layout()
            self._create_top_bar()
            self._create_main_panels(self._fachada)
            self._create_status_bar()
        except Exception as e:
            self._handle_initialization_error(
                UI_TEXTS.get("ui_construction", "Construção da UI"), e
            )
            return

        self._load_initial_session()

    def get_fachada(self) -> FachadaRegistro:
        """Retorna a instância da Fachada, levantando erro se não inicializada."""
        if self._fachada is None:
            logger.critical("Tentativa de acessar Fachada não inicializada.")
            raise RuntimeError("FachadaRegistro não foi inicializada corretamente.")
        return self._fachada

    def _handle_initialization_error(self, component: str, error: Exception):
        """Exibe erro crítico e tenta fechar a aplicação de forma limpa."""
        logger.critical(
            "Erro Crítico de Inicialização - Componente: %s | Erro: %s",
            component, error, exc_info=True,
        )
        try:
            temp_root = None
            if not hasattr(tk, "_default_root") or not tk._default_root: # type: ignore
                temp_root = tk.Tk()
                temp_root.withdraw()

            messagebox.showerror(
                UI_TEXTS.get("initialization_error_title", "Erro Fatal na Inicialização"),
                UI_TEXTS.get(
                    "initialization_error_message",
                    "Falha crítica ao inicializar o componente: {component}\n\n"
                    "Erro: {error}\n\nA aplicação será encerrada.",
                ).format(component=component, error=error),
                parent=(self if self.winfo_exists() else None),
            )
            if temp_root:
                temp_root.destroy()
        except Exception as mb_error:
            print(f"ERRO CRÍTICO DE INICIALIZAÇÃO ({component}): {error}", file=sys.stderr)
            print(f"(Erro ao exibir messagebox: {mb_error})", file=sys.stderr)

        if self.winfo_exists():
            try:
                self.destroy()
            except tk.TclError:
                pass
        sys.exit(1)

    def _configure_style(self):
        """Configura o tema ttkbootstrap e estilos customizados para widgets."""
        try:
            self.style = ttk.Style(theme="minty")
            default_font = ("Segoe UI", 12)
            heading_font = (default_font[0], 10, "bold")
            label_font = (default_font[0], 11, "bold")
            small_font = (default_font[0], 9)
            self.style.configure("Custom.Treeview", font=(default_font[0], 9), rowheight=30)
            self.style.configure("Custom.Treeview.Heading",
                                 font=heading_font,
                                 background=self.style.colors.light,
                                 foreground=self.style.colors.get_foreground('light'))
            self.style.configure("TLabelframe.Label", font=label_font)
            self.style.configure("Status.TLabel", font=small_font)
            self.style.configure("Feedback.TLabel", font=small_font)
            self.style.configure("Preview.TLabel", font=small_font, justify=LEFT)
            self.style.configure("Count.TLabel", font=heading_font, anchor=CENTER)
            self.colors = self.style.colors
        except (TclError, AttributeError) as e:
            logger.warning("Erro ao configurar estilo ttkbootstrap: %s.", e)
            self.style = ttk.Style()
            self.colors = getattr(self.style, "colors", {})

    def _configure_grid_layout(self):
        """Configura o grid da janela principal (Tk)."""
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

    def _create_top_bar(self):
        """Cria a barra superior com informações da sessão e botões globais."""
        self._top_bar = ttk.Frame(self, padding=(10, 5), bootstyle=LIGHT) # type: ignore
        self._top_bar.grid(row=0, column=0, sticky="ew")

        self._session_info_label = ttk.Label(
            self._top_bar,
            text=UI_TEXTS.get("loading_session", "Carregando Sessão..."),
            font="-size 14 -weight bold",
            bootstyle="inverse-light", # type: ignore
        )
        self._session_info_label.pack(side=LEFT, padx=(0, 20), anchor="w")

        buttons_frame = ttk.Frame(self._top_bar, bootstyle=LIGHT) # type: ignore
        buttons_frame.pack(side=RIGHT, anchor="e")

        ttk.Button(
            buttons_frame,
            text=UI_TEXTS.get("export_end_button", "💾 Exportar & Encerrar"),
            command=self.export_and_end_session,
            bootstyle="light", # type: ignore
        ).pack(side=RIGHT, padx=(10, 0))

        ttk.Button(
            buttons_frame,
            text=UI_TEXTS.get("sync_served_button", "📤 Sync Servidos"),
            command=self.sync_session_with_spreadsheet,
            bootstyle="light", # type: ignore
        ).pack(side=RIGHT, padx=3)

        ttk.Button(
            buttons_frame,
            text=UI_TEXTS.get("sync_master_button", "🔄 Sync Cadastros"),
            command=self._sync_master_data,
            bootstyle="light", # type: ignore
        ).pack(side=RIGHT, padx=3)

        ttk.Separator(buttons_frame, orient=VERTICAL).pack(side=RIGHT, padx=8, fill="y", pady=3)

        ttk.Button(
            buttons_frame,
            text=UI_TEXTS.get("filter_classes_button", "📊 Filtrar Turmas"),
            command=self._open_class_filter_dialog,
            bootstyle="light", # type: ignore
        ).pack(side=RIGHT, padx=3)

        ttk.Button(
            buttons_frame,
            text=UI_TEXTS.get("change_session_button", "⚙️ Alterar Sessão"),
            command=self._open_session_dialog,
            bootstyle="light", # type: ignore
        ).pack(side=RIGHT, padx=3)

    def _create_main_panels(self, fachada: FachadaRegistro):
        """Cria o PanedWindow e instancia os painéis."""
        self._main_paned_window = ttk.PanedWindow(self, orient=HORIZONTAL, bootstyle="light") # type: ignore
        self._main_paned_window.grid(row=1, column=0, sticky="nsew", padx=10, pady=(5, 0))

        self._action_panel = ActionSearchPanel(self._main_paned_window, self, fachada)
        self._main_paned_window.add(self._action_panel, weight=1)

        self._status_panel = StatusRegisteredPanel(self._main_paned_window, self, fachada)
        self._main_paned_window.add(self._status_panel, weight=2)

    def _create_status_bar(self):
        """Cria a barra de status inferior."""
        self._status_bar = ttk.Frame(self, padding=(5, 3), bootstyle=LIGHT, name="statusBarFrame") # type: ignore
        self._status_bar.grid(row=2, column=0, sticky="ew")

        self._status_bar_label = ttk.Label(
            self._status_bar,
            text=UI_TEXTS.get("status_ready", "Pronto."),
            bootstyle="inverse-light", # type: ignore
            font=("-size 10"),
        )
        self._status_bar_label.pack(side=LEFT, padx=5, anchor="w")

        self._progress_bar = ttk.Progressbar(
            self._status_bar, mode="indeterminate", bootstyle="striped-info", length=200 # type: ignore
        )

    def _load_initial_session(self):
        """Tenta carregar a última sessão ativa ou abre o diálogo de sessão."""
        logger.info("Tentando carregar estado inicial da sessão...")
        # TODO: A fachada não tem um método para carregar a última sessão
        # de um arquivo de estado (ex: session.json). A lógica original era:
        # session_info = self._session_manager.load_session()
        # if session_info:
        #     self._setup_ui_for_loaded_session()
        # else:
        #     self.after(100, self._open_session_dialog)
        
        logger.warning("Fachada não suporta carregar sessão de arquivo. Abrindo diálogo.")
        self.after(100, self._open_session_dialog)

    def handle_session_dialog_result(
        self, result: Union[Dict, int, None]
    ) -> bool:
        """Callback chamado pelo SessionDialog."""
        if result is None:
            logger.info("Diálogo de sessão cancelado.")
            if not self._fachada or self._fachada.id_sessao_ativa is None:
                logger.warning("Diálogo cancelado sem sessão ativa.")
            return True

        success = False
        action_desc = ""
        if not self._fachada:
            messagebox.showerror("Erro Interno", "Fachada não encontrada.", parent=self)
            return False

        try:
            if isinstance(result, int):
                session_id = result
                action_desc = f"carregar sessão ID: {session_id}"
                self._fachada.definir_sessao_ativa(session_id)
                success = True

            elif isinstance(result, dict):
                new_session_data = result
                action_desc = f"criar nova sessão: {new_session_data.get('refeicao')}"
                self._fachada.iniciar_nova_sessao(new_session_data) # type: ignore
                success = True
        except Exception as e:
            logger.exception("Falha ao %s: %s", action_desc, e)
            messagebox.showerror(
                "Operação Falhou",
                f"Não foi possível {action_desc}.\nErro: {e}",
                parent=self,
            )
            return False

        if success:
            logger.info("Sucesso ao %s.", action_desc)
            self._setup_ui_for_loaded_session()
            return True
        else:
            return False

    def _setup_ui_for_loaded_session(self):
        """Configura a UI para a sessão ativa."""
        logger.debug("Configurando UI para sessão ativa...")
        if not self._fachada:
            return

        try:
            session_details = self._fachada.obter_detalhes_sessao_ativa()
        except ErroSessaoNaoAtiva:
            logger.error("Não é possível configurar UI: Nenhuma sessão ativa.")
            self.title(UI_TEXTS.get("app_title_no_session", "Registro [Sem Sessão]"))
            if self._session_info_label:
                self._session_info_label.config(text="Erro: Nenhuma Sessão Ativa", bootstyle="inverse-danger") # type: ignore
            if self._action_panel: self._action_panel.disable_controls()
            if self._status_panel: self._status_panel.clear_table()
            return

        if not all([session_details, self._session_info_label, self._action_panel, self._status_panel]):
            logger.error("Componentes da UI ou detalhes da sessão ausentes.")
            return

        try:
            meal_display = capitalize(session_details.get("refeicao", "?"))
            time_display = session_details.get("hora", "??")
            date_raw = session_details.get("data", "")
            display_date = datetime.strptime(date_raw, "%Y-%m-%d").strftime("%d/%m/%Y") if date_raw else ""
            session_id = session_details.get("id")

            title = UI_TEXTS.get("app_title_active_session", "Registro: {meal} - {date} {time} [ID:{id}]").format(
                meal=meal_display, date=display_date, time=time_display, id=session_id
            )
            self.title(title)
            self._session_info_label.config(text=title, bootstyle="inverse-light") # type: ignore

        except Exception as e:
            logger.exception("Erro ao formatar detalhes da sessão para UI: %s", e)
            self.title("RU Registro [Erro na Sessão]")
            if self._session_info_label: self._session_info_label.config(text="Erro ao carregar detalhes", bootstyle="inverse-danger") # type: ignore
            return

        logger.debug("Habilitando painéis e carregando dados...")
        if self._action_panel: self._action_panel.enable_controls()
        if self._status_panel: self._status_panel.load_registered_students()
        if self._action_panel: self._action_panel.refresh_results()

        try:
            self.deiconify(); self.lift(); self.focus_force()
            if self._action_panel: self._action_panel.focus_entry()
        except tk.TclError as e:
            logger.warning("Erro Tcl ao focar/levantar janela: %s", e)
        
        logger.info("UI configurada para sessão ID: %s", session_details.get("id"))

    def _refresh_ui_after_data_change(self):
        """Atualiza os componentes da UI que dependem dos dados da sessão."""
        logger.info("Atualizando UI após mudança nos dados da sessão...")
        if not self._fachada or self._fachada.id_sessao_ativa is None:
            logger.warning("Nenhuma sessão ativa para atualizar a UI.")
            return

        # TODO: A fachada não tem um método explícito para aplicar filtros,
        # mas as buscas já consideram os grupos da sessão.
        # A chamada original era: self._session_manager.filter_eligible_students()

        if self._status_panel: self._status_panel.update_counters()
        if self._action_panel: self._action_panel.refresh_results()
        logger.debug("Refresh da UI concluído.")

    def notify_registration_success(self, student_data: Tuple):
        """Chamado pelo ActionSearchPanel após um registro bem-sucedido."""
        logger.debug("Notificação de registro recebida para: %s", student_data[0])
        if self._status_panel:
            self._status_panel.load_registered_students()

    def handle_consumption_deletion(self, data_for_logic: Tuple, iid_to_delete: str):
        """Processa a exclusão de um registro."""
        # TODO: A fachada (desfazer_consumo) requer um `id_consumo`, que a UI
        # não possui. A UI tem os dados do aluno (prontuário, nome, etc.).
        # Seria necessário um novo método na fachada, como `desfazer_consumo_por_prontuario`.
        # A lógica original era:
        # success = self._session_manager.delete_consumption(data_for_logic)
        pront = data_for_logic[0] if data_for_logic else "N/A"
        nome = data_for_logic[1] if len(data_for_logic) > 1 else "N/A"
        logger.error("Deleção de consumo não é suportada pela fachada atual (requer id_consumo).")
        messagebox.showerror(
            "Funcionalidade Indisponível",
            f"Não é possível remover o registro para {nome} ({pront}).\n"
            "A interface do núcleo (fachada) não suporta esta operação.",
            parent=self,
        )

    def _open_session_dialog(self: "RegistrationApp"):
        """Abre o diálogo para selecionar/criar uma sessão."""
        logger.info("Abrindo diálogo de sessão.")
        SessionDialog(
            title=UI_TEXTS.get("session_dialog_title", "Selecionar ou Criar Sessão"),
            callback=self.handle_session_dialog_result,
            parent_app=self,
        )

    def _open_class_filter_dialog(self):
        """Abre o diálogo para filtrar turmas visíveis."""
        if not self._fachada or self._fachada.id_sessao_ativa is None:
            messagebox.showwarning("Nenhuma Sessão Ativa", "É necessário iniciar uma sessão.", parent=self)
            return
        logger.info("Abrindo diálogo de filtro de turmas.")
        ClassFilterDialog(parent=self, fachada_nucleo=self._fachada, apply_callback=self.on_class_filter_apply) # type: ignore

    def on_class_filter_apply(self, selected_identifiers: List[str]):
        """Callback chamado pelo ClassFilterDialog."""
        logger.info("Aplicando filtros de turma: %s", selected_identifiers)
        if not self._fachada: return

        try:
            # A fachada espera apenas os nomes das turmas, sem o prefixo '#'
            clean_class_names = [name.lstrip('#') for name in selected_identifiers]
            unique_class_names = sorted(list(set(clean_class_names)))
            self._fachada.atualizar_grupos_sessao(unique_class_names)
            logger.info("Filtros de turma aplicados com sucesso no backend.")
            self._refresh_ui_after_data_change()
        except Exception as e:
            logger.exception("Falha ao aplicar filtros de turma via fachada: %s", e)
            messagebox.showerror("Erro ao Filtrar", f"Não foi possível aplicar os filtros.\nErro: {e}", parent=self)

    def show_progress_bar(self, start: bool, text: Optional[str] = None):
        """Mostra ou esconde a barra de progresso."""
        if not self._progress_bar or not self._status_bar_label: return
        try:
            if start:
                progress_text = text or UI_TEXTS.get("status_processing", "Processando...")
                self._status_bar_label.config(text=progress_text)
                if not self._progress_bar.winfo_ismapped():
                    self._progress_bar.pack(side=RIGHT, padx=5, pady=0, fill=X, expand=False)
                self._progress_bar.start(10)
            else:
                if self._progress_bar.winfo_ismapped():
                    self._progress_bar.stop()
                    self._progress_bar.pack_forget()
                self._status_bar_label.config(text=UI_TEXTS.get("status_ready", "Pronto."))
        except tk.TclError as e:
            logger.error("Erro Tcl ao manipular barra de progresso: %s", e)

    def _sync_master_data(self):
        """Inicia a sincronização dos dados mestre."""
        if not self._fachada: return
        if not messagebox.askyesno("Confirmar Sincronização", "Deseja sincronizar os dados mestre?", parent=self):
            return
        self.show_progress_bar(True, "Sincronizando cadastros...")
        self._start_sync_thread(self._fachada.sincronizar_do_google_sheets, "Sincronização de Cadastros")

    def sync_session_with_spreadsheet(self):
        """Inicia a sincronização dos registros servidos."""
        if not self._fachada or self._fachada.id_sessao_ativa is None:
            messagebox.showwarning("Nenhuma Sessão Ativa", "É necessário ter uma sessão ativa para sincronizar.", parent=self)
            return
        self.show_progress_bar(True, "Sincronizando servidos para planilha...")
        self._start_sync_thread(self._fachada.sincronizar_para_google_sheets, "Sincronização de Servidos")

    def _start_sync_thread(self, sync_function: callable, task_name: str):
        """Cria e monitora uma thread para uma função de sincronização da fachada."""
        def sync_action():
            thread.error = None
            thread.success = False
            try:
                sync_function()
                thread.success = True
            except Exception as e:
                thread.error = e

        thread = Thread(target=sync_action, daemon=True)
        thread.error = None # type: ignore
        thread.success = False # type: ignore
        thread.start()
        self._monitor_sync_thread(thread, task_name)

    def _monitor_sync_thread(self, thread: Thread, task_name: str):
        """Verifica periodicamente se uma thread terminou e atualiza a UI."""
        if thread.is_alive():
            self.after(150, lambda: self._monitor_sync_thread(thread, task_name))
            return
        
        self.show_progress_bar(False)
        error = getattr(thread, "error", None)
        success = getattr(thread, "success", False)

        if error:
            logger.error("%s falhou: %s", task_name, error)
            messagebox.showerror("Erro na Sincronização", f"{task_name} falhou:\n{error}", parent=self)
        elif success:
            logger.info("%s concluída com sucesso.", task_name)
            messagebox.showinfo("Sincronização Concluída", f"{task_name} concluída com sucesso.", parent=self)
            self._refresh_ui_after_data_change()
        else:
            logger.warning("%s finalizada com estado indeterminado.", task_name)
            messagebox.showwarning("Status Desconhecido", f"{task_name} finalizada, mas o status é incerto.", parent=self)

    def export_session_to_excel(self) -> bool:
        """Exporta os dados da sessão atual para um arquivo Excel."""
        if not self._fachada: return False
        try:
            file_path = self._fachada.exportar_sessao_para_xlsx()
            logger.info("Dados da sessão exportados para: %s", file_path)
            messagebox.showinfo("Exportação Concluída", f"Dados exportados com sucesso para:\n{file_path}", parent=self)
            return True
        except ErroSessaoNaoAtiva:
            messagebox.showwarning("Nenhuma Sessão Ativa", "Não há sessão ativa para exportar.", parent=self)
        except ValueError as ve: # Ex: Ninguém consumiu
             messagebox.showwarning("Nada para Exportar", str(ve), parent=self)
        except Exception as e:
            logger.exception("Erro inesperado durante a exportação para Excel.")
            messagebox.showerror("Erro na Exportação", f"Ocorreu um erro ao exportar:\n{e}", parent=self)
        return False

    def export_and_end_session(self):
        """Exporta dados, limpa o estado da sessão e fecha a aplicação."""
        if not self._fachada or self._fachada.id_sessao_ativa is None:
            messagebox.showwarning("Nenhuma Sessão Ativa", "Não há sessão ativa para encerrar.", parent=self)
            return
        if not messagebox.askyesno("Confirmar Encerramento", "Deseja exportar os dados e encerrar esta sessão?", icon="warning", parent=self):
            return

        export_successful = self.export_session_to_excel()
        if not export_successful:
            if not messagebox.askyesno("Falha na Exportação", "A exportação falhou. Deseja encerrar mesmo assim?", icon="error", parent=self):
                return

        # TODO: A fachada não gerencia o arquivo session.json.
        # A limpeza do estado local não pode ser feita. A sessão no banco de dados
        # permanece, mas a aplicação fechará. A lógica original era:
        # state_cleaned = self._remove_session_state_file()
        logger.warning("A fachada não gerencia o estado local (session.json). Apenas fechando.")
        
        self.on_close_app(triggered_by_end_session=True)

    def on_close_app(self, triggered_by_end_session: bool = False):
        """Ações ao fechar a janela."""
        logger.info("Sequência de fechamento da aplicação iniciada...")

        if self._action_panel and self._action_panel.search_after_id is not None:
            try:
                self._action_panel.after_cancel(self._action_panel.search_after_id)
            except Exception: pass

        if self._fachada:
            # TODO: A fachada não tem um método para salvar o estado da sessão
            # em um arquivo. A lógica original era:
            # if not triggered_by_end_session:
            #     self._session_manager.save_session_state()
            logger.info("Fechando recursos da fachada (conexão com DB)...")
            self._fachada.fechar_conexao()

        logger.debug("Destruindo janela principal Tkinter...")
        try:
            self.destroy()
        except tk.TclError: pass
        logger.info("Aplicação finalizada.")
```

---
#### **`registro/view/status_registered_panel.py`**
As chamadas ao `SessionManager` foram trocadas pelas da fachada. A atualização de contadores e a remoção de registros foram marcadas com `TODO` devido à falta de métodos equivalentes na fachada.

```python
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

from registro.control.constants import UI_TEXTS
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
        self._fachada:FachadaRegistro = fachada_nucleo

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
                "stretch": False, "width": 100, "iid": "pront", "minwidth": 80,
            },
            {
                "text": UI_TEXTS.get("col_nome", "✍️ Nome"),
                "stretch": True, "iid": "nome", "minwidth": 150,
            },
            {
                "text": UI_TEXTS.get("col_turma", "👥 Turma"),
                "stretch": False, "width": 150, "iid": "turma", "minwidth": 100,
            },
            {
                "text": UI_TEXTS.get("col_hora", "⏱️ Hora"),
                "stretch": False, "width": 70, "anchor": CENTER, "iid": "hora", "minwidth": 60,
            },
            {
                "text": UI_TEXTS.get("col_prato_status", "🍽️ Prato/Status"),
                "stretch": True, "width": 150, "iid": "prato", "minwidth": 100,
            },
            {
                "text": self.ACTION_COLUMN_TEXT, "stretch": False, "width": 40,
                "anchor": CENTER, "iid": self.ACTION_COLUMN_ID, "minwidth": 30,
            },
        ]

    def _create_counters_area(self):
        """Cria a área inferior com os labels de contagem."""
        counters_frame = ttk.Frame(self, padding=(0, 5))
        counters_frame.grid(row=1, column=0, sticky="ew")
        counters_frame.columnconfigure(0, weight=1)
        counters_frame.columnconfigure(1, weight=1)

        self._registered_count_label = ttk.Label(
            counters_frame, text=UI_TEXTS.get("registered_count_label", "Registrados: -"),
            bootstyle="secondary", font=("Helvetica", 10, "bold"), padding=(5, 2), anchor=CENTER, # type: ignore
        )
        self._registered_count_label.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self._remaining_count_label = ttk.Label(
            counters_frame, text=UI_TEXTS.get("remaining_count_label", "Elegíveis: - / Restantes: -"),
            bootstyle="secondary", font=("Helvetica", 10, "bold"), padding=(5, 2), anchor=CENTER, # type: ignore
        )
        self._remaining_count_label.grid(row=0, column=1, sticky="ew", padx=(5, 0))

    def _create_registered_table(self):
        """Cria a tabela para exibir os alunos registrados."""
        reg_frame = ttk.Labelframe(
            self, text=UI_TEXTS.get("registered_students_label", "✅ Alunos Registrados (Clique ❌ para Remover)"),
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
            str(cd.get("iid")) for cd in self._registered_cols_definition
            if cd.get("iid") and cd.get("iid") != self.ACTION_COLUMN_ID
        ]
        self._registered_students_table.setup_sorting(sortable_columns=sortable_cols or None)

    def load_registered_students(self):
        """Carrega ou recarrega os dados na tabela de alunos registrados."""
        if not self._registered_students_table: return
        logger.debug("Carregando tabela de registrados...")
        try:
            # Usa a fachada para obter os alunos que já consumiram
            served_data = self._fachada.obter_estudantes_para_sessao(consumido=True)
            if served_data:
                rows_with_action = []
                # A fachada retorna dicts: pront, nome, turma, hora_consumo, prato
                for student in served_data:
                    display_prato = student.get("prato") or UI_TEXTS.get("no_reservation_status", "Sem Reserva")
                    row = (
                        student.get("pront", ""),
                        student.get("nome", ""),
                        student.get("turma", ""),
                        student.get("hora_consumo", ""),
                        display_prato,
                    )
                    final_row = tuple(map(str, row)) + (self.ACTION_COLUMN_TEXT,)
                    rows_with_action.append(final_row)
                
                self._registered_students_table.build_table_data(rowdata=rows_with_action)
                logger.info("Carregados %d alunos registrados na tabela.", len(rows_with_action))
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
            messagebox.showerror("Erro", "Não foi possível carregar a lista de registrados.", parent=self._app)
            if self._registered_students_table: self._registered_students_table.delete_rows()
            self.update_counters()

    def update_counters(self):
        """Atualiza os labels dos contadores."""
        if not self._registered_count_label or not self._remaining_count_label: return

        reg_text = UI_TEXTS.get("registered_count_label", "Registrados: -")
        rem_text = UI_TEXTS.get("remaining_count_label", "Elegíveis: - / Restantes: -")
        reg_style, rem_style = "secondary", "secondary"
        
        try:
            # TODO: A fachada não tem métodos otimizados para contagem.
            # Os métodos `obter_estudantes_para_sessao` retornam listas
            # completas, cujo `len()` pode ser usado, mas é menos eficiente
            # que uma contagem direta no banco.
            registered_list = self._fachada.obter_estudantes_para_sessao(consumido=True)
            eligible_not_served_list = self._fachada.obter_estudantes_para_sessao(consumido=False)
            
            registered_count = len(registered_list)
            remaining_count = len(eligible_not_served_list)
            total_eligible_count = registered_count + remaining_count

            reg_text = UI_TEXTS.get("registered_count_label", "Registrados: {count}").format(count=registered_count)
            rem_text = UI_TEXTS.get(
                "remaining_count_label", "Elegíveis: {eligible_count} / Restantes: {remaining_count}"
            ).format(eligible_count=total_eligible_count, remaining_count=remaining_count)
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
            
        self._registered_count_label.config(text=reg_text, bootstyle=reg_style) # type: ignore
        self._remaining_count_label.config(text=rem_text, bootstyle=rem_style) # type: ignore

    def clear_table(self):
        """Limpa a tabela e reseta contadores."""
        logger.debug("Limpando tabela de registrados e contadores.")
        if self._registered_students_table:
            self._registered_students_table.delete_rows()
        self.update_counters()

    def remove_row_from_table(self, iid_to_delete: str):
        """Remove uma linha da tabela e atualiza contadores."""
        if not self._registered_students_table: return
        try:
            if self._registered_students_table.view.exists(iid_to_delete):
                self._registered_students_table.delete_rows([iid_to_delete])
                logger.debug("Linha %s removida da tabela UI.", iid_to_delete)
                self.update_counters()
            else:
                logger.warning("Tentativa de remover IID %s que não existe.", iid_to_delete)
                self.load_registered_students()
        except Exception as e:
            logger.exception("Erro ao remover linha %s da UI: %s", iid_to_delete, e)
            self.load_registered_students()

    def _on_registered_table_click(self, event: tk.Event):
        """Handler para cliques na tabela."""
        if not self._registered_students_table: return
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
        if not self._registered_students_table: return
        selected_iid = self._registered_students_table.get_selected_iid()
        if selected_iid:
            logger.debug("Tecla Delete pressionada para iid: %s", selected_iid)
            self._confirm_and_delete_consumption(selected_iid)

    def _confirm_and_delete_consumption(self, iid_to_delete: str):
        """Pede confirmação e chama a App principal para deletar."""
        if not self._registered_students_table: return

        row_values_full = self._registered_students_table.get_row_values(iid_to_delete)
        if not row_values_full or len(row_values_full) != len(self._registered_cols_definition):
            logger.error("Não foi possível obter valores válidos para iid %s.", iid_to_delete)
            messagebox.showerror("Erro Interno", "Erro ao obter dados da linha.", parent=self._app)
            return

        try:
            # A fachada não precisa de todos os dados, mas usamos para a msg de confirmação
            data_for_logic = tuple(row_values_full[:5])
            pront, nome = data_for_logic[0], data_for_logic[1]
            if not pront: raise ValueError("Prontuário vazio.")
        except (IndexError, ValueError) as e:
            logger.error("Erro ao extrair dados da linha %s: %s.", iid_to_delete, e)
            messagebox.showerror("Erro de Dados", "Erro ao processar dados da linha.", parent=self._app)
            return

        confirm_msg = UI_TEXTS.get("confirm_deletion_message",
            "Tem certeza que deseja remover o registro para:\n\nProntuário: {pront}\nNome: {nome}?"
        ).format(pront=pront, nome=nome)

        if messagebox.askyesno("Confirmar Remoção", confirm_msg, icon=WARNING, parent=self._app):
            logger.info("Confirmada exclusão para %s (iid UI: %s).", pront, iid_to_delete)
            self._app.handle_consumption_deletion(data_for_logic, iid_to_delete)
        else:
            logger.debug("Exclusão de %s cancelada.", pront)
```

---
*Os demais arquivos (`__init__.py`, `simple_treeview.py`, `facade.py`) não precisaram de modificações, pois são, respectivamente, um marcador de pacote, um componente de UI genérico e as próprias fachadas que deveriam ser usadas.*
