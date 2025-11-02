"""
Funções para importar dados de estudantes e reservas, encapsulando a
lógica de processamento e inserção no banco de dados.
"""

import csv
from typing import Dict

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from registro.nucleo.exceptions import DataImportError
from registro.nucleo.repository import (
    EstudanteRepository,
    GrupoRepository,
    ReservaRepository,
)
from registro.nucleo.utils import adjust_keys


def _get_or_create_groups(db_session: Session, group_names: set) -> Dict[str, int]:
    """Busca ou cria grupos e retorna um mapeamento de nome para ID."""
    grupo_repo = GrupoRepository(db_session)
    existing_grupos = grupo_repo.por_nomes(group_names)
    existing_map = {g.nome: g.id for g in existing_grupos}

    new_group_names = group_names - set(existing_map.keys())
    if new_group_names:
        new_rows = [{"nome": name} for name in new_group_names]
        grupo_repo.bulk_create(new_rows)
        # Re-fetch all to get new IDs
        all_grupos = grupo_repo.por_nomes(group_names)
        return {g.nome: g.id for g in all_grupos}
    return existing_map


def import_students_csv(
    estudante_repo: EstudanteRepository, grupo_repo: GrupoRepository, csv_file_path: str
) -> int:
    """Importa e atualiza estudantes e suas associações com grupos de um arquivo CSV."""
    try:
        students_to_create = []
        students_to_update = []
        student_group_relations = []
        all_group_names = set()

        # Lê todos os estudantes existentes e mapeia por prontuário
        existing_students_map = {s.prontuario: s for s in estudante_repo.read_all()}

        with open(csv_file_path, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                row = adjust_keys(row)
                pront = row.get("pront")
                if not pront:
                    continue

                student_data = {"prontuario": pront, "nome": row.get("nome", "")}

                if pront in existing_students_map:
                    # Se o estudante existe, verifica se o nome mudou
                    if existing_students_map[pront].nome != student_data["nome"]:
                        # Adiciona o ID para a atualização em massa
                        update_payload = student_data.copy()
                        update_payload["id"] = existing_students_map[pront].id
                        students_to_update.append(update_payload)
                else:
                    # Se não existe, adiciona à lista de criação
                    students_to_create.append(student_data)

                # Lógica de grupos permanece a mesma...
                if row.get("turma"):
                    turma = row["turma"]
                    all_group_names.add(turma)
                    student_group_relations.append(
                        {"prontuario": pront, "grupo_nome": turma}
                    )

        # Executa as operações em massa
        if students_to_create:
            estudante_repo.bulk_create(students_to_create)
        if students_to_update:
            estudante_repo.bulk_update(students_to_update)

        # Processa grupos e associações
        if student_group_relations:
            # Garante que todos os grupos existam no DB
            grupo_map = _get_or_create_groups(grupo_repo.get_session(), all_group_names)

            # Garante que todos os estudantes existam no DB
            all_pronts = {rel["prontuario"] for rel in student_group_relations}
            student_map = {
                s.prontuario: s for s in estudante_repo.por_prontuario(all_pronts)
            }

            # Associa estudantes a grupos
            for rel in student_group_relations:
                student = student_map.get(rel["prontuario"])
                group_id = grupo_map.get(rel["grupo_nome"])
                if student and group_id:
                    # Evita adicionar associações duplicadas
                    if not any(g.id == group_id for g in student.grupos):
                        grupo = grupo_repo.read_one(group_id)
                        if grupo:
                            student.grupos.append(grupo)

        estudante_repo.get_session().commit()
        return len(students_to_create)

    except (FileNotFoundError, csv.Error, KeyError, SQLAlchemyError) as e:
        raise DataImportError(
            f"Falha ao importar estudantes de '{csv_file_path}': {e}"
        ) from e


def import_reserves_csv(
    estudante_repo: EstudanteRepository, reserva_repo: ReservaRepository, csv_file_path: str
) -> int:
    """Importa reservas de almoço de um arquivo CSV para o banco de dados."""
    try:
        student_map = {s.prontuario: s.id for s in estudante_repo.read_all()}
        reserves_to_insert = []

        with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                row = adjust_keys(row)
                pront = row.get('pront', None)
                student_id = student_map.get(pront) if pront else None

                if student_id:
                    reserves_to_insert.append({
                        'estudante_id': student_id,
                        'prato': row.get('prato', 'Não especificado'),
                        'data': row.get('data'),
                        'cancelada': False
                    })

        if reserves_to_insert:
            reserva_repo.bulk_create(reserves_to_insert)

        reserva_repo.get_session().commit()
        return len(reserves_to_insert)

    except (FileNotFoundError, csv.Error, KeyError, SQLAlchemyError) as e:
        raise DataImportError(f"Falha ao importar reservas de '{csv_file_path}': {e}") from e
