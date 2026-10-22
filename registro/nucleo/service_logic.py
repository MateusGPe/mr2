# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/service_logic.py (Módulo de Serviços)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Módulo de serviço funcional que encapsula toda a lógica de negócio
da aplicação de registro de refeições.
"""

import csv
import datetime as dt
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Union

logger = logging.getLogger(__name__)

from fuzzywuzzy import fuzz
import xlsxwriter
from sqlalchemy import select, union
from sqlalchemy.orm import selectinload

REGEX_LIMPEZA_PRONTUARIO: re.Pattern[str] = re.compile(r"^[Ii][Qq]30+")

from registro.nucleo import google_api_service, importers_service, models
from registro.nucleo.exceptions import (
    ErroAPIGoogle,
    ErroImportacaoDados,
    ErroNucleoRegistro,
    ErroSessao,
)
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
    obter_caminho_documentos,
    para_codigo,
    salvar_csv,
)


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

    if refeicao == "almoço":
        reservas = repo_reserva.ler_filtrado(
            data=data_formatada, cancelada=False)
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

    repo_sessao.obter_sessao().commit()
    return nova_sessao_db.id


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
    """Retorna uma lista de todos os grupos existentes."""
    grupos = repo_grupo.ler_todos()
    return [{"id": g.id, "nome": g.nome} for g in grupos]


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
    excessao_grupos: Optional[Set[str]] = None,
    pular_grupos: bool = False,
) -> List[Dict[str, Any]]:
    """
    Busca estudantes elegíveis para a sessão.
    """
    sessao = obter_detalhes_sessao(repo_sessao, id_sessao)
    db_session = repo_estudante.obter_sessao()
    EstudanteGrupo = models.associacao_estudante_grupo

    ids_grupos_sessao = {g.id for g in sessao.grupos}
    ids_excecao_grupos = {
        g.id for g in repo_grupo.por_nomes(excessao_grupos or set())}

    q1 = select(EstudanteGrupo.c.estudante_id).where(
        EstudanteGrupo.c.grupo_id.in_(ids_grupos_sessao)
    )

    q2 = select(EstudanteGrupo.c.estudante_id).where(
        EstudanteGrupo.c.grupo_id.in_(ids_excecao_grupos)
    )

    q3 = select(Reserva.estudante_id).where(
        Reserva.data == sessao.data, Reserva.cancelada.is_(False)
    )

    query_ids_elegiveis = union(q1, q2, q3).subquery()

    if consumido is True:

        consumos_na_sessao = (
            select(Consumo.estudante_id)
            .where(Consumo.sessao_id == id_sessao)
            .subquery()
        )
        stmt = select(Estudante.id).join(
            consumos_na_sessao, Estudante.id == consumos_na_sessao.c.estudante_id
        )
    else:

        stmt = (
            select(Estudante.id)
            .join(
                query_ids_elegiveis, Estudante.id == query_ids_elegiveis.c.estudante_id
            )
            .where(Estudante.ativo.is_(True))
        )

    ids_para_buscar = set(db_session.execute(stmt).scalars().all())

    if not ids_para_buscar:
        return []

    opcoes_carregamento = [selectinload(Estudante.grupos)]
    estudantes = repo_estudante.ler_filtrado(
        opcoes_carregamento=opcoes_carregamento, id=Estudante.id.in_(
            ids_para_buscar)
    )

    mapa_consumos_por_estudante = {
        c.estudante_id: c for c in repo_consumo.ler_filtrado(sessao_id=id_sessao)
    }
    mapa_reservas_dia = {
        r.estudante_id: r
        for r in repo_reserva.ler_filtrado(data=sessao.data, cancelada=False)
    }

    detalhes_estudantes = []
    for est in estudantes:
        autorizado = False
        motivo = "Acesso Negado"
        prato = "Sem Reserva"

        ids_grupos_estudante = {g.id for g in est.grupos}

        if sessao.refeicao == "almoço":
            reserva = mapa_reservas_dia.get(est.id)
            if reserva and (
                ids_grupos_sessao.intersection(
                    ids_grupos_estudante) or pular_grupos
            ):
                autorizado = True
                motivo = "Reserva"
                prato = reserva.prato
            elif ids_excecao_grupos.intersection(ids_grupos_estudante) or pular_grupos:
                autorizado = True
                motivo = "Exceção (Grupo)"
        elif ids_grupos_sessao.intersection(ids_grupos_estudante):
            autorizado = True
            motivo = "Autorizado (Grupo)"
            prato = sessao.item_servido or "Lanche"

        if not autorizado:
            continue

        info_consumo = mapa_consumos_por_estudante.get(est.id)

        if consumido is True and not info_consumo:
            continue
        if consumido is False and info_consumo:
            continue

        grupos = ", ".join(sorted(g.nome for g in est.grupos)
                           ) if est.grupos else "N/A"

        detalhes_estudantes.append(
            {
                "pront": est.prontuario,
                "nome": est.nome,
                "turma": grupos,
                "prato": prato,
                "consumido": bool(info_consumo),
                "id_consumo": info_consumo.id if info_consumo else None,
                "hora_consumo": info_consumo.hora_consumo if info_consumo else "",
                "status": motivo,
                **para_codigo(est.prontuario),
            }
        )

    return detalhes_estudantes


def deletar_sessao(repo_sessao: RepositorioSessao, id_sessao: int):
    """Deleta uma sessão e seus consumos associados (via cascade do DB)."""
    if not repo_sessao.deletar(id_sessao):
        raise ErroSessao(
            f"Sessão com ID {id_sessao} não encontrada para exclusão.")
    repo_sessao.obter_sessao().commit()


def atualizar_sessao(
    repo_sessao: RepositorioSessao, id_sessao: int, dados: Dict[str, Any]
):
    """Atualiza os dados de uma sessão existente."""
    dados.pop("grupos", None)
    sessao_atualizada = repo_sessao.atualizar(id_sessao, dados)
    if not sessao_atualizada:
        raise ErroSessao(
            f"Sessão com ID {id_sessao} não encontrada para atualização.")
    repo_sessao.obter_sessao().commit()
    return sessao_atualizada


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
    """Aplica a lógica de autorização e, se bem-sucedido, registra o consumo."""
    sessao = obter_detalhes_sessao(repo_sessao, id_sessao)
    estudantes = repo_estudante.ler_filtrado(prontuario=prontuario)
    if not estudantes:
        return {"autorizado": False, "motivo": "Estudante não encontrado."}
    estudante = estudantes[0]
    turma = ", ".join(sorted(g.nome for g in estudante.grupos)
                      ) if estudante.grupos else "N/A"

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

    id_reserva = None
    autorizado = False
    motivo = "Acesso Negado"
    prato = "Sem Reserva"

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
    Aplica uma lógica de autorização estrita e, se bem-sucedido, registra o consumo.
    O consumo só é autorizado se o estudante tiver uma reserva válida para a sessão
    e pertencer a um grupo autorizado (grupo da sessão, grupo de exceção ou se a
    verificação de grupos for pulada).
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

    id_reserva = None
    autorizado = False
    motivo = "Acesso Negado"
    prato = "Sem Reserva"

    # Regra 1: Deve ter uma reserva válida (típico para almoço).
    reservas = []
    if sessao.refeicao == "almoço":
        reservas = repo_reserva.ler_filtrado(
            estudante_id=estudante.id, data=sessao.data, cancelada=False
        )

    if not reservas:
        motivo = "Sem reserva válida."
    else:
        # Se tem reserva, continua a verificação de grupo.
        id_reserva = reservas[0].id
        prato = reservas[0].prato or "Padrão"

        # Regra 2: Deve pertencer a um grupo autorizado para a sessão.
        nomes_grupos_estudante = {g.nome for g in estudante.grupos}
        nomes_grupos_sessao = {g.nome for g in sessao.grupos}

        grupo_autorizado = False
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
            autorizado = True
        else:
            # Se não está em nenhum grupo autorizado, nega o acesso.
            autorizado = False
            motivo = "Com reserva, mas sem permissão de grupo."

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


def desfazer_consumo(repo_consumo: RepositorioConsumo, id_consumo: int):
    """Remove um registro de consumo do banco de dados."""
    if repo_consumo.deletar(id_consumo):
        repo_consumo.obter_sessao().commit()


def desfazer_consumo_por_prontuario(
    repo_consumo: RepositorioConsumo, prontuario: str, id_sessao: int
) -> bool:
    """Remove um registro de consumo do banco de dados."""
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


def atualizar_cancelamento_reserva(
    repo_reserva: RepositorioReserva, id_reserva: int, cancelar: bool = True
):
    """Marca ou desmarca uma reserva como cancelada."""
    atualizado = repo_reserva.atualizar(id_reserva, {"cancelada": cancelar})
    if not atualizado:
        raise ErroNucleoRegistro(
            f"Reserva com ID {id_reserva} não encontrada.")
    repo_reserva.obter_sessao().commit()


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
    repo_sessao.obter_sessao().commit()


def _escrever_consumos_em_planilha(
    workbook: xlsxwriter.Workbook,
    worksheet_name: str,
    consumos: Sequence[Consumo],
    incluir_sessao_id: bool,
):
    """
    Função auxiliar para escrever uma lista de consumos em uma planilha XLSX.

    Args:
        workbook: O objeto do workbook xlsxwriter.
        worksheet_name: O nome para a nova planilha.
        consumos: A lista de objetos de Consumo a serem escritos.
        incluir_sessao_id: Se True, adiciona uma coluna com o ID da sessão.
    """
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

        turma = consumo.estudante.grupos[0].nome if consumo.estudante.grupos else "N/A"

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
        db_session.query(Consumo).options(
            *opcoes).order_by(Consumo.id.desc()).all()
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
    """Exporta os dados de consumo da sessão para um arquivo XLSX."""
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
            planilha, "Discentes")
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
            f"Erro inesperado na sincronização: {e}") from e


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
            consumo.estudante.grupos[0].nome if consumo.estudante.grupos else "N/A"
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


def criar_estudante(
    repo_estudante: RepositorioEstudante,
    repo_grupo: RepositorioGrupo,
    prontuario: str,
    nome: str,
    grupos: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Cria um novo estudante e associa aos grupos fornecidos."""
    existente = repo_estudante.ler_filtrado(prontuario=prontuario)
    if existente:
        raise ValueError(f"Estudante com prontuário {prontuario} já existe.")

    novo_estudante = repo_estudante.criar({"prontuario": prontuario, "nome": nome})

    if grupos:
        for grupo_nome in grupos:
            grupo = repo_grupo.por_nome(grupo_nome)
            if not grupo:
                grupo = repo_grupo.criar({"nome": grupo_nome})
            novo_estudante.grupos.append(grupo)
    repo_estudante.obter_sessao().commit()
    return {
        "id": novo_estudante.id,
        "prontuario": novo_estudante.prontuario,
        "nome": novo_estudante.nome,
    }


