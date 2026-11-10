# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/services/consumo_service.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Serviço de registro, validação de políticas de consumo e estorno de refeições.
Aplica princípios DRY e KISS através de um pipeline unificado de autorização.
"""

import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Set, Tuple

from sqlalchemy.orm import selectinload

from registro.nucleo import models
from registro.nucleo.repository import (
    RepositorioConsumo,
    RepositorioEstudante,
    RepositorioReserva,
    RepositorioSessao,
)
from registro.nucleo.services import grade_horarios_service
from registro.nucleo.services.sessao_service import obter_detalhes_sessao
from registro.nucleo.utils import extrair_turmas_e_categorias

logger = logging.getLogger(__name__)

PolicyEvaluator = Callable[
    [
        models.Sessao,
        models.Estudante,
        RepositorioReserva,
        Optional[Set[str]],
        bool,
        Optional[models.Reserva],
    ],
    Tuple[bool, str, str, Optional[int]],
]


def _obter_reserva_ativa_dia(
    repo_reserva: RepositorioReserva, estudante_id: int, data: str
) -> Optional[models.Reserva]:
    """Busca a reserva ativa (não cancelada) do estudante para a data informada, com grupos."""
    reservas = repo_reserva.ler_filtrado(
        opcoes_carregamento=[selectinload(models.Reserva.grupos)],
        estudante_id=estudante_id,
        data=data,
        cancelada=False,
    )
    return reservas[0] if reservas else None


def _grupos_efetivos_ids_e_nomes(
    estudante: models.Estudante, reserva_dia: Optional[models.Reserva]
) -> Tuple[Set[int], Set[str]]:
    """Retorna IDs e nomes combinando os grupos do estudante e os da reserva ativa na data."""
    ids = {g.id for g in estudante.grupos}
    nomes = {g.nome for g in estudante.grupos}
    if reserva_dia is not None and not getattr(reserva_dia, "cancelada", False):
        for g in getattr(reserva_dia, "grupos", None) or []:
            ids.add(g.id)
            nomes.add(g.nome)
    return ids, nomes


def _avaliar_regra_padrao(
    sessao: models.Sessao,
    estudante: models.Estudante,
    repo_reserva: RepositorioReserva,
    excecao_grupos: Optional[Set[str]],
    pular_grupos: bool,
    reserva_dia: Optional[models.Reserva] = None,
) -> Tuple[bool, str, str, Optional[int]]:
    """Aplica as regras de validação padrão (com reserva, ignorar grupos ou exceção)."""
    autorizado = False
    motivo = "Acesso Negado"
    prato = "Sem Reserva"
    id_reserva = None
    ids_grupos_estudante, nomes_estudante = _grupos_efetivos_ids_e_nomes(
        estudante, reserva_dia
    )

    if sessao.refeicao in ("almoço", "jantar"):
        reservas_candidatas = repo_reserva.ler_filtrado(
            estudante_id=estudante.id, data=sessao.data, cancelada=False
        )
        reservas = [
            r for r in reservas_candidatas
            if not (r.consumo and getattr(r.consumo, "ativo", False))
        ]
        if reservas:
            autorizado = True
            id_reserva = reservas[0].id
            motivo = "Autorizado com reserva."
            prato = reservas[0].prato or "Padrão"
        elif pular_grupos:
            autorizado = True
            motivo = "Autorizado por ignorar grupos."
            prato = "Sem Reserva (Forçado)"
        elif reservas_candidatas:
            autorizado = False
            motivo = "Reserva já utilizada nesta data."
            prato = "Reserva Utilizada"
        else:
            ids_excecao_grupos = {
                g.id for g in sessao.grupos if g.nome in (excecao_grupos or set())
            }
            if ids_excecao_grupos.intersection(ids_grupos_estudante):
                autorizado = True
                motivo = "Autorizado por exceção (grupo)."
                prato = "Sem Reserva (Grupo)"
            elif excecao_grupos and nomes_estudante.intersection(excecao_grupos):
                autorizado = True
                motivo = "Autorizado por exceção (grupo)."
                prato = "Sem Reserva (Grupo)"
    else:
        prato = sessao.item_servido or "Lanche"
        ids_grupos_sessao = {g.id for g in sessao.grupos}
        if pular_grupos or ids_grupos_sessao.intersection(ids_grupos_estudante):
            autorizado = True
            motivo = "Autorizado para lanche (grupo)."
        elif excecao_grupos:
            if nomes_estudante.intersection(excecao_grupos):
                autorizado = True
                motivo = "Autorizado por exceção (grupo)."

    return autorizado, motivo, prato, id_reserva


def _avaliar_regra_com_reserva(
    sessao: models.Sessao,
    estudante: models.Estudante,
    repo_reserva: RepositorioReserva,
    excecao_grupos: Optional[Set[str]],
    pular_grupos: bool,
    reserva_dia: Optional[models.Reserva] = None,
) -> Tuple[bool, str, str, Optional[int]]:
    """Aplica as regras estritas onde a reserva prévia é obrigatória."""
    id_reserva = None
    prato = "Sem Reserva"

    reservas = []
    reservas_candidatas = []
    if sessao.refeicao in ("almoço", "jantar"):
        reservas_candidatas = repo_reserva.ler_filtrado(
            opcoes_carregamento=[selectinload(models.Reserva.grupos)],
            estudante_id=estudante.id,
            data=sessao.data,
            cancelada=False,
        )
        reservas = [
            r for r in reservas_candidatas
            if not (r.consumo and getattr(r.consumo, "ativo", False))
        ]

    if not reservas:
        if sessao.refeicao in ("almoço", "jantar") and reservas_candidatas:
            return False, "Reserva já utilizada nesta data.", prato, id_reserva
        return False, "Sem reserva válida.", prato, id_reserva

    reserva_ativa = reservas[0]
    id_reserva = reserva_ativa.id
    prato = reserva_ativa.prato or "Padrão"

    _, nomes_grupos_estudante = _grupos_efetivos_ids_e_nomes(
        estudante, reserva_dia or reserva_ativa
    )
    nomes_grupos_sessao = {g.nome for g in sessao.grupos}

    grupo_autorizado = False
    motivo = "Acesso Negado"
    if pular_grupos:
        grupo_autorizado = True
        motivo = "Autorizado com reserva (grupos ignorados)."
    elif nomes_grupos_estudante.intersection(nomes_grupos_sessao):
        grupo_autorizado = True
        motivo = "Autorizado com reserva (grupo da sessão)."
    elif nomes_grupos_estudante.intersection(excecao_grupos or set()):
        grupo_autorizado = True
        motivo = "Autorizado com reserva (grupo de exceção)."

    if grupo_autorizado:
        return True, motivo, prato, id_reserva
    return False, "Com reserva, mas sem permissão de grupo.", prato, id_reserva


def _processar_consumo_pipeline(
    repo_sessao: RepositorioSessao,
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    repo_consumo: RepositorioConsumo,
    id_sessao: int,
    prontuario: str,
    avaliador_regra: PolicyEvaluator,
    excecao_grupos: Optional[Set[str]] = None,
    pular_grupos: bool = False,
    permitir_fora_horario: bool = False,
    ignorar_horario_grade: bool = False,
    filtro_categoria: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Pipeline unificado de autorização e registro de consumo (DRY + KISS).
    Valida existência de estudante, duplicidade de consumo, restrição de categoria,
    janela de horário, aplica a política e persiste o registro no banco em caso de sucesso.
    """
    sessao = obter_detalhes_sessao(repo_sessao, id_sessao)
    prontuario_limpo = (prontuario or "").strip().upper()
    estudantes = repo_estudante.ler_filtrado(prontuario=prontuario_limpo)
    if not estudantes and prontuario != prontuario_limpo:
        estudantes = repo_estudante.ler_filtrado(prontuario=prontuario)
    if not estudantes:
        return {"autorizado": False, "motivo": "Estudante não encontrado."}

    estudante = estudantes[0]
    reserva_dia = _obter_reserva_ativa_dia(repo_reserva, estudante.id, sessao.data)
    turmas_efetivas, categorias_efetivas = extrair_turmas_e_categorias(
        estudante, reserva_dia
    )
    turma = ", ".join(turmas_efetivas) if turmas_efetivas else "N/A"
    categoria = ", ".join(categorias_efetivas) if categorias_efetivas else "-"

    # 1. Duplicidade na mesma sessão
    consumo_existente = repo_consumo.ler_filtrado(
        estudante_id=estudante.id, sessao_id=id_sessao, ativo=True
    )
    if consumo_existente:
        return {
            "autorizado": False,
            "motivo": "Consumo já registrado.",
            "nome": estudante.nome,
            "aluno": estudante.nome,
            "prontuario": estudante.prontuario,
            "turma": turma,
            "categoria": categoria,
        }

    # 2. Cota diária por refeição e período (protegida mesmo com pular_grupos)
    sessao_db = repo_consumo.obter_sessao()
    refeicao_tipo = (sessao.refeicao or "").strip().lower()

    if refeicao_tipo in ("almoço", "jantar"):
        consumo_mesma_refeicao = (
            sessao_db.query(models.Consumo)
            .join(models.Consumo.sessao)
            .filter(
                models.Consumo.estudante_id == estudante.id,
                models.Consumo.ativo.is_(True),
                models.Sessao.data == sessao.data,
                models.Sessao.refeicao.ilike(refeicao_tipo),
            )
            .first()
        )
        if consumo_mesma_refeicao:
            return {
                "autorizado": False,
                "motivo": f"Consumo de {refeicao_tipo} já registrado nesta data (Cota diária atingida).",
                "nome": estudante.nome,
                "aluno": estudante.nome,
                "prontuario": estudante.prontuario,
                "turma": turma,
                "categoria": categoria,
            }
    elif refeicao_tipo == "lanche":
        periodo_sessao = (sessao.periodo or "").strip()
        query_lanche = (
            sessao_db.query(models.Consumo)
            .join(models.Consumo.sessao)
            .filter(
                models.Consumo.estudante_id == estudante.id,
                models.Consumo.ativo.is_(True),
                models.Sessao.data == sessao.data,
                models.Sessao.refeicao.ilike("lanche"),
            )
        )
        if periodo_sessao:
            query_lanche = query_lanche.filter(models.Sessao.periodo.ilike(periodo_sessao))
        consumo_lanche_existente = query_lanche.first()
        if consumo_lanche_existente:
            detalhe_periodo = f" no período {periodo_sessao}" if periodo_sessao else ""
            return {
                "autorizado": False,
                "motivo": f"Lanche já consumido nesta data{detalhe_periodo} (Cota atingida).",
                "nome": estudante.nome,
                "aluno": estudante.nome,
                "prontuario": estudante.prontuario,
                "turma": turma,
                "categoria": categoria,
            }

    # Validação de janela de horário
    if not permitir_fora_horario and not pular_grupos:
        valido, motivo_horario = grade_horarios_service.validar_janela_horario(
            turmas_estudante=turmas_efetivas,
            refeicao=sessao.refeicao,
            categorias_estudante=categorias_efetivas,
            ignorar_horario=ignorar_horario_grade,
        )
        if not valido:
            return {
                "autorizado": False,
                "motivo": motivo_horario,
                "aluno": estudante.nome,
                "nome": estudante.nome,
                "prontuario": estudante.prontuario,
                "turma": turma,
                "categoria": categoria,
                "categorias": categorias_efetivas,
            }

    autorizado, motivo, prato, id_reserva = avaliador_regra(
        sessao, estudante, repo_reserva, excecao_grupos, pular_grupos, reserva_dia
    )

    hora_consumo = ""
    if autorizado:
        hora_consumo = datetime.now().strftime("%H:%M:%S")
        payload = {
            "estudante_id": estudante.id,
            "sessao_id": sessao.id,
            "hora_consumo": hora_consumo,
            "reserva_id": id_reserva,
            "ativo": True,
        }
        try:
            repo_consumo.criar(payload)
            repo_consumo.obter_sessao().commit()
        except Exception as e:
            logger.exception("Falha ao salvar consumo no banco de dados: %s", e)
            try:
                repo_consumo.obter_sessao().rollback()
            except Exception:
                pass
            return {
                "autorizado": False,
                "motivo": "Erro de gravação no banco de dados. Tente novamente.",
                "aluno": estudante.nome,
                "nome": estudante.nome,
                "prontuario": estudante.prontuario,
                "turma": turma,
                "categoria": categoria,
            }

    return {
        "autorizado": autorizado,
        "motivo": motivo,
        "aluno": estudante.nome,
        "nome": estudante.nome,
        "prontuario": estudante.prontuario,
        "turma": turma,
        "categoria": categoria,
        "categorias": categorias_efetivas,
        "prato": prato,
        "hora_consumo": hora_consumo,
    }


