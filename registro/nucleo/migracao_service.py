# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/migracao_service.py (Serviço de Migração de Banco)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Serviço de migração e evolução de esquema do SQLite.
Garante atualização segura, não-destrutiva e atômica das tabelas
para suporte a soft-delete, auditoria e novas colunas.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Optional

from registro.nucleo import backup_service
from registro.nucleo.constants import DIRETORIO_CONFIG

logger = logging.getLogger(__name__)


def obter_caminho_banco_dados(caminho_db: Optional[Path] = None) -> Path:
    """Retorna o caminho padrão do banco de dados SQLite."""
    if caminho_db is not None:
        return Path(caminho_db)
    return DIRETORIO_CONFIG / "registro.db"


def verificar_necessidade_migracao(caminho_db: Optional[Path] = None) -> bool:
    """
    Verifica se o banco de dados SQLite precisa de migração estrutural
    (ex.: campos de soft delete em consumos).
    """
    db_path = obter_caminho_banco_dados(caminho_db)
    if not db_path.exists():
        return False

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # 1. Verifica tabela consumos
            cursor.execute("PRAGMA table_info(consumos)")
            colunas_consumos = {row[1] for row in cursor.fetchall()}
            if colunas_consumos:
                campos_obrigatorios = {
                    "ativo",
                    "deletado_em",
                    "deletado_por",
                    "motivo_cancelamento",
                }
                if not campos_obrigatorios.issubset(colunas_consumos):
                    return True

            # 2. Verifica índice parcial uq_consumos_estudante_sessao_ativo
            cursor.execute("PRAGMA index_list(consumos)")
            indices = {row[1] for row in cursor.fetchall()}
            if "uq_consumos_estudante_sessao_ativo" not in indices:
                return True

    except Exception as e:
        logger.error("Erro ao verificar necessidade de migração do banco: %s", e)

    return False


def executar_migracao(caminho_db: Optional[Path] = None) -> bool:
    """
    Executa a migração das tabelas no SQLite de forma atômica e com backup prévio.
    """
    db_path = obter_caminho_banco_dados(caminho_db)
    if not db_path.exists():
        return True

    # 1. Executa backup de segurança
    try:
        backup_service.criar_backup(prefixo="backup_pre_migracao")
    except Exception as e:
        logger.warning("Falha ao gerar backup pré-migração: %s", e)

    # 2. Executa operações atômicas no SQLite
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Desativa temporariamente chaves estrangeiras para manipulação segura da tabela
            cursor.execute("PRAGMA foreign_keys = OFF")

            # --- Migração Consumos ---
            cursor.execute("PRAGMA table_info(consumos)")
            colunas_consumos = {row[1] for row in cursor.fetchall()}
            cursor.execute("PRAGMA index_list(consumos)")
            indices_consumos = {row[1] for row in cursor.fetchall()}

            precisa_migrar_consumos = (
                colunas_consumos
                and (
                    "ativo" not in colunas_consumos
                    or "uq_consumos_estudante_sessao_ativo" not in indices_consumos
                )
            )

            if precisa_migrar_consumos:
                logger.info("Migrando tabela 'consumos' para modelo de auditoria...")
                cursor.execute("BEGIN TRANSACTION")

                cursor.execute(
                    """
                    CREATE TABLE consumos_migrado (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        estudante_id INTEGER NOT NULL,
                        sessao_id INTEGER NOT NULL,
                        hora_consumo VARCHAR(8) NOT NULL,
                        reserva_id INTEGER,
                        ativo BOOLEAN NOT NULL DEFAULT 1,
                        deletado_em DATETIME,
                        deletado_por VARCHAR(50),
                        motivo_cancelamento VARCHAR(200),
                        FOREIGN KEY (estudante_id) REFERENCES estudantes(id) ON DELETE RESTRICT,
                        FOREIGN KEY (sessao_id) REFERENCES sessoes(id) ON DELETE RESTRICT,
                        FOREIGN KEY (reserva_id) REFERENCES reservas(id) ON DELETE RESTRICT
                    )
                    """
                )

                # Copia registros legados
                cursor.execute(
                    """
                    INSERT INTO consumos_migrado (id, estudante_id, sessao_id, hora_consumo, reserva_id, ativo)
                    SELECT id, estudante_id, sessao_id, hora_consumo, reserva_id, 1 FROM consumos
                    """
                )

                cursor.execute("DROP TABLE consumos")
                cursor.execute("ALTER TABLE consumos_migrado RENAME TO consumos")

                # Índices
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS ix_consumos_estudante_id ON consumos(estudante_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS ix_consumos_sessao_id ON consumos(sessao_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS ix_consumos_reserva_id ON consumos(reserva_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS ix_consumos_ativo ON consumos(ativo)"
                )
                cursor.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_consumos_estudante_sessao_ativo
                    ON consumos(estudante_id, sessao_id)
                    WHERE ativo = 1
                    """
                )

            cursor.execute("PRAGMA foreign_keys = ON")
            conn.commit()

        logger.info("Migração de esquema concluída com sucesso no banco: %s", db_path)
        return True

    except Exception as e:
        logger.error("Erro durante a execução da migração do banco: %s", e)
        return False

