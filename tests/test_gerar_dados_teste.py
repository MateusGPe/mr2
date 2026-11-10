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
    _hora_para_minutos,
    converter_linhas_configuracao_para_grade,
    salvar_grade_horarios,
    validar_janela_horario,
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

    assert len(linhas_config) >= 30
    for row in linhas_config:
        assert len(row) == len(CABECALHO_CONFIGURACAO)
        assert _hora_para_minutos(row[2]) < _hora_para_minutos(row[3])

    grade = converter_linhas_configuracao_para_grade(
        [CABECALHO_CONFIGURACAO] + linhas_config
    )
    # Verifica escalonamento múltiplo nos dias úteis e programação no sábado
    for dia in ("segunda", "terca", "quarta", "quinta", "sexta"):
        assert len(grade[dia]["almoco"]) >= 2
        assert len(grade[dia]["lanche"]) >= 2
        assert len(grade[dia]["jantar"]) >= 1
    assert len(grade["sabado"]["almoco"]) >= 2
    assert len(grade["sabado"]["lanche"]) >= 2

    # Verifica diferenciação entre dias da semana (não é repetição idêntica)
    assert grade["segunda"]["almoco"] != grade["terca"]["almoco"]
    assert grade["quarta"]["jantar"] != grade["sexta"]["jantar"]

    # Verifica cobertura de todas as turmas padrão, categorias e coringas
    turmas_encontradas = set()
    categorias_encontradas = set()
    tipos_restricao = set()
    for dia_dict in grade.values():
        for slots in dia_dict.values():
            for slot in slots:
                turmas = slot["turmas"]
                cats = slot["categorias"]
                turma_especifica = turmas != ["*"]
                cat_especifica = cats != ["*"]
                tipos_restricao.add((turma_especifica, cat_especifica))
                turmas_encontradas.update(t for t in turmas if t != "*")
                categorias_encontradas.update(c for c in cats if c != "*")

    assert set(TURMAS_PADRAO).issubset(turmas_encontradas)
    assert {"PAP", "ESP1", "LIB0", "EVENTO_ESPORTIVO", "VISITA_TECNICA"}.issubset(
        categorias_encontradas
    )
    # Deve contemplar slots abertos, só por turma, só por categoria e combinados
    assert tipos_restricao == {
        (False, False),
        (True, False),
        (False, True),
        (True, True),
    }

    # Verifica presença dos coringas '*' e 'TODAS' na planilha bruta
    celulas_coringa = {row[4] for row in linhas_config} | {row[5] for row in linhas_config}
    assert "*" in celulas_coringa
    assert "TODAS" in celulas_coringa


def test_consumos_coerentes_com_grade_configuracao(tmp_path):
    from datetime import datetime

    gerador = GeradorDadosTeste(qtd_alunos=60, seed=77)
    dados = gerador.gerar_massa_completa(dias_passados=5, dias_futuros=1)

    _, lin_config = dados["Configuração"]
    grade = converter_linhas_configuracao_para_grade(
        [CABECALHO_CONFIGURACAO] + lin_config
    )
    caminho_grade = tmp_path / "grade_teste.json"
    salvar_grade_horarios(grade, caminho_grade)

    mapa_dias = {
        0: "segunda",
        1: "terca",
        2: "quarta",
        3: "quinta",
        4: "sexta",
        5: "sabado",
        6: "domingo",
    }

    # Consumos regulares de almoço devem respeitar a janela configurada da grade
    _, lin_almoco = dados["Almoço"]
    regulares_almoco = [r for r in lin_almoco if r[4] != "Sem Reserva (Exceção)"]
    assert len(regulares_almoco) > 0
    for _matr, data_s, _nome, turma, _prato, hora, categoria in regulares_almoco:
        dia_sem = mapa_dias[datetime.strptime(data_s, "%Y-%m-%d").weekday()]
        ok, motivo = validar_janela_horario(
            turmas_estudante=[turma],
            refeicao="almoco",
            hora_atual=hora[:5],
            dia_semana=dia_sem,
            categoria_estudante=categoria,
            tolerancia_min=0,
            caminho_grade=caminho_grade,
        )
        assert ok is True, f"Consumo fora da grade em {data_s} {hora}: {motivo}"


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

