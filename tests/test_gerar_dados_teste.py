# ----------------------------------------------------------------------------
# Arquivo: tests/test_gerar_dados_teste.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Testes para validar a integridade e coerência da massa de dados gerada pelo
script scripts/gerar_dados_teste.py.
"""

from scripts.gerar_dados_teste import (
    CATEGORIAS_PONTUAIS_RESERVA,
    TURMAS_PADRAO,
    GeradorDadosTeste,
)
from registro.nucleo.constants import (
    CABECALHO_CANCELADOS,
    CABECALHO_CONFIGURACAO,
    CABECALHO_DISCENTES,
    CABECALHO_EXPORTACAO,
    CABECALHO_LANCHES,
    CABECALHO_RESERVAS,
)
from registro.nucleo.services.grade_horarios_service import (
    converter_linhas_configuracao_para_grade,
)


def test_geracao_estudantes_valida():
    gerador = GeradorDadosTeste(qtd_alunos=30, seed=123)
    linhas = gerador.gerar_estudantes()

    assert len(linhas) == 30
    matriculas = set()
    categorias_encontradas = set()
    for row in linhas:
        assert len(row) == len(CABECALHO_DISCENTES)
        matr, nome, turma, categoria = row
        assert matr.startswith("SP30")
        assert len(nome.split()) >= 2
        assert turma in TURMAS_PADRAO
        assert categoria != "REGULAR"
        if categoria != "-":
            for tag in categoria.split(","):
                categorias_encontradas.add(tag.strip())
        matriculas.add(matr)

    # Prontuários devem ser únicos e deve haver categorias reais (PAP, ESP1, LIB0...)
    assert len(matriculas) == 30
    assert categorias_encontradas & {"PAP", "ESP1", "LIB0"}


def test_geracao_configuracao_compativel_com_servico_grade():
    gerador = GeradorDadosTeste(qtd_alunos=10, seed=123)
    linhas_config = gerador.gerar_configuracao()

    assert len(linhas_config) > 0
    for row in linhas_config:
        assert len(row) == len(CABECALHO_CONFIGURACAO)

    grade = converter_linhas_configuracao_para_grade(
        [CABECALHO_CONFIGURACAO] + linhas_config
    )
    # Verifica se os dias úteis possuem os slots esperados
    assert len(grade["segunda"]["almoco"]) >= 1
    assert len(grade["segunda"]["lanche"]) >= 1
    assert len(grade["segunda"]["jantar"]) >= 1
    assert len(grade["sexta"]["almoco"]) >= 1


def test_massa_completa_consistencia():
    gerador = GeradorDadosTeste(qtd_alunos=40, seed=999)
    dados = gerador.gerar_massa_completa(dias_passados=2, dias_futuros=1)

    assert "Discentes" in dados
    assert "Configuração" in dados
    assert "Lanches" in dados
    assert "DB" in dados
    assert "Almoço" in dados
    assert "Jantar" in dados
    assert "Lanche" in dados
    assert "Consumo_Cancelados" in dados

    cab_disc, lin_disc = dados["Discentes"]
    assert cab_disc == CABECALHO_DISCENTES
    assert len(lin_disc) == 40

    cab_res, lin_res = dados["DB"]
    assert cab_res == CABECALHO_RESERVAS
    assert len(lin_res) > 0
    assert all(len(row) == len(CABECALHO_RESERVAS) for row in lin_res)
    turnos_presentes = {(row[7], row[8]) for row in lin_res}
    assert ("Sim", "Não") in turnos_presentes
    assert ("Não", "Sim") in turnos_presentes
    assert ("Sim", "Sim") in turnos_presentes
    assert any(
        any(tag in row[6] for tag in CATEGORIAS_PONTUAIS_RESERVA)
        for row in lin_res
    )

    cab_alm, lin_alm = dados["Almoço"]
    assert cab_alm == CABECALHO_EXPORTACAO
    assert len(lin_alm) > 0

    cab_jan, lin_jan = dados["Jantar"]
    assert cab_jan == CABECALHO_EXPORTACAO
    assert len(lin_jan) > 0

    cab_canc, lin_canc = dados["Consumo_Cancelados"]
    assert cab_canc == CABECALHO_CANCELADOS
    assert len(lin_canc) > 0

