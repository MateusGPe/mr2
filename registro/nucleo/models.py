"""
Define os modelos de dados SQLAlchemy para a aplicação: Students, Reserve
e Session.
"""
import re
from typing import List, Optional

from sqlalchemy import (Boolean, ForeignKey, Integer, String, UniqueConstraint,
                        create_engine)
from sqlalchemy.orm import (DeclarativeBase, Mapped, mapped_column,
                            relationship, sessionmaker)

TRANSLate_dict = str.maketrans("0123456789Xx", "abcdefghijkk")
REMOVE_IQ = re.compile(r"[Ii][Qq]\d0+")


def to_code(text: str) -> str:
    """Traduz o prontuário para um código de busca simplificado."""
    text = REMOVE_IQ.sub("", text)
    translated = text.translate(TRANSLate_dict)
    return " ".join(translated)


class Base(DeclarativeBase):
    """Base declarativa para os modelos do SQLAlchemy."""


class Students(Base):
    """Representa a tabela de estudantes no banco de dados."""
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    pront: Mapped[str] = mapped_column(String)
    nome: Mapped[str] = mapped_column(String)
    turma: Mapped[str] = mapped_column(String)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)

    reserves: Mapped[List["Reserve"]] = relationship(
        back_populates="student"
    )

    @property
    def translated_id(self) -> str:
        """Retorna o ID traduzido (código simplificado) do prontuário."""
        return to_code(self.pront)

    __table_args__ = (
        UniqueConstraint(
            "pront", name="_pront_uc", sqlite_on_conflict="REPLACE"
        ),
    )


class Reserve(Base):
    """Representa a tabela de reservas de refeições."""
    __tablename__ = "reserve"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    prato: Mapped[Optional[str]] = mapped_column(String)
    data: Mapped[str] = mapped_column(String)
    snacks: Mapped[bool] = mapped_column(Boolean, default=False)
    reserved: Mapped[bool] = mapped_column(Boolean, default=False)
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("session.id")
    )
    registro_time: Mapped[Optional[str]] = mapped_column(String)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    canceled: Mapped[bool] = mapped_column(Boolean, default=False)

    student: Mapped["Students"] = relationship(
        back_populates="reserves"
    )
    session: Mapped["Session"] = relationship(
        back_populates="reserves"
    )

    __table_args__ = (
        UniqueConstraint(
            "student_id", "data", "snacks", name="_reserve_uc",
            sqlite_on_conflict="REPLACE"
        ),
    )


class Session(Base):
    """Representa uma sessão de serviço de refeição (um evento)."""
    __tablename__ = "session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    refeicao: Mapped[str] = mapped_column(String)
    periodo: Mapped[str] = mapped_column(String)
    data: Mapped[str] = mapped_column(String)
    hora: Mapped[str] = mapped_column(String)
    turmas: Mapped[str] = mapped_column(String)

    reserves: Mapped[List["Reserve"]] = relationship(
        back_populates="session"
    )

    __table_args__ = (
        UniqueConstraint(
            'refeicao', 'periodo', 'data', 'hora', 'turmas', name="_session_uc",
            sqlite_on_conflict="REPLACE"
        ),
    )


DATABASE_URL = "sqlite:///./config/registro.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_database_and_tables():
    """Cria o banco de dados e todas as tabelas, se não existirem."""
    Base.metadata.create_all(bind=engine)
