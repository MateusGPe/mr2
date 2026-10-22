# ----------------------------------------------------------------------------
# Arquivo: registro/importar/facade.py (Fachada de Importação)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Fachada do subsistema de importação.
Ponto único de acesso para a interface gráfica.
"""

from typing import Any, Dict, List, Optional

from registro.importar.definitions import ItemRevisao
from registro.importar.service import ServicoImportacao
from registro.importar.strategies import (
    CarregarCSVComCabecalho,
    CarregarCSVPosicional,
    CarregarGoogleSheets,
    CarregarListaSimples,
)
from registro.nucleo.facade import FachadaRegistro


class FachadaImportacao:
    """Interface pública para o fluxo de importação."""

    def __init__(self, fachada_nucleo: FachadaRegistro):
        self._servico = ServicoImportacao(fachada_nucleo)

    def analisar_arquivo(self, caminho: str, tipo: str = "auto") -> Dict[str, Any]:
        """
        Carrega e analisa um arquivo.
        Retorna resumo e lista de itens para revisão manual.

        Args:
            caminho: Path do arquivo.
            tipo: 'simples' (txt), 'header' (csv c/ header), 'sheets', ou 'auto'.
        """
        if tipo == "simples":
            estrategia = CarregarListaSimples()
        elif tipo == "header":
            estrategia = CarregarCSVComCabecalho()
        elif tipo == "sheets":
            estrategia = CarregarGoogleSheets()
        else:
            estrategia = CarregarCSVPosicional()

        return self._servico.preparar_importacao(estrategia, caminho)

    def simular_importacao(
        self,
        itens_revisados: List[ItemRevisao],
        valores_padrao: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, List[Dict]]:
        """Gera preview da importação sem salvar."""
        return self._servico.simular_importacao(itens_revisados, valores_padrao)

    def confirmar_importacao(
        self,
        itens_resolvidos: List[ItemRevisao],
        valores_padrao: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, int]:
        """
        Finaliza a importação aplicando as decisões do usuário e valores padrão.
        """
        return self._servico.finalizar_importacao(itens_resolvidos, valores_padrao)
