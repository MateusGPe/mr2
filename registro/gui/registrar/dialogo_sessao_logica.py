# ----------------------------------------------------------------------------
# Arquivo: registro/gui/registrar/dialogo_sessao_logica.py (Lógica do Diálogo)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""Funções puras de ordenação, formatação e filtragem da grade de sessões."""

import datetime as dt
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from registro.gui.comum.utils import capitalizar
from registro.nucleo.services import grade_horarios_service
from registro.nucleo.utils import carregar_json, salvar_json

logger = logging.getLogger(__name__)

MAPA_NOMES_DIAS: Dict[str, str] = {
    "segunda": "Segunda-feira",
    "terca": "Terça-feira",
    "quarta": "Quarta-feira",
    "quinta": "Quinta-feira",
    "sexta": "Sexta-feira",
    "sabado": "Sábado",
    "domingo": "Domingo",
}


def ordenar_slots_grade(
    grade: Any, dia_semana: str, refeicao: str
) -> List[Dict[str, Any]]:
    """Extrai e ordena os slots de uma grade para o dia e refeição informados."""
    if not isinstance(grade, dict):
        return []
    dia_norm = grade_horarios_service._normalizar_chave(dia_semana)
    ref_norm = grade_horarios_service._normalizar_chave(refeicao)
    slots = grade.get(dia_norm, {}).get(ref_norm, [])
    if not isinstance(slots, list):
        return []
    return sorted(
        [s for s in slots if isinstance(s, dict)],
        key=lambda s: str(s.get("inicio", "99:99")),
    )


def expandir_grupos_slot(
    slot: Dict[str, Any],
    turmas_disponiveis: List[str],
    categorias_disponiveis: List[str],
) -> Set[str]:
    """Retorna os nomes de turmas/categorias autorizadas por um slot da grade."""
    turmas_slot = slot.get("turmas", [])
    cats_slot = slot.get("categorias", [])
    rest_turma = grade_horarios_service._tem_restricao_especifica(turmas_slot)
    rest_cat = grade_horarios_service._tem_restricao_especifica(cats_slot)

    grupos: Set[str] = set()
    coringas = {"*", "TODAS"}
    for t in turmas_slot:
        t_limpo = str(t).strip()
        if t_limpo and t_limpo.upper() not in coringas:
            grupos.add(t_limpo)
    for c in cats_slot:
        c_limpo = str(c).strip()
        if c_limpo and c_limpo.upper() not in coringas:
            grupos.add(c_limpo)

    if not rest_turma and not rest_cat:
        grupos.update(turmas_disponiveis)
        grupos.update(categorias_disponiveis)
    return grupos


def resumo_slot_texto(slot: Dict[str, Any]) -> str:
    """Gera descrição legível das turmas e categorias de um slot."""
    turmas_slot = [str(t).strip() for t in slot.get("turmas", []) if str(t).strip()]
    cats_slot = [str(c).strip() for c in slot.get("categorias", []) if str(c).strip()]
    rest_turma = grade_horarios_service._tem_restricao_especifica(turmas_slot)
    rest_cat = grade_horarios_service._tem_restricao_especifica(cats_slot)

    if not rest_turma and not rest_cat:
        return "Todas as turmas e categorias (*)"

    partes: List[str] = []
    if rest_turma:
        if len(turmas_slot) > 4:
            partes.append(", ".join(turmas_slot[:4]) + f" (+{len(turmas_slot) - 4})")
        else:
            partes.append(", ".join(turmas_slot))
    if rest_cat:
        partes.append("Cat: " + ", ".join(cats_slot))
    return " | ".join(partes)


def slot_esta_ativo_agora(
    slot: Dict[str, Any], agora: Optional[dt.datetime] = None
) -> bool:
    """Verifica se o horário atual está dentro do intervalo do slot."""
    try:
        ini = grade_horarios_service._hora_para_minutos(slot.get("inicio", ""))
        fim = grade_horarios_service._hora_para_minutos(slot.get("fim", ""))
        ref = agora or dt.datetime.now()
        atual_m = ref.hour * 60 + ref.minute
        return ini <= atual_m <= fim
    except (ValueError, TypeError):
        return False


