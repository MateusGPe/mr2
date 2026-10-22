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
    """Calcula estatísticas consolidadas para o dashboard geral."""
    hoje_iso = dt.date.today().isoformat()
    hoje_br = dt.date.today().strftime("%d/%m/%Y")
    ontem_iso = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    ontem_br = (dt.date.today() - dt.timedelta(days=1)).strftime("%d/%m/%Y")

    alunos = repo_estudante.ler_todos()
    grupos = repo_grupo.ler_todos()

    reservas_hoje = [
        r
        for r in repo_reserva.ler_todos()
        if not r.cancelada and (r.data == hoje_iso or r.data == hoje_br)
    ]

    consumos_ontem = [
        c
        for c in repo_consumo.ler_todos()
        if c.data == ontem_iso or c.data == ontem_br
    ]

    return {
        "alunos_ativos": len(alunos),
        "reservas_hoje": len(reservas_hoje),
        "consumo_ontem": len(consumos_ontem),
        "grupos_total": len(grupos),
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