def registrar_consumo(
    repo_sessao: RepositorioSessao,
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    repo_consumo: RepositorioConsumo,
    id_sessao: int,
    prontuario: str,
    excecao_grupos: Optional[Set[str]] = None,
    excessao_grupos: Optional[Set[str]] = None,
    pular_grupos: bool = False,
    permitir_fora_horario: bool = False,
    ignorar_horario_grade: bool = False,
    filtro_categoria: Optional[str] = None,
) -> Dict[str, Any]:
    """Aplica a lógica de autorização padrão e, se bem-sucedido, registra o consumo."""
    grupos_filtro = excecao_grupos if excecao_grupos is not None else excessao_grupos
    return _processar_consumo_pipeline(
        repo_sessao=repo_sessao,
        repo_estudante=repo_estudante,
        repo_reserva=repo_reserva,
        repo_consumo=repo_consumo,
        id_sessao=id_sessao,
        prontuario=prontuario,
        avaliador_regra=_avaliar_regra_padrao,
        excecao_grupos=grupos_filtro,
        pular_grupos=pular_grupos,
        permitir_fora_horario=permitir_fora_horario,
        ignorar_horario_grade=ignorar_horario_grade,
        filtro_categoria=filtro_categoria,
    )


def registrar_consumo_com_reserva(
    repo_sessao: RepositorioSessao,
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    repo_consumo: RepositorioConsumo,
    id_sessao: int,
    prontuario: str,
    excecao_grupos: Optional[Set[str]] = None,
    excessao_grupos: Optional[Set[str]] = None,
    pular_grupos: bool = False,
    permitir_fora_horario: bool = False,
    ignorar_horario_grade: bool = False,
    filtro_categoria: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Aplica a lógica de autorização estrita (com reserva obrigatória) e registra o consumo.
    """
    grupos_filtro = excecao_grupos if excecao_grupos is not None else excessao_grupos
    return _processar_consumo_pipeline(
        repo_sessao=repo_sessao,
        repo_estudante=repo_estudante,
        repo_reserva=repo_reserva,
        repo_consumo=repo_consumo,
        id_sessao=id_sessao,
        prontuario=prontuario,
        avaliador_regra=_avaliar_regra_com_reserva,
        excecao_grupos=grupos_filtro,
        pular_grupos=pular_grupos,
        permitir_fora_horario=permitir_fora_horario,
        ignorar_horario_grade=ignorar_horario_grade,
        filtro_categoria=filtro_categoria,
    )


def desfazer_consumo(
    repo_consumo: RepositorioConsumo,
    id_consumo: int,
    operador: str = "Operador",
    motivo: str = "Cancelado pelo operador",
) -> bool:
    """Cancela logicamente um registro de consumo do banco de dados (soft delete)."""
    consumo = repo_consumo.ler_um(id_consumo)
    if consumo:
        consumo.ativo = False
        consumo.deletado_em = datetime.now()
        consumo.deletado_por = operador
        consumo.motivo_cancelamento = motivo
        try:
            repo_consumo.obter_sessao().commit()
            return True
        except Exception as e:
            logger.exception("Falha ao desfazer consumo %s: %s", id_consumo, e)
            try:
                repo_consumo.obter_sessao().rollback()
            except Exception:
                pass
            return False
    return False


def desfazer_consumo_por_prontuario(
    repo_consumo: RepositorioConsumo,
    prontuario: str,
    id_sessao: int,
    operador: str = "Operador",
    motivo: str = "Cancelado pelo operador",
) -> bool:
    """Cancela logicamente um registro de consumo pelo prontuário e id da sessão (soft delete)."""
    consumo = repo_consumo.por_prontuario_e_sessao(
        prontuario, id_sessao, apenas_ativo=True
    )
    if consumo:
        consumo.ativo = False
        consumo.deletado_em = datetime.now()
        consumo.deletado_por = operador
        consumo.motivo_cancelamento = motivo
        try:
            repo_consumo.obter_sessao().commit()
            return True
        except Exception as e:
            logger.exception("Falha ao desfazer consumo por prontuário %s: %s", prontuario, e)
            try:
                repo_consumo.obter_sessao().rollback()
            except Exception:
                pass
            return False
    return False


def atualizar_consumo(
    repo_consumo: RepositorioConsumo,
    repo_reserva: RepositorioReserva,
    id_consumo: int,
    hora_consumo: Optional[str] = None,
    prato: Optional[str] = None,
) -> bool:
    """Atualiza campos de um registro de consumo (horário e prato da reserva associada)."""
    consumo = repo_consumo.ler_um(id_consumo)
    if not consumo:
        return False

    if hora_consumo is not None:
        consumo.hora_consumo = hora_consumo.strip()

    if prato is not None:
        prato_limpo = prato.strip()
        if consumo.reserva_id:
            reserva = repo_reserva.ler_um(consumo.reserva_id)
            if reserva:
                reserva.prato = prato_limpo
        else:
            data_sessao = consumo.sessao.data if consumo.sessao else None
            if data_sessao:
                reservas = repo_reserva.ler_filtrado(
                    estudante_id=consumo.estudante_id,
                    data=data_sessao,
                    cancelada=False,
                )
                if reservas:
                    reserva = reservas[0]
                    reserva.prato = prato_limpo
                    consumo.reserva_id = reserva.id
                else:
                    nova_reserva = repo_reserva.criar(
                        {
                            "estudante_id": consumo.estudante_id,
                            "data": data_sessao,
                            "prato": prato_limpo,
                            "cancelada": False,
                        }
                    )
                    consumo.reserva_id = nova_reserva.id

    try:
        repo_consumo.obter_sessao().commit()
        return True
    except Exception as e:
        logger.exception("Falha ao atualizar consumo %s: %s", id_consumo, e)
        try:
            repo_consumo.obter_sessao().rollback()
        except Exception:
            pass
        return False
