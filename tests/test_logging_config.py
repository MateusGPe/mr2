# ----------------------------------------------------------------------------
# Arquivo: tests/test_logging_config.py
# ----------------------------------------------------------------------------
"""
Testes unitários para o módulo centralizador de logging (registro.nucleo.logging_config).
"""

import logging
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from registro.nucleo.logging_config import (
    BACKUP_COUNT_LOG,
    MAX_BYTES_LOG,
    configurar_logging,
)


def test_configurar_logging_cria_diretorio_e_handlers(tmp_path: Path):
    pasta_logs = tmp_path / "test_logs"
    logger = configurar_logging("test_app", nivel=logging.DEBUG, diretorio_logs=pasta_logs)

    assert pasta_logs.exists()
    arquivo_esperado = pasta_logs / "test_app.log"
    assert arquivo_esperado.exists()

    handlers = logger.handlers
    # Deve conter pelo menos Console (StreamHandler) e Arquivo (RotatingFileHandler)
    stream_handlers = [h for h in handlers if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)]
    file_handlers = [h for h in handlers if isinstance(h, logging.handlers.RotatingFileHandler)]

    assert len(stream_handlers) >= 1
    assert len(file_handlers) >= 1

    file_handler = file_handlers[0]
    assert file_handler.maxBytes == MAX_BYTES_LOG
    assert file_handler.backupCount == BACKUP_COUNT_LOG
    assert file_handler.encoding == "utf-8"

    # Teste de escrita no log
    mensagem_teste = "Mensagem de teste em UTF-8 com acentuação: Refeição válida!"
    logger.info(mensagem_teste)

    # Forçar flush
    for h in handlers:
        h.flush()

    conteudo = arquivo_esperado.read_text(encoding="utf-8")
    assert mensagem_teste in conteudo
    assert "INFO" in conteudo
    assert "test_app" in conteudo or "root" in conteudo


def test_configurar_logging_chamadas_multiplas(tmp_path: Path):
    pasta_logs = tmp_path / "logs_multiplos"
    # Chamada para primeiro app
    configurar_logging("app1", diretorio_logs=pasta_logs)
    # Chamada para segundo app (substitui handlers)
    logger2 = configurar_logging("app2", diretorio_logs=pasta_logs)

    assert (pasta_logs / "app1.log").exists()
    assert (pasta_logs / "app2.log").exists()

    logger2.info("Mensagem apenas para app2")
    for h in logger2.handlers:
        h.flush()

    assert "Mensagem apenas para app2" in (pasta_logs / "app2.log").read_text(encoding="utf-8")


def test_gancho_excecao_global(tmp_path: Path, monkeypatch):
    pasta_logs = tmp_path / "logs_excecao"
    logger = configurar_logging("crash_app", diretorio_logs=pasta_logs)

    # Simula chamada do sys.excepthook
    hook = sys.excepthook
    assert callable(hook)

    try:
        raise ValueError("Simulação de erro fatal não tratado")
    except ValueError:
        exc_type, exc_val, exc_tb = sys.exc_info()
        hook(exc_type, exc_val, exc_tb)

    for h in logger.handlers:
        h.flush()

    conteudo = (pasta_logs / "crash_app.log").read_text(encoding="utf-8")
    assert "CRITICAL" in conteudo
    assert "Simulação de erro fatal não tratado" in conteudo
    assert "ValueError" in conteudo
