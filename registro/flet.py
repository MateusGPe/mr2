import flet as ft
from datetime import datetime


class MockFachada:
    def __init__(self):
        self.alunos = [
            {"id": i, "nome": f"Estudante {i}", "prontuario": f"SP303{i:03}",
                "grupos": ["Integrado"], "ativo": True}
            for i in range(1, 30)
        ]
        self.reservas = [
            {"id": i, "data": datetime.now().strftime("%d/%m/%Y"), "nome_estudante": f"Estudante {i}",
             "prontuario_estudante": f"SP303{i:03}", "prato": "Tradicional", "cancelada": i % 5 == 0}
            for i in range(100, 120)
        ]

    def listar_estudantes_fuzzy(self, termo_busca="", limite=100):
        if not termo_busca:
            return self.alunos
        return [a for a in self.alunos if termo_busca.lower() in a["nome"].lower()]

    def criar_estudante(self, prontuario, nome, grupos):
        new_id = max([a['id'] for a in self.alunos]) + 1 if self.alunos else 1
        self.alunos.insert(0, {"id": new_id, "nome": nome,
                           "prontuario": prontuario, "grupos": grupos, "ativo": True})

    def atualizar_estudante(self, id_aluno, dados):
        for a in self.alunos:
            if a['id'] == id_aluno:
                a.update(dados)

    def listar_reservas(self, filtros=None):
        data_filtro = filtros.get('data') if filtros else None
        res = self.reservas
        if data_filtro:
            res = [r for r in res if r['data'] == data_filtro]
        return res

    def atualizar_reserva(self, id_reserva, payload):
        for r in self.reservas:
            if r['id'] == id_reserva:
                r.update(payload)

    def listar_todos_os_grupos(self):
        return [{"nome": "Integrado"}, {"nome": "Superior"}, {"nome": "Servidores"}]

    def analisar_arquivo(self, path, tipo):
        return {
            "resumo": {"automaticos": 15, "para_revisao": 2, "invalidos": 0},
            "itens_revisao": [
                {"dados_csv": {"nome": "João Silva", "prontuario": "123"},
                    "tipo_conflito": "nome_similar", "resolucao_escolhida": "IGNORAR"},
                {"dados_csv": {"nome": "Maria", "prontuario": ""},
                    "tipo_conflito": "sem_prontuario", "resolucao_escolhida": "CRIAR_NOVO"}
            ]
        }

    def simular_importacao(self, itens, defaults):
        return {"novos_estudantes": [{"prontuario": "SP999", "nome": "Novo Aluno 1"}], "reservas": [{"data": "28/11/2025", "prontuario": "SP999", "aluno": "Novo Aluno 1", "prato": "Almoço"}]}


class DashboardView(ft.Container):
    def __init__(self):
        super().__init__()
        self.padding = 20
        self.expand = True
        self.content = ft.Column([
            ft.Text("Dashboard", size=32, weight=ft.FontWeight.BOLD),
            ft.Text("Visão geral do refeitório.",
                    color=ft.Colors.SURFACE_CONTAINER_HIGHEST),
            ft.Divider(height=30, color=ft.Colors.TRANSPARENT),
            ft.Row([
                self._create_card(ft.Icons.PEOPLE, "Alunos Ativos",
                                  "1,240", ft.Colors.BLUE_800, "+12 esta semana"),
                self._create_card(ft.Icons.RESTAURANT_MENU, "Reservas Hoje",
                                  "342", ft.Colors.ORANGE_800, "85% capacidade"),
                self._create_card(ft.Icons.CHECK_CIRCLE, "Consumo Ontem",
                                  "310", ft.Colors.GREEN_800, "Desperdício: 2%"),
            ], wrap=True, spacing=20)
        ], scroll=ft.ScrollMode.AUTO)

    def _create_card(self, icon, title, value, color, subtitle):
        return ft.Container(
            content=ft.Column([
                ft.Row([ft.Icon(icon, color="white"), ft.Text(
                    title, color="white70", weight="bold")]),
                ft.Text(value, size=40, weight="bold", color="white"),
                ft.Text(subtitle, color="white54", size=12)
            ]),
            width=260, height=140, bgcolor=color, border_radius=15, padding=20,
            shadow=ft.BoxShadow(
                blur_radius=10, color=ft.Colors.with_opacity(0.4, ft.Colors.BLACK))
        )


