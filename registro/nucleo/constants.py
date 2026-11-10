# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/constants.py (Constantes do Núcleo e Dados)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>
"""
Módulo central do núcleo para definição de caminhos, configurações de dados,
URLs de banco de dados e constantes de persistência.
"""

import sys
from pathlib import Path
from typing import Dict, List, Set

if getattr(sys, "frozen", False):
    DIRETORIO_APP: Path = Path(sys.executable).parent
else:
    DIRETORIO_APP: Path = Path(".")

DIRETORIO_CONFIG: Path = DIRETORIO_APP / "config"
DIRETORIO_LOG: Path = DIRETORIO_APP / "logs"
DIRETORIO_BACKUPS: Path = DIRETORIO_APP / "backups"

CAMINHO_CREDENCIAS: Path = DIRETORIO_CONFIG / "credentials.json"
CAMINHO_TOKEN: Path = DIRETORIO_CONFIG / "token.json"
CAMINHO_SETTINGS: Path = DIRETORIO_CONFIG / "settings.json"
CAMINHO_SESSAO: Path = DIRETORIO_CONFIG / "session.json"
CAMINHO_JSON_LANCHES: Path = DIRETORIO_CONFIG / "lanches.json"
CAMINHO_JSON_PRESETS_TURMAS: Path = DIRETORIO_CONFIG / "presets_turmas.json"
CAMINHO_JSON_TURMAS_INTEGRADO: Path = DIRETORIO_CONFIG / "turmas_integrado.json"
CAMINHO_JSON_MAPEAMENTO_COLUNAS: Path = DIRETORIO_CONFIG / "mapeamento_colunas.json"
CAMINHO_GRADE_HORARIOS: Path = DIRETORIO_CONFIG / "grade_horarios.json"
JSON_ID_PLANILHA: Path = DIRETORIO_CONFIG / "spreadsheet.json"
CAMINHO_CSV_ESTUDANTES: Path = DIRETORIO_CONFIG / "students.csv"
CAMINHO_CSV_RESERVAS: Path = DIRETORIO_CONFIG / "reserves.csv"

URL_BANCO_DADOS: str = f"sqlite:///{DIRETORIO_CONFIG.resolve()}/registro.db"

# Valores padrão com fallback para configurações extraíveis em JSON
TURMAS_INTEGRADO_PADRAO: List[str] = [
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

MAPEAMENTO_COLUNAS_PADRAO: Dict[str, str] = {
    "matrícula iq": "pront",
    "matrícula": "pront",
    "prontuário": "pront",
    "refeição": "dish",
    "curso": "turma",
    "situação": "status",
    "nome completo": "nome",
}

AUDIO_FREQ_SUCESSO_PADRAO: int = 1000
AUDIO_DUR_SUCESSO_MS_PADRAO: int = 200
AUDIO_FREQ_ERRO_PADRAO: int = 400
AUDIO_DUR_ERRO_MS_PADRAO: int = 1000

ESCOPOS: List[str] = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
NOME_ABA_RESERVAS: str = "DB"
NOME_ABA_ESTUDANTES: str = "Discentes"
NOME_ABA_CANCELADOS: str = "Consumo_Cancelados"
NOME_ABA_CONFIGURACAO: str = "Configuração"
NOME_ABA_LANCHES: str = "Lanches"

REFEICOES_PERMITIDAS: List[str] = [
    "Almoço",
    "Jantar",
    "Lanche",
]

CATEGORIA_PADRAO: str = "REGULAR"
CATEGORIA_PAP: str = "PAP"

CABECALHO_EXPORTACAO: List[str] = [
    "Matrícula",
    "Data",
    "Nome",
    "Turma",
    "Refeição",
    "Hora",
    "Categoria",
]

CABECALHO_DISCENTES: List[str] = [
    "Matrícula",
    "Nome",
    "Turma",
    "Categoria",
]

CABECALHO_CANCELADOS: List[str] = [
    "Data",
    "Hora Original",
    "Hora Cancelamento",
    "Matrícula",
    "Nome",
    "Turma",
    "Categoria",
    "Refeição",
    "Cancelado Por",
    "Motivo",
]

CABECALHO_RESERVAS: List[str] = [
    "DATA",
    "MATRÍCULA",
    "NOME",
    "TURMA",
    "REFEIÇÃO",
    "DIA DA SEMANA",
]

CABECALHO_CONFIGURACAO: List[str] = [
    "Dia",
    "Refeição",
    "Horário Início",
    "Horário Fim",
    "Turmas Liberadas",
    "Categorias Permitidas",
]

CABECALHO_LANCHES: List[str] = [
    "Lanche",
]

ESTRUTURA_ABAS_PADRAO: Dict[str, List[str]] = {
    NOME_ABA_ESTUDANTES: CABECALHO_DISCENTES,
    NOME_ABA_RESERVAS: CABECALHO_RESERVAS,
    "Almoço": CABECALHO_EXPORTACAO,
    "Jantar": CABECALHO_EXPORTACAO,
    "Lanche": CABECALHO_EXPORTACAO,
    NOME_ABA_CANCELADOS: CABECALHO_CANCELADOS,
    NOME_ABA_CONFIGURACAO: CABECALHO_CONFIGURACAO,
    NOME_ABA_LANCHES: CABECALHO_LANCHES,
}

NOME_LANCHE_PADRAO: str = "Lanche Padrão"
NOME_PRATO_SEM_RESERVA: str = "Não Especificado"
