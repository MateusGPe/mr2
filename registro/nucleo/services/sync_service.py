# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/services/sync_service.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Serviço de sincronização de dados com planilhas Google Sheets.
"""

import json
from datetime import datetime
import logging
from pathlib import Path
from typing import List, Optional, Sequence

from sqlalchemy.orm import selectinload

from registro.nucleo import google_api_service, importers_service
from registro.nucleo.constants import (
    DIRETORIO_CONFIG,
    NOME_ABA_CANCELADOS,
    NOME_ABA_CONFIGURACAO,
    NOME_ABA_LANCHES,
)
from registro.nucleo.services import grade_horarios_service
from registro.nucleo.exceptions import (
    ErroAPIGoogle,
    ErroImportacaoDados,
    ErroNucleoRegistro,
    ErroSessao,
)
from registro.nucleo.models import Consumo, Estudante, Sessao
from registro.nucleo.repository import (
    RepositorioConsumo,
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
    RepositorioSessao,
)
from registro.nucleo.services.sessao_service import obter_detalhes_sessao
from registro.nucleo.utils import salvar_csv

logger = logging.getLogger(__name__)


def sincronizar_do_google_sheets(
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    repo_grupo: RepositorioGrupo,
    caminho_config: Optional[Path] = None,
):
    """Sincroniza estudantes e reservas a partir de uma planilha do Google Sheets."""
    try:
        caminho_config = Path(caminho_config) if caminho_config else DIRETORIO_CONFIG
        caminho_config.mkdir(parents=True, exist_ok=True)
        planilha = google_api_service.obter_planilha()

        discentes = google_api_service.buscar_valores_aba(
            planilha, "Discentes"
        )
        if discentes:
            caminho_csv = caminho_config / "students.csv"
            if salvar_csv(discentes, caminho_csv):
                importers_service.importar_estudantes_csv(
                    repo_estudante, repo_grupo, caminho_csv
                )

        reservas = google_api_service.buscar_valores_aba(planilha, "DB")
        if reservas:
            caminho_csv = caminho_config / "reserves.csv"
            if salvar_csv(reservas, caminho_csv):
                importers_service.importar_reservas_csv(
                    repo_estudante, repo_reserva, caminho_csv
                )

        # Sincronização da aba Configuração (Grade de Horários e Categorias)
        try:
            linhas_config = google_api_service.buscar_valores_aba(
                planilha, NOME_ABA_CONFIGURACAO
            )
            if linhas_config:
                grade_estruturada = (
                    grade_horarios_service.converter_linhas_configuracao_para_grade(
                        linhas_config
                    )
                )
                tem_slots = any(
                    any(slots for slots in dia.values())
                    for dia in grade_estruturada.values()
                )
                if tem_slots:
                    grade_horarios_service.salvar_grade_horarios(
                        grade_estruturada, caminho_config / "grade_horarios.json"
                    )
                    logger.info("Grade horária sincronizada da aba Configuração.")
        except Exception as e:
            logger.warning("Aba '%s' não sincronizada: %s", NOME_ABA_CONFIGURACAO, e)

        # Sincronização bidirecional da aba Lanches
        try:
            linhas_lanches = google_api_service.buscar_valores_aba(
                planilha, NOME_ABA_LANCHES
            )
            caminho_lanches = caminho_config / "lanches.json"
            lanches_locais = set()
            if caminho_lanches.exists():
                try:
                    with open(caminho_lanches, "r", encoding="utf-8") as f:
                        dados = json.load(f)
                        if isinstance(dados, list):
                            lanches_locais = {
                                str(item).strip() for item in dados if str(item).strip()
                            }
                except Exception:
                    pass

            novos_lanches_remotos = set()
            if linhas_lanches:
                for row in linhas_lanches:
                    if not row:
                        continue
                    item = str(row[0]).strip()
                    if not item or item.lower() in ("lanche", "item", "cardápio", "cardapio"):
                        continue
                    novos_lanches_remotos.add(item)

            if novos_lanches_remotos or lanches_locais:
                lanches_unificados = sorted(list(lanches_locais | novos_lanches_remotos))
                with open(caminho_lanches, "w", encoding="utf-8") as f:
                    json.dump(lanches_unificados, f, indent=2, ensure_ascii=False)
                logger.info("Lista de opções de lanches sincronizada (%d itens).", len(lanches_unificados))

                # Bidirecional: envia itens locais que ainda não existiam na planilha
                lanches_para_enviar = [
                    [l] for l in lanches_locais if l not in novos_lanches_remotos
                ]
                if lanches_para_enviar:
                    google_api_service.anexar_linhas_unicas(
                        planilha, lanches_para_enviar, NOME_ABA_LANCHES
                    )
        except Exception as e:
            logger.warning("Aba '%s' não sincronizada: %s", NOME_ABA_LANCHES, e)

    except (ErroAPIGoogle, ErroImportacaoDados) as e:
        repo_estudante.obter_sessao().rollback()
        raise e
    except Exception as e:
        repo_estudante.obter_sessao().rollback()
        raise ErroNucleoRegistro(
            f"Erro inesperado na sincronização: {e}"
        ) from e


def _montar_linhas_para_sessao(
    sessao: Sessao,
    consumos: Sequence[Consumo],
) -> List[List[str]]:
    """Constrói as linhas que serão enviadas para a planilha de uma sessão."""
    linhas_para_adicionar = []
    for consumo in consumos:
        prato = "Sem Reserva (Exceção)"
        if consumo.reserva:
            prato = consumo.reserva.prato
        elif sessao.refeicao == "lanche":
            prato = sessao.item_servido or "Lanche"

        turma = (
            consumo.estudante.grupos[0].nome
            if consumo.estudante.grupos
            else "N/A"
        )
        categoria = getattr(consumo.estudante, "categoria", "REGULAR")

        linhas_para_adicionar.append(
            [
                consumo.estudante.prontuario,
                sessao.data,
                consumo.estudante.nome,
                turma,
                prato,
                consumo.hora_consumo,
                categoria,
            ]
        )
    return linhas_para_adicionar


def _montar_linhas_canceladas(
    sessao: Sessao,
    consumos_cancelados: Sequence[Consumo],
) -> List[List[str]]:
    """Constrói as linhas de auditoria para registros cancelados (soft delete)."""
    linhas = []
    for c in consumos_cancelados:
        turma = c.estudante.grupos[0].nome if c.estudante.grupos else "N/A"
        hora_canc = (
            c.deletado_em.strftime("%H:%M:%S")
            if isinstance(c.deletado_em, datetime)
            else str(c.deletado_em or "")
        )
        linhas.append(
            [
                sessao.data,
                c.hora_consumo,
                hora_canc,
                c.estudante.prontuario,
                c.estudante.nome,
                turma,
                getattr(c.estudante, "categoria", "REGULAR"),
                sessao.refeicao.capitalize(),
                c.deletado_por or "Operador",
                c.motivo_cancelamento or "Cancelado",
            ]
        )
    return linhas


def sincronizar_para_google_sheets(
    repo_sessao: RepositorioSessao,
    repo_consumo: RepositorioConsumo,
    id_sessao: int,
):
    """Envia os registros de consumo ativos e cancelados de uma sessão para o Google Sheets."""
    try:
        sessao = obter_detalhes_sessao(repo_sessao, id_sessao)
        opcoes = [
            selectinload(Consumo.reserva),
            selectinload(Consumo.estudante).selectinload(Estudante.grupos),
        ]
        # Consumos ativos (RepositorioConsumo filtra ativo=True por padrão)
        consumos_ativos = repo_consumo.ler_filtrado(
            opcoes_carregamento=opcoes, sessao_id=id_sessao
        )
        linhas_ativos = _montar_linhas_para_sessao(sessao, consumos_ativos)

        # Consumos cancelados (auditoria)
        try:
            consumos_cancelados = repo_consumo.ler_filtrado(
                opcoes_carregamento=opcoes, sessao_id=id_sessao, ativo=False
            )
        except TypeError:
            consumos_cancelados = []
        linhas_canceladas = _montar_linhas_canceladas(sessao, consumos_cancelados)

        planilha = google_api_service.obter_planilha()
        if linhas_ativos:
            google_api_service.anexar_linhas_unicas(
                planilha, linhas_ativos, sessao.refeicao.capitalize()
            )
        if linhas_canceladas:
            google_api_service.anexar_linhas_unicas(
                planilha, linhas_canceladas, NOME_ABA_CANCELADOS
            )
    except (ErroAPIGoogle, ErroSessao) as e:
        raise e
    except Exception as e:
        raise ErroNucleoRegistro(
            f"Erro inesperado no upload para a planilha: {e}"
        ) from e


def sincronizar_todas_sessoes_para_google_sheets(
    repo_sessao: RepositorioSessao,
    repo_consumo: RepositorioConsumo,
):
    """Envia os registros de consumo de todas as sessões para a planilha do Google Sheets."""
    try:
        opcoes = [
            selectinload(Consumo.reserva),
            selectinload(Consumo.estudante).selectinload(Estudante.grupos),
        ]
        todas_sessoes = repo_sessao.ler_todos()
        planilha = google_api_service.obter_planilha()

        for sessao in todas_sessoes:
            consumos_ativos = repo_consumo.ler_filtrado(
                opcoes_carregamento=opcoes,
                sessao_id=sessao.id,
            )
            linhas_ativos = _montar_linhas_para_sessao(sessao, consumos_ativos)
            if linhas_ativos:
                google_api_service.anexar_linhas_unicas(
                    planilha,
                    linhas_ativos,
                    sessao.refeicao.capitalize(),
                )

            try:
                consumos_cancelados = repo_consumo.ler_filtrado(
                    opcoes_carregamento=opcoes,
                    sessao_id=sessao.id,
                    ativo=False,
                )
            except TypeError:
                consumos_cancelados = []
            linhas_canceladas = _montar_linhas_canceladas(sessao, consumos_cancelados)
            if linhas_canceladas:
                google_api_service.anexar_linhas_unicas(
                    planilha,
                    linhas_canceladas,
                    NOME_ABA_CANCELADOS,
                )
    except (ErroAPIGoogle, ErroSessao) as e:
        raise e
    except Exception as e:
        raise ErroNucleoRegistro(
            f"Erro inesperado no upload de todas as sessões: {e}"
        ) from e


def sincronizar_novo_lanche_para_planilha(item_lanche: str):
    """Envia um novo item de lanche para a aba Lanches da planilha se disponível."""
    if not item_lanche or not item_lanche.strip():
        return
    try:
        planilha = google_api_service.obter_planilha()
        google_api_service.anexar_linhas_unicas(
            planilha, [[item_lanche.strip()]], NOME_ABA_LANCHES
        )
    except Exception as e:
        logger.warning("Não foi possível enviar novo lanche para a planilha: %s", e)
