"""Exceções customizadas para a camada de serviço."""


class RegistrationCoreError(Exception):
    """Classe base para exceções neste módulo."""


class SessionError(RegistrationCoreError):
    """Erro relacionado ao gerenciamento de sessões de refeição."""


class NoActiveSessionError(SessionError):
    """
    Erro para quando uma operação requer uma sessão ativa,
    mas não há nenhuma.
    """


class DataImportError(RegistrationCoreError):
    """Erro durante a importação de dados de arquivos (CSV, etc.)."""


class GoogleAPIError(RegistrationCoreError):
    """Erro na comunicação com as APIs do Google (Sheets, Drive)."""
