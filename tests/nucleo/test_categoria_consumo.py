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

    id_sessao = facade.iniciar_nova_sessao(
        {
            "refeicao": "lanche",
            "periodo": "Tarde",
            "data": "2026-11-09",
            "hora": "15:00",
            "item_servido": "Suco",
            "grupos": [cat_pap.nome],
        }
    )
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

    facade.iniciar_nova_sessao(
        {
            "refeicao": "lanche",
            "periodo": "Manhã",
            "data": "2026-11-09",
            "hora": "09:30",
            "item_servido": "Fruta",
            "grupos": ["PAP"],
        }
    )

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

    facade.iniciar_nova_sessao(
        {
            "refeicao": "lanche",
            "periodo": "Manhã",
            "data": "2026-11-09",
            "hora": "09:30",
            "item_servido": "Biscoito",
            "grupos": ["3ELT"],
        }
    )

    res1 = facade.registrar_consumo("IQ3003001")
    assert res1["autorizado"] is True
    assert res1["categoria"] == "-"

    res2 = facade.registrar_consumo("IQ3003002")
    assert res2["autorizado"] is True
    assert res2["categoria"] == "PAP"


def test_categoria_arbitraria_almoco_com_excecao_respeita_grade_e_separa_jantar(
    facade: FachadaRegistro,
    criar_grupo,
    criar_estudante,
    criar_reserva,
    tmp_path,
    monkeypatch,
):
    """
    Categoria arbitrária (ex.: Evento Feira) com Exceção (#) no almoço libera sem reserva
    no horário da grade, respeita o horário e não confunde reserva de jantar com almoço.
    """
    from unittest.mock import patch

    from registro.nucleo import constants
    from registro.nucleo.services import grade_horarios_service

    caminho_grade = tmp_path / "grade_evento.json"
    monkeypatch.setattr(grade_horarios_service, "CAMINHO_GRADE_HORARIOS", caminho_grade)
    monkeypatch.setattr(constants, "CAMINHO_GRADE_HORARIOS", caminho_grade)
    grade_horarios_service.salvar_grade_horarios(
        {
            "segunda": {
                "almoco": [
                    {
                        "inicio": "11:30",
                        "fim": "12:00",
                        "turmas": ["*"],
                        "categorias": ["Evento Feira"],
                    },
                ]
            }
        },
        caminho_grade,
    )

    turma = criar_grupo(nome="1INFO", tipo="turma")
    cat_evento = criar_grupo(nome="Evento Feira", tipo="categoria")
    est_evento = criar_estudante(
        prontuario="IQ3004001", nome="Aluno Evento", grupos=[turma, cat_evento]
    )
    est_so_jantar = criar_estudante(
        prontuario="IQ3004002", nome="Aluno Só Jantar", grupos=[turma]
    )
    est_com_almoco = criar_estudante(
        prontuario="IQ3004003", nome="Aluno Com Almoço", grupos=[turma]
    )
    # Reserva apenas de jantar não libera almoço (e não abre sessão de almoço)
    criar_reserva(estudante=est_so_jantar, data="10/11/2026", almoco=False, jantar=True)
    assert (
        facade.iniciar_nova_sessao(
            {
                "refeicao": "almoço",
                "periodo": "Tarde",
                "data": "2026-11-10",
                "hora": "11:30",
                "grupos": ["1INFO"],
            }
        )
        is None
    )

    criar_reserva(
        estudante=est_com_almoco, data="10/11/2026", almoco=True, jantar=False
    )
    id_sessao = facade.iniciar_nova_sessao(
        {
            "refeicao": "almoço",
            "periodo": "Tarde",
            "data": "2026-11-10",
            "hora": "11:30",
            "grupos": ["1INFO"],
        }
    )
    assert id_sessao is not None
    facade.definir_excecao_grupos({"evento feira"})  # também valida case-insensitive

    with patch("registro.nucleo.services.grade_horarios_service.datetime") as mock_dt_g:
        mock_dt_g.now.return_value.weekday.return_value = 0

        # Fora do horário da categoria -> bloqueado mesmo com Exceção (#)
        mock_dt_g.now.return_value.strftime.return_value = "12:15"
        r_fora = facade.registrar_consumo(est_evento.prontuario)
        assert r_fora["autorizado"] is False
        assert "11:30 às 12:00" in r_fora["motivo"]

        # Dentro do horário da categoria -> autorizado por exceção (grupo)
        mock_dt_g.now.return_value.strftime.return_value = "11:40"
        r_ok = facade.registrar_consumo(est_evento.prontuario)
        assert r_ok["autorizado"] is True
        assert r_ok["prato"] == "Sem Reserva (Grupo)"

        # Aluno sem categoria e com reserva apenas de jantar -> bloqueado no almoço
        r_jantar = facade.registrar_consumo(est_so_jantar.prontuario)
        assert r_jantar["autorizado"] is False
