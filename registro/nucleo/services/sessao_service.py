# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/services/sessao_service.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Serviço de gerenciamento do ciclo de vida, estado e consultas de Sessões de Refeição.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import select, union
from sqlalchemy.orm import selectinload

from registro.nucleo import constants, models
from registro.nucleo.exceptions import ErroSessao
from registro.nucleo.models import Consumo, Estudante, Reserva, Sessao
from registro.nucleo.repository import (
    RepositorioConsumo,
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
    RepositorioSessao,
)
from registro.nucleo.utils import (
    DADOS_SESSAO,
    extrair_turmas_e_categorias,
    para_codigo,
    rollback_seguro,
)

logger = logging.getLogger(__name__)


def iniciar_nova_sessao(
    repo_sessao: RepositorioSessao,
    repo_grupo: RepositorioGrupo,
    repo_reserva: RepositorioReserva,
    dados_sessao: DADOS_SESSAO,
) -> Optional[int]:
    """Inicia uma nova sessão de refeição e a associa aos grupos selecionados."""
    refeicao = dados_sessao["refeicao"].lower()
    data_formatada = datetime.strptime(dados_sessao["data"], "%Y-%m-%d").strftime(
        "%d/%m/%Y"
    )

    if refeicao in ("almoço", "jantar"):
        filtro_ref = {"almoco": True} if refeicao == "almoço" else {"jantar": True}
        reservas = repo_reserva.ler_filtrado(
            data=data_formatada, cancelada=False, **filtro_ref
        )
        if not reservas:
            return None

    payload_sessao = {
        "refeicao": refeicao,
        "periodo": dados_sessao["periodo"],
        "data": data_formatada,
        "hora": dados_sessao["hora"],
        "item_servido": dados_sessao.get("item_servido"),
    }

    nova_sessao_db = repo_sessao.criar(payload_sessao)

    if dados_sessao["grupos"]:
        grupos_db = repo_grupo.por_nomes(set(dados_sessao["grupos"]))
        nova_sessao_db.grupos.extend(grupos_db)

    try:
        repo_sessao.obter_sessao().commit()
        return nova_sessao_db.id
    except Exception as e:
        logger.exception("Falha ao iniciar nova sessão: %s", e)
        rollback_seguro(repo_sessao.obter_sessao())
        raise ErroSessao(f"Falha ao iniciar nova sessão no banco de dados: {e}") from e


def listar_todas_sessoes(repo_sessao: RepositorioSessao) -> List[Dict[str, Any]]:
    """Retorna uma lista simplificada de todas as sessões existentes."""
    sessoes = repo_sessao.ler_todos()
    return [
        {
            "id": s.id,
            "refeicao": s.refeicao,
            "periodo": s.periodo,
            "data": s.data,
            "hora": s.hora,
            "item_servido": s.item_servido,
            "grupos": [g.nome for g in s.grupos],
        }
        for s in sessoes
    ]


def listar_todos_os_grupos(repo_grupo: RepositorioGrupo) -> List[Dict[str, Any]]:
    """Retorna uma lista de todos os grupos existentes com seu tipo ('turma' ou 'categoria')."""
    grupos = repo_grupo.ler_todos()
    return [
        {
            "id": g.id,
            "nome": g.nome,
            "tipo": getattr(g, "tipo", constants.TIPO_GRUPO_TURMA) or constants.TIPO_GRUPO_TURMA,
        }
        for g in grupos
    ]


def obter_detalhes_sessao(
    repo_sessao: RepositorioSessao, id_sessao: int
) -> models.Sessao:
    """
    Retorna o objeto de uma sessão específica a partir do seu ID,
    carregando seus grupos de forma otimizada.
    """
    opcoes = [selectinload(Sessao.grupos)]
    sessao = repo_sessao.ler_um(id_sessao, opcoes_carregamento=opcoes)
    if not sessao:
        raise ErroSessao(f"Sessão com ID {id_sessao} não encontrada.")
    return sessao


