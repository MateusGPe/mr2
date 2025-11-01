"""
Módulo de serviço funcional que encapsula toda a lógica de negócio
da aplicação de registro de refeições.
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

import xlsxwriter
from sqlalchemy.orm import Session as DBSession

from registro.nucleo import google_api_service, importers_service, models
from registro.nucleo.exceptions import (DataImportError, GoogleAPIError,
                                        RegistrationCoreError, SessionError)
from registro.nucleo.repository import (ReserveRepository, SessionRepository,
                                        StudentRepository)
from registro.nucleo.utils import SESSION as SessionData
from registro.nucleo.utils import get_documents_path, save_csv


def start_new_session(
    db_session: DBSession,
    session_repo: SessionRepository,
    reserve_repo: ReserveRepository,
    student_repo: StudentRepository,
    session_data: SessionData,
) -> int:
    """Inicia uma nova sessão de refeição."""
    refeicao = session_data["refeição"].lower()
    data = session_data["data"]
    is_snacks = refeicao == "lanche"

    reserves = reserve_repo.read_filtered(data=data, snacks=is_snacks)
    if not reserves:
        if is_snacks:
            importers_service.reserve_snacks_for_all(student_repo, reserve_repo, data, session_data['lanche'])
        else:
            raise SessionError(f"Não há reservas de almoço para a data {data}. Realize a importação primeiro.")

    turmas_config_payload = {
        "com_reserva": session_data["turmas_com_reserva"],
        "sem_reserva": session_data["turmas_sem_reserva"],
    }

    session_payload = {
        "refeicao": refeicao,
        "periodo": session_data["período"],
        "data": data,
        "hora": session_data["hora"],
        "turmas_config": json.dumps(turmas_config_payload),
    }
    new_session_db = session_repo.create(session_payload)
    new_session_id = new_session_db.id

    reserves_to_update = reserve_repo.read_filtered(data=data, snacks=is_snacks, session_id=None)
    update_mappings = [{"id": r.id, "session_id": new_session_id} for r in reserves_to_update]
    if update_mappings:
        reserve_repo.bulk_update(update_mappings)

    db_session.commit()
    return new_session_id


def list_all_sessions(session_repo: SessionRepository) -> List[Dict]:
    """Retorna uma lista de todas as sessões existentes."""
    sessoes = session_repo.read_all()
    sessions_list = []
    for s in sessoes:
        turmas_config = json.loads(s.turmas_config)
        sessions_list.append({
            "id": s.id, "refeicao": s.refeicao, "periodo": s.periodo,
            "data": s.data, "hora": s.hora,
            "turmas_com_reserva": turmas_config.get("com_reserva", []),
            "turmas_sem_reserva": turmas_config.get("sem_reserva", [])
        })
    return sessions_list


def get_session_details(session_repo: SessionRepository, session_id: int) -> models.Session:
    """Retorna o objeto de uma sessão específica."""
    session = session_repo.read_one(session_id)
    if not session:
        raise SessionError(f"Sessão com ID {session_id} não encontrada.")
    return session


def get_students_for_session(
    reserve_repo: ReserveRepository,
    session_repo: SessionRepository,
    session_id: int,
    consumed: Optional[bool] = None,
) -> List[Dict]:
    """
    Busca estudantes para a sessão, delegando a busca ao repositório com
    os vetores de turmas já definidos na sessão.
    """
    session = get_session_details(session_repo, session_id)
    turmas_config = json.loads(session.turmas_config)

    turmas_com_reserva = set(turmas_config.get("com_reserva", []))
    turmas_sem_reserva = set(turmas_config.get("sem_reserva", []))

    student_details = reserve_repo.get_students_for_session_details(
        session_id=session_id,
        turmas_com_reserva=turmas_com_reserva,
        turmas_sem_reserva=turmas_sem_reserva,
        consumed=consumed,
    )

    for student in student_details:
        if student.get("prato") is None:
            student["prato"] = "Sem Reserva"

    return student_details


def register_consumption(db_session: DBSession, reserve_repo: ReserveRepository, reserve_id: int) -> bool:
    """Registra o consumo de uma refeição para uma reserva."""
    now_str = datetime.now().strftime("%H:%M:%S")
    payload = {"consumed": True, "registro_time": now_str}

    if reserve_repo.update(reserve_id, payload):
        db_session.commit()
        return True
    return False


def undo_consumption(db_session: DBSession, reserve_repo: ReserveRepository, reserve_id: int):
    """Desfaz o registro de consumo de uma refeição."""
    payload = {"consumed": False, "registro_time": None}
    if reserve_repo.update(reserve_id, payload):
        db_session.commit()


def update_session_turmas_config(db_session: DBSession, session_repo: SessionRepository, session_id: int, turmas_com_reserva: List[str], turmas_sem_reserva: List[str]):
    """Atualiza a configuração de turmas para uma sessão existente."""
    get_session_details(session_repo, session_id)  # Validação

    turmas_config_payload = {
        "com_reserva": turmas_com_reserva,
        "sem_reserva": turmas_sem_reserva,
    }

    session_repo.update(session_id, {"turmas_config": json.dumps(turmas_config_payload)})
    db_session.commit()


def export_session_to_xlsx(
    reserve_repo: ReserveRepository,
    session_repo: SessionRepository,
    session_id: int,
) -> str:
    """Exporta os dados da sessão para um arquivo XLSX."""
    session = get_session_details(session_repo, session_id)
    served = get_students_for_session(reserve_repo, session_repo, session_id, consumed=True)

    name = f"{session.refeicao.capitalize()} {session.data.replace('/', '-')} {session.hora.replace(':', '.')}"
    filepath = os.path.join(get_documents_path(), name + '.xlsx')

    with xlsxwriter.Workbook(filepath) as workbook:
        worksheet = workbook.add_worksheet(name)
        header = ["Matrícula", "Data", "Nome", "Turma", "Refeição", "Hora"]
        worksheet.write_row(0, 0, header)
        for i, item in enumerate(served):
            row_data = [item['pront'], session.data, item['nome'], item['turma'], item['prato'], item['registro_time']]
            worksheet.write_row(i + 1, 0, row_data)

    return filepath


def sync_from_google_sheets(
    db_session: DBSession,
    student_repo: StudentRepository,
    reserve_repo: ReserveRepository,
):
    """Sincroniza estudantes e reservas a partir do Google Sheets."""
    try:
        os.makedirs(os.path.abspath('./config'), exist_ok=True)
        spreadsheet = google_api_service.get_spreadsheet()

        discentes = google_api_service.fetch_sheet_values(spreadsheet, "Discentes")
        if discentes:
            path = "./config/students.csv"
            if save_csv(discentes, path):
                importers_service.import_students_csv(student_repo, path)

        reservas = google_api_service.fetch_sheet_values(spreadsheet, "DB")
        if reservas:
            path = "./config/reserves.csv"
            if save_csv(reservas, path):
                importers_service.import_reserves_csv(student_repo, reserve_repo, path)
        db_session.commit()
    except (GoogleAPIError, DataImportError) as e:
        db_session.rollback()
        raise e
    except Exception as e:
        db_session.rollback()
        raise RegistrationCoreError(f"Erro inesperado na sincronização: {e}") from e


def sync_to_google_sheets(
    reserve_repo: ReserveRepository,
    session_repo: SessionRepository,
    session_id: int,
):
    """Sincroniza os registros de consumo da sessão para o Google Sheets."""
    try:
        session = get_session_details(session_repo, session_id)
        served_meals = get_students_for_session(reserve_repo, session_repo, session_id, consumed=True)

        rows_to_add = [
            [item['pront'], session.data, item['nome'], item['turma'], item['prato'], item['registro_time']]
            for item in served_meals
        ]

        if rows_to_add:
            spreadsheet = google_api_service.get_spreadsheet()
            google_api_service.append_unique_rows(spreadsheet, rows_to_add, session.refeicao.capitalize())
    except (GoogleAPIError, SessionError) as e:
        raise e
    except Exception as e:
        raise RegistrationCoreError(f"Erro inesperado no upload: {e}") from e
