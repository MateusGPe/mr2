# --- Arquivo: registro/nucleo/__init__.py ---

"""
Pacote principal da lógica de negócio para o sistema de registro de refeições.

Este pacote expõe a classe `FachadaRegistro` como a única interface
pública para interação com o sistema, além dos tipos de dados e exceções
necessários.
"""

from registro.nucleo.exceptions import (
    ErroAPIGoogle,
    ErroImportacaoDados,
    ErroNucleoRegistro,
    ErroSessao,
    ErroSessaoNaoAtiva,
)
from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.utils import DADOS_SESSAO

__all__ = [
    "FachadaRegistro",
    "DADOS_SESSAO",
    "ErroNucleoRegistro",
    "ErroSessao",
    "ErroSessaoNaoAtiva",
    "ErroImportacaoDados",
    "ErroAPIGoogle",
]
