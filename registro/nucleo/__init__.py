# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/__init__.py (Módulo Principal)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>


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
from registro.nucleo import service_logic

__all__ = [
    "FachadaRegistro",
    "DADOS_SESSAO",
    "ErroNucleoRegistro",
    "ErroSessao",
    "ErroSessaoNaoAtiva",
    "ErroImportacaoDados",
    "ErroAPIGoogle",
    "service_logic"
]
