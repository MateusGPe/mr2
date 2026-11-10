# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/models.py (Módulo de Modelos)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Define os modelos de dados SQLAlchemy que representam as tabelas do banco de
dados da aplicação de registro de refeições. Inclui tabelas para Estudantes,
Grupos (Turmas), Reservas, Sessoes e Consumos.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)


class Base(DeclarativeBase):
    """Base declarativa para os modelos do SQLAlchemy."""


associacao_estudante_grupo = Table(
    "associacao_estudante_grupo",
    Base.metadata,
    Column(
        "estudante_id",
        Integer,
        ForeignKey("estudantes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "grupo_id",
        Integer,
        ForeignKey("grupos.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

associacao_sessao_grupo = Table(
    "associacao_sessao_grupo",
    Base.metadata,
    Column(
        "sessao_id",
        Integer,
        ForeignKey("sessoes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "grupo_id",
        Integer,
        ForeignKey("grupos.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

associacao_reserva_grupo = Table(
    "associacao_reserva_grupo",
    Base.metadata,
    Column(
        "reserva_id",
        Integer,
        ForeignKey("reservas.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "grupo_id",
        Integer,
        ForeignKey("grupos.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Grupo(Base):
    """Representa um grupo (turma real ou categoria/tag) de estudantes."""

    __tablename__ = "grupos"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(
        String(20), default="turma", nullable=False, index=True
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)

    estudantes: Mapped[List["Estudante"]] = relationship(
        secondary=associacao_estudante_grupo, back_populates="grupos", lazy="select"
    )
    sessoes: Mapped[List["Sessao"]] = relationship(
        secondary=associacao_sessao_grupo, back_populates="grupos", lazy="select"
    )
    reservas: Mapped[List["Reserva"]] = relationship(
        secondary=associacao_reserva_grupo, back_populates="grupos", lazy="select"
    )

    @property
    def eh_categoria(self) -> bool:
        """Indica se o grupo representa uma categoria/tag (ex.: PAP, ESP1, LIB0)."""
        return (self.tipo or "turma").strip().lower() == "categoria"

    def __repr__(self) -> str:
        return f"<Grupo(id={self.id}, nome='{self.nome}', tipo='{self.tipo}')>"


class Estudante(Base):
    """Representa um estudante cadastrado no sistema."""

    __tablename__ = "estudantes"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    prontuario: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)

    grupos: Mapped[List["Grupo"]] = relationship(
        secondary=associacao_estudante_grupo, back_populates="estudantes", lazy="select"
    )
    reservas: Mapped[List["Reserva"]] = relationship(
        back_populates="estudante", lazy="select", cascade="all, delete-orphan"
    )
    consumos: Mapped[List["Consumo"]] = relationship(
        back_populates="estudante", lazy="select", cascade="all, delete-orphan"
    )

    @property
    def turmas_nomes(self) -> List[str]:
        """Retorna os nomes ordenados dos grupos do tipo 'turma' vinculados ao estudante."""
        return sorted(g.nome for g in self.grupos if not g.eh_categoria)

    @property
    def categorias_nomes(self) -> List[str]:
        """Retorna os nomes ordenados dos grupos do tipo 'categoria' vinculados ao estudante."""
        return sorted(g.nome for g in self.grupos if g.eh_categoria)

    def __repr__(self) -> str:
        return "<Estudante(id={}, prontuario='{}', nome='{}...')>".format(
            self.id, self.prontuario, self.nome[:30]
        )


class Reserva(Base):
    """Representa uma reserva de refeição (almoço e/ou jantar) feita por um estudante para uma data específica."""

    __tablename__ = "reservas"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    estudante_id: Mapped[int] = mapped_column(
        ForeignKey("estudantes.id", ondelete="RESTRICT"), index=True
    )
    prato: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    data: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    almoco: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False)
    jantar: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False)
    cancelada: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False)

    estudante: Mapped["Estudante"] = relationship(
        back_populates="reservas", lazy="joined"
    )
    grupos: Mapped[List["Grupo"]] = relationship(
        secondary=associacao_reserva_grupo, back_populates="reservas", lazy="select"
    )
    consumos: Mapped[List["Consumo"]] = relationship(
        back_populates="reserva", lazy="select"
    )

    @property
    def consumo(self) -> Optional["Consumo"]:
        """Retorna o consumo ativo mais recente vinculado à reserva (retrocompatibilidade)."""
        ativos = [c for c in self.consumos if getattr(c, "ativo", False)]
        if ativos:
            return ativos[0]
        return self.consumos[0] if self.consumos else None

    @property
    def categorias_nomes(self) -> List[str]:
        """Retorna os nomes ordenados das categorias vinculadas diretamente à reserva."""
        return sorted(g.nome for g in self.grupos if g.eh_categoria)

    __table_args__ = (
        UniqueConstraint(
            "estudante_id",
            "data",
            name="_estudante_data_uc",
            sqlite_on_conflict="IGNORE",
        ),
    )

    def __repr__(self) -> str:
        if self.cancelada:
            status = "Cancelada"
        elif self.almoco and self.jantar:
            status = "Almoço e Jantar"
        elif self.jantar:
            status = "Jantar"
        else:
            status = "Almoço"
        return (
            f"<Reserva(id={self.id}, estudante_id={self.estudante_id}, data='{self.data}', "
            f"tipo='{status}', prato='{self.prato}')>"
        )


class Sessao(Base):
    """Representa uma sessão de serviço de refeição."""

    __tablename__ = "sessoes"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    refeicao: Mapped[str] = mapped_column(String(50), nullable=False)
    periodo: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    data: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    hora: Mapped[str] = mapped_column(String(5), nullable=False)
    item_servido: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True)

    grupos: Mapped[List["Grupo"]] = relationship(
        secondary=associacao_sessao_grupo, back_populates="sessoes", lazy="select"
    )
    consumos: Mapped[List["Consumo"]] = relationship(
        back_populates="sessao", lazy="select", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "refeicao", "data", "hora", name="_sessao_data_hora_refeicao_uc"
        ),
    )

    def __repr__(self) -> str:
        item_repr = f", item='{self.item_servido}'" if self.item_servido else ""
        return (
            f"<Sessao(id={self.id}, refeicao='{self.refeicao}', "
            f"data='{self.data}', hora='{self.hora}'{item_repr})>"
        )


class Consumo(Base):
    """Representa o registro de consumo de uma refeição por um estudante."""

    __tablename__ = "consumos"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    estudante_id: Mapped[int] = mapped_column(
        ForeignKey("estudantes.id", ondelete="RESTRICT"), index=True
    )
    sessao_id: Mapped[int] = mapped_column(
        ForeignKey("sessoes.id", ondelete="RESTRICT"), index=True
    )
    hora_consumo: Mapped[str] = mapped_column(String(8), nullable=False)
    reserva_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("reservas.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    ativo: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    deletado_em: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deletado_por: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    motivo_cancelamento: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )

    estudante: Mapped["Estudante"] = relationship(
        back_populates="consumos", lazy="joined"
    )
    sessao: Mapped["Sessao"] = relationship(
        back_populates="consumos", lazy="joined")
    reserva: Mapped[Optional["Reserva"]] = relationship(
        back_populates="consumos", lazy="select"
    )

    __table_args__ = (
        Index(
            "uq_consumos_estudante_sessao_ativo",
            "estudante_id",
            "sessao_id",
            unique=True,
            sqlite_where=(Column("ativo") == True),
        ),
    )

    def __repr__(self) -> str:
        info_reserva = (
            f"reserva_id={self.reserva_id}"
            if self.reserva_id is not None
            else "sem_reserva=True"
        )
        return (
            f"<Consumo(id={self.id}, estudante_id={self.estudante_id}, sessao_id={self.sessao_id}, "
            f"hora='{self.hora_consumo}', {info_reserva})>"
        )


class SyncLog(Base):
    """Registra os eventos de sincronização com fontes de dados externas."""

    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[str] = mapped_column(String, nullable=False)
    direction: Mapped[str] = mapped_column(
        String(50), nullable=False)  # 'upload' or 'download'
    # 'success', 'failure', 'unknown'
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    records_affected: Mapped[Optional[int]
                             ] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<SyncLog(id={self.id}, timestamp='{self.timestamp}', "
            f"direction='{self.direction}', status='{self.status}')>"
        )


from registro.nucleo.constants import URL_BANCO_DADOS as URL_BANCO_DE_DADOS

motor = create_engine(
    URL_BANCO_DE_DADOS,
    connect_args={"check_same_thread": False},
)
SessaoLocal = sessionmaker(autocommit=False, autoflush=False, bind=motor)


def criar_banco_de_dados_e_tabelas():
    """Cria o banco de dados e todas as tabelas, se não existirem."""
    Base.metadata.create_all(bind=motor)
