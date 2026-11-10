# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/services/estudante_service.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Serviço de gerenciamento de Estudantes (CRUD, filtros e buscas fuzzy).
"""

import logging
import re
from typing import Any, Dict, List, Optional

from fuzzywuzzy import fuzz
from sqlalchemy.orm import selectinload

from registro.nucleo.constants import TIPO_GRUPO_CATEGORIA, TIPO_GRUPO_TURMA
from registro.nucleo.exceptions import ErroNucleoRegistro
from registro.nucleo.models import Consumo, Estudante, Grupo, Reserva
from registro.nucleo.repository import (
    RepositorioConsumo,
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
)
from registro.nucleo.utils import (
    extrair_turmas_e_categorias,
    normalizar_lista_categorias,
)

logger = logging.getLogger(__name__)

REGEX_LIMPEZA_PRONTUARIO: re.Pattern[str] = re.compile(r"^[Ii][Qq]30+")


def _vincular_grupos_estudante(
    estudante: Estudante,
    repo_grupo: RepositorioGrupo,
    grupos: Optional[List[str]] = None,
    categorias: Optional[List[str]] = None,
) -> None:
    """Associa turmas e categorias ao estudante sem duplicar grupos existentes."""
    nomes_vistos = {g.nome for g in estudante.grupos}

    for grupo_nome in grupos or []:
        nome_limpo = (grupo_nome or "").strip()
        if not nome_limpo or nome_limpo in nomes_vistos:
            continue
        grupo = repo_grupo.por_nome(nome_limpo)
        if not grupo:
            grupo = repo_grupo.criar({"nome": nome_limpo, "tipo": TIPO_GRUPO_TURMA})
        estudante.grupos.append(grupo)
        nomes_vistos.add(nome_limpo)

    for cat_nome in normalizar_lista_categorias(categorias):
        if cat_nome in nomes_vistos:
            continue
        grupo = repo_grupo.por_nome(cat_nome)
        if not grupo:
            grupo = repo_grupo.criar({"nome": cat_nome, "tipo": TIPO_GRUPO_CATEGORIA})
        estudante.grupos.append(grupo)
        nomes_vistos.add(cat_nome)


def _serializar_estudante(est: Estudante) -> Dict[str, Any]:
    """Serializa estudante separando turmas reais de categorias/tags."""
    turmas, categorias = extrair_turmas_e_categorias(est)
    return {
        "id": est.id,
        "prontuario": est.prontuario,
        "nome": est.nome,
        "ativo": bool(est.ativo) if est.ativo is not None else True,
        "turma": ", ".join(turmas) if turmas else "N/A",
        "turmas": turmas,
        "categorias": categorias,
        "categoria": ", ".join(categorias) if categorias else "-",
        "grupos": [g.nome for g in est.grupos],
    }


def criar_estudante(
    repo_estudante: RepositorioEstudante,
    repo_grupo: RepositorioGrupo,
    prontuario: str,
    nome: str,
    grupos: Optional[List[str]] = None,
    categoria: Optional[str] = None,
    categorias: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Cria um novo estudante e associa às turmas e categorias fornecidas."""
    existente = repo_estudante.ler_filtrado(prontuario=prontuario)
    if existente:
        raise ValueError(f"Estudante com prontuário {prontuario} já existe.")

    novo_estudante = repo_estudante.criar(
        {"prontuario": prontuario, "nome": nome, "ativo": True}
    )

    lista_cats = list(categorias or [])
    if categoria:
        lista_cats.extend(normalizar_lista_categorias(categoria))

    _vincular_grupos_estudante(
        novo_estudante, repo_grupo, grupos=grupos, categorias=lista_cats
    )

    try:
        repo_estudante.obter_sessao().commit()
    except Exception as e:
        logger.exception("Falha ao criar estudante %s: %s", prontuario, e)
        try:
            repo_estudante.obter_sessao().rollback()
        except Exception:
            pass
        raise ErroNucleoRegistro(f"Falha ao criar estudante no banco de dados: {e}") from e

    _, cats_finais = extrair_turmas_e_categorias(novo_estudante)
    return {
        "id": novo_estudante.id,
        "prontuario": novo_estudante.prontuario,
        "nome": novo_estudante.nome,
        "categorias": cats_finais,
        "categoria": ", ".join(cats_finais) if cats_finais else "-",
    }


