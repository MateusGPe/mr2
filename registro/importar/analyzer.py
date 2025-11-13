# --- Arquivo: registro/nucleo/importers/analyzer.py ---

"""
Encapsula a lógica de análise, validação, correspondência (fuzzy matching)
e classificação das linhas de dados importadas. Este é o cérebro do sistema.
"""

import re
from typing import Dict, List, Optional, Sequence

from fuzzywuzzy import fuzz

from registro.importar.definitions import LimiaresConfianca, LinhaAnalisada, SugestaoMatch
from registro.nucleo.models import Estudante
from registro.nucleo.repository import RepositorioEstudante


class AnalisadorDeLinhas:
    """Realiza a análise inteligente de dados para encontrar correspondências."""

    def __init__(
        self,
        repo_estudante: RepositorioEstudante,
        limiares: LimiaresConfianca,
    ):
        self._repo_estudante = repo_estudante
        self._limiares = limiares
        # Carrega todos os estudantes ativos em memória para evitar múltiplas queries ao DB.
        self._cache_estudantes: Sequence[Estudante] = self._repo_estudante.ler_filtrado(
            ativo=True
        )
        self._cache_prontuarios = {e.prontuario for e in self._cache_estudantes}

    def _sanitizar_e_validar(self, dados_mapeados: Dict) -> Optional[str]:
        """Limpa e valida os dados essenciais. Retorna uma mensagem de erro se falhar."""
        nome = dados_mapeados.get("nome")
        if not nome or not str(nome).strip():
            return "O campo 'nome' é obrigatório e não pode estar vazio."

        data = dados_mapeados.get("data")
        if data and not self._validar_formato_data(str(data)):
            return "Formato de data inválido. Use AAAA-MM-DD."

        return None

    @staticmethod
    def _validar_formato_data(data_str: str) -> bool:
        """Valida se a data está no formato AAAA-MM-DD."""
        return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", data_str.strip()))

    def _encontrar_correspondencias(
        self, nome: str, prontuario: Optional[str]
    ) -> List[SugestaoMatch]:
        """Busca por estudantes correspondentes no cache usando fuzzy matching."""
        sugestoes = []
        nome_limpo = nome.lower()

        # Prioriza match exato por prontuário, se fornecido.
        if prontuario:
            for est in self._cache_estudantes:
                if est.prontuario == prontuario:
                    pontuacao_nome = fuzz.token_sort_ratio(nome_limpo, est.nome.lower())
                    return [
                        {
                            "id": est.id,
                            "prontuario": est.prontuario,
                            "nome": est.nome,
                            "pontuacao": max(100, pontuacao_nome),
                        }
                    ]

        # Se não há prontuário ou não encontrou, faz fuzzy matching por nome.
        for est in self._cache_estudantes:
            pontuacao = fuzz.token_sort_ratio(nome_limpo, est.nome.lower())
            if pontuacao >= self._limiares["match_ambiguo"]:
                sugestoes.append(
                    {
                        "id": est.id,
                        "prontuario": est.prontuario,
                        "nome": est.nome,
                        "pontuacao": pontuacao,
                    }
                )

        # Retorna as melhores sugestões ordenadas pela pontuação.
        return sorted(sugestoes, key=lambda x: x["pontuacao"], reverse=True)

    def analisar_linha(
        self, id_linha: int, dados_originais: Dict, dados_mapeados: Dict
    ) -> LinhaAnalisada:
        """Processa uma única linha, classificando-a e sugerindo uma ação."""
        resultado: LinhaAnalisada = {
            "id_linha": id_linha,
            "dados_originais": dados_originais,
            "dados_mapeados": dados_mapeados,
            "status": "PENDENTE",
            "mensagem_erro": None,
            "sugestoes": [],
            "acao_final_sugerida": None,
            "acao_final": None,
        }

        erro_validacao = self._sanitizar_e_validar(dados_mapeados)
        if erro_validacao:
            resultado["status"] = "ERRO"
            resultado["mensagem_erro"] = erro_validacao
            resultado["acao_final_sugerida"] = "IGNORAR"
            return resultado

        nome = str(dados_mapeados.get("nome", "")).strip()
        prontuario = str(dados_mapeados.get("prontuario", "")).strip() or None

        sugestoes = self._encontrar_correspondencias(nome, prontuario)
        resultado["sugestoes"] = sugestoes

        if not sugestoes:
            resultado["status"] = "NOVO_ALUNO"
            resultado["acao_final_sugerida"] = "CRIAR_ALUNO_E_RESERVA"
        elif sugestoes[0]["pontuacao"] >= self._limiares["match_automatico"]:
            resultado["status"] = "MATCH_AUTOMATICO"
            dados_mapeados["_estudante_id_resolvido"] = sugestoes[0]["id"]
            resultado["acao_final_sugerida"] = "CRIAR_RESERVA"
        else:
            resultado["status"] = "MATCH_AMBIGUO"
            resultado["acao_final_sugerida"] = "IGNORAR"

        return resultado
