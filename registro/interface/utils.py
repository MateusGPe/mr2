import flet as ft

def show_error(page: ft.Page, message: str):
    """Exibe snackbar de erro (vermelho)."""
    page.open(ft.SnackBar(
        content=ft.Text(message, color=ft.Colors.WHITE),
        bgcolor=ft.Colors.ERROR,
        show_close_icon=True
    ))

def show_success(page: ft.Page, message: str):
    """Exibe snackbar de sucesso (verde)."""
    page.open(ft.SnackBar(
        content=ft.Text(message, color=ft.Colors.WHITE),
        bgcolor=ft.Colors.GREEN,
        show_close_icon=True
    ))