# --- Arquivo: registro/nucleo/google_api_service.py ---

"""
Módulo funcional para interagir com as APIs do Google, especificamente
Google Sheets, para sincronização de dados.
"""

import json
from pathlib import Path
from typing import Any, List

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound
from gspread.utils import ValueInputOption

from registro.nucleo.exceptions import ErroAPIGoogle

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
CAMINHO_CONFIG = Path("./config")

def obter_credenciais(
    caminho_token: Path = CAMINHO_CONFIG / "token.json",
    caminho_credenciais: Path = CAMINHO_CONFIG / "credentials.json"
) -> Credentials:
    """Gerencia a autenticação e retorna credenciais válidas."""
    credenciais = None
    if caminho_token.exists():
        credenciais = Credentials.from_authorized_user_file(str(caminho_token), SCOPES)

    if credenciais and credenciais.valid:
        return credenciais

    if not credenciais or not credenciais.valid:
        if credenciais and credenciais.expired and credenciais.refresh_token:
            try:
                credenciais.refresh(Request())
            except Exception as e:
                raise ErroAPIGoogle(f"Falha ao atualizar token: {e}") from e
        else:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(caminho_credenciais), SCOPES
                )
                credenciais = flow.run_local_server(port=0)
            except FileNotFoundError as e:
                raise ErroAPIGoogle(
                    f"Arquivo de credenciais não encontrado em: {caminho_credenciais}") from e
        
        caminho_token.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho_token, "w", encoding="utf-8") as token:
            token.write(credenciais.to_json())
            
    return credenciais


def obter_planilha(arquivo_config: Path = CAMINHO_CONFIG / "spreadsheet.json") -> gspread.Spreadsheet:
    """
    Inicializa o cliente gspread e abre a planilha especificada no arquivo de config.
    """
    try:
        credenciais = obter_credenciais()
        cliente = gspread.authorize(credenciais)
        with open(arquivo_config, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return cliente.open_by_key(config['key'])
    except (FileNotFoundError, json.JSONDecodeError, SpreadsheetNotFound) as e:
        raise ErroAPIGoogle(f"Falha ao inicializar planilha: {e}") from e
    except Exception as e:
        raise ErroAPIGoogle(f"Erro inesperado ao conectar ao Google Sheets: {e}") from e


def buscar_valores_aba(planilha: gspread.Spreadsheet, nome_aba: str) -> List[List[str]]:
    """Busca todos os valores de uma aba específica de uma planilha."""
    try:
        aba = planilha.worksheet(nome_aba)
        return aba.get_all_values()
    except (WorksheetNotFound, APIError) as e:
        raise ErroAPIGoogle(f"Falha ao buscar dados da aba '{nome_aba}': {e}") from e


def anexar_linhas_unicas(planilha: gspread.Spreadsheet, linhas: List[List[str]],
                         nome_aba: str) -> int:
    """Adiciona apenas as linhas que ainda não existem em uma aba."""
    try:
        aba = planilha.worksheet(nome_aba)
        dados_existentes = set(tuple(row) for row in aba.get_all_values())
        novas_linhas_set = set(tuple(row) for row in linhas)

        linhas_unicas_para_adicionar = [list(row) for row in novas_linhas_set - dados_existentes]

        if linhas_unicas_para_adicionar:
            aba.append_rows(
                linhas_unicas_para_adicionar, value_input_option=ValueInputOption.user_entered
            )
        return len(linhas_unicas_para_adicionar)
    except (WorksheetNotFound, APIError) as e:
        raise ErroAPIGoogle(f"Falha ao adicionar linhas em '{nome_aba}': {e}") from e