# --- Arquivo: registro/nucleo/importers_service.py ---

"""
Funções para importar dados de estudantes e reservas, encapsulando a
lógica de processamento e inserção no banco de dados.
"""

import csv
from pathlib import Path
from typing import Dict, Set

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from registro.nucleo.exceptions import ErroImportacaoDados
from registro.nucleo.repository import (
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
)
from registro.nucleo.utils import ajustar_chaves_e_valores


def _obter_ou_criar_grupos(
    sessao_db: Session, nomes_grupos: Set[str]
) -> Dict[str, int]:
    """Busca ou cria grupos e retorna um mapeamento de nome para ID."""
    repo_grupo = RepositorioGrupo(sessao_db)
    grupos_existentes = repo_grupo.por_nomes(nomes_grupos)
    mapa_existentes = {g.nome: g.id for g in grupos_existentes}

    nomes_novos_grupos = nomes_grupos - set(mapa_existentes.keys())
    if nomes_novos_grupos:
        novas_linhas = [{"nome": nome} for nome in nomes_novos_grupos]
        repo_grupo.criar_em_massa(novas_linhas)
        todos_os_grupos = repo_grupo.por_nomes(nomes_grupos)
        return {g.nome: g.id for g in todos_os_grupos}
    return mapa_existentes


def importar_estudantes_csv(
    repo_estudante: RepositorioEstudante,
    repo_grupo: RepositorioGrupo,
    caminho_arquivo_csv: Path,
) -> int:
    """Importa e atualiza estudantes e suas associações com grupos de um arquivo CSV."""
    try:
        estudantes_para_criar = []
        estudantes_para_atualizar = []
        relacoes_estudante_grupo = []
        todos_nomes_grupos = set()

        mapa_estudantes_existentes = {
            s.prontuario: s
            for s in repo_estudante.ler_todos_com_grupos()  # Otimização aqui
        }

        with open(caminho_arquivo_csv, "r", encoding="utf-8") as arquivo_csv:
            leitor = csv.DictReader(arquivo_csv)
            for linha in leitor:
                linha = ajustar_chaves_e_valores(linha)
                pront = linha.get("pront")
                if not pront:
                    continue

                dados_estudante = {"prontuario": pront, "nome": linha.get("nome", "")}

                if pront in mapa_estudantes_existentes:
                    estudante_existente = mapa_estudantes_existentes[pront]
                    if estudante_existente.nome != dados_estudante["nome"]:
                        payload = {**dados_estudante, "id": estudante_existente.id}
                        estudantes_para_atualizar.append(payload)
                else:
                    estudantes_para_criar.append(dados_estudante)

                if turma := linha.get("turma"):
                    todos_nomes_grupos.add(turma)
                    relacoes_estudante_grupo.append(
                        {"prontuario": pront, "nome_grupo": turma}
                    )

        if estudantes_para_criar:
            repo_estudante.criar_em_massa(estudantes_para_criar)
        if estudantes_para_atualizar:
            repo_estudante.atualizar_em_massa(estudantes_para_atualizar)

        if relacoes_estudante_grupo:
            mapa_grupos = _obter_ou_criar_grupos(
                repo_grupo.obter_sessao(), todos_nomes_grupos
            )

            prontuarios_envolvidos = {
                rel["prontuario"] for rel in relacoes_estudante_grupo
            }

            # Otimização: Carrega estudantes e seus grupos de uma vez
            estudantes_envolvidos = repo_estudante.por_prontuarios_com_grupos(
                prontuarios_envolvidos
            )
            mapa_estudantes = {s.prontuario: s for s in estudantes_envolvidos}

            for rel in relacoes_estudante_grupo:
                estudante = mapa_estudantes.get(rel["prontuario"])
                id_grupo = mapa_grupos.get(rel["nome_grupo"])
                if estudante and id_grupo:
                    ids_grupos_atuais = {g.id for g in estudante.grupos}
                    if id_grupo not in ids_grupos_atuais:
                        grupo = repo_grupo.ler_um(id_grupo)
                        if grupo:
                            estudante.grupos.append(grupo)

        repo_estudante.obter_sessao().commit()
        return len(estudantes_para_criar)

    except (FileNotFoundError, csv.Error, KeyError, SQLAlchemyError) as e:
        repo_estudante.obter_sessao().rollback()
        raise ErroImportacaoDados(
            f"Falha ao importar estudantes de '{caminho_arquivo_csv}': {e}"
        ) from e


def importar_reservas_csv(
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    caminho_arquivo_csv: Path,
) -> int:
    """Importa reservas de almoço de um arquivo CSV para o banco de dados."""
    try:
        mapa_estudantes = {s.prontuario: s.id for s in repo_estudante.ler_todos()}
        reservas_para_inserir = []

        with open(caminho_arquivo_csv, "r", encoding="utf-8") as arquivo_csv:
            leitor = csv.DictReader(arquivo_csv)
            for linha in leitor:
                linha = ajustar_chaves_e_valores(linha)
                pront = linha.get("pront")
                id_estudante = mapa_estudantes.get(pront) if pront else None

                if id_estudante:
                    reservas_para_inserir.append(
                        {
                            "estudante_id": id_estudante,
                            "prato": linha.get("prato", "Não especificado"),
                            "data": linha.get("data"),
                            "cancelada": False,
                        }
                    )

        if reservas_para_inserir:
            repo_reserva.criar_em_massa(reservas_para_inserir)

        repo_reserva.obter_sessao().commit()
        return len(reservas_para_inserir)

    except (FileNotFoundError, csv.Error, KeyError, SQLAlchemyError) as e:
        repo_reserva.obter_sessao().rollback()
        raise ErroImportacaoDados(
            f"Falha ao importar reservas de '{caminho_arquivo_csv}': {e}"
        ) from e
