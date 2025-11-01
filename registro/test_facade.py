import json
import pytest
from unittest.mock import MagicMock, patch, ANY

# Importe as classes e exceções do seu projeto com o novo modelo
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
        yield facade
        facade.close()


@pytest.fixture
def active_facade(facade_instance):
    """
    Fixture que retorna uma instância da fachada com uma sessão já ativa (ID 123).
    Útil para todos os testes que requerem este estado.
    """
    facade_instance.active_session_id = 123
    return facade_instance

# --- Suítes de Testes ---

class TestFacadeLifecycle:
    """Testa a criação, destruição e o comportamento como gerenciador de contexto."""

    def test_facade_initialization(self, facade_instance):
        """Verifica se o estado inicial e os novos repositórios da fachada estão corretos."""
        assert facade_instance._estudante_repo is not None
        assert facade_instance._grupo_repo is not None
        assert facade_instance._reserva_repo is not None
        assert facade_instance._sessao_repo is not None
        assert facade_instance._consumo_repo is not None
        assert facade_instance.active_session_id is None
        assert facade_instance._db_session.is_active

    def test_facade_as_context_manager(self):
        """Testa o uso da fachada com 'with', garantindo que 'close' é chamado."""
        with patch('registro.nucleo.facade.create_database_and_tables'), \
                patch('registro.nucleo.models.create_engine') as mock_create_engine:

            from sqlalchemy import create_engine as sa_create_engine
            mock_create_engine.return_value = sa_create_engine("sqlite:///:memory:")

            with patch('registro.nucleo.facade.RegistroFacade.close') as mock_close:
                with RegistroFacade():
                    pass
                mock_close.assert_called_once()


@patch('registro.nucleo.facade.service_logic')
class TestFacadeSessionManagement:
    """Testa a criação, listagem e definição de sessões."""

    def test_start_new_session_updates_state(self, mock_service, facade_instance):
        """Verifica se iniciar uma sessão atualiza o active_session_id."""
        mock_service.start_new_session.return_value = 456
        session_data: SessionData = {
            "refeicao": "lanche",
            "item_servido": "Biscoito e suco",
            "periodo": "Matutino",
            "data": "2025-11-20",
            "hora": "09:30",
            "grupos": ["1A INFO", "1B AGRO"]
        }

        session_id = facade_instance.start_new_session(session_data)

        assert session_id == 456
        assert facade_instance.active_session_id == 456
        mock_service.start_new_session.assert_called_once_with(
            facade_instance._sessao_repo,
            facade_instance._grupo_repo,
            session_data
        )

    def test_list_all_sessions_passthrough(self, mock_service, facade_instance):
        """Verifica se a fachada repassa corretamente os dados do serviço."""
        expected_list = [{"id": 1}, {"id": 2, "data": "2025-11-20"}]
        mock_service.list_all_sessions.return_value = expected_list

        assert facade_instance.list_all_sessions() == expected_list
        mock_service.list_all_sessions.assert_called_once_with(facade_instance._sessao_repo)

    def test_set_active_session_updates_state(self, mock_service, facade_instance):
        """Caminho feliz: definir uma sessão ativa."""
        facade_instance.set_active_session(99)
        assert facade_instance.active_session_id == 99
        mock_service.get_session_details.assert_called_once_with(facade_instance._sessao_repo, 99)

    def test_set_active_session_propagates_error(self, mock_service, facade_instance):
        """Se a sessão não existe, a exceção do serviço é repassada."""
        mock_service.get_session_details.side_effect = SessionError("Sessão 999 não encontrada.")

        with pytest.raises(SessionError, match="Sessão 999 não encontrada."):
            facade_instance.set_active_session(999)
        assert facade_instance.active_session_id is None


