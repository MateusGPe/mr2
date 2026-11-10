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
    formatar_turnos_reserva,
    normalizar_lista_categorias,
    resolver_turnos_reserva,
)

logger = logging.getLogger(__name__)


def _validar_turnos_reserva(almoco: bool, jantar: bool) -> None:
    """Garante que a reserva possua pelo menos um turno (almoço ou jantar) marcado."""
    if not almoco and not jantar:
        raise ValueError("A reserva deve incluir pelo menos Almoço ou Jantar.")


def _limpar_chaves_turno_payload(payload: Dict[str, Any]) -> None:
    """Remove chaves auxiliares de turno antes de persistir no modelo Reserva."""
    for chave in ("almoço", "turno", "tipo_refeicao"):
        payload.pop(chave, None)


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

    almoco, jantar = resolver_turnos_reserva(payload)
    _validar_turnos_reserva(almoco, jantar)
    _limpar_chaves_turno_payload(payload)
    payload["almoco"] = almoco
    payload["jantar"] = jantar
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
        "almoco": bool(nova_reserva.almoco),
        "jantar": bool(nova_reserva.jantar),
        "turnos_str": formatar_turnos_reserva(bool(nova_reserva.almoco), bool(nova_reserva.jantar)),
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

    chaves_turno = {"almoco", "almoço", "jantar", "turno", "tipo_refeicao"}
    tem_turno = any(k in payload for k in chaves_turno)

    reserva = repo_reserva.ler_um(
        id_reserva, opcoes_carregamento=[selectinload(Reserva.grupos)]
    )
    if not reserva:
        return False

    if tem_turno:
        almoco, jantar = resolver_turnos_reserva(
            payload,
            default_almoco=bool(getattr(reserva, "almoco", True)),
            default_jantar=bool(getattr(reserva, "jantar", False)),
        )
        _validar_turnos_reserva(almoco, jantar)
        _limpar_chaves_turno_payload(payload)
        payload["almoco"] = almoco
        payload["jantar"] = jantar

    if payload:
        reserva = repo_reserva.atualizar(id_reserva, payload)

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
    try:
        if repo_reserva.deletar(id_reserva):
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
        if "almoco" in filtros:
            reservas = [r for r in reservas if bool(r.almoco) == bool(filtros["almoco"])]
        if "jantar" in filtros:
            reservas = [r for r in reservas if bool(r.jantar) == bool(filtros["jantar"])]
        if "cancelada" in filtros:
            reservas = [r for r in reservas if bool(r.cancelada) == bool(filtros["cancelada"])]
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
        alm = bool(getattr(res, "almoco", True))
        jan = bool(getattr(res, "jantar", False))
        resultado.append(
            {
                "id": res.id,
                "prontuario_estudante": res.estudante.prontuario,
                "nome_estudante": res.estudante.nome,
                "turma_estudante": ", ".join(turmas_est) if turmas_est else "N/A",
                "prato": res.prato,
                "data": res.data,
                "almoco": alm,
                "jantar": jan,
                "turnos_str": formatar_turnos_reserva(alm, jan),
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


def persistir_ou_mesclar_reservas(
    repo_reserva: RepositorioReserva,
    itens: List[Dict[str, Any]],
    repo_grupo: Optional[RepositorioGrupo] = None,
) -> Tuple[int, int]:
    """
    Persiste reservas em lote mesclando turnos (`almoco` / `jantar` via OR) e
    categorias quando já houver reserva para o mesmo `(estudante_id, data)`
    no mesmo lote ou no banco de dados.

    Retorna `(quantidade_criadas, quantidade_atualizadas)`.
    """
    if not itens:
        return 0, 0

    consolidado: Dict[Tuple[int, str], Dict[str, Any]] = {}
    todas_categorias: Set[str] = set()

    for item in itens:
        est_id = item["estudante_id"]
        data = item["data"]
        almoco = bool(item.get("almoco", True))
        jantar = bool(item.get("jantar", False))
        _validar_turnos_reserva(almoco, jantar)

        cats = normalizar_lista_categorias(item.get("categorias"))
        todas_categorias.update(cats)
        chave = (est_id, data)

        if chave not in consolidado:
            consolidado[chave] = {
                "estudante_id": est_id,
                "data": data,
                "prato": item.get("prato"),
                "almoco": almoco,
                "jantar": jantar,
                "cancelada": bool(item.get("cancelada", False)),
                "categorias": list(cats),
            }
        else:
            prev = consolidado[chave]
            prev["almoco"] = prev["almoco"] or almoco
            prev["jantar"] = prev["jantar"] or jantar
            if (not prev["prato"] or prev["prato"] == "Não especificado") and item.get("prato"):
                prev["prato"] = item.get("prato")
            for c in cats:
                if c not in prev["categorias"]:
                    prev["categorias"].append(c)

    sessao_db = repo_reserva.obter_sessao()
    est_ids = {k[0] for k in consolidado}
    datas = {k[1] for k in consolidado}
    existentes = (
        sessao_db.query(Reserva)
        .filter(Reserva.estudante_id.in_(est_ids), Reserva.data.in_(datas))
        .all()
    )
    mapa_existentes: Dict[Tuple[int, str], Reserva] = {
        (r.estudante_id, r.data): r for r in existentes
    }

    para_inserir: List[Dict[str, Any]] = []
    atualizadas = 0
    categorias_por_chave: Dict[Tuple[int, str], List[str]] = {}

    for chave, item in consolidado.items():
        if item["categorias"]:
            categorias_por_chave[chave] = item["categorias"]

        res_db = mapa_existentes.get(chave)
        if res_db is not None:
            novo_alm = bool(getattr(res_db, "almoco", True)) or item["almoco"]
            novo_jan = bool(getattr(res_db, "jantar", False)) or item["jantar"]
            mudou = (novo_alm != bool(res_db.almoco)) or (novo_jan != bool(res_db.jantar))
            res_db.almoco = novo_alm
            res_db.jantar = novo_jan
            if (not res_db.prato or res_db.prato == "Não especificado") and item["prato"]:
                res_db.prato = item["prato"]
                mudou = True
            if mudou:
                atualizadas += 1
        else:
            para_inserir.append(
                {
                    "estudante_id": item["estudante_id"],
                    "prato": item["prato"],
                    "data": item["data"],
                    "almoco": item["almoco"],
                    "jantar": item["jantar"],
                    "cancelada": item["cancelada"],
                }
            )

    if para_inserir:
        repo_reserva.criar_em_massa(para_inserir)

    if categorias_por_chave:
        rg = repo_grupo or RepositorioGrupo(sessao_db)
        mapa_grupos = rg.obter_ou_criar_por_nomes(
            todas_categorias, tipo=TIPO_GRUPO_CATEGORIA
        )
        est_cats = {k[0] for k in categorias_por_chave}
        datas_cats = {k[1] for k in categorias_por_chave}
        reservas_db = (
            sessao_db.query(Reserva)
            .filter(Reserva.estudante_id.in_(est_cats), Reserva.data.in_(datas_cats))
            .all()
        )
        assoc_rows = []
        for res in reservas_db:
            for c_nome in categorias_por_chave.get((res.estudante_id, res.data), []):
                g = mapa_grupos.get(c_nome)
                if g:
                    assoc_rows.append({"reserva_id": res.id, "grupo_id": g.id})
        if assoc_rows:
            sessao_db.execute(
                insert(associacao_reserva_grupo).prefix_with("OR IGNORE"),
                assoc_rows,
            )

    return len(para_inserir), atualizadas


def salvar_importacao_dados(
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    dados: List[Dict[str, Any]],
    repo_grupo: Optional[RepositorioGrupo] = None,
) -> Dict[str, int]:
    """Persiste dados importados de estudantes e reservas de forma atômica."""
    novos_estudantes = []
    reservas_para_criar = []

    for linha in dados:
        id_banco = linha.get("_id_banco")
        pront = linha.get("prontuario")

        if not (data := linha.get("data")):
            continue

        almoco, jantar = resolver_turnos_reserva(linha)
        _validar_turnos_reserva(almoco, jantar)

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

        reservas_para_criar.append(
            {
                "payload": {
                    "prato": linha.get("prato"),
                    "data": data,
                    "almoco": almoco,
                    "jantar": jantar,
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

    itens_reservas: List[Dict[str, Any]] = []
    for item in reservas_para_criar:
        chave = item["chave"]
        id_final = None

        if isinstance(chave, int):
            id_final = chave
        elif isinstance(chave, str):
            id_final = mapa_ids.get(chave)

        if id_final:
            payload = item["payload"]
            itens_reservas.append(
                {
                    "estudante_id": id_final,
                    "prato": payload["prato"],
                    "data": payload["data"],
                    "almoco": payload["almoco"],
                    "jantar": payload["jantar"],
                    "cancelada": payload["cancelada"],
                    "categorias": item["categorias"],
                }
            )

    criadas, atualizadas = persistir_ou_mesclar_reservas(
        repo_reserva, itens_reservas, repo_grupo=repo_grupo
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
        "reservas_criadas": criadas,
        "reservas_atualizadas": atualizadas,
    }
