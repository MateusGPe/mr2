"""
Módulo para interagir com as APIs do Google, especificamente
Google Sheets e Google Drive, para sincronização de dados.
"""

import json
import os.path
from typing import Any, List

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound
from gspread.utils import ValueInputOption
from registro.nucleo.exceptions import GoogleAPIError

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


def get_credentials(
    token_path: str = "./config/token.json",
    creds_path: str = "./config/credentials.json"
) -> Credentials | Any:
    """Gerencia a autenticação e retorna credenciais válidas."""
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if creds and creds.valid:
            return creds

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                raise GoogleAPIError(f"Falha ao atualizar token: {e}") from e
        else:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    creds_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
            except FileNotFoundError as e:
                raise GoogleAPIError(f"Arquivo de credenciais não encontrado em: {creds_path}"
                                     ) from e
        with open(token_path, "w", encoding="utf-8") as token:
            token.write(creds.to_json())
    return creds


class SpreadSheet:
    """Classe para interagir com uma planilha do Google Sheets."""

    def __init__(self, config_file: str = "./config/spreadsheet.json"):
        """Inicializa o cliente e abre a planilha especificada."""
        try:
            creds = get_credentials()
            client = gspread.authorize(creds)
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.spreadsheet = client.open_by_key(config['key'])
        except (FileNotFoundError, json.JSONDecodeError, SpreadsheetNotFound) as e:
            raise GoogleAPIError(f"Falha ao inicializar SpreadSheet: {e}") from e
        except Exception as e:
            raise GoogleAPIError(f"Erro inesperado: {e}") from e

    def fetch_sheet_values(self, sheet_name: str) -> List[List[str]]:
        """Busca todos os valores de uma aba específica."""
        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
            return worksheet.get_all_values()
        except (WorksheetNotFound, APIError) as e:
            raise GoogleAPIError(
                f"Falha ao buscar dados da aba '{sheet_name}': {e}"
            ) from e

    def append_unique_rows(self, rows: List[List[str]], sheet_name: str) -> int:
        """Adiciona apenas as linhas que ainda não existem na aba."""
        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
            existing_data = set(
                tuple(row) for row in worksheet.get_all_values()
            )
            new_rows_set = set(tuple(row) for row in rows)

            unique_rows_to_add = [
                list(row) for row in new_rows_set - existing_data
            ]

            if unique_rows_to_add:
                worksheet.append_rows(
                    unique_rows_to_add, value_input_option=ValueInputOption.user_entered
                )
            return len(unique_rows_to_add)
        except (WorksheetNotFound, APIError) as e:
            raise GoogleAPIError(
                f"Falha ao adicionar linhas em '{sheet_name}': {e}"
            ) from e
