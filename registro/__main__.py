# ----------------------------------------------------------------------------
# Arquivo: registro/__main__.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Ponto de entrada principal da aplicação de registro de refeições.

Executa o despachante principal (launcher), que suporta flags de linha
de comando ou exibe o menu gráfico de seleção entre os módulos.
"""

from registro.launcher import main

if __name__ == "__main__":
    main()

