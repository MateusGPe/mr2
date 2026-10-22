# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/constants.py (Constantes do Núcleo e Dados)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>
"""
Módulo central do núcleo para definição de caminhos, configurações de dados,
URLs de banco de dados e constantes de persistência.
"""

from pathlib import Path
from typing import Dict, List, Set

DIRETORIO_APP: Path = Path(".")
DIRETORIO_CONFIG: Path = DIRETORIO_APP / "config"
DIRETORIO_LOG: Path = DIRETORIO_APP / "logs"

CAMINHO_CREDENCIAS: Path = DIRETORIO_CONFIG / "credentials.json"
CAMINHO_TOKEN: Path = DIRETORIO_CONFIG / "token.json"
CAMINHO_SESSAO: Path = DIRETORIO_CONFIG / "session.json"
CAMINHO_JSON_LANCHES: Path = DIRETORIO_CONFIG / "lanches.json"
CAMINHO_JSON_PRESETS_TURMAS: Path = DIRETORIO_CONFIG / "presets_turmas.json"
JSON_ID_PLANILHA: Path = DIRETORIO_CONFIG / "spreadsheet.json"
CAMINHO_CSV_ESTUDANTES: Path = DIRETORIO_CONFIG / "students.csv"
CAMINHO_CSV_RESERVAS: Path = DIRETORIO_CONFIG / "reserves.csv"

URL_BANCO_DADOS: str = f"sqlite:///{DIRETORIO_CONFIG.resolve()}/registro.db"

ESCOPOS: List[str] = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
NOME_ABA_RESERVAS: str = "DB"
NOME_ABA_ESTUDANTES: str = "Discentes"

CABECALHO_EXPORTACAO: List[str] = [
    "Matrícula",
    "Data",
    "Nome",
    "Turma",
    "Refeição",
    "Hora",
]

NOME_LANCHE_PADRAO: str = "Lanche Padrão"
NOME_PRATO_SEM_RESERVA: str = "Não Especificado"