class AlunosView(ft.Container):
    def __init__(self, fachada):
        super().__init__()
        self.fachada = fachada
        self.expand = True
        self.padding = 20

        self.txt_busca = ft.TextField(
            hint_text="Buscar aluno...", prefix_icon=ft.Icons.SEARCH,
            width=300, on_change=self._on_search, border_radius=30, height=40, content_padding=10
        )

        self.tabela = ft.DataTable(

            width=float("inf"),

            heading_row_color=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            columns=[
                ft.DataColumn(ft.Text("ID")),
                ft.DataColumn(ft.Text("Nome")),
                ft.DataColumn(ft.Text("Prontuário")),
                ft.DataColumn(ft.Text("Grupos")),
                ft.DataColumn(ft.Text("Status")),
                ft.DataColumn(ft.Text("Ações")),
            ],
            expand=True
        )

        self.content = ft.Column([
            ft.Row([
                ft.Text("Gerenciar Alunos", size=28,
                        weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                self.txt_busca,
                ft.FloatingActionButton(
                    icon=ft.Icons.ADD, text="Novo", on_click=lambda e: self._abrir_modal())
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(),

            ft.Column([self.tabela], scroll=ft.ScrollMode.AUTO, expand=True)
        ], expand=True)

    def did_mount(self):
        self._carregar_dados()

    def _carregar_dados(self, termo=""):
        self.tabela.rows.clear()
        dados = self.fachada.listar_estudantes_fuzzy(termo)
        for aluno in dados:

            status_bg = ft.Colors.GREEN_900 if aluno['ativo'] else ft.Colors.RED_900
            status_fg = ft.Colors.GREEN_100 if aluno['ativo'] else ft.Colors.RED_100

            self.tabela.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(aluno['id']))),
                    ft.DataCell(ft.Text(aluno['nome'], weight="bold")),


                    ft.DataCell(ft.Container(
                        content=ft.Text(
                            aluno['prontuario'], size=12, weight="bold", color=ft.Colors.ON_PRIMARY_CONTAINER),

                        bgcolor=ft.Colors.PRIMARY_CONTAINER,
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        border_radius=6
                    )),

                    ft.DataCell(ft.Text(", ".join(aluno['grupos']))),


                    ft.DataCell(ft.Container(
                        content=ft.Text(
                            "Ativo" if aluno['ativo'] else "Inativo", color=status_fg, size=11, weight="bold"),
                        bgcolor=status_bg,
                        padding=ft.padding.symmetric(
                            horizontal=10, vertical=4),
                        border_radius=12
                    )),

                    ft.DataCell(ft.IconButton(
                        icon=ft.Icons.EDIT, icon_color=ft.Colors.PRIMARY,
                        data=aluno, on_click=lambda e: self._abrir_modal(
                            e.control.data)
                    ))
                ])
            )
        self.update()

    def _on_search(self, e):
        self._carregar_dados(e.control.value)

    def _abrir_modal(self, aluno=None):
        is_edit = aluno is not None
        nome_field = ft.TextField(
            label="Nome", value=aluno['nome'] if is_edit else "")
        pront_field = ft.TextField(
            label="Prontuário", value=aluno['prontuario'] if is_edit else "")
        grupos = self.fachada.listar_todos_os_grupos()
        dd_grupo = ft.Dropdown(
            label="Grupo",
            options=[ft.dropdown.Option(g['nome']) for g in grupos],
            value=aluno['grupos'][0] if is_edit and aluno['grupos'] else None
        )

        def salvar(e):
            if not nome_field.value or not pront_field.value:
                self.page.open(ft.SnackBar(
                    ft.Text("Preencha todos os campos!"), bgcolor=ft.Colors.RED))
                return
            grupos_sel = [dd_grupo.value] if dd_grupo.value else []
            if is_edit:
                self.fachada.atualizar_estudante(
                    aluno['id'], {"nome": nome_field.value, "grupos": grupos_sel})
            else:
                self.fachada.criar_estudante(
                    pront_field.value, nome_field.value, grupos_sel)
            self.page.close(dlg)
            self._carregar_dados(self.txt_busca.value)
            self.page.open(ft.SnackBar(
                ft.Text("Salvo com sucesso!"), bgcolor=ft.Colors.GREEN))

        dlg = ft.AlertDialog(
            title=ft.Text("Editar Aluno" if is_edit else "Novo Aluno"),
            content=ft.Column(
                [nome_field, pront_field, dd_grupo], tight=True, width=400),
            actions=[
                ft.TextButton(
                    "Cancelar", on_click=lambda e: self.page.close(dlg)),
                ft.FilledButton("Salvar", on_click=salvar)
            ]
        )
        self.page.open(dlg)


