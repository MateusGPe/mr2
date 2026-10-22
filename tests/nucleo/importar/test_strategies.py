"""
Testes unitários para estratégias de leitura de arquivo em registro.nucleo.importar.strategies.
"""

from pathlib import Path
import pytest

from registro.nucleo.importar.strategies import (
    CarregarCSVComCabecalho,
    CarregarCSVPosicional,
    CarregarListaSimples,
)
from registro.nucleo.exceptions import ErroImportacaoDados


def test_carregar_csv_com_cabecalho(tmp_path: Path):
    """Lê arquivo CSV padrão com cabeçalho mapeado."""
    csv_file = tmp_path / "alunos.csv"
    csv_file.write_text(
        "Matrícula,Nome,Turma\n"
        "IQ3001001,Lucas Silva,1º A - MEC\n"
        "IQ3001002,Maria Souza,1º B - MEC\n",
        encoding="utf-8",
    )

    estrategia = CarregarCSVComCabecalho()
    dados = estrategia.carregar(str(csv_file))

    assert len(dados) == 2
    assert dados[0]["prontuario"] == "IQ3001001"
    assert dados[0]["nome"] == "Lucas Silva"
    assert dados[1]["prontuario"] == "IQ3001002"


def test_carregar_lista_simples(tmp_path: Path):
    """Lê arquivo de lista simples separando prontuário e nome."""
    txt_file = tmp_path / "lista.txt"
    txt_file.write_text(
        "IQ3001001\n"
        "mariana oliveira\n"
        "\n"
        "IQ3001002\n",
        encoding="utf-8",
    )

    estrategia = CarregarListaSimples()
    dados = estrategia.carregar(str(txt_file))

    assert len(dados) == 3
    assert dados[0]["prontuario"] == "IQ3001001"
    assert dados[1]["nome"] == "Mariana Oliveira"
    assert dados[2]["prontuario"] == "IQ3001002"


def test_carregar_csv_posicional(tmp_path: Path):
    """Lê CSV sem cabeçalho identificando colunas por inferência vertical."""
    csv_file = tmp_path / "posicional.csv"
    csv_file.write_text(
        "IQ3001001,Carlos Silva,1º A - MEC\n"
        "IQ3001002,Ana Beatriz,1º A - MEC\n",
        encoding="utf-8",
    )

    estrategia = CarregarCSVPosicional()
    dados = estrategia.carregar(str(csv_file))

    assert len(dados) == 2
    assert dados[0]["prontuario"] == "IQ3001001"
    assert dados[0]["nome"] == "Carlos Silva"


def test_arquivo_inexistente_lanca_erro():
    """Tentar carregar arquivo que não existe deve levantar ErroImportacaoDados."""
    estrategia = CarregarCSVComCabecalho()
    with pytest.raises(ErroImportacaoDados):
        estrategia.carregar("arquivo_fantasma_inexistente.csv")

    with pytest.raises(ErroImportacaoDados):
        CarregarListaSimples().carregar("arquivo_fantasma_inexistente.txt")

    with pytest.raises(ErroImportacaoDados):
        CarregarCSVPosicional().carregar("arquivo_fantasma_inexistente.csv")


def test_carregar_csv_posicional_casos_borda(tmp_path: Path):
    """Testa arquivo vazio e arquivo com colunas indetectáveis no CSV posicional."""
    arq_vazio = tmp_path / "vazio.csv"
    arq_vazio.write_text("", encoding="utf-8")
    assert CarregarCSVPosicional().carregar(str(arq_vazio)) == []

    arq_indetectavel = tmp_path / "indetectavel.csv"
    arq_indetectavel.write_text("???,!!!\n###,$$$\n", encoding="utf-8")
    assert CarregarCSVPosicional().carregar(str(arq_indetectavel)) == []


def test_carregar_google_sheets():
    """Testa o carregamento de dados a partir do Google Sheets com mock."""
    from unittest.mock import MagicMock, patch
    from registro.nucleo.importar.strategies import CarregarGoogleSheets

    with patch("registro.nucleo.google_api_service.obter_planilha") as m_obter, \
         patch("registro.nucleo.google_api_service.buscar_valores_aba") as m_buscar:

        m_planilha = MagicMock()
        m_obter.return_value = m_planilha
        # Cabeçalho + 2 linhas de dados
        m_buscar.return_value = [
            ["Matrícula", "Nome", "Turma"],
            ["IQ3002001", "Julia Lima", "1º A - INFO"],
            ["IQ3002002", "Pedro Rocha", "1º A - INFO"],
        ]

        # Com sheet_key explícita
        estrategia = CarregarGoogleSheets()
        dados = estrategia.carregar("minha_chave_123:Aba1")
        assert len(dados) == 2
        assert dados[0]["prontuario"] == "IQ3002001"
        assert dados[1]["nome"] == "Pedro Rocha"
        m_obter.assert_called_with("minha_chave_123")

        # Com menos de 2 linhas
        m_buscar.return_value = [["Matrícula"]]
        assert estrategia.carregar("Aba2") == []

        # Com exceção de API
        m_buscar.side_effect = RuntimeError("Erro de conexão")
        with pytest.raises(ErroImportacaoDados, match="Erro no Google Sheets"):
            estrategia.carregar("Aba3")

