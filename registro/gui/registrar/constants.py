# ----------------------------------------------------------------------------
# Arquivo: registro/gui/registrar/constants.py (Constantes do Registro)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>
"""
Módulo central para a definição de constantes utilizadas em toda a aplicação.

Isso inclui caminhos de diretórios, URLs, configurações de API, mapeamentos
de dados e listas de valores predefinidos.
"""

import re
from pathlib import Path
from typing import Dict, List, Literal, Optional, Set, TypedDict

from registro.nucleo.constants import (
    CABECALHO_EXPORTACAO,
    CAMINHO_CREDENCIAS,
    CAMINHO_CSV_ESTUDANTES,
    CAMINHO_CSV_RESERVAS,
    CAMINHO_JSON_LANCHES,
    CAMINHO_JSON_PRESETS_TURMAS,
    CAMINHO_SESSAO,
    CAMINHO_TOKEN,
    DIRETORIO_APP,
    DIRETORIO_CONFIG,
    DIRETORIO_LOG,
    ESCOPOS,
    JSON_ID_PLANILHA,
    NOME_ABA_ESTUDANTES,
    NOME_ABA_RESERVAS,
    NOME_LANCHE_PADRAO,
    NOME_PRATO_SEM_RESERVA,
    URL_BANCO_DADOS,
)

from registro.gui.comum.constants import (
    CSIDL_PERSONAL,
    EXCECOES_CAPITALIZACAO,
    MAPA_OFUSCAMENTO_PRONTUARIO,
    REGEX_LIMPEZA_PRONTUARIO,
    SHGFP_TYPE_CURRENT,
    TRADUCAO_CHAVE_EXTERNA,
)

TURMAS_INTEGRADO: List[str] = [
    "1º A - MAC",
    "1º A - MEC",
    "1º B - MEC",
    "2º A - MAC",
    "2º A - MEC",
    "2º B - MEC",
    "3º A - MAC",
    "3º A - MEC",
    "3º B - MEC",
]

DadosNovaSessao = TypedDict(
    "DadosNovaSessao",
    {
        "refeição": Literal["Lanche", "Almoço"],
        "lanche": Optional[str],
        "período": str,
        "data": str,
        "hora": str,
        "groups": List[str],
    },
)
SESSAO = DadosNovaSessao
