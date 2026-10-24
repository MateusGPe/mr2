import tkinter as tk
import pytest


@pytest.fixture(scope="session")
def app_root():
    """Raiz Tk única compartilhada para todos os testes de GUI da sessão."""
    try:
        root = tk.Tk()
        root.withdraw()
        yield root
        try:
            root.destroy()
        except Exception:
            pass
    except tk.TclError:
        pytest.skip("Ambiente sem display Tkinter disponível")