def atualizar_estudante(
    repo_estudante: RepositorioEstudante,
    id_estudante: int,
    dados: Dict[str, Any],
) -> bool:
    """Atualiza os dados de um estudante."""
    estudante = repo_estudante.atualizar(id_estudante, dados)
    if estudante:
        repo_estudante.obter_sessao().commit()
        return True
    return False


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
) -> List[Dict[str, Any]]:
    """Lista estudantes com filtro textual opcional por nome ou prontuário."""
    sessao = repo_estudante.obter_sessao()
    query = sessao.query(Estudante).options(selectinload(Estudante.grupos))
    if termo_busca:
        termo_like = f"%{termo_busca}%"
        query = query.filter(
            (Estudante.nome.ilike(termo_like))
            | (Estudante.prontuario.ilike(termo_like))
        )
    estudantes = query.order_by(Estudante.nome).all()
    return [
        {
            "id": est.id,
            "prontuario": est.prontuario,
            "nome": est.nome,
            "ativo": est.ativo,
            "grupos": [g.nome for g in est.grupos],
        }
        for est in estudantes
    ]


def listar_estudantes_fuzzy(
    repo_estudante: RepositorioEstudante,
    termo_busca: Optional[str] = None,
    limite: int = 60,
) -> List[Dict[str, Any]]:
    """Lista estudantes ordenados por relevância fuzzy."""
    if not termo_busca or not termo_busca.strip():
        todos_estudantes = repo_estudante.ler_todos_com_grupos()
        estudantes = sorted(todos_estudantes, key=lambda e: e.nome)
    else:
        termo_lower = termo_busca.lower().strip()
        pront_lower = REGEX_LIMPEZA_PRONTUARIO.sub("", termo_lower)
        candidatos = repo_estudante.ler_todos_com_grupos()
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

    return [
        {
            "id": est.id,
            "prontuario": est.prontuario,
            "nome": est.nome,
            "ativo": est.ativo,
            "grupos": [g.nome for g in est.grupos],
        }
        for est in estudantes
    ]


