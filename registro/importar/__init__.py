"""
Pacote responsável pela importação assistida de dados.

Expõe a fachada principal e os tipos de dados necessários para a
construção da Interface de Usuário (GUI).
"""

from .definitions import (
    CandidatoMatch,
    ItemRevisao,
    ResolucaoUsuario,
    ResumoImportacao,
    TipoConflito,
)
from .exceptions import ErroImportacao, ErroSessaoImportacao
from .facade import FachadaImportacao

__all__ = [
    "FachadaImportacao",
    "ItemRevisao",
    "CandidatoMatch",
    "ResolucaoUsuario",
    "ResumoImportacao",
    "TipoConflito",
    "ErroImportacao",
    "ErroSessaoImportacao",
]