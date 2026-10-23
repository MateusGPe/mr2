# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/services/export_service.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Serviço de exportação de dados para planilhas XLSX e arquivos CSV.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import xlsxwriter
from sqlalchemy.orm import selectinload

from registro.nucleo.models import Consumo, Estudante
from registro.nucleo.repository import (
    RepositorioConsumo,
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
    RepositorioSessao,
)
from registro.nucleo.services.reserva_service import listar_reservas
from registro.nucleo.services.sessao_service import obter_detalhes_sessao
from registro.nucleo.utils import obter_caminho_documentos

logger = logging.getLogger(__name__)


def _escrever_consumos_em_planilha(
    workbook: xlsxwriter.Workbook,
    worksheet_name: str,
    consumos: Sequence[Consumo],
    incluir_sessao_id: bool,
):
    """Função auxiliar para escrever uma lista de consumos em uma planilha XLSX."""
    worksheet = workbook.add_worksheet(worksheet_name)
    cabecalho = ["Matrícula", "Data", "Nome", "Turma", "Refeição", "Hora"]
    if incluir_sessao_id:
        cabecalho.append("Sessão ID")

    worksheet.write_row(0, 0, cabecalho)

    for i, consumo in enumerate(consumos):
        sessao_consumo = consumo.sessao
        prato = "Sem Reserva (Exceção)"
        if consumo.reserva:
            prato = consumo.reserva.prato
        elif sessao_consumo and sessao_consumo.refeicao == "lanche":
            prato = sessao_consumo.item_servido or "Lanche"

        turma = (
            consumo.estudante.grupos[0].nome if consumo.estudante.grupos else "N/A"
        )

        dados_linha = [
            consumo.estudante.prontuario,
            sessao_consumo.data if sessao_consumo else "N/A",
            consumo.estudante.nome,
            turma,
            prato,
            consumo.hora_consumo,
        ]
        if incluir_sessao_id:
            dados_linha.append(consumo.sessao_id)

        worksheet.write_row(i + 1, 0, dados_linha)


def exportar_todos_os_consumos_para_xlsx(
    repo_consumo: RepositorioConsumo,
    nome_arquivo_arg: Optional[Path] = None,
) -> str:
    """Exporta todos os dados de consumo do banco de dados para um arquivo XLSX."""
    opcoes = [
        selectinload(Consumo.reserva),
        selectinload(Consumo.sessao),
        selectinload(Consumo.estudante).selectinload(Estudante.grupos),
    ]

    db_session = repo_consumo.obter_sessao()
    consumos = (
        db_session.query(Consumo)
        .options(*opcoes)
        .order_by(Consumo.id.desc())
        .all()
    )

    if not consumos:
        raise ValueError("Nenhum consumo registrado para exportar.")

    if nome_arquivo_arg:
        caminho_arquivo = nome_arquivo_arg
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"exportacao_total_consumos_{timestamp}.xlsx"
        caminho_arquivo = obter_caminho_documentos() / nome_arquivo

    with xlsxwriter.Workbook(str(caminho_arquivo)) as workbook:
        _escrever_consumos_em_planilha(
            workbook=workbook,
            worksheet_name="Todos os Consumos",
            consumos=consumos,
            incluir_sessao_id=True,
        )
    return str(caminho_arquivo)


def exportar_sessao_para_xlsx(
    repo_sessao: RepositorioSessao,
    repo_consumo: RepositorioConsumo,
    id_sessao: int,
    nome_arquivo_arg: Optional[Path] = None,
) -> str:
    """Exporta os dados de consumo de uma sessão específica para um arquivo XLSX."""
    sessao = obter_detalhes_sessao(repo_sessao, id_sessao)
    opcoes = [
        selectinload(Consumo.reserva),
        selectinload(Consumo.sessao),
        selectinload(Consumo.estudante).selectinload(Estudante.grupos),
    ]
    consumos = repo_consumo.ler_filtrado(
        opcoes_carregamento=opcoes, sessao_id=id_sessao
    )

    if nome_arquivo_arg:
        caminho_arquivo = nome_arquivo_arg
        nome_arquivo = Path(caminho_arquivo).stem
    else:
        nome_arquivo = ".".join(
            (
                sessao.refeicao.capitalize(),
                sessao.data.replace("/", "-"),
                sessao.hora.replace(":", "."),
                "xlsx",
            )
        )
        caminho_arquivo = obter_caminho_documentos() / nome_arquivo

    with xlsxwriter.Workbook(str(caminho_arquivo)) as workbook:
        _escrever_consumos_em_planilha(
            workbook=workbook,
            worksheet_name=nome_arquivo[:31],
            consumos=consumos,
            incluir_sessao_id=False,
        )
    return str(caminho_arquivo)


