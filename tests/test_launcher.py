# ----------------------------------------------------------------------------
# Arquivo: tests/test_launcher.py
# ----------------------------------------------------------------------------
"""
Testes unitários para o módulo despachante e inicializador unificado (registro.launcher).
"""

from unittest.mock import MagicMock, patch
import pytest

from registro.launcher import (
    executar_autoatendimento,
    executar_painel,
    executar_registrar,
    identificar_alvo_cli,
    main,
)


def test_identificar_alvo_cli_painel():
    for flag in ["--painel", "/painel", "-painel", "painel", "/PAINEL"]:
        alvo = identificar_alvo_cli([flag])
        assert alvo == executar_painel


def test_identificar_alvo_cli_autoatendimento():
    for flag in ["--auto", "/auto", "-auto", "auto", "--autoatendimento", "/autoatendimento", "/AUTO"]:
        alvo = identificar_alvo_cli([flag])
        assert alvo == executar_autoatendimento


def test_identificar_alvo_cli_registrar():
    for flag in ["--reg", "/reg", "-reg", "reg", "--registrar", "/registrar", "/REG"]:
        alvo = identificar_alvo_cli([flag])
        assert alvo == executar_registrar


def test_identificar_alvo_cli_ajuda():
    with pytest.raises(SystemExit) as exc_info:
        with patch("registro.launcher.exibir_ajuda") as mock_ajuda:
            identificar_alvo_cli(["--help"])
            mock_ajuda.assert_called_once()
    assert exc_info.value.code == 0


def test_identificar_alvo_cli_vazio():
    assert identificar_alvo_cli([]) is None
    assert identificar_alvo_cli(["--flag-desconhecida"]) is None


def test_executar_modulos():
    with patch("registro.gui.registrar.app.main") as mock_registrar:
        executar_registrar()
        mock_registrar.assert_called_once()

    with patch("registro.gui.painel.app.main") as mock_painel:
        executar_painel()
        mock_painel.assert_called_once()

    with patch("registro.gui.autoatendimento.app.main") as mock_auto:
        executar_autoatendimento()
        mock_auto.assert_called_once()


def test_main_com_argumentos():
    with patch("sys.argv", ["registro", "--painel"]):
        with patch("registro.launcher.executar_painel") as mock_painel:
            main()
            mock_painel.assert_called_once()


def test_main_sem_argumentos():
    with patch("sys.argv", ["registro"]):
        mock_alvo = MagicMock()
        with patch("registro.launcher.abrir_menu_inicial", return_value=mock_alvo):
            main()
            mock_alvo.assert_called_once()
