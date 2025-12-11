import traceback
from datetime import datetime
import flet as ft
from registro.nucleo.facade import FachadaRegistro
from registro.interface.utils import show_error, show_success

class ReservasView(ft.Container):
    """Tela de gerenciamento de reservas."""

    def __init__(self, fachada_nucleo: FachadaRegistro):
        super().__init__()
        self.fachada = fachada_nucleo
        self.expand = True
        self.padding = 20

        
        self.date_picker = ft.DatePicker(on_change=self._on_date_change)
        self.btn_date = ft.ElevatedButton("Todas as datas", icon=ft.Icons.CALENDAR_MONTH, on_click=lambda _: self.page.open(self.date_picker))
        self.dd_turma = ft.Dropdown(
            label="Filtrar por Turma", width=200, value="Todas", content_padding=10,
            options=[ft.dropdown.Option("Todas")], on_change=lambda e: self._carregar_dados()
        )

        self.tabela = ft.DataTable(
            width=float("inf"), heading_row_color=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            columns=[
                ft.DataColumn(ft.Text("Data")),
                ft.DataColumn(ft.Text("Aluno")),
                ft.DataColumn(ft.Text("Prato")),
                ft.DataColumn(ft.Text("Status")),
                ft.DataColumn(ft.Text("Ações")),
            ], expand=True
        )

        self.content = ft.Column([
            ft.Row([
                ft.Text("Reservas", size=28, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                self.dd_turma, self.btn_date,
                ft.FloatingActionButton(icon=ft.Icons.ADD, text="Nova", on_click=lambda e: self._abrir_modal())
            ]),
            ft.Divider(),
            ft.Column([self.tabela], scroll=ft.ScrollMode.AUTO, expand=True)
        ], expand=True)

    def did_mount(self):
        try:
            grupos = self.fachada.listar_todos_os_grupos()
            self.dd_turma.options = [ft.dropdown.Option("Todas")] + [ft.dropdown.Option(g['nome']) for g in grupos]
        except: pass
        self._carregar_dados()

    def _on_date_change(self, e):
        if e.control.value:
            txt_data = e.control.value.strftime('%d/%m/%Y')
            self.btn_date.text, self.btn_date.data = f"Data: {txt_data}", txt_data
        else:
            self.btn_date.text, self.btn_date.data = "Todas as datas", None
        self.btn_date.update()
        self._carregar_dados()

    def _carregar_dados(self):
        self.tabela.rows.clear()
        filtros = {}
        if hasattr(self.btn_date, 'data') and self.btn_date.data: filtros["data"] = self.btn_date.data
        if self.dd_turma.value and self.dd_turma.value != "Todas": filtros["grupos"] = [self.dd_turma.value]

        try:
            reservas = self.fachada.listar_reservas(filtros)
            for r in reservas:
                cancelada = r.get('cancelada', False)
                cor_txt = ft.Colors.ON_ERROR_CONTAINER if cancelada else ft.Colors.ON_TERTIARY_CONTAINER
                cor_bg = ft.Colors.ERROR_CONTAINER if cancelada else ft.Colors.TERTIARY_CONTAINER
                
                self.tabela.rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(r['data'])),
                    ft.DataCell(ft.Column([ft.Text(r['nome_estudante'], weight="bold"), ft.Text(r['prontuario_estudante'], size=10)])),
                    ft.DataCell(ft.Text(r['prato'])),
                    ft.DataCell(ft.Container(content=ft.Text("Cancelada" if cancelada else "Ativa", color=cor_txt, weight="bold"), bgcolor=cor_bg, padding=5, border_radius=5)),
                    ft.DataCell(ft.Row([
                        ft.IconButton(icon=ft.Icons.EDIT, icon_color=ft.Colors.PRIMARY, data=r, on_click=lambda e: self._abrir_modal(e.control.data)),
                        ft.IconButton(icon=ft.Icons.DELETE, icon_color=ft.Colors.ERROR, data=r['id'], on_click=lambda e: self._deletar_reserva(e.control.data))
                    ]))
                ]))
            self.update()
        except Exception:
            traceback.print_exc()
            show_error(self.page, "Erro ao carregar reservas.")

    def _deletar_reserva(self, id_reserva):
        def confirmar(e):
            self.page.close(dlg)
            try:
                self.fachada.deletar_reserva(id_reserva)
                show_success(self.page, "Reserva excluída.")
                self._carregar_dados()
            except Exception as ex: show_error(self.page, str(ex))

        dlg = ft.AlertDialog(title=ft.Text("Confirmar Exclusão"), content=ft.Text("Deseja apagar esta reserva?"),
                             actions=[ft.TextButton("Não", on_click=lambda e: self.page.close(dlg)), ft.FilledButton("Sim", on_click=confirmar, style=ft.ButtonStyle(bgcolor=ft.Colors.ERROR))])
        self.page.open(dlg)

    def _abrir_modal(self, reserva=None):
        is_edit = reserva is not None
        
        
        opcoes_alunos = []
        if not is_edit:
            try:
                todos = self.fachada.listar_todos_os_estudantes()
                opcoes_alunos = [ft.dropdown.Option(key=a['prontuario'], text=f"{a['prontuario']} - {a['nome']}") for a in todos]
            except: pass

        dd_aluno = ft.Dropdown(label="Aluno", options=opcoes_alunos, visible=not is_edit, enable_filter=True)
        lbl_aluno = ft.TextField(label="Aluno", value=f"{reserva['nome_estudante']}" if is_edit else "", read_only=True, visible=is_edit)
        txt_data = ft.TextField(label="Data (YYYY-MM-DD)", value=reserva['data'] if is_edit else datetime.now().strftime("%Y-%m-%d"))
        dd_prato = ft.Dropdown(label="Prato", options=[ft.dropdown.Option("Tradicional"), ft.dropdown.Option("Vegetariano"), ft.dropdown.Option("Vegano")], value=reserva['prato'] if is_edit else "Tradicional")
        sw_canc = ft.Switch(label="Cancelada", value=reserva['cancelada'] if is_edit else False)

        def salvar(e):
            if not txt_data.value or (not is_edit and not dd_aluno.value):
                show_error(self.page, "Dados incompletos.")
                return
            payload = {"data": txt_data.value, "prato": dd_prato.value, "cancelada": sw_canc.value}
            try:
                if is_edit: self.fachada.atualizar_reserva(reserva['id'], payload)
                else: self.fachada.criar_reserva(dd_aluno.value, payload)
                self.page.close(dlg)
                self._carregar_dados()
                show_success(self.page, "Reserva salva!")
            except Exception as ex: show_error(self.page, f"Erro: {ex}")

        dlg = ft.AlertDialog(title=ft.Text("Editar Reserva" if is_edit else "Nova Reserva"),
                             content=ft.Column([dd_aluno, lbl_aluno, txt_data, dd_prato, sw_canc], tight=True, width=400),
                             actions=[ft.TextButton("Cancelar", on_click=lambda e: self.page.close(dlg)), ft.FilledButton("Salvar", on_click=salvar)])
        self.page.open(dlg)