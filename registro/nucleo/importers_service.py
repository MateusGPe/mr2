# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/importers_service.py (Importadores de Dados)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Funções para importar dados de estudantes e reservas, encapsulando a
lógica de processamento e inserção no banco de dados.
"""

import csv
import logging
from pathlib import Path
from typing import Dict, Optional, Set

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from registro.nucleo.constants import TIPO_GRUPO_CATEGORIA, TIPO_GRUPO_TURMA
from registro.nucleo.exceptions import ErroImportacaoDados
from registro.nucleo.repository import (
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
)
from registro.nucleo.services.reserva_service import persistir_ou_mesclar_reservas
from registro.nucleo.utils import (
    ajustar_chaves_e_valores,
    normalizar_lista_categorias,
    resolver_turnos_reserva,
)

logger = logging.getLogger(__name__)


def _obter_ou_criar_grupos(
    sessao_db: Session,
    nomes_grupos: Set[str],
    tipo: str = TIPO_GRUPO_TURMA,
) -> Dict[str, int]:
    """Busca ou cria grupos com o tipo especificado e retorna mapa nome -> ID."""
    repo_grupo = RepositorioGrupo(sessao_db)
    grupos_existentes = repo_grupo.por_nomes(nomes_grupos)
    mapa_existentes = {g.nome: g.id for g in grupos_existentes}

    nomes_novos_grupos = nomes_grupos - set(mapa_existentes.keys())
    if nomes_novos_grupos:
        novas_linhas = [{"nome": nome, "tipo": tipo} for nome in nomes_novos_grupos]
        repo_grupo.criar_em_massa(novas_linhas)
        todos_os_grupos = repo_grupo.por_nomes(nomes_grupos)
        return {g.nome: g.id for g in todos_os_grupos}
    return mapa_existentes


def importar_estudantes_csv(
    repo_estudante: RepositorioEstudante,
    repo_grupo: RepositorioGrupo,
    caminho_arquivo_csv: Path,
) -> int:
    """Importa e atualiza estudantes, suas turmas e categorias de um arquivo CSV."""
    try:
        estudantes_para_criar = []
        estudantes_para_atualizar = []
        relacoes_estudante_grupo = []
        turmas_nomes: Set[str] = set()
        categorias_nomes: Set[str] = set()
        linhas_ignoradas = 0
        prontuarios_no_csv = set()

        mapa_estudantes_existentes = {
            s.prontuario: s
            for s in repo_estudante.ler_todos_com_grupos()
        }

        with open(caminho_arquivo_csv, "r", encoding="utf-8") as arquivo_csv:
            leitor = csv.DictReader(arquivo_csv)
            for i, linha in enumerate(leitor):
                linha_original = linha.copy()
                if not any(v and str(v).strip() for v in linha_original.values()):
                    continue
                linha = ajustar_chaves_e_valores(linha)
                pront = linha.get("pront")
                if not pront:
                    logger.debug(
                        "Linha %d do CSV ignorada: 'prontuário' ausente ou vazio. Dados: %s",
                        i + 2,  # +1 para cabeçalho, +1 para índice 0
                        linha_original,
                    )
                    linhas_ignoradas += 1
                    continue

                # Processa associações de turma e categorias em TODAS as linhas em que o estudante aparece.
                if turma := linha.get("turma"):
                    turma_limpa = str(turma).strip()
                    if turma_limpa:
                        turmas_nomes.add(turma_limpa)
                        relacoes_estudante_grupo.append(
                            {"prontuario": pront, "nome_grupo": turma_limpa}
                        )

                for cat_nome in normalizar_lista_categorias(linha.get("categoria")):
                    categorias_nomes.add(cat_nome)
                    relacoes_estudante_grupo.append(
                        {"prontuario": pront, "nome_grupo": cat_nome}
                    )

                # Se o prontuário já foi processado neste CSV, pula criação/atualização do aluno.
                if pront in prontuarios_no_csv:
                    continue
                prontuarios_no_csv.add(pront)

                dados_estudante = {
                    "prontuario": pront,
                    "nome": linha.get("nome", ""),
                }

                if pront in mapa_estudantes_existentes:
                    estudante_existente = mapa_estudantes_existentes[pront]
                    if estudante_existente.nome != dados_estudante["nome"]:
                        payload = {**dados_estudante, "id": estudante_existente.id}
                        estudantes_para_atualizar.append(payload)
                else:
                    estudantes_para_criar.append(dados_estudante)

        if linhas_ignoradas > 0:
            logger.info(
                "%d linha(s) foram ignoradas por falta de prontuário.", linhas_ignoradas
            )

        if estudantes_para_criar:
            repo_estudante.criar_em_massa(estudantes_para_criar)
        if estudantes_para_atualizar:
            repo_estudante.atualizar_em_massa(estudantes_para_atualizar)

        if relacoes_estudante_grupo:
            sessao_db = repo_grupo.obter_sessao()
            mapa_grupos: Dict[str, int] = {}
            if turmas_nomes:
                mapa_grupos.update(
                    _obter_ou_criar_grupos(sessao_db, turmas_nomes, tipo=TIPO_GRUPO_TURMA)
                )
            # Categorias explícitas nunca sobrescrevem o tipo se o mesmo nome já veio como turma,
            # mas se veio apenas na coluna Categoria é criado como TIPO_GRUPO_CATEGORIA.
            cats_novas = categorias_nomes - set(mapa_grupos.keys())
            if cats_novas:
                mapa_grupos.update(
                    _obter_ou_criar_grupos(sessao_db, cats_novas, tipo=TIPO_GRUPO_CATEGORIA)
                )

            todos_nomes_grupos = turmas_nomes | categorias_nomes
            mapa_grupos_obj = {
                g.id: g for g in repo_grupo.por_nomes(todos_nomes_grupos)
            }

            prontuarios_envolvidos = {
                rel["prontuario"] for rel in relacoes_estudante_grupo
            }

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
                        grupo = mapa_grupos_obj.get(id_grupo) or repo_grupo.ler_um(id_grupo)
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
    repo_grupo: Optional[RepositorioGrupo] = None,
) -> int:
    """Importa reservas de um arquivo CSV, mesclando turnos e vinculando categorias pontuais."""
    try:
        mapa_estudantes = {
            s.prontuario: s.id for s in repo_estudante.ler_todos()}
        itens_reservas = []
        linhas_ignoradas = 0

        with open(caminho_arquivo_csv, "r", encoding="utf-8") as arquivo_csv:
            leitor = csv.DictReader(arquivo_csv)
            for i, linha in enumerate(leitor):
                linha_original = linha.copy()
                if not any(v and str(v).strip() for v in linha_original.values()):
                    continue
                linha = ajustar_chaves_e_valores(linha)
                pront = linha.get("pront") or linha.get("prontuario")
                data = linha.get("data")
                id_estudante = mapa_estudantes.get(pront) if pront else None

                if not id_estudante or not data:
                    logger.warning(
                        "Linha %d do CSV de reservas ignorada: 'prontuário' ou 'data' ausente/inválido. Dados: %s",
                        i + 2,
                        linha_original,
                    )
                    linhas_ignoradas += 1
                    continue

                almoco, jantar = resolver_turnos_reserva(linha)
                cats_linha = normalizar_lista_categorias(
                    linha.get("categorias") if linha.get("categorias") is not None else linha.get("categoria")
                )

                itens_reservas.append(
                    {
                        "estudante_id": id_estudante,
                        "prato": linha.get("prato", "Não especificado"),
                        "data": data,
                        "almoco": almoco,
                        "jantar": jantar,
                        "cancelada": False,
                        "categorias": cats_linha,
                    }
                )

        criadas, atualizadas = persistir_ou_mesclar_reservas(
            repo_reserva, itens_reservas, repo_grupo=repo_grupo
        )

        repo_reserva.obter_sessao().commit()
        return criadas + atualizadas

    except (FileNotFoundError, csv.Error, KeyError, ValueError, SQLAlchemyError) as e:
        repo_reserva.obter_sessao().rollback()
        raise ErroImportacaoDados(
            f"Falha ao importar reservas de '{caminho_arquivo_csv}': {e}"
        ) from e
