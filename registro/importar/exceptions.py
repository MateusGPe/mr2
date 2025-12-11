# ----------------------------------------------------------------------------
# Arquivo: registro/importar/exceptions.py (Módulo de Exceções)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""Exceções customizadas para o módulo de importação."""


class ErroImportacao(Exception):
    """Classe base para exceções neste módulo."""


class ErroSessaoImportacao(ErroImportacao):
    """Erro operado quando o fluxo da sessão de importação é violado."""