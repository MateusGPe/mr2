# ----------------------------------------------------------------------------
# Arquivo: tests/nucleo/test_grupo_service.py
# ----------------------------------------------------------------------------
"""
Testes unitários para o serviço de grupos/turmas e utilitário rollback_seguro.
"""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from registro.nucleo.constants import TIPO_GRUPO_CATEGORIA, TIPO_GRUPO_TURMA
from registro.nucleo.repository import RepositorioGrupo
from registro.nucleo.services import grupo_service
from registro.nucleo.utils import rollback_seguro


def test_criar_grupo_sucesso_e_validacoes(db_session):
    repo = RepositorioGrupo(db_session)

    criado = grupo_service.criar_grupo(
        repo, "  1º A - INF  ", ativo=True, tipo=TIPO_GRUPO_TURMA
    )
    assert criado["nome"] == "1º A - INF"
    assert criado["tipo"] == TIPO_GRUPO_TURMA
    assert criado["ativo"] is True

    cat = grupo_service.criar_grupo(repo, "PAP", tipo=TIPO_GRUPO_CATEGORIA)
    assert cat["tipo"] == TIPO_GRUPO_CATEGORIA

    with pytest.raises(ValueError, match="vazio"):
        grupo_service.criar_grupo(repo, "   ")

    with pytest.raises(ValueError, match="inválido"):
        grupo_service.criar_grupo(repo, "Outro", tipo="desconhecido")

    with pytest.raises(ValueError, match="já existe"):
        grupo_service.criar_grupo(repo, "1º A - INF")


def test_atualizar_grupo(db_session):
    repo = RepositorioGrupo(db_session)
    g1 = grupo_service.criar_grupo(repo, "Turma 1")
    grupo_service.criar_grupo(repo, "Turma 2")

    assert grupo_service.atualizar_grupo(repo, 999999, {"nome": "X"}) is False

    with pytest.raises(ValueError, match="vazio"):
        grupo_service.atualizar_grupo(repo, g1["id"], {"nome": "  "})

    with pytest.raises(ValueError, match="Já existe"):
        grupo_service.atualizar_grupo(repo, g1["id"], {"nome": "Turma 2"})

    ok = grupo_service.atualizar_grupo(
        repo,
        g1["id"],
        {"nome": "Turma 1B", "tipo": TIPO_GRUPO_CATEGORIA, "ativo": False},
    )
    assert ok is True
    atualizado = repo.ler_um(g1["id"])
    assert atualizado is not None
    assert atualizado.nome == "Turma 1B"
    assert atualizado.tipo == TIPO_GRUPO_CATEGORIA
    assert atualizado.ativo is False


def test_deletar_grupo_com_e_sem_vinculos(db_session, criar_grupo, criar_estudante):
    repo = RepositorioGrupo(db_session)
    assert grupo_service.deletar_grupo(repo, 999999)["status"] == "not_found"

    grupo = criar_grupo(nome="Turma Vinculada")
    criar_estudante(prontuario="IQ3010101", nome="Aluno Vinculado", grupos=[grupo])

    bloqueado = grupo_service.deletar_grupo(repo, grupo.id, forcar=False)
    assert bloqueado["status"] == "has_relations"
    assert bloqueado["qtd_alunos"] == 1

    forcado = grupo_service.deletar_grupo(repo, grupo.id, forcar=True)
    assert forcado["status"] == "deleted"
    assert repo.ler_um(grupo.id) is None


def test_listar_turmas_detalhadas_filtros(db_session, criar_grupo, criar_estudante):
    repo = RepositorioGrupo(db_session)
    t = criar_grupo(nome="1º A - MEC", tipo=TIPO_GRUPO_TURMA)
    criar_grupo(nome="PAP", tipo=TIPO_GRUPO_CATEGORIA)
    criar_estudante(prontuario="IQ3010102", nome="Aluno Mec", grupos=[t])

    todas = grupo_service.listar_turmas_detalhadas(repo)
    assert len(todas) == 2

    apenas_mec = grupo_service.listar_turmas_detalhadas(
        repo, termo_busca="MEC", tipo=TIPO_GRUPO_TURMA
    )
    assert len(apenas_mec) == 1
    assert apenas_mec[0]["nome"] == "1º A - MEC"
    assert apenas_mec[0]["total_alunos"] == 1

    apenas_cat = grupo_service.listar_turmas_detalhadas(repo, tipo=TIPO_GRUPO_CATEGORIA)
    assert len(apenas_cat) == 1
    assert apenas_cat[0]["nome"] == "PAP"


def test_rollback_seguro_registra_falha_sem_propagar():
    sessao_mock = MagicMock()
    sessao_mock.rollback.side_effect = SQLAlchemyError("erro simulado")
    rollback_seguro(sessao_mock, contexto="teste")
    sessao_mock.rollback.assert_called_once()
