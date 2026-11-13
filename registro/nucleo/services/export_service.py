# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/services/export_service.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Serviço de exportação de dados para planilhas XLSX e arquivos CSV.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import xlsxwriter
from sqlalchemy.orm import selectinload

from registro.nucleo.constants import TIPO_GRUPO_TURMA
from registro.nucleo.models import Consumo, Estudante, Reserva
from registro.nucleo.repository import (
    RepositorioConsumo,
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
    RepositorioSessao,
)
from registro.nucleo.services.reserva_service import listar_reservas
from registro.nucleo.services.sessao_service import obter_detalhes_sessao
from registro.nucleo.utils import (
    formatar_turma_e_categoria,
    obter_caminho_documentos,
)

logger = logging.getLogger(__name__)

_PREFIXOS_FORMULA_PERIGOSOS = ("=", "+", "-", "@", "\t", "\r")
_OPCOES_XLSX_SEGURO = {"strings_to_formulas": False, "strings_to_urls": False}


def _sanitizar_celula_planilha(valor: Any) -> Any:
    """Previne CSV/Formula Injection (OWASP) escapando células iniciadas por operadores de fórmula."""
    if (
        isinstance(valor, str)
        and valor.startswith(_PREFIXOS_FORMULA_PERIGOSOS)
        and valor != "-"
    ):
        return f"'{valor}"
    return valor


