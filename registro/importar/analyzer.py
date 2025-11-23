# --- Arquivo: registro/nucleo/importers/analyzer.py ---

"""
Módulo de análise inteligente de dados usando Fuzzy Matching.
Lógica refinada para priorizar prontuários e lidar com combinações de dados.
"""

from typing import Dict, List, Tuple, Optional

from fuzzywuzzy import fuzz

from registro.importar.definitions import (
    REGEX_LIMPEZA_PRONTUARIO,
    CandidatoMatch,
    ItemRevisao,
)
from registro.nucleo.repository import RepositorioEstudante


class AnalisadorSimplificado:
    """Classifica registros importados em Automáticos, Revisão ou Inválidos."""

    def __init__(self, repo_estudante: RepositorioEstudante):
        # Carrega estudantes ativos para cache em memória
        self._todos_alunos = repo_estudante.ler_todos_com_grupos()
        self._mapa_prontuario = {a.prontuario: a for a in self._todos_alunos}

    def processar_lote(
        self, dados_brutos: List[Dict]
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
            pront_csv = linha.get("prontuario")
            nome_csv = linha.get("nome", "")

            # 1. Validação Mínima
            # A linha deve ter pelo menos um identificador (Nome OU Prontuário)
            if not pront_csv and not nome_csv:
                invalidos.append(linha)
                continue

            # 2. Match Exato por Prontuário (Prioridade Máxima)
            if pront_csv and pront_csv in self._mapa_prontuario:
                aluno_db = self._mapa_prontuario[pront_csv]

                # Caso A: CSV não tem nome, apenas Prontuário.
                # Confiamos no ID e usamos o nome do banco.
                if not nome_csv:
                    linha["_id_banco"] = aluno_db.id
                    linha["nome"] = aluno_db.nome  # Preenche para visualização
                    automaticos.append(linha)
                    continue

                # Caso B: CSV tem nome. Verificamos se bate com o banco.
                ratio = fuzz.ratio(nome_csv.lower(), aluno_db.nome.lower())

                if ratio > 75:  # Confiança alta que é a mesma pessoa
                    linha["_id_banco"] = aluno_db.id
                    linha["nome"] = aluno_db.nome  # Preenche para visualização
                    linha["prontuario"] = aluno_db.prontuario
                    automaticos.append(linha)
                else:
                    # Prontuário existe, mas nome é muito diferente (Possível erro de digitação no ID do CSV)
                    # Enviamos para o usuário decidir se mantem o vínculo ou se é outra pessoa
                    revisao.append(
                        self._criar_item_revisao(
                            id_temp,
                            linha,
                            "DADOS_DIVERGENTES",
                            [self._converter_aluno_para_match(aluno_db, 100)],
                        )
                    )
                    id_temp += 1
                continue

            # 3. Busca Fuzzy por Nome (Quando Prontuário não bate exato ou não existe)
            if nome_csv:
                candidatos = self._buscar_candidatos_nome(nome_csv)

                # Refinamento: Se o usuário forneceu um Prontuário (que não bateu exato no passo 2),
                # vamos ver se ele se parece com o prontuário dos candidatos encontrados pelo nome.
                candidatos_ajustados = []
                for cand in candidatos:
                    score_final = cand["score"]

                    # Se CSV tem prontuário, verifica similaridade com o do candidato
                    if pront_csv:
                        score_pront = fuzz.ratio(pront_csv, cand["prontuario"])
                        # Se o prontuário for muito parecido (ex: erro de 1 digito), aumenta confiança
                        if score_pront > 85:
                            score_final = max(score_final, 98)  # Quase certeza
                        # Se o prontuário for totalmente diferente, penaliza, mas mantém na lista
                        elif score_pront < 40:
                            score_final -= 20

                    cand["score"] = score_final
                    candidatos_ajustados.append(cand)

                # Reordena após ajuste
                candidatos_ajustados.sort(key=lambda x: x["score"], reverse=True)

                if not candidatos_ajustados:
                    # Nenhum nome parecido -> Novo Aluno
                    revisao.append(
                        self._criar_item_revisao(id_temp, linha, "NOVO_ESTUDANTE", [])
                    )
                    id_temp += 1

                elif candidatos_ajustados[0]["score"] >= 95:
                    # Match muito forte (Nome igual e/ou Prontuário typo)
                    linha["_id_banco"] = candidatos_ajustados[0]["id"]
                    linha["nome"] = candidatos_ajustados[0]["nome"]
                    linha["prontuario"] = candidatos_ajustados[0]["prontuario"]
                    automaticos.append(linha)

                else:
                    # Match existe mas não é perfeito -> Usuário decide
                    revisao.append(
                        self._criar_item_revisao(
                            id_temp, linha, "MULTIPLOS_MATCHES", candidatos_ajustados
                        )
                    )
                    id_temp += 1

            elif pront_csv:
                candidatos = self._buscar_candidatos_pront(pront_csv)
                if not candidatos:
                    revisao.append(
                        self._criar_item_revisao(id_temp, linha, "NOVO_ESTUDANTE", [])
                    )
                    id_temp += 1
                else:
                    # Match existe mas não é perfeito -> Usuário decide
                    linha["nome"] = "Nome Desconhecido"  # Placeholder visual
                    revisao.append(
                        self._criar_item_revisao(
                            id_temp, linha, "MULTIPLOS_MATCHES", candidatos
                        )
                    )
                    id_temp += 1

        return automaticos, revisao, invalidos

    def _buscar_candidatos_nome(self, nome_buscado: str) -> List[CandidatoMatch]:
        """Retorna top 3 alunos do banco parecidos com o nome."""
        resultados = []
        nome_lower = nome_buscado.lower()

        for aluno in self._todos_alunos:
            # Token Sort Ratio lida bem com nomes fora de ordem
            score = fuzz.token_sort_ratio(nome_lower, aluno.nome.lower())

            if score > 60:
                resultados.append(self._converter_aluno_para_match(aluno, score))

        return sorted(resultados, key=lambda x: x["score"], reverse=True)[:4]

    def _buscar_candidatos_pront(self, pront_buscado: str) -> List[CandidatoMatch]:
        """Retorna top 3 alunos do banco parecidos com o prontuário."""
        resultados = []
        pront_lower = REGEX_LIMPEZA_PRONTUARIO.sub("", pront_buscado.lower())

        for aluno in self._todos_alunos:
            score = fuzz.partial_ratio(
                pront_lower, REGEX_LIMPEZA_PRONTUARIO.sub("", aluno.prontuario.lower())
            )

            if score > 85:
                resultados.append(self._converter_aluno_para_match(aluno, score))

        return sorted(resultados, key=lambda x: x["score"], reverse=True)[:4]

    def _converter_aluno_para_match(self, aluno, score: int) -> CandidatoMatch:
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
        self, id_temp: int, dados: Dict, tipo: str, candidatos: List
    ) -> ItemRevisao:
        """Helper para criar estrutura de ItemRevisao."""
        resolucao = "CRIAR_NOVO"
        id_vinculo = None

        if tipo == "DADOS_DIVERGENTES":
            # Sugere ignorar (segurança) ou vincular se score for alto
            resolucao = "IGNORAR"
            if candidatos:
                id_vinculo = candidatos[0]["id"]

        elif tipo == "MULTIPLOS_MATCHES":
            resolucao = "VINCULAR"
            if candidatos:
                id_vinculo = candidatos[0]["id"]

        return {
            "id_temp": id_temp,
            "dados_csv": dados,
            "tipo_conflito": tipo,
            "candidatos": candidatos,
            "resolucao_escolhida": resolucao,
            "id_estudante_vinculo": id_vinculo,
        }
