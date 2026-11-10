# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/services/grupo_service.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Serviço de gerenciamento de Grupos / Turmas (CRUD, listagens e vinculação de alunos).
"""

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import selectinload

from registro.nucleo.constants import (
    TIPOS_GRUPO_VALIDOS,
    TIPO_GRUPO_TURMA,
)
from registro.nucleo.exceptions import ErroNucleoRegistro
from registro.nucleo.models import Estudante, Grupo
from registro.nucleo.repository import RepositorioEstudante, RepositorioGrupo

logger = logging.getLogger(__name__)


def _normalizar_tipo_grupo(tipo: Optional[str]) -> str:
    """Valida e normaliza o tipo do grupo ('turma' ou 'categoria')."""
    tipo_norm = (tipo or TIPO_GRUPO_TURMA).strip().lower()
    if tipo_norm not in TIPOS_GRUPO_VALIDOS:
        raise ValueError(
            f"Tipo de grupo inválido: '{tipo}'. Valores permitidos: {', '.join(sorted(TIPOS_GRUPO_VALIDOS))}."
        )
    return tipo_norm


def criar_grupo(
    repo_grupo: RepositorioGrupo,
    nome: str,
    ativo: bool = True,
    tipo: str = TIPO_GRUPO_TURMA,
) -> Dict[str, Any]:
    """Cria uma nova turma ou categoria."""
    nome_limpo = nome.strip()
    if not nome_limpo:
        raise ValueError("O nome da turma/categoria não pode estar vazio.")

    tipo_norm = _normalizar_tipo_grupo(tipo)

    existente = repo_grupo.por_nome(nome_limpo)
    if existente:
        raise ValueError(f"O grupo '{nome_limpo}' já existe.")

    grupo = repo_grupo.criar({"nome": nome_limpo, "ativo": ativo, "tipo": tipo_norm})
    try:
        repo_grupo.obter_sessao().commit()
    except Exception as e:
        logger.exception("Falha ao criar grupo %s: %s", nome_limpo, e)
        try:
            repo_grupo.obter_sessao().rollback()
        except Exception:
            pass
        raise ErroNucleoRegistro(f"Falha ao criar grupo no banco: {e}") from e
    return {"id": grupo.id, "nome": grupo.nome, "ativo": grupo.ativo, "tipo": grupo.tipo}


def atualizar_grupo(
    repo_grupo: RepositorioGrupo,
    id_grupo: int,
    dados: Dict[str, Any],
) -> bool:
    """Atualiza o nome, tipo e/ou status de uma turma/categoria."""
    sessao = repo_grupo.obter_sessao()
    grupo = repo_grupo.ler_um(id_grupo)
    if not grupo:
        return False

    if "nome" in dados:
        novo_nome = dados["nome"].strip()
        if not novo_nome:
            raise ValueError("O nome da turma/categoria não pode estar vazio.")
        outro = repo_grupo.por_nome(novo_nome)
        if outro and outro.id != id_grupo:
            raise ValueError(f"Já existe um grupo cadastrado com o nome '{novo_nome}'.")
        grupo.nome = novo_nome

    if "tipo" in dados:
        grupo.tipo = _normalizar_tipo_grupo(dados["tipo"])

    if "ativo" in dados:
        grupo.ativo = bool(dados["ativo"])

    try:
        sessao.commit()
        return True
    except Exception as e:
        logger.exception("Falha ao atualizar turma %s: %s", id_grupo, e)
        try:
            sessao.rollback()
        except Exception:
            pass
        raise ErroNucleoRegistro(f"Falha ao atualizar turma no banco: {e}") from e


def deletar_grupo(
    repo_grupo: RepositorioGrupo,
    id_grupo: int,
    forcar: bool = False,
) -> Dict[str, Any]:
    """
    Remove uma turma.
    Se a turma possuir alunos ou sessões vinculadas e 'forcar' for False,
    bloqueia a exclusão e avisa o usuário.
    """
    sessao = repo_grupo.obter_sessao()
    grupo = (
        sessao.query(Grupo)
        .options(selectinload(Grupo.estudantes), selectinload(Grupo.sessoes))
        .filter(Grupo.id == id_grupo)
        .one_or_none()
    )
    if not grupo:
        return {"status": "not_found", "mensagem": "Turma não encontrada."}

    qtd_alunos = len(grupo.estudantes)
    qtd_sessoes = len(grupo.sessoes)

    if (qtd_alunos > 0 or qtd_sessoes > 0) and not forcar:
        return {
            "status": "has_relations",
            "mensagem": (
                f"A turma '{grupo.nome}' possui {qtd_alunos} aluno(s) e "
                f"{qtd_sessoes} sessão(ões) vinculada(s). Desvincule-os antes ou desative a turma."
            ),
            "qtd_alunos": qtd_alunos,
            "qtd_sessoes": qtd_sessoes,
        }

    # Desassocia alunos antes de remover
    grupo.estudantes.clear()
    grupo.sessoes.clear()
    sessao.delete(grupo)
    try:
        sessao.commit()
        return {"status": "deleted", "mensagem": f"Turma '{grupo.nome}' excluída com sucesso."}
    except Exception as e:
        logger.exception("Falha ao excluir turma %s: %s", id_grupo, e)
        try:
            sessao.rollback()
        except Exception:
            pass
        raise ErroNucleoRegistro(f"Falha ao excluir turma no banco: {e}") from e


def listar_turmas_detalhadas(
    repo_grupo: RepositorioGrupo,
    termo_busca: Optional[str] = None,
    tipo: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Lista grupos (turmas e categorias) com quantidade de estudantes, tipo e status."""
    sessao = repo_grupo.obter_sessao()
    query = sessao.query(Grupo).options(selectinload(Grupo.estudantes))

    if tipo and tipo.strip().lower() in TIPOS_GRUPO_VALIDOS:
        query = query.filter(Grupo.tipo == tipo.strip().lower())

    if termo_busca and termo_busca.strip():
        termo = f"%{termo_busca.strip()}%"
        query = query.filter(Grupo.nome.ilike(termo))

    grupos = query.order_by(Grupo.tipo, Grupo.nome).all()
    return [
        {
            "id": g.id,
            "nome": g.nome,
            "tipo": getattr(g, "tipo", TIPO_GRUPO_TURMA) or TIPO_GRUPO_TURMA,
            "ativo": bool(g.ativo) if g.ativo is not None else True,
            "total_alunos": len(g.estudantes),
        }
        for g in grupos
    ]


