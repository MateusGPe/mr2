# --- Arquivo: registro/nucleo/google_api_service.py ---

"""
Módulo funcional para interagir com as APIs do Google, especificamente
Google Sheets, para sincronização de dados.
"""

import json
from pathlib import Path
from typing import List

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound
from gspread.utils import ValueInputOption

from registro.nucleo.exceptions import ErroAPIGoogle

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CAMINHO_CONFIG = Path("./config")
CAMINHO_TOKEN = CAMINHO_CONFIG / "token.json"
CAMINHO_CREDENCIAS = CAMINHO_CONFIG / "credentials.json"
CAMINHO_PLANILHA_JSON = CAMINHO_CONFIG / "spreadsheet.json"


def _obter_credenciais(
    caminho_token: Path = CAMINHO_TOKEN,
    caminho_credenciais: Path = CAMINHO_CREDENCIAS,
) -> Credentials:
    """
    Gerencia o fluxo de autenticação OAuth2 e retorna credenciais válidas.
    (Lógica interna, não destinada ao uso externo).
    """
    credenciais = None
    if caminho_token.exists():
        credenciais = Credentials.from_authorized_user_file(str(caminho_token), SCOPES)
    if not credenciais or not credenciais.valid:
        if credenciais and credenciais.expired and credenciais.refresh_token:
            try:
                credenciais.refresh(Request())
            except Exception as e:
                raise ErroAPIGoogle(f"Falha ao atualizar token de acesso: {e}") from e
        else:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(caminho_credenciais), SCOPES
                )
                credenciais = flow.run_local_server(port=0)
            except FileNotFoundError as e:
                raise ErroAPIGoogle(
                    f"Arquivo de credenciais não encontrado em: {caminho_credenciais}"
                ) from e
        caminho_token.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho_token, "w", encoding="utf-8") as token:
            token.write(credenciais.to_json())
    return credenciais  # type: ignore


class GoogleSheetsService:
    """
    Classe de serviço para interagir com uma planilha específica do Google Sheets.
    """

    def __init__(self, spreadsheet_key: str):
        try:
            credenciais = _obter_credenciais()
            self._cliente = gspread.authorize(credenciais)
            self._planilha = self._cliente.open_by_key(spreadsheet_key)
        except (SpreadsheetNotFound, APIError) as e:
            raise ErroAPIGoogle(
                f"Falha ao abrir planilha com a chave '{spreadsheet_key}': {e}"
            ) from e
        except Exception as e:
            raise ErroAPIGoogle(
                f"Erro inesperado na inicialização do serviço: {e}"
            ) from e

    @property
    def planilha(self) -> gspread.Spreadsheet:
        return self._planilha

    def ler_aba_completa(self, nome_aba: str) -> List[List[str]]:
        try:
            aba = self._planilha.worksheet(nome_aba)
            return aba.get_all_values()
        except (WorksheetNotFound, APIError) as e:
            raise ErroAPIGoogle(f"Falha ao ler dados da aba '{nome_aba}': {e}") from e

    def anexar_linhas_unicas(self, nome_aba: str, linhas: List[List[str]]) -> int:
        try:
            aba = self._planilha.worksheet(nome_aba)
            dados_existentes = set(tuple(row) for row in aba.get_all_values())
            novas_linhas_set = set(tuple(map(str, row)) for row in linhas)
            linhas_para_adicionar = [
                list(row) for row in novas_linhas_set - dados_existentes
            ]
            if linhas_para_adicionar:
                aba.append_rows(
                    linhas_para_adicionar,
                    value_input_option=ValueInputOption.user_entered,
                )
            return len(linhas_para_adicionar)
        except (WorksheetNotFound, APIError) as e:
            raise ErroAPIGoogle(f"Falha ao anexar linhas em '{nome_aba}': {e}") from e


def obter_servico_planilha_padrao() -> GoogleSheetsService:
    """
    Cria uma instância do serviço usando a chave do 'spreadsheet.json'.
    Esta é a forma recomendada de instanciar o serviço.
    """
    try:
        with open(CAMINHO_PLANILHA_JSON, "r", encoding="utf-8") as f:
            config = json.load(f)
        return GoogleSheetsService(config["key"])
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        raise ErroAPIGoogle(
            "Falha ao ler config 'spreadsheet.json'. Verifique o arquivo. Erro: {e}"
        ) from e


class _ServicoPadrao:
    _instance = None

    @classmethod
    def get_instance(cls) -> GoogleSheetsService:
        """Função interna para evitar reinicializar o serviço a cada chamada."""
        if cls._instance is None:
            cls._instance = obter_servico_planilha_padrao()
        return cls._instance


def obter_planilha() -> gspread.Spreadsheet:
    """
    Inicializa o cliente gspread e abre a planilha do arquivo de config.
    Retorna o objeto `gspread.Spreadsheet` para compatibilidade com código antigo.
    """
    servico = _ServicoPadrao.get_instance()
    return servico.planilha


def buscar_valores_aba(planilha: gspread.Spreadsheet, nome_aba: str) -> List[List[str]]:
    """
    Busca todos os valores de uma aba a partir de um objeto planilha.
    Esta função é mantida sem alterações, pois sua lógica é independente.
    """
    try:
        aba = planilha.worksheet(nome_aba)
        return aba.get_all_values()
    except (WorksheetNotFound, APIError) as e:
        raise ErroAPIGoogle(f"Falha ao buscar dados da aba '{nome_aba}': {e}") from e


def anexar_linhas_unicas(
    planilha: gspread.Spreadsheet, linhas: List[List[str]], nome_aba: str
) -> int:
    """
    Adiciona linhas únicas a uma aba a partir de um objeto planilha.
    Esta função é mantida sem alterações, pois sua lógica é independente.
    """
    try:
        aba = planilha.worksheet(nome_aba)
        dados_existentes = set(tuple(row) for row in aba.get_all_values())
        novas_linhas_set = set(tuple(row) for row in linhas)
        linhas_unicas_para_adicionar = [
            list(row) for row in novas_linhas_set - dados_existentes
        ]
        if linhas_unicas_para_adicionar:
            aba.append_rows(
                linhas_unicas_para_adicionar,
                value_input_option=ValueInputOption.user_entered,
            )
        return len(linhas_unicas_para_adicionar)
    except (WorksheetNotFound, APIError) as e:
        raise ErroAPIGoogle(f"Falha ao adicionar linhas em '{nome_aba}': {e}") from e
