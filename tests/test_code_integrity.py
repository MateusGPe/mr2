# ----------------------------------------------------------------------------
# Arquivo: tests/test_code_integrity.py
# ----------------------------------------------------------------------------
"""
Testes de integridade de código e análise estática.

Garante que o código não contenha erros de sintaxe (E9), referências a nomes
indefinidos (F821), símbolos ausentes em __all__ (F822) ou variáveis locais
não atribuídas (F823), e que todos os módulos do projeto sejam importáveis.
"""

import importlib
import pkgutil
import subprocess
import sys
from pathlib import Path
import pytest


def test_ruff_static_code_integrity():
    """Garante que a verificação estática do Ruff (E9, F821, F822, F823) passe com zero erros."""
    raiz = Path(__file__).parent.parent
    resultado = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "."],
        cwd=raiz,
        capture_output=True,
        text=True,
    )
    assert (
        resultado.returncode == 0
    ), f"Ruff encontrou erros de integridade/referências indefinidas:\n{resultado.stdout}\n{resultado.stderr}"


def test_importabilidade_de_todos_os_modulos():
    """Garante que todos os submódulos dentro do pacote 'registro' possam ser importados sem erro."""
    import registro

    prefixo = f"{registro.__name__}."
    modulos_falhos = []

    for _, mod_name, _ in pkgutil.walk_packages(registro.__path__, prefix=prefixo):
        try:
            importlib.import_module(mod_name)
        except Exception as e:
            modulos_falhos.append((mod_name, str(e)))

    assert not modulos_falhos, f"Falha ao importar os seguintes módulos:\n{modulos_falhos}"