def listar_alunos_por_turma(
    repo_grupo: RepositorioGrupo,
    id_grupo: int,
) -> List[Dict[str, Any]]:
    """Retorna os alunos vinculados a uma turma específica."""
    sessao = repo_grupo.obter_sessao()
    grupo = (
        sessao.query(Grupo)
        .options(selectinload(Grupo.estudantes))
        .filter(Grupo.id == id_grupo)
        .one_or_none()
    )
    if not grupo:
        return []

    return [
        {
            "id": est.id,
            "prontuario": est.prontuario,
            "nome": est.nome,
            "ativo": est.ativo if est.ativo is not None else True,
        }
        for est in sorted(grupo.estudantes, key=lambda e: e.nome)
    ]


def vincular_aluno_turma(
    repo_grupo: RepositorioGrupo,
    repo_estudante: RepositorioEstudante,
    id_grupo: int,
    id_estudante: int,
) -> bool:
    """Adiciona um estudante à turma."""
    sessao = repo_grupo.obter_sessao()
    grupo = (
        sessao.query(Grupo)
        .options(selectinload(Grupo.estudantes))
        .filter(Grupo.id == id_grupo)
        .one_or_none()
    )
    estudante = repo_estudante.ler_um(id_estudante)
    if not grupo or not estudante:
        return False

    if estudante not in grupo.estudantes:
        grupo.estudantes.append(estudante)
        try:
            sessao.commit()
        except Exception as e:
            logger.exception("Falha ao vincular aluno %s à turma %s: %s", id_estudante, id_grupo, e)
            try:
                sessao.rollback()
            except Exception:
                pass
            raise ErroNucleoRegistro(f"Falha ao vincular aluno à turma: {e}") from e
    return True


def desvincular_aluno_turma(
    repo_grupo: RepositorioGrupo,
    id_grupo: int,
    id_estudante: int,
) -> bool:
    """Remove um estudante da turma."""
    sessao = repo_grupo.obter_sessao()
    grupo = (
        sessao.query(Grupo)
        .options(selectinload(Grupo.estudantes))
        .filter(Grupo.id == id_grupo)
        .one_or_none()
    )
    if not grupo:
        return False

    estudante_para_remover = next(
        (e for e in grupo.estudantes if e.id == id_estudante), None
    )
    if estudante_para_remover:
        grupo.estudantes.remove(estudante_para_remover)
        try:
            sessao.commit()
            return True
        except Exception as e:
            logger.exception("Falha ao desvincular aluno %s da turma %s: %s", id_estudante, id_grupo, e)
            try:
                sessao.rollback()
            except Exception:
                pass
            raise ErroNucleoRegistro(f"Falha ao desvincular aluno da turma: {e}") from e
    return False
