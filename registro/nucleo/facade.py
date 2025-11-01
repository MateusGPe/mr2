"""
Fornece uma Facade de alto nível para interagir com o subsistema
registro_core.

Qualquer aplicação cliente deve interagir exclusivamente com a classe
RegistroFacade, que gerencia internamente a sessão do banco de dados,
os repositórios e a lógica de serviço.
"""

from typing import Any, Dict, List, Optional

from registro.nucleo import service_logic
from registro.nucleo.exceptions import NoActiveSessionError
from registro.nucleo.models import (Consumo, Estudante, Grupo, Reserva, Sessao,
                                    SessionLocal,
                                    create_database_and_tables)
from registro.nucleo.repository import (ConsumoRepository, EstudanteRepository,
                                        GrupoRepository, ReservaRepository,
                                        SessaoRepository)
from registro.nucleo.utils import SESSION as SessionData


class RegistroFacade:
    """
    Interface simplificada para o sistema de registro de refeições.
    """

    def __init__(self):
        """
        Inicializa a Facade, configurando a conexão com o banco de dados
        e instanciando os repositórios.
        """
        create_database_and_tables()
        self._db_session = SessionLocal()

        self._estudante_repo = EstudanteRepository(self._db_session)
        self._reserva_repo = ReservaRepository(self._db_session)
        self._sessao_repo = SessaoRepository(self._db_session)
        self._consumo_repo = ConsumoRepository(self._db_session)
        self._grupo_repo = GrupoRepository(self._db_session)

        self.active_session_id: Optional[int] = None

    def close(self):
        """Fecha a conexão com o banco de dados."""
        self._db_session.close()

    def __enter__(self):
        """Permite o uso da Facade como um gerenciador de contexto."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Garante que a conexão com o banco de dados seja fechada."""
        self.close()

    def start_new_session(self, session_data: SessionData) -> Optional[int]:
        """Inicia uma nova sessão de refeição e a define como ativa."""
        session_id = service_logic.start_new_session(
            self._sessao_repo, self._grupo_repo, session_data
        )
        self.active_session_id = session_id
        return session_id

    def list_all_sessions(self) -> List[Dict]:
        """Retorna uma lista simplificada de todas as sessões."""
        return service_logic.list_all_sessions(self._sessao_repo)

    def set_active_session(self, session_id: int):
        """Define uma sessão existente como ativa pelo seu ID."""
        service_logic.get_session_details(self._sessao_repo, session_id)
        self.active_session_id = session_id

    def get_active_session_details(self) -> Dict[str, Any]:
        """Retorna um dicionário com os detalhes da sessão ativa."""
        if self.active_session_id is None:
            raise NoActiveSessionError("Nenhuma sessão ativa definida.")
        session_model = service_logic.get_session_details(self._sessao_repo,
                                                          self.active_session_id)
        return {
            "id": session_model.id,
            "refeicao": session_model.refeicao,
            "periodo": session_model.periodo,
            "data": session_model.data,
            "hora": session_model.hora,
            "item_servido": session_model.item_servido,
            "grupos": [g.nome for g in session_model.grupos]
        }

    def get_students_for_session(self, consumed: Optional[bool] = None) -> List[Dict]:
        """Retorna estudantes para a sessão ativa, com opção de filtro por consumo."""
        if self.active_session_id is None:
            raise NoActiveSessionError("Nenhuma sessão ativa definida.")
        return service_logic.get_students_for_session(
            session_repo=self._sessao_repo,
            estudante_repo=self._estudante_repo,
            reserva_repo=self._reserva_repo,
            consumo_repo=self._consumo_repo,
            session_id=self.active_session_id,
            consumed=consumed
        )

    def register_consumption(self, prontuario: str) -> Dict[str, Any]:
        """Registra que um estudante consumiu uma refeição, seguindo as regras de autorização."""
        if self.active_session_id is None:
            raise NoActiveSessionError("Nenhuma sessão ativa definida.")
        return service_logic.register_consumption(
            session_repo=self._sessao_repo,
            estudante_repo=self._estudante_repo,
            reserva_repo=self._reserva_repo,
            consumo_repo=self._consumo_repo,
            session_id=self.active_session_id,
            prontuario=prontuario
        )

    def undo_consumption(self, consumo_id: int):
        """Desfaz o registro de consumo de uma refeição."""
        service_logic.undo_consumption(self._consumo_repo, consumo_id)

    def update_session_groups(self, grupos: List[str]):
        """Atualiza a configuração de grupos para a sessão ativa."""
        if self.active_session_id is None:
            raise NoActiveSessionError("Nenhuma sessão ativa definida.")
        service_logic.update_session_groups(
            self._sessao_repo, self._grupo_repo, self.active_session_id,
            grupos
        )

    def export_session_to_xlsx(self) -> str:
        """Exporta os dados de consumo da sessão ativa para um arquivo XLSX."""
        if self.active_session_id is None:
            raise NoActiveSessionError("Nenhuma sessão ativa definida.")
        return service_logic.export_session_to_xlsx(
            self._sessao_repo, self._consumo_repo, self.active_session_id
        )

    def sync_from_google_sheets(self):
        """Sincroniza a base de dados local a partir de uma planilha do Google Sheets."""
        service_logic.sync_from_google_sheets(
            self._estudante_repo, self._reserva_repo, self._grupo_repo
        )

    def sync_to_google_sheets(self):
        """Envia os dados de consumo da sessão ativa para a planilha do Google Sheets."""
        if self.active_session_id is None:
            raise NoActiveSessionError("Nenhuma sessão ativa definida.")
        service_logic.sync_to_google_sheets(
            self._sessao_repo, self._consumo_repo, self.active_session_id
        )