def obter_estudantes_para_sessao(
    repo_sessao: RepositorioSessao,
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    repo_consumo: RepositorioConsumo,
    repo_grupo: RepositorioGrupo,
    id_sessao: int,
    consumido: Optional[bool] = None,
    excecao_grupos: Optional[Set[str]] = None,
    pular_grupos: bool = False,
) -> List[Dict[str, Any]]:
    """Busca estudantes elegíveis ou atendidos para uma sessão."""
    sessao = obter_detalhes_sessao(repo_sessao, id_sessao)
    db_session = repo_estudante.obter_sessao()
    EstudanteGrupo = models.associacao_estudante_grupo

    ids_grupos_sessao = {g.id for g in sessao.grupos}
    ids_excecao_grupos = {
        g.id for g in repo_grupo.por_nomes(excecao_grupos or set())
    }

    q1 = select(EstudanteGrupo.c.estudante_id).where(
        EstudanteGrupo.c.grupo_id.in_(ids_grupos_sessao)
    )

    q2 = select(EstudanteGrupo.c.estudante_id).where(
        EstudanteGrupo.c.grupo_id.in_(ids_excecao_grupos)
    )

    condicoes_q3 = [Reserva.data == sessao.data, Reserva.cancelada.is_(False)]
    if sessao.refeicao == "almoço":
        condicoes_q3.append(Reserva.almoco.is_(True))
    elif sessao.refeicao == "jantar":
        condicoes_q3.append(Reserva.jantar.is_(True))

    q3 = select(Reserva.estudante_id).where(*condicoes_q3)

    query_ids_elegiveis = union(q1, q2, q3).subquery()

    if consumido is True:
        consumos_na_sessao = (
            select(Consumo.estudante_id)
            .where(Consumo.sessao_id == id_sessao, Consumo.ativo.is_(True))
            .subquery()
        )
        stmt = select(Estudante.id).join(
            consumos_na_sessao, Estudante.id == consumos_na_sessao.c.estudante_id
        )
    elif pular_grupos:
        stmt = select(Estudante.id).where(Estudante.ativo.is_(True))
    else:
        stmt = (
            select(Estudante.id)
            .join(
                query_ids_elegiveis,
                Estudante.id == query_ids_elegiveis.c.estudante_id,
            )
            .where(Estudante.ativo.is_(True))
        )

    ids_para_buscar = set(db_session.execute(stmt).scalars().all())
    if not ids_para_buscar:
        return []

    opcoes_carregamento = [selectinload(Estudante.grupos)]
    estudantes = repo_estudante.ler_filtrado(
        opcoes_carregamento=opcoes_carregamento,
        id=Estudante.id.in_(ids_para_buscar),
    )

    mapa_consumos_por_estudante = {
        c.estudante_id: c for c in repo_consumo.ler_filtrado(sessao_id=id_sessao)
    }
    mapa_reservas_dia = {
        r.estudante_id: r
        for r in repo_reserva.ler_filtrado(
            opcoes_carregamento=[selectinload(Reserva.grupos)],
            data=sessao.data,
            cancelada=False,
        )
    }

    detalhes_estudantes = []
    for est in estudantes:
        autorizado = False
        motivo = "Acesso Negado"
        prato = "Sem Reserva"

        reserva = mapa_reservas_dia.get(est.id)
        ids_grupos_estudante = {g.id for g in est.grupos}
        if reserva and not reserva.cancelada:
            ids_grupos_estudante |= {g.id for g in reserva.grupos}

        if sessao.refeicao in ("almoço", "jantar"):
            reserva_ref_valida = reserva is not None and (
                (sessao.refeicao == "almoço" and bool(getattr(reserva, "almoco", True)))
                or (sessao.refeicao == "jantar" and bool(getattr(reserva, "jantar", False)))
            )
            if reserva_ref_valida:
                autorizado = True
                motivo = "Reserva"
                prato = reserva.prato
            elif (
                ids_excecao_grupos.intersection(ids_grupos_estudante)
                or pular_grupos
            ):
                autorizado = True
                motivo = "Exceção (Grupo)"
        elif (
            ids_grupos_sessao.intersection(ids_grupos_estudante)
            or pular_grupos
        ):
            autorizado = True
            motivo = "Autorizado (Grupo)"
            prato = sessao.item_servido or "Lanche"
        elif ids_excecao_grupos.intersection(ids_grupos_estudante):
            autorizado = True
            motivo = "Exceção (Grupo)"
            prato = sessao.item_servido or "Lanche"

        info_consumo = mapa_consumos_por_estudante.get(est.id)
        if consumido is True:
            if not info_consumo:
                continue
            if not autorizado:
                autorizado = True
                motivo = "Registrado (Exceção/Bypass)"
                if info_consumo.reserva:
                    prato = info_consumo.reserva.prato or "Padrão"
                elif sessao.refeicao == "lanche":
                    prato = sessao.item_servido or "Lanche"
        elif not autorizado:
            continue

        if consumido is False and info_consumo:
            continue

        turmas_est, cats_est = extrair_turmas_e_categorias(est, reserva)

        detalhes_estudantes.append(
            {
                "pront": est.prontuario,
                "nome": est.nome,
                "turma": ", ".join(turmas_est) if turmas_est else "N/A",
                "turmas": turmas_est,
                "categorias": cats_est,
                "categoria": ", ".join(cats_est) if cats_est else "-",
                "prato": prato,
                "consumido": bool(info_consumo),
                "id_consumo": info_consumo.id if info_consumo else None,
                "hora_consumo": info_consumo.hora_consumo
                if info_consumo
                else "",
                "status": motivo,
                **para_codigo(est.prontuario),
            }
        )

    return detalhes_estudantes


