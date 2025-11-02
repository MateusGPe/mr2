"""
Fornece implementações concretas do Repository Pattern, especializando
a classe CRUD genérica para cada modelo de dados da aplicação.
"""
from sqlalchemy.orm import Session

from registro.nucleo.crud import CRUD
from registro.nucleo.models import (Consumo, Estudante, Grupo, Reserva,
                                    Sessao)


class EstudanteRepository(CRUD[Estudante]):
    """Repositório para operações CRUD com o modelo Estudante."""

    def __init__(self, session: Session):
        super().__init__(session, Estudante)

    def por_id(self, ids: set[int]) -> list[Estudante]:
        """Retorna uma lista de estudantes cujos IDs estão na coleção fornecida."""
        return self._db_session.query(Estudante).filter(Estudante.id.in_(ids)).all()

    def por_prontuario(self, ids: set[str]) -> list[Estudante]:
        """Retorna uma lista de estudantes cujos IDs estão na coleção fornecida."""
        return self._db_session.query(Estudante).filter(Estudante.prontuario.in_(ids)).all()


class ReservaRepository(CRUD[Reserva]):
    """Repositório para operações CRUD com o modelo Reserva."""

    def __init__(self, session: Session):
        super().__init__(session, Reserva)


class SessaoRepository(CRUD[Sessao]):
    """Repositório para operações CRUD com o modelo Sessao."""

    def __init__(self, session: Session):
        super().__init__(session, Sessao)


class ConsumoRepository(CRUD[Consumo]):
    """Repositório para operações CRUD com o modelo Consumo."""

    def __init__(self, session: Session):
        super().__init__(session, Consumo)


class GrupoRepository(CRUD[Grupo]):
    """Repositório para operações CRUD com o modelo Grupo."""

    def __init__(self, session: Session):
        super().__init__(session, Grupo)

    def por_nomes(self, nomes: set[str]) -> list[Grupo]:
        """Retorna uma lista de grupos cujos nomes estão na coleção fornecida."""
        return self._db_session.query(Grupo).filter(Grupo.nome.in_(nomes)).all()
