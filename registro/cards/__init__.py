# ----------------------------------------------------------------------------
# Arquivo: registro/cards/__init__.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""Módulo de geração de cartões e crachás de identificação com QR Code."""

from registro.cards.generator import (
    CardOptions,
    generate_cards_html,
    generate_cards_pdf,
    load_students_from_file,
)

__all__ = [
    "CardOptions",
    "generate_cards_pdf",
    "generate_cards_html",
    "load_students_from_file",
]
