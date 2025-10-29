"""
Fornece uma Facade de alto nível para interagir com o subsistema
registro_core.

Qualquer aplicação cliente deve interagir exclusivamente com a classe
RegistroFacade, que gerencia internamente a sessão do banco de dados e a
lógica de serviço.
"""

from typing import Any, Dict, List, Optional

from registro.nucleo.exceptions import NoActiveSessionError
from registro.nucleo.models import SessionLocal, create_database_and_tables
from registro.nucleo.service import RegistroService
from registro.nucleo.utils import SESSION as SessionData


class RegistroFacade:
    """
    Interface simplificada para o sistema de registro de refeições.
    """

    def __init__(self):
        """
        Inicializa a Facade, configurando a conexão com o banco de dados
        e instanciando a camada de serviço interna.
        """
        create_database_and_tables()
        self._db_session = SessionLocal()
        self._service = RegistroService(self._db_session)
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
        """
        Inicia uma nova sessão de refeição e a define como ativa.

        Retorna o ID da sessão criada.
        """
        session_id = self._service.start_new_session(session_data)
        self.active_session_id = session_id
        return session_id

    def list_all_sessions(self) -> List[Dict]:
        """Retorna uma lista simplificada de todas as sessões."""
        return self._service.list_all_sessions()

    def set_active_session(self, session_id: int):
        """Define uma sessão existente como ativa pelo seu ID."""
        self._service.set_active_session(session_id)
        self.active_session_id = session_id

    def get_active_session_details(self) -> Dict[str, Any]:
        """
        Retorna um dicionário com os detalhes da sessão ativa.
        """
        if self.active_session_id is None:
            raise NoActiveSessionError("Nenhuma sessão ativa definida.")
        session_model = self._service.get_active_session_details(self.active_session_id)
        return {
            "id": session_model.id,
            "refeicao": session_model.refeicao,
            "periodo": session_model.periodo,
            "data": session_model.data,
            "hora": session_model.hora,
            "turmas": session_model.turmas  # Mantido como JSON string
        }

    def get_students_for_session(
        self, consumed: Optional[bool] = None
    ) -> List[Dict]:
        """
        Retorna estudantes para a sessão ativa, com opção de filtro por consumo.
        - consumed=True: Apenas os que já se serviram.
        - consumed=False: Apenas os que ainda não se serviram.
        - consumed=None: Todos.
        """
        if self.active_session_id is None:
            raise NoActiveSessionError("Nenhuma sessão ativa definida.")
        return self._service.get_students_for_session(self.active_session_id, consumed)

    def register_consumption(self, reserve_id: int) -> bool:
        """Registra que um estudante consumiu uma refeição."""
        return self._service.register_consumption(reserve_id)

    def undo_consumption(self, reserve_id: int):
        """Desfaz o registro de consumo de uma refeição."""
        self._service.undo_consumption(reserve_id)

    def update_session_classes(self, classes: List[str]):
        """Atualiza a lista de turmas para a sessão ativa."""
        if self.active_session_id is None:
            raise NoActiveSessionError("Nenhuma sessão ativa definida.")
        self._service.update_session_classes(self.active_session_id, classes)

    def export_session_to_xlsx(self) -> str:
        """
        Exporta os dados de consumo da sessão ativa para um arquivo XLSX.

        Retorna o caminho completo do arquivo salvo.
        """
        if self.active_session_id is None:
            raise NoActiveSessionError("Nenhuma sessão ativa definida.")
        return self._service.export_session_to_xlsx(self.active_session_id)

    def sync_from_google_sheets(self):
        """
        Sincroniza a base de dados local a partir de uma planilha do
        Google Sheets.
        """
        self._service.sync_from_google_sheets()

    def sync_to_google_sheets(self):
        """
        Envia os dados de consumo da sessão ativa para a planilha do
        Google Sheets.
        """
        if self.active_session_id is None:
            raise NoActiveSessionError("Nenhuma sessão ativa definida.")
        self._service.sync_to_google_sheets(self.active_session_id)
