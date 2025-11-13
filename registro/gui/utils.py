# ----------------------------------------------------------------------------
# Arquivo: registro/gui/utils.py (Utilitários Principais)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>
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
    EXCECOES_CAPITALIZACAO,
    CSIDL_PERSONAL,
    TRADUCAO_CHAVE_EXTERNA,
    REGEX_LIMPEZA_PRONTUARIO,
    MAPA_OFUSCAMENTO_PRONTUARIO,
    SHGFP_TYPE_CURRENT,
)

logger = logging.getLogger(__name__)


def para_codigo(texto: str) -> str:
    if not isinstance(texto, str):
        logger.warning(
            "Entrada inválida para para_codigo: Esperado str, recebido %s.", type(texto)
        )
        return ""
    texto_limpo = REGEX_LIMPEZA_PRONTUARIO.sub("", texto)
    traduzido = texto_limpo.translate(MAPA_OFUSCAMENTO_PRONTUARIO)
    return traduzido


def capitalizar(texto: str) -> str:
    if not isinstance(texto, str):
        logger.warning(
            "Entrada inválida para capitalizar: Esperado str, recebido %s.", type(texto)
        )
        return ""
    texto = texto.strip()
    if not texto:
        return ""
    palavras = texto.split(" ")
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
            palavras_capitalizadas.append(palavra[0].upper() + lpalavra[1:])
    return " ".join(palavras_capitalizadas)


def ajustar_chaves(dicionario_entrada: Dict[Any, Any]) -> Dict[str, Any]:
    dicionario_ajustado: Dict[str, Any] = {}
    if not isinstance(dicionario_entrada, dict):
        logger.warning(
            "Entrada inválida para ajustar_chaves: Esperado dict, recebido %s.",
            type(dicionario_entrada),
        )
        return dicionario_ajustado

    for chave_original, valor in dicionario_entrada.items():
        chave_normalizada: str
        if isinstance(chave_original, str):
            chave_normalizada = chave_original.strip().lower()
            chave_normalizada = TRADUCAO_CHAVE_EXTERNA.get(
                chave_normalizada, chave_normalizada
            )
        else:
            try:
                chave_normalizada = str(chave_original).strip().lower()
                logger.debug(
                    "Chave não-string '%s' convertida para '%s'.",
                    chave_original,
                    chave_normalizada,
                )
            except Exception:
                chave_normalizada = repr(chave_original)
                logger.warning(
                    "Não foi possível converter a chave %s (%s) para string.",
                    chave_original,
                    type(chave_original),
                )

        valor_processado: Any = valor.strip() if isinstance(valor, str) else valor
        if chave_normalizada in ["nome", "dish"] and isinstance(valor_processado, str):
            valor_processado = capitalizar(valor_processado)
        elif chave_normalizada == "pront" and isinstance(valor_processado, str):
            valor_processado = REGEX_LIMPEZA_PRONTUARIO.sub(
                "", valor_processado
            ).upper()

        dicionario_ajustado[chave_normalizada] = valor_processado

    return dicionario_ajustado


def obter_caminho_documentos() -> str:
    sistema = platform.system()
    caminho_padrao: Path = Path.home() / "Documents"
    caminho_a_retornar: Path

    if sistema == "Windows":
        try:
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(  # type: ignore
                None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf
            )
            caminho_a_retornar = Path(buf.value)
            logger.debug("Caminho Documentos (Windows API): %s", caminho_a_retornar)
        except (AttributeError, OSError, Exception) as e:
            logger.warning("Falha ao obter caminho Documentos via API Windows: %s.", e)
            caminho_a_retornar = caminho_padrao
    elif sistema == "Linux":
        xdg_documents = os.environ.get("XDG_DOCUMENTS_DIR")
        if xdg_documents and Path(xdg_documents).is_dir():
            caminho_a_retornar = Path(xdg_documents)
            logger.debug("Caminho Documentos (XDG): %s", caminho_a_retornar)
        else:
            logger.debug("XDG_DOCUMENTS_DIR não definido. Usando padrão.")
            caminho_a_retornar = caminho_padrao
    else:
        logger.debug("Sistema %s. Usando caminho padrão para Documentos.", sistema)
        caminho_a_retornar = caminho_padrao

    try:
        caminho_a_retornar.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(
            "Não foi possível criar o diretório Documentos em '%s': %s.",
            caminho_a_retornar,
            e,
        )
    except Exception as e:
        logger.exception("Erro inesperado ao criar o diretório Documentos: %s", e)

    return str(caminho_a_retornar.resolve())