def _sanitizar_linhas_csv(dados: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aplica sanitização contra Formula Injection em dicionários de exportação CSV."""
    return [
        {k: _sanitizar_celula_planilha(v) for k, v in linha.items()} for linha in dados
    ]


def _carregar_mapa_reservas_ativas(
    sessao_db: Any, consumos: Sequence[Consumo]
) -> Dict[Tuple[int, str], Reserva]:
    """Carrega reservas ativas por (estudante_id, data) para enriquecer categorias de consumos sem reserva direta."""
    datas = {
        c.sessao.data
        for c in consumos
        if c.sessao and c.sessao.data and c.reserva is None
    }
    est_ids = {c.estudante_id for c in consumos if c.reserva is None}
    if not datas or not est_ids or sessao_db is None:
        return {}
    reservas = (
        sessao_db.query(Reserva)
        .options(selectinload(Reserva.grupos))
        .filter(
            Reserva.estudante_id.in_(est_ids),
            Reserva.data.in_(datas),
            Reserva.cancelada.is_(False),
        )
        .all()
    )
    return {(r.estudante_id, r.data): r for r in reservas}


def _escrever_consumos_em_planilha(
    workbook: xlsxwriter.Workbook,
    worksheet_name: str,
    consumos: Sequence[Consumo],
    incluir_sessao_id: bool,
    mapa_reservas_dia: Optional[Dict[Tuple[int, str], Reserva]] = None,
):
    """Função auxiliar para escrever uma lista de consumos em uma planilha XLSX."""
    worksheet = workbook.add_worksheet(worksheet_name)
    cabecalho = ["Matrícula", "Data", "Nome", "Turma", "Refeição", "Hora", "Categoria"]
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

        data_sessao = sessao_consumo.data if sessao_consumo else "N/A"
        reserva_ref = consumo.reserva
        if reserva_ref is None and mapa_reservas_dia and sessao_consumo:
            reserva_ref = mapa_reservas_dia.get((consumo.estudante_id, data_sessao))

        turma, categoria = formatar_turma_e_categoria(consumo.estudante, reserva_ref)

        dados_linha = [
            consumo.estudante.prontuario,
            data_sessao,
            consumo.estudante.nome,
            turma,
            prato,
            consumo.hora_consumo,
            categoria,
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
        selectinload(Consumo.reserva).selectinload(Reserva.grupos),
        selectinload(Consumo.sessao),
        selectinload(Consumo.estudante).selectinload(Estudante.grupos),
    ]

    db_session = repo_consumo.obter_sessao()
    consumos = (
        db_session.query(Consumo)
        .options(*opcoes)
        .filter(Consumo.ativo.is_(True))
        .order_by(Consumo.id.desc())
        .all()
    )

    if not consumos:
        raise ValueError("Nenhum consumo registrado para exportar.")

    mapa_reservas = _carregar_mapa_reservas_ativas(db_session, consumos)

    if nome_arquivo_arg:
        caminho_arquivo = nome_arquivo_arg
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"exportacao_total_consumos_{timestamp}.xlsx"
        caminho_arquivo = obter_caminho_documentos() / nome_arquivo

    with xlsxwriter.Workbook(str(caminho_arquivo), _OPCOES_XLSX_SEGURO) as workbook:
        _escrever_consumos_em_planilha(
            workbook=workbook,
            worksheet_name="Todos os Consumos",
            consumos=consumos,
            incluir_sessao_id=True,
            mapa_reservas_dia=mapa_reservas,
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
        selectinload(Consumo.reserva).selectinload(Reserva.grupos),
        selectinload(Consumo.sessao),
        selectinload(Consumo.estudante).selectinload(Estudante.grupos),
    ]
    consumos = repo_consumo.ler_filtrado(
        opcoes_carregamento=opcoes, sessao_id=id_sessao
    )
    mapa_reservas = _carregar_mapa_reservas_ativas(
        repo_consumo.obter_sessao(), consumos
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

    with xlsxwriter.Workbook(str(caminho_arquivo), _OPCOES_XLSX_SEGURO) as workbook:
        _escrever_consumos_em_planilha(
            workbook=workbook,
            worksheet_name=nome_arquivo[:31],
            consumos=consumos,
            incluir_sessao_id=False,
            mapa_reservas_dia=mapa_reservas,
        )

        consumos_cancelados = repo_consumo.ler_filtrado(
            opcoes_carregamento=opcoes, sessao_id=id_sessao, ativo=False
        )
        if consumos_cancelados:
            mapa_res_canc = _carregar_mapa_reservas_ativas(
                repo_consumo.obter_sessao(), consumos_cancelados
            )
            ws_cancelados = workbook.add_worksheet("Cancelados")
            cab_cancelados = [
                "Matrícula",
                "Data",
                "Nome",
                "Turma",
                "Refeição",
                "Hora",
                "Categoria",
                "Cancelado Por",
                "Motivo",
            ]
            ws_cancelados.write_row(0, 0, cab_cancelados)
            for j, c_canc in enumerate(consumos_cancelados):
                res_ref = c_canc.reserva or mapa_res_canc.get(
                    (c_canc.estudante_id, sessao.data)
                )
                turma_canc, cat_canc = formatar_turma_e_categoria(
                    c_canc.estudante, res_ref
                )
                prato_canc = (
                    c_canc.reserva.prato
                    if c_canc.reserva
                    else (sessao.item_servido or "Não especificado")
                )
                ws_cancelados.write_row(
                    j + 1,
                    0,
                    [
                        c_canc.estudante.prontuario,
                        sessao.data,
                        c_canc.estudante.nome,
                        turma_canc,
                        prato_canc,
                        c_canc.hora_consumo,
                        cat_canc,
                        c_canc.deletado_por or "",
                        c_canc.motivo_cancelamento or "",
                    ],
                )
    return str(caminho_arquivo)


def _montar_dados_exportacao_estudantes(
    repo_estudante: RepositorioEstudante,
) -> List[Dict[str, Any]]:
    """Monta linhas padronizadas de estudantes separando turmas e categorias."""
    estudantes = repo_estudante.ler_todos_com_grupos()
    dados = []
    for est in estudantes:
        turma_str, cat_str = formatar_turma_e_categoria(est, turma_vazia="")
        dados.append(
            {
                "id": est.id,
                "prontuario": est.prontuario,
                "nome": est.nome,
                "grupos": turma_str,
                "categoria": cat_str,
                "ativo": "Sim" if getattr(est, "ativo", True) else "Não",
            }
        )
    return dados


def exportar_estudantes_para_csv(
    repo_estudante: RepositorioEstudante,
    caminho_arquivo: Union[str, Path],
    estudantes_dados: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Exporta estudantes cadastrados para um arquivo CSV."""
    caminho = Path(caminho_arquivo)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    dados = (
        estudantes_dados
        if estudantes_dados is not None
        else _montar_dados_exportacao_estudantes(repo_estudante)
    )

    keys = (
        list(dados[0].keys())
        if dados
        else ["id", "prontuario", "nome", "grupos", "categoria", "ativo"]
    )
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(_sanitizar_linhas_csv(dados))
    return str(caminho)


def exportar_estudantes_para_xlsx(
    repo_estudante: RepositorioEstudante,
    caminho_arquivo: Union[str, Path],
    estudantes_dados: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Exporta estudantes cadastrados para um arquivo Excel (.xlsx)."""
    caminho = Path(caminho_arquivo)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    dados = (
        estudantes_dados
        if estudantes_dados is not None
        else _montar_dados_exportacao_estudantes(repo_estudante)
    )

    with xlsxwriter.Workbook(str(caminho), _OPCOES_XLSX_SEGURO) as workbook:
        ws = workbook.add_worksheet("Alunos")
        cabecalho = ["ID", "Prontuário", "Nome", "Turmas", "Categorias", "Ativo"]
        ws.write_row(0, 0, cabecalho)
        for i, row in enumerate(dados):
            turmas_val = row.get("turma") if "turma" in row else row.get("grupos", "")
            if isinstance(turmas_val, list):
                turmas_val = ", ".join(turmas_val)
            ws.write_row(
                i + 1,
                0,
                [
                    row.get("id", ""),
                    _sanitizar_celula_planilha(row.get("prontuario", "")),
                    _sanitizar_celula_planilha(row.get("nome", "")),
                    _sanitizar_celula_planilha(turmas_val),
                    _sanitizar_celula_planilha(row.get("categoria", "-")),
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
                "turnos": r.get("turnos_str", "Almoço"),
                "prato": r.get("prato"),
                "categorias": r.get("categorias_str", "-"),
                "cancelada": "Sim" if r.get("cancelada") else "Não",
            }
            for r in reservas
        ]

    keys = (
        list(dados[0].keys())
        if dados
        else [
            "id",
            "data",
            "prontuario",
            "nome",
            "turnos",
            "prato",
            "categorias",
            "cancelada",
        ]
    )
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(_sanitizar_linhas_csv(dados))
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
                "turnos": r.get("turnos_str", "Almoço"),
                "prato": r.get("prato"),
                "categorias": r.get("categorias_str", "-"),
                "cancelada": "Sim" if r.get("cancelada") else "Não",
            }
            for r in reservas
        ]

    with xlsxwriter.Workbook(str(caminho), _OPCOES_XLSX_SEGURO) as workbook:
        ws = workbook.add_worksheet("Reservas")
        cabecalho = [
            "ID",
            "Data",
            "Prontuário",
            "Nome Aluno",
            "Turnos",
            "Prato",
            "Categorias",
            "Cancelada",
        ]
        ws.write_row(0, 0, cabecalho)
        for i, row in enumerate(dados):
            ws.write_row(
                i + 1,
                0,
                [
                    row.get("id", ""),
                    _sanitizar_celula_planilha(row.get("data", "")),
                    _sanitizar_celula_planilha(row.get("prontuario", "")),
                    _sanitizar_celula_planilha(row.get("nome", "")),
                    _sanitizar_celula_planilha(
                        row.get("turnos", row.get("turnos_str", "Almoço"))
                    ),
                    _sanitizar_celula_planilha(row.get("prato", "")),
                    _sanitizar_celula_planilha(
                        row.get("categorias", row.get("categorias_str", "-"))
                    ),
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
                "tipo": "Categoria" if getattr(g, "eh_categoria", False) else "Turma",
                "ativo": "Sim" if getattr(g, "ativo", True) else "Não",
                "total_alunos": len(g.estudantes) if hasattr(g, "estudantes") else 0,
            }
            for g in grupos
        ]

    keys = (
        list(dados[0].keys())
        if dados
        else ["id", "nome", "tipo", "ativo", "total_alunos"]
    )
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(_sanitizar_linhas_csv(dados))
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
                "tipo": "Categoria" if getattr(g, "eh_categoria", False) else "Turma",
                "ativo": "Sim" if getattr(g, "ativo", True) else "Não",
                "total_alunos": len(g.estudantes) if hasattr(g, "estudantes") else 0,
            }
            for g in grupos
        ]

    with xlsxwriter.Workbook(str(caminho), _OPCOES_XLSX_SEGURO) as workbook:
        ws = workbook.add_worksheet("Turmas")
        cabecalho = ["ID", "Nome", "Tipo", "Status Ativo", "Total de Alunos"]
        ws.write_row(0, 0, cabecalho)
        for i, row in enumerate(dados):
            tipo_val = row.get("tipo", TIPO_GRUPO_TURMA)
            tipo_label = (
                "Categoria" if str(tipo_val).lower() == "categoria" else "Turma"
            )
            ws.write_row(
                i + 1,
                0,
                [
                    row.get("id", ""),
                    _sanitizar_celula_planilha(row.get("nome", "")),
                    tipo_label,
                    row.get("ativo", "Sim"),
                    row.get("total_alunos", 0),
                ],
            )
    return str(caminho)