def deletar_sessao(repo_sessao: RepositorioSessao, id_sessao: int):
    """Deleta uma sessão e seus consumos associados (via cascade do DB)."""
    if not repo_sessao.deletar(id_sessao):
        raise ErroSessao(
            f"Sessão com ID {id_sessao} não encontrada para exclusão."
        )
    try:
        repo_sessao.obter_sessao().commit()
    except Exception as e:
        logger.exception("Falha ao deletar sessão %s: %s", id_sessao, e)
        rollback_seguro(repo_sessao.obter_sessao())
        raise ErroSessao(f"Falha ao excluir sessão do banco de dados: {e}") from e


def atualizar_sessao(
    repo_sessao: RepositorioSessao, id_sessao: int, dados: Dict[str, Any]
):
    """Atualiza os dados de uma sessão existente."""
    dados.pop("grupos", None)
    sessao_atualizada = repo_sessao.atualizar(id_sessao, dados)
    if not sessao_atualizada:
        raise ErroSessao(
            f"Sessão com ID {id_sessao} não encontrada para atualização."
        )
    try:
        repo_sessao.obter_sessao().commit()
        return sessao_atualizada
    except Exception as e:
        logger.exception("Falha ao atualizar sessão %s: %s", id_sessao, e)
        rollback_seguro(repo_sessao.obter_sessao())
        raise ErroSessao(f"Falha ao atualizar sessão no banco de dados: {e}") from e


def atualizar_grupos_sessao(
    repo_sessao: RepositorioSessao,
    repo_grupo: RepositorioGrupo,
    id_sessao: int,
    nomes_grupos: List[str],
):
    """Atualiza a lista de grupos autorizados para uma sessão."""
    sessao = obter_detalhes_sessao(repo_sessao, id_sessao)
    grupos_db = repo_grupo.por_nomes(set(nomes_grupos))
    sessao.grupos = grupos_db
    try:
        repo_sessao.obter_sessao().commit()
    except Exception as e:
        logger.exception("Falha ao atualizar grupos da sessão %s: %s", id_sessao, e)
        rollback_seguro(repo_sessao.obter_sessao())
        raise ErroSessao(f"Falha ao atualizar grupos da sessão no banco de dados: {e}") from e


def carregar_estado_sessao(fachada: Any) -> Optional[Dict[str, Any]]:
    """Carrega o arquivo session.json e define a sessão ativa na fachada se existir."""
    if not constants.CAMINHO_SESSAO.exists():
        logger.info(
            "Arquivo de estado da sessão não encontrado: %s",
            constants.CAMINHO_SESSAO,
        )
        return None
    try:
        with open(constants.CAMINHO_SESSAO, "r", encoding="utf-8") as f:
            dados = json.load(f)
        logger.info(
            "Estado da sessão carregado: %s", constants.CAMINHO_SESSAO
        )
        if "id_sessao" in dados:
            fachada.definir_sessao_ativa(dados["id_sessao"])
        if "excecao_grupos" in dados and hasattr(fachada, "excecao_grupos"):
            fachada.excecao_grupos = set(dados.get("excecao_grupos") or [])
        if hasattr(fachada, "ignorar_horario_grade"):
            fachada.ignorar_horario_grade = bool(dados.get("ignorar_horario_grade", False))
        return dados
    except (OSError, json.JSONDecodeError, ValueError, ErroSessao) as e:
        logger.error(
            "Erro ao carregar estado da sessão de %s: %s",
            constants.CAMINHO_SESSAO,
            e,
        )
        return None


def salvar_estado_sessao(
    fachada: Any, id_sessao: Optional[int] = None
) -> bool:
    """Salva o estado da sessão ativa no arquivo session.json."""
    sid = (
        id_sessao
        if id_sessao is not None
        else getattr(fachada, "id_sessao_ativa", None)
    )
    if sid is None:
        return False
    try:
        excecao_grupos = list(getattr(fachada, "excecao_grupos", []))
        ignorar_horario_grade = getattr(fachada, "ignorar_horario_grade", False) is True
        payload = {
            "id_sessao": sid,
            "excecao_grupos": excecao_grupos,
            "ignorar_horario_grade": ignorar_horario_grade,
        }
        constants.CAMINHO_SESSAO.parent.mkdir(parents=True, exist_ok=True)
        constants.CAMINHO_SESSAO.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(
            "Estado da sessão salvo em %s.", constants.CAMINHO_SESSAO
        )
        return True
    except (OSError, TypeError, ValueError) as e:
        logger.error(
            "Erro ao salvar estado da sessão em %s: %s",
            constants.CAMINHO_SESSAO,
            e,
        )
        return False


def limpar_estado_sessao(fachada: Any) -> bool:
    """Remove o arquivo session.json e desativa a sessão."""
    try:
        constants.CAMINHO_SESSAO.unlink(missing_ok=True)
        fachada.id_sessao_ativa = None
        if hasattr(fachada, "ignorar_horario_grade"):
            fachada.ignorar_horario_grade = False
        logger.info("Estado da sessão limpo: %s", constants.CAMINHO_SESSAO)
        return True
    except OSError as e:
        logger.error("Erro ao limpar estado da sessão: %s", e)
        return False