def criar_reserva(
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    prontuario_estudante: str,
    dados_reserva: Dict[str, Any],
) -> Dict[str, Any]:
    """Cria uma reserva para o estudante especificado."""
    estudantes = repo_estudante.ler_filtrado(prontuario=prontuario_estudante)
    if not estudantes:
        raise ValueError(
            f"Estudante com prontuário {prontuario_estudante} não encontrado."
        )

    payload = dados_reserva.copy()
    payload["estudante_id"] = estudantes[0].id

    nova_reserva = repo_reserva.criar(payload)
    repo_reserva.obter_sessao().commit()

    return {
        "id": nova_reserva.id,
        "estudante_id": nova_reserva.estudante_id,
        "prato": nova_reserva.prato,
        "data": nova_reserva.data,
        "cancelada": nova_reserva.cancelada,
    }


def atualizar_reserva(
    repo_reserva: RepositorioReserva,
    id_reserva: int,
    dados: Dict[str, Any],
) -> bool:
    """Atualiza os dados de uma reserva."""
    reserva = repo_reserva.atualizar(id_reserva, dados)
    if reserva:
        repo_reserva.obter_sessao().commit()
        return True
    return False


def deletar_reserva(
    repo_reserva: RepositorioReserva,
    id_reserva: int,
) -> bool:
    """Remove uma reserva do sistema."""
    if repo_reserva.deletar(id_reserva):
        repo_reserva.obter_sessao().commit()
        return True
    return False


