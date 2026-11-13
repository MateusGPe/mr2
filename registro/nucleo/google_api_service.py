# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/google_api_service.py (Módulo Google API Service)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Módulo funcional para interagir com as APIs do Google, especificamente
Google Sheets, para sincronização de dados.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import gspread
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from gspread.exceptions import (
    APIError,
    GSpreadException,
    SpreadsheetNotFound,
    WorksheetNotFound,
)
from gspread.utils import ValueInputOption
from requests.exceptions import RequestException

from registro.nucleo.constants import (
    CAMINHO_CREDENCIAS,
    CAMINHO_TOKEN,
    ESTRUTURA_ABAS_PADRAO,
)
from registro.nucleo.constants import (
    ESCOPOS as SCOPES,
)
from registro.nucleo.constants import (
    JSON_ID_PLANILHA as CAMINHO_PLANILHA_JSON,
)
from registro.nucleo.exceptions import ErroAPIGoogle

logger = logging.getLogger(__name__)


def _chave_identificadora_linha(linha: List[str]) -> tuple[str, ...]:
    """Gera uma chave de identidade usando apenas os campos relevantes."""
    valores = [str(item).strip() for item in linha]
    if len(valores) < 4:
        return tuple(valores)
    return tuple(valores[:2] + valores[-2:])


def _obter_credenciais(
    caminho_token: Path = CAMINHO_TOKEN,
    caminho_credenciais: Path = CAMINHO_CREDENCIAS,
) -> Credentials:
    """
    Gerencia o fluxo de autenticação OAuth2 / Service Account e retorna credenciais válidas.
    """
    # 1. Verifica se as credenciais são do tipo Service Account (Conta de Serviço)
    if caminho_credenciais.exists():
        try:
            with open(caminho_credenciais, "r", encoding="utf-8") as f:
                conteudo = json.load(f)
                if conteudo.get("type") == "service_account":
                    return ServiceAccountCredentials.from_service_account_file(  # type: ignore
                        str(caminho_credenciais), scopes=SCOPES
                    )
        except (OSError, json.JSONDecodeError, ValueError, GoogleAuthError) as e:
            logger.debug(
                "Credenciais em %s não são conta de serviço válida: %s",
                caminho_credenciais,
                e,
            )

    # 2. Fluxo OAuth2 Desktop com token existente
    credenciais = None
    if caminho_token.exists():
        try:
            credenciais = Credentials.from_authorized_user_file(
                str(caminho_token), SCOPES
            )
        except (OSError, ValueError) as e:
            logger.debug("Token existente inválido ou ilegível: %s", e)
            credenciais = None

    if credenciais and credenciais.valid:
        return credenciais

    if credenciais and credenciais.expired and credenciais.refresh_token:
        try:
            credenciais.refresh(Request())
        except Exception as e:  # noqa: BLE001 - traduz qualquer falha de refresh para ErroAPIGoogle
            raise ErroAPIGoogle(f"Falha ao atualizar token de acesso: {e}") from e
    else:
        if not caminho_credenciais.exists():
            raise ErroAPIGoogle(
                f"Arquivo de credenciais não encontrado em: {caminho_credenciais}"
            )
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(caminho_credenciais), SCOPES
            )
            credenciais = flow.run_local_server(port=0)
        except (OSError, ValueError, GoogleAuthError) as e:
            raise ErroAPIGoogle(f"Falha na autenticação OAuth: {e}") from e

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
        except Exception as e:  # noqa: BLE001 - fronteira de serviço traduz falhas para ErroAPIGoogle
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
        except (WorksheetNotFound, APIError, RequestException) as e:
            raise ErroAPIGoogle(f"Falha ao ler dados da aba '{nome_aba}': {e}") from e

    def anexar_linhas_unicas(self, nome_aba: str, linhas: List[List[str]]) -> int:
        try:
            try:
                aba = self._planilha.worksheet(nome_aba)
            except WorksheetNotFound:
                self.criar_abas_necessarias()
                aba = self._planilha.worksheet(nome_aba)

            dados_existentes = {
                _chave_identificadora_linha(row) for row in aba.get_all_values()
            }
            linhas_para_adicionar = []
            for row in linhas:
                chave = _chave_identificadora_linha(row)
                if chave not in dados_existentes:
                    linhas_para_adicionar.append(row)
                    dados_existentes.add(chave)
            if linhas_para_adicionar:
                aba.append_rows(
                    linhas_para_adicionar,
                    value_input_option=ValueInputOption.user_entered,
                )
            return len(linhas_para_adicionar)
        except (WorksheetNotFound, APIError, RequestException) as e:
            raise ErroAPIGoogle(f"Falha ao anexar linhas em '{nome_aba}': {e}") from e

    def criar_abas_necessarias(
        self,
        estrutura: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, List[str]]:
        """
        Garante que as abas essenciais existam na planilha com cabeçalhos padronizados.
        - Não sobrescreve abas existentes com dados.
        - Se uma aba já existir mas estiver vazia, insere o cabeçalho padronizado.
        - Congela a primeira linha (cabeçalho) e aplica estilo negrito.

        Retorna dicionário com listas:
            {"criadas": [...], "atualizadas_vazias": [...], "mantidas": [...]}
        """
        estrutura_alvo = estrutura if estrutura is not None else ESTRUTURA_ABAS_PADRAO
        criadas: List[str] = []
        atualizadas_vazias: List[str] = []
        mantidas: List[str] = []

        try:
            worksheets_existentes = {ws.title: ws for ws in self._planilha.worksheets()}

            for nome_aba, cabecalho in estrutura_alvo.items():
                if nome_aba not in worksheets_existentes:
                    aba = self._planilha.add_worksheet(
                        title=nome_aba,
                        rows=100,
                        cols=max(len(cabecalho), 10),
                    )
                    aba.append_row(
                        cabecalho,
                        value_input_option=ValueInputOption.user_entered,
                    )
                    _formatar_cabecalho_aba(aba)
                    criadas.append(nome_aba)
                else:
                    aba = worksheets_existentes[nome_aba]
                    valores = aba.get_all_values()
                    esta_vazia = not valores or not any(
                        any(str(cel).strip() for cel in linha) for linha in valores
                    )
                    if esta_vazia:
                        aba.append_row(
                            cabecalho,
                            value_input_option=ValueInputOption.user_entered,
                        )
                        _formatar_cabecalho_aba(aba)
                        atualizadas_vazias.append(nome_aba)
                    else:
                        mantidas.append(nome_aba)

            return {
                "criadas": criadas,
                "atualizadas_vazias": atualizadas_vazias,
                "mantidas": mantidas,
            }
        except (APIError, RequestException, GSpreadException) as e:
            raise ErroAPIGoogle(
                f"Falha ao criar/verificar abas na planilha: {e}"
            ) from e


