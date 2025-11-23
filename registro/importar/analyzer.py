# --- Arquivo: registro/nucleo/importers/analyzer.py ---

"""
Módulo de análise inteligente de dados usando Fuzzy Matching.
Lógica refinada para priorizar prontuários e lidar com combinações de dados.
"""

from typing import Any, Dict, List, Optional, Tuple

from fuzzywuzzy import fuzz

from registro.importar.definitions import (
    REGEX_LIMPEZA_PRONTUARIO,
    CandidatoMatch,
    ItemRevisao,
)
from registro.nucleo.repository import RepositorioEstudante


class AnalisadorSimplificado:
    """Classifica registros importados em Automáticos, Revisão ou Inválidos."""

    # Constantes de calibração (Thresholds)
    SCORE_MATCH_CERTO = 95
    SCORE_MATCH_PRONTUARIO = 85
    SCORE_MATCH_NOME = 75
    SCORE_CORTE_BUSCA = 60
    SCORE_BONUS_PRONTUARIO = 98
    SCORE_PENALIDADE_PRONTUARIO = 20

    def __init__(self, repo_estudante: RepositorioEstudante) -> None:
        """
        Inicializa o analisador e pré-carrega dados para performance.
        """
        # Carrega estudantes ativos
        self._todos_alunos = repo_estudante.ler_todos_com_grupos()
        self._mapa_prontuario = {a.prontuario: a for a in self._todos_alunos}

        # Otimização: Cache com dados normalizados para evitar .lower() em loops
        # Estrutura: (objeto_aluno, nome_lower, prontuario_limpo_lower)
        self._cache_busca: List[Tuple[Any, str, str]] = []
        for aluno in self._todos_alunos:
            p_limpo = REGEX_LIMPEZA_PRONTUARIO.sub("", aluno.prontuario.lower())
            self._cache_busca.append((aluno, aluno.nome.lower(), p_limpo))

    def processar_lote(
        self, dados_brutos: List[Dict[str, Any]]
    ) -> Tuple[List[Dict], List[ItemRevisao], List[Dict]]:
        """
        Analisa uma lista de dados brutos.
        Retorna tupla: (lista_automaticos, lista_revisao, lista_invalidos).
        """
        automaticos = []
        revisao = []
        invalidos = []
        id_temp = 1

        for linha in dados_brutos:
            prontuario_csv = linha.get("prontuario")
            nome_csv = linha.get("nome", "")

            # 1. Validação Mínima
            if not prontuario_csv and not nome_csv:
                invalidos.append(linha)
                continue

            # 2. Match Exato por Prontuário (Prioridade Máxima)
            if prontuario_csv and prontuario_csv in self._mapa_prontuario:
                self._tratar_match_exato(
                    linha, prontuario_csv, nome_csv, automaticos, revisao, id_temp
                )
                if linha not in automaticos and not self._item_revisao_existe(
                    revisao, linha
                ):
                    # Se não foi para automáticos, incrementa ID pois foi para revisão
                    id_temp += 1
                continue

            # 3. Busca Fuzzy (Quando Prontuário não bate exato ou não existe)
            if nome_csv:
                item_rev = self._processar_busca_fuzzy_nome(
                    linha, nome_csv, prontuario_csv, id_temp
                )
                if item_rev:
                    revisao.append(item_rev)
                    id_temp += 1
                else:
                    # Se não retornou item de revisão, é porque foi match automático
                    # (O método _processar_busca_fuzzy_nome modifica a linha e a insere na lista se for match)
                    # *Nota*: A lógica original inseria em 'automaticos' dentro do fluxo.
                    # Para manter compatibilidade, faremos a inserção aqui se detectado.
                    if "_id_banco" in linha:
                        automaticos.append(linha)

            elif prontuario_csv:
                # Apenas prontuário fornecido, sem nome
                candidatos = self._buscar_candidatos_pront(prontuario_csv)
                linha["nome"] = "Nome Desconhecido"  # Placeholder visual
                if not candidatos:
                    revisao.append(
                        self._criar_item_revisao(id_temp, linha, "NOVO_ESTUDANTE", [])
                    )
                else:
                    revisao.append(
                        self._criar_item_revisao(
                            id_temp, linha, "MULTIPLOS_MATCHES", candidatos
                        )
                    )
                id_temp += 1

        return automaticos, revisao, invalidos

    def _tratar_match_exato(
        self,
        linha: Dict,
        pront_csv: str,
        nome_csv: str,
        lista_auto: List,
        lista_rev: List,
        id_temp: int,
    ) -> None:
        """Lida com a lógica quando o prontuário existe exatamente no banco."""
        aluno_db = self._mapa_prontuario[pront_csv]

        # Caso A: CSV sem nome, confiamos no ID.
        if not nome_csv:
            linha.update({"_id_banco": aluno_db.id, "nome": aluno_db.nome})
            lista_auto.append(linha)
            return

        # Caso B: CSV tem nome. Validar similaridade.
        ratio = fuzz.ratio(nome_csv.lower(), aluno_db.nome.lower())

        if ratio > self.SCORE_MATCH_NOME:
            linha.update(
                {
                    "_id_banco": aluno_db.id,
                    "nome": aluno_db.nome,
                    "prontuario": aluno_db.prontuario,
                }
            )
            lista_auto.append(linha)
        else:
            # Divergência suspeita (Prontuário igual, nome muito diferente)
            lista_rev.append(
                self._criar_item_revisao(
                    id_temp,
                    linha,
                    "DADOS_DIVERGENTES",
                    [self._converter_aluno_para_match(aluno_db, 100)],
                )
            )

    def _processar_busca_fuzzy_nome(
        self, linha: Dict, nome_csv: str, pront_csv: Optional[str], id_temp: int
    ) -> Optional[ItemRevisao]:
        """
        Executa a busca fuzzy por nome e refina com prontuário se disponível.
        Retorna ItemRevisao se necessário, ou None se for match automático.
        """
        candidatos = self._buscar_candidatos_nome(nome_csv)
        candidatos_ajustados = []

        for cand in candidatos:
            score_final = self._calcular_score_ajustado(
                cand["score"], cand["prontuario"], pront_csv
            )
            cand["score"] = score_final
            candidatos_ajustados.append(cand)

        # Reordena após ajuste
        candidatos_ajustados.sort(key=lambda x: x["score"], reverse=True)

        if not candidatos_ajustados:
            return self._criar_item_revisao(id_temp, linha, "NOVO_ESTUDANTE", [])

        melhor_cand = candidatos_ajustados[0]

        if melhor_cand["score"] >= self.SCORE_MATCH_CERTO:
            # Match Automático
            linha.update(
                {
                    "_id_banco": melhor_cand["id"],
                    "nome": melhor_cand["nome"],
                    "prontuario": melhor_cand["prontuario"],
                }
            )
            return None  # Sinaliza que foi automático

        # Match inconclusivo -> Revisão
        return self._criar_item_revisao(
            id_temp, linha, "MULTIPLOS_MATCHES", candidatos_ajustados
        )

    def _calcular_score_ajustado(
        self, score_atual: int, pront_cand: str, pront_csv: Optional[str]
    ) -> int:
        """Refina o score do nome baseado na similaridade do prontuário."""
        if not pront_csv:
            return score_atual

        score_pront = fuzz.ratio(pront_csv, pront_cand)

        if score_pront > self.SCORE_MATCH_PRONTUARIO:
            return max(score_atual, self.SCORE_BONUS_PRONTUARIO)

        if score_pront < 40:
            return score_atual - self.SCORE_PENALIDADE_PRONTUARIO

        return score_atual

    def _buscar_candidatos_nome(self, nome_buscado: str) -> List[CandidatoMatch]:
        """Retorna top 4 alunos do banco parecidos com o nome usando cache."""
        resultados = []
        nome_lower = nome_buscado.lower()

        # Itera sobre o cache pré-processado (aluno, nome_norm, pront_norm)
        for aluno, nome_db_lower, _ in self._cache_busca:
            score = fuzz.token_sort_ratio(nome_lower, nome_db_lower)

            if score > self.SCORE_CORTE_BUSCA:
                resultados.append(self._converter_aluno_para_match(aluno, score))

        return sorted(resultados, key=lambda x: x["score"], reverse=True)[:4]

    def _buscar_candidatos_pront(self, pront_buscado: str) -> List[CandidatoMatch]:
        """Retorna top 4 alunos parecidos com o prontuário usando cache."""
        resultados = []
        pront_lower = REGEX_LIMPEZA_PRONTUARIO.sub("", pront_buscado.lower())

        # Itera sobre o cache pré-processado
        for aluno, _, pront_db_lower in self._cache_busca:
            score = fuzz.partial_ratio(pront_lower, pront_db_lower)

            if score > self.SCORE_MATCH_PRONTUARIO:
                resultados.append(self._converter_aluno_para_match(aluno, score))

        return sorted(resultados, key=lambda x: x["score"], reverse=True)[:4]

    def _converter_aluno_para_match(self, aluno: Any, score: int) -> CandidatoMatch:
        """Helper para formatar o objeto de aluno."""
        turma = aluno.grupos[0].nome if aluno.grupos else "Sem Turma"
        return {
            "id": aluno.id,
            "prontuario": aluno.prontuario,
            "nome": aluno.nome,
            "turma": turma,
            "score": int(score),
        }

    def _criar_item_revisao(
        self,
        id_temp: int,
        dados: Dict[str, Any],
        tipo: str,
        candidatos: List[CandidatoMatch],
    ) -> ItemRevisao:
        """Helper para criar estrutura de ItemRevisao."""
        resolucao = "CRIAR_NOVO"
        id_vinculo = None

        if candidatos and (tipo == "MULTIPLOS_MATCHES" or tipo == "DADOS_DIVERGENTES"):
            id_vinculo = candidatos[0]["id"]
            if tipo == "MULTIPLOS_MATCHES":
                resolucao = "VINCULAR"
            else:
                resolucao = "IGNORAR"

        return {
            "id_temp": id_temp,
            "dados_csv": dados,
            "tipo_conflito": tipo,
            "candidatos": candidatos,
            "resolucao_escolhida": resolucao,
            "id_estudante_vinculo": id_vinculo,
        }

    def _item_revisao_existe(self, lista_rev: List[ItemRevisao], linha: Dict) -> bool:
        """Verifica se a linha já foi adicionada à lista de revisão."""
        # Verificação simples baseada em identidade do objeto dados_csv
        return any(item["dados_csv"] is linha for item in lista_rev)
