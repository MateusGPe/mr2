# --- Arquivo: registro/importar/facade.py ---

"""
Fornece uma Fachada de alto nível para interagir com o subsistema de
importação de dados.
"""

from typing import Dict, List, Optional

from registro.importar.definitions import AcaoFinal, LinhaAnalisada
from registro.importar.service import ServicoImportacao
from registro.importar.strategies import CarregarCSVDetalhado, CarregarCSVSeguro, CarregarCSVSimples
from registro.nucleo.facade import FachadaRegistro


class FachadaImportacao:
    """
    Interface simplificada para o sistema de importação assistida de dados.
    """

    def __init__(self, fachada_nucleo: FachadaRegistro):
        """Inicializa a Fachada com acesso ao núcleo do sistema."""
        self._servico = ServicoImportacao(fachada_nucleo)

    def analisar_arquivo_csv(
        self, caminho_arquivo: str, detalhado: bool
    ) -> List[LinhaAnalisada]:
        """
        Cria a estratégia de carregamento apropriada para um CSV e inicia a
        análise, retornando o resultado para revisão do usuário.

        Args:
            caminho_arquivo: O caminho para o arquivo .csv ou .txt.
            detalhado: Se True, espera um CSV com cabeçalho. Se False, espera
                       um arquivo de texto simples com um nome por linha.
        """
        estrategia = CarregarCSVSeguro() if detalhado else CarregarCSVSimples()
        return self._servico.iniciar_analise(estrategia, caminho_arquivo)

    def obter_estado_analise(self) -> List[LinhaAnalisada]:
        """Retorna a lista de linhas no estado atual da análise."""
        return self._servico.obter_linhas_analisadas()

    def resolver_linha(
        self,
        id_linha: int,
        acao: AcaoFinal,
        id_estudante_escolhido: Optional[int] = None,
    ):
        """
        Define a ação final para uma linha, com base na interação do usuário.

        Args:
            id_linha: O ID da linha a ser atualizada.
            acao: A ação final a ser executada ('CRIAR_RESERVA', 'IGNORAR', etc.).
            id_estudante_escolhido: Se a ação requer um estudante existente (por
                                    exemplo, resolvendo uma ambiguidade), este
                                    é o ID do estudante selecionado.
        """
        self._servico.atualizar_acao_linha(id_linha, acao, id_estudante_escolhido)

    def executar(self) -> Dict[str, int]:
        """
        Finaliza a sessão de importação, executando todas as ações definidas
        e persistindo os dados no banco. Retorna um resumo do que foi feito.
        """
        return self._servico.executar_importacao()
