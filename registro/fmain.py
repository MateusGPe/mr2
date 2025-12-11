import flet as ft
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, List


try:
    from registro.nucleo.facade import FachadaRegistro
    from registro.importar.facade import FachadaImportacao
    from registro.nucleo.exceptions import ErroSessaoNaoAtiva
except ImportError as e:
    print("ERRO CRÍTICO: Não foi possível importar o backend.")
    print("Verifique se a pasta 'registro' existe e está estruturada corretamente.")
    raise e


def show_error(page: ft.Page, message: str):
    page.open(ft.SnackBar(
        content=ft.Text(message, color=ft.Colors.WHITE),
        bgcolor=ft.Colors.ERROR,
        show_close_icon=True
    ))


def show_success(page: ft.Page, message: str):
    page.open(ft.SnackBar(
        content=ft.Text(message, color=ft.Colors.WHITE),
        bgcolor=ft.Colors.GREEN,
        show_close_icon=True
    ))


class DashboardView(ft.Container):
    def __init__(self, fachada_nucleo: FachadaRegistro):
        super().__init__()
        self.fachada = fachada_nucleo
        self.expand = True
        self.padding = 20

        self.lbl_alunos = ft.Text("0", size=40, weight="bold", color="white")
        self.lbl_reservas = ft.Text("0", size=40, weight="bold", color="white")
        self.lbl_grupos = ft.Text("0", size=40, weight="bold", color="white")

        self.content = ft.Column([
            ft.Text("Dashboard", size=32, weight=ft.FontWeight.BOLD),
            ft.Text("Visão geral do sistema.",
                    color=ft.Colors.SURFACE_CONTAINER_HIGHEST),
            ft.Divider(height=30, color=ft.Colors.TRANSPARENT),
            ft.Row([
                self._create_card(
                    ft.Icons.PEOPLE, "Alunos Cadastrados", self.lbl_alunos, ft.Colors.BLUE_800),
                self._create_card(ft.Icons.RESTAURANT_MENU, "Reservas Hoje",
                                  self.lbl_reservas, ft.Colors.ORANGE_800),
                self._create_card(ft.Icons.GROUPS, "Turmas/Grupos",
                                  self.lbl_grupos, ft.Colors.GREEN_800),
            ], wrap=True, spacing=20)
        ], scroll=ft.ScrollMode.AUTO)

    def _create_card(self, icon, title, value_control, color):
        return ft.Container(
            content=ft.Column([
                ft.Row([ft.Icon(icon, color="white"), ft.Text(
                    title, color="white70", weight="bold")]),
                value_control,
            ]),
            width=260, height=140, bgcolor=color, border_radius=15, padding=20,
            shadow=ft.BoxShadow(
                blur_radius=10, color=ft.Colors.with_opacity(0.4, ft.Colors.BLACK))
        )

    def did_mount(self):
        self._carregar_estatisticas()

    def _carregar_estatisticas(self):
        try:

            alunos = self.fachada.listar_todos_os_estudantes()
            grupos = self.fachada.listar_todos_os_grupos()

            hoje_str = datetime.now().strftime("%d/%m/%Y")

            reservas = self.fachada.listar_reservas(filtros={"data": hoje_str})

            self.lbl_alunos.value = str(len(alunos))
            self.lbl_reservas.value = str(len(reservas))
            self.lbl_grupos.value = str(len(grupos))
            self.update()
        except Exception as e:
            traceback.print_exc()


