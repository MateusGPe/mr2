# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/services/sync_service.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Serviço de sincronização de dados com planilhas Google Sheets.
"""

import logging
from pathlib import Path
from typing import List, Sequence

from sqlalchemy.orm import selectinload

from registro.nucleo import google_api_service, importers_service
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
):
    """Sincroniza estudantes e reservas a partir de uma planilha do Google Sheets."""
    try:
        caminho_config = Path("./config")
        caminho_config.mkdir(exist_ok=True)
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

        linhas_para_adicionar.append(
            [
                consumo.estudante.prontuario,
                sessao.data,
                consumo.estudante.nome,
                turma,
                prato,
                consumo.hora_consumo,
            ]
        )
    return linhas_para_adicionar


def sincronizar_para_google_sheets(
    repo_sessao: RepositorioSessao,
    repo_consumo: RepositorioConsumo,
    id_sessao: int,
):
    """Envia os registros de consumo de uma sessão para a planilha do Google Sheets."""
    try:
        sessao = obter_detalhes_sessao(repo_sessao, id_sessao)
        opcoes = [
            selectinload(Consumo.reserva),
            selectinload(Consumo.estudante).selectinload(Estudante.grupos),
        ]
        consumos = repo_consumo.ler_filtrado(
            opcoes_carregamento=opcoes, sessao_id=id_sessao
        )

        linhas_para_adicionar = _montar_linhas_para_sessao(sessao, consumos)
        if linhas_para_adicionar:
            planilha = google_api_service.obter_planilha()
            google_api_service.anexar_linhas_unicas(
                planilha, linhas_para_adicionar, sessao.refeicao.capitalize()
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

        for sessao in todas_sessoes:
            consumos = repo_consumo.ler_filtrado(
                opcoes_carregamento=opcoes,
                sessao_id=sessao.id,
            )
            linhas_para_adicionar = _montar_linhas_para_sessao(sessao, consumos)
            if linhas_para_adicionar:
                planilha = google_api_service.obter_planilha()
                google_api_service.anexar_linhas_unicas(
                    planilha,
                    linhas_para_adicionar,
                    sessao.refeicao.capitalize(),
                )
    except (ErroAPIGoogle, ErroSessao) as e:
        raise e
    except Exception as e:
        raise ErroNucleoRegistro(
            f"Erro inesperado no upload de todas as sessões: {e}"
        ) from e
