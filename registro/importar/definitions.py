# ----------------------------------------------------------------------------
# Arquivo: registro/importar/definitions.py (Módulo de Definições)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Define as estruturas de dados (TypedDicts) utilizadas para comunicação
entre a camada de serviço de importação e a interface de usuário.
"""

import re
from typing import Any, Dict, List, Literal, Optional, TypedDict

REGEX_LIMPEZA_PRONTUARIO: re.Pattern[str] = re.compile(r"^[Ii][Qq]\d0+")

TipoConflito = Literal[
    "NOVO_ESTUDANTE",
    "MULTIPLOS_MATCHES",
    "DADOS_DIVERGENTES",
]


ResolucaoUsuario = Literal[
    "CRIAR_NOVO",
    "VINCULAR",
    "IGNORAR",
]


class CandidatoMatch(TypedDict):
    """Representa uma sugestão de estudante existente no banco."""

    id: int
    prontuario: str
    nome: str
    turma: str
    score: int


class ItemRevisao(TypedDict):
    """
    Representa uma linha da importação que requer decisão do usuário.
    Estrutura otimizada para renderização em tabelas na GUI.
    """

    id_temp: int
    dados_csv: Dict[str, Any]
    tipo_conflito: TipoConflito
    candidatos: List[CandidatoMatch]
    resolucao_escolhida: ResolucaoUsuario
    id_estudante_vinculo: Optional[int]


class ResumoImportacao(TypedDict):
    """Estatísticas da análise inicial da importação."""

    total_linhas: int
    automaticos: int
    invalidos: int
    para_revisao: int