class AlunosView(ft.Container):
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
        try:
            dados = self.fachada.listar_estudantes_fuzzy(
                termo_busca=termo, limite=70)

            for aluno in dados:
                ativo = aluno.get('ativo', True)
                status_bg = ft.Colors.GREEN_900 if ativo else ft.Colors.RED_900
                status_fg = ft.Colors.GREEN_100 if ativo else ft.Colors.RED_100
                grupos_str = ", ".join(aluno.get('grupos', []))

                self.tabela.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(aluno['id']))),
                        ft.DataCell(ft.Text(aluno['nome'], weight="bold")),
                        ft.DataCell(ft.Container(
                            content=ft.Text(
                                aluno['prontuario'], size=12, weight="bold", color=ft.Colors.ON_PRIMARY_CONTAINER),
                            bgcolor=ft.Colors.PRIMARY_CONTAINER,
                            padding=ft.padding.symmetric(
                                horizontal=8, vertical=4),
                            border_radius=6
                        )),
                        ft.DataCell(ft.Text(grupos_str)),
                        ft.DataCell(ft.Container(
                            content=ft.Text(
                                "Sim" if ativo else "Não", color=status_fg, size=11, weight="bold"),
                            bgcolor=status_bg,
                            padding=ft.padding.symmetric(
                                horizontal=10, vertical=4),
                            border_radius=12
                        )),
                        ft.DataCell(ft.IconButton(
                            icon=ft.Icons.EDIT,
                            icon_color=ft.Colors.PRIMARY,
                            data=aluno,
                            on_click=lambda e: self._abrir_modal(
                                e.control.data)
                        ))
                    ])
                )
            self.update()
        except Exception as e:
            traceback.print_exc()
            show_error(self.page, f"Erro ao carregar alunos: {e}")

    def _on_search(self, e):
        self._carregar_dados(e.control.value)

    def _abrir_modal(self, aluno=None):
        is_edit = aluno is not None

        nome_field = ft.TextField(
            label="Nome Completo", value=aluno['nome'] if is_edit else "", autofocus=True)
        pront_field = ft.TextField(
            label="Prontuário", value=aluno['prontuario'] if is_edit else "", read_only=is_edit)

        try:
            grupos_db = self.fachada.listar_todos_os_grupos()
            opcoes_grupos = [ft.dropdown.Option(g['nome']) for g in grupos_db]
        except:
            opcoes_grupos = []

        valor_grupo_inicial = None
        if is_edit and aluno.get('grupos'):
            # Pega o primeiro grupo por padrão
            valor_grupo_inicial = aluno['grupos'][0]
        elif opcoes_grupos:
            valor_grupo_inicial = opcoes_grupos[0].key

        dd_grupo = ft.Dropdown(
            label="Turma/Grupo Principal",
            options=opcoes_grupos,
            value=valor_grupo_inicial,
            expand=True
        )

        def salvar(e):
            if not nome_field.value or not pront_field.value:
                show_error(self.page, "Nome e Prontuário são obrigatórios.")
                return

            grupos_sel = [dd_grupo.value] if dd_grupo.value else []

            try:
                if is_edit:

                    self.fachada.atualizar_estudante(
                        aluno['id'], {"nome": nome_field.value})
                else:
                    self.fachada.criar_estudante(
                        pront_field.value, nome_field.value, grupos=grupos_sel)

                self.page.close(dlg)
                self._carregar_dados(self.txt_busca.value)
                show_success(self.page, "Dados salvos com sucesso!")
            except ValueError as ve:
                show_error(self.page, str(ve))
            except Exception as ex:
                traceback.print_exc()
                show_error(self.page, f"Erro interno: {ex}")

        dlg = ft.AlertDialog(
            title=ft.Text("Editar Aluno" if is_edit else "Adicionar Aluno"),
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
    def __init__(self, fachada_nucleo: FachadaRegistro):
        super().__init__()
        self.fachada = fachada_nucleo
        self.expand = True
        self.padding = 20

        self.date_picker = ft.DatePicker(on_change=self._on_date_change)
        self.btn_date = ft.ElevatedButton(
            "Todas as datas",
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=lambda _: self.page.open(self.date_picker)
        )

        self.dd_turma = ft.Dropdown(
            label="Filtrar por Turma",
            width=200,
            options=[ft.dropdown.Option("Todas")],
            value="Todas",
            content_padding=10,
            on_change=lambda e: self._carregar_dados()
        )

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
                self.dd_turma,
                self.btn_date,
                ft.FloatingActionButton(
                    icon=ft.Icons.ADD, text="Nova", on_click=lambda e: self._abrir_modal())
            ]),
            ft.Divider(),
            ft.Column([self.tabela], scroll=ft.ScrollMode.AUTO, expand=True)
        ], expand=True)

    def did_mount(self):

        try:
            grupos = self.fachada.listar_todos_os_grupos()
            self.dd_turma.options = [ft.dropdown.Option(
                "Todas")] + [ft.dropdown.Option(g['nome']) for g in grupos]
        except:
            pass

        self._carregar_dados()

    def _on_date_change(self, e):
        if e.control.value:

            data_str = e.control.value.strftime('%d/%m/%Y')
            self.btn_date.text = f"Data: {data_str}"
            self.btn_date.data = data_str
        else:
            self.btn_date.text = "Todas as datas"
            self.btn_date.data = None

        self.btn_date.update()
        self._carregar_dados()

    def _carregar_dados(self):
        self.tabela.rows.clear()

        filtros = {}

        if hasattr(self.btn_date, 'data') and self.btn_date.data:
            filtros["data"] = self.btn_date.data

        if self.dd_turma.value and self.dd_turma.value != "Todas":
            filtros["grupos"] = [self.dd_turma.value]

        try:
            reservas = self.fachada.listar_reservas(filtros)

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
                        ft.DataCell(ft.Row([
                            ft.IconButton(icon=ft.Icons.EDIT, icon_color=ft.Colors.PRIMARY,
                                          data=r, on_click=lambda e: self._abrir_modal(e.control.data)),
                            ft.IconButton(icon=ft.Icons.DELETE, icon_color=ft.Colors.ERROR,
                                          data=r['id'], on_click=lambda e: self._deletar_reserva(e.control.data))
                        ]))
                    ])
                )
            self.update()
        except Exception as e:
            traceback.print_exc()
            show_error(self.page, "Erro ao carregar reservas.")

    def _deletar_reserva(self, id_reserva):
        def confirmar(e):
            self.page.close(dlg)
            try:
                self.fachada.deletar_reserva(id_reserva)
                show_success(self.page, "Reserva excluída.")
                self._carregar_dados()
            except Exception as ex:
                show_error(self.page, f"Erro ao excluir: {ex}")

        dlg = ft.AlertDialog(
            title=ft.Text("Confirmar Exclusão"),
            content=ft.Text("Tem certeza que deseja apagar esta reserva?"),
            actions=[
                ft.TextButton("Não", on_click=lambda e: self.page.close(dlg)),
                ft.FilledButton("Sim", on_click=confirmar,
                                style=ft.ButtonStyle(bgcolor=ft.Colors.ERROR))
            ]
        )
        self.page.open(dlg)

    def _abrir_modal(self, reserva=None):
        is_edit = reserva is not None

        if not is_edit:
            try:
                todos_alunos = self.fachada.listar_todos_os_estudantes()
                opcoes_alunos = [
                    ft.dropdown.Option(
                        key=a['prontuario'],
                        text=f"{a['prontuario']} - {a['nome']}"
                    ) for a in todos_alunos
                ]
            except:
                opcoes_alunos = []

        dd_aluno = ft.Dropdown(
            label="Selecione o Aluno",
            options=opcoes_alunos if not is_edit else [],
            visible=not is_edit,
            enable_filter=True
        )
        lbl_aluno_edit = ft.TextField(
            label="Aluno",
            value=f"{reserva['prontuario_estudante']} - {reserva['nome_estudante']}" if is_edit else "",
            read_only=True,
            visible=is_edit
        )

        txt_data = ft.TextField(
            label="Data (YYYY-MM-DD)",
            value=reserva['data'] if is_edit else datetime.now().strftime(
                "%Y-%m-%d"),
            helper_text="Formato ISO YYYY-MM-DD"
        )

        dd_prato = ft.Dropdown(
            label="Prato",
            options=[
                ft.dropdown.Option("Tradicional"),
                ft.dropdown.Option("Vegetariano"),
                ft.dropdown.Option("Vegano"),
            ],
            value=reserva['prato'] if is_edit else "Tradicional"
        )

        sw_cancelada = ft.Switch(
            label="Reserva Cancelada", value=reserva['cancelada'] if is_edit else False)

        def salvar(e):
            if not is_edit and not dd_aluno.value:
                show_error(self.page, "Selecione um aluno.")
                return
            if not txt_data.value:
                show_error(self.page, "Informe a data.")
                return

            payload = {
                "data": txt_data.value,
                "prato": dd_prato.value,
                "cancelada": sw_cancelada.value
            }

            try:
                if is_edit:
                    self.fachada.atualizar_reserva(reserva['id'], payload)
                else:
                    prontuario = dd_aluno.value
                    self.fachada.criar_reserva(prontuario, payload)

                self.page.close(dlg)
                self._carregar_dados()
                show_success(self.page, "Reserva salva!")
            except Exception as ex:
                traceback.print_exc()
                show_error(self.page, f"Erro: {ex}")

        dlg = ft.AlertDialog(
            title=ft.Text("Editar Reserva" if is_edit else "Nova Reserva"),
            content=ft.Column(
                [dd_aluno, lbl_aluno_edit, txt_data, dd_prato, sw_cancelada],
                tight=True, width=400
            ),
            actions=[
                ft.TextButton(
                    "Cancelar", on_click=lambda e: self.page.close(dlg)),
                ft.FilledButton("Salvar", on_click=salvar)
            ]
        )
        self.page.open(dlg)


