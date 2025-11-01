import json
import pytest
from unittest.mock import MagicMock, patch

# Importe as classes e exceções do seu projeto
from registro.nucleo.facade import RegistroFacade
from registro.nucleo.exceptions import NoActiveSessionError, SessionError
from registro.nucleo.models import Base, Students, Reserve, Session as SessionModel
from registro.nucleo.utils import SESSION as SessionData

# Mock para a função create_engine para usar um banco de dados em memória
# Isso garante que os testes não toquem em arquivos reais do disco


@patch('registro.nucleo.models.create_engine')
def test_facade_initialization(mock_create_engine):
    """Testa se a fachada é inicializada corretamente."""
    from sqlalchemy import create_engine as sa_create_engine
    # Configura o mock para retornar um engine de SQLite em memória
    mock_create_engine.return_value = sa_create_engine("sqlite:///:memory:")

    # Patch para evitar que a função real seja chamada durante o init
    with patch('registro.nucleo.facade.create_database_and_tables') as mock_create_db:
        facade = RegistroFacade()

        # Verifica se a criação do banco de dados foi chamada
        mock_create_db.assert_called_once()

        # Verifica se os repositórios foram instanciados
        assert facade._student_repo is not None
        assert facade._reserve_repo is not None
        assert facade._session_repo is not None

        # Verifica o estado inicial
        assert facade.active_session_id is None
        facade.close()

# Um fixture do pytest para criar uma fachada limpa para cada teste


@pytest.fixture
def facade_instance():
    """Cria uma instância da RegistroFacade com um DB em memória para testes."""
    with patch('registro.nucleo.facade.create_database_and_tables'), \
            patch('registro.nucleo.models.create_engine') as mock_create_engine:

        from sqlalchemy import create_engine as sa_create_engine
        mock_create_engine.return_value = sa_create_engine("sqlite:///:memory:")

        facade = RegistroFacade()
        # Garante que o banco seja fechado após o teste
        yield facade
        facade.close()


# --- Testes para Gerenciamento de Sessão ---

@patch('registro.nucleo.facade.service_logic')
def test_start_new_session(mock_service, facade_instance):
    """
    Testa o início de uma nova sessão.
    Verifica se a lógica de serviço é chamada e se o ID da sessão ativa é definido.
    """
    # Configura o mock para retornar um ID de sessão
    mock_service.start_new_session.return_value = 123

    session_data: SessionData = {
        "refeição": "Almoço", "lanche": "", "período": "Integral",
        "data": "2025-11-20", "hora": "12:00",
        "turmas_com_reserva": ["3A INFO"], "turmas_sem_reserva": ["2B AGRO"]
    }

    session_id = facade_instance.start_new_session(session_data)

    # Verifica se a função de serviço foi chamada com os argumentos corretos
    mock_service.start_new_session.assert_called_once_with(
        facade_instance._db_session,
        facade_instance._session_repo,
        facade_instance._reserve_repo,
        facade_instance._student_repo,
        session_data
    )
    # Verifica se o ID retornado está correto e se o estado da fachada foi atualizado
    assert session_id == 123
    assert facade_instance.active_session_id == 123


@patch('registro.nucleo.facade.service_logic')
def test_list_all_sessions(mock_service, facade_instance):
    """Testa a listagem de todas as sessões."""
    mock_service.list_all_sessions.return_value = [{"id": 1}, {"id": 2}]

    sessions = facade_instance.list_all_sessions()

    mock_service.list_all_sessions.assert_called_once_with(facade_instance._session_repo)
    assert sessions == [{"id": 1}, {"id": 2}]


@patch('registro.nucleo.facade.service_logic')
def test_set_active_session(mock_service, facade_instance):
    """Testa a definição de uma sessão ativa."""
    # O mock de get_session_details não precisa retornar nada,
    # apenas existir para provar que a validação foi chamada.

    facade_instance.set_active_session(99)

    mock_service.get_session_details.assert_called_once_with(facade_instance._session_repo, 99)
    assert facade_instance.active_session_id == 99


@patch('registro.nucleo.facade.service_logic')
def test_set_active_session_raises_error_if_not_found(mock_service, facade_instance):
    """Testa se um erro é levantado ao tentar ativar uma sessão inexistente."""
    mock_service.get_session_details.side_effect = SessionError("Não encontrada")

    with pytest.raises(SessionError, match="Não encontrada"):
        facade_instance.set_active_session(999)

    assert facade_instance.active_session_id is None


# --- Testes para Métodos que Requerem Sessão Ativa ---

