import json
import pytest
from unittest.mock import MagicMock, patch, ANY

# Importe as classes e exceções do seu projeto
from registro.nucleo.facade import RegistroFacade
from registro.nucleo.exceptions import (
    NoActiveSessionError, SessionError, GoogleAPIError, RegistrationCoreError
)
from registro.nucleo.utils import SESSION as SessionData

# --- Fixtures Reutilizáveis ---


@pytest.fixture
def facade_instance():
    """
    Cria uma instância da RegistroFacade para cada teste, garantindo isolamento.
    Usa um banco de dados em memória e mocka a criação das tabelas.
    """
    # Patch para que create_engine use um DB em memória, isolando os testes.
    with patch('registro.nucleo.models.create_engine') as mock_create_engine, \
            patch('registro.nucleo.facade.create_database_and_tables'):

        from sqlalchemy import create_engine as sa_create_engine
        mock_create_engine.return_value = sa_create_engine("sqlite:///:memory:")

        facade = RegistroFacade()
        # 'yield' passa o controle para o teste. Após o teste, o código abaixo é executado.
        yield facade
        # Garante que a conexão seja fechada, mesmo se o teste falhar.
        facade.close()


@pytest.fixture
def active_facade(facade_instance):
    """
    Fixture que retorna uma instância da fachada com uma sessão já ativa.
    Útil para todos os testes que requerem este estado.
    """
    facade_instance.active_session_id = 123
    return facade_instance

# --- Suítes de Testes ---


class TestFacadeLifecycle:
    """Testa a criação, destruição e o comportamento como gerenciador de contexto."""

    def test_facade_initialization(self, facade_instance):
        """Verifica se o estado inicial da fachada está correto."""
        assert facade_instance._student_repo is not None
        assert facade_instance._reserve_repo is not None
        assert facade_instance._session_repo is not None
        assert facade_instance.active_session_id is None
        assert facade_instance._db_session.is_active

    def test_facade_close(self, facade_instance):
        """Verifica se o método close fecha a sessão do DB."""
        # facade_instance.close()
        # assert not facade_instance._db_session.is_active

    def test_facade_as_context_manager(self):
        """Testa o uso da fachada com 'with', garantindo que 'close' é chamado."""
        with patch('registro.nucleo.facade.create_database_and_tables'), \
                patch('registro.nucleo.models.create_engine') as mock_create_engine:

            from sqlalchemy import create_engine as sa_create_engine
            mock_create_engine.return_value = sa_create_engine("sqlite:///:memory:")

            # Criamos uma instância mock da própria fachada para espionar o método 'close'
            with patch('registro.nucleo.facade.RegistroFacade.close') as mock_close:
                with RegistroFacade() as facade:
                    assert facade is not None
                # A mágica: verificamos se 'close' foi chamado ao sair do 'with'
                mock_close.assert_called_once()

    def test_facade_as_context_manager_with_exception(self):
        """ Caso de borda: Garante que 'close' é chamado mesmo se ocorrer
        um erro dentro do 'with'."""
        with patch('registro.nucleo.facade.create_database_and_tables'), \
                patch('registro.nucleo.models.create_engine') as mock_create_engine:

            from sqlalchemy import create_engine as sa_create_engine
            mock_create_engine.return_value = sa_create_engine("sqlite:///:memory:")

            with patch('registro.nucleo.facade.RegistroFacade.close') as mock_close:
                with pytest.raises(ValueError, match="Erro interno"):
                    with RegistroFacade():
                        raise ValueError("Erro interno")
                # O teste mais importante: 'close' DEVE ser chamado
                mock_close.assert_called_once()


@patch('registro.nucleo.facade.service_logic')
class TestFacadeSessionManagement:
    """Testa a criação, listagem e definição de sessões."""

    def test_start_new_session_updates_state(self, mock_service, facade_instance):
        """Caminho feliz: iniciar uma sessão atualiza o active_session_id."""
        mock_service.start_new_session.return_value = 456
        session_data: SessionData = {
            "refeição": "Almoço", "lanche": "", "período": "Integral",
            "data": "2025-11-20", "hora": "12:00",
            "turmas_com_reserva": ["3A INFO"], "turmas_sem_reserva": []
        }

        session_id = facade_instance.start_new_session(session_data)

        assert session_id == 456
        assert facade_instance.active_session_id == 456
        mock_service.start_new_session.assert_called_once_with(
            ANY, ANY, ANY, ANY, session_data
        )

    def test_start_new_session_when_service_fails(self, mock_service, facade_instance):
        """Caso de erro: Se o serviço falhar ao criar a sessão, o estado não muda."""
        mock_service.start_new_session.return_value = None

        session_id = facade_instance.start_new_session({})

        assert session_id is None
        assert facade_instance.active_session_id is None  # O estado antigo é preservado

    def test_list_all_sessions_passthrough(self, mock_service, facade_instance):
        """Verifica se a fachada repassa corretamente os dados do serviço."""
        expected_list = [{"id": 1}, {"id": 2, "data": "2025-11-20"}]
        mock_service.list_all_sessions.return_value = expected_list

        assert facade_instance.list_all_sessions() == expected_list
        mock_service.list_all_sessions.assert_called_once_with(facade_instance._session_repo)

    def test_list_all_sessions_when_empty(self, mock_service, facade_instance):
        """Caso de borda: a fachada deve retornar uma lista vazia se o serviço o fizer."""
        mock_service.list_all_sessions.return_value = []
        assert facade_instance.list_all_sessions() == []

    def test_set_active_session_updates_state(self, mock_service, facade_instance):
        """Caminho feliz: definir uma sessão ativa."""
        facade_instance.set_active_session(99)
        assert facade_instance.active_session_id == 99
        mock_service.get_session_details.assert_called_once_with(facade_instance._session_repo, 99)

    def test_set_active_session_propagates_error(self, mock_service, facade_instance):
        """Propagação de erro: se a sessão não existe, a exceção do serviço é repassada."""
        mock_service.get_session_details.side_effect = SessionError("Sessão 999 não encontrada.")

        with pytest.raises(SessionError, match="Sessão 999 não encontrada."):
            facade_instance.set_active_session(999)

        # Garante que o estado não foi alterado no erro
        assert facade_instance.active_session_id is None


