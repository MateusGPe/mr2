import traceback
import flet as ft
from registro.nucleo.facade import FachadaRegistro
from registro.interface.utils import show_error, show_success

class AlunosView(ft.Container):
    """Tela de listagem e edição de estudantes."""

    def __init__(self, fachada_nucleo: FachadaRegistro):
        super().__init__()
        self.fachada = fachada_nucleo
        self.expand = True
        self.padding = 20

        self.txt_busca = ft.TextField(
            hint_text="Buscar por nome ou prontuário...",
            prefix_icon=ft.Icons.SEARCH,
            width=300,
            on_change=self._on_search,
            border_radius=30, height=40, content_padding=10
        )

        self.tabela = ft.DataTable(
            width=float("inf"),
            heading_row_color=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            columns=[
                ft.DataColumn(ft.Text("ID"), numeric=True),
                ft.DataColumn(ft.Text("Nome")),
                ft.DataColumn(ft.Text("Prontuário")),
                ft.DataColumn(ft.Text("Grupos")),
                ft.DataColumn(ft.Text("Ativo")),
                ft.DataColumn(ft.Text("Ações")),
            ],
            expand=True
        )

        self.content = ft.Column([
            ft.Row([
                ft.Text("Gerenciar Alunos", size=28, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                self.txt_busca,
                ft.FloatingActionButton(icon=ft.Icons.ADD, text="Novo", on_click=lambda e: self._abrir_modal())
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(),
            ft.Column([self.tabela], scroll=ft.ScrollMode.AUTO, expand=True)
        ], expand=True)

    def did_mount(self):
        self._carregar_dados()

    def _carregar_dados(self, termo=""):
        self.tabela.rows.clear()
        try:
            dados = self.fachada.listar_estudantes_fuzzy(termo_busca=termo, limite=70)
            
            for aluno in dados:
                ativo = aluno.get('ativo', True)
                status_color = ft.Colors.GREEN_100 if ativo else ft.Colors.RED_100
                status_bg = ft.Colors.GREEN_900 if ativo else ft.Colors.RED_900
                
                self.tabela.rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(aluno['id']))),
                    ft.DataCell(ft.Text(aluno['nome'], weight="bold")),
                    ft.DataCell(ft.Container(
                        content=ft.Text(aluno['prontuario'], size=12, weight="bold", color=ft.Colors.ON_PRIMARY_CONTAINER),
                        bgcolor=ft.Colors.PRIMARY_CONTAINER, padding=ft.padding.symmetric(horizontal=8, vertical=4), border_radius=6
                    )),
                    ft.DataCell(ft.Text(", ".join(aluno.get('grupos', [])))),
                    ft.DataCell(ft.Container(
                        content=ft.Text("Sim" if ativo else "Não", color=status_color, size=11, weight="bold"),
                        bgcolor=status_bg, padding=ft.padding.symmetric(horizontal=10, vertical=4), border_radius=12
                    )),
                    ft.DataCell(ft.IconButton(
                        icon=ft.Icons.EDIT, icon_color=ft.Colors.PRIMARY,
                        data=aluno, on_click=lambda e: self._abrir_modal(e.control.data)
                    ))
                ]))
            self.update()
        except Exception as e:
            traceback.print_exc()
            show_error(self.page, f"Erro ao carregar alunos: {e}")

    def _on_search(self, e):
        self._carregar_dados(e.control.value)

    def _abrir_modal(self, aluno=None):
        """Abre diálogo para criar ou editar aluno."""
        is_edit = aluno is not None
        
        nome_field = ft.TextField(label="Nome Completo", value=aluno['nome'] if is_edit else "", autofocus=True)
        pront_field = ft.TextField(label="Prontuário", value=aluno['prontuario'] if is_edit else "", read_only=is_edit)
        
        
        try:
            grupos_db = self.fachada.listar_todos_os_grupos()
            opcoes = [ft.dropdown.Option(g['nome']) for g in grupos_db]
        except:
            opcoes = []

        val_inicial = aluno['grupos'][0] if is_edit and aluno.get('grupos') else (opcoes[0].key if opcoes else None)
        dd_grupo = ft.Dropdown(label="Turma/Grupo", options=opcoes, value=val_inicial, expand=True)

        def salvar(e):
            if not nome_field.value or not pront_field.value:
                show_error(self.page, "Preencha todos os campos.")
                return
            
            try:
                grupos = [dd_grupo.value] if dd_grupo.value else []
                if is_edit:
                    self.fachada.atualizar_estudante(aluno['id'], {"nome": nome_field.value})
                else:
                    self.fachada.criar_estudante(pront_field.value, nome_field.value, grupos=grupos)
                
                self.page.close(dlg)
                self._carregar_dados(self.txt_busca.value)
                show_success(self.page, "Salvo com sucesso!")
            except ValueError as ve:
                show_error(self.page, str(ve))
            except Exception as ex:
                traceback.print_exc()
                show_error(self.page, f"Erro interno: {ex}")

        dlg = ft.AlertDialog(
            title=ft.Text("Editar Aluno" if is_edit else "Adicionar Aluno"),
            content=ft.Column([nome_field, pront_field, dd_grupo], tight=True, width=400),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: self.page.close(dlg)),
                ft.FilledButton("Salvar", on_click=salvar)
            ]
        )
        self.page.open(dlg)