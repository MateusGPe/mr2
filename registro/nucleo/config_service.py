# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/config_service.py (Serviço de Configurações e Diagnóstico)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Serviço central para gerenciamento de configurações do sistema,
segurança e PIN do operador, integração Google Sheets e diagnóstico de status.
"""

import hashlib
import json
import logging
import re
import secrets
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from registro.nucleo.constants import (
    CAMINHO_CREDENCIAS,
    CAMINHO_JSON_LANCHES,
    CAMINHO_JSON_PRESETS_TURMAS,
    CAMINHO_SETTINGS,
    CAMINHO_TOKEN,
    DIRETORIO_BACKUPS,
    DIRETORIO_CONFIG,
    JSON_ID_PLANILHA,
)

logger = logging.getLogger(__name__)

CONFIG_PADRAO: Dict[str, Any] = {
    "pin_hash": "",
    "pin_salt": "",
    "totem": {
        "fullscreen": False,
        "camera_on_start": True,
        "require_pin_to_exit": True,
        "feedback_delay_ms": 1500,
    },
}


def _carregar_json_seguro(caminho: Path, padrao: Any) -> Any:
    """Carrega dados JSON com fallback em caso de inexistência ou arquivo corrompido."""
    if not caminho.exists():
        return padrao
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Falha ao ler %s: %s. Utilizando padrão.", caminho, e)
        return padrao


def _salvar_json_atomico(caminho: Path, dados: Any) -> None:
    """Salva dados em formato JSON garantindo a criação de diretórios pai."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temp_path = caminho.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
    temp_path.replace(caminho)


def obter_configuracoes() -> Dict[str, Any]:
    """Retorna o dicionário de configurações gerais (settings.json)."""
    dados = _carregar_json_seguro(CAMINHO_SETTINGS, {})
    # Mescla recursiva básica com valores padrão
    resultado = dict(CONFIG_PADRAO)
    resultado.update(dados)
    totem_config = dict(CONFIG_PADRAO["totem"])
    if isinstance(dados.get("totem"), dict):
        totem_config.update(dados["totem"])
    resultado["totem"] = totem_config
    return resultado


def salvar_configuracoes(dados: Dict[str, Any]) -> None:
    """Salva o dicionário completo de configurações."""
    _salvar_json_atomico(CAMINHO_SETTINGS, dados)


def obter_config_totem() -> Dict[str, Any]:
    """Retorna as preferências configuradas para o Totem."""
    return obter_configuracoes().get("totem", CONFIG_PADRAO["totem"])


def atualizar_config_totem(chave: str, valor: Any) -> None:
    """Atualiza uma chave específica nas opções do Totem."""
    config = obter_configuracoes()
    if "totem" not in config or not isinstance(config["totem"], dict):
        config["totem"] = dict(CONFIG_PADRAO["totem"])
    config["totem"][chave] = valor
    salvar_configuracoes(config)


# ----------------------------------------------------------------------------
# Gerenciamento de PIN de Operador (Segurança)
# ----------------------------------------------------------------------------


def _hash_pin(pin: str, salt: str) -> str:
    """Gera hash PBKDF2 HMAC SHA-256 do PIN com salt."""
    return hashlib.pbkdf2_hmac(
        "sha256", pin.encode("utf-8"), salt.encode("utf-8"), 100_000
    ).hex()


def definir_pin(pin: str) -> None:
    """
    Define um novo PIN de operador. Se a string for vazia, remove o PIN.
    """
    pin_limpo = pin.strip()
    config = obter_configuracoes()
    if not pin_limpo:
        config["pin_hash"] = ""
        config["pin_salt"] = ""
    else:
        salt = secrets.token_hex(16)
        config["pin_hash"] = _hash_pin(pin_limpo, salt)
        config["pin_salt"] = salt
    salvar_configuracoes(config)


def verificar_pin(pin: str) -> bool:
    """
    Verifica se o PIN fornecido coincide com o cadastrado.
    Caso não haja PIN configurado no sistema, retorna True.
    """
    config = obter_configuracoes()
    pin_hash = config.get("pin_hash", "")
    pin_salt = config.get("pin_salt", "")

    if not pin_hash or not pin_salt:
        return True  # Sem PIN configurado -> livre acesso

    pin_teste = _hash_pin(pin.strip(), pin_salt)
    return secrets.compare_digest(pin_hash, pin_teste)


def tem_pin_configurado() -> bool:
    """Informa se um PIN de operador está atualmente ativo no sistema."""
    config = obter_configuracoes()
    return bool(config.get("pin_hash") and config.get("pin_salt"))


def remover_pin() -> None:
    """Remove o PIN de segurança ativo."""
    definir_pin("")


# ----------------------------------------------------------------------------
# Google Cloud & Google Sheets
# ----------------------------------------------------------------------------


def extrair_id_planilha(texto: str) -> str:
    """
    Extrai o ID da planilha do Google a partir de uma URL completa ou retorna o próprio ID limpo.
    Exemplo: https://docs.google.com/spreadsheets/d/1x78c5OyyzvwQB-El0PjnfOwLYKa4M-MlJVNEWaG_3YQ/edit -> 1x78c5...
    """
    texto = texto.strip()
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", texto)
    if match:
        return match.group(1)
    return texto


def obter_id_planilha() -> Optional[str]:
    """Retorna o ID configurado da planilha Google a partir de spreadsheet.json."""
    dados = _carregar_json_seguro(JSON_ID_PLANILHA, {})
    return dados.get("key") or dados.get("spreadsheet_id")