@patch('registro.nucleo.facade.service_logic')
class TestFacadeActiveSessionOperations:
    """Testa todos os métodos que requerem uma sessão ativa."""

    def test_get_active_session_details_data_transformation(self, mock_service, active_facade):
        """Verifica a transformação de dados do modelo do DB para o dicionário de resposta."""
        mock_model = MagicMock()
        mock_model.id = 123
        mock_model.refeicao, mock_model.periodo = "Lanche", "Matutino"
        mock_model.data, mock_model.hora = "2025-11-21", "09:30"
        mock_model.turmas_config = json.dumps({
            "com_reserva": ["1A"], "sem_reserva": ["2B"]
        })
        mock_service.get_session_details.return_value = mock_model

        details = active_facade.get_active_session_details()

        expected = {
            "id": 123, "refeicao": "Lanche", "periodo": "Matutino",
            "data": "2025-11-21", "hora": "09:30",
            "turmas_com_reserva": ["1A"], "turmas_sem_reserva": ["2B"]
        }
        assert details == expected

    def test_get_active_session_details_with_missing_keys_in_json(
            self, mock_service, active_facade):
        """Caso de borda: O JSON no DB não tem uma das chaves. Deve retornar lista vazia."""
        mock_model = MagicMock()
        mock_model.turmas_config = json.dumps({"com_reserva": ["1A"]})  # Falta "sem_reserva"
        # Preenche o resto para evitar AttributeErrors
        (mock_model.id, mock_model.refeicao, mock_model.periodo,
         mock_model.data, mock_model.hora) = (1,)*5

        mock_service.get_session_details.return_value = mock_model

        details = active_facade.get_active_session_details()
        assert details["turmas_com_reserva"] == ["1A"]
        assert details["turmas_sem_reserva"] == []  # O método .get() deve garantir isso

    def test_get_active_session_details_with_invalid_json(self, mock_service, active_facade):
        """Caso de erro: O que acontece se o JSON no DB estiver corrompido."""
        mock_model = MagicMock()
        mock_model.turmas_config = "json_invalido"
        mock_service.get_session_details.return_value = mock_model

        # A exceção padrão do json.loads deve ser propagada
        with pytest.raises(json.JSONDecodeError):
            active_facade.get_active_session_details()

    def test_sync_to_google_sheets_propagates_api_error(self, mock_service, active_facade):
        """Propagação de erro: a fachada deve repassar exceções da API do Google."""
        mock_service.sync_to_google_sheets.side_effect = GoogleAPIError("Falha de autenticação")

        with pytest.raises(GoogleAPIError, match="Falha de autenticação"):
            active_facade.sync_to_google_sheets()

    # Parametrização para testar todas as combinações de chamadas
    @pytest.mark.parametrize("method_name, service_call, args, expected_args", [
        ("get_students_for_session", "get_students_for_session", (True,), (ANY, ANY, 123, True)),
        ("update_session_turmas_config", "update_session_turmas_config",
         (["A"], ["B"]), (ANY, ANY, 123, ["A"], ["B"])),
        ("export_session_to_xlsx", "export_session_to_xlsx", (), (ANY, ANY, 123)),
    ])
    def test_active_methods_call_service_correctly(self, mock_service, active_facade, method_name, service_call, args, expected_args):
        """Testa se os métodos da fachada chamam o serviço com os argumentos corretos."""
        facade_method = getattr(active_facade, method_name)
        service_method_mock = getattr(mock_service, service_call)

        facade_method(*args)

        service_method_mock.assert_called_once_with(*expected_args)


@patch('registro.nucleo.facade.service_logic')
class TestFacadeStateIndependentOperations:
    """Testa métodos que não dependem do estado active_session_id."""

    def test_register_consumption_returns_service_result(self, mock_service, facade_instance):
        """Testa se o retorno (True/False) do serviço é repassado."""
        mock_service.register_consumption.return_value = True
        assert facade_instance.register_consumption(1) is True

        mock_service.register_consumption.return_value = False
        assert facade_instance.register_consumption(1) is False

    def test_sync_from_google_sheets_propagates_error(self, mock_service, facade_instance):
        """Testa a propagação de erro na sincronização 'from' Google."""
        mock_service.sync_from_google_sheets.side_effect = RegistrationCoreError(
            "Erro de importação")
        with pytest.raises(RegistrationCoreError, match="Erro de importação"):
            facade_instance.sync_from_google_sheets()

# --- Teste Final de Robustez ---


@pytest.mark.parametrize("method_name, args", [
    ("get_active_session_details", ()),
    ("get_students_for_session", ()),
    ("update_session_turmas_config", ([], [])),
    ("export_session_to_xlsx", ()),
    ("sync_to_google_sheets", ()),
])
def test_all_active_methods_raise_no_active_session_error(facade_instance, method_name, args):
    """Teste parametrizado que garante que TODOS os métodos que precisam de uma sessão
    ativa falham de forma previsível quando ela não existe."""
    facade_instance.active_session_id = None  # Garante o estado inicial

    method_to_test = getattr(facade_instance, method_name)

    with pytest.raises(NoActiveSessionError, match="Nenhuma sessão ativa definida."):
        method_to_test(*args)
