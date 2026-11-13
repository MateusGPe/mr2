# ----------------------------------------------------------------------------
# Arquivo: tests/nucleo/test_sessao_mutacoes_filtros.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Testes abrangentes de mutações, filtros, ciclo de vida e casos de uso
(prováveis e improváveis) para o serviço de sessões (sessao_service).
"""

import json

import pytest
from sqlalchemy.orm import Session

from registro.nucleo import constants
from registro.nucleo.exceptions import ErroSessao
from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.models import Consumo
from registro.nucleo.repository import (
    RepositorioConsumo,
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
    RepositorioSessao,
)
from registro.nucleo.services import sessao_service


@pytest.fixture
def repos_sessao(db_session: Session):
    return {
        "sessao": RepositorioSessao(db_session),
        "estudante": RepositorioEstudante(db_session),
        "grupo": RepositorioGrupo(db_session),
        "reserva": RepositorioReserva(db_session),
        "consumo": RepositorioConsumo(db_session),
    }


# ============================================================================
# 1. Testes de Criação, Falha por Falta de Reserva e Edição da Sessão
# ============================================================================


def test_iniciar_sessao_sem_reservas_bloqueia_almoco_mas_permite_lanche(repos_sessao):
    """Cenário provável: almoço/jantar sem reservas não deve criar sessão; lanche sim."""
    repo_s = repos_sessao["sessao"]
    repo_g = repos_sessao["grupo"]
    repo_r = repos_sessao["reserva"]

    # Tentativa de almoço sem reservas no dia -> Retorna None
    dados_almoco = {
        "refeicao": "almoço",
        "periodo": "tarde",
        "data": "2026-11-10",
        "hora": "12:00",
        "grupos": [],
    }
    id_almoco = sessao_service.iniciar_nova_sessao(repo_s, repo_g, repo_r, dados_almoco)
    assert id_almoco is None

    # Tentativa de lanche sem reservas -> Deve criar normalmente
    dados_lanche = {
        "refeicao": "lanche",
        "periodo": "tarde",
        "data": "2026-11-10",
        "hora": "15:30",
        "item_servido": "Suco e Biscoito",
        "grupos": [],
    }
    id_lanche = sessao_service.iniciar_nova_sessao(repo_s, repo_g, repo_r, dados_lanche)
    assert id_lanche is not None
    assert id_lanche > 0


def test_atualizar_sessao_sucesso_e_inexistente(repos_sessao, criar_sessao):
    """Atualização de metadados da sessão e garantia de exceção em ID inexistente."""
    repo_s = repos_sessao["sessao"]
    sessao = criar_sessao(refeicao="lanche", item_servido="Biscoito")

    # 1. Atualização com sucesso
    atualizada = sessao_service.atualizar_sessao(
        repo_s, sessao.id, {"item_servido": "Bolo de Cenoura", "hora": "16:00"}
    )
    assert atualizada.item_servido == "Bolo de Cenoura"
    assert atualizada.hora == "16:00"

    # 2. Cenário improvável: Atualizar sessão com ID inexistente -> ErroSessao
    with pytest.raises(ErroSessao, match="não encontrada"):
        sessao_service.atualizar_sessao(repo_s, 99999, {"item_servido": "Nada"})


# ============================================================================
# 2. Múltiplas Mutações em Filtros de Turmas e Impacto em Estudantes Elegíveis
# ============================================================================


def test_mutacoes_continuas_em_filtros_de_turma(
    repos_sessao, criar_grupo, criar_estudante, criar_sessao
):
    """
    Testa sequência de mutações de grupos na sessão:
    - Sessão começa com Turma A e Turma B
    - Filtro é alterado para apenas Turma A -> Turma B desaparece dos elegíveis
    - Filtro é alterado para zero turmas (vazio) -> nenhum discente elegível
    - Filtro é restaurado para Turma A, B e C -> todos retornam aos elegíveis
    """
    repo_s = repos_sessao["sessao"]
    repo_e = repos_sessao["estudante"]
    repo_r = repos_sessao["reserva"]
    repo_c = repos_sessao["consumo"]
    repo_g = repos_sessao["grupo"]

    g_a = criar_grupo(nome="1º A", ativo=True)
    g_b = criar_grupo(nome="2º A", ativo=True)
    g_c = criar_grupo(nome="3º A", ativo=True)

    e_a = criar_estudante(prontuario="IQ01", nome="Aluno A", grupos=[g_a])
    e_b = criar_estudante(prontuario="IQ02", nome="Aluno B", grupos=[g_b])
    e_c = criar_estudante(prontuario="IQ03", nome="Aluno C", grupos=[g_c])

    sessao = criar_sessao(
        refeicao="lanche",
        item_servido="Iogurte",
        grupos=[g_a, g_b],
    )

    # 1. Estado inicial: 1º A e 2º A autorizados
    elegiveis = sessao_service.obter_estudantes_para_sessao(
        repo_s, repo_e, repo_r, repo_c, repo_g, sessao.id
    )
    prontuarios = {e["pront"] for e in elegiveis}
    assert prontuarios == {"IQ01", "IQ02"}

    # 2. Mutação 1: Reduzir para apenas 1º A
    sessao_service.atualizar_grupos_sessao(repo_s, repo_g, sessao.id, ["1º A"])
    elegiveis_m1 = sessao_service.obter_estudantes_para_sessao(
        repo_s, repo_e, repo_r, repo_c, repo_g, sessao.id
    )
    prontuarios_m1 = {e["pront"] for e in elegiveis_m1}
    assert prontuarios_m1 == {"IQ01"}

    # 3. Mutação 2: Zero turmas selecionadas
    sessao_service.atualizar_grupos_sessao(repo_s, repo_g, sessao.id, [])
    elegiveis_m2 = sessao_service.obter_estudantes_para_sessao(
        repo_s, repo_e, repo_r, repo_c, repo_g, sessao.id
    )
    assert len(elegiveis_m2) == 0

    # 4. Mutação 3: Expandir para 1º A, 2º A e 3º A
    sessao_service.atualizar_grupos_sessao(
        repo_s, repo_g, sessao.id, ["1º A", "2º A", "3º A"]
    )
    elegiveis_m3 = sessao_service.obter_estudantes_para_sessao(
        repo_s, repo_e, repo_r, repo_c, repo_g, sessao.id
    )
    prontuarios_m3 = {e["pront"] for e in elegiveis_m3}
    assert prontuarios_m3 == {"IQ01", "IQ02", "IQ03"}


def test_obter_estudantes_excecao_grupos_e_pular_grupos(
    repos_sessao, criar_grupo, criar_estudante, criar_sessao
):
    """Testa filtros com exceção de grupos e bypass (pular_grupos)."""
    repo_s = repos_sessao["sessao"]
    repo_e = repos_sessao["estudante"]
    repo_r = repos_sessao["reserva"]
    repo_c = repos_sessao["consumo"]
    repo_g = repos_sessao["grupo"]

    g_sessao = criar_grupo(nome="TURMA_OFICIAL")
    g_extra = criar_grupo(nome="MONITORES")
    g_fora = criar_grupo(nome="TURMA_FORA")

    criar_estudante(prontuario="IQ01", nome="Oficial", grupos=[g_sessao])
    criar_estudante(prontuario="IQ02", nome="Monitor", grupos=[g_extra])
    criar_estudante(prontuario="IQ03", nome="De Fora", grupos=[g_fora])

    sessao = criar_sessao(refeicao="lanche", grupos=[g_sessao])

    # Sem exceção: apenas Oficial
    res1 = sessao_service.obter_estudantes_para_sessao(
        repo_s, repo_e, repo_r, repo_c, repo_g, sessao.id
    )
    assert {e["pront"] for e in res1} == {"IQ01"}

    # Com exceção para MONITORES: Oficial + Monitor
    res2 = sessao_service.obter_estudantes_para_sessao(
        repo_s, repo_e, repo_r, repo_c, repo_g, sessao.id, excecao_grupos={"MONITORES"}
    )
    assert {e["pront"] for e in res2} == {"IQ01", "IQ02"}


# ============================================================================
# 3. Testes de Ciclo de Vida e Persistência de session.json
# ============================================================================


def test_ciclo_vida_sessao_json(facade: FachadaRegistro, criar_sessao, tmp_path, monkeypatch):
    """Testa salvar, recarregar, corromper e limpar session.json."""
    arquivo_sessao = tmp_path / "session.json"
    monkeypatch.setattr(constants, "CAMINHO_SESSAO", arquivo_sessao)

    sessao = criar_sessao(refeicao="lanche")

    # 1. Salvar estado
    assert not arquivo_sessao.exists()
    ok_salvar = sessao_service.salvar_estado_sessao(facade, sessao.id)
    assert ok_salvar is True
    assert arquivo_sessao.exists()

    # 2. Recarregar estado
    facade.id_sessao_ativa = None
    dados = sessao_service.carregar_estado_sessao(facade)
    assert dados is not None
    assert dados["id_sessao"] == sessao.id
    assert facade.id_sessao_ativa == sessao.id

    # 3. Cenário improvável: session.json corrompido
    arquivo_sessao.write_text("invalido: json {", encoding="utf-8")
    dados_corrompidos = sessao_service.carregar_estado_sessao(facade)
    assert dados_corrompidos is None

    # 4. Limpar estado
    arquivo_sessao.write_text(json.dumps({"id_sessao": sessao.id}), encoding="utf-8")
    assert arquivo_sessao.exists()
    ok_limpar = sessao_service.limpar_estado_sessao(facade)
    assert ok_limpar is True
    assert not arquivo_sessao.exists()
    assert facade.id_sessao_ativa is None


# ============================================================================
# 4. Deleção em Cascata de Sessão com Consumos
# ============================================================================


def test_deletar_sessao_com_consumos_cascata(
    repos_sessao, db_session: Session, criar_estudante, criar_sessao, criar_consumo
):
    """Verifica se a deleção da sessão remove a sessão e propaga adequadamente."""
    repo_s = repos_sessao["sessao"]

    estudante = criar_estudante(prontuario="IQ99")
    sessao = criar_sessao(refeicao="lanche")
    consumo = criar_consumo(estudante=estudante, sessao=sessao)

    id_sessao = sessao.id
    id_consumo = consumo.id

    # Deleta a sessão via serviço
    sessao_service.deletar_sessao(repo_s, id_sessao)

    # Sessão não existe mais
    assert repo_s.ler_um(id_sessao) is None

    # Consumo associado foi deletado por cascata
    consumo_db = db_session.query(Consumo).filter_by(id=id_consumo).first()
    assert consumo_db is None

    # Deletar sessão inexistente -> ErroSessao
    with pytest.raises(ErroSessao, match="não encontrada para exclusão"):
        sessao_service.deletar_sessao(repo_s, 88888)


def test_obter_estudantes_inativos_e_filtro_consumido(
    repos_sessao, criar_grupo, criar_estudante, criar_sessao, criar_consumo
):
    """Verifica exclusão de estudantes inativos e diferenciação de consumido=True/False."""
    repo_s = repos_sessao["sessao"]
    repo_e = repos_sessao["estudante"]
    repo_r = repos_sessao["reserva"]
    repo_c = repos_sessao["consumo"]
    repo_g = repos_sessao["grupo"]

    grupo = criar_grupo(nome="TURMA_TESTE")
    e_ativo = criar_estudante(prontuario="IQ_ATIVO", ativo=True, grupos=[grupo])
    e_inativo = criar_estudante(prontuario="IQ_INATIVO", ativo=False, grupos=[grupo])

    sessao = criar_sessao(refeicao="lanche", grupos=[grupo])

    # 1. Inativo não deve aparecer nos elegíveis
    elegiveis = sessao_service.obter_estudantes_para_sessao(
        repo_s, repo_e, repo_r, repo_c, repo_g, sessao.id, consumido=False
    )
    pronts = [e["pront"] for e in elegiveis]
    assert "IQ_ATIVO" in pronts
    assert "IQ_INATIVO" not in pronts

    # 2. Registra consumo para o estudante ativo
    criar_consumo(estudante=e_ativo, sessao=sessao)

    # consumido=False -> vazio
    pendentes = sessao_service.obter_estudantes_para_sessao(
        repo_s, repo_e, repo_r, repo_c, repo_g, sessao.id, consumido=False
    )
    assert len(pendentes) == 0

    # consumido=True -> contém e_ativo
    atendidos = sessao_service.obter_estudantes_para_sessao(
        repo_s, repo_e, repo_r, repo_c, repo_g, sessao.id, consumido=True
    )
    assert len(atendidos) == 1
    assert atendidos[0]["pront"] == "IQ_ATIVO"
    assert atendidos[0]["consumido"] is True

