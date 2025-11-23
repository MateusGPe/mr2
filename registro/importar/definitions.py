"""
Define as estruturas de dados (TypedDicts) utilizadas para comunicação
entre a camada de serviço de importação e a interface de usuário.
"""

import re
from typing import Any, Dict, List, Literal, Optional, TypedDict

REGEX_LIMPEZA_PRONTUARIO: re.Pattern[str] = re.compile(r"^[Ii][Qq]\d0+")

# Tipos de inconsistência que requerem atenção do usuário
TipoConflito = Literal[
    "NOVO_ESTUDANTE",  # Não existe no banco -> Sugere criar
    "MULTIPLOS_MATCHES",  # Fuzzy achou gente parecida -> Sugere vincular
    "DADOS_DIVERGENTES",  # Prontuário bate, mas Nome difere -> Atenção
]

# Ação que o usuário escolhe na GUI
ResolucaoUsuario = Literal[
    "CRIAR_NOVO",  # Aceita o dado do CSV como um novo aluno
    "VINCULAR",  # Aceita que o dado do CSV é o Estudante X do banco
    "IGNORAR",  # Não faz nada com essa linha
]


class CandidatoMatch(TypedDict):
    """Representa uma sugestão de estudante existente no banco."""

    id: int
    prontuario: str
    nome: str
    turma: str
    score: int


class ItemRevisao(TypedDict):
    """
    Representa uma linha da importação que requer decisão do usuário.
    Estrutura otimizada para renderização em tabelas na GUI.
    """

    id_temp: int  # Identificador temporário para controle da GUI
    dados_csv: Dict[str, Any]  # Dados brutos (Nome, Pront, Data, Prato)
    tipo_conflito: TipoConflito
    candidatos: List[CandidatoMatch]  # Sugestões para preencher Combobox
    resolucao_escolhida: ResolucaoUsuario  # Ação padrão sugerida
    id_estudante_vinculo: Optional[int]  # ID selecionado (se VINCULAR)


class ResumoImportacao(TypedDict):
    """Estatísticas da análise inicial da importação."""

    total_linhas: int
    automaticos: int  # Processados sem intervenção (Verdes)
    invalidos: int  # Descartados por erro de dados (Vermelhos)
    para_revisao: int  # Enviados para a GUI (Amarelos)
