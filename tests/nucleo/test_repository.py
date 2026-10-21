"""
Testes unitários para as operações de CRUD e repositórios em registro.nucleo.repository.
"""

import pytest
from sqlalchemy.orm import Session

from registro.nucleo.repository import (
    RepositorioConsumo,
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
    RepositorioSessao,
)


def test_repositorio_estudante_operacoes(
    db_session: Session, criar_estudante, criar_grupo
):
    """Testa métodos especializados do RepositorioEstudante."""
    repo = RepositorioEstudante(db_session)
    grupo = criar_grupo(nome="3º A - MAC")

    e1 = criar_estudante(prontuario="IQ3001001", nome="Lucas Silva", grupos=[grupo])
    e2 = criar_estudante(prontuario="IQ3001002", nome="Mariana Costa")

    # Busca por prontuários
    encontrados = repo.por_prontuarios({"IQ3001001", "IQ3001002", "INEXISTENTE"})
    assert len(encontrados) == 2

    # Busca vazia
    assert repo.por_prontuarios(set()) == []
    assert repo.por_ids(set()) == []

    # Busca por IDs
    por_id = repo.por_ids({e1.id, e2.id})
    assert len(por_id) == 2

    # Busca com grupos carregados
    com_grupos = repo.por_prontuarios_com_grupos({"IQ3001001"})
    assert len(com_grupos) == 1
    assert com_grupos[0].grupos[0].nome == "3º A - MAC"

    todos_com_grupos = repo.ler_todos_com_grupos()
    assert len(todos_com_grupos) >= 2


def test_repositorio_grupo_operacoes(db_session: Session, criar_grupo, criar_estudante):
    """Testa busca por nomes e carregamento em RepositorioGrupo."""
    repo = RepositorioGrupo(db_session)
    g1 = criar_grupo(nome="1º A - MEC")
    g2 = criar_grupo(nome="1º B - MEC")

    grupos = repo.por_nomes({"1º A - MEC", "1º B - MEC"})
    assert len(grupos) == 2
    assert repo.por_nomes(set()) == []

    # Teste por_nome
    grupo_lido = repo.por_nome("1º A - MEC")
    assert grupo_lido is not None
    assert grupo_lido.id == g1.id


def test_repositorio_crud_generico(db_session: Session):
    """Testa criar, ler, atualizar e deletar via CRUD genérico."""
    repo = RepositorioGrupo(db_session)

    # Criar
    grupo = repo.criar({"nome": "Grupo Temp", "ativo": True})
    db_session.commit()
    assert grupo.id is not None

    # Ler um
    lido = repo.ler_um(grupo.id)
    assert lido is not None
    assert lido.nome == "Grupo Temp"

    # Atualizar
    atualizado = repo.atualizar(grupo.id, {"nome": "Grupo Atualizado"})
    db_session.commit()
    assert atualizado.nome == "Grupo Atualizado"

    # Deletar
    removido = repo.deletar(grupo.id)
    db_session.commit()
    assert removido is True
    assert repo.ler_um(grupo.id) is None


def test_repositorio_sessao_e_consumo(
    db_session: Session, criar_estudante, criar_sessao, criar_consumo
):
    """Testa consultas em RepositorioSessao e RepositorioConsumo."""
    repo_sessao = RepositorioSessao(db_session)
    repo_consumo = RepositorioConsumo(db_session)

    sessao = criar_sessao(refeicao="lanche", data="21/10/2026", hora="15:30")
    estudante = criar_estudante(prontuario="IQ3002001", nome="Teste Consumo")

    criar_consumo(estudante=estudante, sessao=sessao, hora_consumo="15:32:00")

    consumos = repo_consumo.ler_filtrado(sessao_id=sessao.id)
    assert len(consumos) == 1
    assert consumos[0].estudante.prontuario == "IQ3002001"