@patch('registro.nucleo.facade.service_logic')
class TestFacadeActiveSessionOperations:
    """Testa todos os métodos que requerem uma sessão ativa."""

    def test_get_active_session_details_data_transformation(self, mock_service, active_facade):
        """Verifica a transformação de dados do novo modelo para o dicionário de resposta."""
        # Mock para os grupos relacionados
        mock_grupo1 = MagicMock()
        mock_grupo1.nome = "3A INFO"
        mock_grupo2 = MagicMock()
        mock_grupo2.nome = "3B AGRO"

        mock_model = MagicMock()
        mock_model.id = 123
        mock_model.refeicao, mock_model.periodo = "lanche", "Vespertino"
        mock_model.data, mock_model.hora = "2025-11-21", "15:30"
        mock_model.item_servido = "Pão com geleia"
        mock_model.grupos = [mock_grupo1, mock_grupo2]

        mock_service.get_session_details.return_value = mock_model

        details = active_facade.get_active_session_details()

        expected = {
            "id": 123, "refeicao": "lanche", "periodo": "Vespertino",
            "data": "2025-11-21", "hora": "15:30",
            "item_servido": "Pão com geleia",
            "grupos": ["3A INFO", "3B AGRO"]
        }
        assert details == expected

    @pytest.mark.parametrize("consumed_filter", [True, False, None])
    def test_get_students_for_session(self, mock_service, active_facade, consumed_filter):
        """Testa a chamada para buscar estudantes, verificando os novos argumentos."""
        active_facade.get_students_for_session(consumed=consumed_filter)
        mock_service.get_students_for_session.assert_called_once_with(
            session_repo=active_facade._sessao_repo,
            estudante_repo=active_facade._estudante_repo,
            reserva_repo=active_facade._reserva_repo,
            consumo_repo=active_facade._consumo_repo,
            session_id=123,
            consumed=consumed_filter
        )

    def test_register_consumption(self, mock_service, active_facade):
        """Testa o registro de consumo com a nova assinatura (prontuario)."""
        prontuario_aluno = "SP123456"
        expected_response = {"autorizado": True, "motivo": "Reserva encontrada"}
        mock_service.register_consumption.return_value = expected_response

        response = active_facade.register_consumption(prontuario_aluno)

        assert response == expected_response
        mock_service.register_consumption.assert_called_once_with(
            session_repo=active_facade._sessao_repo,
            estudante_repo=active_facade._estudante_repo,
            reserva_repo=active_facade._reserva_repo,
            consumo_repo=active_facade._consumo_repo,
            session_id=123,
            prontuario=prontuario_aluno
        )

    def test_update_session_groups(self, mock_service, active_facade):
        """Testa a atualização de grupos (substituto de 'turmas_config')."""
        novos_grupos = ["1A INFO", "1B INFO"]
        active_facade.update_session_groups(novos_grupos)
        mock_service.update_session_groups.assert_called_once_with(
            active_facade._sessao_repo,
            active_facade._grupo_repo,
            123,
            novos_grupos
        )

    def test_export_session_to_xlsx(self, mock_service, active_facade):
        """Testa a exportação com os novos repositórios."""
        active_facade.export_session_to_xlsx()
        mock_service.export_session_to_xlsx.assert_called_once_with(
            active_facade._sessao_repo,
            active_facade._consumo_repo,
            123
        )

    def test_sync_to_google_sheets(self, mock_service, active_facade):
        """Testa a sincronização 'para' o Google Sheets com os novos repositórios."""
        active_facade.sync_to_google_sheets()
        mock_service.sync_to_google_sheets.assert_called_once_with(
            active_facade._sessao_repo,
            active_facade._consumo_repo,
            123
        )


@patch('registro.nucleo.facade.service_logic')
class TestFacadeStateIndependentOperations:
    """Testa métodos que não dependem diretamente do estado active_session_id."""

    def test_undo_consumption(self, mock_service, facade_instance):
        """Testa o cancelamento de consumo com a nova assinatura (consumo_id)."""
        consumo_id_para_remover = 987
        facade_instance.undo_consumption(consumo_id_para_remover)
        mock_service.undo_consumption.assert_called_once_with(
            facade_instance._consumo_repo,
            consumo_id_para_remover
        )

    def test_sync_from_google_sheets(self, mock_service, facade_instance):
        """Testa a sincronização 'do' Google Sheets com o novo repositório de grupo."""
        facade_instance.sync_from_google_sheets()
        mock_service.sync_from_google_sheets.assert_called_once_with(
            facade_instance._estudante_repo,
            facade_instance._reserva_repo,
            facade_instance._grupo_repo
        )

    def test_sync_from_google_sheets_propagates_error(self, mock_service, facade_instance):
        """Testa a propagação de erro na sincronização 'do' Google."""
        mock_service.sync_from_google_sheets.side_effect = RegistrationCoreError("Erro de importação")
        with pytest.raises(RegistrationCoreError, match="Erro de importação"):
            facade_instance.sync_from_google_sheets()


# --- Teste Final de Robustez ---

@pytest.mark.parametrize("method_name, args", [
    ("get_active_session_details", ()),
    ("get_students_for_session", ()),
    ("update_session_groups", ([],)),
    ("export_session_to_xlsx", ()),
    ("sync_to_google_sheets", ()),
    ("register_consumption", ("some-prontuario",)), # Adicionado, pois agora requer sessão
])
def test_all_active_methods_raise_no_active_session_error(facade_instance, method_name, args):
    """
    Teste parametrizado que garante que TODOS os métodos que precisam de uma sessão
    ativa falham de forma previsível quando ela não existe.
    """
    facade_instance.active_session_id = None  # Garante o estado inicial

    method_to_test = getattr(facade_instance, method_name)

    with pytest.raises(NoActiveSessionError, match="Nenhuma sessão ativa definida."):
        method_to_test(*args)