# ----------------------------------------------------------------------------
# Arquivo: registro/gui/comum/constants.py (Constantes Comuns de GUI)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>
"""
Constantes compartilhadas entre as diferentes interfaces gráficas do sistema.
"""

import re
from typing import Dict, Set

EXCECOES_CAPITALIZACAO: Set[str] = {
    "a",
    "o",
    "as",
    "os",
    "de",
    "do",
    "da",
    "dos",
    "das",
    "e",
    "é",
    "em",
    "com",
    "sem",
    "ou",
    "para",
    "por",
    "pelo",
    "pela",
    "no",
    "na",
    "nos",
    "nas",
}

TRADUCAO_CHAVE_EXTERNA: Dict[str, str] = {
    "matrícula iq": "pront",
    "matrícula": "pront",
    "prontuário": "pront",
    "refeição": "dish",
    "curso": "turma",
    "situação": "status",
    "nome completo": "nome",
}

MAPA_OFUSCAMENTO_PRONTUARIO: Dict[int, int] = str.maketrans(
    "0123456789Xx", "abcdefghijkk"
)

REGEX_LIMPEZA_PRONTUARIO: re.Pattern[str] = re.compile(r"^[Ii][Qq]30+")

CSIDL_PERSONAL: int = 5
SHGFP_TYPE_CURRENT: int = 0
