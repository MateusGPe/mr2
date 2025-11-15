# --- Arquivo: registro/nucleo/importers/strategies.py ---

"""
Define as estratégias para carregar dados de diferentes fontes (CSV, Sheets, etc.).
O uso do Padrão de Estratégia torna o sistema extensível a novas fontes de dados
(ex: API, arquivo XML) sem alterar o serviço de importação principal.
"""

import abc
import csv
from typing import Dict, List

from registro.importar.patterns_find import detectar_tipo_valor
from registro.nucleo import google_api_service
from registro.nucleo.exceptions import ErroImportacaoDados
from registro.nucleo.utils import ajustar_chaves_e_valores


class EstrategiaCarregamento(abc.ABC):
    """Interface abstrata para as estratégias de carregamento de dados."""

    @abc.abstractmethod
    def carregar(self, fonte: str) -> List[Dict[str, str]]:
        """Carrega os dados da fonte e retorna uma lista de dicionários."""
        raise NotImplementedError


class CarregarCSVSimples(EstrategiaCarregamento):
    """Carrega dados de um arquivo CSV/TXT contendo apenas nomes, um por linha."""

    def carregar(self, fonte: str) -> List[Dict[str, str]]:
        try:
            with open(fonte, "r", encoding="utf-8") as f:
                linhas = set()
                for linha in f:
                    linha = linha.strip()
                    chave = detectar_tipo_valor(linha)
                    print({chave: linha})

                    if chave in ["pront", "nome"]:
                        linhas.add((chave, linha))
                return list({c: v} for c, v in linhas)

        except FileNotFoundError as e:
            raise ErroImportacaoDados(f"Arquivo não encontrado: {fonte}") from e


class CarregarCSVDetalhado(EstrategiaCarregamento):
    """Carrega dados de um arquivo CSV com cabeçalhos."""

    def carregar(self, fonte: str) -> List[Dict[str, str]]:
        try:
            with open(fonte, "r", encoding="utf-8") as f:
                leitor = csv.DictReader(f)
                # `ajustar_chaves_e_valores` padroniza os cabeçalhos para facilitar o mapeamento.
                return [ajustar_chaves_e_valores(linha) for linha in leitor]
        except (FileNotFoundError, csv.Error) as e:
            raise ErroImportacaoDados(f"Falha ao ler CSV detalhado: {e}") from e


class CarregarCSVSeguro(EstrategiaCarregamento):
    """Carrega dados de um arquivo CSV com cabeçalhos."""

    def carregar(self, fonte: str) -> List[Dict[str, str]]:
        try:
            with open(fonte, "r", encoding="utf-8") as f:
                leitor = csv.reader(f)

                next(leitor)
                linhas = []

                for valores in leitor:
                    itens = {
                        "prontuario": None,
                        "nome": None,
                        "prato": None,
                        "data": None,
                    }
                    for valor in valores:
                        c, v = detectar_tipo_valor(valor)
                        if c is None:
                            continue
                        itens[c] = v
                    linhas.append(itens)

                return linhas
        except (FileNotFoundError, csv.Error) as e:
            raise ErroImportacaoDados(f"Falha ao ler CSV detalhado: {e}") from e


class CarregarGoogleSheets(EstrategiaCarregamento):
    """Carrega dados de uma aba de uma planilha do Google Sheets."""

    def carregar(self, fonte: str) -> List[Dict[str, str]]:
        """`fonte` deve ser uma string no formato "chave_da_planilha:nome_da_aba"."""
        try:
            _chave, nome_aba = fonte.split(":", 1)
            # A chave da planilha pode ser usada aqui para abrir a planilha correta,
            # embora o `obter_planilha` atual use a chave do arquivo de configuração.
            # Idealmente, `obter_planilha` seria modificado para aceitar uma chave.
            planilha = google_api_service.obter_planilha()
            valores = google_api_service.buscar_valores_aba(planilha, nome_aba)

            if not valores or len(valores) < 2:
                return []  # Retorna vazio se não houver dados ou apenas o cabeçalho.

            cabecalho = [str(h).strip().lower() for h in valores[0]]
            dados = []
            for linha in valores[1:]:
                # Garante que a linha tenha o mesmo número de colunas que o cabeçalho
                linha_dict = dict(zip(cabecalho, linha))
                dados.append(ajustar_chaves_e_valores(linha_dict))
            return dados
        except (ValueError, IndexError, google_api_service.ErroAPIGoogle) as e:
            raise ErroImportacaoDados(f"Falha ao carregar do Google Sheets: {e}") from e
