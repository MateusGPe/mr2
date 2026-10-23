# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/backup_service.py (Serviço de Backup e Restauração)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Módulo para criação, listagem, restauração e exclusão de backups compactados (.zip)
do banco de dados SQLite e dos arquivos de configuração do sistema.
"""

import datetime as dt
import logging
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from registro.nucleo.constants import (
    DIRETORIO_APP,
    DIRETORIO_BACKUPS,
    DIRETORIO_CONFIG,
    URL_BANCO_DADOS,
)

logger = logging.getLogger(__name__)


def criar_backup(
    destino_personalizado: Optional[Union[str, Path]] = None,
    prefixo: str = "backup_registro",
) -> Path:
    """
    Cria um arquivo compactado .zip contendo todo o diretório config (banco SQLite e JSONs).
    Retorna o Path do arquivo criado.
    """
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo = f"{prefixo}_{timestamp}.zip"

    if destino_personalizado:
        pasta_destino = Path(destino_personalizado)
    else:
        pasta_destino = DIRETORIO_BACKUPS

    pasta_destino.mkdir(parents=True, exist_ok=True)
    caminho_zip = pasta_destino / nome_arquivo

    with zipfile.ZipFile(caminho_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        if DIRETORIO_CONFIG.exists():
            for item in DIRETORIO_CONFIG.glob("*"):
                if item.is_file():
                    # Não inclui arquivos temporários ou de lock
                    if item.suffix in (".tmp", ".lock"):
                        continue
                    zipf.write(item, arcname=f"config/{item.name}")

    logger.info("Backup criado com sucesso em: %s", caminho_zip)
    return caminho_zip


def listar_backups(diretorio: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Retorna a lista de backups disponíveis ordenados do mais recente para o mais antigo.
    """
    pasta = diretorio or DIRETORIO_BACKUPS
    if not pasta.exists():
        return []

    arquivos = list(pasta.glob("*.zip"))
    arquivos.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    resultado = []
    for arq in arquivos:
        try:
            stat = arq.stat()
            dt_criacao = dt.datetime.fromtimestamp(stat.st_mtime)
            tamanho_kb = round(stat.st_size / 1024, 1)
            tamanho_str = (
                f"{round(tamanho_kb / 1024, 2)} MB"
                if tamanho_kb >= 1024
                else f"{tamanho_kb} KB"
            )
            resultado.append(
                {
                    "nome": arq.name,
                    "caminho": arq,
                    "data": dt_criacao.strftime("%d/%m/%Y %H:%M:%S"),
                    "tamanho": tamanho_str,
                    "tamanho_bytes": stat.st_size,
                    "mtime": stat.st_mtime,
                }
            )
        except Exception as e:
            logger.warning("Falha ao inspecionar arquivo de backup %s: %s", arq, e)

    return resultado


def restaurar_backup(
    caminho_zip: Union[str, Path], criar_salvaguarda: bool = True
) -> Tuple[bool, str]:
    """
    Restaura um arquivo compactado de backup sobre o diretório config atual.
    Opcionalmente cria um backup de segurança prévio antes de sobrescrever.
    """
    zip_path = Path(caminho_zip)
    if not zip_path.exists():
        return False, f"Arquivo de backup não encontrado: {zip_path}"

    if not zipfile.is_zipfile(zip_path):
        return False, "O arquivo selecionado não é um arquivo ZIP válido."

    salvaguarda_path = None
    if criar_salvaguarda:
        try:
            salvaguarda_path = criar_backup(prefixo="backup_pre_restauracao")
        except Exception as e:
            logger.warning("Não foi possível gerar backup prévio de segurança: %s", e)

    try:
        # Fechar pools de conexões SQLAlchemy ativas se possível
        try:
            from sqlalchemy import create_engine

            engine = create_engine(URL_BANCO_DADOS)
            engine.dispose()
        except Exception:
            pass

        DIRETORIO_CONFIG.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zipf:
            for membro in zipf.infolist():
                if membro.is_dir():
                    continue

                # Evita vulnerabilidades de Path Traversal (Zip Slip)
                nome_limpo = Path(membro.filename).name
                if not nome_limpo:
                    continue

                destino_arquivo = DIRETORIO_CONFIG / nome_limpo
                with zipf.open(membro) as fonte, open(destino_arquivo, "wb") as destino:
                    destino.write(fonte.read())

        msg_extra = (
            f"\n(Salvaguarda prévia gerada em: {salvaguarda_path.name})"
            if salvaguarda_path
            else ""
        )
        return (
            True,
            f"Backup restaurado com sucesso a partir de '{zip_path.name}'!{msg_extra}",
        )
    except Exception as e:
        logger.error("Falha durante a restauração do backup: %s", e)
        return False, f"Erro ao restaurar backup: {e}"


def excluir_backup(caminho_zip: Union[str, Path]) -> bool:
    """Exclui permanentemente um arquivo de backup."""
    arq = Path(caminho_zip)
    if arq.exists():
        try:
            arq.unlink()
            return True
        except Exception as e:
            logger.error("Falha ao excluir backup %s: %s", arq, e)
            return False
    return False


def redefinir_banco_dados(criar_backup_previo: bool = True) -> Tuple[bool, str]:
    """
    Redefine o banco de dados SQLite local, recriando as tabelas vazias.
    Gera um backup de segurança prévio caso solicitado.
    """
    backup_criado = None
    if criar_backup_previo:
        try:
            backup_criado = criar_backup(prefixo="backup_pre_redefinicao")
        except Exception as e:
            logger.warning("Falha ao gerar backup prévio da redefinição: %s", e)

    try:
        from sqlalchemy import create_engine
        from registro.nucleo.models import Base

        engine = create_engine(URL_BANCO_DADOS)
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        engine.dispose()

        msg = "Banco de dados recriado com sucesso com tabelas limpas."
        if backup_criado:
            msg += f"\nBackup prévio salvo como: {backup_criado.name}"
        return True, msg
    except Exception as e:
        logger.error("Falha ao redefinir banco de dados: %s", e)
        return False, f"Erro ao redefinir banco de dados: {e}"
