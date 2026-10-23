# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/services/stats_service.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Serviço de agregação analítica e estatísticas para sessões e dashboards.
"""

import datetime as dt
import logging
from typing import Any, Dict, Optional, Set

from sqlalchemy.orm import selectinload

from registro.nucleo.models import Consumo, Estudante, Grupo, Reserva, Sessao
from registro.nucleo.repository import (
    RepositorioConsumo,
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
    RepositorioSessao,
)
from registro.nucleo.services.sessao_service import (
    obter_detalhes_sessao,
    obter_estudantes_para_sessao,
)

logger = logging.getLogger(__name__)


def obter_estatisticas_dashboard(
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    repo_grupo: RepositorioGrupo,
    repo_consumo: RepositorioConsumo,
) -> Dict[str, Any]:
    """Calcula estatísticas consolidadas e distribuições para o dashboard geral."""
    hoje_iso = dt.date.today().isoformat()
    hoje_br = dt.date.today().strftime("%d/%m/%Y")
    ontem_iso = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    ontem_br = (dt.date.today() - dt.timedelta(days=1)).strftime("%d/%m/%Y")

    sessao_db = repo_estudante.obter_sessao()

    # Estudantes
    alunos = (
        sessao_db.query(Estudante)
        .options(selectinload(Estudante.grupos))
        .all()
    )
    alunos_ativos = sum(1 for a in alunos if getattr(a, "ativo", True) is not False)
    alunos_inativos = len(alunos) - alunos_ativos

    # Grupos / Turmas
    grupos = (
        sessao_db.query(Grupo)
        .options(selectinload(Grupo.estudantes))
        .all()
    )
    grupos_ativos = sum(1 for g in grupos if getattr(g, "ativo", True) is not False)

    # Reservas
    reservas = (
        sessao_db.query(Reserva)
        .options(selectinload(Reserva.estudante).selectinload(Estudante.grupos))
        .all()
    )
    reservas_hoje = [
        r for r in reservas
        if not r.cancelada and (r.data in (hoje_iso, hoje_br))
    ]

    # Consumos com carregamento eager de Sessão e Estudante
    consumos = (
        sessao_db.query(Consumo)
        .options(
            selectinload(Consumo.sessao),
            selectinload(Consumo.reserva),
            selectinload(Consumo.estudante).selectinload(Estudante.grupos),
        )
        .all()
    )

    consumos_hoje = [
        c for c in consumos
        if c.sessao and (c.sessao.data in (hoje_iso, hoje_br))
    ]

    consumos_ontem = [
        c for c in consumos
        if c.sessao and (c.sessao.data in (ontem_iso, ontem_br))
    ]

    # Distribuição de Pratos (a partir de reservas e consumos de hoje)
    dist_pratos: Dict[str, int] = {}
    for r in reservas_hoje:
        prato = r.prato.strip() if r.prato else "Padrão"
        dist_pratos[prato] = dist_pratos.get(prato, 0) + 1

    # Distribuição por Turmas
    mapa_turmas: Dict[str, Dict[str, int]] = {}
    for g in grupos:
        mapa_turmas[g.nome] = {
            "total_alunos": len(g.estudantes),
            "reservas_hoje": 0,
            "consumos_hoje": 0,
        }

    for r in reservas_hoje:
        if r.estudante and r.estudante.grupos:
            for g in r.estudante.grupos:
                if g.nome in mapa_turmas:
                    mapa_turmas[g.nome]["reservas_hoje"] += 1

    for c in consumos_hoje:
        if c.estudante and c.estudante.grupos:
            for g in c.estudante.grupos:
                if g.nome in mapa_turmas:
                    mapa_turmas[g.nome]["consumos_hoje"] += 1

    dist_turmas_lista = [
        {
            "turma": nome_t,
            "total_alunos": dados["total_alunos"],
            "reservas_hoje": dados["reservas_hoje"],
            "consumos_hoje": dados["consumos_hoje"],
        }
        for nome_t, dados in sorted(mapa_turmas.items(), key=lambda x: x[0])
    ]

    return {
        "alunos_total": len(alunos),
        "alunos_ativos": alunos_ativos,
        "alunos_inativos": alunos_inativos,
        "grupos_total": len(grupos),
        "grupos_ativos": grupos_ativos,
        "reservas_hoje": len(reservas_hoje),
        "reservas_total": len([r for r in reservas if not r.cancelada]),
        "consumos_hoje": len(consumos_hoje),
        "consumo_ontem": len(consumos_ontem),
        "consumos_total": len(consumos),
        "distribuicao_pratos": dist_pratos,
        "distribuicao_turmas": dist_turmas_lista,
    }


def obter_estatisticas_sessao(
    repo_sessao: RepositorioSessao,
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    repo_consumo: RepositorioConsumo,
    repo_grupo: RepositorioGrupo,
    id_sessao: int,
    excessao_grupos: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Calcula estatísticas detalhadas e consolidadas para uma sessão de refeição."""
    sessao = obter_detalhes_sessao(repo_sessao, id_sessao)
    consumidos = obter_estudantes_para_sessao(
        repo_sessao=repo_sessao,
        repo_estudante=repo_estudante,
        repo_reserva=repo_reserva,
        repo_consumo=repo_consumo,
        repo_grupo=repo_grupo,
        id_sessao=id_sessao,
        consumido=True,
        pular_grupos=True,
        excessao_grupos=excessao_grupos,
    )
    elegiveis = obter_estudantes_para_sessao(
        repo_sessao=repo_sessao,
        repo_estudante=repo_estudante,
        repo_reserva=repo_reserva,
        repo_consumo=repo_consumo,
        repo_grupo=repo_grupo,
        id_sessao=id_sessao,
        consumido=False,
        excessao_grupos=excessao_grupos,
    )

    total_consumidos = len(consumidos)
    total_restantes = len(elegiveis)
    total_esperado = total_consumidos + total_restantes
    taxa_adesao = (
        round((total_consumidos / total_esperado * 100), 1)
        if total_esperado > 0
        else 0.0
    )

    dist_pratos: Dict[str, int] = {}
    total_com_reserva = 0
    total_sem_reserva = 0
    dist_turmas: Dict[str, int] = {}
    dist_horarios: Dict[str, int] = {}

    consumidos_com_hora = [c for c in consumidos if c.get("hora_consumo")]
    consumidos_com_hora.sort(key=lambda x: str(x.get("hora_consumo", "")))

    for c in consumidos:
        prato = str(c.get("prato") or "Sem Reserva")
        dist_pratos[prato] = dist_pratos.get(prato, 0) + 1
        if prato == "Sem Reserva" or c.get("status") == "Sem Reserva":
            total_sem_reserva += 1
        else:
            total_com_reserva += 1

        turma = str(c.get("turma") or "N/A")
        for t in [item.strip() for item in turma.split(",") if item.strip()]:
            dist_turmas[t] = dist_turmas.get(t, 0) + 1

        hora = str(c.get("hora_consumo", ""))
        if hora and len(hora) >= 5:
            try:
                partes = hora.split(":")
                h = int(partes[0])
                m = int(partes[1])
                bloco_m = (m // 15) * 15
                bloco_fim_m = bloco_m + 15
                bloco_fim_h = h
                if bloco_fim_m >= 60:
                    bloco_fim_m = 0
                    bloco_fim_h = (h + 1) % 24
                chave_intervalo = (
                    f"{h:02d}:{bloco_m:02d} - {bloco_fim_h:02d}:{bloco_fim_m:02d}"
                )
                dist_horarios[chave_intervalo] = (
                    dist_horarios.get(chave_intervalo, 0) + 1
                )
            except Exception:
                chave_hora = f"{hora[:2]}:00"
                dist_horarios[chave_hora] = dist_horarios.get(chave_hora, 0) + 1

    horario_pico = None
    if dist_horarios:
        horario_pico = max(dist_horarios.items(), key=lambda x: x[1])

    primeiro_consumo = consumidos_com_hora[0] if consumidos_com_hora else None
    ultimo_consumo = consumidos_com_hora[-1] if consumidos_com_hora else None

    velocidade = 0.0
    if len(consumidos_com_hora) >= 2 and primeiro_consumo and ultimo_consumo:
        try:
            h_ini_str = str(primeiro_consumo.get("hora_consumo", ""))[:8]
            h_fim_str = str(ultimo_consumo.get("hora_consumo", ""))[:8]
            fmt = "%H:%M:%S" if len(h_ini_str) == 8 else "%H:%M"
            h_ini = dt.datetime.strptime(h_ini_str, fmt)
            h_fim = dt.datetime.strptime(h_fim_str, fmt)
            minutos = (h_fim - h_ini).total_seconds() / 60.0
            if minutos >= 1.0:
                velocidade = round(total_consumidos / minutos, 1)
        except Exception:
            velocidade = 0.0

    return {
        "id_sessao": id_sessao,
        "refeicao": sessao.refeicao,
        "data": sessao.data,
        "hora_prevista": sessao.hora,
        "item_servido": sessao.item_servido,
        "total_consumidos": total_consumidos,
        "total_restantes": total_restantes,
        "total_esperado": total_esperado,
        "taxa_adesao": taxa_adesao,
        "total_com_reserva": total_com_reserva,
        "total_sem_reserva": total_sem_reserva,
        "distribuicao_pratos": dist_pratos,
        "distribuicao_turmas": dict(
            sorted(dist_turmas.items(), key=lambda x: x[1], reverse=True)
        ),
        "distribuicao_horarios": dict(sorted(dist_horarios.items())),
        "horario_pico": horario_pico,
        "primeiro_consumo": primeiro_consumo,
        "ultimo_consumo": ultimo_consumo,
        "velocidade_por_minuto": velocidade,
    }
