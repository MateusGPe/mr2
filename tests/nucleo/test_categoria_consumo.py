"""
Testes unitários para validação de categoria de discente (PAP / REGULAR) no consumo.
"""

import pytest
from registro.nucleo.facade import FachadaRegistro


def test_consumo_bloqueado_quando_categoria_incompativel(facade: FachadaRegistro, criar_grupo, criar_estudante):
    """Garante que aluno REGULAR não consegue consumir em sessão filtrada como PAP."""
    grupo = criar_grupo(nome="1INFO")
    aluno_regular = criar_estudante(prontuario="IQ3001001", nome="Aluno Regular", grupos=[grupo])
    aluno_regular.categoria = "REGULAR"
    facade.repo_estudante.obter_sessao().commit()

    id_sessao = facade.iniciar_nova_sessao({
        "refeicao": "lanche",
        "periodo": "Tarde",
        "data": "2026-11-09",
        "hora": "15:00",
        "item_servido": "Suco",
        "grupos": ["1INFO"],
    })
    assert facade.id_sessao_ativa == id_sessao

    # Ativa filtro de categoria PAP
    facade.definir_filtro_categoria_sessao("PAP")
    assert facade.filtro_categoria_sessao == "PAP"

    # Tenta registrar consumo do aluno regular
    res = facade.registrar_consumo("IQ3001001")
    assert res["autorizado"] is False
    assert "não permitido para sessão filtrada" in res["motivo"].lower()

    # Com pular_grupos=True (bypass manual do operador), autorização deve ser concedida
    res_bypass = facade.registrar_consumo("IQ3001001", pular_grupos=True)
    assert res_bypass["autorizado"] is True


def test_consumo_autorizado_quando_categoria_compativel(facade: FachadaRegistro, criar_grupo, criar_estudante):
    """Garante que aluno PAP consome normalmente em sessão filtrada como PAP."""
    grupo = criar_grupo(nome="2MEC")
    aluno_pap = criar_estudante(prontuario="IQ3002002", nome="Aluno PAP", grupos=[grupo])
    aluno_pap.categoria = "PAP"
    facade.repo_estudante.obter_sessao().commit()

    facade.iniciar_nova_sessao({
        "refeicao": "lanche",
        "periodo": "Manhã",
        "data": "2026-11-09",
        "hora": "09:30",
        "item_servido": "Fruta",
        "grupos": ["2MEC"],
    })
    facade.definir_filtro_categoria_sessao("PAP")

    res = facade.registrar_consumo("IQ3002002")
    assert res["autorizado"] is True
    assert res["categoria"] == "PAP"


def test_consumo_sem_filtro_categoria_permite_ambos(facade: FachadaRegistro, criar_grupo, criar_estudante):
    """Garante que sem filtro ativo tanto REGULAR quanto PAP são atendidos."""
    grupo = criar_grupo(nome="3ELT")
    e1 = criar_estudante(prontuario="IQ3003001", nome="Aluno 1", grupos=[grupo])
    e1.categoria = "REGULAR"
    e2 = criar_estudante(prontuario="IQ3003002", nome="Aluno 2", grupos=[grupo])
    e2.categoria = "PAP"
    facade.repo_estudante.obter_sessao().commit()

    facade.iniciar_nova_sessao({
        "refeicao": "lanche",
        "periodo": "Manhã",
        "data": "2026-11-09",
        "hora": "09:30",
        "item_servido": "Biscoito",
        "grupos": ["3ELT"],
    })
    facade.definir_filtro_categoria_sessao(None)
    assert facade.filtro_categoria_sessao is None

    res1 = facade.registrar_consumo("IQ3003001")
    assert res1["autorizado"] is True

    res2 = facade.registrar_consumo("IQ3003002")
    assert res2["autorizado"] is True

