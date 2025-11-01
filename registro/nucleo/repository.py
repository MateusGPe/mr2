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
