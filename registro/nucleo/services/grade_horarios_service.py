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
from datetime import datetime
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


def obter_dia_semana_por_data(data_str: str) -> Optional[str]:
    """Converte uma data ('DD/MM/YYYY' ou 'YYYY-MM-DD') para o dia da semana da grade."""
    texto = (data_str or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            data_dt = datetime.strptime(texto, fmt)
            return MAPA_DIAS_SEMANA.get(data_dt.weekday())
        except ValueError:
            continue
    return None


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
    except (OSError, json.JSONDecodeError, ValueError) as e:
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
    except (OSError, TypeError, ValueError) as e:
        logger.error("Erro ao salvar grade horária em %s: %s", caminho_arquivo, e)
        return False


def _hora_para_minutos(hora_str: str) -> int:
    """Converte 'HH:MM' ou 'HH:MM:SS' para quantidade total de minutos desde 00:00."""
    partes = str(hora_str).strip().split(":")
    if len(partes) < 2:
        raise ValueError(f"Formato de horário inválido: {hora_str}")
    h = int(partes[0])
    m = int(partes[1])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"Horário fora dos limites (00:00-23:59): {hora_str}")
    return h * 60 + m


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
        except (ValueError, TypeError):
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
            categorias = [c.strip() for c in cats_brutas.split(",") if c.strip()]
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


def _tem_restricao_especifica(valores: List[str]) -> bool:
    """Indica se a lista possui restrições específicas (não vazia e sem coringa '*' / 'TODAS')."""
    if not valores:
        return False
    norm = {str(v).strip().upper() for v in valores if v and str(v).strip()}
    return bool(norm) and "*" not in norm and "TODAS" not in norm


def _turmas_autorizadas_para_slot(slot: Dict[str, Any], turmas_estudante: Set[str]) -> bool:
    """Verifica se alguma turma do estudante é aceita pelo slot."""
    turmas_slot = slot.get("turmas", [])
    if not _tem_restricao_especifica(turmas_slot):
        return True
    turmas_norm = {t.strip().upper() for t in turmas_slot if t and str(t).strip()}
    est_norm = {t.strip().upper() for t in turmas_estudante if t and str(t).strip()}
    return bool(est_norm.intersection(turmas_norm))


def _categorias_autorizadas_para_slot(
    slot: Dict[str, Any], categorias_estudante: Set[str]
) -> bool:
    """Verifica se alguma categoria do estudante é aceita pelo slot."""
    categorias_slot = slot.get("categorias", [])
    if not _tem_restricao_especifica(categorias_slot):
        return True
    cats_slot_norm = {c.strip().upper() for c in categorias_slot if c and str(c).strip()}
    est_cats_norm = {c.strip().upper() for c in categorias_estudante if c and str(c).strip()}
    return bool(est_cats_norm.intersection(cats_slot_norm))


def _slot_autoriza_estudante(
    slot: Dict[str, Any],
    turmas_estudante: Set[str],
    categorias_estudante: Set[str],
) -> Tuple[bool, str]:
    """
    Avalia um slot com regra OU entre turmas e categorias quando ambos possuem restrições
    específicas; quando apenas um possui restrição (e o outro é '*' ou vazio), valida só o específico.
    Retorna `(autorizado, origem)` onde `origem` é `'turma'`, `'categoria'`, `'livre'` ou `''`.
    """
    turmas_slot = slot.get("turmas", [])
    cats_slot = slot.get("categorias", [])
    rest_turma = _tem_restricao_especifica(turmas_slot)
    rest_cat = _tem_restricao_especifica(cats_slot)

    if not rest_turma and not rest_cat:
        return True, "livre"

    turma_ok = _turmas_autorizadas_para_slot(slot, turmas_estudante) if rest_turma else False
    cat_ok = (
        _categorias_autorizadas_para_slot(slot, categorias_estudante) if rest_cat else False
    )

    if turma_ok:
        return True, "turma"
    if cat_ok:
        return True, "categoria"
    return False, ""