def exportar_estudantes_para_csv(
    repo_estudante: RepositorioEstudante,
    caminho_arquivo: Union[str, Path],
    estudantes_dados: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Exporta estudantes cadastrados para um arquivo CSV."""
    caminho = Path(caminho_arquivo)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    if estudantes_dados is not None:
        dados = estudantes_dados
    else:
        estudantes = repo_estudante.ler_todos()
        dados = [
            {
                "id": est.id,
                "prontuario": est.prontuario,
                "nome": est.nome,
                "grupos": ", ".join(g.nome for g in est.grupos) if est.grupos else "",
                "ativo": "Sim" if getattr(est, "ativo", True) else "Não",
            }
            for est in estudantes
        ]

    keys = (
        list(dados[0].keys())
        if dados
        else ["id", "prontuario", "nome", "grupos", "ativo"]
    )
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(dados)
    return str(caminho)


def exportar_estudantes_para_xlsx(
    repo_estudante: RepositorioEstudante,
    caminho_arquivo: Union[str, Path],
    estudantes_dados: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Exporta estudantes cadastrados para um arquivo Excel (.xlsx)."""
    caminho = Path(caminho_arquivo)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    if estudantes_dados is not None:
        dados = estudantes_dados
    else:
        estudantes = repo_estudante.ler_todos()
        dados = [
            {
                "id": est.id,
                "prontuario": est.prontuario,
                "nome": est.nome,
                "grupos": ", ".join(g.nome for g in est.grupos) if est.grupos else "",
                "ativo": "Sim" if getattr(est, "ativo", True) else "Não",
            }
            for est in estudantes
        ]

    with xlsxwriter.Workbook(str(caminho)) as workbook:
        ws = workbook.add_worksheet("Alunos")
        cabecalho = ["ID", "Prontuário", "Nome", "Turmas", "Ativo"]
        ws.write_row(0, 0, cabecalho)
        for i, row in enumerate(dados):
            ws.write_row(
                i + 1,
                0,
                [
                    row.get("id", ""),
                    row.get("prontuario", ""),
                    row.get("nome", ""),
                    row.get("grupos", ""),
                    row.get("ativo", "Sim"),
                ],
            )
    return str(caminho)


def exportar_reservas_para_csv(
    repo_grupo: RepositorioGrupo,
    repo_reserva: RepositorioReserva,
    caminho_arquivo: Union[str, Path],
    reservas_dados: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Exporta reservas para um arquivo CSV."""
    caminho = Path(caminho_arquivo)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    if reservas_dados is not None:
        dados = reservas_dados
    else:
        reservas = listar_reservas(repo_grupo, repo_reserva)
        dados = [
            {
                "id": r.get("id"),
                "data": r.get("data"),
                "prontuario": r.get("prontuario_estudante"),
                "nome": r.get("nome_estudante"),
                "prato": r.get("prato"),
                "cancelada": "Sim" if r.get("cancelada") else "Não",
            }
            for r in reservas
        ]

    keys = (
        list(dados[0].keys())
        if dados
        else ["id", "data", "prontuario", "nome", "prato", "cancelada"]
    )
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(dados)
    return str(caminho)


def exportar_reservas_para_xlsx(
    repo_grupo: RepositorioGrupo,
    repo_reserva: RepositorioReserva,
    caminho_arquivo: Union[str, Path],
    reservas_dados: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Exporta reservas para um arquivo Excel (.xlsx)."""
    caminho = Path(caminho_arquivo)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    if reservas_dados is not None:
        dados = reservas_dados
    else:
        reservas = listar_reservas(repo_grupo, repo_reserva)
        dados = [
            {
                "id": r.get("id"),
                "data": r.get("data"),
                "prontuario": r.get("prontuario_estudante"),
                "nome": r.get("nome_estudante"),
                "prato": r.get("prato"),
                "cancelada": "Sim" if r.get("cancelada") else "Não",
            }
            for r in reservas
        ]

    with xlsxwriter.Workbook(str(caminho)) as workbook:
        ws = workbook.add_worksheet("Reservas")
        cabecalho = ["ID", "Data", "Prontuário", "Nome Aluno", "Prato", "Cancelada"]
        ws.write_row(0, 0, cabecalho)
        for i, row in enumerate(dados):
            ws.write_row(
                i + 1,
                0,
                [
                    row.get("id", ""),
                    row.get("data", ""),
                    row.get("prontuario", ""),
                    row.get("nome", ""),
                    row.get("prato", ""),
                    row.get("cancelada", "Não"),
                ],
            )
    return str(caminho)


def exportar_turmas_para_csv(
    repo_grupo: RepositorioGrupo,
    caminho_arquivo: Union[str, Path],
    turmas_dados: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Exporta turmas cadastradas para um arquivo CSV."""
    caminho = Path(caminho_arquivo)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    if turmas_dados is not None:
        dados = turmas_dados
    else:
        grupos = repo_grupo.ler_todos()
        dados = [
            {
                "id": g.id,
                "nome": g.nome,
                "ativo": "Sim" if getattr(g, "ativo", True) else "Não",
                "total_alunos": len(g.estudantes) if hasattr(g, "estudantes") else 0,
            }
            for g in grupos
        ]

    keys = (
        list(dados[0].keys())
        if dados
        else ["id", "nome", "ativo", "total_alunos"]
    )
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(dados)
    return str(caminho)


def exportar_turmas_para_xlsx(
    repo_grupo: RepositorioGrupo,
    caminho_arquivo: Union[str, Path],
    turmas_dados: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Exporta turmas cadastradas para um arquivo Excel (.xlsx)."""
    caminho = Path(caminho_arquivo)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    if turmas_dados is not None:
        dados = turmas_dados
    else:
        grupos = repo_grupo.ler_todos()
        dados = [
            {
                "id": g.id,
                "nome": g.nome,
                "ativo": "Sim" if getattr(g, "ativo", True) else "Não",
                "total_alunos": len(g.estudantes) if hasattr(g, "estudantes") else 0,
            }
            for g in grupos
        ]

    with xlsxwriter.Workbook(str(caminho)) as workbook:
        ws = workbook.add_worksheet("Turmas")
        cabecalho = ["ID", "Nome da Turma", "Status Ativo", "Total de Alunos"]
        ws.write_row(0, 0, cabecalho)
        for i, row in enumerate(dados):
            ws.write_row(
                i + 1,
                0,
                [
                    row.get("id", ""),
                    row.get("nome", ""),
                    row.get("ativo", "Sim"),
                    row.get("total_alunos", 0),
                ],
            )
    return str(caminho)
