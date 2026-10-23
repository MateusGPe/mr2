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

from registro.nucleo import models
from registro.nucleo.repository import (
    RepositorioConsumo,
    RepositorioEstudante,
    RepositorioReserva,
    RepositorioSessao,
)
from registro.nucleo.services.sessao_service import obter_detalhes_sessao

logger = logging.getLogger(__name__)

PolicyEvaluator = Callable[
    [models.Sessao, models.Estudante, RepositorioReserva, Optional[Set[str]], bool],
    Tuple[bool, str, str, Optional[int]],
]


def _avaliar_regra_padrao(
    sessao: models.Sessao,
    estudante: models.Estudante,
    repo_reserva: RepositorioReserva,
    excecao_grupos: Optional[Set[str]],
    pular_grupos: bool,
) -> Tuple[bool, str, str, Optional[int]]:
    """Aplica as regras de validação padrão (com reserva, ignorar grupos ou exceção)."""
    autorizado = False
    motivo = "Acesso Negado"
    prato = "Sem Reserva"
    id_reserva = None

    if sessao.refeicao == "almoço":
        reservas = repo_reserva.ler_filtrado(
            estudante_id=estudante.id, data=sessao.data, cancelada=False
        )
        if reservas:
            autorizado = True
            id_reserva = reservas[0].id
            motivo = "Autorizado com reserva."
            prato = reservas[0].prato or "Padrão"
        elif pular_grupos:
            autorizado = True
            motivo = "Autorizado por ignorar grupos."
            prato = "Sem Reserva (Forçado)"
        else:
            ids_excecao_grupos = {
                g.id for g in sessao.grupos if g.nome in (excecao_grupos or set())
            }
            ids_grupos_estudante = {g.id for g in estudante.grupos}
            if ids_excecao_grupos.intersection(ids_grupos_estudante):
                autorizado = True
                motivo = "Autorizado por exceção (grupo)."
                prato = "Sem Reserva (Grupo)"
    else:
        prato = sessao.item_servido or "Lanche"
        ids_grupos_sessao = {g.id for g in sessao.grupos}
        ids_grupos_estudante = {g.id for g in estudante.grupos}
        if ids_grupos_sessao.intersection(ids_grupos_estudante):
            autorizado = True
            motivo = "Autorizado para lanche (grupo)."

    return autorizado, motivo, prato, id_reserva


def _avaliar_regra_com_reserva(
    sessao: models.Sessao,
    estudante: models.Estudante,
    repo_reserva: RepositorioReserva,
    excecao_grupos: Optional[Set[str]],
    pular_grupos: bool,
) -> Tuple[bool, str, str, Optional[int]]:
    """Aplica as regras estritas onde a reserva prévia é obrigatória."""
    id_reserva = None
    prato = "Sem Reserva"

    reservas = []
    if sessao.refeicao == "almoço":
        reservas = repo_reserva.ler_filtrado(
            estudante_id=estudante.id, data=sessao.data, cancelada=False
        )

    if not reservas:
        return False, "Sem reserva válida.", prato, id_reserva

    id_reserva = reservas[0].id
    prato = reservas[0].prato or "Padrão"

    nomes_grupos_estudante = {g.nome for g in estudante.grupos}
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
) -> Dict[str, Any]:
    """
    Pipeline unificado de autorização e registro de consumo (DRY + KISS).
    Valida existência de estudante, duplicidade de consumo, aplica a política
    e persiste o registro no banco em caso de sucesso.
    """
    sessao = obter_detalhes_sessao(repo_sessao, id_sessao)
    estudantes = repo_estudante.ler_filtrado(prontuario=prontuario)
    if not estudantes:
        return {"autorizado": False, "motivo": "Estudante não encontrado."}

    estudante = estudantes[0]
    turma = (
        ", ".join(sorted(g.nome for g in estudante.grupos))
        if estudante.grupos
        else "N/A"
    )

    consumo_existente = repo_consumo.ler_filtrado(
        estudante_id=estudante.id, sessao_id=id_sessao
    )
    if consumo_existente:
        return {
            "autorizado": False,
            "motivo": "Consumo já registrado.",
            "nome": estudante.nome,
            "aluno": estudante.nome,
            "prontuario": estudante.prontuario,
            "turma": turma,
        }

    autorizado, motivo, prato, id_reserva = avaliador_regra(
        sessao, estudante, repo_reserva, excecao_grupos, pular_grupos
    )

    hora_consumo = ""
    if autorizado:
        hora_consumo = datetime.now().strftime("%H:%M:%S")
        payload = {
            "estudante_id": estudante.id,
            "sessao_id": sessao.id,
            "hora_consumo": hora_consumo,
            "reserva_id": id_reserva,
        }
        repo_consumo.criar(payload)
        repo_consumo.obter_sessao().commit()

    return {
        "autorizado": autorizado,
        "motivo": motivo,
        "aluno": estudante.nome,
        "nome": estudante.nome,
        "prontuario": estudante.prontuario,
        "turma": turma,
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
    pular_grupos: bool = False,
) -> Dict[str, Any]:
    """Aplica a lógica de autorização padrão e, se bem-sucedido, registra o consumo."""
    return _processar_consumo_pipeline(
        repo_sessao=repo_sessao,
        repo_estudante=repo_estudante,
        repo_reserva=repo_reserva,
        repo_consumo=repo_consumo,
        id_sessao=id_sessao,
        prontuario=prontuario,
        avaliador_regra=_avaliar_regra_padrao,
        excecao_grupos=excecao_grupos,
        pular_grupos=pular_grupos,
    )


def registrar_consumo_com_reserva(
    repo_sessao: RepositorioSessao,
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    repo_consumo: RepositorioConsumo,
    id_sessao: int,
    prontuario: str,
    excecao_grupos: Optional[Set[str]] = None,
    pular_grupos: bool = False,
) -> Dict[str, Any]:
    """
    Aplica a lógica de autorização estrita (com reserva obrigatória) e registra o consumo.
    """
    return _processar_consumo_pipeline(
        repo_sessao=repo_sessao,
        repo_estudante=repo_estudante,
        repo_reserva=repo_reserva,
        repo_consumo=repo_consumo,
        id_sessao=id_sessao,
        prontuario=prontuario,
        avaliador_regra=_avaliar_regra_com_reserva,
        excecao_grupos=excecao_grupos,
        pular_grupos=pular_grupos,
    )


def desfazer_consumo(repo_consumo: RepositorioConsumo, id_consumo: int):
    """Remove um registro de consumo do banco de dados."""
    if repo_consumo.deletar(id_consumo):
        repo_consumo.obter_sessao().commit()


def desfazer_consumo_por_prontuario(
    repo_consumo: RepositorioConsumo, prontuario: str, id_sessao: int
) -> bool:
    """Remove um registro de consumo pelo prontuário e id da sessão."""
    consumo = repo_consumo.por_prontuario_e_sessao(prontuario, id_sessao)
    if consumo and repo_consumo.deletar(consumo.id):
        repo_consumo.obter_sessao().commit()
        return True
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

    repo_consumo.obter_sessao().commit()
    return True
