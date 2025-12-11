import flet as ft
from registro.interface.views.dashboard import DashboardView
from registro.interface.views.alunos import AlunosView
from registro.interface.views.reservas import ReservasView
from registro.interface.views.importacao import ImportacaoWizard


try:
    from registro.nucleo.facade import FachadaRegistro
    from registro.importar.facade import FachadaImportacao
except ImportError as e:
    print("ERRO: Backend 'registro' não encontrado.")
    raise e

def main(page: ft.Page):
    
    page.title = "Sistema de Gestão de Refeitório"
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(color_scheme_seed="blue")

    
    try:
        fachada_nucleo = FachadaRegistro()
        fachada_imp = FachadaImportacao(fachada_nucleo)
    except Exception as e:
        page.add(ft.Text(f"Erro fatal ao conectar ao banco de dados: {e}", color="red", size=20))
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
            views[0].carregar_estatisticas()
        
        body_container.content = views[idx]
        body_container.update()

    def toggle_theme(e):
        page.theme_mode = ft.ThemeMode.LIGHT if page.theme_mode == ft.ThemeMode.DARK else ft.ThemeMode.DARK
        e.control.icon = ft.Icons.DARK_MODE if page.theme_mode == ft.ThemeMode.LIGHT else ft.Icons.LIGHT_MODE
        page.update()

    
    rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100, min_extended_width=200, group_alignment=-0.9,
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.DASHBOARD, label="Dashboard"),
            ft.NavigationRailDestination(icon=ft.Icons.PEOPLE, label="Alunos"),
            ft.NavigationRailDestination(icon=ft.Icons.CALENDAR_MONTH, label="Reservas"),
            ft.NavigationRailDestination(icon=ft.Icons.UPLOAD, label="Importar"),
        ],
        on_change=change_nav,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
    )

    btn_theme = ft.IconButton(
        icon=ft.Icons.LIGHT_MODE, 
        tooltip="Alternar Tema", 
        on_click=toggle_theme
    )

    
    page.add(
        ft.Row([
            ft.Container(
                content=ft.Column([
                    ft.Container(content=ft.Icon(ft.Icons.RESTAURANT_MENU, size=30, color=ft.Colors.PRIMARY), padding=20),
                    ft.Container(content=rail, expand=True),
                    ft.Container(content=btn_theme, padding=10)
                ], expand=True),
                width=100,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST
            ),
            ft.VerticalDivider(width=1, thickness=1, color=ft.Colors.OUTLINE_VARIANT),
            body_container
        ], expand=True, spacing=0)
    )

    
    def on_disconnect(e):
        print("Encerrando conexão...")
        try: fachada_nucleo.fechar_conexao()
        except: pass
    
    
    

if __name__ == "__main__":
    ft.app(target=main)