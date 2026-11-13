import tkinter as tk
from dataclasses import dataclass, field
from typing import Any, Dict, List
from unittest.mock import patch

import pytest
from ttkbootstrap.localization.msgcat import MessageCatalog
from ttkbootstrap.style.engine import Style, StyleBuilderTTK


@dataclass
class MessageboxSpy:
    """Espião para capturar e controlar chamadas a diálogos do ttkbootstrap."""

    info_calls: List[Dict[str, Any]] = field(default_factory=list)
    warning_calls: List[Dict[str, Any]] = field(default_factory=list)
    error_calls: List[Dict[str, Any]] = field(default_factory=list)
    yesno_calls: List[Dict[str, Any]] = field(default_factory=list)
    question_calls: List[Dict[str, Any]] = field(default_factory=list)
    yesno_response: Any = None
    question_response: Any = None

    def __post_init__(self):
        if self.yesno_response is None:
            self.yesno_response = MessageCatalog.translate("Yes")
        if self.question_response is None:
            self.question_response = MessageCatalog.translate("Yes")


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


@pytest.fixture(autouse=True)
def ensure_ttkbootstrap_theme_builder():
    """Garante que Style._get_builder() resolva com segurança o theme builder no ciclo de testes."""
    original_get_builder = Style._get_builder

    def safe_get_builder():
        style = Style.get_instance()
        if style is not None:
            theme_name = getattr(style.theme, "name", "sandstone")
            if theme_name not in style._theme_objects:
                base_name = theme_name.split("-")[0]
                if base_name in style._theme_objects:
                    return style._theme_objects[base_name]
                try:
                    style._theme_objects[theme_name] = StyleBuilderTTK()
                except Exception:
                    style._theme_objects[theme_name] = StyleBuilderTTK(build=False)
        return original_get_builder()

    with patch.object(Style, "_get_builder", side_effect=safe_get_builder):
        yield


@pytest.fixture
def mock_messagebox():
    """Intercepta e espiona diálogos modais para testes sem bloquear a interface."""
    spy = MessageboxSpy()

    def fake_info(message="", title="", **kwargs):
        spy.info_calls.append({"message": message, "title": title, "kwargs": kwargs})
        return "OK"

    def fake_warning(message="", title="", **kwargs):
        spy.warning_calls.append({"message": message, "title": title, "kwargs": kwargs})
        return "OK"

    def fake_error(message="", title="", **kwargs):
        spy.error_calls.append({"message": message, "title": title, "kwargs": kwargs})
        return "OK"

    def fake_yesno(message="", title="", **kwargs):
        spy.yesno_calls.append({"message": message, "title": title, "kwargs": kwargs})
        return spy.yesno_response

    def fake_question(message="", title="", **kwargs):
        spy.question_calls.append({"message": message, "title": title, "kwargs": kwargs})
        return spy.question_response

    with patch("ttkbootstrap.dialogs.Messagebox.show_info", side_effect=fake_info), \
         patch("ttkbootstrap.dialogs.Messagebox.show_warning", side_effect=fake_warning), \
         patch("ttkbootstrap.dialogs.Messagebox.show_error", side_effect=fake_error), \
         patch("ttkbootstrap.dialogs.Messagebox.yesno", side_effect=fake_yesno), \
         patch("ttkbootstrap.dialogs.Messagebox.show_question", side_effect=fake_question):
        yield spy
