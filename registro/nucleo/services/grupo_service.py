# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/services/grupo_service.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Serviço de gerenciamento de Grupos / Turmas (CRUD, listagens e vinculação de alunos).
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import selectinload

from registro.nucleo.models import Estudante, Grupo
from registro.nucleo.repository import RepositorioEstudante, RepositorioGrupo


def criar_grupo(
    repo_grupo: RepositorioGrupo,
    nome: str,
    ativo: bool = True,
) -> Dict[str, Any]:
    """Cria uma nova turma / grupo."""
    nome_limpo = nome.strip()
    if not nome_limpo:
        raise ValueError("O nome da turma não pode estar vazio.")

    existente = repo_grupo.por_nome(nome_limpo)
    if existente:
        raise ValueError(f"A turma '{nome_limpo}' já existe.")

    grupo = repo_grupo.criar({"nome": nome_limpo, "ativo": ativo})
    repo_grupo.obter_sessao().commit()
    return {"id": grupo.id, "nome": grupo.nome, "ativo": grupo.ativo}


def atualizar_grupo(
    repo_grupo: RepositorioGrupo,
    id_grupo: int,
    dados: Dict[str, Any],
) -> bool:
    """Atualiza o nome e/ou status de uma turma."""
    sessao = repo_grupo.obter_sessao()
    grupo = repo_grupo.ler_um(id_grupo)
    if not grupo:
        return False

    if "nome" in dados:
        novo_nome = dados["nome"].strip()
        if not novo_nome:
            raise ValueError("O nome da turma não pode estar vazio.")
        outro = repo_grupo.por_nome(novo_nome)
        if outro and outro.id != id_grupo:
            raise ValueError(f"Já existe uma turma cadastrada com o nome '{novo_nome}'.")
        grupo.nome = novo_nome

    if "ativo" in dados:
        grupo.ativo = bool(dados["ativo"])

    sessao.commit()
    return True


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
    sessao.commit()
    return {"status": "deleted", "mensagem": f"Turma '{grupo.nome}' excluída com sucesso."}


def listar_turmas_detalhadas(
    repo_grupo: RepositorioGrupo,
    termo_busca: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Lista todas as turmas com quantidade de estudantes e status."""
    sessao = repo_grupo.obter_sessao()
    query = sessao.query(Grupo).options(selectinload(Grupo.estudantes))

    if termo_busca and termo_busca.strip():
        termo = f"%{termo_busca.strip()}%"
        query = query.filter(Grupo.nome.ilike(termo))

    grupos = query.order_by(Grupo.nome).all()
    return [
        {
            "id": g.id,
            "nome": g.nome,
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
        sessao.commit()
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
        sessao.commit()
        return True
    return False
