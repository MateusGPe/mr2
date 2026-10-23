# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/__init__.py (Módulo Principal)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>


"""
Pacote principal da lógica de negócio para o sistema de registro de refeições.

Este pacote expõe a classe `FachadaRegistro` como a interface pública
unificada para interação com o sistema, além dos tipos de dados e exceções
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