class ReservasView(ft.Container):
    def __init__(self, fachada):
        super().__init__()
        self.fachada = fachada
        self.expand = True
        self.padding = 20

        self.date_picker = ft.DatePicker(on_change=self._on_date_change)
        self.btn_date = ft.ElevatedButton(
            "Filtrar Data", icon=ft.Icons.CALENDAR_MONTH, on_click=lambda _: self.page.open(self.date_picker))

        self.tabela = ft.DataTable(
            width=float("inf"),
            heading_row_color=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            columns=[
                ft.DataColumn(ft.Text("Data")),
                ft.DataColumn(ft.Text("Aluno")),
                ft.DataColumn(ft.Text("Prato")),
                ft.DataColumn(ft.Text("Status")),
                ft.DataColumn(ft.Text("Ações")),
            ],
            expand=True
        )

        self.content = ft.Column([
            ft.Row([
                ft.Text("Reservas", size=28, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                self.btn_date,
            ]),
            ft.Divider(),
            ft.Column([self.tabela], scroll=ft.ScrollMode.AUTO, expand=True)
        ], expand=True)

    def did_mount(self):
        self._carregar_dados()

    def _on_date_change(self, e):
        data_str = e.control.value.strftime('%d/%m/%Y')
        self.btn_date.text = f"Data: {data_str}"
        self.btn_date.update()
        self._carregar_dados(data_str)

    def _carregar_dados(self, data_filtro=None):
        filtros = {"data": data_filtro} if data_filtro else None
        reservas = self.fachada.listar_reservas(filtros)

        self.tabela.rows.clear()
        for r in reservas:
            cancelada = r.get('cancelada', False)
            bg_color = ft.Colors.ERROR_CONTAINER if cancelada else ft.Colors.TERTIARY_CONTAINER
            fg_color = ft.Colors.ON_ERROR_CONTAINER if cancelada else ft.Colors.ON_TERTIARY_CONTAINER

            self.tabela.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(r['data'])),
                    ft.DataCell(ft.Column([
                        ft.Text(r['nome_estudante'], weight="bold"),
                        ft.Text(r['prontuario_estudante'], size=10,
                                color=ft.Colors.SURFACE_CONTAINER_HIGHEST)
                    ], spacing=2, alignment=ft.MainAxisAlignment.CENTER)),
                    ft.DataCell(ft.Text(r['prato'])),
                    ft.DataCell(ft.Container(
                        content=ft.Text(
                            "Cancelada" if cancelada else "Ativa", color=fg_color, size=11, weight="bold"),
                        bgcolor=bg_color,
                        padding=ft.padding.symmetric(
                            horizontal=10, vertical=4),
                        border_radius=12
                    )),
                    ft.DataCell(ft.IconButton(
                        icon=ft.Icons.EDIT, icon_color=ft.Colors.PRIMARY,
                        data=r, on_click=lambda e: self._editar_reserva(
                            e.control.data)
                    ))
                ])
            )
        self.update()

    def _editar_reserva(self, reserva):
        sw_cancelada = ft.Switch(
            label="Cancelar Reserva", value=reserva['cancelada'])

        def salvar(e):
            self.fachada.atualizar_reserva(
                reserva['id'], {"cancelada": sw_cancelada.value})
            self.page.close(dlg)
            self._carregar_dados(self.date_picker.value.strftime(
                '%d/%m/%Y') if self.date_picker.value else None)

        dlg = ft.AlertDialog(
            title=ft.Text("Editar Reserva"),
            content=ft.Column(
                [ft.Text(f"Aluno: {reserva['nome_estudante']}"), sw_cancelada], tight=True),
            actions=[ft.TextButton("Cancelar", on_click=lambda e: self.page.close(
                dlg)), ft.FilledButton("Salvar", on_click=salvar)]
        )
        self.page.open(dlg)


