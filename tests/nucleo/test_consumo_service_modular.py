# ----------------------------------------------------------------------------
# Arquivo: tests/nucleo/test_consumo_service_modular.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Testes unitários específicos para o serviço modular de consumo e o pipeline
unificado de autorização em registro.nucleo.services.consumo_service.
"""

from registro.nucleo.services import consumo_service


def test_modular_consumo_estudante_nao_encontrado(repos, criar_sessao):
    sessao = criar_sessao(refeicao="lanche")
    res = consumo_service.registrar_consumo(
        repo_sessao=repos["sessao"],
        repo_estudante=repos["estudante"],
        repo_reserva=repos["reserva"],
        repo_consumo=repos["consumo"],
        id_sessao=sessao.id,
        prontuario="IQ3099999",
    )
    assert res["autorizado"] is False
    assert res["motivo"] == "Estudante não encontrado."


def test_modular_consumo_duplicado(repos, criar_grupo, criar_estudante, criar_sessao):
    grupo = criar_grupo("1A")
    estudante = criar_estudante("IQ3001001", "Aluno Teste", grupos=[grupo])
    sessao = criar_sessao(refeicao="lanche", grupos=[grupo])

    res1 = consumo_service.registrar_consumo(
        repo_sessao=repos["sessao"],
        repo_estudante=repos["estudante"],
        repo_reserva=repos["reserva"],
        repo_consumo=repos["consumo"],
        id_sessao=sessao.id,
        prontuario=estudante.prontuario,
    )
    assert res1["autorizado"] is True

    res2 = consumo_service.registrar_consumo(
        repo_sessao=repos["sessao"],
        repo_estudante=repos["estudante"],
        repo_reserva=repos["reserva"],
        repo_consumo=repos["consumo"],
        id_sessao=sessao.id,
        prontuario=estudante.prontuario,
    )
    assert res2["autorizado"] is False
    assert res2["motivo"] == "Consumo já registrado."


def test_modular_consumo_com_reserva_sem_reserva(
    repos, criar_grupo, criar_estudante, criar_sessao
):
    grupo = criar_grupo("1B")
    estudante = criar_estudante("IQ3002002", "Aluno Sem Reserva", grupos=[grupo])
    sessao = criar_sessao(refeicao="almoço", grupos=[grupo])

    res = consumo_service.registrar_consumo_com_reserva(
        repo_sessao=repos["sessao"],
        repo_estudante=repos["estudante"],
        repo_reserva=repos["reserva"],
        repo_consumo=repos["consumo"],
        id_sessao=sessao.id,
        prontuario=estudante.prontuario,
    )
    assert res["autorizado"] is False
    assert res["motivo"] == "Sem reserva válida."
