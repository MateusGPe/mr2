"""
Serviço de orquestração da importação.
Gerencia estado entre etapas e garante persistência segura.
"""

from typing import Any, Dict, List, Optional

from registro.importar.analyzer import AnalisadorSimplificado
from registro.importar.definitions import ItemRevisao, ResumoImportacao
from registro.importar.strategies import EstrategiaCarregamento
from registro.nucleo.exceptions import ErroImportacaoDados
from registro.nucleo.facade import FachadaRegistro


class ServicoImportacao:
    """Gerencia o ciclo de vida de uma importação."""

    def __init__(self, fachada_nucleo: FachadaRegistro):
        self._fachada = fachada_nucleo
        self._cache_automaticos: List[Dict] = []
        self._cache_resumo: Optional[ResumoImportacao] = None

    def preparar_importacao(
        self, estrategia: EstrategiaCarregamento, fonte: str
    ) -> Dict[str, Any]:
        """Etapa 1: Carrega, Analisa e Separa dados."""
        self._cache_automaticos = []
        dados_brutos = estrategia.carregar(fonte)

        if not dados_brutos:
            raise ErroImportacaoDados("Nenhum dado válido encontrado na fonte.")

        analisador = AnalisadorSimplificado(self._fachada.repo_estudante)
        autos, revisao, invalidos = analisador.processar_lote(dados_brutos)

        self._cache_automaticos = autos
        self._cache_resumo = {
            "total_linhas": len(dados_brutos),
            "automaticos": len(autos),
            "invalidos": len(invalidos),
            "para_revisao": len(revisao),
        }

        return {"resumo": self._cache_resumo, "itens_revisao": revisao}

    def simular_importacao(
        self,
        itens_revisados: List[ItemRevisao],
        valores_padrao: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, List[Dict]]:
        """
        Gera uma previsão do que será feito, sem salvar no banco.
        Retorna listas de 'novos_estudantes' e 'reservas_a_criar'.
        """
        lista_consolidada = self._processar_dados_finais(
            itens_revisados, valores_padrao
        )

        # Simula a separação dos dados
        novos = []
        reservas = []

        for linha in lista_consolidada:
            id_banco = linha.get("_id_banco")
            pront = linha.get("prontuario")
            data = linha.get("data")

            # Sem data, não é possível criar reserva)
            if not data:
                continue

            # Detecta novo estudante
            if not id_banco and pront:
                # Usa um set ou dict auxiliar para evitar duplicatas visuais na simulação
                exists = any(n["prontuario"] == pront for n in novos)
                if not exists:
                    novos.append(
                        {
                            "prontuario": pront,
                            "nome": linha.get("nome", "Desconhecido"),
                            "turma": linha.get("turma", "-"),  # Se houver
                        }
                    )

            # Detecta reserva
            nome_display = linha.get("nome")
            # Se for vinculado, tentamos pegar o nome original ou mantemos o do CSV
            reservas.append(
                {
                    "data": data,
                    "prato": linha.get("prato"),
                    "aluno": nome_display,
                    "prontuario": pront,
                }
            )

        return {"novos_estudantes": novos, "reservas": reservas}

    def finalizar_importacao(
        self,
        itens_revisados: List[ItemRevisao],
        valores_padrao: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, int]:
        """Consolida e Persiste."""
        lista_final = self._processar_dados_finais(itens_revisados, valores_padrao)
        return self._persistir_dados(lista_final)

    def _processar_dados_finais(
        self,
        itens_revisados: List[ItemRevisao],
        valores_padrao: Optional[Dict[str, Any]],
    ) -> List[Dict]:
        """Lógica interna: Junta Automáticos + Revisados + Defaults."""
        lista_final = list(self._cache_automaticos)
        # 1. Aplica decisões da revisão
        for item in itens_revisados:
            decisao = item["resolucao_escolhida"]
            dados = item["dados_csv"]

            if decisao == "IGNORAR":
                continue
            elif decisao == "VINCULAR" and item["id_estudante_vinculo"]:
                novo = dados.copy()
                novo["_id_banco"] = item["id_estudante_vinculo"]
                try:
                    if iid := item.get("id_estudante_vinculo"):
                        cand = next(
                            cand
                            for cand in item.get("candidatos", [])
                            if cand["id"] == iid
                        )
                        novo["nome"] = cand["nome"]
                        novo["prontuario"] = cand["prontuario"]
                except Exception:
                    pass
                lista_final.append(novo)
            elif decisao == "CRIAR_NOVO":
                dados.pop("_id_banco", None)
                lista_final.append(dados)

        # 2. Aplica Defaults
        if valores_padrao:
            for linha in lista_final:
                for chave, valor in valores_padrao.items():
                    if not linha.get(chave):
                        linha[chave] = valor
        return lista_final

    def _persistir_dados(self, dados: List[Dict]) -> Dict[str, int]:
        """Persistência segura com tratamento de dependências (IDs)."""
        novos_estudantes = []
        reservas_para_criar = []

        # Separação
        for linha in dados:
            id_banco = linha.get("_id_banco")
            pront = linha.get("prontuario")
            data = linha.get("data")

            # Sem data, não é possível criar reserva
            if not data:
                continue

            # Identifica novos alunos
            if not id_banco and pront:
                novos_estudantes.append(
                    {
                        "prontuario": pront,
                        "nome": linha.get("nome", "Desconhecido"),
                        "ativo": True,
                    }
                )

            # Prepara payload da reserva com chave de resolução
            reservas_para_criar.append(
                {
                    "payload": {
                        "prato": linha.get("prato"),
                        "data": data,
                        "cancelada": False,
                    },
                    "chave": id_banco if id_banco else pront,
                }
            )

        # Criação de Novos Alunos (Unicos)
        if novos_estudantes:
            unicos = {e["prontuario"]: e for e in novos_estudantes}.values()
            self._fachada.repo_estudante.criar_em_massa(list(unicos))

        # Recuperação de IDs (Fix para SQLite não retornar IDs em bulk)
        mapa_ids = {}
        if novos_estudantes:
            pronts = {e["prontuario"] for e in novos_estudantes}
            objs = self._fachada.repo_estudante.por_prontuarios(pronts)
            mapa_ids = {e.prontuario: e.id for e in objs}

        # Criação de Reservas
        reservas_finais = []
        for item in reservas_para_criar:
            chave = item["chave"]
            id_final = None

            if isinstance(chave, int):
                id_final = chave
            elif isinstance(chave, str):
                id_final = mapa_ids.get(chave)

            if id_final:
                payload = item["payload"]
                payload["estudante_id"] = id_final
                reservas_finais.append(payload)

        if reservas_finais:
            self._fachada.repo_reserva.criar_em_massa(reservas_finais)

        self._fachada.repo_estudante.obter_sessao().commit()

        return {
            "estudantes_criados": len(novos_estudantes),
            "reservas_criadas": len(reservas_finais),
        }
