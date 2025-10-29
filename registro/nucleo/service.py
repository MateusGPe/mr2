"""
Classe de serviço principal que encapsula toda a lógica de negócio
da aplicação de registro de refeições. Esta camada é agnóstica à
interface de usuário.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional

import xlsxwriter
from sqlalchemy.orm import Session

from registro.nucleo import crud, importers, models
from registro.nucleo.exceptions import (DataImportError, GoogleAPIError,
                                        NoActiveSessionError, RegistrationCoreError, SessionError)
from registro.nucleo.google_api import SpreadSheet
from registro.nucleo.utils import SESSION as SessionData
from registro.nucleo.utils import get_documents_path, save_csv


class RegistroService:
    """Coordena a lógica de negócio, acesso a dados e serviços externos."""

    def __init__(self, db_session: Session):
        """Inicializa o serviço com uma sessão de banco de dados."""
        self._db = db_session
        self.student_crud = crud.CRUD(self._db, models.Students)
        self.reserve_crud = crud.CRUD(self._db, models.Reserve)
        self.session_crud = crud.CRUD(self._db, models.Session)

        self.active_session_id: Optional[int] = None

    def start_new_session(self, session_data: SessionData) -> Optional[int]:
        """Inicia uma nova sessão de refeição e a define como ativa."""
        refeicao = session_data["refeição"].lower()
        data = session_data["data"]
        is_snacks = refeicao == "lanche"

        reserves = self.reserve_crud.read_filtered(data=data, snacks=is_snacks)
        if not reserves:
            if is_snacks:
                importers.reserve_snacks_for_all(
                    self._db, data, session_data['lanche']
                )
            else:
                raise SessionError(
                    f"Não há reservas de almoço para a data {data}. "
                    "Realize a importação primeiro."
                )

        new_session_db = models.Session(
            refeicao=refeicao,
            periodo=session_data["período"],
            data=data,
            hora=session_data["hora"],
            turmas=json.dumps(session_data["turmas"]),
        )
        self._db.add(new_session_db)
        self._db.flush()
        new_session_id = new_session_db.id

        reserves_to_update = self.reserve_crud.read_filtered(
            data=data, snacks=is_snacks, session_id=None
        )
        update_mappings = [
            {"id": r.id, "session_id": new_session_id}
            for r in reserves_to_update
        ]
        if update_mappings:
            self.reserve_crud.bulk_update(update_mappings)

        self._db.commit()
        return new_session_id

    def list_all_sessions(self) -> List[Dict]:
        """Retorna uma lista de todas as sessões existentes."""
        sessoes = self.session_crud.read_all()
        return [
            {
                "id": s.id,
                "refeicao": s.refeicao,
                "periodo": s.periodo,
                "data": s.data,
                "hora": s.hora,
                "turmas": s.turmas
            }
            for s in sessoes
        ]

    def set_active_session(self, session_id: int):
        """Verifica se uma sessão com o ID fornecido existe."""
        session = self.session_crud.read_one(session_id)
        if not session:
            raise SessionError(f"Sessão com ID {session_id} não encontrada.")

    def get_active_session_details(self, session_id: int) -> models.Session:
        """Retorna o objeto da sessão ativa."""
        session = self.session_crud.read_one(session_id)
        if not session:
            raise SessionError(
                f"Sessão ativa (ID {session_id}) não encontrada."
            )
        return session

    def get_students_for_session(self, session_id: int,
                                 consumed: Optional[bool] = None) -> List[Dict]:
        """
        Retorna uma lista de estudantes para a sessão ativa, com filtros.
        - consumed=True: Apenas os que já se serviram.
        - consumed=False: Apenas os que ainda não se serviram.
        - consumed=None: Todos.
        """
        session = self.get_active_session_details(session_id)
        turmas_sel = set(json.loads(session.turmas))
        show_sem_reserva = "SEM RESERVA" in turmas_sel
        turmas_filtro = turmas_sel - {"SEM RESERVA"}

        query = (
            self._db.query(models.Students, models.Reserve)
            .join(models.Reserve)
            .filter(
                models.Reserve.session_id == session_id,
                models.Students.ativo
            )
        )

        if not show_sem_reserva:
            query = query.filter(models.Reserve.prato != 'Sem Reserva')
        if turmas_filtro and 'Todas' not in turmas_filtro:
            query = query.filter(models.Students.turma.in_(turmas_filtro))
        if consumed is not None:
            query = query.filter(models.Reserve.consumed == consumed)

        results = query.all()
        return [
            {
                "pront": s.pront, "nome": s.nome, "turma": s.turma,
                "prato": r.prato, "data": r.data, "id": s.translated_id,
                "reserve_id": r.id, "consumed": r.consumed,
                "registro_time": r.registro_time or ""
            } for s, r in results
        ]

    def register_consumption(self, reserve_id: int) -> bool:
        """Registra o consumo de uma refeição para uma reserva."""
        updated = self.reserve_crud.update(reserve_id, {
            "consumed": True,
            "registro_time": datetime.now().strftime("%H:%M:%S")
        })
        if updated:
            self._db.commit()
            return True
        return False

    def undo_consumption(self, reserve_id: int):
        """Desfaz o registro de consumo de uma refeição."""
        updated = self.reserve_crud.update(
            reserve_id, {"consumed": False, "registro_time": None}
        )
        if updated:
            self._db.commit()

    def update_session_classes(self, session_id: int, classes: List[str]):
        """Atualiza as turmas da sessão ativa."""
        session = self.get_active_session_details(session_id)
        self.session_crud.update(session.id, {"turmas": json.dumps(classes)})
        self._db.commit()

    def export_session_to_xlsx(self, session_id: int) -> str:
        """Exporta os dados da sessão ativa para um arquivo XLSX."""
        session = self.get_active_session_details(session_id)
        served = self.get_students_for_session(session_id, consumed=True)

        name = (f"{session.refeicao.capitalize()} "
                f"{session.data.replace('/', '-')} "
                f"{session.hora.replace(':', '.')}")
        filepath = os.path.join(get_documents_path(), name + '.xlsx')

        workbook = xlsxwriter.Workbook(filepath)
        worksheet = workbook.add_worksheet(name)

        header = ["Matrícula", "Data", "Nome", "Turma", "Refeição", "Hora"]
        worksheet.write_row(0, 0, header)

        for i, item in enumerate(served):
            row_data = [
                item['pront'], session.data, item['nome'],
                item['turma'], item['prato'], item['registro_time']
            ]
            worksheet.write_row(i + 1, 0, row_data)

        workbook.close()
        return filepath

    def sync_from_google_sheets(self):
        """
        Sincroniza estudantes e reservas a partir do Google Sheets,
        baixando os dados e importando-os para o banco de dados local.
        """
        try:
            os.makedirs(os.path.abspath('./config'), exist_ok=True)
            spreadsheet = SpreadSheet()

            discentes = spreadsheet.fetch_sheet_values("Discentes")
            if discentes:
                path = "./config/students.csv"
                if save_csv(discentes, path):
                    importers.import_students_csv(self._db, path)

            reservas = spreadsheet.fetch_sheet_values("DB")
            if reservas:
                path = "./config/reserves.csv"
                if save_csv(reservas, path):
                    importers.import_reserves_csv(self._db, path)

            self._db.commit()
        except (GoogleAPIError, DataImportError) as e:
            self._db.rollback()
            raise e  # Re-lança a exceção para a camada da UI tratar
        except Exception as e:
            self._db.rollback()
            raise RegistrationCoreError(f"Erro inesperado na sincronização: {e}") from e

    def sync_to_google_sheets(self, session_id: int):
        """
        Sincroniza os registros de consumo da sessão ativa para a
        planilha do Google Sheets.
        """
        try:
            session = self.get_active_session_details(session_id)
            served_meals = self.get_students_for_session(session_id, consumed=True)

            rows_to_add = [
                [
                    item['pront'], session.data, item['nome'],
                    item['turma'], item['prato'], item['registro_time']
                ] for item in served_meals
            ]

            if rows_to_add:
                spreadsheet = SpreadSheet()
                spreadsheet.append_unique_rows(
                    rows_to_add, session.refeicao.capitalize()
                )
        except (GoogleAPIError, NoActiveSessionError) as e:
            raise e
        except Exception as e:
            raise RegistrationCoreError(f"Erro inesperado no upload: {e}") from e
