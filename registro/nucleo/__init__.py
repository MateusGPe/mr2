"""
Pacote principal da lógica de negócio para o sistema de registro de refeições.

Este pacote expõe a classe `RegistroFacade` como a única interface
pública para interação com o sistema, além dos tipos de dados e exceções
necessários.
"""

from registro.nucleo.exceptions import (DataImportError, GoogleAPIError, NoActiveSessionError,
                                        RegistrationCoreError, SessionError)
from registro.nucleo.facade import RegistroFacade
from registro.nucleo.utils import SESSION as SessionData

__all__ = [
    'RegistroFacade',
    'SessionData',
    'RegistrationCoreError',
    'SessionError',
    'NoActiveSessionError',
    'DataImportError',
    'GoogleAPIError',
]