def validar_janela_horario(
    turmas_estudante: List[str],
    refeicao: str,
    hora_atual: Optional[str] = None,
    dia_semana: Optional[str] = None,
    categoria_estudante: Optional[str] = None,
    categorias_estudante: Optional[List[str]] = None,
    tolerancia_min: int = 5,
    caminho_grade: Optional[Path] = None,
    ignorar_horario: bool = False,
) -> Tuple[bool, str]:
    """
    Valida se o estudante (por suas turmas ou categorias) está autorizado no slot de horário atual.
    Quando `ignorar_horario=True`, ignora os limites de hora (início/fim), exigindo ainda que
    turma ou categoria esteja prevista em algum slot da refeição do dia.

    Retorna:
        Tuple[autorizado: bool, motivo_se_bloqueado: str]
    """
    grade = carregar_grade_horarios(caminho_grade)
    dia = _normalizar_chave(dia_semana or obter_dia_semana_atual())
    ref = _normalizar_chave(refeicao)

    grade_dia = grade.get(dia, {})
    slots_refeicao = grade_dia.get(ref, [])

    # Fallback / Grade Inexistente: Se não houver slots configurados para o dia e refeição,
    # a restrição horária não se aplica (validação livre por grupos da sessão).
    if not slots_refeicao:
        return True, ""

    conjunto_turmas_estudante = {t.strip() for t in turmas_estudante if t and str(t).strip()}
    conjunto_categorias_estudante: Set[str] = set()
    if categorias_estudante:
        conjunto_categorias_estudante.update(
            c.strip() for c in categorias_estudante if c and str(c).strip()
        )
    if categoria_estudante:
        for parte in str(categoria_estudante).split(","):
            p = parte.strip()
            if p and p.upper() not in ("-", "REGULAR", "N/A"):
                conjunto_categorias_estudante.add(p)

    if ignorar_horario:
        for slot in slots_refeicao:
            ok, _ = _slot_autoriza_estudante(
                slot, conjunto_turmas_estudante, conjunto_categorias_estudante
            )
            if ok:
                return True, ""
        return False, "Sua turma ou categoria não possui autorização para esta refeição hoje."

    if hora_atual is None:
        hora_atual = datetime.now().strftime("%H:%M")

    try:
        minutos_atuais = _hora_para_minutos(hora_atual)
    except (ValueError, TypeError):
        logger.warning("Formato inválido de hora: %s", hora_atual)
        return True, ""

    # 1. Procura se há um slot ativo no horário corrente (considerando tolerância)
    slot_corrente = None

    for slot in slots_refeicao:
        try:
            inicio_m = _hora_para_minutos(slot.get("inicio", "")) - tolerancia_min
            fim_m = _hora_para_minutos(slot.get("fim", "")) + tolerancia_min
        except (ValueError, TypeError) as e:
            logger.warning("Slot com horário inválido ignorado: %s", e)
            continue

        if inicio_m <= minutos_atuais <= fim_m:
            slot_corrente = slot
            ok, _ = _slot_autoriza_estudante(
                slot, conjunto_turmas_estudante, conjunto_categorias_estudante
            )
            if ok:
                return True, ""

    # 2. Se não foi autorizado, procura qual é o horário previsto para a turma ou categoria do discente
    slot_previsto = None
    origem_prevista = ""
    for slot in slots_refeicao:
        try:
            inicio_m = _hora_para_minutos(slot.get("inicio", ""))
            _hora_para_minutos(slot.get("fim", ""))
        except (ValueError, TypeError):
            continue
        ok, origem = _slot_autoriza_estudante(
            slot, conjunto_turmas_estudante, conjunto_categorias_estudante
        )
        if ok:
            if slot_previsto is None:
                slot_previsto = slot
                origem_prevista = origem
            if inicio_m >= minutos_atuais:
                slot_previsto = slot
                origem_prevista = origem
                break

    if slot_previsto:
        alvo = "categoria" if origem_prevista == "categoria" else "turma"
        return (
            False,
            f"Fora do horário da sua {alvo}. Seu horário: {slot_previsto['inicio']} às {slot_previsto['fim']}.",
        )

    # Se a turma/categoria do estudante nem sequer está prevista na grade do dia
    if slot_corrente:
        return False, "Sua turma ou categoria não possui autorização para este horário de refeição."

    return False, "Horário de refeição encerrado ou não iniciado para sua turma ou categoria."


def obter_turmas_previstas_para_refeicao(
    dia_semana: str,
    refeicao: str,
    caminho_grade: Optional[Path] = None,
    incluir_categorias: bool = False,
    turmas_disponiveis: Optional[List[str]] = None,
    categorias_disponiveis: Optional[List[str]] = None,
) -> List[str]:
    """Retorna uma lista ordenada e única de turmas (e opcionalmente categorias) previstas para o dia e refeição.

    Quando um slot não possui restrição específica (ex.: usa '*' / 'Todas' em turmas e
    categorias) e as listas de grupos cadastrados são informadas, expande o acesso livre
    para incluir todas as turmas (e categorias, se ``incluir_categorias=True``).
    """
    grade = carregar_grade_horarios(caminho_grade)
    dia = _normalizar_chave(dia_semana)
    ref = _normalizar_chave(refeicao)

    slots = grade.get(dia, {}).get(ref, [])
    grupos: Set[str] = set()
    coringas = {"*", "TODAS"}
    for s in slots:
        turmas_slot = s.get("turmas", [])
        cats_slot = s.get("categorias", [])
        rest_turma = _tem_restricao_especifica(turmas_slot)
        rest_cat = _tem_restricao_especifica(cats_slot)

        for t in turmas_slot:
            t_limpo = str(t).strip()
            if t_limpo and t_limpo.upper() not in coringas:
                grupos.add(t_limpo)
        if incluir_categorias:
            for c in cats_slot:
                c_limpo = str(c).strip()
                if c_limpo and c_limpo.upper() not in coringas:
                    grupos.add(c_limpo)

        if not rest_turma and not rest_cat:
            if turmas_disponiveis:
                grupos.update(t for t in turmas_disponiveis if t)
            if incluir_categorias and categorias_disponiveis:
                grupos.update(c for c in categorias_disponiveis if c)

    return sorted(list(grupos))
