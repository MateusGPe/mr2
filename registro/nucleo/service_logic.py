"""
Módulo de serviço funcional que encapsula toda a lógica de negócio
da aplicação de registro de refeições.
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import xlsxwriter

from registro.nucleo import google_api_service, importers_service, models
from registro.nucleo.exceptions import (
    DataImportError,
    GoogleAPIError,
    RegistrationCoreError,
    SessionError,
)
from registro.nucleo.repository import (
    ConsumoRepository,
    EstudanteRepository,
    GrupoRepository,
    ReservaRepository,
    SessaoRepository,
)
from registro.nucleo.utils import SESSION as SessionData
from registro.nucleo.utils import get_documents_path, save_csv, to_code


def start_new_session(
    sessao_repo: SessaoRepository,
    grupo_repo: GrupoRepository,
    session_data: SessionData,
) -> int:
    """Inicia uma nova sessão de refeição e a associa aos grupos selecionados."""
    refeicao = session_data["refeicao"].lower()

    session_payload = {
        "refeicao": refeicao,
        "periodo": session_data["periodo"],
        "data": session_data["data"],
        "hora": session_data["hora"],
        "item_servido": session_data.get("item_servido"),
    }

    # Cria a sessão
    new_session_db = sessao_repo.create(session_payload)

    # Associa os grupos à sessão
    if session_data["grupos"]:
        grupos_db = grupo_repo.por_nomes(set(session_data["grupos"]))
        new_session_db.grupos.extend(grupos_db)

    sessao_repo.get_session().commit()
    return new_session_db.id


def list_all_sessions(sessao_repo: SessaoRepository) -> List[Dict]:
    """Retorna uma lista de todas as sessões existentes."""
    sessoes = sessao_repo.read_all()
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


def get_session_details(
    sessao_repo: SessaoRepository, session_id: int
) -> models.Sessao:
    """Retorna o objeto de uma sessão específica."""
    session = sessao_repo.read_one(session_id)
    if not session:
        raise SessionError(f"Sessão com ID {session_id} não encontrada.")
    return session


def get_students_for_session(
    session_repo: SessaoRepository,
    estudante_repo: EstudanteRepository,
    reserva_repo: ReservaRepository,
    consumo_repo: ConsumoRepository,
    session_id: int,
    consumed: Optional[bool] = None,
) -> List[Dict]:
    """Busca estudantes elegíveis para a sessão, com base nas regras de negócio."""
    session = get_session_details(session_repo, session_id)
    session_group_ids = {g.id for g in session.grupos}

    # 1. Obter todos os consumos já registrados para esta sessão
    consumos_sessao = consumo_repo.read_filtered(sessao_id=session_id)
    consumed_student_ids = {c.estudante_id: c for c in consumos_sessao}

    # 2. Filtrar por status de consumo, se solicitado
    if consumed is True:
        student_ids_to_fetch = set(consumed_student_ids.keys())
        estudantes = estudante_repo.por_id(student_ids_to_fetch)
    # elif consumed is False:
        # Se for para buscar não consumidos, a lógica é mais complexa,
        # por ora, vamos buscar todos os elegíveis e filtrar no final.
    #     estudantes = estudante_repo.read_filtered(ativo=True)
    else:  # None
        estudantes = estudante_repo.read_filtered(ativo=True)

    # 3. Construir a lista final de estudantes elegíveis
    student_details = []

    # Busca todas as reservas para a data da sessão de uma vez
    reservas_dia = {
        r.estudante_id: r
        for r in reserva_repo.read_filtered(data=session.data, cancelada=False)
    }

    for est in estudantes:
        autorizado = False
        motivo = "Acesso Negado"
        prato = "Sem Reserva"
        # reserva_id = None

        if session.refeicao == "almoço":
            reserva = reservas_dia.get(est.id)
            if reserva:  # Regra 1: Almoço com reserva
                autorizado = True
                motivo = "Reserva"
                prato = reserva.prato
                # reserva_id = reserva.id
            else:  # Regra 2: Almoço por exceção de grupo
                est_group_ids = {g.id for g in est.grupos}
                if session_group_ids.intersection(est_group_ids):
                    autorizado = True
                    motivo = "Exceção (Grupo)"
        else:  # Lanche
            est_group_ids = {g.id for g in est.grupos}
            if session_group_ids.intersection(est_group_ids):
                autorizado = True
                motivo = "Autorizado (Grupo)"
                prato = session.item_servido or "Lanche"

        if not autorizado:
            continue

        consumo_info = consumed_student_ids.get(est.id)

        # Aplicar filtro de consumo
        if consumed is True and not consumo_info:
            continue
        if consumed is False and consumo_info:
            continue

        student_details.append(
            {
                "pront": est.prontuario,
                "nome": est.nome,
                "turma": est.grupos[0].nome if est.grupos else "N/A",
                "prato": prato,
                "consumed": bool(consumo_info),
                "consumo_id": consumo_info.id if consumo_info else None,
                "registro_time": consumo_info.hora_consumo if consumo_info else "",
                "status": motivo,
                **to_code(est.prontuario),
            }
        )

    return sorted(student_details, key=lambda x: x["nome"])


def delete_session(sessao_repo: SessaoRepository, session_id: int):
    """Deleta uma sessão e seus consumos associados."""
    if not sessao_repo.delete(session_id):
        raise SessionError(f"Sessão com ID {session_id} não encontrada para exclusão.")
    sessao_repo.get_session().commit()


def update_session(sessao_repo: SessaoRepository, session_id: int, data: Dict[str, Any]):
    """Atualiza os dados de uma sessão existente."""
    # Remove 'grupos' do dicionário, pois eles são tratados separadamente.
    if 'grupos' in data:
        del data['grupos']

    updated_session = sessao_repo.update(session_id, data)
    if not updated_session:
        raise SessionError(f"Sessão com ID {session_id} não encontrada para atualização.")

    sessao_repo.get_session().commit()
    return updated_session


def register_consumption(
    session_repo: SessaoRepository,
    estudante_repo: EstudanteRepository,
    reserva_repo: ReservaRepository,
    consumo_repo: ConsumoRepository,
    session_id: int,
    prontuario: str,
) -> Dict[str, Any]:
    """Aplica a lógica de autorização e, se bem-sucedido, registra o consumo."""
    session = get_session_details(session_repo, session_id)
    estudante = estudante_repo.read_filtered(prontuario=prontuario)
    if not estudante:
        return {"autorizado": False, "motivo": "Estudante não encontrado."}
    estudante = estudante[0]

    # Verificar se já consumiu
    existing_consumo = consumo_repo.read_filtered(
        estudante_id=estudante.id, sessao_id=session_id
    )
    if existing_consumo:
        return {"autorizado": False, "motivo": "Consumo já registrado."}

    # Lógica de autorização
    reserva_id = None
    autorizado = False
    motivo = "Acesso Negado"

    if session.refeicao == "almoço":
        reserva = reserva_repo.read_filtered(
            estudante_id=estudante.id, data=session.data, cancelada=False
        )
        if reserva:
            autorizado = True
            reserva_id = reserva[0].id
            motivo = "Autorizado com reserva."
        else:
            session_group_ids = {g.id for g in session.grupos}
            est_group_ids = {g.id for g in estudante.grupos}
            if session_group_ids.intersection(est_group_ids):
                autorizado = True
                motivo = "Autorizado por exceção (grupo)."
    else:  # Lanche
        session_group_ids = {g.id for g in session.grupos}
        est_group_ids = {g.id for g in estudante.grupos}
        if session_group_ids.intersection(est_group_ids):
            autorizado = True
            motivo = "Autorizado para lanche (grupo)."

    if autorizado:
        payload = {
            "estudante_id": estudante.id,
            "sessao_id": session.id,
            "hora_consumo": datetime.now().strftime("%H:%M:%S"),
            "reserva_id": reserva_id,
        }
        consumo_repo.create(payload)
        consumo_repo.get_session().commit()

    return {"autorizado": autorizado, "motivo": motivo, "aluno": estudante.nome}


def undo_consumption(consumo_repo: ConsumoRepository, consumo_id: int):
    """Desfaz o registro de consumo de uma refeição deletando o registro."""
    if consumo_repo.delete(consumo_id):
        consumo_repo.get_session().commit()


def update_cancel_reserve(reserva_repo: ReservaRepository, reserva_id: int, cancel: bool = True):
    """Marca uma reserva como cancelada."""
    updated = reserva_repo.update(reserva_id, {"cancelada": cancel})
    if not updated:
        raise RegistrationCoreError(f"Reserva com ID {reserva_id} não encontrada.")
    reserva_repo.get_session().commit()


def update_session_groups(
    sessao_repo: SessaoRepository,
    grupo_repo: GrupoRepository,
    session_id: int,
    nomes_grupos: List[str],
):
    """Atualiza a lista de grupos autorizados para uma sessão."""
    session = get_session_details(sessao_repo, session_id)
    grupos_db = grupo_repo.por_nomes(set(nomes_grupos))
    session.grupos = grupos_db
    sessao_repo.get_session().commit()


def export_session_to_xlsx(
    sessao_repo: SessaoRepository, consumo_repo: ConsumoRepository, session_id: int
) -> str:
    """Exporta os dados de consumo da sessão para um arquivo XLSX."""
    session = get_session_details(sessao_repo, session_id)
    consumos = consumo_repo.read_filtered(sessao_id=session_id)

    name = ".".join(
        (
            session.refeicao.capitalize(),
            session.data.replace("/", "-"),
            session.hora.replace(":", "."),
            "xlsx",
        )
    )
    filepath = os.path.join(get_documents_path(), name)

    with xlsxwriter.Workbook(filepath) as workbook:
        worksheet = workbook.add_worksheet(name)
        header = ["Matrícula", "Data", "Nome", "Turma", "Refeição", "Hora"]
        worksheet.write_row(0, 0, header)
        for i, consumo in enumerate(consumos):
            prato = "Sem Reserva (Exceção)"
            if consumo.reserva_id and consumo.reserva:
                prato = consumo.reserva.prato
            elif session.refeicao == "lanche":
                prato = session.item_servido or "Lanche"

            turma = (
                consumo.estudante.grupos[0].nome if consumo.estudante.grupos else "N/A"
            )

            row_data = [
                consumo.estudante.prontuario,
                session.data,
                consumo.estudante.nome,
                turma,
                prato,
                consumo.hora_consumo,
            ]
            worksheet.write_row(i + 1, 0, row_data)
    return filepath


def sync_from_google_sheets(
    estudante_repo: EstudanteRepository,
    reserva_repo: ReservaRepository,
    grupo_repo: GrupoRepository,
):
    """Sincroniza estudantes e reservas a partir do Google Sheets."""
    try:
        os.makedirs(os.path.abspath("./config"), exist_ok=True)
        spreadsheet = google_api_service.get_spreadsheet()

        discentes = google_api_service.fetch_sheet_values(spreadsheet, "Discentes")
        if discentes:
            path = "./config/students.csv"
            if save_csv(discentes, path):
                importers_service.import_students_csv(estudante_repo, grupo_repo, path)

        reservas = google_api_service.fetch_sheet_values(spreadsheet, "DB")
        if reservas:
            path = "./config/reserves.csv"
            if save_csv(reservas, path):
                importers_service.import_reserves_csv(
                    estudante_repo, reserva_repo, path
                )

    except (GoogleAPIError, DataImportError) as e:
        estudante_repo.get_session().rollback()
        raise e
    except Exception as e:
        estudante_repo.get_session().rollback()
        raise RegistrationCoreError(f"Erro inesperado na sincronização: {e}") from e


def sync_to_google_sheets(
    sessao_repo: SessaoRepository,
    consumo_repo: ConsumoRepository,
    session_id: int,
):
    """Sincroniza os registros de consumo da sessão para o Google Sheets."""
    try:
        session = get_session_details(sessao_repo, session_id)
        consumos = consumo_repo.read_filtered(sessao_id=session_id)

        rows_to_add = []
        for consumo in consumos:
            prato = "Sem Reserva (Exceção)"
            if consumo.reserva_id and consumo.reserva:
                prato = consumo.reserva.prato
            elif session.refeicao == "lanche":
                prato = session.item_servido or "Lanche"

            turma = (
                consumo.estudante.grupos[0].nome if consumo.estudante.grupos else "N/A"
            )

            rows_to_add.append(
                [
                    consumo.estudante.prontuario,
                    session.data,
                    consumo.estudante.nome,
                    turma,
                    prato,
                    consumo.hora_consumo,
                ]
            )

        if rows_to_add:
            spreadsheet = google_api_service.get_spreadsheet()
            google_api_service.append_unique_rows(
                spreadsheet, rows_to_add, session.refeicao.capitalize()
            )  # Idealmente uma aba genérica
    except (GoogleAPIError, SessionError) as e:
        raise e
    except Exception as e:
        raise RegistrationCoreError(f"Erro inesperado no upload: {e}") from e
