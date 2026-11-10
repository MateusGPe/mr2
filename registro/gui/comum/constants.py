# ----------------------------------------------------------------------------
# Arquivo: registro/gui/comum/constants.py (Constantes Comuns de GUI)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>
"""
Constantes compartilhadas entre as diferentes interfaces gráficas do sistema.
"""

import re
import sys
from typing import Dict, Set

from registro.nucleo.config_service import obter_mapeamento_colunas

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

TRADUCAO_CHAVE_EXTERNA: Dict[str, str] = obter_mapeamento_colunas()

FONTE_UI_PADRAO: str = "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"

MAPA_OFUSCAMENTO_PRONTUARIO: Dict[int, int] = str.maketrans(
    "0123456789Xx", "abcdefghijkk"
)

REGEX_LIMPEZA_PRONTUARIO: re.Pattern[str] = re.compile(r"^[Ii][Qq]30+")

CSIDL_PERSONAL: int = 5
SHGFP_TYPE_CURRENT: int = 0
