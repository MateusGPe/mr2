# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/services/estudante_service.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Serviço de gerenciamento de Estudantes (CRUD, filtros e buscas fuzzy).
"""

import logging
import re
from typing import Any, Dict, List, Optional

from fuzzywuzzy import fuzz
from sqlalchemy.orm import selectinload

from registro.nucleo.models import Consumo, Estudante, Grupo, Reserva
from registro.nucleo.repository import (
    RepositorioConsumo,
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
)

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

    novo_estudante = repo_estudante.criar({"prontuario": prontuario, "nome": nome, "ativo": True})

    if grupos:
        for grupo_nome in grupos:
            if not grupo_nome:
                continue
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
    repo_grupo: Optional[RepositorioGrupo] = None,
    grupos: Optional[List[str]] = None,
) -> bool:
    """Atualiza os dados de um estudante e seus grupos associados."""
    sessao = repo_estudante.obter_sessao()
    estudante = (
        sessao.query(Estudante)
        .options(selectinload(Estudante.grupos))
        .filter(Estudante.id == id_estudante)
        .one_or_none()
    )
    if not estudante:
        return False

    for k, v in dados.items():
        if hasattr(estudante, k):
            setattr(estudante, k, v)

    if grupos is not None and repo_grupo is not None:
        estudante.grupos.clear()
        for grupo_nome in grupos:
            if not grupo_nome:
                continue
            grupo = repo_grupo.por_nome(grupo_nome)
            if not grupo:
                grupo = repo_grupo.criar({"nome": grupo_nome})
            estudante.grupos.append(grupo)

    sessao.commit()
    return True


def alternar_status_estudante(
    repo_estudante: RepositorioEstudante,
    id_estudante: int,
) -> bool:
    """Alterna o status ativo do estudante entre True e False."""
    sessao = repo_estudante.obter_sessao()
    estudante = repo_estudante.ler_um(id_estudante)
    if not estudante:
        return False
    estudante.ativo = not bool(estudante.ativo)
    sessao.commit()
    return True


def deletar_ou_desativar_estudante(
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    repo_consumo: RepositorioConsumo,
    id_estudante: int,
    forcar_desativacao: bool = False,
) -> Dict[str, Any]:
    """
    Exclusão segura de estudante.
    Se possuir histórico de consumo ou reservas e não forçar desativação,
    solicita desativação para não corromper integridade referencial.
    """
    sessao = repo_estudante.obter_sessao()
    estudante = (
        sessao.query(Estudante)
        .options(selectinload(Estudante.grupos))
        .filter(Estudante.id == id_estudante)
        .one_or_none()
    )
    if not estudante:
        return {"status": "not_found", "mensagem": "Estudante não encontrado."}

    # Verifica histórico em reservas ou consumos
    tem_reservas = (
        sessao.query(Reserva).filter(Reserva.estudante_id == id_estudante).count()
    )
    tem_consumos = (
        sessao.query(Consumo).filter(Consumo.estudante_id == id_estudante).count()
    )

    if (tem_reservas > 0 or tem_consumos > 0) and not forcar_desativacao:
        return {
            "status": "has_records",
            "mensagem": (
                f"O aluno '{estudante.nome}' possui histórico ({tem_reservas} reserva(s) e "
                f"{tem_consumos} consumo(s)). Ele não pode ser excluído permanentemente. "
                "Deseja apenas desativá-lo?"
            ),
            "reservas": tem_reservas,
            "consumos": tem_consumos,
        }

    if forcar_desativacao:
        estudante.ativo = False
        sessao.commit()
        return {
            "status": "deactivated",
            "mensagem": f"O aluno '{estudante.nome}' foi desativado com sucesso.",
        }

    # Sem histórico: pode excluir com segurança
    estudante.grupos.clear()
    sessao.delete(estudante)
    sessao.commit()
    return {
        "status": "deleted",
        "mensagem": f"O aluno '{estudante.nome}' foi excluído com sucesso.",
    }


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
    turma_nome: Optional[str] = None,
    status_ativo: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Lista estudantes com filtro textual opcional por nome, prontuário, turma e status ativo."""
    sessao = repo_estudante.obter_sessao()
    query = sessao.query(Estudante).options(selectinload(Estudante.grupos))

    if termo_busca and termo_busca.strip():
        termo_like = f"%{termo_busca.strip()}%"
        query = query.filter(
            (Estudante.nome.ilike(termo_like))
            | (Estudante.prontuario.ilike(termo_like))
        )

    if status_ativo is not None:
        query = query.filter(Estudante.ativo == status_ativo)

    if turma_nome and turma_nome != "Todas":
        query = query.filter(Estudante.grupos.any(Grupo.nome == turma_nome))

    estudantes = query.order_by(Estudante.nome).all()
    return [
        {
            "id": est.id,
            "prontuario": est.prontuario,
            "nome": est.nome,
            "ativo": bool(est.ativo) if est.ativo is not None else True,
            "grupos": [g.nome for g in est.grupos],
        }
        for est in estudantes
    ]


def listar_estudantes_fuzzy(
    repo_estudante: RepositorioEstudante,
    termo_busca: Optional[str] = None,
    limite: int = 60,
    turma_nome: Optional[str] = None,
    status_ativo: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Lista estudantes ordenados por relevância fuzzy, respeitando filtros de turma e status."""
    todos_estudantes = repo_estudante.ler_todos_com_grupos()

    # Aplica filtros prévios
    candidatos = []
    for est in todos_estudantes:
        if status_ativo is not None and bool(est.ativo) != status_ativo:
            continue
        if turma_nome and turma_nome != "Todas":
            nomes_grupos = [g.nome for g in est.grupos]
            if turma_nome not in nomes_grupos:
                continue
        candidatos.append(est)

    if not termo_busca or not termo_busca.strip():
        estudantes = sorted(candidatos, key=lambda e: e.nome)
    else:
        termo_lower = termo_busca.lower().strip()
        pront_lower = REGEX_LIMPEZA_PRONTUARIO.sub("", termo_lower)
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
            "ativo": bool(est.ativo) if est.ativo is not None else True,
            "grupos": [g.nome for g in est.grupos],
        }
        for est in estudantes
    ]
