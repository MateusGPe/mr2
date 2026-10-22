# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/services/estudante_service.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Serviço de gerenciamento de Estudantes (CRUD, filtros e buscas fuzzy).
"""

import logging
import re
from typing import Any, Dict, List, Optional

from fuzzywuzzy import fuzz
from sqlalchemy.orm import selectinload

from registro.nucleo.models import Estudante
from registro.nucleo.repository import RepositorioEstudante, RepositorioGrupo

logger = logging.getLogger(__name__)

REGEX_LIMPEZA_PRONTUARIO: re.Pattern[str] = re.compile(r"^[Ii][Qq]30+")


def criar_estudante(
    repo_estudante: RepositorioEstudante,
    repo_grupo: RepositorioGrupo,
    prontuario: str,
    nome: str,
    grupos: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Cria um novo estudante e associa aos grupos fornecidos."""
    existente = repo_estudante.ler_filtrado(prontuario=prontuario)
    if existente:
        raise ValueError(f"Estudante com prontuário {prontuario} já existe.")

    novo_estudante = repo_estudante.criar({"prontuario": prontuario, "nome": nome})

    if grupos:
        for grupo_nome in grupos:
            grupo = repo_grupo.por_nome(grupo_nome)
            if not grupo:
                grupo = repo_grupo.criar({"nome": grupo_nome})
            novo_estudante.grupos.append(grupo)
    repo_estudante.obter_sessao().commit()
    return {
        "id": novo_estudante.id,
        "prontuario": novo_estudante.prontuario,
        "nome": novo_estudante.nome,
    }


def atualizar_estudante(
    repo_estudante: RepositorioEstudante,
    id_estudante: int,
    dados: Dict[str, Any],
) -> bool:
    """Atualiza os dados de um estudante."""
    estudante = repo_estudante.atualizar(id_estudante, dados)
    if estudante:
        repo_estudante.obter_sessao().commit()
        return True
    return False


def listar_todos_os_estudantes(
    repo_estudante: RepositorioEstudante,
) -> List[Dict[str, Any]]:
    """Retorna todos os estudantes com seus grupos associados."""
    sessao = repo_estudante.obter_sessao()
    estudantes = (
        sessao.query(Estudante)
        .options(selectinload(Estudante.grupos))
        .order_by(Estudante.nome)
        .all()
    )
    return [
        {
            "id": e.id,
            "prontuario": e.prontuario,
            "nome": e.nome,
            "ativo": e.ativo,
            "grupos": [g.nome for g in e.grupos],
        }
        for e in estudantes
    ]


def listar_estudantes(
    repo_estudante: RepositorioEstudante,
    termo_busca: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Lista estudantes com filtro textual opcional por nome ou prontuário."""
    sessao = repo_estudante.obter_sessao()
    query = sessao.query(Estudante).options(selectinload(Estudante.grupos))
    if termo_busca:
        termo_like = f"%{termo_busca}%"
        query = query.filter(
            (Estudante.nome.ilike(termo_like))
            | (Estudante.prontuario.ilike(termo_like))
        )
    estudantes = query.order_by(Estudante.nome).all()
    return [
        {
            "id": est.id,
            "prontuario": est.prontuario,
            "nome": est.nome,
            "ativo": est.ativo,
            "grupos": [g.nome for g in est.grupos],
        }
        for est in estudantes
    ]


def listar_estudantes_fuzzy(
    repo_estudante: RepositorioEstudante,
    termo_busca: Optional[str] = None,
    limite: int = 60,
) -> List[Dict[str, Any]]:
    """Lista estudantes ordenados por relevância fuzzy."""
    if not termo_busca or not termo_busca.strip():
        todos_estudantes = repo_estudante.ler_todos_com_grupos()
        estudantes = sorted(todos_estudantes, key=lambda e: e.nome)
    else:
        termo_lower = termo_busca.lower().strip()
        pront_lower = REGEX_LIMPEZA_PRONTUARIO.sub("", termo_lower)
        candidatos = repo_estudante.ler_todos_com_grupos()
        resultados_com_score = []
        for est in candidatos:
            score_nome = fuzz.partial_ratio(termo_lower, est.nome.lower())
            score_pront = fuzz.ratio(
                pront_lower,
                REGEX_LIMPEZA_PRONTUARIO.sub("", est.prontuario.lower()),
            )
            final_score = max(score_nome, score_pront)
            if final_score >= limite:
                resultados_com_score.append(
                    {"estudante": est, "score": final_score}
                )

        resultados_com_score.sort(key=lambda x: x["score"], reverse=True)
        estudantes = [item["estudante"] for item in resultados_com_score]

    return [
        {
            "id": est.id,
            "prontuario": est.prontuario,
            "nome": est.nome,
            "ativo": est.ativo,
            "grupos": [g.nome for g in est.grupos],
        }
        for est in estudantes
    ]
