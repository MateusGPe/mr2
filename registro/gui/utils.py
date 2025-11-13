# ----------------------------------------------------------------------------
# Arquivo: registro/gui/utils.py (Utilitários Principais)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>
"""
Módulo com funções utilitárias para a aplicação, incluindo manipulação de
strings, normalização de dados, operações de arquivo (JSON, CSV) e funções
específicas do sistema operacional.
"""

import csv
import ctypes
import ctypes.wintypes
import json
import logging
import os
import platform
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from registro.gui.constants import (
    CSIDL_PERSONAL,
    EXCECOES_CAPITALIZACAO,
    MAPA_OFUSCAMENTO_PRONTUARIO,
    REGEX_LIMPEZA_PRONTUARIO,
    SHGFP_TYPE_CURRENT,
    TRADUCAO_CHAVE_EXTERNA,
)

logger = logging.getLogger(__name__)


def para_codigo(texto: str) -> str:
    """
    Ofusca um texto (geralmente prontuário) para um código pseudo-aleatório.

    Args:
        texto: A string de entrada a ser ofuscada.

    Returns:
        A string ofuscada.
    """
    if not isinstance(texto, str):
        logger.warning(
            "Entrada inválida para para_codigo: esperado str, recebido %s.", type(texto)
        )
        return ""
    texto_limpo = REGEX_LIMPEZA_PRONTUARIO.sub("", texto)
    return texto_limpo.translate(MAPA_OFUSCAMENTO_PRONTUARIO)


def capitalizar(texto: str) -> str:
    """
    Capitaliza um texto (ex: nome completo) de forma inteligente, respeitando
    exceções como preposições e artigos.

    Args:
        texto: A string a ser capitalizada.

    Returns:
        A string formatada.
    """
    if not isinstance(texto, str):
        logger.warning(
            "Entrada inválida para capitalizar: esperado str, recebido %s.", type(texto)
        )
        return ""

    palavras = texto.strip().split()
    palavras_capitalizadas = []
    for palavra in palavras:
        if not palavra:
            continue
        lpalavra = palavra.lower()
        if lpalavra in EXCECOES_CAPITALIZACAO:
            palavras_capitalizadas.append(lpalavra)
        elif len(palavra) == 1 or (len(palavra) == 2 and palavra.endswith(".")):
            palavras_capitalizadas.append(palavra.upper())
        else:
            palavras_capitalizadas.append(palavra.capitalize())

    return " ".join(palavras_capitalizadas)


def ajustar_chaves(dicionario_entrada: Dict[Any, Any]) -> Dict[str, Any]:
    """
    Normaliza as chaves de um dicionário para um formato padrão interno,
    convertendo-as para minúsculas e aplicando traduções predefinidas.

    Args:
        dicionario_entrada: O dicionário com chaves a serem normalizadas.

    Returns:
        Um novo dicionário com as chaves ajustadas.
    """
    if not isinstance(dicionario_entrada, dict):
        logger.warning(
            "Entrada inválida para ajustar_chaves: esperado dict, recebido %s.",
            type(dicionario_entrada),
        )
        return {}

    dicionario_ajustado = {}
    for chave, valor in dicionario_entrada.items():
        chave_str = str(chave).strip().lower()
        chave_norm = TRADUCAO_CHAVE_EXTERNA.get(chave_str, chave_str)

        valor_proc = valor.strip() if isinstance(valor, str) else valor
        if chave_norm in ["nome", "dish"] and isinstance(valor_proc, str):
            valor_proc = capitalizar(valor_proc)
        elif chave_norm == "pront" and isinstance(valor_proc, str):
            valor_proc = REGEX_LIMPEZA_PRONTUARIO.sub("", valor_proc).upper()

        dicionario_ajustado[chave_norm] = valor_proc

    return dicionario_ajustado


