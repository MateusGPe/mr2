"""
Funções para importar dados de estudantes e reservas, encapsulando a
lógica de processamento e inserção no banco de dados.
"""

import csv

from sqlalchemy.exc import SQLAlchemyError

from registro.nucleo.exceptions import DataImportError
from registro.nucleo.repository import ReserveRepository, StudentRepository
from registro.nucleo.utils import adjust_keys, find_best_matching_pair


def import_students_csv(student_repo: StudentRepository, csv_file_path: str) -> int:
    """Importa novos estudantes de um arquivo CSV para o banco de dados."""
    try:
        existing_pronts = {s.pront for s in student_repo.read_all()}
        new_students = []

        with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                row = adjust_keys(row)
                pront = row.get('pront')
                if pront and pront not in existing_pronts:
                    new_students.append({
                        'pront': pront,
                        'nome': row.get('nome', ''),
                        'turma': row.get('turma', '')
                    })
                    existing_pronts.add(pront)

        if new_students:
            student_repo.bulk_create(new_students)
        return len(new_students)

    except (FileNotFoundError, csv.Error, KeyError, SQLAlchemyError) as e:
        raise DataImportError(f"Falha ao importar estudantes de '{csv_file_path}': {e}") from e


def import_reserves_csv(
    student_repo: StudentRepository, reserve_repo: ReserveRepository, csv_file_path: str
) -> int:
    """Importa reservas de um arquivo CSV para o banco de dados."""
    try:
        all_students = student_repo.read_all()
        existing_students_map = {s.pront: s for s in all_students}
        student_tuples = {(s.pront, s.nome) for s in all_students}

        new_students_data = {}
        csv_reserves_data = []
        unique_dates = set()
        reserved_data_pront_pairs = set()

        with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                row = adjust_keys(row)
                pront, nome, data = row['pront'], row['nome'], row['data']

                unique_dates.add(data)
                reserved_data_pront_pairs.add((data, pront))

                if pront not in existing_students_map and pront not in new_students_data:
                    pair, ratio = find_best_matching_pair((pront, nome), list(student_tuples))
                    if ratio >= 95:
                        (pront, nome) = pair
                    else:
                        new_students_data[pront] = {
                            'pront': pront,
                            'nome': nome,
                            'turma': row['turma']
                        }
                csv_reserves_data.append(
                    {
                        'pront': pront,
                        'prato': row['prato'],
                        'data': data,
                        'snacks': False,
                        'reserved': True
                    })

        if new_students_data:
            student_repo.bulk_create(list(new_students_data.values()))
            all_students = student_repo.read_all()
            existing_students_map = {s.pront: s for s in all_students}

        not_in_reserve_entries = [
            {
                'pront': student.pront,
                'prato': 'Sem Reserva',
                'data': date,
                'snacks': False,
                'reserved': False
            }
            for student in all_students
            for date in unique_dates
            if (date, student.pront) not in reserved_data_pront_pairs
        ]

        all_reserves_data = csv_reserves_data + not_in_reserve_entries
        reserves_to_insert = [
            {
                'student_id': existing_students_map.get(r_info['pront']).id,
                'prato': r_info.get('prato'),
                'data': r_info['data'],
                'reserved': r_info['reserved'],
                'snacks': r_info['snacks']
            }
            for r_info in all_reserves_data if existing_students_map.get(r_info['pront'])
        ]

        if reserves_to_insert:
            reserve_repo.bulk_create(reserves_to_insert)
        return len(reserves_to_insert)

    except (FileNotFoundError, csv.Error, KeyError, SQLAlchemyError) as e:
        raise DataImportError(f"Falha ao importar reservas de '{csv_file_path}': {e}") from e


def reserve_snacks_for_all(
    student_repo: StudentRepository, reserve_repo: ReserveRepository, data: str, prato: str
) -> int:
    """Cria uma reserva de lanche para todos os estudantes em uma data."""
    try:
        students = student_repo.read_all()
        reserves_to_insert = [
            {
                'student_id': student.id,
                'prato': prato,
                'data': data,
                'reserved': True,
                'snacks': True
            }
            for student in students
        ]
        if reserves_to_insert:
            reserve_repo.bulk_create(reserves_to_insert)
        return len(reserves_to_insert)

    except SQLAlchemyError as e:
        raise DataImportError(f"Falha ao reservar lanches: {e}") from e
