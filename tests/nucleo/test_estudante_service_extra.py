"""Testes complementares para cobertura >= 90% em estudante_service."""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from registro.nucleo.exceptions import ErroNucleoRegistro
from registro.nucleo.models import Base, Estudante
from registro.nucleo.repository import (
    RepositorioConsumo,
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
)
from registro.nucleo.services import estudante_service


@pytest.fixture()
def repos():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    sessao = Session()
    try:
        yield (
            RepositorioEstudante(sessao),
            RepositorioGrupo(sessao),
            RepositorioReserva(sessao),
            RepositorioConsumo(sessao),
            sessao,
        )
    finally:
        sessao.close()
        engine.dispose()


def test_estudante_service_crud_filtros_e_erros(repos):
    repo_est, repo_grp, repo_res, repo_cons, sessao = repos

    criado = estudante_service.criar_estudante(
        repo_est,
        repo_grp,
        prontuario="IQ3000011",
        nome="Alice Teste",
        grupos=["1º A"],
        categoria="PAP",
    )
    assert criado["prontuario"] == "IQ3000011"
    assert "PAP" in criado["categorias"]

    # Atualizar mantendo categorias quando apenas grupos mudam, e alterando via dados["categoria"]
    assert (
        estudante_service.atualizar_estudante(repo_est, 99999, {"nome": "Inexistente"})
        is False
    )
    assert estudante_service.atualizar_estudante(
        repo_est,
        criado["id"],
        {"categoria": "Optativas", "nome": "Alice Atualizada"},
        repo_grupo=repo_grp,
    )
    assert estudante_service.atualizar_estudante(
        repo_est,
        criado["id"],
        {"nome": "Alice Final"},
        repo_grupo=repo_grp,
        grupos=["1º B"],
    )

    # Alternar status (inexistente e existente)
    assert estudante_service.alternar_status_estudante(repo_est, 99999) is False
    assert estudante_service.alternar_status_estudante(repo_est, criado["id"]) is True

    # Filtros em listar_estudantes e listar_estudantes_fuzzy
    assert estudante_service.listar_estudantes(
        repo_est, termo_busca="Alice", turma_nome="1º B", status_ativo=False
    )
    assert (
        estudante_service.listar_estudantes_fuzzy(
            repo_est, termo_busca="", turma_nome="1º B", status_ativo=False
        )
        != []
    )
    assert (
        estudante_service.listar_estudantes_fuzzy(
            repo_est, termo_busca="Alice", turma_nome="Outra"
        )
        == []
    )

    # Erros de commit em criar, atualizar, alternar e excluir
    with patch.object(sessao, "commit", side_effect=SQLAlchemyError("falha")):
        with pytest.raises(ErroNucleoRegistro):
            estudante_service.criar_estudante(
                repo_est, repo_grp, prontuario="IQ3000099", nome="Erro"
            )
        with pytest.raises(ErroNucleoRegistro):
            estudante_service.atualizar_estudante(repo_est, criado["id"], {"nome": "X"})
        with pytest.raises(ErroNucleoRegistro):
            estudante_service.alternar_status_estudante(repo_est, criado["id"])
        with pytest.raises(ErroNucleoRegistro):
            estudante_service.deletar_ou_desativar_estudante(
                repo_est, repo_res, repo_cons, criado["id"]
            )

    # Exclusão com sucesso quando sem histórico
    res_del = estudante_service.deletar_ou_desativar_estudante(
        repo_est, repo_res, repo_cons, criado["id"]
    )
    assert res_del["status"] == "deleted"
    assert sessao.get(Estudante, criado["id"]) is None
