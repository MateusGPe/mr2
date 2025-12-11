# ----------------------------------------------------------------------------
# Arquivo: registro/importar/__init__.py (Pacote de Importação)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Pacote responsável pela importação assistida de dados.

Expõe a fachada principal e os tipos de dados necessários para a
construção da Interface de Usuário (GUI).
"""

from .definitions import (
    CandidatoMatch,
    ItemRevisao,
    ResolucaoUsuario,
    ResumoImportacao,
    TipoConflito,
)
from .exceptions import ErroImportacao, ErroSessaoImportacao
from .facade import FachadaImportacao

__all__ = [
    "FachadaImportacao",
    "ItemRevisao",
    "CandidatoMatch",
    "ResolucaoUsuario",
    "ResumoImportacao",
    "TipoConflito",
    "ErroImportacao",
    "ErroSessaoImportacao",
]