def obter_caminho_documentos() -> str:
    """
    Retorna o caminho para a pasta 'Documentos' do usuário de forma
    compatível com diferentes sistemas operacionais (Windows, Linux).

    Returns:
        O caminho absoluto para a pasta de documentos.
    """
    sistema = platform.system()
    caminho_padrao = Path.home() / "Documents"

    if sistema == "Windows":
        try:
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(
                None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf
            )
            caminho = Path(buf.value)
        except Exception as e: # pylint: disable=broad-exception-caught
            logger.warning(
                "Falha ao obter caminho de Documentos via API Windows: %s. Usando padrão.",
                e,
            )
            caminho = caminho_padrao
    elif sistema == "Linux":
        xdg_path = os.environ.get("XDG_DOCUMENTS_DIR")
        caminho = (
            Path(xdg_path) if xdg_path and Path(xdg_path).is_dir() else caminho_padrao
        )
    else:
        caminho = caminho_padrao

    try:
        caminho.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(
            "Não foi possível criar o diretório Documentos em '%s': %s.", caminho, e
        )

    return str(caminho.resolve())


def carregar_json(nome_arquivo: str) -> Optional[Any]:
    """
    Carrega dados de um arquivo JSON de forma segura.

    Args:
        nome_arquivo: O caminho para o arquivo JSON.

    Returns:
        Os dados desserializados do JSON, ou None em caso de erro.
    """
    logger.debug("Carregando JSON de: %s", nome_arquivo)
    try:
        with open(nome_arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e: # pylint: disable=broad-exception-caught
        _tratar_erro_arquivo(e, nome_arquivo, "leitura JSON")
        return None


def salvar_json(nome_arquivo: str, dados: Union[Dict, List]) -> bool:
    """
    Salva dados em um arquivo JSON com formatação legível.

    Args:
        nome_arquivo: O caminho onde o arquivo será salvo.
        dados: Os dados (dicionário ou lista) a serem serializados.

    Returns:
        True se a operação foi bem-sucedida, False caso contrário.
    """
    logger.debug("Salvando JSON em: %s", nome_arquivo)
    try:
        caminho = Path(nome_arquivo)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e: # pylint: disable=broad-exception-caught
        _tratar_erro_arquivo(e, nome_arquivo, "escrita JSON")
        return False


def carregar_csv_como_dict(nome_arquivo: str) -> Optional[List[Dict[str, str]]]:
    """
    Lê um arquivo CSV e o retorna como uma lista de dicionários.

    Args:
        nome_arquivo: O caminho para o arquivo CSV.

    Returns:
        Uma lista de dicionários representando as linhas do CSV, ou None em caso de erro.
    """
    logger.debug("Carregando CSV como dict de: %s", nome_arquivo)
    try:
        with open(nome_arquivo, "r", newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except Exception as e: # pylint: disable=broad-exception-caught
        _tratar_erro_arquivo(e, nome_arquivo, "leitura CSV (como dict)")
        return None


def salvar_csv_de_lista(dados: List[List[Any]], nome_arquivo: str, **kwargs) -> bool:
    """
    Salva uma lista de listas em um arquivo CSV.

    Args:
        dados: Uma lista de listas, onde a primeira lista é o cabeçalho.
        nome_arquivo: O caminho onde o arquivo será salvo.
        **kwargs: Argumentos adicionais para csv.writer (delimiter, etc.).

    Returns:
        True se a operação foi bem-sucedida, False caso contrário.
    """
    logger.debug("Salvando lista para CSV: %s", nome_arquivo)
    if not dados:
        logger.warning("Nenhum dado para salvar em: %s.", nome_arquivo)
        return True
    try:
        caminho = Path(nome_arquivo)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, **kwargs)
            writer.writerows(dados)
        logger.info("%s linhas salvas no CSV: %s", len(dados), nome_arquivo)
        return True
    except Exception as e: # pylint: disable=broad-exception-caught
        _tratar_erro_arquivo(e, nome_arquivo, "escrita CSV (de lista)")
        return False


def _tratar_erro_arquivo(e: Exception, caminho: Union[str, Path], operacao: str):
    """Função auxiliar para registrar erros de I/O de forma padronizada."""
    if isinstance(e, FileNotFoundError):
        logger.error("Arquivo não encontrado em '%s': %s", operacao, caminho)
    elif isinstance(e, PermissionError):
        logger.error("Permissão negada em '%s' no arquivo: %s", operacao, caminho)
    elif isinstance(e, (JSONDecodeError, csv.Error)):
        logger.error("Erro de formato em '%s' no arquivo: %s", operacao, caminho)
    elif isinstance(e, (IOError, OSError)):
        logger.error("Erro de I/O em '%s' em %s: %s", operacao, caminho, e)
    else:
        logger.exception("Erro inesperado em '%s' de %s: %s", operacao, caminho, e)