def atualizar_estudante(
    repo_estudante: RepositorioEstudante,
    id_estudante: int,
    dados: Dict[str, Any],
    repo_grupo: Optional[RepositorioGrupo] = None,
    grupos: Optional[List[str]] = None,
    categorias: Optional[List[str]] = None,
) -> bool:
    """Atualiza os dados de um estudante e suas turmas/categorias associadas."""
    sessao = repo_estudante.obter_sessao()
    estudante = (
        sessao.query(Estudante)
        .options(selectinload(Estudante.grupos))
        .filter(Estudante.id == id_estudante)
        .one_or_none()
    )
    if not estudante:
        return False

    for k, v in dados.items():
        if k == "categoria":
            continue
        if hasattr(estudante, k):
            setattr(estudante, k, v)

    if repo_grupo is not None and (grupos is not None or categorias is not None or "categoria" in dados):
        # Se ambos ou grupos+categorias foram passados explicitamente, substitui seletivamente
        turmas_atuais = [g.nome for g in estudante.grupos if not g.eh_categoria]
        cats_atuais = [g.nome for g in estudante.grupos if g.eh_categoria]

        novas_turmas = grupos if grupos is not None else turmas_atuais
        if categorias is not None:
            novas_cats = categorias
        elif "categoria" in dados:
            novas_cats = normalizar_lista_categorias(dados["categoria"])
        else:
            novas_cats = cats_atuais

        estudante.grupos.clear()
        _vincular_grupos_estudante(
            estudante, repo_grupo, grupos=novas_turmas, categorias=novas_cats
        )

    try:
        sessao.commit()
        return True
    except Exception as e:
        logger.exception("Falha ao atualizar estudante %s: %s", id_estudante, e)
        try:
            sessao.rollback()
        except Exception:
            pass
        raise ErroNucleoRegistro(f"Falha ao atualizar estudante no banco de dados: {e}") from e


def alternar_status_estudante(
    repo_estudante: RepositorioEstudante,
    id_estudante: int,
) -> bool:
    """Alterna o status ativo do estudante entre True e False."""
    sessao = repo_estudante.obter_sessao()
    estudante = repo_estudante.ler_um(id_estudante)
    if not estudante:
        return False
    estudante.ativo = not bool(estudante.ativo)
    try:
        sessao.commit()
        return True
    except Exception as e:
        logger.exception("Falha ao alternar status do estudante %s: %s", id_estudante, e)
        try:
            sessao.rollback()
        except Exception:
            pass
        raise ErroNucleoRegistro(f"Falha ao alternar status do estudante no banco: {e}") from e


def deletar_ou_desativar_estudante(
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    repo_consumo: RepositorioConsumo,
    id_estudante: int,
    forcar_desativacao: bool = False,
) -> Dict[str, Any]:
    """
    Exclusão segura de estudante.
    Se possuir histórico de consumo ou reservas e não forçar desativação,
    solicita desativação para não corromper integridade referencial.
    """
    sessao = repo_estudante.obter_sessao()
    estudante = (
        sessao.query(Estudante)
        .options(selectinload(Estudante.grupos))
        .filter(Estudante.id == id_estudante)
        .one_or_none()
    )
    if not estudante:
        return {"status": "not_found", "mensagem": "Estudante não encontrado."}

    # Verifica histórico em reservas ou consumos
    tem_reservas = (
        sessao.query(Reserva).filter(Reserva.estudante_id == id_estudante).count()
    )
    tem_consumos = (
        sessao.query(Consumo).filter(Consumo.estudante_id == id_estudante).count()
    )

    if (tem_reservas > 0 or tem_consumos > 0) and not forcar_desativacao:
        return {
            "status": "has_records",
            "mensagem": (
                f"O aluno '{estudante.nome}' possui histórico ({tem_reservas} reserva(s) e "
                f"{tem_consumos} consumo(s)). Ele não pode ser excluído permanentemente. "
                "Deseja apenas desativá-lo?"
            ),
            "reservas": tem_reservas,
            "consumos": tem_consumos,
        }

    if forcar_desativacao:
        estudante.ativo = False
        try:
            sessao.commit()
            return {
                "status": "deactivated",
                "mensagem": f"O aluno '{estudante.nome}' foi desativado com sucesso.",
            }
        except Exception as e:
            logger.exception("Falha ao desativar estudante %s: %s", id_estudante, e)
            try:
                sessao.rollback()
            except Exception:
                pass
            raise ErroNucleoRegistro(f"Falha ao desativar estudante no banco: {e}") from e

    # Sem histórico: pode excluir com segurança
    estudante.grupos.clear()
    sessao.delete(estudante)
    try:
        sessao.commit()
        return {
            "status": "deleted",
            "mensagem": f"O aluno '{estudante.nome}' foi excluído com sucesso.",
        }
    except Exception as e:
        logger.exception("Falha ao excluir estudante %s: %s", id_estudante, e)
        try:
            sessao.rollback()
        except Exception:
            pass
        raise ErroNucleoRegistro(f"Falha ao excluir estudante no banco: {e}") from e


