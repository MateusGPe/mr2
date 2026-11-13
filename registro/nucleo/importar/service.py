# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/importar/service.py (Serviço de Importação)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Serviço de orquestração da importação.
Gerencia estado entre etapas e garante persistência segura.
"""

from typing import Any, Dict, List, Optional

from registro.nucleo.exceptions import ErroImportacaoDados
from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.importar.analyzer import AnalisadorSimplificado
from registro.nucleo.importar.definitions import ItemRevisao, ResumoImportacao
from registro.nucleo.importar.strategies import EstrategiaCarregamento
from registro.nucleo.utils import (
    formatar_turnos_reserva,
    resolver_turnos_reserva,
)


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

        alunos = (
            self._fachada.obter_todos_estudantes_com_grupos()
            if hasattr(self._fachada, "obter_todos_estudantes_com_grupos")
            else self._fachada.repo_estudante
        )
        analisador = AnalisadorSimplificado(alunos)
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


        novos = []
        reservas = []
        prontuarios_vistos = set()

        for linha in lista_consolidada:
            id_banco = linha.get("_id_banco")
            pront = linha.get("prontuario")
            data = linha.get("data")

            if not data:
                continue

            if not id_banco and pront and pront not in prontuarios_vistos:
                prontuarios_vistos.add(pront)
                novos.append(
                    {
                        "prontuario": pront,
                        "nome": linha.get("nome", "Desconhecido"),
                        "turma": linha.get("turma", "-"),
                    }
                )


            nome_display = linha.get("nome")

            alm = bool(linha.get("almoco", True))
            jan = bool(linha.get("jantar", False))
            reservas.append(
                {
                    "data": data,
                    "prato": linha.get("prato"),
                    "aluno": nome_display,
                    "prontuario": pront,
                    "categoria": linha.get("categoria") or "-",
                    "almoco": alm,
                    "jantar": jan,
                    "turnos_str": formatar_turnos_reserva(alm, jan),
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
        lista_final = [dict(item) for item in self._cache_automaticos]

        for item in itens_revisados:
            decisao = item["resolucao_escolhida"]
            dados = item["dados_csv"]

            if decisao == "IGNORAR":
                continue
            elif decisao == "VINCULAR" and item["id_estudante_vinculo"]:
                novo = dados.copy()
                novo["_id_banco"] = item["id_estudante_vinculo"]
                if iid := item.get("id_estudante_vinculo"):
                    cand = next(
                        (
                            c
                            for c in item.get("candidatos", [])
                            if c["id"] == iid
                        ),
                        None,
                    )
                    if cand is not None:
                        novo["nome"] = cand["nome"]
                        novo["prontuario"] = cand["prontuario"]
                lista_final.append(novo)
            elif decisao == "CRIAR_NOVO":
                dados.pop("_id_banco", None)
                lista_final.append(dados)

        defaults = valores_padrao or {}
        default_almoco = bool(defaults.get("almoco", True))
        default_jantar = bool(defaults.get("jantar", False))

        for linha in lista_final:
            for chave, valor in defaults.items():
                if chave in ("almoco", "jantar"):
                    continue
                if not linha.get(chave):
                    linha[chave] = valor

            almoco, jantar = resolver_turnos_reserva(
                linha,
                default_almoco=default_almoco,
                default_jantar=default_jantar,
            )
            if linha.get("data") and not almoco and not jantar:
                raise ErroImportacaoDados(
                    "Selecione ou informe pelo menos Almoço ou Jantar para as reservas."
                )
            linha["almoco"] = almoco
            linha["jantar"] = jantar

        return lista_final

    def _persistir_dados(self, dados: List[Dict]) -> Dict[str, int]:
        """Persistência segura com tratamento de dependências (IDs)."""
        if hasattr(self._fachada, "salvar_importacao_dados"):
            return self._fachada.salvar_importacao_dados(dados)

        from registro.nucleo.services.reserva_service import salvar_importacao_dados

        return salvar_importacao_dados(
            self._fachada.repo_estudante, self._fachada.repo_reserva, dados
        )
