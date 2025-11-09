# --- Arquivo: registro/nucleo/repository.py ---

"""
Fornece implementações concretas do Padrão de Repositório, especializando
a classe CRUD genérica para cada modelo de dados da aplicação.
"""
from typing import List, Set

from sqlalchemy.orm import Session, selectinload

from registro.nucleo.crud import CRUD
from registro.nucleo.models import Consumo, Estudante, Grupo, Reserva, Sessao


class RepositorioEstudante(CRUD[Estudante]):
    """Repositório para operações CRUD com o modelo Estudante."""

    def __init__(self, sessao: Session):
        super().__init__(sessao, Estudante)

    def por_ids(self, ids: Set[int]) -> List[Estudante]:
        """Retorna uma lista de estudantes cujos IDs estão na coleção fornecida."""
        if not ids:
            return []
        return self._sessao_db.query(Estudante).filter(Estudante.id.in_(ids)).all()

    def por_prontuarios(self, prontuarios: Set[str]) -> List[Estudante]:
        """Retorna uma lista de estudantes cujos prontuários estão na coleção."""
        if not prontuarios:
            return []
        return (
            self._sessao_db.query(Estudante)
            .filter(Estudante.prontuario.in_(prontuarios))
            .all()
        )

    def ler_todos_com_grupos(self) -> List[Estudante]:
        """Lê todos os estudantes, carregando seus grupos de forma otimizada."""
        return (
            self._sessao_db.query(Estudante)
            .options(selectinload(Estudante.grupos))
            .all()
        )

    def por_prontuarios_com_grupos(self, prontuarios: Set[str]) -> List[Estudante]:
        """Busca estudantes por prontuário, carregando seus grupos de forma otimizada."""
        if not prontuarios:
            return []
        return (
            self._sessao_db.query(Estudante)
            .filter(Estudante.prontuario.in_(prontuarios))
            .options(selectinload(Estudante.grupos))
            .all()
        )


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

    def por_prontuario_e_sessao(
        self, prontuario: str, id_sessao: int
    ) -> Consumo | None:
        """Retorna um consumo baseado no prontuário do estudante e na sessão."""
        return (
            self._sessao_db.query(Consumo)
            .join(Estudante)
            .filter(Estudante.prontuario == prontuario, Consumo.sessao_id == id_sessao)
            .one_or_none()
        )


class RepositorioGrupo(CRUD[Grupo]):
    """Repositório para operações CRUD com o modelo Grupo."""

    def __init__(self, sessao: Session):
        super().__init__(sessao, Grupo)

    def por_nomes(self, nomes: Set[str]) -> List[Grupo]:
        """Retorna uma lista de grupos cujos nomes estão na coleção fornecida."""
        if not nomes:
            return []
        return self._sessao_db.query(Grupo).filter(Grupo.nome.in_(nomes)).all()