def listar_datas_reservas(repo_reserva: RepositorioReserva) -> List[str]:
    """Retorna uma lista única e cronologicamente ordenada de datas de reservas existentes."""
    from registro.nucleo.importar.patterns_find import obter_data

    def _chave_data(texto: str) -> int:
        obj = obter_data(texto)
        return int(obj.timestamp()) if obj else 0

    datas = {s.data for s in repo_reserva.ler_unicos() if s.data}
    return sorted(datas, reverse=True, key=_chave_data)


def listar_reservas(
    repo_grupo: RepositorioGrupo,
    repo_reserva: RepositorioReserva,
    filtros: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Lista reservas com base nos filtros fornecidos."""
    filtros = filtros or {}
    if "grupos" in filtros or "grupo" in filtros:
        grupos = set(filtros.get("grupos", [])) or set(
            filtros.get("grupo", ""),
        )
        grupos_ids = [g.id for g in repo_grupo.por_nomes(grupos)]
        reservas = repo_reserva.por_data_e_grupos(
            grupos_ids=grupos_ids, data_formatada=filtros.get("data")
        )
    else:
        reservas = repo_reserva.ler_filtrado(**filtros)

    return [
        {
            "id": res.id,
            "prontuario_estudante": res.estudante.prontuario,
            "nome_estudante": res.estudante.nome,
            "prato": res.prato,
            "data": res.data,
            "cancelada": res.cancelada,
        }
        for res in reservas
    ]


def salvar_importacao_dados(
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    dados: List[Dict[str, Any]],
) -> Dict[str, int]:
    """Persiste dados importados de estudantes e reservas de forma atômica."""
    novos_estudantes = []
    reservas_para_criar = []

    for linha in dados:
        id_banco = linha.get("_id_banco")
        pront = linha.get("prontuario")

        if not (data := linha.get("data")):
            continue

        if not id_banco and pront:
            novos_estudantes.append(
                {
                    "prontuario": pront,
                    "nome": linha.get("nome", "Desconhecido"),
                    "ativo": True,
                }
            )

        reservas_para_criar.append(
            {
                "payload": {
                    "prato": linha.get("prato"),
                    "data": data,
                    "cancelada": False,
                },
                "chave": id_banco if id_banco else pront,
            }
        )

    if novos_estudantes:
        unicos = {e["prontuario"]: e for e in novos_estudantes}.values()
        repo_estudante.criar_em_massa(list(unicos))

    mapa_ids = {}
    if novos_estudantes:
        pronts = {e["prontuario"] for e in novos_estudantes}
        objs = repo_estudante.por_prontuarios(pronts)
        mapa_ids = {e.prontuario: e.id for e in objs}

    reservas_finais = []
    for item in reservas_para_criar:
        chave = item["chave"]
        id_final = None

        if isinstance(chave, int):
            id_final = chave
        elif isinstance(chave, str):
            id_final = mapa_ids.get(chave)

        if id_final:
            payload = item["payload"]
            payload["estudante_id"] = id_final
            reservas_finais.append(payload)

    if reservas_finais:
        repo_reserva.criar_em_massa(reservas_finais)

    repo_estudante.obter_sessao().commit()

    return {
        "estudantes_criados": len(novos_estudantes),
        "reservas_criadas": len(reservas_finais),
    }


def carregar_estado_sessao(fachada: Any) -> Optional[Dict[str, Any]]:
    """Carrega o arquivo session.json e define a sessão ativa na fachada se existir."""
    from registro.nucleo.constants import CAMINHO_SESSAO

    if not CAMINHO_SESSAO.exists():
        logger.info("Arquivo de estado da sessão não encontrado: %s", CAMINHO_SESSAO)
        return None
    try:
        with open(CAMINHO_SESSAO, "r", encoding="utf-8") as f:
            dados = json.load(f)
        logger.info("Estado da sessão carregado: %s", CAMINHO_SESSAO)
        if "id_sessao" in dados:
            fachada.definir_sessao_ativa(dados["id_sessao"])
        return dados
    except Exception as e:
        logger.error("Erro ao carregar estado da sessão de %s: %s", CAMINHO_SESSAO, e)
        return None


def salvar_estado_sessao(fachada: Any, id_sessao: Optional[int] = None) -> bool:
    """Salva o estado da sessão ativa no arquivo session.json."""
    from registro.nucleo.constants import CAMINHO_SESSAO

    sid = id_sessao if id_sessao is not None else getattr(fachada, "id_sessao_ativa", None)
    if sid is None:
        return False
    try:
        CAMINHO_SESSAO.parent.mkdir(parents=True, exist_ok=True)
        CAMINHO_SESSAO.write_text(
            json.dumps({"id_sessao": sid}, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Estado da sessão salvo em %s.", CAMINHO_SESSAO)
        return True
    except Exception as e:
        logger.error("Erro ao salvar estado da sessão em %s: %s", CAMINHO_SESSAO, e)
        return False


def limpar_estado_sessao(fachada: Any) -> bool:
    """Remove o arquivo session.json e desativa a sessão."""
    from registro.nucleo.constants import CAMINHO_SESSAO

    try:
        CAMINHO_SESSAO.unlink(missing_ok=True)
        fachada.id_sessao_ativa = None
        logger.info("Estado da sessão limpo: %s", CAMINHO_SESSAO)
        return True
    except Exception as e:
        logger.error("Erro ao limpar estado da sessão: %s", e)
        return False


def exportar_estudantes_para_csv(
    repo_estudante: RepositorioEstudante, caminho_arquivo: Union[str, Path]
) -> str:
    """Exporta todos os estudantes cadastrados para um arquivo CSV."""
    caminho = Path(caminho_arquivo)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    estudantes = repo_estudante.ler_todos()
    dados = []
    for est in estudantes:
        dados.append(
            {
                "id": est.id,
                "prontuario": est.prontuario,
                "nome": est.nome,
                "grupos": ", ".join(g.nome for g in est.grupos) if est.grupos else "",
                "ativo": "Sim" if getattr(est, "ativo", True) else "Não",
            }
        )
    keys = list(dados[0].keys()) if dados else ["id", "prontuario", "nome", "grupos", "ativo"]
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(dados)
    return str(caminho)


def exportar_reservas_para_csv(
    repo_grupo: RepositorioGrupo,
    repo_reserva: RepositorioReserva,
    caminho_arquivo: Union[str, Path],
) -> str:
    """Exporta todas as reservas cadastradas para um arquivo CSV."""
    caminho = Path(caminho_arquivo)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    reservas = listar_reservas(repo_grupo, repo_reserva)
    dados = []
    for r in reservas:
        dados.append(
            {
                "id": r.get("id"),
                "data": r.get("data"),
                "prontuario": r.get("prontuario_estudante"),
                "nome": r.get("nome_estudante"),
                "prato": r.get("prato"),
                "cancelada": "Sim" if r.get("cancelada") else "Não",
            }
        )
    keys = list(dados[0].keys()) if dados else ["id", "data", "prontuario", "nome", "prato", "cancelada"]
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(dados)
    return str(caminho)


def obter_estatisticas_dashboard(
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    repo_grupo: RepositorioGrupo,
    repo_consumo: RepositorioConsumo,
) -> Dict[str, Any]:
    """Calcula estatísticas consolidadas para o dashboard."""
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