class ImportacaoWizard(ft.Container):
    def __init__(self, fachada_nucleo: FachadaRegistro, fachada_importacao: FachadaImportacao):
        super().__init__()
        self.fachada_nucleo = fachada_nucleo
        self.fachada_imp = fachada_importacao
        self.expand = True
        self.padding = 20

        self.file_picker = ft.FilePicker(on_result=self._on_file_pick)

        self.current_path: Optional[str] = None
        self.itens_revisao: List[Dict] = []
        self.resumo_analise: Optional[Dict] = None

        self.step_content = ft.Container(expand=True)
        self.progress = ft.ProgressBar(value=0.0, height=5)
        self.lbl_titulo = ft.Text(
            "Assistente de Importação", size=20, weight="bold")

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

        self._go_step_1()

    def will_unmount(self):
        if self.file_picker in self.page.overlay:
            self.page.overlay.remove(self.file_picker)

    def _go_step_1(self):
        self.progress.value = 0.25
        self.lbl_titulo.value = "Passo 1: Selecionar Arquivo"

        self.txt_file = ft.TextField(
            read_only=True, label="Caminho do Arquivo", expand=True, value=self.current_path or "")
        self.rg_tipo = ft.RadioGroup(content=ft.Column([
            ft.Radio(value="auto", label="Automático (Detectar colunas)"),
            ft.Radio(value="simples", label="Lista Simples (.txt)"),
            ft.Radio(value="header", label="CSV com Cabeçalho"),
            ft.Radio(value="sheets", label="Google Spreadsheets (ID)"),
        ]), value="auto")

        self.step_content.content = ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Text("Configuração da Fonte", weight="bold"),
                    self.rg_tipo,
                ]),
                padding=10, border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT), border_radius=10
            ),
            ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
            ft.Row([
                self.txt_file,
                ft.ElevatedButton("Buscar...", icon=ft.Icons.FOLDER_OPEN,
                                  on_click=lambda _: self.file_picker.pick_files(allowed_extensions=["csv", "txt"]))
            ]),
            ft.Container(expand=True),
            ft.Row([
                ft.FilledButton("Analisar Dados >",
                                on_click=self._iniciar_analise)
            ], alignment=ft.MainAxisAlignment.END)
        ])
        self.update()

    def _on_file_pick(self, e: ft.FilePickerResultEvent):
        if e.files:
            self.current_path = e.files[0].path
            self.txt_file.value = self.current_path
            self.txt_file.update()

    def _iniciar_analise(self, e):
        path = self.txt_file.value
        tipo = self.rg_tipo.value

        if not path:
            show_error(self.page, "Selecione um arquivo primeiro.")
            return

        try:
            resultado = self.fachada_imp.analisar_arquivo(path, tipo)
            self.resumo_analise = resultado["resumo"]
            self.itens_revisao = resultado["itens_revisao"]

            show_success(self.page, "Análise concluída!")
            self._go_step_2()
        except Exception as ex:
            traceback.print_exc()
            show_error(self.page, f"Erro na análise: {ex}")

    def _go_step_2(self):
        self.progress.value = 0.50
        self.lbl_titulo.value = "Passo 2: Revisão de Conflitos"

        res = self.resumo_analise
        txt_resumo = f"✅ {res['automaticos']} Automáticos | ⚠️ {res['para_revisao']} Para Revisão | ❌ {res['invalidos']} Inválidos"

        self.date_default = ft.DatePicker()
        self.txt_data_def = ft.TextField(
            label="Data Padrão", width=150, value=datetime.now().strftime("%d/%m/%Y"))
        self.dd_prato_def = ft.Dropdown(
            label="Refeição Padrão", width=150,
            options=[ft.dropdown.Option("Almoço"), ft.dropdown.Option(
                "Jantar"), ft.dropdown.Option("Lanche")],
            value="Almoço"
        )

        lv_itens = ft.ListView(expand=True, spacing=10)

        if not self.itens_revisao:
            lv_itens.controls.append(
                ft.Container(content=ft.Text(
                    "Nenhum conflito encontrado. Tudo pronto!", size=16), padding=20)
            )
        else:
            for item in self.itens_revisao:
                lv_itens.controls.append(self._criar_linha_revisao(item))

        self.step_content.content = ft.Column([
            ft.Container(
                content=ft.Text(txt_resumo, weight="bold",
                                color=ft.Colors.ON_SECONDARY_CONTAINER),
                bgcolor=ft.Colors.SECONDARY_CONTAINER,
                padding=10,
                border_radius=5
            ),
            ft.Row([self.txt_data_def, self.dd_prato_def]),
            ft.Divider(),
            ft.Text("Itens que precisam da sua atenção:", size=14),
            lv_itens,
            ft.Row([
                ft.OutlinedButton(
                    "Voltar", on_click=lambda _: self._go_step_1()),
                ft.FilledButton("Verificar e Simular >",
                                on_click=self._ir_para_preview)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        ])
        self.update()

    def _criar_linha_revisao(self, item: Dict):

        dados = item["dados_csv"]
        texto_principal = f"{dados.get('nome', 'Sem Nome')} ({dados.get('prontuario', '')})"

        dd_acao = ft.Dropdown(
            width=140,
            options=[
                ft.dropdown.Option("CRIAR_NOVO"),
                ft.dropdown.Option("VINCULAR"),
                ft.dropdown.Option("IGNORAR")
            ],
            value=item["resolucao_escolhida"],
            dense=True,
            text_size=12
        )

        candidatos = item.get("candidatos", [])
        opts_cand = []
        mapa_ids = {}

        for cand in candidatos:
            lbl = f"{cand['nome']} ({cand['score']}%)"
            opts_cand.append(ft.dropdown.Option(key=str(cand['id']), text=lbl))
            mapa_ids[str(cand['id'])] = cand['id']

        dd_cand = ft.Dropdown(
            width=200,
            options=opts_cand,
            dense=True,
            text_size=12,
            disabled=(len(opts_cand) == 0),
            value=str(candidatos[0]['id']) if candidatos else None
        )

        def on_change_acao(e):
            item["resolucao_escolhida"] = dd_acao.value
            dd_cand.disabled = (dd_acao.value != "VINCULAR")
            dd_cand.update()

        def on_change_cand(e):
            if dd_cand.value:
                item["id_estudante_vinculo"] = int(dd_cand.value)

        dd_acao.on_change = on_change_acao
        dd_cand.on_change = on_change_cand

        if candidatos and item["resolucao_escolhida"] == "VINCULAR":
            item["id_estudante_vinculo"] = candidatos[0]['id']

        return ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text(texto_principal, weight="bold"),
                    ft.Text(
                        f"Problema: {item['tipo_conflito']}", size=11, color="red")
                ], expand=True),
                dd_cand,
                dd_acao
            ]),
            padding=10,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=8
        )

    def _ir_para_preview(self, e):
        defaults = {}
        if self.txt_data_def.value:
            defaults["data"] = self.txt_data_def.value
        if self.dd_prato_def.value:
            defaults["prato"] = self.dd_prato_def.value

        try:
            self.preview_dados = self.fachada_imp.simular_importacao(
                self.itens_revisao, defaults)
            self._go_step_3()
        except Exception as ex:
            traceback.print_exc()
            show_error(self.page, f"Erro na simulação: {ex}")

    def _go_step_3(self):
        self.progress.value = 0.75
        self.lbl_titulo.value = "Passo 3: Confirmação Final"

        novos = self.preview_dados.get("novos_estudantes", [])
        reservas = self.preview_dados.get("reservas", [])

        col_novos = ft.DataTable(
            columns=[ft.DataColumn(ft.Text("Prontuário")),
                     ft.DataColumn(ft.Text("Nome"))],
            rows=[ft.DataRow(cells=[ft.DataCell(ft.Text(n['prontuario'])), ft.DataCell(
                ft.Text(n['nome']))]) for n in novos[:50]]
        )

        col_res = ft.DataTable(
            columns=[ft.DataColumn(ft.Text("Data")), ft.DataColumn(
                ft.Text("Nome")), ft.DataColumn(ft.Text("Prato"))],
            rows=[ft.DataRow(cells=[
                ft.DataCell(ft.Text(r['data'])),
                ft.DataCell(ft.Text(r['aluno'])),
                ft.DataCell(ft.Text(r['prato']))
            ]) for r in reservas[:50]]
        )

        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(text=f"Novos Alunos ({len(novos)})", content=ft.Column(
                    [col_novos], scroll=ft.ScrollMode.AUTO)),
                ft.Tab(text=f"Reservas ({len(reservas)})", content=ft.Column(
                    [col_res], scroll=ft.ScrollMode.AUTO)),
            ],
            expand=True
        )

        self.step_content.content = ft.Column([
            ft.Text(
                "Verifique os dados abaixo antes de salvar (Mostrando os primeiros 50 registros).", color="grey"),
            tabs,
            ft.Row([
                ft.OutlinedButton("Voltar e Editar",
                                  on_click=lambda _: self._go_step_2()),
                ft.FilledButton("CONFIRMAR E SALVAR", on_click=self._executar_salvamento,
                                style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN))
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        ])
        self.update()

    def _executar_salvamento(self, e):

        def confirmar_final(ev):
            self.page.close(dlg)
            self._processar_salvamento_real()

        dlg = ft.AlertDialog(
            title=ft.Text("Tem certeza?"),
            content=ft.Text(
                "Isso irá alterar o banco de dados permanentemente."),
            actions=[
                ft.TextButton(
                    "Cancelar", on_click=lambda ev: self.page.close(dlg)),
                ft.FilledButton("Sim, Salvar", on_click=confirmar_final)
            ]
        )
        self.page.open(dlg)

    def _processar_salvamento_real(self):
        defaults = {}
        if self.txt_data_def.value:
            defaults["data"] = self.txt_data_def.value
        if self.dd_prato_def.value:
            defaults["prato"] = self.dd_prato_def.value

        try:
            res = self.fachada_imp.confirmar_importacao(
                self.itens_revisao, defaults)
            self.resultado_final = res
            self._go_step_4()
        except Exception as e:
            traceback.print_exc()
            show_error(self.page, f"Erro fatal ao salvar: {e}")

    def _go_step_4(self):
        self.progress.value = 1.0
        self.lbl_titulo.value = "Sucesso!"

        res = self.resultado_final
        txt = (
            f"Estudantes Cadastrados: {res.get('estudantes_criados', 0)}\n"
            f"Reservas Geradas: {res.get('reservas_criadas', 0)}"
        )

        self.step_content.content = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.CHECK_CIRCLE, size=100,
                        color=ft.Colors.GREEN),
                ft.Text("Importação realizada com sucesso!",
                        size=24, weight="bold"),
                ft.Text(txt, size=16, text_align=ft.TextAlign.CENTER),
                ft.SizedBox(height=20),
                ft.ElevatedButton("Nova Importação",
                                  on_click=lambda _: self._go_step_1())
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.alignment.center,
            expand=True
        )
        self.update()


def main(page: ft.Page):

    page.title = "Sistema de Gestão de Refeitório"
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(color_scheme_seed="blue")

    try:
        fachada_nucleo = FachadaRegistro()
        fachada_imp = FachadaImportacao(fachada_nucleo)
    except Exception as e:
        page.add(ft.Text(f"Erro fatal ao iniciar backend: {e}", color="red"))
        return

    views = {
        0: DashboardView(fachada_nucleo),
        1: AlunosView(fachada_nucleo),
        2: ReservasView(fachada_nucleo),
        3: ImportacaoWizard(fachada_nucleo, fachada_imp)
    }

    body_container = ft.Container(content=views[0], expand=True)

    def change_nav(e):
        idx = e.control.selected_index

        if idx == 0:
            views[0]._carregar_estatisticas()

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

    def on_close(e):
        print("Fechando conexão com banco de dados...")
        try:
            fachada_nucleo.fechar_conexao()
        except:
            pass


if __name__ == "__main__":
    ft.app(target=main)
