# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/services/reserva_service.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Serviço de gerenciamento de Reservas (CRUD, listagens e importações em lote).
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import insert
from sqlalchemy.orm import selectinload

from registro.nucleo.constants import TIPO_GRUPO_CATEGORIA
from registro.nucleo.exceptions import ErroNucleoRegistro
from registro.nucleo.models import Estudante, Grupo, Reserva, associacao_reserva_grupo
from registro.nucleo.repository import (
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
)
from registro.nucleo.utils import (
    extrair_turmas_e_categorias,
    normalizar_lista_categorias,
)

logger = logging.getLogger(__name__)


def _sincronizar_categorias_reserva(
    reserva: Reserva,
    categorias_raw: Any,
    repo_grupo: RepositorioGrupo,
) -> None:
    """Atualiza as categorias vinculadas diretamente à reserva (sem alterar o estudante)."""
    cats = normalizar_lista_categorias(categorias_raw)
    reserva.grupos.clear()
    if not cats:
        return
    mapa = repo_grupo.obter_ou_criar_por_nomes(set(cats), tipo=TIPO_GRUPO_CATEGORIA)
    for nome in cats:
        if nome in mapa:
            reserva.grupos.append(mapa[nome])


def criar_reserva(
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    prontuario_estudante: str,
    dados_reserva: Dict[str, Any],
    repo_grupo: Optional[RepositorioGrupo] = None,
) -> Dict[str, Any]:
    """Cria uma reserva para o estudante especificado, com categorias pontuais opcionais."""
    estudantes = repo_estudante.ler_filtrado(prontuario=prontuario_estudante)
    if not estudantes:
        raise ValueError(
            f"Estudante com prontuário {prontuario_estudante} não encontrado."
        )

    payload = dados_reserva.copy()
    has_cats = "categorias" in payload or "categoria" in payload
    cats_raw = payload.pop("categorias", None)
    if cats_raw is None:
        cats_raw = payload.pop("categoria", None)
    else:
        payload.pop("categoria", None)

    payload["estudante_id"] = estudantes[0].id

    nova_reserva = repo_reserva.criar(payload)
    if has_cats:
        rg = repo_grupo or RepositorioGrupo(repo_reserva.obter_sessao())
        _sincronizar_categorias_reserva(nova_reserva, cats_raw, rg)

    try:
        repo_reserva.obter_sessao().commit()
    except Exception as e:
        logger.exception("Falha ao criar reserva para estudante %s: %s", prontuario_estudante, e)
        try:
            repo_reserva.obter_sessao().rollback()
        except Exception:
            pass
        raise ErroNucleoRegistro(f"Falha ao criar reserva no banco: {e}") from e

    cats_salvas = sorted(g.nome for g in nova_reserva.grupos)
    return {
        "id": nova_reserva.id,
        "estudante_id": nova_reserva.estudante_id,
        "prato": nova_reserva.prato,
        "data": nova_reserva.data,
        "cancelada": nova_reserva.cancelada,
        "categorias": cats_salvas,
    }


def atualizar_reserva(
    repo_reserva: RepositorioReserva,
    id_reserva: int,
    dados: Dict[str, Any],
    repo_grupo: Optional[RepositorioGrupo] = None,
) -> bool:
    """Atualiza os dados e categorias pontuais de uma reserva."""
    payload = dados.copy()
    has_cats = "categorias" in payload or "categoria" in payload
    cats_raw = payload.pop("categorias", None)
    if cats_raw is None and "categoria" in payload:
        cats_raw = payload.pop("categoria", None)
    else:
        payload.pop("categoria", None)

    reserva = repo_reserva.atualizar(id_reserva, payload) if payload else repo_reserva.ler_um(
        id_reserva, opcoes_carregamento=[selectinload(Reserva.grupos)]
    )
    if reserva:
        if has_cats:
            rg = repo_grupo or RepositorioGrupo(repo_reserva.obter_sessao())
            _sincronizar_categorias_reserva(reserva, cats_raw, rg)
        try:
            repo_reserva.obter_sessao().commit()
            return True
        except Exception as e:
            logger.exception("Falha ao atualizar reserva %s: %s", id_reserva, e)
            try:
                repo_reserva.obter_sessao().rollback()
            except Exception:
                pass
            raise ErroNucleoRegistro(f"Falha ao atualizar reserva no banco: {e}") from e
    return False


def deletar_reserva(
    repo_reserva: RepositorioReserva,
    id_reserva: int,
) -> bool:
    """Remove uma reserva do sistema."""
    if repo_reserva.deletar(id_reserva):
        try:
            repo_reserva.obter_sessao().commit()
            return True
        except Exception as e:
            logger.exception("Falha ao deletar reserva %s: %s", id_reserva, e)
            try:
                repo_reserva.obter_sessao().rollback()
            except Exception:
                pass
            raise ErroNucleoRegistro(f"Falha ao excluir reserva no banco: {e}") from e
    return False


