"""
Fornece implementações concretas do Repository Pattern, especializando
a classe CRUD genérica para cada modelo de dados da aplicação.
"""

from typing import Any, Dict, List, Optional, Set

from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql import func

from registro.nucleo.crud import CRUD
from registro.nucleo.exceptions import RegistrationCoreError
from registro.nucleo.models import Reserve, Session as SessionModel, Students


class StudentRepository(CRUD[Students]):
    """Repositório para operações CRUD com o modelo Students."""

    def __init__(self, session: Session):
        super().__init__(session, Students)


class ReserveRepository(CRUD[Reserve]):
    """Repositório para operações CRUD com o modelo Reserve."""

    def __init__(self, session: Session):
        super().__init__(session, Reserve)

    def get_students_for_session_details(
        self,
        session_id: int,
        turmas_com_reserva: Set[str],
        turmas_sem_reserva: Set[str],
        consumed: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """
        Busca detalhes de alunos para uma sessão, aplicando uma lógica de
        elegibilidade baseada em dois conjuntos de turmas.

        A elegibilidade é definida como:
        - (Aluno pertence a uma turma COM reserva E possui uma reserva válida)
        OU
        - (Aluno pertence a uma turma SEM reserva)

        Args:
            session_id: O ID da sessão ativa.
            turmas_com_reserva: Conjunto de turmas onde a reserva é obrigatória.
            turmas_sem_reserva: Conjunto de turmas onde a reserva é opcional.
            consumed: Filtra pelo status de consumo (True, False, ou None).

        Returns:
            Uma lista de dicionários, cada um representando um aluno elegível.
        """
        s = aliased(Students, name="s")
        r = aliased(Reserve, name="r")

        try:
            query = (
                self._db_session.query(
                    s.pront.label("pront"),
                    s.nome.label("nome"),
                    s.turma.label("turma"),
                    s.translated_id.label("id"),
                    r.id.label("reserve_id"),
                    r.prato.label("prato"),
                    r.data.label("data"),
                    r.consumed.label("consumed"),
                    func.coalesce(r.registro_time, "").label("registro_time"),
                )
                .select_from(s)
                .outerjoin(r, (s.id == r.student_id) & (r.session_id == session_id))
            )

            # --- Construção da Lógica de Elegibilidade (WHERE) ---
            conditions = []
            # 1. Alunos de turmas COM reserva obrigatória:
            #    A turma deve estar na lista E a reserva deve existir (r.id IS NOT NULL).
            if turmas_com_reserva:
                conditions.append(
                    (s.turma.in_(turmas_com_reserva)) & (r.id.isnot(None))
                )

            # 2. Alunos de turmas SEM reserva obrigatória:
            #    Apenas a verificação de turma é suficiente.
            if turmas_sem_reserva:
                conditions.append(s.turma.in_(turmas_sem_reserva))

            if conditions:
                query = query.filter(or_(*conditions))
            else:
                # Se nenhuma turma foi selecionada, retorna uma lista vazia.
                return []

            # Filtro adicional de atividade do aluno
            query = query.filter(s.ativo.is_(True))

            # Filtro adicional por status de consumo (se especificado)
            if consumed is not None:
                if consumed is False:
                    # Inclui alunos com consumo falso E alunos sem reserva (r.id is NULL)
                    query = query.filter(
                        (r.consumed.is_(False)) | (r.id.is_(None))
                    )
                else:  # consumed is True
                    query = query.filter(r.consumed.is_(True))

            query = query.order_by(s.nome)
            return [row._asdict() for row in query.all()]

        except SQLAlchemyError as e:
            raise RegistrationCoreError(
                f"Erro de banco de dados ao buscar alunos para sessão {session_id}: {e}"
            ) from e


class SessionRepository(CRUD[SessionModel]):
    """Repositório para operações CRUD com o modelo Session."""

    def __init__(self, session: Session):
        super().__init__(session, SessionModel)