def salvar_id_planilha(texto_ou_url: str) -> str:
    """
    Processa e salva o ID da planilha no arquivo spreadsheet.json.
    Retorna o ID extraído.
    """
    planilha_id = extrair_id_planilha(texto_ou_url)
    _salvar_json_atomico(
        JSON_ID_PLANILHA,
        {
            "key": planilha_id,
            "spreadsheet_id": planilha_id,
        },
    )
    return planilha_id


def salvar_arquivo_credenciais(caminho_origem: Union[str, Path]) -> bool:
    """
    Copia um arquivo JSON de credenciais baixado do Google Cloud para config/credentials.json.
    """
    origem = Path(caminho_origem)
    if not origem.exists():
        return False
    CAMINHO_CREDENCIAS.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origem, CAMINHO_CREDENCIAS)
    return True


def limpar_token() -> bool:
    """Remove o arquivo token.json para forçar nova autenticação."""
    if CAMINHO_TOKEN.exists():
        try:
            CAMINHO_TOKEN.unlink()
            return True
        except Exception as e:
            logger.error("Erro ao remover token.json: %s", e)
            return False
    return True


def testar_conexao_google_sheets() -> Tuple[bool, str]:
    """
    Testa a conexão e autenticação com a planilha do Google Sheets.
    Retorna (sucesso, mensagem descritiva).
    """
    if not CAMINHO_CREDENCIAS.exists():
        return (
            False,
            "Arquivo 'credentials.json' não encontrado na pasta config.",
        )

    sheet_id = obter_id_planilha()
    if not sheet_id:
        return (
            False,
            "ID da planilha não configurado em 'spreadsheet.json'.",
        )

    try:
        from registro.nucleo.google_api_service import GoogleSheetsService

        service = GoogleSheetsService(sheet_id)
        titulo = service.planilha.title
        return (
            True,
            f"Conexão estabelecida com sucesso!\nPlanilha: '{titulo}'",
        )
    except Exception as e:
        return (False, f"Falha ao conectar à API do Google Sheets:\n{e}")


# ----------------------------------------------------------------------------
# Lanches e Presets de Turmas
# ----------------------------------------------------------------------------


def obter_lanches() -> List[str]:
    """Retorna a lista de itens de refeição/lanches cadastrados."""
    return _carregar_json_seguro(CAMINHO_JSON_LANCHES, [])


def salvar_lanches(lanches: List[str]) -> None:
    """Salva a lista atualizada de itens de refeição/lanches."""
    _salvar_json_atomico(CAMINHO_JSON_LANCHES, lanches)


def obter_presets_turmas() -> Dict[str, Any]:
    """Retorna o dicionário de predefinições de turmas."""
    return _carregar_json_seguro(
        CAMINHO_JSON_PRESETS_TURMAS,
        {
            "manha": {"seg": [], "ter": [], "qua": [], "qui": [], "sex": []},
            "tarde": {"seg": [], "ter": [], "qua": [], "qui": [], "sex": []},
        },
    )


def salvar_presets_turmas(presets: Dict[str, Any]) -> None:
    """Salva o dicionário de predefinições de turmas."""
    _salvar_json_atomico(CAMINHO_JSON_PRESETS_TURMAS, presets)


# ----------------------------------------------------------------------------
# Diagnóstico de Status Geral do Sistema
# ----------------------------------------------------------------------------


def obter_status_sistema() -> Dict[str, Any]:
    """
    Coleta dados de integridade e configuração para o checklist inicial.
    """
    caminho_db = DIRETORIO_CONFIG / "registro.db"
    db_existe = caminho_db.exists()
    db_tamanho_kb = round(caminho_db.stat().st_size / 1024, 1) if db_existe else 0.0

    total_alunos = 0
    total_consumos = 0
    if db_existe:
        try:
            from registro.nucleo.facade import FachadaRegistro

            fachada = FachadaRegistro()
            total_alunos = len(fachada.obter_todos_estudantes())
            # Consulta contagem simples se disponível
            total_consumos = len(fachada.obter_todos_consumos())
        except Exception:
            pass

    credenciais_existem = CAMINHO_CREDENCIAS.exists()
    token_existe = CAMINHO_TOKEN.exists()
    planilha_id = obter_id_planilha()
    tem_pin = tem_pin_configurado()
    totem_cfg = obter_config_totem()

    # Backups
    backups = list(DIRETORIO_BACKUPS.glob("backup_*.zip")) if DIRETORIO_BACKUPS.exists() else []
    ultimo_backup_str = None
    if backups:
        backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        mais_recente = backups[0]
        import datetime as _dt

        dt_mod = _dt.datetime.fromtimestamp(mais_recente.stat().st_mtime)
        ultimo_backup_str = dt_mod.strftime("%d/%m/%Y %H:%M")

    return {
        "banco_dados": {
            "existe": db_existe,
            "caminho": str(caminho_db),
            "tamanho_kb": db_tamanho_kb,
            "total_alunos": total_alunos,
            "total_consumos": total_consumos,
        },
        "google_cloud": {
            "credenciais_ok": credenciais_existem,
            "token_ok": token_existe,
            "planilha_id": planilha_id,
        },
        "totem": {
            "pin_ativo": tem_pin,
            "fullscreen": totem_cfg.get("fullscreen", False),
            "camera_on_start": totem_cfg.get("camera_on_start", True),
            "require_pin_to_exit": totem_cfg.get("require_pin_to_exit", True),
        },
        "backup": {
            "total_backups": len(backups),
            "ultimo_backup": ultimo_backup_str,
        },
    }
