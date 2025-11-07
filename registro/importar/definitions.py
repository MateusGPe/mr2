# --- Arquivo: registro/nucleo/importers/definitions.py ---

"""
Define tipos de dados, constantes e estruturas para o submódulo de importação.
Centralizar essas definições torna o código mais legível e fácil de manter.
"""

from typing import Dict, List, Literal, Optional, TypedDict

# Status possíveis para uma linha durante a análise da importação
StatusAnalise = Literal[
    "ERRO", "MATCH_AUTOMATICO", "MATCH_AMBIGUO", "NOVO_ALUNO", "PENDENTE"
]

# Ação final a ser executada para uma linha, definida pelo usuário ou automaticamente
AcaoFinal = Literal["CRIAR_RESERVA", "CRIAR_ALUNO_E_RESERVA", "IGNORAR"]


class LimiaresConfianca(TypedDict):
    """Define os limiares para classificação de correspondência."""

    match_automatico: int  # Ex: 95
    match_ambiguo: int  # Ex: 80


class SugestaoMatch(TypedDict):
    """Representa uma sugestão de estudante correspondente encontrada durante a análise."""

    id: int
    prontuario: str
    nome: str
    pontuacao: int


class LinhaAnalisada(TypedDict):
    """
    Estrutura de dados completa para uma linha após a análise,
    pronta para ser exibida na interface de revisão do usuário.
    """

    id_linha: int  # Identificador único para a linha na sessão de importação
    dados_originais: Dict[str, str]
    dados_mapeados: Dict[str, Optional[str]|int]
    status: StatusAnalise
    mensagem_erro: Optional[str]
    sugestoes: List[SugestaoMatch]
    acao_final_sugerida: Optional[AcaoFinal]
    acao_final: Optional[AcaoFinal]  # Ação que será de fato executada
