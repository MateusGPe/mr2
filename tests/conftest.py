"""
Fixtures compartilhadas e configuração de testes para o projeto mr2.
Utiliza SQLite em memória isolado para cada teste e factories para entidades.
"""

from typing import Any, Callable, Dict, List, Optional
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from registro.nucleo.models import (
    Base,
    Consumo,
    Estudante,
    Grupo,
    Reserva,
    Sessao,
    SyncLog,
)
from registro.nucleo.facade import FachadaRegistro


@pytest.fixture
def db_engine():
    """Cria um engine SQLAlchemy em memória isolado com StaticPool."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Session:
    """Fornece uma sessão SQLAlchemy isolada para o banco em memória."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def facade(db_session: Session) -> FachadaRegistro:
    """Retorna uma instância da FachadaRegistro usando a sessão do banco em memória."""
    return FachadaRegistro(sessao_db=db_session)


@pytest.fixture
def repos(db_session: Session) -> Dict[str, Any]:
    """Agrupa todos os repositórios para facilitar injeção nos serviços."""
    from registro.nucleo.repository import (
        RepositorioConsumo,
        RepositorioEstudante,
        RepositorioGrupo,
        RepositorioReserva,
        RepositorioSessao,
    )

    return {
        "sessao": RepositorioSessao(db_session),
        "estudante": RepositorioEstudante(db_session),
        "grupo": RepositorioGrupo(db_session),
        "reserva": RepositorioReserva(db_session),
        "consumo": RepositorioConsumo(db_session),
    }



# --- Factories para criação de dados de teste ---


@pytest.fixture
def criar_grupo(db_session: Session) -> Callable[..., Grupo]:
    """Factory para criar instâncias de Grupo."""

    def _criar(nome: str = "1º A - INFO", ativo: bool = True) -> Grupo:
        grupo = Grupo(nome=nome, ativo=ativo)
        db_session.add(grupo)
        db_session.commit()
        db_session.refresh(grupo)
        return grupo

    return _criar


@pytest.fixture
def criar_estudante(db_session: Session) -> Callable[..., Estudante]:
    """Factory para criar instâncias de Estudante, opcionalmente com grupos."""

    def _criar(
        prontuario: str = "IQ3000001",
        nome: str = "Estudante Teste",
        ativo: bool = True,
        grupos: Optional[List[Grupo]] = None,
    ) -> Estudante:
        estudante = Estudante(prontuario=prontuario, nome=nome, ativo=ativo)
        if grupos:
            estudante.grupos.extend(grupos)
        db_session.add(estudante)
        db_session.commit()
        db_session.refresh(estudante)
        return estudante

    return _criar


@pytest.fixture
def criar_sessao(db_session: Session) -> Callable[..., Sessao]:
    """Factory para criar instâncias de Sessao de refeição."""

    def _criar(
        refeicao: str = "lanche",
        data: str = "21/10/2026",
        hora: str = "09:30",
        periodo: Optional[str] = "Manhã",
        item_servido: Optional[str] = "Suco e Biscoito",
        grupos: Optional[List[Grupo]] = None,
    ) -> Sessao:
        sessao = Sessao(
            refeicao=refeicao,
            data=data,
            hora=hora,
            periodo=periodo,
            item_servido=item_servido,
        )
        if grupos:
            sessao.grupos.extend(grupos)
        db_session.add(sessao)
        db_session.commit()
        db_session.refresh(sessao)
        return sessao

    return _criar


@pytest.fixture
def criar_reserva(db_session: Session) -> Callable[..., Reserva]:
    """Factory para criar instâncias de Reserva de almoço."""

    def _criar(
        estudante: Estudante,
        data: str = "21/10/2026",
        prato: Optional[str] = "Padrão",
        cancelada: bool = False,
    ) -> Reserva:
        reserva = Reserva(
            estudante_id=estudante.id,
            data=data,
            prato=prato,
            cancelada=cancelada,
        )
        db_session.add(reserva)
        db_session.commit()
        db_session.refresh(reserva)
        return reserva

    return _criar


@pytest.fixture
def criar_consumo(db_session: Session) -> Callable[..., Consumo]:
    """Factory para criar instâncias de Consumo."""

    def _criar(
        estudante: Estudante,
        sessao: Sessao,
        hora_consumo: str = "09:35:00",
        reserva: Optional[Reserva] = None,
    ) -> Consumo:
        consumo = Consumo(
            estudante_id=estudante.id,
            sessao_id=sessao.id,
            hora_consumo=hora_consumo,
            reserva_id=reserva.id if reserva else None,
        )
        db_session.add(consumo)
        db_session.commit()
        db_session.refresh(consumo)
        return consumo

    return _criar


# --- Fixtures com snippets realistas de CSV / dados de importação ---


@pytest.fixture
def csv_valido_padrao() -> str:
    """CSV bem formatado com colunas padrão de alunos."""
    return (
        "Prontuário,Nome,Turma\n"
        "IQ3000001,João da Silva,1º A - MEC\n"
        "IQ3000002,Maria Oliveira,1º B - MEC\n"
        "IQ3000003,Carlos Santos,2º A - MAC\n"
    )


@pytest.fixture
def csv_com_linhas_vazias_e_resumos() -> str:
    """
    CSV com linhas em branco, espaços e rodapé de resumo/turma sem prontuário
    (cenário comum nos relatórios reais que geravam logs de aviso).
    """
    return (
        "Matrícula;Nome;Turma\n"
        "IQ3001001;Lucas Ferreira;1º A - MAC\n"
        ";;\n"
        "  ;  ;  \n"
        "IQ3001002;Beatriz Souza;1º A - MAC\n"
        ";1º A - MAC;\n"
        ";Total de Alunos: 2;\n"
    )


@pytest.fixture
def csv_sem_cabecalho_explicito() -> str:
    """CSV onde os dados precisam de detecção heurística/regex de padrão."""
    return (
        "SP3012345,Fernanda Lima,3º A - MEC\n"
        "SP3098765,Gabriel Alves,3º B - MEC\n"
    )
