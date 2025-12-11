import traceback
from datetime import datetime
import flet as ft
from registro.nucleo.facade import FachadaRegistro

class DashboardView(ft.Container):
    """Tela principal com estatísticas gerais do sistema."""

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
            ft.Text("Visão geral do sistema.", color=ft.Colors.SURFACE_CONTAINER_HIGHEST),
            ft.Divider(height=30, color=ft.Colors.TRANSPARENT),
            ft.Row([
                self._create_card(ft.Icons.PEOPLE, "Alunos Cadastrados", self.lbl_alunos, ft.Colors.BLUE_800),
                self._create_card(ft.Icons.RESTAURANT_MENU, "Reservas Hoje", self.lbl_reservas, ft.Colors.ORANGE_800),
                self._create_card(ft.Icons.GROUPS, "Turmas/Grupos", self.lbl_grupos, ft.Colors.GREEN_800),
            ], wrap=True, spacing=20)
        ], scroll=ft.ScrollMode.AUTO)

    def _create_card(self, icon, title, value_control, color):
        """Cria um card visual padronizado."""
        return ft.Container(
            content=ft.Column([
                ft.Row([ft.Icon(icon, color="white"), ft.Text(title, color="white70", weight="bold")]),
                value_control,
            ]),
            width=260, height=140, bgcolor=color, border_radius=15, padding=20,
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.4, ft.Colors.BLACK))
        )

    def did_mount(self):
        self.carregar_estatisticas()

    def carregar_estatisticas(self):
        """Busca dados atualizados do banco."""
        try:
            alunos = self.fachada.listar_todos_os_estudantes()
            grupos = self.fachada.listar_todos_os_grupos()
            
            
            hoje_str = datetime.now().strftime("%d/%m/%Y")
            reservas = self.fachada.listar_reservas(filtros={"data": hoje_str})

            self.lbl_alunos.value = str(len(alunos))
            self.lbl_reservas.value = str(len(reservas))
            self.lbl_grupos.value = str(len(grupos))
            self.update()
        except Exception:
            traceback.print_exc()