class TestFacadeWithActiveSession:

    @pytest.fixture
    def active_facade(self, facade_instance):
        """Fixture que cria uma fachada e já define uma sessão ativa."""
        facade_instance.active_session_id = 1
        return facade_instance

    @patch('registro.nucleo.facade.service_logic')
    def test_get_active_session_details(self, mock_service, active_facade):
        """Testa a obtenção de detalhes da sessão ativa."""
        mock_session_model = MagicMock()
        mock_session_model.id = 1
        mock_session_model.refeicao = "Almoço"
        mock_session_model.periodo = "Integral"
        mock_session_model.data = "2025-11-20"
        mock_session_model.hora = "12:00"
        # O modelo do banco de dados armazena um JSON como string
        mock_session_model.turmas_config = json.dumps({
            "com_reserva": ["3A INFO"], "sem_reserva": []
        })

        mock_service.get_session_details.return_value = mock_session_model

        details = active_facade.get_active_session_details()

        mock_service.get_session_details.assert_called_once_with(active_facade._session_repo, 1)
        expected_details = {
            "id": 1, "refeicao": "Almoço", "periodo": "Integral",
            "data": "2025-11-20", "hora": "12:00",
            "turmas_com_reserva": ["3A INFO"], "turmas_sem_reserva": []
        }
        assert details == expected_details

    # Testando as combinações de filtro para get_students_for_session
    @pytest.mark.parametrize("consumed_filter, expected_call_arg", [
        (None, None),
        (True, True),
        (False, False),
    ])
    @patch('registro.nucleo.facade.service_logic')
    def test_get_students_for_session_combinations(
            self, mock_service, active_facade, consumed_filter, expected_call_arg):
        """Testa a busca de estudantes com diferentes filtros de consumo."""
        mock_service.get_students_for_session.return_value = [{"nome": "Aluno Teste"}]

        students = active_facade.get_students_for_session(consumed=consumed_filter)

        mock_service.get_students_for_session.assert_called_once_with(
            active_facade._reserve_repo,
            active_facade._session_repo,
            1,  # active_session_id
            expected_call_arg
        )
        assert students == [{"nome": "Aluno Teste"}]

    @patch('registro.nucleo.facade.service_logic')
    def test_update_session_turmas_config(self, mock_service, active_facade):
        """Testa a atualização da configuração de turmas."""
        com_reserva = ["Nova Turma A"]
        sem_reserva = ["Nova Turma B"]

        active_facade.update_session_turmas_config(com_reserva, sem_reserva)

        mock_service.update_session_turmas_config.assert_called_once_with(
            active_facade._db_session,
            active_facade._session_repo,
            1,
            com_reserva,
            sem_reserva
        )

    @patch('registro.nucleo.facade.service_logic')
    def test_sync_to_google_sheets(self, mock_service, active_facade):
        """Testa a sincronização para o Google Sheets."""
        active_facade.sync_to_google_sheets()
        mock_service.sync_to_google_sheets.assert_called_once_with(
            active_facade._reserve_repo, active_facade._session_repo, 1
        )

    @patch('registro.nucleo.facade.service_logic')
    def test_export_session_to_xlsx(self, mock_service, active_facade):
        """Testa a exportação para XLSX."""
        mock_service.export_session_to_xlsx.return_value = "/path/to/file.xlsx"

        filepath = active_facade.export_session_to_xlsx()

        mock_service.export_session_to_xlsx.assert_called_once_with(
            active_facade._reserve_repo, active_facade._session_repo, 1
        )
        assert filepath == "/path/to/file.xlsx"

# --- Testes para Métodos que NÃO Requerem Sessão Ativa (mas podem falhar sem ela) ---


@patch('registro.nucleo.facade.service_logic')
def test_sync_from_google_sheets(mock_service, facade_instance):
    """Testa a sincronização do Google Sheets."""
    facade_instance.sync_from_google_sheets()
    mock_service.sync_from_google_sheets.assert_called_once_with(
        facade_instance._db_session,
        facade_instance._student_repo,
        facade_instance._reserve_repo
    )


@patch('registro.nucleo.facade.service_logic')
def test_register_and_undo_consumption(mock_service, facade_instance):
    """Testa o registro e o cancelamento de consumo."""
    reserve_id = 42

    # Teste de registro
    facade_instance.register_consumption(reserve_id)
    mock_service.register_consumption.assert_called_once_with(
        facade_instance._db_session, facade_instance._reserve_repo, reserve_id
    )

    # Teste de cancelamento
    facade_instance.undo_consumption(reserve_id)
    mock_service.undo_consumption.assert_called_once_with(
        facade_instance._db_session, facade_instance._reserve_repo, reserve_id
    )


# --- Testes de Erro para Métodos que Requerem Sessão Ativa ---

@pytest.mark.parametrize("method_name, args", [
    ("get_active_session_details", ()),
    ("get_students_for_session", ()),
    ("update_session_turmas_config", ([], [])),
    ("export_session_to_xlsx", ()),
    ("sync_to_google_sheets", ()),
])
def test_methods_raise_no_active_session_error(facade_instance, method_name, args):
    """
    Testa de forma parametrizada se todos os métodos que precisam de uma
    sessão ativa levantam NoActiveSessionError quando nenhuma está definida.
    """
    # Garante que não há sessão ativa
    facade_instance.active_session_id = None

    method_to_test = getattr(facade_instance, method_name)

    with pytest.raises(NoActiveSessionError, match="Nenhuma sessão ativa definida."):
        method_to_test(*args)