def _formatar_cabecalho_aba(aba: gspread.Worksheet) -> None:
    """Congela e aplica negrito na linha de cabeçalho da aba, sem falhar em caso de erro de formatação."""
    try:
        aba.freeze(rows=1)
    except (APIError, RequestException, GSpreadException) as e:
        logger.debug(
            "Não foi possível congelar cabeçalho da aba '%s': %s", aba.title, e
        )
    try:
        aba.format("1:1", {"textFormat": {"bold": True}})
    except (APIError, RequestException, GSpreadException) as e:
        logger.debug(
            "Não foi possível formatar cabeçalho da aba '%s': %s", aba.title, e
        )


def obter_servico_planilha_padrao() -> GoogleSheetsService:
    """
    Cria uma instância do serviço usando a chave do 'spreadsheet.json'.
    Esta é a forma recomendada de instanciar o serviço.
    """
    try:
        with open(CAMINHO_PLANILHA_JSON, "r", encoding="utf-8") as f:
            config = json.load(f)
        key = config.get("key") or config.get("spreadsheet_id")
        if not key:
            raise KeyError("Chave 'key' ou 'spreadsheet_id' não encontrada no arquivo.")
        return GoogleSheetsService(str(key).strip())
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        raise ErroAPIGoogle(
            f"Falha ao ler config 'spreadsheet.json'. Verifique o arquivo. Erro: {e}"
        ) from e


class _ServicoPadrao:
    _instance = None

    @classmethod
    def get_instance(cls) -> GoogleSheetsService:
        """Função interna para evitar reinicializar o serviço a cada chamada."""
        if cls._instance is None:
            cls._instance = obter_servico_planilha_padrao()
        return cls._instance


def obter_planilha(sheet_key: Optional[str] = None) -> gspread.Spreadsheet:
    """
    Inicializa o cliente gspread e abre a planilha do arquivo de config.
    Retorna o objeto `gspread.Spreadsheet` para compatibilidade com código antigo.
    """
    if sheet_key:
        return GoogleSheetsService(sheet_key).planilha

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
    except (WorksheetNotFound, APIError, RequestException) as e:
        raise ErroAPIGoogle(f"Falha ao buscar dados da aba '{nome_aba}': {e}") from e


def anexar_linhas_unicas(
    planilha: gspread.Spreadsheet, linhas: List[List[str]], nome_aba: str
) -> int:
    """
    Adiciona linhas únicas a uma aba a partir de um objeto planilha.
    A comparação considera apenas a matrícula, a data, a refeição e a hora.
    """
    try:
        try:
            aba = planilha.worksheet(nome_aba)
        except WorksheetNotFound:
            criar_abas_necessarias(planilha)
            aba = planilha.worksheet(nome_aba)
        dados_existentes = {
            _chave_identificadora_linha(row) for row in aba.get_all_values()
        }
        linhas_unicas_para_adicionar = []
        for row in linhas:
            chave = _chave_identificadora_linha(row)
            if chave not in dados_existentes:
                linhas_unicas_para_adicionar.append(row)
                dados_existentes.add(chave)
        if linhas_unicas_para_adicionar:
            aba.append_rows(
                linhas_unicas_para_adicionar,
                value_input_option=ValueInputOption.user_entered,
            )
        return len(linhas_unicas_para_adicionar)
    except (WorksheetNotFound, APIError, RequestException) as e:
        raise ErroAPIGoogle(f"Falha ao adicionar linhas em '{nome_aba}': {e}") from e


def criar_abas_necessarias(
    planilha: Optional[gspread.Spreadsheet] = None,
    estrutura: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, List[str]]:
    """
    Garante a existência das abas essenciais na planilha do Google Sheets.
    Se nenhuma planilha for especificada, usa a planilha padrão configurada.
    """
    if planilha is None:
        servico = _ServicoPadrao.get_instance()
        return servico.criar_abas_necessarias(estrutura)

    class _WrapperServico:
        def __init__(self, pl: gspread.Spreadsheet):
            self._planilha = pl

    wrapper = _WrapperServico(planilha)
    return GoogleSheetsService.criar_abas_necessarias(wrapper, estrutura)  # type: ignore