def chave_ordenacao_sessao(sessao: Dict[str, Any]) -> dt.datetime:
    """Chave de ordenação para as sessões, tratando datas mal formatadas."""
    try:
        return dt.datetime.strptime(
            str(sessao.get("data", "01/01/1900"))
            + " "
            + str(sessao.get("hora", "00:00")),
            "%d/%m/%Y %H:%M",
        )
    except ValueError:
        return dt.datetime.min


def indice_refeicao_por_hora(hora_agora: Optional[dt.time] = None) -> int:
    """Retorna o índice padrão no combobox de refeição: 0=Lanche, 1=Almoço, 2=Jantar."""
    ref = hora_agora or dt.datetime.now().time()
    if dt.time(17, 30) <= ref <= dt.time(21, 30):
        return 2
    if dt.time(11, 0) <= ref <= dt.time(14, 0):
        return 1
    return 0


def extrair_grupos_reservas(reservas: List[Dict[str, Any]]) -> Set[str]:
    """Extrai o conjunto de turmas e categorias presentes nas reservas."""
    grupos: Set[str] = set()
    for r in reservas:
        if not isinstance(r, dict):
            continue
        turma_str = str(r.get("turma_estudante", "") or "")
        for parte in turma_str.split(","):
            t = parte.strip()
            if t and t != "N/A":
                grupos.add(t)
        for cat in r.get("categorias", []) or []:
            c = str(cat).strip()
            if c:
                grupos.add(c)
    return grupos


def carregar_opcoes_lanche_arquivo(
    caminho: Path, padrao: List[str]
) -> Tuple[Set[str], List[str]]:
    """Carrega opções de lanche de JSON, criando padrão quando ausente ou inválido."""
    try:
        opcoes = carregar_json(str(caminho))
        if not isinstance(opcoes, list) or not all(isinstance(s, str) for s in opcoes):
            raise TypeError("Conteúdo do JSON de lanches é inválido.")
        return set(opcoes) or set(padrao), sorted(opcoes) or padrao
    except (FileNotFoundError, TypeError) as e:
        logger.warning(
            "Arquivo de lanches não encontrado ou inválido: %s. Usando padrão.", e
        )
        salvar_json(str(caminho), padrao)
        return set(padrao), padrao
    except OSError as e:
        logger.exception("Erro ao carregar lanches de '%s': %s", caminho, e)
        return set(), [f"Erro ao carregar {caminho.name}"]


def formatar_linhas_sessoes(sessoes: List[Dict[str, Any]]) -> List[Tuple]:
    """Ordena e formata sessões para exibição na Treeview."""
    sessoes_ordenadas = sorted(sessoes, key=chave_ordenacao_sessao, reverse=True)
    linhas: List[Tuple] = []
    for s in sessoes_ordenadas:
        grupos = s.get("grupos") or []
        if len(grupos) > 3:
            resumo_grupos = f"{len(grupos)} ({', '.join(grupos[:3])}...)"
        elif grupos:
            resumo_grupos = ", ".join(grupos)
        else:
            resumo_grupos = "-"

        linhas.append(
            (
                s.get("id"),
                s.get("data"),
                s.get("hora"),
                capitalizar(s.get("refeicao", "")),
                s.get("item_servido") or "-",
                resumo_grupos,
            )
        )
    return linhas


def filtrar_linhas_sessoes(linhas: List[Tuple], termo: str) -> List[Tuple]:
    """Filtra linhas formatadas de sessões por termo de busca."""
    termo_limpo = termo.strip().lower()
    if not termo_limpo:
        return list(linhas)
    return [
        linha
        for linha in linhas
        if any(termo_limpo in str(col).lower() for col in linha)
    ]
