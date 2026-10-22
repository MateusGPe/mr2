"""
Testes unitários para a classe FachadaImportacao em registro.nucleo.importar.facade.
"""

from unittest.mock import MagicMock
import pytest

from registro.nucleo.importar.facade import FachadaImportacao
from registro.nucleo.importar.strategies import (
    CarregarCSVComCabecalho,
    CarregarCSVPosicional,
    CarregarGoogleSheets,
    CarregarListaSimples,
)
from registro.nucleo.facade import FachadaRegistro


def test_fachada_importacao_analisar_arquivo_tipos():
    """Testa a seleção da estratégia correta com base no parâmetro 'tipo'."""
    mock_fachada_nucleo = MagicMock(spec=FachadaRegistro)
    fachada_imp = FachadaImportacao(mock_fachada_nucleo)
    fachada_imp._servico = MagicMock()

    # simples
    fachada_imp.analisar_arquivo("caminho/lista.txt", tipo="simples")
    args, _ = fachada_imp._servico.preparar_importacao.call_args
    assert isinstance(args[0], CarregarListaSimples)
    assert args[1] == "caminho/lista.txt"

    # header
    fachada_imp.analisar_arquivo("caminho/dados.csv", tipo="header")
    args, _ = fachada_imp._servico.preparar_importacao.call_args
    assert isinstance(args[0], CarregarCSVComCabecalho)

    # sheets
    fachada_imp.analisar_arquivo("caminho/planilha.json", tipo="sheets")
    args, _ = fachada_imp._servico.preparar_importacao.call_args
    assert isinstance(args[0], CarregarGoogleSheets)

    # auto / default -> CarregarCSVPosicional
    fachada_imp.analisar_arquivo("caminho/outro.csv", tipo="auto")
    args, _ = fachada_imp._servico.preparar_importacao.call_args
    assert isinstance(args[0], CarregarCSVPosicional)


def test_fachada_importacao_simular_e_confirmar():
    """Testa a deleção de simular_importacao e confirmar_importacao para o serviço."""
    mock_fachada_nucleo = MagicMock(spec=FachadaRegistro)
    fachada_imp = FachadaImportacao(mock_fachada_nucleo)
    fachada_imp._servico = MagicMock()

    itens = [{"dados": {}, "resolucao_escolhida": "CRIAR_NOVO"}]
    valores_padrao = {"data": "21/10/2026"}

    # Simular
    fachada_imp.simular_importacao(itens, valores_padrao)
    fachada_imp._servico.simular_importacao.assert_called_once_with(itens, valores_padrao)

    # Confirmar
    fachada_imp.confirmar_importacao(itens, valores_padrao)
    fachada_imp._servico.finalizar_importacao.assert_called_once_with(itens, valores_padrao)