def listar_datas_reservas(repo_reserva: RepositorioReserva) -> List[str]:
    """Retorna uma lista única e cronologicamente ordenada de datas de reservas existentes."""
    from sqlalchemy import select
    from registro.nucleo.importar.patterns_find import obter_data
    from registro.nucleo.models import Reserva

    def _chave_data(texto: str) -> int:
        obj = obter_data(texto)
        return int(obj.timestamp()) if obj else 0

    sessao = repo_reserva.obter_sessao()
    if hasattr(sessao, "scalars"):
        try:
            valores = sessao.scalars(select(Reserva.data).distinct()).all()
            datas = {d for d in valores if isinstance(d, str) and d}
            return sorted(datas, reverse=True, key=_chave_data)
        except Exception:
            pass

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
        raw_grupos = filtros.get("grupos") or filtros.get("grupo") or []
        if isinstance(raw_grupos, str):
            grupos = {raw_grupos} if raw_grupos.strip() else set()
        else:
            grupos = set(raw_grupos)
        grupos_ids = [g.id for g in repo_grupo.por_nomes(grupos)]
        reservas = repo_reserva.por_data_e_grupos(
            grupos_ids=grupos_ids, data_formatada=filtros.get("data")
        )
    else:
        reservas = repo_reserva.ler_filtrado(
            opcoes_carregamento=[
                selectinload(Reserva.grupos),
                selectinload(Reserva.estudante).selectinload(Estudante.grupos),
            ],
            **filtros,
        )

    resultado = []
    for res in reservas:
        turmas_est, _ = extrair_turmas_e_categorias(res.estudante)
        cats_reserva = sorted(g.nome for g in (res.grupos or []))
        resultado.append(
            {
                "id": res.id,
                "prontuario_estudante": res.estudante.prontuario,
                "nome_estudante": res.estudante.nome,
                "turma_estudante": ", ".join(turmas_est) if turmas_est else "N/A",
                "prato": res.prato,
                "data": res.data,
                "cancelada": res.cancelada,
                "categorias": cats_reserva,
                "categorias_str": ", ".join(cats_reserva) if cats_reserva else "-",
            }
        )
    return resultado


def atualizar_cancelamento_reserva(
    repo_reserva: RepositorioReserva, id_reserva: int, cancelar: bool = True
):
    """Marca ou desmarca uma reserva como cancelada."""
    atualizado = repo_reserva.atualizar(id_reserva, {"cancelada": cancelar})
    if not atualizado:
        raise ErroNucleoRegistro(
            f"Reserva com ID {id_reserva} não encontrada."
        )
    try:
        repo_reserva.obter_sessao().commit()
    except Exception as e:
        logger.exception("Falha ao atualizar cancelamento da reserva %s: %s", id_reserva, e)
        try:
            repo_reserva.obter_sessao().rollback()
        except Exception:
            pass
        raise ErroNucleoRegistro(f"Falha ao atualizar cancelamento da reserva: {e}") from e


def salvar_importacao_dados(
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    dados: List[Dict[str, Any]],
    repo_grupo: Optional[RepositorioGrupo] = None,
) -> Dict[str, int]:
    """Persiste dados importados de estudantes e reservas de forma atômica."""
    novos_estudantes = []
    reservas_para_criar = []
    todas_categorias_reservas: Set[str] = set()

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

        cats_linha = normalizar_lista_categorias(
            linha.get("categorias") if linha.get("categorias") is not None else linha.get("categoria")
        )
        todas_categorias_reservas.update(cats_linha)

        reservas_para_criar.append(
            {
                "payload": {
                    "prato": linha.get("prato"),
                    "data": data,
                    "cancelada": False,
                },
                "chave": id_banco if id_banco else pront,
                "categorias": cats_linha,
            }
        )

    unicos = (
        list({e["prontuario"]: e for e in novos_estudantes}.values())
        if novos_estudantes
        else []
    )
    if unicos:
        repo_estudante.criar_em_massa(unicos)

    mapa_ids = {}
    if unicos:
        pronts = {e["prontuario"] for e in unicos}
        objs = repo_estudante.por_prontuarios(pronts)
        mapa_ids = {e.prontuario: e.id for e in objs}

    reservas_finais = []
    categorias_por_chave: Dict[Tuple[int, str], List[str]] = {}
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
            if item["categorias"]:
                categorias_por_chave[(id_final, payload["data"])] = item["categorias"]

    if reservas_finais:
        repo_reserva.criar_em_massa(reservas_finais)

    if categorias_por_chave:
        sessao_db = repo_estudante.obter_sessao()
        rg = repo_grupo or RepositorioGrupo(sessao_db)
        mapa_grupos = rg.obter_ou_criar_por_nomes(
            todas_categorias_reservas, tipo=TIPO_GRUPO_CATEGORIA
        )
        est_ids = {k[0] for k in categorias_por_chave}
        datas = {k[1] for k in categorias_por_chave}
        reservas_db = (
            sessao_db.query(Reserva)
            .filter(Reserva.estudante_id.in_(est_ids), Reserva.data.in_(datas))
            .all()
        )
        assoc_rows = []
        for res in reservas_db:
            cats = categorias_por_chave.get((res.estudante_id, res.data), [])
            for c_nome in cats:
                g = mapa_grupos.get(c_nome)
                if g:
                    assoc_rows.append({"reserva_id": res.id, "grupo_id": g.id})
        if assoc_rows:
            sessao_db.execute(
                insert(associacao_reserva_grupo).prefix_with("OR IGNORE"),
                assoc_rows,
            )

    try:
        repo_estudante.obter_sessao().commit()
    except Exception as e:
        logger.exception("Falha ao salvar dados importados: %s", e)
        try:
            repo_estudante.obter_sessao().rollback()
        except Exception:
            pass
        raise ErroNucleoRegistro(f"Falha ao salvar importação de dados no banco: {e}") from e

    return {
        "estudantes_criados": len(unicos),
        "reservas_criadas": len(reservas_finais),
    }
