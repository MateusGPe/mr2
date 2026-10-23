# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/logging_config.py (Configuração de Logs do Sistema)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>
"""
Módulo centralizador de configuração de logging do sistema.
Configura saída dupla (Console e Arquivo Rotacionado em disco) em UTF-8,
além de ganchos para captura de exceções não tratadas em threads e no processo principal.
"""

import logging
import logging.handlers
import sys
import threading
from pathlib import Path
from typing import Optional

from registro.nucleo.constants import DIRETORIO_LOG

FORMATO_LOG_PADRAO = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
MAX_BYTES_LOG = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT_LOG = 5


def _instalar_ganchos_excecao(logger: logging.Logger) -> None:
    """Instala ganchos globais para capturar exceções não tratadas no log."""

    def uncaught_exception_handler(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical(
            "Exceção não tratada capturada no processo principal:",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = uncaught_exception_handler

    def threading_exception_handler(args):
        if issubclass(args.exc_type, KeyboardInterrupt):
            return
        logger.critical(
            f"Exceção não tratada capturada na thread '{args.thread.name}':",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = threading_exception_handler


def configurar_logging(
    nome_app: str = "app",
    nivel: int = logging.INFO,
    diretorio_logs: Optional[Path] = None,
) -> logging.Logger:
    """
    Configura o sistema de logging com saída no console e arquivo rotacionado em disco.

    :param nome_app: Nome identificador do aplicativo (ex: 'autoatendimento', 'painel').
    :param nivel: Nível mínimo de criticidade a ser capturado (default: logging.INFO).
    :param diretorio_logs: Diretório opcional para gravação (default: DIRETORIO_LOG).
    :return: Logger raiz configurado.
    """
    pasta_logs = diretorio_logs or DIRETORIO_LOG
    pasta_logs.mkdir(parents=True, exist_ok=True)

    caminho_arquivo_log = pasta_logs / f"{nome_app}.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(nivel)

    formatter = logging.Formatter(FORMATO_LOG_PADRAO)

    # Evita acúmulo de handlers se chamada repetidas vezes
    # Remove handlers antigos vinculados ao root logger
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    # 1. Handler de Console (Terminal / Stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(nivel)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 2. Handler de Arquivo Rotacionado em Disco
    file_handler = logging.handlers.RotatingFileHandler(
        caminho_arquivo_log,
        maxBytes=MAX_BYTES_LOG,
        backupCount=BACKUP_COUNT_LOG,
        encoding="utf-8",
    )
    file_handler.setLevel(nivel)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Instala ganchos para registrar exceções não tratadas
    _instalar_ganchos_excecao(root_logger)

    root_logger.info(
        "Logging inicializado para '%s' em disco: %s",
        nome_app,
        caminho_arquivo_log.resolve(),
    )

    return root_logger
