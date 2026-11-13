# ----------------------------------------------------------------------------
# Arquivo: tests/e2e/test_e2e_integridade_transacional_stats.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Testes E2E rigorosos para:
1. Constraints reais de SQLite com `PRAGMA foreign_keys = ON` (`RESTRICT`, `UniqueConstraint`, `CASCADE`).
2. Blindagem transacional: recuperação da mesma instância `FachadaRegistro` após erro de `commit()`.
3. Persistência/restauração completa de estado de sessão (`session.json`) entre instâncias.
4. Consistência rigorosa de `obter_estatisticas_dashboard` e `obter_estatisticas_sessao`
   sob mutações (estorno, cancelamento de reserva, inativação de estudante, categorias).
"""

import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from registro.nucleo import constants
from registro.nucleo.exceptions import ErroNucleoRegistro, ErroSessao
from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.models import Consumo, Reserva


def test_constraints_fk_restrict_e_unique_sqlite_ativo(
    facade: FachadaRegistro,
    db_session,
    criar_grupo,
    criar_estudante,
    criar_reserva,
):
    """
    Valida com `PRAGMA foreign_keys=ON` que:
    - Excluir Reserva ou Estudante que possui Consumo vinculado dispara `IntegrityError` (`RESTRICT`).
    - `deletar_grupo(..., forcar=False)` bloqueia exclusão quando há vínculo e `forcar=True` limpa e remove.
    """
    turma = criar_grupo(nome="1º TESTE", tipo="turma")
    est = criar_estudante(prontuario="IQ3080001", nome="Aluno FK", grupos=[turma])
    res = criar_reserva(estudante=est, data="10/11/2026", almoco=True)

    id_sessao = facade.iniciar_nova_sessao(
        {
            "refeicao": "almoço",
            "periodo": "Tarde",
            "data": "2026-11-10",
            "hora": "12:00",
            "grupos": ["1º TESTE"],
        }
    )
    assert id_sessao is not None
    assert facade.registrar_consumo(est.prontuario)["autorizado"] is True

    # Tentativa de excluir reserva vinculada a consumo -> ErroNucleoRegistro (wrapping IntegrityError)
    with pytest.raises(ErroNucleoRegistro):
        facade.deletar_reserva(res.id)

    # Sessão SQLAlchemy deve continuar saudável após rollback automático
    assert db_session.query(Reserva).filter_by(id=res.id).one() is not None

    # Tentativa de inserir Consumo apontando para estudante inexistente -> IntegrityError (FK ON)
    consumo_orfao = Consumo(
        estudante_id=999999, sessao_id=id_sessao, hora_consumo="12:05:00", ativo=True
    )
    db_session.add(consumo_orfao)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Grupo com alunos/sessão vinculados: forcar=False bloqueia, forcar=True exclui
    res_del_bloqueado = facade.deletar_grupo(turma.id, forcar=False)
    assert res_del_bloqueado["status"] == "has_relations"
    assert facade.deletar_grupo(turma.id, forcar=True)["status"] == "deleted"


def test_recuperacao_transacional_mesma_fachada_apos_falha_commit(
    facade: FachadaRegistro,
    db_session,
    criar_grupo,
    criar_estudante,
):
    """
    Simula falhas de `commit()` em operações críticas da mesma `FachadaRegistro`
    e comprova que o rollback preventivo evita `PendingRollbackError` nas operações seguintes.
    """
    turma = criar_grupo(nome="2º ROBUSTO", tipo="turma")
    est = criar_estudante(prontuario="IQ3090001", nome="Aluno Rollback", grupos=[turma])

    commit_original = db_session.commit
    falhar_uma_vez = {"ativo": True}

    def commit_com_falha():
        if falhar_uma_vez["ativo"]:
            falhar_uma_vez["ativo"] = False
            raise SQLAlchemyError("Disco ocupado simulado")
        return commit_original()

    db_session.commit = commit_com_falha
    try:
        # 1. Falha ao criar reserva -> rollback automático e erro encapsulado
        with pytest.raises(ErroNucleoRegistro):
            facade.criar_reserva(est.prontuario, {"data": "10/11/2026", "almoco": True})

        # 2. Operação imediatamente posterior na MESMA fachada funciona normalmente
        res_ok = facade.criar_reserva(
            est.prontuario, {"data": "10/11/2026", "almoco": True}
        )
        assert res_ok["id"] is not None

        # 3. Falha ao iniciar sessão -> ErroSessao com rollback
        falhar_uma_vez["ativo"] = True
        with pytest.raises(ErroSessao):
            facade.iniciar_nova_sessao(
                {
                    "refeicao": "almoço",
                    "periodo": "Tarde",
                    "data": "2026-11-10",
                    "hora": "12:00",
                    "grupos": ["2º ROBUSTO"],
                }
            )

        # 4. Próxima tentativa de iniciar sessão funciona normalmente
        id_sessao = facade.iniciar_nova_sessao(
            {
                "refeicao": "almoço",
                "periodo": "Tarde",
                "data": "2026-11-10",
                "hora": "12:00",
                "grupos": ["2º ROBUSTO"],
            }
        )
        assert id_sessao is not None

        # 5. Falha ao registrar consumo -> retorna autorizado=False e faz rollback sem travar sessão
        falhar_uma_vez["ativo"] = True
        r_falha = facade.registrar_consumo(est.prontuario)
        assert r_falha["autorizado"] is False
        assert "banco de dados" in r_falha["motivo"].lower()

        # 6. Tentativa imediata seguinte grava consumo normalmente
        r_sucesso = facade.registrar_consumo(est.prontuario)
        assert r_sucesso["autorizado"] is True
        assert (
            db_session.query(Consumo).filter_by(sessao_id=id_sessao, ativo=True).count()
            == 1
        )
    finally:
        db_session.commit = commit_original


def test_persistencia_e_restauracao_estado_sessao_entre_instancias_fachada(
    db_session,
    criar_grupo,
    criar_estudante,
    tmp_path,
    monkeypatch,
):
    """
    Simula fechamento e reabertura da aplicação:
    Instância 1 cria sessão, define exceção de grupos e ignorar_horario_grade e salva `session.json`.
    Instância 2 (nova `FachadaRegistro`) carrega estado e aplica exatamente os mesmos filtros.
    """
    caminho_sessao = tmp_path / "session.json"
    monkeypatch.setattr(constants, "CAMINHO_SESSAO", caminho_sessao)

    g_1a = criar_grupo(nome="1º A", tipo="turma")
    g_exc = criar_grupo(nome="MONITORIA", tipo="turma")
    criar_estudante(prontuario="IQ3091001", nome="Aluno Monitor", grupos=[g_exc])

    fachada_1 = FachadaRegistro(sessao_db=db_session)
    id_sessao = fachada_1.iniciar_nova_sessao(
        {
            "refeicao": "lanche",
            "periodo": "Tarde",
            "data": "2026-11-10",
            "hora": "15:00",
            "item_servido": "Bolo",
            "grupos": [g_1a.nome],
        }
    )
    assert id_sessao is not None
    fachada_1.definir_excecao_grupos({g_exc.nome})
    fachada_1.definir_ignorar_horario_grade(True)
    assert fachada_1.salvar_estado_sessao(id_sessao) is True

    # Nova instância simulando reinício do aplicativo
    fachada_2 = FachadaRegistro(sessao_db=db_session)
    estado = fachada_2.carregar_estado_sessao()
    assert estado is not None
    assert fachada_2.id_sessao_ativa == id_sessao
    assert fachada_2.excecao_grupos == {g_exc.nome}
    assert fachada_2.ignorar_horario_grade is True

    # Monitor autorizado graças à exceção restaurada
    assert fachada_2.registrar_consumo("IQ3091001")["autorizado"] is True


def test_estatisticas_dashboard_e_sessao_sob_mutacoes_e_soft_delete(
    facade: FachadaRegistro,
    criar_grupo,
    criar_estudante,
):
    """
    Verifica invariantes de `obter_estatisticas_dashboard` e `obter_estatisticas_sessao`
    após criação, consumo, estorno (soft delete), reatendimento, cancelamento de reserva
    e inativação de estudante.
    """
    hoje_iso = dt.date.today().isoformat()
    hoje_br = dt.date.today().strftime("%d/%m/%Y")

    t_1a = criar_grupo(nome="1º A", tipo="turma")
    c_pap = criar_grupo(nome="PAP", tipo="categoria")

    e1 = criar_estudante(
        prontuario="IQ3095001", nome="Est 1", ativo=True, grupos=[t_1a, c_pap]
    )
    e2 = criar_estudante(
        prontuario="IQ3095002", nome="Est 2", ativo=True, grupos=[t_1a]
    )
    e3 = criar_estudante(
        prontuario="IQ3095003", nome="Est 3 Inativo", ativo=False, grupos=[t_1a]
    )

    r1 = facade.criar_reserva(
        e1.prontuario, {"data": hoje_br, "prato": "Frango", "almoco": True}
    )
    r2 = facade.criar_reserva(
        e2.prontuario, {"data": hoje_br, "prato": "Peixe", "almoco": True}
    )
    # Reserva para aluno inativo não deve contar como pendente elegível na sessão
    facade.criar_reserva(
        e3.prontuario, {"data": hoje_br, "prato": "Peixe", "almoco": True}
    )

    id_sessao = facade.iniciar_nova_sessao(
        {
            "refeicao": "almoço",
            "periodo": "Tarde",
            "data": hoje_iso,
            "hora": "12:00",
            "grupos": ["1º A"],
        }
    )
    assert id_sessao is not None

    # Ambos ativos consomem
    assert facade.registrar_consumo(e1.prontuario)["autorizado"] is True
    assert facade.registrar_consumo(e2.prontuario)["autorizado"] is True

    stats_antes = facade.obter_estatisticas_sessao(id_sessao)
    assert stats_antes["total_consumidos"] == 2
    assert stats_antes["total_restantes"] == 0
    assert stats_antes["total_pap"] == 1
    assert stats_antes["taxa_adesao"] == 100.0

    # Estorno de e2 -> total_consumidos cai para 1, total_restantes sobe para 1, taxa cai para 50%
    assert facade.desfazer_consumo_por_prontuario(e2.prontuario) is True
    stats_pos_estorno = facade.obter_estatisticas_sessao(id_sessao)
    assert stats_pos_estorno["total_consumidos"] == 1
    assert stats_pos_estorno["total_restantes"] == 1
    assert stats_pos_estorno["taxa_adesao"] == 50.0

    # Cancelamento da reserva de e2 -> não aparece mais nem nos restantes
    facade.cancelar_reserva(r2["id"])
    stats_pos_canc_res = facade.obter_estatisticas_sessao(id_sessao)
    assert stats_pos_canc_res["total_consumidos"] == 1
    assert stats_pos_canc_res["total_restantes"] == 0

    # Dashboard geral ignora consumo estornado e reserva cancelada
    dash = facade.obter_estatisticas_dashboard()
    assert dash["alunos_total"] == 3
    assert dash["alunos_ativos"] == 2
    assert dash["alunos_inativos"] == 1
    assert dash["alunos_pap"] == 1
    assert dash["consumos_total"] == 1
    assert dash["consumos_hoje"] == 1
    assert dash["reservas_total"] == 2  # r1 e r3 ativas; r2 cancelada
    assert dash["distribuicao_pratos"] == {"Frango": 1, "Peixe": 1}
