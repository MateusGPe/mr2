# ----------------------------------------------------------------------------
# Arquivo: cards.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Atalho principal para inicialização do utilitário de geração de crachás e
cartões com QR Code em folha A4 (exportação em PDF vetorial e HTML).
Delega a execução para a interface gráfica em `registro.cards.app`.
"""

import sys
from pathlib import Path

# Adiciona o diretório raiz ao path caso executado isoladamente
sys.path.insert(0, str(Path(__file__).resolve().parent))

from registro.cards.app import main

if __name__ == "__main__":
    main()
