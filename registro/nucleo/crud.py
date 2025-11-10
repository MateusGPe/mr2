# --- Arquivo: registro/nucleo/crud.py ---

"""
Fornece uma classe CRUD (Create, Read, Update, Delete) genérica para
interações com o banco de dados via SQLAlchemy.
"""

from typing import Any, Dict, Generic, List, Optional, Self, Sequence, Type, TypeVar

from sqlalchemy import ColumnElement, insert, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session as DBSession

from registro.nucleo.models import Base

MODELO = TypeVar("MODELO", bound=Base)


class CRUD(Generic[MODELO]):
    """
    Classe base para operações CRUD usando SQLAlchemy.
    """

    def __init__(self: Self, sessao: DBSession, modelo: Type[MODELO]):
        """Inicializa o CRUD com a sessão de DB e o modelo."""
        self._sessao_db = sessao
        self._modelo = modelo
        nome_pk = modelo.__mapper__.primary_key[0].name
        self._coluna_chave_primaria = getattr(self._modelo, nome_pk)

    def obter_sessao(self) -> DBSession:
        """Retorna a sessão do banco de dados associada."""
        return self._sessao_db

    def criar(self: Self, dados: Dict[str, Any]) -> MODELO:
        """
        Cria um novo registro, o adiciona à sessão e atualiza seu estado.
        A transação não é confirmada aqui.
        """
        item_db = self._modelo(**dados)
        self._sessao_db.add(item_db)
        self._sessao_db.flush()
        self._sessao_db.refresh(item_db)
        return item_db

    def ler_um(
        self: Self, id_item: int, opcoes_carregamento: Optional[List] = None
    ) -> Optional[MODELO]:
        """Lê um registro único pela sua chave primária, com opções de carregamento."""
        consulta = select(self._modelo).where(self._coluna_chave_primaria == id_item)
        if opcoes_carregamento:
            consulta = consulta.options(*opcoes_carregamento)
        return self._sessao_db.scalar(consulta)

    def ler_filtrado(
        self: Self, opcoes_carregamento: Optional[List] = None, **filtros: Any
    ) -> Sequence[MODELO]:
        """Lê múltiplos registros com base em filtros e com opções de carregamento."""
        consulta = select(self._modelo)
        if opcoes_carregamento:
            consulta = consulta.options(*opcoes_carregamento)

        clausula_where = []
        for chave, valor in filtros.items():
            coluna = getattr(self._modelo, chave)
            if isinstance(valor, ColumnElement):
                clausula_where.append(valor)
            else:
                clausula_where.append(coluna == valor)

        if clausula_where:
            consulta = consulta.where(*clausula_where)

        return self._sessao_db.scalars(consulta).all()

    def ler_todos(self: Self) -> Sequence[MODELO]:
        """Lê todos os registros de uma tabela."""
        return self._sessao_db.scalars(select(self._modelo)).all()

    def atualizar(self: Self, id_item: int, linha: Dict[str, Any]) -> Optional[MODELO]:
        """
        Atualiza um registro existente.
        A transação não é confirmada aqui.
        """
        item_para_atualizar = self.ler_um(id_item)
        if item_para_atualizar:
            for chave, valor in linha.items():
                setattr(item_para_atualizar, chave, valor)
            self._sessao_db.flush()
            self._sessao_db.refresh(item_para_atualizar)
        return item_para_atualizar

    def deletar(self: Self, id_item: int) -> bool:
        """
        Deleta um registro.
        A transação não é confirmada aqui.
        """
        item_para_deletar = self.ler_um(id_item)
        if item_para_deletar:
            self._sessao_db.delete(item_para_deletar)
            self._sessao_db.flush()
            return True
        return False

    def criar_em_massa(self: Self, linhas: List[Dict[str, Any]]) -> bool:
        """Cria múltiplos registros em uma única operação."""
        if not linhas:
            return True
        try:
            self._sessao_db.execute(insert(self._modelo), linhas)
            return True
        except DBAPIError as e:
            print(
                f"Erro de banco de dados durante a inserção em massa de {type(self._modelo)}: {e}"
            )
            return False

    def atualizar_em_massa(self: Self, linhas: List[Dict[str, Any]]) -> bool:
        """Atualiza múltiplos registros em uma única operação."""
        if not linhas:
            return True
        try:
            self._sessao_db.bulk_update_mappings(self._modelo, linhas)  # type: ignore
            return True
        except DBAPIError as e:
            print(
                "Erro de banco de dados durante a atualização em massa de "
                f"{type(self._modelo)}: {e}"
            )
            return False