def listar_todos_os_estudantes(
    repo_estudante: RepositorioEstudante,
) -> List[Dict[str, Any]]:
    """Retorna todos os estudantes com seus grupos associados."""
    sessao = repo_estudante.obter_sessao()
    estudantes = (
        sessao.query(Estudante)
        .options(selectinload(Estudante.grupos))
        .order_by(Estudante.nome)
        .all()
    )
    return [
        {
            "id": e.id,
            "prontuario": e.prontuario,
            "nome": e.nome,
            "ativo": e.ativo,
            "grupos": [g.nome for g in e.grupos],
        }
        for e in estudantes
    ]


def listar_estudantes(
    repo_estudante: RepositorioEstudante,
    termo_busca: Optional[str] = None,
    turma_nome: Optional[str] = None,
    status_ativo: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Lista estudantes com filtro textual opcional por nome, prontuário, turma e status ativo."""
    sessao = repo_estudante.obter_sessao()
    query = sessao.query(Estudante).options(selectinload(Estudante.grupos))

    if termo_busca and termo_busca.strip():
        termo_like = f"%{termo_busca.strip()}%"
        query = query.filter(
            (Estudante.nome.ilike(termo_like))
            | (Estudante.prontuario.ilike(termo_like))
        )

    if status_ativo is not None:
        query = query.filter(Estudante.ativo == status_ativo)

    if turma_nome and turma_nome != "Todas":
        query = query.filter(Estudante.grupos.any(Grupo.nome == turma_nome))

    estudantes = query.order_by(Estudante.nome).all()
    return [_serializar_estudante(est) for est in estudantes]


def listar_estudantes_fuzzy(
    repo_estudante: RepositorioEstudante,
    termo_busca: Optional[str] = None,
    limite: int = 60,
    turma_nome: Optional[str] = None,
    status_ativo: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Lista estudantes ordenados por relevância fuzzy, respeitando filtros de turma e status."""
    todos_estudantes = repo_estudante.ler_todos_com_grupos()

    # Aplica filtros prévios
    candidatos = []
    for est in todos_estudantes:
        if status_ativo is not None and bool(est.ativo) != status_ativo:
            continue
        if turma_nome and turma_nome != "Todas":
            nomes_grupos = [g.nome for g in est.grupos]
            if turma_nome not in nomes_grupos:
                continue
        candidatos.append(est)

    if not termo_busca or not termo_busca.strip():
        estudantes = sorted(candidatos, key=lambda e: e.nome)
    else:
        termo_lower = termo_busca.lower().strip()
        pront_lower = REGEX_LIMPEZA_PRONTUARIO.sub("", termo_lower)
        resultados_com_score = []
        for est in candidatos:
            score_nome = fuzz.partial_ratio(termo_lower, est.nome.lower())
            score_pront = fuzz.ratio(
                pront_lower,
                REGEX_LIMPEZA_PRONTUARIO.sub("", est.prontuario.lower()),
            )
            final_score = max(score_nome, score_pront)
            if final_score >= limite:
                resultados_com_score.append(
                    {"estudante": est, "score": final_score}
                )

        resultados_com_score.sort(key=lambda x: x["score"], reverse=True)
        estudantes = [item["estudante"] for item in resultados_com_score]

    return [_serializar_estudante(est) for est in estudantes]
