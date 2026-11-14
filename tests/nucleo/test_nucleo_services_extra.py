"""Testes extras para cobertura de serviços do núcleo (grupo_service e consumo_service)."""

import pytest

from registro.nucleo.exceptions import ErroSessao
from registro.nucleo.repository import (
    RepositorioConsumo,
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
    RepositorioSessao,
)
from registro.nucleo.services import consumo_service, grupo_service


def test_grupo_service_crud_vinculos_e_erros(db_session, criar_estudante, criar_grupo):
    repo_grupo = RepositorioGrupo(db_session)
    repo_estudante = RepositorioEstudante(db_session)

    # Criar grupo valido
    g1 = grupo_service.criar_grupo(repo_grupo, "1A", ativo=True, tipo="turma")
    assert g1["nome"] == "1A"
    assert g1["tipo"] == "turma"

    # Criar categoria
    g2 = grupo_service.criar_grupo(repo_grupo, "Bolsista", ativo=True, tipo="categoria")
    assert g2["tipo"] == "categoria"

    # Nome vazio ou duplicado
    with pytest.raises(ValueError):
        grupo_service.criar_grupo(repo_grupo, "   ")
    with pytest.raises(ValueError):
        grupo_service.criar_grupo(repo_grupo, "1A")

    # Atualizar grupo (inexistente, nome vazio, conflito de nome, sucesso)
    assert grupo_service.atualizar_grupo(repo_grupo, 99999, {"nome": "X"}) is False
    with pytest.raises(ValueError):
        grupo_service.atualizar_grupo(repo_grupo, g1["id"], {"nome": "  "})
    with pytest.raises(ValueError):
        grupo_service.atualizar_grupo(repo_grupo, g1["id"], {"nome": "Bolsista"})

    assert (
        grupo_service.atualizar_grupo(
            repo_grupo, g1["id"], {"nome": "1A-Novo", "tipo": "turma", "ativo": False}
        )
        is True
    )

    # Listar turmas detalhadas com filtros
    detalhes = grupo_service.listar_turmas_detalhadas(
        repo_grupo, termo_busca="1A-Novo", tipo="turma"
    )
    assert len(detalhes) == 1
    assert detalhes[0]["ativo"] is False

    # Vincular e desvincular estudante
    est = criar_estudante(prontuario="PR900", nome="Aluno Vinculo")
    assert (
        grupo_service.vincular_aluno_turma(repo_grupo, repo_estudante, 99999, est.id)
        is False
    )
    assert (
        grupo_service.vincular_aluno_turma(repo_grupo, repo_estudante, g1["id"], est.id)
        is True
    )

    alunos_turma = grupo_service.listar_alunos_por_turma(repo_grupo, g1["id"])
    assert len(alunos_turma) == 1
    assert alunos_turma[0]["prontuario"] == "PR900"
    assert grupo_service.listar_alunos_por_turma(repo_grupo, 99999) == []

    # Deletar grupo com vinculos sem forcar -> has_relations
    res_rel = grupo_service.deletar_grupo(repo_grupo, g1["id"], forcar=False)
    assert res_rel["status"] == "has_relations"

    # Desvincular e deletar
    assert grupo_service.desvincular_aluno_turma(repo_grupo, 99999, est.id) is False
    assert grupo_service.desvincular_aluno_turma(repo_grupo, g1["id"], 99999) is False
    assert grupo_service.desvincular_aluno_turma(repo_grupo, g1["id"], est.id) is True

    res_del = grupo_service.deletar_grupo(repo_grupo, g1["id"], forcar=False)
    assert res_del["status"] == "deleted"
    assert grupo_service.deletar_grupo(repo_grupo, 99999)["status"] == "not_found"


def test_consumo_service_erros_e_bordas(
    db_session, criar_grupo, criar_estudante, criar_sessao
):
    repo_consumo = RepositorioConsumo(db_session)
    repo_estudante = RepositorioEstudante(db_session)
    repo_sessao = RepositorioSessao(db_session)
    repo_reserva = RepositorioReserva(db_session)

    # Sessao inexistente ao registrar consumo
    with pytest.raises(ErroSessao):
        consumo_service.registrar_consumo(
            repo_sessao, repo_estudante, repo_reserva, repo_consumo, 99999, "PR1"
        )

    # Estudante inexistente
    grupo = criar_grupo(nome="2A")
    sessao = criar_sessao(refeicao="Almoço", data="13/11/2026", grupos=[grupo])
    res_sem_est = consumo_service.registrar_consumo(
        repo_sessao,
        repo_estudante,
        repo_reserva,
        repo_consumo,
        sessao.id,
        "INEXISTENTE",
    )
    assert res_sem_est["autorizado"] is False

    # Estudante inativo
    est_inativo = criar_estudante(
        prontuario="PR_INAT", nome="Inativo", ativo=False, grupos=[grupo]
    )
    res_inat = consumo_service.registrar_consumo(
        repo_sessao,
        repo_estudante,
        repo_reserva,
        repo_consumo,
        sessao.id,
        est_inativo.prontuario,
    )
    assert res_inat["autorizado"] is False

    # Desfazer consumo inexistente
    assert consumo_service.desfazer_consumo(repo_consumo, 99999) is False
    assert (
        consumo_service.desfazer_consumo_por_prontuario(
            repo_consumo, "INEXISTENTE", sessao.id
        )
        is False
    )
