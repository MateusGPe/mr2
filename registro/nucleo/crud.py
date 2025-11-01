"""
Fornece uma classe CRUD (Create, Read, Update, Delete) genérica para
interações com o banco de dados via SQLAlchemy.
"""

from typing import Any, Dict, Generic, List, Optional, Self, Sequence, Type, TypeVar, cast

from sqlalchemy import ColumnElement, insert, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.orm.mapper import Mapper

from registro.nucleo.models import Base

MODEL = TypeVar('MODEL', bound=Base)


class CRUD(Generic[MODEL]):
    """
    Classe base para operações CRUD usando SQLAlchemy.
    """

    def __init__(self: Self, session: DBSession, model: Type[MODEL]):
        """Inicializa o CRUD com a sessão de DB e o modelo."""
        self._db_session = session
        self._model = model
        pk_name = model.__mapper__.primary_key[0].name
        self._primary_key_column = getattr(self._model, pk_name)

    def get_session(self) -> DBSession:
        """Retorna a sessão do banco de dados associada."""
        return self._db_session

    def create(self: Self, data: Dict) -> MODEL:
        """
        Cria um novo registro, o adiciona à sessão e atualiza seu estado.
        A transação não é confirmada aqui.
        """
        db_item = self._model(**data)
        self._db_session.add(db_item)
        self._db_session.flush()
        self._db_session.refresh(db_item)
        return db_item

    def read_one(self: Self, item_id: int) -> Optional[MODEL]:
        """Lê um registro único pela sua chave primária."""
        return self._db_session.scalar(
            select(self._model).where(self._primary_key_column == item_id)
        )

    def read_filtered(self: Self, **filters: Any) -> Sequence[MODEL]:
        """Lê múltiplos registros com base em filtros."""
        query = select(self._model)
        where_clause = []
        for key, value in filters.items():
            column = getattr(self._model, key)
            if isinstance(value, ColumnElement):
                where_clause.append(value)
            else:
                where_clause.append(column == value)

        if where_clause:
            query = query.where(*where_clause)

        return self._db_session.scalars(query).all()

    def read_all(self: Self) -> Sequence[MODEL]:
        """Lê todos os registros de uma tabela."""
        return self._db_session.scalars(select(self._model)).all()

    def update(self: Self, item_id: int, row: Dict) -> Optional[MODEL]:
        """
        Atualiza um registro existente.
        A transação não é confirmada aqui.
        """
        item_to_update = self.read_one(item_id)
        if item_to_update:
            for key, value in row.items():
                setattr(item_to_update, key, value)
            self._db_session.flush()
            self._db_session.refresh(item_to_update)
        return item_to_update

    def delete(self: Self, item_id: int) -> bool:
        """
        Deleta um registro.
        A transação não é confirmada aqui.
        """
        item_to_delete = self.read_one(item_id)
        if item_to_delete:
            self._db_session.delete(item_to_delete)
            self._db_session.flush()
            return True
        return False

    def bulk_create(self: Self, rows: List[Dict]) -> bool:
        """Cria múltiplos registros em uma única operação."""
        try:
            if not rows:
                return True
            self._db_session.execute(insert(self._model), rows)
            return True
        except DBAPIError as e:
            print(f"Error during bulk insert of {type(self._model)}: {e}")
            return False

    def bulk_update(self: Self, rows: List[Dict]) -> bool:
        """Atualiza múltiplos registros em uma única operação."""
        try:
            if not rows:
                return True
            self._db_session.bulk_update_mappings(cast(Mapper[Any], self._model), rows)
            return True
        except DBAPIError as e:
            print(f"DB error during bulk update of {type(self._model)}: {e}")
            return False
