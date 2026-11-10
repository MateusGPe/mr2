"""
Testes unitários para validação de categorias (PAP, ESP1, LIB0) como grupos no consumo.
"""

from registro.nucleo.facade import FachadaRegistro


def test_consumo_bloqueado_quando_categoria_incompativel(
    facade: FachadaRegistro, criar_grupo, criar_estudante
):
    """Aluno sem a categoria filtrada na sessão é bloqueado, salvo com pular_grupos=True."""
    turma = criar_grupo(nome="1INFO", tipo="turma")
    cat_pap = criar_grupo(nome="PAP", tipo="categoria")
    criar_estudante(prontuario="IQ3001001", nome="Aluno Sem PAP", grupos=[turma])

    id_sessao = facade.iniciar_nova_sessao({
        "refeicao": "lanche",
        "periodo": "Tarde",
        "data": "2026-11-09",
        "hora": "15:00",
        "item_servido": "Suco",
        "grupos": [cat_pap.nome],
    })
    assert facade.id_sessao_ativa == id_sessao

    # Aluno de 1INFO sem categoria PAP -> não autorizado em sessão só de PAP
    res = facade.registrar_consumo("IQ3001001")
    assert res["autorizado"] is False

    # Com pular_grupos=True (bypass manual do operador), autorização é concedida
    res_bypass = facade.registrar_consumo("IQ3001001", pular_grupos=True)
    assert res_bypass["autorizado"] is True


def test_consumo_autorizado_quando_categoria_compativel(
    facade: FachadaRegistro, criar_grupo, criar_estudante
):
    """Aluno vinculado à categoria PAP consome normalmente em sessão filtrada para PAP."""
    turma = criar_grupo(nome="2MEC", tipo="turma")
    cat_pap = criar_grupo(nome="PAP", tipo="categoria")
    criar_estudante(prontuario="IQ3002002", nome="Aluno PAP", grupos=[turma, cat_pap])

    facade.iniciar_nova_sessao({
        "refeicao": "lanche",
        "periodo": "Manhã",
        "data": "2026-11-09",
        "hora": "09:30",
        "item_servido": "Fruta",
        "grupos": ["PAP"],
    })

    res = facade.registrar_consumo("IQ3002002")
    assert res["autorizado"] is True
    assert res["turma"] == "2MEC"
    assert res["categoria"] == "PAP"


def test_consumo_sem_filtro_categoria_permite_ambos(
    facade: FachadaRegistro, criar_grupo, criar_estudante
):
    """Sessão filtrada para a turma permite alunos com e sem categorias."""
    turma = criar_grupo(nome="3ELT", tipo="turma")
    cat_pap = criar_grupo(nome="PAP", tipo="categoria")
    criar_estudante(prontuario="IQ3003001", nome="Aluno 1", grupos=[turma])
    criar_estudante(prontuario="IQ3003002", nome="Aluno 2", grupos=[turma, cat_pap])

    facade.iniciar_nova_sessao({
        "refeicao": "lanche",
        "periodo": "Manhã",
        "data": "2026-11-09",
        "hora": "09:30",
        "item_servido": "Biscoito",
        "grupos": ["3ELT"],
    })

    res1 = facade.registrar_consumo("IQ3003001")
    assert res1["autorizado"] is True
    assert res1["categoria"] == "-"

    res2 = facade.registrar_consumo("IQ3003002")
    assert res2["autorizado"] is True
    assert res2["categoria"] == "PAP"

