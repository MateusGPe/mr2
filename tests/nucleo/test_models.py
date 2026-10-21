"""
Testes unitários para os modelos SQLAlchemy e restrições de integridade em registro.nucleo.models.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from registro.nucleo.models import (
    Consumo,
    Estudante,
    Grupo,
    Reserva,
    Sessao,
    SyncLog,
)


def test_criar_estudante_e_grupo_relacionamento(
    db_session: Session, criar_estudante, criar_grupo
):
    """Verifica criação de estudante, grupo e associação n:m."""
    grupo = criar_grupo(nome="1º A - MEC")
    estudante = criar_estudante(
        prontuario="IQ3000010", nome="Aluno Teste", grupos=[grupo]
    )

    assert estudante.id is not None
    assert estudante.prontuario == "IQ3000010"
    assert len(estudante.grupos) == 1
    assert estudante.grupos[0].nome == "1º A - MEC"
    assert len(grupo.estudantes) == 1
    assert grupo.estudantes[0].prontuario == "IQ3000010"
    assert "Aluno Teste" in repr(estudante)
    assert "1º A - MEC" in repr(grupo)


def test_prontuario_duplicado_lanca_integridade(
    db_session: Session, criar_estudante
):
    """Verifica que o prontuário é único no banco."""
    criar_estudante(prontuario="IQ3000020", nome="Primeiro")

    with pytest.raises(IntegrityError):
        segundo = Estudante(prontuario="IQ3000020", nome="Segundo")
        db_session.add(segundo)
        db_session.commit()
    db_session.rollback()


def test_grupo_nome_duplicado_lanca_integridade(
    db_session: Session, criar_grupo
):
    """Verifica que o nome do grupo é único."""
    criar_grupo(nome="2º B - MEC")

    with pytest.raises(IntegrityError):
        segundo_grupo = Grupo(nome="2º B - MEC")
        db_session.add(segundo_grupo)
        db_session.commit()
    db_session.rollback()


def test_reserva_relacionamento_e_status(
    db_session: Session, criar_estudante, criar_reserva
):
    """Verifica integridade e representação da Reserva."""
    estudante = criar_estudante(prontuario="IQ3000030", nome="Carlos Almoço")
    reserva = criar_reserva(
        estudante=estudante, data="22/10/2026", prato="Vegetariano", cancelada=False
    )

    assert reserva.id is not None
    assert reserva.estudante.id == estudante.id
    assert "Vegetariano" in repr(reserva)
    assert "Almoço" in repr(reserva)

    reserva.cancelada = True
    db_session.commit()
    assert "Cancelada" in repr(reserva)


def test_sessao_e_consumo_fluxo(
    db_session: Session, criar_estudante, criar_sessao, criar_consumo
):
    """Verifica relacionamentos de Sessão e registro de Consumo."""
    estudante = criar_estudante(prontuario="IQ3000040", nome="Consumidor")
    sessao = criar_sessao(
        refeicao="lanche", data="22/10/2026", hora="10:00", item_servido="Maçã"
    )

    consumo = criar_consumo(
        estudante=estudante, sessao=sessao, hora_consumo="10:02:15"
    )

    assert consumo.id is not None
    assert consumo.estudante.prontuario == "IQ3000040"
    assert consumo.sessao.item_servido == "Maçã"
    assert "sem_reserva=True" in repr(consumo)
    assert "Maçã" in repr(sessao)


def test_synclog_criacao_e_repr(db_session: Session):
    """Verifica o modelo SyncLog."""
    log = SyncLog(
        timestamp="2026-10-21 18:00:00",
        direction="upload",
        status="success",
        message="Sincronização realizada com sucesso",
        records_affected=15,
    )
    db_session.add(log)
    db_session.commit()

    assert log.id is not None
    assert "<SyncLog(id=" in repr(log)
    assert "upload" in repr(log)
    assert "success" in repr(log)
