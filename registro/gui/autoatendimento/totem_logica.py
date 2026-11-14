# ----------------------------------------------------------------------------
# Arquivo: registro/gui/autoatendimento/totem_logica.py (Lógica Pura do Totem)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""Funções puras de formatação, matching fuzzy e formatação de sessão para o Totem."""

import re
from typing import Any, Dict, List, Tuple

from fuzzywuzzy import fuzz


def formatar_matricula(valor: Any) -> str:
    """Padroniza a matrícula para o formato IQ30XXXXX."""
    texto = str(valor).upper()
    numeros_e_x = re.findall(r"[0-9X]", texto)
    sufixo = "".join(numeros_e_x)[-5:]
    sufixo_formatado = sufixo.zfill(5)
    return f"IQ30{sufixo_formatado}"


def filtrar_correspondencias_nome(
    candidatos: Any, nome_busca: str, score_minimo: int
) -> List[Dict[str, Any]]:
    """Ordena candidatos por similaridade parcial de nome acima do limiar."""
    correspondencias: List[Dict[str, Any]] = []
    nome_lower = nome_busca.lower()
    for estudante in candidatos:
        nome_estudante = estudante.get("nome", "").lower()
        if not nome_estudante:
            continue
        score = fuzz.partial_ratio(nome_lower, nome_estudante)
        if score >= score_minimo:
            estudante["score"] = score
            correspondencias.append(estudante)
    correspondencias.sort(key=lambda x: -x["score"])
    return correspondencias


def resolver_match_nome(
    correspondencias: List[Dict[str, Any]], nome_busca: str
) -> Tuple[bool, str, Dict[str, Any]]:
    """Valida unicidade e prontuário do melhor match fuzzy encontrado."""
    if not correspondencias:
        return (
            False,
            "Aluno não encontrado",
            {"nome": nome_busca, "turma": "Não Encontrado"},
        )

    melhor_match = correspondencias[0]

    if len(correspondencias) > 1 and (
        melhor_match["score"] < 98
        or (melhor_match["score"] - correspondencias[1]["score"]) < 10
    ):
        return (
            False,
            "Múltiplos resultados. Seja mais específico.",
            {"nome": nome_busca, "turma": "Busca Ambígua"},
        )

    prontuario_encontrado = melhor_match.get("pront")
    if not prontuario_encontrado:
        return (
            False,
            "Prontuário não encontrado para o nome.",
            {"nome": nome_busca, "turma": "Erro Interno"},
        )

    return True, str(prontuario_encontrado), melhor_match


def formatar_resumo_sessao_topo(
    detalhes: Dict[str, Any],
    qtd_exc: int,
    ignorar_horario_grade: bool,
) -> Tuple[str, str]:
    """Formata os textos de resumo da sessão ativa para o cabeçalho e painel lateral."""
    refeicao = str(detalhes.get("refeicao", "Sessão")).capitalize()
    hora = str(detalhes.get("hora", ""))
    data = str(detalhes.get("data", ""))
    item = detalhes.get("item_servido") or ""
    texto_item = f" • {item}" if item else ""
    grupos = list(detalhes.get("grupos", []))
    qtd_grupos = len(grupos)

    if qtd_grupos and qtd_exc:
        grupos_str = f"{qtd_grupos} turmas (+{qtd_exc} exc.)"
    elif qtd_grupos:
        grupos_str = f"{qtd_grupos} turmas"
    elif qtd_exc:
        grupos_str = f"Todas (+{qtd_exc} exc.)"
    else:
        grupos_str = "Todas"

    horario_livre_info = " | 🕒 Horário Livre" if ignorar_horario_grade is True else ""
    texto_lateral = f"{refeicao} ({hora}){texto_item}"
    texto_topo = (
        f"🍲 {refeicao} ({hora}){texto_item} | 📅 {data} | 👥 {grupos_str}"
        f"{horario_livre_info}"
    )
    return texto_lateral, texto_topo
