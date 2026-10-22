# ----------------------------------------------------------------------------
# Arquivo: registro/importar/strategies.py (Estratégias de Carregamento)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Estratégias para carregar dados de diferentes fontes (CSV, TXT, Google Sheets).
"""

import abc
import csv
from typing import Dict, List, Optional

from registro.importar.patterns_find import (
    ajustar_chaves_e_valores,
    checar_prontuario,
    detectar_tipo_coluna,
)
from registro.nucleo import google_api_service
from registro.nucleo.exceptions import ErroImportacaoDados


class EstrategiaCarregamento(abc.ABC):
    """Interface abstrata para estratégias de carregamento."""

    @abc.abstractmethod
    def carregar(self, fonte: str) -> List[Dict[str, Optional[str]]]:
        """Carrega dados da fonte e retorna lista de dicionários padronizados."""
        raise NotImplementedError


class CarregarListaSimples(EstrategiaCarregamento):
    """
    Carrega arquivo TXT/CSV de coluna única.
    Separa Prontuário de Nome via Regex. Outros campos ficam vazios.
    """

    def carregar(self, fonte: str) -> List[Dict[str, Optional[str]]]:
        try:
            dados = []
            with open(fonte, "r", encoding="utf-8") as f:
                for linha in f:
                    texto = linha.strip().replace("\ufeff", "")
                    if not texto:
                        continue

                    item = {
                        "prontuario": None,
                        "nome": None,
                        "data": None,
                        "prato": None,
                        "turma": None,
                    }

                    if checar_prontuario(texto):
                        item["prontuario"] = texto.upper()
                    else:
                        item["nome"] = " ".join(p.capitalize() for p in texto.split())

                    dados.append(item)
            return dados
        except FileNotFoundError as e:
            raise ErroImportacaoDados(f"Arquivo não encontrado: {fonte}") from e


class CarregarCSVPosicional(EstrategiaCarregamento):
    """
    Carrega CSV sem cabeçalho (ou ignora cabeçalho).
    Usa detecção vertical de colunas para evitar conflitos de tipos.
    """

    def carregar(self, fonte: str) -> List[Dict[str, Optional[str]]]:
        try:
            with open(fonte, "r", encoding="utf-8") as f:
                leitor = csv.reader(f)
                linhas_csv = list(leitor)

            if not linhas_csv:
                return []

            colunas = list(zip(*linhas_csv))
            mapa_colunas: Dict[int, str] = {}

            for i, valores_coluna in enumerate(colunas):
                tipo = detectar_tipo_coluna(valores_coluna)
                if tipo:
                    mapa_colunas[i] = tipo

            if not mapa_colunas:
                return []

            resultados = []
            for linha in linhas_csv:
                if not any(linha):
                    continue

                item = {}
                for idx, tipo in mapa_colunas.items():
                    if idx < len(linha):
                        val = linha[idx].strip()
                        if tipo == "prontuario":
                            val = val.upper()
                        elif tipo == "nome":
                            val = " ".join(p.capitalize() for p in val.split())
                        item[tipo] = val

                if item:
                    resultados.append(item)

            return resultados
        except (FileNotFoundError, csv.Error) as e:
            raise ErroImportacaoDados(f"Erro no CSV: {e}") from e


class CarregarCSVComCabecalho(EstrategiaCarregamento):
    """Carrega CSV confiando na primeira linha como cabeçalho."""

    def carregar(self, fonte: str) -> List[Dict[str, Optional[str]]]:
        try:
            with open(fonte, "r", encoding="utf-8") as f:
                leitor = csv.DictReader(f)
                return [ajustar_chaves_e_valores(linha) for linha in leitor]
        except (FileNotFoundError, csv.Error) as e:
            raise ErroImportacaoDados(f"Erro no CSV com cabeçalho: {e}") from e


class CarregarGoogleSheets(EstrategiaCarregamento):
    """Carrega dados do Google Sheets."""

    def carregar(self, fonte: str) -> List[Dict[str, Optional[str]]]:
        """fonte: 'NomeDaAba' ou 'IDPlanilha:NomeDaAba'."""
        try:
            if ":" in fonte:
                sheet_key, nome_aba = fonte.split(":", 1)
            else:
                sheet_key = None
                nome_aba = fonte

            planilha = google_api_service.obter_planilha(sheet_key)
            valores = google_api_service.buscar_valores_aba(planilha, nome_aba)

            if not valores or len(valores) < 2:
                return []

            cabecalho = [str(h).strip().lower() for h in valores[0]]
            dados = []

            for linha in valores[1:]:
                linha_ajustada = linha + [""] * (len(cabecalho) - len(linha))
                linha_dict = dict(zip(cabecalho, linha_ajustada))
                dados.append(ajustar_chaves_e_valores(linha_dict))

            return dados
        except Exception as e:
            raise ErroImportacaoDados(f"Erro no Google Sheets: {e}") from e
