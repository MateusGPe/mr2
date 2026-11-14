"""Testes unitários para a lógica pura de DialogoSessao."""

import datetime as dt
from pathlib import Path

from registro.gui.registrar import dialogo_sessao_logica as logica


def test_ordenar_e_expandir_slots_grade():
    grade = {
        "segunda": {
            "almoco": [
                {
                    "inicio": "12:00",
                    "fim": "12:30",
                    "turmas": ["1º B"],
                    "categorias": [],
                },
                {
                    "inicio": "11:00",
                    "fim": "11:30",
                    "turmas": ["*"],
                    "categorias": ["*"],
                },
            ]
        }
    }
    slots = logica.ordenar_slots_grade(grade, "segunda", "almoco")
    assert [s["inicio"] for s in slots] == ["11:00", "12:00"]
    assert logica.ordenar_slots_grade(None, "segunda", "almoco") == []

    grupos_todos = logica.expandir_grupos_slot(slots[0], ["1º A"], ["PAP"])
    assert grupos_todos == {"1º A", "PAP"}
    assert logica.resumo_slot_texto(slots[0]) == "Todas as turmas e categorias (*)"

    slot_muitos = {
        "turmas": ["1A", "1B", "1C", "1D", "1E"],
        "categorias": ["PAP"],
    }
    resumo = logica.resumo_slot_texto(slot_muitos)
    assert "(+1)" in resumo
    assert "Cat: PAP" in resumo


def test_slot_ativo_chave_ordenacao_e_refeicao_por_hora():
    slot = {"inicio": "11:00", "fim": "13:00"}
    assert logica.slot_esta_ativo_agora(slot, dt.datetime(2026, 3, 10, 12, 0)) is True
    assert logica.slot_esta_ativo_agora(slot, dt.datetime(2026, 3, 10, 15, 0)) is False
    assert logica.slot_esta_ativo_agora({"inicio": "xx", "fim": "yy"}) is False

    assert logica.chave_ordenacao_sessao(
        {"data": "10/03/2026", "hora": "11:30"}
    ) == dt.datetime(2026, 3, 10, 11, 30)
    assert logica.chave_ordenacao_sessao({"data": "invalida"}) == dt.datetime.min

    assert logica.indice_refeicao_por_hora(dt.time(18, 0)) == 2
    assert logica.indice_refeicao_por_hora(dt.time(12, 0)) == 1
    assert logica.indice_refeicao_por_hora(dt.time(9, 0)) == 0


def test_extrair_grupos_reservas_lanches_e_sessoes(tmp_path: Path):
    grupos = logica.extrair_grupos_reservas(
        [
            {"turma_estudante": "1º A, 1º B, N/A", "categorias": ["PAP", ""]},
            "invalido",
        ]
    )
    assert grupos == {"1º A", "1º B", "PAP"}

    arq = tmp_path / "lanches.json"
    conj, lista = logica.carregar_opcoes_lanche_arquivo(arq, ["Padrão"])
    assert conj == {"Padrão"}
    assert lista == ["Padrão"]
    assert arq.exists()

    arq.write_text('["Suco", "Bolo"]', encoding="utf-8")
    conj2, lista2 = logica.carregar_opcoes_lanche_arquivo(arq, ["Padrão"])
    assert conj2 == {"Suco", "Bolo"}
    assert lista2 == ["Bolo", "Suco"]

    linhas = logica.formatar_linhas_sessoes(
        [
            {
                "id": 1,
                "data": "10/03/2026",
                "hora": "11:30",
                "refeicao": "almoco",
                "item_servido": "",
                "grupos": ["A", "B", "C", "D"],
            },
            {
                "id": 2,
                "data": "11/03/2026",
                "hora": "12:00",
                "refeicao": "lanche",
                "item_servido": "Bolo",
                "grupos": [],
            },
        ]
    )
    assert linhas[0][0] == 2
    assert linhas[0][5] == "-"
    assert linhas[1][5].startswith("4 (A, B, C")
    assert len(logica.filtrar_linhas_sessoes(linhas, "bolo")) == 1
    assert len(logica.filtrar_linhas_sessoes(linhas, "")) == 2
