# ----------------------------------------------------------------------------
# Arquivo: tests/nucleo/test_configuracao_planilha.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

from unittest.mock import MagicMock

from registro.nucleo.constants import NOME_ABA_CONFIGURACAO, NOME_ABA_LANCHES
from registro.nucleo.services import grade_horarios_service, sync_service


def test_converter_linhas_configuracao_para_grade():
    linhas = [
        ["Dia", "Refeição", "Horário Início", "Horário Fim", "Turmas Liberadas", "Categorias Permitidas"],
        ["Segunda-feira", "Almoço", "11:30", "12:15", "1º BEM, 2º BEM", "REGULAR, PAP"],
        ["segunda", "almoço", "12:15", "13:00", "3º BEM", "REGULAR"],
        ["terça", "Lanche", "15:30", "16:00", "*", "Optativa Artes"],
        ["quarta", "jantar", "18:00", "19:00", "Turma ADS", "*"],
        ["", "", "", "", "", ""],  # linha vazia
    ]

    grade = grade_horarios_service.converter_linhas_configuracao_para_grade(linhas)

    # Verifica segunda almoço
    assert len(grade["segunda"]["almoco"]) == 2
    slot1 = grade["segunda"]["almoco"][0]
    assert slot1["inicio"] == "11:30"
    assert slot1["fim"] == "12:15"
    assert slot1["turmas"] == ["1º BEM", "2º BEM"]
    assert slot1["categorias"] == ["REGULAR", "PAP"]

    slot2 = grade["segunda"]["almoco"][1]
    assert slot2["inicio"] == "12:15"
    assert slot2["fim"] == "13:00"
    assert slot2["turmas"] == ["3º BEM"]
    assert slot2["categorias"] == ["REGULAR"]

    # Verifica terça lanche (preserva grafia da categoria)
    assert len(grade["terca"]["lanche"]) == 1
    slot_terca = grade["terca"]["lanche"][0]
    assert slot_terca["turmas"] == ["*"]
    assert slot_terca["categorias"] == ["Optativa Artes"]

    # Verifica quarta jantar
    assert len(grade["quarta"]["jantar"]) == 1
    slot_quarta = grade["quarta"]["jantar"][0]
    assert slot_quarta["turmas"] == ["Turma ADS"]
    assert slot_quarta["categorias"] == ["*"]


