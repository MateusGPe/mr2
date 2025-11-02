# --- Arquivo: registro/nucleo/repository.py ---

"""
Fornece implementações concretas do Padrão de Repositório, especializando
a classe CRUD genérica para cada modelo de dados da aplicação.
"""
from sqlalchemy.orm import Session

from registro.nucleo.crud import CRUD
from registro.nucleo.models import (Consumo, Estudante, Grupo, Reserva,
                                    Sessao)


class RepositorioEstudante(CRUD[Estudante]):
    """Repositório para operações CRUD com o modelo Estudante."""

    def __init__(self, sessao: Session):
        super().__init__(sessao, Estudante)

    def por_ids(self, ids: set[int]) -> list[Estudante]:
        """Retorna uma lista de estudantes cujos IDs estão na coleção fornecida."""
        return self._sessao_db.query(Estudante).filter(Estudante.id.in_(ids)).all()

    def por_prontuarios(self, prontuarios: set[str]) -> list[Estudante]:
        """Retorna uma lista de estudantes cujos prontuários estão na coleção fornecida."""
        return self._sessao_db.query(Estudante).filter(Estudante.prontuario.in_(prontuarios)).all()


class RepositorioReserva(CRUD[Reserva]):
    """Repositório para operações CRUD com o modelo Reserva."""

    def __init__(self, sessao: Session):
        super().__init__(sessao, Reserva)


class RepositorioSessao(CRUD[Sessao]):
    """Repositório para operações CRUD com o modelo Sessao."""

    def __init__(self, sessao: Session):
        super().__init__(sessao, Sessao)


class RepositorioConsumo(CRUD[Consumo]):
    """Repositório para operações CRUD com o modelo Consumo."""

    def __init__(self, sessao: Session):
        super().__init__(sessao, Consumo)


class RepositorioGrupo(CRUD[Grupo]):
    """Repositório para operações CRUD com o modelo Grupo."""

    def __init__(self, sessao: Session):
        super().__init__(sessao, Grupo)

    def por_nomes(self, nomes: set[str]) -> list[Grupo]:
        """Retorna uma lista de grupos cujos nomes estão na coleção fornecida."""
        return self._sessao_db.query(Grupo).filter(Grupo.nome.in_(nomes)).all()