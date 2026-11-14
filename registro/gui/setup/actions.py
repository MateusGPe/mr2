# ----------------------------------------------------------------------------
# Arquivo: registro/gui/setup/actions.py (Ações e Lógica Pura do Setup)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""Funções puras e ações de sistema da Central de Configurações (sem Tkinter)."""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from registro.nucleo.constants import DIRETORIO_APP
from registro.nucleo.services import grade_horarios_service

logger = logging.getLogger(__name__)


def validar_e_montar_regra_grade(
    inicio: str, fim: str, turmas_raw: str, cats_raw: str
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Valida horários HH:MM e monta o dicionário de regra da grade."""
    ini = inicio.strip()
    fim_limpo = fim.strip()
    if not ini or not fim_limpo:
        return False, "Horários de início e fim são obrigatórios.", None

    try:
        grade_horarios_service._hora_para_minutos(ini)
        grade_horarios_service._hora_para_minutos(fim_limpo)
    except ValueError as e:
        return False, f"Formato de horário inválido: {e}", None

    coringas = {"*", "TODAS"}
    turmas = (
        [t.strip() for t in turmas_raw.split(",") if t.strip()]
        if turmas_raw.strip() and turmas_raw.strip().upper() not in coringas
        else ["*"]
    )
    cats = (
        [c.strip() for c in cats_raw.split(",") if c.strip()]
        if cats_raw.strip() and cats_raw.strip().upper() not in coringas
        else ["*"]
    )
    return (
        True,
        "",
        {
            "inicio": ini,
            "fim": fim_limpo,
            "turmas": turmas,
            "categorias": cats,
        },
    )


def adicionar_regra_grade(
    grade: Dict[str, Any], dia_chave: str, ref_chave: str, regra: Dict[str, Any]
) -> None:
    """Insere uma regra na estrutura da grade para dia e refeição."""
    if dia_chave not in grade:
        grade[dia_chave] = {"almoco": [], "jantar": [], "lanche": []}
    if ref_chave not in grade[dia_chave]:
        grade[dia_chave][ref_chave] = []
    grade[dia_chave][ref_chave].append(regra)


def remover_regra_grade(
    grade: Dict[str, Any], dia_chave: str, ref_chave: str, idx: int
) -> bool:
    """Remove a regra no índice informado; retorna True se removida."""
    regras = grade.get(dia_chave, {}).get(ref_chave, [])
    if 0 <= idx < len(regras):
        regras.pop(idx)
        return True
    return False


def criar_atalhos_desktop(
    desktop_dir: Optional[Path] = None,
    app_dir: Optional[Path] = None,
    executable: Optional[str] = None,
    frozen: Optional[bool] = None,
) -> Tuple[bool, str]:
    """Cria scripts de inicialização rápida na Área de Trabalho do Windows."""
    try:
        if desktop_dir is not None:
            desktop = desktop_dir
        else:
            desktop = Path.home() / "Desktop"
            if not desktop.exists():
                desktop = Path.home() / "Área de Trabalho"

        eh_frozen = getattr(sys, "frozen", False) if frozen is None else frozen
        if eh_frozen:
            exe_path = Path(executable or sys.executable).resolve()
            atalho_totem = f'@echo off\nstart "" "{exe_path}" --auto\n'
            atalho_reg = f'@echo off\nstart "" "{exe_path}" --reg\n'
            atalho_painel = f'@echo off\nstart "" "{exe_path}" --painel\n'
        else:
            dir_proj = (app_dir or DIRETORIO_APP).resolve()
            atalho_totem = (
                f'@echo off\ncd /d "{dir_proj}"\ncall uv run autoatendimento\n'
            )
            atalho_reg = f'@echo off\ncd /d "{dir_proj}"\ncall uv run registrar\n'
            atalho_painel = f'@echo off\ncd /d "{dir_proj}"\ncall uv run painel\n'

        (desktop / "Totem Autoatendimento.bat").write_text(
            atalho_totem, encoding="utf-8"
        )
        (desktop / "Registro de Refeicoes.bat").write_text(atalho_reg, encoding="utf-8")
        (desktop / "Painel Administrativo.bat").write_text(
            atalho_painel, encoding="utf-8"
        )
        return True, "Atalhos gerados com sucesso na sua Área de Trabalho!"
    except OSError as e:
        logger.error("Não foi possível criar os atalhos: %s", e)
        return False, f"Não foi possível criar os atalhos:\n{e}"


def formatar_status_cards(status: Dict[str, Any]) -> Dict[str, Tuple[str, str]]:
    """Formata textos e estilos dos 4 cartões de diagnóstico do Setup."""
    db = status["banco_dados"]
    if db["existe"]:
        txt_db = (
            f"✅ Conectado ({db['tamanho_kb']} KB)\n"
            f"Estudantes: {db['total_alunos']}  |  Registros de Consumo: {db['total_consumos']}"
        )
    else:
        txt_db = "⚠️ Banco de dados local ainda não criado."

    gcp = status["google_cloud"]
    if gcp["credenciais_ok"]:
        txt_gcp = "✅ credentials.json detectado"
        txt_gcp += "  |  Token ativo" if gcp["token_ok"] else "  |  Token pendente"
        lbl_cred = (
            "✅ Arquivo 'credentials.json' presente e configurado.",
            "success",
        )
    else:
        txt_gcp = "❌ credentials.json não encontrado"
        lbl_cred = (
            "⚠️ Arquivo 'credentials.json' ausente. Importe o arquivo JSON gerado no GCP.",
            "warning",
        )

    p_id = gcp["planilha_id"]
    if p_id:
        txt_sheet = f"✅ Planilha Vinculada\nID: {p_id}"
    else:
        txt_sheet = "⚠️ Nenhuma planilha vinculada em spreadsheet.json"

    tem_pin = status["totem"]["pin_ativo"]
    if tem_pin:
        txt_pin = "✅ PIN do Operador ATIVO e protegido"
        lbl_pin = ("Status: ✅ PIN de operador configurado e ativo.", "success")
    else:
        txt_pin = "⚠️ Nenhum PIN configurado (Menu e saída livres)"
        lbl_pin = (
            "Status: ⚠️ Nenhum PIN definido. O Totem opera sem restrição de acesso.",
            "warning",
        )

    return {
        "db": (txt_db, ""),
        "gcp": (txt_gcp, ""),
        "cred": lbl_cred,
        "sheet": (txt_sheet, p_id or ""),
        "pin_card": (txt_pin, ""),
        "pin_lbl": lbl_pin,
    }