def test_validar_janela_horario_com_categoria(tmp_path):
    caminho_grade = tmp_path / "grade_teste.json"
    grade = {
        "segunda": {
            "almoco": [
                {
                    "inicio": "11:30",
                    "fim": "12:15",
                    "turmas": ["*"],
                    "categorias": ["PAP"],
                },
                {
                    "inicio": "12:15",
                    "fim": "13:00",
                    "turmas": ["1º BEM"],
                    "categorias": ["*"],
                },
            ],
            "lanche": [],
            "jantar": [],
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho_grade)

    # Às 11:45, aluno 1º BEM com categoria PAP -> DEVE autorizar
    aut, motivo = grade_horarios_service.validar_janela_horario(
        turmas_estudante=["1º BEM"],
        refeicao="almoco",
        hora_atual="11:45",
        dia_semana="segunda",
        categorias_estudante=["PAP"],
        caminho_grade=caminho_grade,
    )
    assert aut is True
    assert motivo == ""

    # Às 11:45, aluno 1º BEM sem categoria -> DEVE BLOQUEAR informando o horário da sua turma (12:15 às 13:00)
    aut, motivo = grade_horarios_service.validar_janela_horario(
        turmas_estudante=["1º BEM"],
        refeicao="almoco",
        hora_atual="11:45",
        dia_semana="segunda",
        categorias_estudante=[],
        caminho_grade=caminho_grade,
    )
    assert aut is False
    assert "Fora do horário da sua turma. Seu horário: 12:15 às 13:00." in motivo

    # Às 12:30, aluno 1º BEM sem categoria -> DEVE autorizar (slot de 1º BEM)
    aut, motivo = grade_horarios_service.validar_janela_horario(
        turmas_estudante=["1º BEM"],
        refeicao="almoco",
        hora_atual="12:30",
        dia_semana="segunda",
        categorias_estudante=[],
        caminho_grade=caminho_grade,
    )
    assert aut is True


def test_validar_janela_horario_turma_coringa_todas(tmp_path):
    caminho_grade = tmp_path / "grade_coringa.json"
    grade = {
        "segunda": {
            "almoco": [],
            "lanche": [
                {
                    "inicio": "15:30",
                    "fim": "16:00",
                    "turmas": ["*"],
                    "categorias": ["PAP"],
                }
            ],
            "jantar": [],
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho_grade)

    # Qualquer turma com categoria PAP autoriza
    aut, _ = grade_horarios_service.validar_janela_horario(
        turmas_estudante=["Qualquer Turma X"],
        refeicao="lanche",
        hora_atual="15:40",
        dia_semana="segunda",
        categoria_estudante="PAP",
        caminho_grade=caminho_grade,
    )
    assert aut is True

    # Aluno REGULAR bloqueia
    aut, motivo = grade_horarios_service.validar_janela_horario(
        turmas_estudante=["Qualquer Turma X"],
        refeicao="lanche",
        hora_atual="15:40",
        dia_semana="segunda",
        categoria_estudante="REGULAR",
        caminho_grade=caminho_grade,
    )
    assert aut is False


def test_atualizar_sessao_ativa_facade(facade):
    # Cria sessão inicial
    id_sessao = facade.iniciar_nova_sessao(
        {
            "refeicao": "lanche",
            "item_servido": "Biscoito",
            "periodo": "Integral",
            "data": "2026-11-06",
            "hora": "15:30",
            "grupos": [],
        }
    )
    assert id_sessao is not None
    assert facade.id_sessao_ativa == id_sessao

    # Atualiza sessão ativa
    facade.criar_grupo("PAP", tipo="categoria")
    sucesso = facade.atualizar_sessao_ativa(
        item_servido="Fruta e Suco",
        turmas=["PAP"],
    )
    assert sucesso is True

    detalhes = facade.obter_detalhes_sessao_ativa()
    assert detalhes["item_servido"] == "Fruta e Suco"
    assert "PAP" in detalhes["grupos"]


def test_sincronizacao_lanches_e_configuracao(facade, monkeypatch, tmp_path):
    # Mock do google_api_service
    mock_planilha = MagicMock()
    monkeypatch.setattr(
        sync_service.google_api_service, "obter_planilha", lambda: mock_planilha
    )

    valores_config = [
        ["Dia", "Refeição", "Horário Início", "Horário Fim", "Turmas Liberadas", "Categorias Permitidas"],
        ["segunda", "lanche", "10:00", "10:30", "1º BEM", "PAP"],
    ]
    valores_lanches = [
        ["Lanche"],
        ["Vitamina de Morango"],
        ["Iogurte com Cereais"],
    ]

    def mock_buscar_valores(planilha, nome_aba):
        if nome_aba == NOME_ABA_CONFIGURACAO:
            return valores_config
        elif nome_aba == NOME_ABA_LANCHES:
            return valores_lanches
        return []

    monkeypatch.setattr(
        sync_service.google_api_service, "buscar_valores_aba", mock_buscar_valores
    )
    mock_anexar = MagicMock()
    monkeypatch.setattr(
        sync_service.google_api_service, "anexar_linhas_unicas", mock_anexar
    )

    # Executa sincronização isolada em diretório temporário
    caminho_config_teste = tmp_path / "config"
    sync_service.sincronizar_do_google_sheets(
        facade.repo_estudante,
        facade.repo_reserva,
        facade.repo_grupo,
        caminho_config=caminho_config_teste,
    )

    # Verifica se os lanches foram salvos no JSON temporário
    caminho_lanches = caminho_config_teste / "lanches.json"
    assert caminho_lanches.exists()
    import json
    with open(caminho_lanches, "r", encoding="utf-8") as f:
        lanches_salvos = json.load(f)
    assert "Vitamina de Morango" in lanches_salvos
    assert "Iogurte com Cereais" in lanches_salvos

    # Verifica se a grade foi salva no JSON temporário
    caminho_grade = caminho_config_teste / "grade_horarios.json"
    assert caminho_grade.exists()

    # Testa envio de novo lanche
    sync_service.sincronizar_novo_lanche_para_planilha("Bolo de Cenoura")
    mock_anexar.assert_called_with(mock_planilha, [["Bolo de Cenoura"]], NOME_ABA_LANCHES)