class ImportacaoWizard(ft.Container):
    def __init__(self, fachada):
        super().__init__()
        self.fachada = fachada
        self.expand = True
        self.padding = 20

        self.file_picker = ft.FilePicker(on_result=self._on_file_pick)

        self.step_content = ft.Container(expand=True)
        self.progress = ft.ProgressBar(value=0.25, height=5)
        self.lbl_titulo = ft.Text("Passo 1: Arquivo", size=20, weight="bold")

        self.path = None
        self.itens_revisao = []

        self.content = ft.Column([
            self.lbl_titulo,
            self.progress,
            ft.Divider(color=ft.Colors.TRANSPARENT, height=20),
            self.step_content
        ], expand=True)

    def did_mount(self):

        if self.file_picker not in self.page.overlay:
            self.page.overlay.append(self.file_picker)
            self.page.update()

        if not self.step_content.content:
            self._go_step_1()

    def will_unmount(self):

        if self.file_picker in self.page.overlay:
            self.page.overlay.remove(self.file_picker)
            self.page.update()

    def _on_file_pick(self, e: ft.FilePickerResultEvent):
        if e.files:
            self.path = e.files[0].path
            self.txt_file.value = self.path
            self.txt_file.update()

    def _go_step_1(self):
        self.progress.value = 0.25
        self.lbl_titulo.value = "Passo 1: Selecionar Arquivo"
        self.txt_file = ft.TextField(
            read_only=True, label="Arquivo", expand=True)

        self.step_content.content = ft.Column([
            ft.Row([
                self.txt_file,
                ft.ElevatedButton("Buscar", icon=ft.Icons.FOLDER,
                                  on_click=lambda _: self.file_picker.pick_files())
            ]),
            ft.Container(expand=True),
            ft.Row([ft.FilledButton("Próximo >", on_click=self._go_step_2)],
                   alignment=ft.MainAxisAlignment.END)
        ])
        self.update()

    def _go_step_2(self, e):
        if not self.path:
            self.page.open(ft.SnackBar(ft.Text("Selecione um arquivo!")))
            return

        res = self.fachada.analisar_arquivo(self.path, "auto")
        self.itens_revisao = res['itens_revisao']

        self.progress.value = 0.50
        self.lbl_titulo.value = "Passo 2: Revisão"

        lv = ft.ListView(expand=True, spacing=10)
        for item in self.itens_revisao:
            lv.controls.append(ft.Container(
                content=ft.Row([
                    ft.Text(item['dados_csv']['nome'],
                            weight="bold", expand=True),

                    ft.Chip(label=ft.Text(
                        item['resolucao_escolhida']), bgcolor=ft.Colors.AMBER_900)
                ]),
                padding=10, border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT), border_radius=5
            ))

        self.step_content.content = ft.Column([
            ft.Text(f"{len(self.itens_revisao)} conflitos encontrados."),
            lv,
            ft.Row([
                ft.OutlinedButton(
                    "Voltar", on_click=lambda _: self._go_step_1()),
                ft.FilledButton("Simular >", on_click=self._go_step_3)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        ])
        self.update()

    def _go_step_3(self, e):
        self.progress.value = 0.75
        self.lbl_titulo.value = "Passo 3: Confirmação"
        res = self.fachada.simular_importacao(self.itens_revisao, {})

        self.step_content.content = ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Text(f"Novos Alunos: {len(res['novos_estudantes'])}"),
                    ft.Text(f"Novas Reservas: {len(res['reservas'])}")
                ]),
                bgcolor=ft.Colors.PRIMARY_CONTAINER,
                padding=20,
                border_radius=10
            ),
            ft.Container(expand=True),
            ft.Row([
                ft.OutlinedButton(
                    "Voltar", on_click=lambda _: self._go_step_2(None)),
                ft.FilledButton("CONCLUIR", on_click=self._go_step_4)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        ])
        self.update()

    def _go_step_4(self, e):
        self.progress.value = 1.0
        self.lbl_titulo.value = "Sucesso!"

        conteudo_sucesso = ft.Column(
            [
                ft.Icon(ft.Icons.CHECK_CIRCLE, size=100,
                        color=ft.Colors.GREEN),
                ft.Text(
                    "Importação realizada com sucesso!",
                    size=20,
                    weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.ElevatedButton("Nova Importação",
                                  on_click=lambda _: self._go_step_1())
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20
        )

        self.step_content.content = ft.Container(
            content=conteudo_sucesso,
            alignment=ft.alignment.center,
            expand=True
        )
        self.update()


def main(page: ft.Page):
    page.title = "Sistema Refeitório"
    page.padding = 0

    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(color_scheme_seed="blue")

    fachada = MockFachada()

    views = [DashboardView(), AlunosView(fachada), ReservasView(
        fachada), ImportacaoWizard(fachada)]
    body_container = ft.Container(content=views[0], expand=True)

    def change_nav(e):
        idx = e.control.selected_index
        body_container.content = views[idx]
        body_container.update()

    rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=200,
        group_alignment=-0.9,
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.Icons.DASHBOARD, label="Dashboard"),
            ft.NavigationRailDestination(icon=ft.Icons.PEOPLE, label="Alunos"),
            ft.NavigationRailDestination(
                icon=ft.Icons.CALENDAR_MONTH, label="Reservas"),
            ft.NavigationRailDestination(
                icon=ft.Icons.UPLOAD, label="Importar"),
        ],
        on_change=change_nav,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        expand=True
    )

    toggle_dark = ft.IconButton(
        icon=ft.Icons.LIGHT_MODE,
        tooltip="Alternar Tema",
        on_click=lambda e: _toggle_theme(e)
    )

    def _toggle_theme(e):
        page.theme_mode = ft.ThemeMode.LIGHT if page.theme_mode == ft.ThemeMode.DARK else ft.ThemeMode.DARK
        e.control.icon = ft.Icons.DARK_MODE if page.theme_mode == ft.ThemeMode.LIGHT else ft.Icons.LIGHT_MODE
        page.update()

    page.add(
        ft.Row([
            ft.Container(
                content=ft.Column([
                    ft.Container(content=ft.Icon(
                        ft.Icons.RESTAURANT_MENU, size=30, color=ft.Colors.PRIMARY), padding=20),
                    ft.Container(content=rail, expand=True),
                    ft.Container(content=toggle_dark, padding=10)
                ], expand=True),
                width=100,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST
            ),
            ft.VerticalDivider(width=1, thickness=1,
                               color=ft.Colors.OUTLINE_VARIANT),
            body_container
        ], expand=True, spacing=0)
    )


if __name__ == "__main__":
    ft.app(target=main)
