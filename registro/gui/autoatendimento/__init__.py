# ----------------------------------------------------------------------------
# Arquivo: registro/gui/autoatendimento/__init__.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""Interface de autoatendimento autônomo com webcam e leitor de QR Code."""

from registro.gui.autoatendimento.app import AppSelfService, main
from registro.gui.autoatendimento.consumos import AbaConsumos
from registro.gui.autoatendimento.dashboard import AbaDashboard
from registro.gui.autoatendimento.totem import FrameSelfService

__all__ = [
    "AbaConsumos",
    "AbaDashboard",
    "AppSelfService",
    "FrameSelfService",
    "main",
]