def _tratar_erro_arquivo(e: Exception, nome_arquivo: Union[str, Path], operacao: str):
    caminho_arquivo = str(nome_arquivo)
    if isinstance(e, FileNotFoundError):
        logger.error("Arquivo não encontrado em '%s': %s", operacao, caminho_arquivo)
    elif isinstance(e, PermissionError):
        logger.error(
            "Permissão negada em '%s' no arquivo: %s", operacao, caminho_arquivo
        )
    elif isinstance(e, JSONDecodeError):
        logger.error("Erro de JSON em '%s' no arquivo: %s", operacao, caminho_arquivo)
    elif isinstance(e, csv.Error):
        logger.error("Erro de CSV em '%s' no arquivo: %s", operacao, caminho_arquivo)
    elif isinstance(e, (IOError, OSError)):
        logger.error("Erro de I/O em '%s' em %s: %s", operacao, caminho_arquivo, e)
    else:
        logger.exception(
            "Erro inesperado em '%s' de %s: %s", operacao, caminho_arquivo, e
        )


def carregar_json(nome_arquivo: str) -> Optional[Any]:
    logger.debug("Carregando JSON de: %s", nome_arquivo)
    try:
        with open(nome_arquivo, "r", encoding="utf-8") as f:
            dados = json.load(f)
            logger.debug("JSON carregado com sucesso de: %s", nome_arquivo)
            return dados
    except Exception as e:
        _tratar_erro_arquivo(e, nome_arquivo, "leitura JSON")
        return None


def salvar_json(nome_arquivo: str, dados: Union[Dict[str, Any], List[Any]]) -> bool:
    logger.debug("Salvando JSON em: %s", nome_arquivo)
    try:
        caminho_arquivo = Path(nome_arquivo)
        caminho_arquivo.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho_arquivo, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        logger.debug("JSON salvo com sucesso em: %s", nome_arquivo)
        return True
    except TypeError as te:
        logger.error("Erro de tipo ao salvar JSON em %s: %s", nome_arquivo, te)
        _tratar_erro_arquivo(te, nome_arquivo, "escrita JSON (erro de tipo)")
        return False
    except Exception as e:
        _tratar_erro_arquivo(e, nome_arquivo, "escrita JSON")
        return False


def carregar_csv_como_dict(nome_arquivo: str) -> Optional[List[Dict[str, str]]]:
    logger.debug("Carregando CSV como dict de: %s", nome_arquivo)
    linhas: List[Dict[str, str]] = []
    try:
        with open(nome_arquivo, "r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            linhas = list(reader)
            logger.debug("Carregadas %s linhas do CSV: %s", len(linhas), nome_arquivo)
            return linhas
    except Exception as e:
        _tratar_erro_arquivo(e, nome_arquivo, "leitura CSV (como dict)")
        return None


def salvar_csv_de_lista(
    dados: List[List[Any]],
    nome_arquivo: str,
    delimitador: str = ",",
    quotechar: str = '"',
    quoting: int = csv.QUOTE_MINIMAL,
) -> bool:
    logger.debug("Salvando lista para CSV: %s", nome_arquivo)
    if not dados:
        logger.warning("Nenhum dado para salvar em: %s.", nome_arquivo)
        return True
    try:
        caminho_arquivo = Path(nome_arquivo)
        caminho_arquivo.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho_arquivo, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(
                csvfile, delimiter=delimitador, quotechar=quotechar, quoting=quoting
            )
            writer.writerows(dados)
        logger.info("%s linhas salvas no CSV: %s", len(dados), nome_arquivo)
        return True
    except Exception as e:
        _tratar_erro_arquivo(e, nome_arquivo, "escrita CSV (de lista)")
        return False
