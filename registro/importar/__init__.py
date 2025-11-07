# --- Arquivo: registro/importar/__init__.py ---

"""
Pacote para a funcionalidade de importação assistida de dados.

Expõe a `FachadaImportacao` como ponto de entrada principal e os tipos
de dados necessários para a interação com a camada de apresentação.
"""

from .definitions import AcaoFinal, LinhaAnalisada, StatusAnalise, SugestaoMatch
from .exceptions import ErroImportacao, ErroSessaoImportacao
from .facade import FachadaImportacao

__all__ = [
    "FachadaImportacao",
    "LinhaAnalisada",
    "StatusAnalise",
    "AcaoFinal",
    "SugestaoMatch",
    "ErroImportacao",
    "ErroSessaoImportacao",
]
