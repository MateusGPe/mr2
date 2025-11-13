# ----------------------------------------------------------------------------
# Arquivo: registro/control/constants.py (Constantes da Aplicação)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>
"""
Módulo central para a definição de constantes utilizadas em toda a aplicação.

Isso inclui caminhos de diretórios, URLs, configurações de API, mapeamentos
de dados e listas de valores predefinidos.
"""

import re
from pathlib import Path
from typing import Dict, List, Literal, Optional, Set, TypedDict

# --- Caminhos de Diretórios e Arquivos ---
DIRETORIO_APP: Path = Path(".")
DIRETORIO_CONFIG: Path = DIRETORIO_APP / "config"
DIRETORIO_LOG: Path = DIRETORIO_APP / "logs"

CAMINHO_CREDENCIAS: Path = DIRETORIO_CONFIG / "credentials.json"
CAMINHO_TOKEN: Path = DIRETORIO_CONFIG / "token.json"
CAMINHO_SESSAO: Path = DIRETORIO_CONFIG / "session.json"
CAMINHO_JSON_LANCHES: Path = DIRETORIO_CONFIG / "lanches.json"
JSON_ID_PLANILHA: Path = DIRETORIO_CONFIG / "spreadsheet.json"
CAMINHO_CSV_ESTUDANTES: Path = DIRETORIO_CONFIG / "students.csv"
CAMINHO_CSV_RESERVAS: Path = DIRETORIO_CONFIG / "reserves.csv"

URL_BANCO_DADOS: str = f"sqlite:///{DIRETORIO_CONFIG.resolve()}/registro.db"

# --- Configurações da API Google ---
ESCOPOS: List[str] = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
NOME_ABA_RESERVAS: str = "DB"
NOME_ABA_ESTUDANTES: str = "Discentes"

# --- Mapeamentos e Transformações de Dados ---
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

# --- Valores Padrão e Listas de Negócio ---
TURMAS_INTEGRADO: List[str] = [
    "1º A - MAC",
    "1º A - MEC",
    "1º B - MEC",
    "2º A - MAC",
    "2º A - MEC",
    "2º B - MEC",
    "3º A - MEC",
    "3º B - MEC",
]
NOME_LANCHE_PADRAO: str = "Lanche Padrão"
NOME_PRATO_SEM_RESERVA: str = "Não Especificado"
CABECALHO_EXPORTACAO: List[str] = [
    "Matrícula",
    "Data",
    "Nome",
    "Turma",
    "Refeição",
    "Hora",
]

# --- Tipagem de Dados ---
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

# --- Constantes para API do Windows (obter pasta Documentos) ---
CSIDL_PERSONAL: int = 5
SHGFP_TYPE_CURRENT: int = 0
