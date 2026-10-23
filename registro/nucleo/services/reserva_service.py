# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/services/reserva_service.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Serviço de gerenciamento de Reservas (CRUD, listagens e importações em lote).
"""

import logging
from typing import Any, Dict, List, Optional

from registro.nucleo.exceptions import ErroNucleoRegistro
from registro.nucleo.repository import (
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
)

logger = logging.getLogger(__name__)


def criar_reserva(
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    prontuario_estudante: str,
    dados_reserva: Dict[str, Any],
) -> Dict[str, Any]:
    """Cria uma reserva para o estudante especificado."""
    estudantes = repo_estudante.ler_filtrado(prontuario=prontuario_estudante)
    if not estudantes:
        raise ValueError(
            f"Estudante com prontuário {prontuario_estudante} não encontrado."
        )

    payload = dados_reserva.copy()
    payload["estudante_id"] = estudantes[0].id

    nova_reserva = repo_reserva.criar(payload)
    repo_reserva.obter_sessao().commit()

    return {
        "id": nova_reserva.id,
        "estudante_id": nova_reserva.estudante_id,
        "prato": nova_reserva.prato,
        "data": nova_reserva.data,
        "cancelada": nova_reserva.cancelada,
    }


def atualizar_reserva(
    repo_reserva: RepositorioReserva,
    id_reserva: int,
    dados: Dict[str, Any],
) -> bool:
    """Atualiza os dados de uma reserva."""
    reserva = repo_reserva.atualizar(id_reserva, dados)
    if reserva:
        repo_reserva.obter_sessao().commit()
        return True
    return False


def deletar_reserva(
    repo_reserva: RepositorioReserva,
    id_reserva: int,
) -> bool:
    """Remove uma reserva do sistema."""
    if repo_reserva.deletar(id_reserva):
        repo_reserva.obter_sessao().commit()
        return True
    return False


def listar_datas_reservas(repo_reserva: RepositorioReserva) -> List[str]:
    """Retorna uma lista única e cronologicamente ordenada de datas de reservas existentes."""
    from registro.nucleo.importar.patterns_find import obter_data

    def _chave_data(texto: str) -> int:
        obj = obter_data(texto)
        return int(obj.timestamp()) if obj else 0

    datas = {s.data for s in repo_reserva.ler_unicos() if s.data}
    return sorted(datas, reverse=True, key=_chave_data)


def listar_reservas(
    repo_grupo: RepositorioGrupo,
    repo_reserva: RepositorioReserva,
    filtros: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Lista reservas com base nos filtros fornecidos."""
    filtros = filtros or {}
    if "grupos" in filtros or "grupo" in filtros:
        grupos = set(filtros.get("grupos", [])) or set(
            filtros.get("grupo", ""),
        )
        grupos_ids = [g.id for g in repo_grupo.por_nomes(grupos)]
        reservas = repo_reserva.por_data_e_grupos(
            grupos_ids=grupos_ids, data_formatada=filtros.get("data")
        )
    else:
        reservas = repo_reserva.ler_filtrado(**filtros)

    return [
        {
            "id": res.id,
            "prontuario_estudante": res.estudante.prontuario,
            "nome_estudante": res.estudante.nome,
            "prato": res.prato,
            "data": res.data,
            "cancelada": res.cancelada,
        }
        for res in reservas
    ]


def atualizar_cancelamento_reserva(
    repo_reserva: RepositorioReserva, id_reserva: int, cancelar: bool = True
):
    """Marca ou desmarca uma reserva como cancelada."""
    atualizado = repo_reserva.atualizar(id_reserva, {"cancelada": cancelar})
    if not atualizado:
        raise ErroNucleoRegistro(
            f"Reserva com ID {id_reserva} não encontrada."
        )
    repo_reserva.obter_sessao().commit()


def salvar_importacao_dados(
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    dados: List[Dict[str, Any]],
) -> Dict[str, int]:
    """Persiste dados importados de estudantes e reservas de forma atômica."""
    novos_estudantes = []
    reservas_para_criar = []

    for linha in dados:
        id_banco = linha.get("_id_banco")
        pront = linha.get("prontuario")

        if not (data := linha.get("data")):
            continue

        if not id_banco and pront:
            novos_estudantes.append(
                {
                    "prontuario": pront,
                    "nome": linha.get("nome", "Desconhecido"),
                    "ativo": True,
                }
            )

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

    if novos_estudantes:
        unicos = {e["prontuario"]: e for e in novos_estudantes}.values()
        repo_estudante.criar_em_massa(list(unicos))

    mapa_ids = {}
    if novos_estudantes:
        pronts = {e["prontuario"] for e in novos_estudantes}
        objs = repo_estudante.por_prontuarios(pronts)
        mapa_ids = {e.prontuario: e.id for e in objs}

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
        repo_reserva.criar_em_massa(reservas_finais)

    repo_estudante.obter_sessao().commit()

    return {
        "estudantes_criados": len(novos_estudantes),
        "reservas_criadas": len(reservas_finais),
    }
