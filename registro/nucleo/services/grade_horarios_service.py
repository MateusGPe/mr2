# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/services/grade_horarios_service.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Serviço de gerenciamento da grade horária semanal e validação de janelas de
escalonamento físico de acesso ao refeitório.
"""

import json
import logging
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from registro.nucleo.constants import CAMINHO_GRADE_HORARIOS

logger = logging.getLogger(__name__)

MAPA_DIAS_SEMANA = {
    0: "segunda",
    1: "terca",
    2: "quarta",
    3: "quinta",
    4: "sexta",
    5: "sabado",
    6: "domingo",
}

GRADE_PADRAO: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
    "segunda": {"almoco": [], "jantar": [], "lanche": []},
    "terca": {"almoco": [], "jantar": [], "lanche": []},
    "quarta": {"almoco": [], "jantar": [], "lanche": []},
    "quinta": {"almoco": [], "jantar": [], "lanche": []},
    "sexta": {"almoco": [], "jantar": [], "lanche": []},
    "sabado": {"almoco": [], "jantar": [], "lanche": []},
    "domingo": {"almoco": [], "jantar": [], "lanche": []},
}


def _normalizar_chave(texto: str) -> str:
    """Remove acentos, espaços e converte para minúsculas."""
    texto_norm = unicodedata.normalize("NFKD", texto)
    sem_acentos = "".join(c for c in texto_norm if not unicodedata.combining(c))
    return sem_acentos.strip().lower()


def obter_dia_semana_atual() -> str:
    """Retorna o dia da semana atual no padrão do json ('segunda', 'terca', etc.)."""
    return MAPA_DIAS_SEMANA.get(datetime.now().weekday(), "segunda")


def carregar_grade_horarios(
    caminho: Optional[Path] = None,
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """Carrega o arquivo JSON da grade horária semanal ou cria um modelo padrão caso não exista."""
    caminho_arquivo = caminho or CAMINHO_GRADE_HORARIOS
    caminho_arquivo = Path(caminho_arquivo)

    if not caminho_arquivo.exists():
        salvar_grade_horarios(GRADE_PADRAO, caminho_arquivo)
        return GRADE_PADRAO

    try:
        with open(caminho_arquivo, "r", encoding="utf-8") as f:
            grade = json.load(f)
            return grade
    except Exception as e:
        logger.warning(
            "Erro ao ler grade horária de %s: %s. Utilizando padrão.", caminho_arquivo, e
        )
        return GRADE_PADRAO


def salvar_grade_horarios(
    grade: Dict[str, Any], caminho: Optional[Path] = None
) -> bool:
    """Salva a grade semanal de horários no caminho indicado."""
    caminho_arquivo = caminho or CAMINHO_GRADE_HORARIOS
    caminho_arquivo = Path(caminho_arquivo)
    try:
        caminho_arquivo.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho_arquivo, "w", encoding="utf-8") as f:
            json.dump(grade, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error("Erro ao salvar grade horária em %s: %s", caminho_arquivo, e)
        return False


def _hora_para_minutos(hora_str: str) -> int:
    """Converte 'HH:MM' ou 'HH:MM:SS' para quantidade total de minutos desde 00:00."""
    partes = str(hora_str).strip().split(":")
    return int(partes[0]) * 60 + int(partes[1])


MAPA_NORMALIZACAO_DIAS = {
    "seg": "segunda",
    "segunda": "segunda",
    "segunda-feira": "segunda",
    "ter": "terca",
    "terca": "terca",
    "terça": "terca",
    "terca-feira": "terca",
    "terça-feira": "terca",
    "qua": "quarta",
    "quarta": "quarta",
    "quarta-feira": "quarta",
    "qui": "quinta",
    "quinta": "quinta",
    "quinta-feira": "quinta",
    "sex": "sexta",
    "sexta": "sexta",
    "sexta-feira": "sexta",
    "sab": "sabado",
    "sabado": "sabado",
    "sábado": "sabado",
    "dom": "domingo",
    "domingo": "domingo",
}

MAPA_NORMALIZACAO_REFEICOES = {
    "almoco": "almoco",
    "almoço": "almoco",
    "jantar": "jantar",
    "lanche": "lanche",
}


def converter_linhas_configuracao_para_grade(
    linhas: List[List[str]],
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """
    Converte as linhas brutas da aba 'Configuração' do Google Sheets para o
    dicionário estruturado da grade horária semanal.
    """
    grade: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
        dia: {"almoco": [], "jantar": [], "lanche": []}
        for dia in GRADE_PADRAO
    }

    if not linhas:
        return grade

    for row in linhas:
        if not row or not any(str(c).strip() for c in row):
            continue

        valores = [str(c).strip() for c in row]
        primeira_celula = _normalizar_chave(valores[0])
        # Pula cabeçalho
        if primeira_celula in ("dia", "data", "dia da semana"):
            continue

        dia_bruto = _normalizar_chave(valores[0])
        dia_norm = MAPA_NORMALIZACAO_DIAS.get(dia_bruto)
        if not dia_norm and len(valores) > 0:
            for k, v in MAPA_NORMALIZACAO_DIAS.items():
                if k in dia_bruto:
                    dia_norm = v
                    break
        if not dia_norm or dia_norm not in grade:
            continue

        ref_bruta = _normalizar_chave(valores[1]) if len(valores) > 1 else ""
        ref_norm = MAPA_NORMALIZACAO_REFEICOES.get(ref_bruta)
        if not ref_norm and len(valores) > 1:
            for k, v in MAPA_NORMALIZACAO_REFEICOES.items():
                if k in ref_bruta:
                    ref_norm = v
                    break
        if not ref_norm or ref_norm not in grade[dia_norm]:
            continue

        inicio = valores[2] if len(valores) > 2 else ""
        fim = valores[3] if len(valores) > 3 else ""
        if not inicio or not fim:
            continue

        # Formata horas garantindo HH:MM
        try:
            _hora_para_minutos(inicio)
            _hora_para_minutos(fim)
        except Exception:
            logger.warning("Linha com horário inválido na configuração: %s - %s", inicio, fim)
            continue

        turmas_brutas = valores[4] if len(valores) > 4 else ""
        turmas: List[str] = []
        if turmas_brutas and turmas_brutas not in ("*", "Todas", "TODAS", "todas"):
            turmas = [t.strip() for t in turmas_brutas.split(",") if t.strip()]
        elif turmas_brutas in ("*", "Todas", "TODAS", "todas"):
            turmas = ["*"]

        cats_brutas = valores[5] if len(valores) > 5 else ""
        categorias: List[str] = []
        if cats_brutas and cats_brutas not in ("*", "Todas", "TODAS", "todas"):
            categorias = [c.strip().upper() for c in cats_brutas.split(",") if c.strip()]
        elif cats_brutas in ("*", "Todas", "TODAS", "todas"):
            categorias = ["*"]

        slot = {
            "inicio": inicio,
            "fim": fim,
            "turmas": turmas,
            "categorias": categorias,
        }
        grade[dia_norm][ref_norm].append(slot)

    return grade


def _turmas_autorizadas_para_slot(slot: Dict[str, Any], turmas_estudante: Set[str]) -> bool:
    """Verifica se alguma turma do estudante é aceita pelo slot."""
    turmas_slot = slot.get("turmas", [])
    if not turmas_slot or "*" in turmas_slot or "TODAS" in [t.upper() for t in turmas_slot]:
        return True
    return bool(turmas_estudante.intersection(set(turmas_slot)))


def _categoria_autorizada_para_slot(slot: Dict[str, Any], categoria: Optional[str]) -> bool:
    """Verifica se a categoria do estudante é aceita pelo slot."""
    categorias_slot = slot.get("categorias", [])
    if not categorias_slot or "*" in categorias_slot or "TODAS" in [c.upper() for c in categorias_slot]:
        return True
    cat_estudante = (categoria or "REGULAR").strip().upper()
    cats_normalizadas = [c.strip().upper() for c in categorias_slot]
    return cat_estudante in cats_normalizadas


def validar_janela_horario(
    turmas_estudante: List[str],
    refeicao: str,
    hora_atual: Optional[str] = None,
    dia_semana: Optional[str] = None,
    categoria_estudante: Optional[str] = None,
    tolerancia_min: int = 5,
    caminho_grade: Optional[Path] = None,
) -> Tuple[bool, str]:
    """
    Valida se alguma das turmas e a categoria do estudante estão autorizadas no slot de horário atual.

    Retorna:
        Tuple[autorizado: bool, motivo_se_bloqueado: str]
    """
    grade = carregar_grade_horarios(caminho_grade)
    dia = _normalizar_chave(dia_semana or obter_dia_semana_atual())
    ref = _normalizar_chave(refeicao)

    grade_dia = grade.get(dia, {})
    slots_refeicao = grade_dia.get(ref, [])

    # Fallback / Grade Inexistente: Se não houver slots configurados para o dia e refeição,
    # a restrição horária não se aplica (validação livre por turmas da sessão).
    if not slots_refeicao:
        return True, ""

    if hora_atual is None:
        hora_atual = datetime.now().strftime("%H:%M")

    try:
        minutos_atuais = _hora_para_minutos(hora_atual)
    except Exception:
        logger.warning("Formato inválido de hora: %s", hora_atual)
        return True, ""

    conjunto_turmas_estudante = set(turmas_estudante)
    cat_estudante = (categoria_estudante or "REGULAR").strip().upper()

    # 1. Procura se há um slot ativo no horário corrente (considerando tolerância)
    slot_corrente = None
    bloqueio_por_categoria = False
    categorias_permitidas_slot: List[str] = []

    for slot in slots_refeicao:
        inicio_m = _hora_para_minutos(slot["inicio"]) - tolerancia_min
        fim_m = _hora_para_minutos(slot["fim"]) + tolerancia_min
        if inicio_m <= minutos_atuais <= fim_m:
            slot_corrente = slot
            turma_ok = _turmas_autorizadas_para_slot(slot, conjunto_turmas_estudante)
            cat_ok = _categoria_autorizada_para_slot(slot, cat_estudante)

            if turma_ok and cat_ok:
                return True, ""
            if turma_ok and not cat_ok:
                bloqueio_por_categoria = True
                categorias_permitidas_slot = slot.get("categorias", [])

    if bloqueio_por_categoria:
        permitidas_str = ", ".join(categorias_permitidas_slot) if categorias_permitidas_slot else "Outras"
        return (
            False,
            f"Categoria '{cat_estudante}' não permitida neste horário. Permitidas: {permitidas_str}.",
        )

    # 2. Se não foi autorizado, procura qual é o horário previsto para a turma e categoria do discente
    slot_turma_previsto = None
    for slot in slots_refeicao:
        turma_ok = _turmas_autorizadas_para_slot(slot, conjunto_turmas_estudante)
        cat_ok = _categoria_autorizada_para_slot(slot, cat_estudante)
        if turma_ok and cat_ok:
            slot_turma_previsto = slot
            break

    if slot_turma_previsto:
        return (
            False,
            f"Fora do horário da sua turma. Seu horário: {slot_turma_previsto['inicio']} às {slot_turma_previsto['fim']}.",
        )

    # Se a turma do estudante nem sequer está prevista na grade do dia
    if slot_corrente:
        return False, "Sua turma ou categoria não possui autorização para este horário de refeição."

    return False, "Horário de refeição encerrado ou não iniciado para sua turma."


def obter_turmas_previstas_para_refeicao(
    dia_semana: str,
    refeicao: str,
    caminho_grade: Optional[Path] = None,
) -> List[str]:
    """Retorna uma lista ordenada e única de turmas previstas para aquele dia e refeição."""
    grade = carregar_grade_horarios(caminho_grade)
    dia = _normalizar_chave(dia_semana)
    ref = _normalizar_chave(refeicao)

    slots = grade.get(dia, {}).get(ref, [])
    turmas: Set[str] = set()
    for s in slots:
        for t in s.get("turmas", []):
            if t not in ("*", "Todas", "TODAS", "todas"):
                turmas.add(t)

    return sorted(list(turmas))
