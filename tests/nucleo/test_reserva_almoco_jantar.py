"""
Testes para atribuição independente de Almoço e/ou Jantar em Reservas,
validação de sessão/consumo e merge em importações.
"""

from pathlib import Path

import pytest

from registro.nucleo.exceptions import ErroImportacaoDados
from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.importar.service import ServicoImportacao
from registro.nucleo.importar.strategies import CarregarCSVComCabecalho
from registro.nucleo.importers_service import importar_reservas_csv
from registro.nucleo.repository import RepositorioEstudante, RepositorioReserva


def test_crud_reserva_turnos_e_validacao(
    facade: FachadaRegistro, criar_grupo, criar_estudante
):
    grupo = criar_grupo(nome="3º A - MEC")
    est = criar_estudante(prontuario="IQ3088001", nome="Ana Turnos", grupos=[grupo])
    data = "12/11/2026"

    # Padrão: almoco=True, jantar=False
    r1 = facade.criar_reserva(est.prontuario, {"data": data, "prato": "Tradicional"})
    assert r1["almoco"] is True
    assert r1["jantar"] is False
    assert r1["turnos_str"] == "Almoço"

    # Atualizar para ambos
    assert facade.atualizar_reserva(r1["id"], {"almoco": True, "jantar": True}) is True
    listadas = facade.listar_reservas({"data": data})
    assert len(listadas) == 1
    assert listadas[0]["almoco"] is True
    assert listadas[0]["jantar"] is True
    assert listadas[0]["turnos_str"] == "Almoço e Jantar"

    # Rejeitar ambos False na atualização e na criação
    with pytest.raises(ValueError, match="Almoço ou Jantar"):
        facade.atualizar_reserva(r1["id"], {"almoco": False, "jantar": False})

    with pytest.raises(ValueError, match="Almoço ou Jantar"):
        facade.criar_reserva(
            est.prontuario,
            {"data": "13/11/2026", "prato": "Tradicional", "almoco": False, "jantar": False},
        )


def test_consumo_almoco_e_jantar_independentes_mesma_reserva(
    facade: FachadaRegistro, criar_grupo, criar_estudante, criar_sessao, criar_reserva
):
    grupo = criar_grupo(nome="2º A - MAC")
    est_ambos = criar_estudante(prontuario="IQ3088010", nome="Aluno Ambos", grupos=[grupo])
    est_so_almoco = criar_estudante(prontuario="IQ3088011", nome="Aluno Só Almoço", grupos=[grupo])
    est_so_jantar = criar_estudante(prontuario="IQ3088012", nome="Aluno Só Jantar", grupos=[grupo])

    data_br = "12/11/2026"
    res_ambos = criar_reserva(
        estudante=est_ambos, data=data_br, prato="Vegetariano", almoco=True, jantar=True
    )
    criar_reserva(
        estudante=est_so_almoco, data=data_br, prato="Tradicional", almoco=True, jantar=False
    )
    criar_reserva(
        estudante=est_so_jantar, data=data_br, prato="Tradicional", almoco=False, jantar=True
    )

    sessao_almoco = criar_sessao(
        refeicao="almoço", data=data_br, hora="12:00", periodo="Integral", grupos=[grupo]
    )
    sessao_jantar = criar_sessao(
        refeicao="jantar", data=data_br, hora="19:00", periodo="Noturno", grupos=[grupo]
    )

    # 1. Sessão de Almoço
    facade.id_sessao_ativa = sessao_almoco.id
    elegiveis_alm = {e["pront"] for e in facade.obter_estudantes_para_sessao(consumido=False)}
    assert elegiveis_alm == {"IQ3088010", "IQ3088011"}

    assert facade.registrar_consumo_com_reserva("IQ3088010")["autorizado"] is True
    assert facade.registrar_consumo_com_reserva("IQ3088011")["autorizado"] is True
    res_negado_alm = facade.registrar_consumo_com_reserva("IQ3088012")
    assert res_negado_alm["autorizado"] is False

    # Bloqueia segundo almoço na mesma data mesmo com reserva para jantar também
    res_dup_alm = facade.registrar_consumo_com_reserva("IQ3088010")
    assert res_dup_alm["autorizado"] is False

    # 2. Sessão de Jantar no mesmo dia usando a MESMA reserva de est_ambos
    facade.id_sessao_ativa = sessao_jantar.id
    elegiveis_jan = {e["pront"] for e in facade.obter_estudantes_para_sessao(consumido=False)}
    assert elegiveis_jan == {"IQ3088010", "IQ3088012"}

    reg_ambos_jan = facade.registrar_consumo_com_reserva("IQ3088010")
    assert reg_ambos_jan["autorizado"] is True
    assert reg_ambos_jan["prato"] == "Vegetariano"

    assert facade.registrar_consumo_com_reserva("IQ3088012")["autorizado"] is True
    assert facade.registrar_consumo_com_reserva("IQ3088011")["autorizado"] is False

    # Confirma 2 consumos ativos vinculados à mesma reserva
    consumos_res = [c for c in res_ambos.consumos if c.ativo]
    assert len(consumos_res) == 2


def test_iniciar_nova_sessao_exige_reserva_do_turno(
    facade: FachadaRegistro, criar_grupo, criar_estudante, criar_reserva
):
    grupo = criar_grupo(nome="1º A - MEC")
    est = criar_estudante(prontuario="IQ3088020", nome="Aluno Turno", grupos=[grupo])
    criar_reserva(estudante=est, data="14/11/2026", almoco=True, jantar=False)

    # Sem reserva de jantar para 14/11/2026 -> bloqueado
    id_jan = facade.iniciar_nova_sessao(
        {
            "refeicao": "jantar",
            "periodo": "Noturno",
            "data": "2026-11-14",
            "hora": "19:00",
            "grupos": ["1º A - MEC"],
        }
    )
    assert id_jan is None

    # Com reserva de almoço -> permitido
    id_alm = facade.iniciar_nova_sessao(
        {
            "refeicao": "almoço",
            "periodo": "Integral",
            "data": "2026-11-14",
            "hora": "12:00",
            "grupos": ["1º A - MEC"],
        }
    )
    assert id_alm is not None


def test_importar_reservas_csv_merge_almoco_e_jantar(db_session, tmp_path: Path, criar_estudante):
    repo_est = RepositorioEstudante(db_session)
    repo_res = RepositorioReserva(db_session)
    e1 = criar_estudante(prontuario="IQ3088030", nome="Aluno Merge")
    e2 = criar_estudante(prontuario="IQ3088031", nome="Aluno Turno")

    # 1º CSV: Almoço para e1 e Jantar para e2 (duas linhas para e1 com Almoço e Jantar no mesmo CSV)
    csv1 = tmp_path / "lote1.csv"
    csv1.write_text(
        "prontuário,data,refeição,turno\n"
        "IQ3088030,15/11/2026,Tradicional,Almoço\n"
        "IQ3088031,15/11/2026,Vegano,Jantar\n",
        encoding="utf-8",
    )
    qtd1 = importar_reservas_csv(repo_est, repo_res, csv1)
    assert qtd1 == 2

    res_e1 = repo_res.ler_filtrado(estudante_id=e1.id, data="15/11/2026")[0]
    res_e2 = repo_res.ler_filtrado(estudante_id=e2.id, data="15/11/2026")[0]
    assert (res_e1.almoco, res_e1.jantar) == (True, False)
    assert (res_e2.almoco, res_e2.jantar) == (False, True)

    # 2º CSV: Importa Jantar para e1 (deve fazer OR-merge mantendo almoco=True)
    csv2 = tmp_path / "lote2.csv"
    csv2.write_text(
        "prontuário,data,refeição,almoço,jantar\n"
        "IQ3088030,15/11/2026,Tradicional,Não,Sim\n",
        encoding="utf-8",
    )
    qtd2 = importar_reservas_csv(repo_est, repo_res, csv2)
    assert qtd2 == 1

    db_session.refresh(res_e1)
    assert (res_e1.almoco, res_e1.jantar) == (True, True)


def test_servico_importacao_defaults_e_override_por_coluna(
    facade: FachadaRegistro, tmp_path: Path, criar_estudante
):
    criar_estudante(prontuario="IQ3088040", nome="Aluno Default")
    criar_estudante(prontuario="IQ3088041", nome="Aluno Coluna")

    csv_path = tmp_path / "imp_turnos.csv"
    csv_path.write_text(
        "Prontuário,Nome,Data,Refeição,Turno\n"
        "IQ3088040,Aluno Default,16/11/2026,Tradicional,\n"
        "IQ3088041,Aluno Coluna,16/11/2026,Vegetariano,Ambos\n",
        encoding="utf-8",
    )

    servico = ServicoImportacao(facade)
    analise = servico.preparar_importacao(CarregarCSVComCabecalho(), str(csv_path))
    itens = analise["itens_revisao"]

    # Se ambos defaults forem False e houver linha sem turno -> erro explícito
    with pytest.raises(ErroImportacaoDados, match="Almoço ou Jantar"):
        servico.simular_importacao(
            itens, valores_padrao={"almoco": False, "jantar": False}
        )

    # Default Jantar (almoco=False, jantar=True): linha sem coluna usa default; linha com "Ambos" prevalece
    sim = servico.simular_importacao(
        itens, valores_padrao={"almoco": False, "jantar": True}
    )
    mapa_sim = {r["prontuario"]: r for r in sim["reservas"]}
    assert mapa_sim["IQ3088040"]["turnos_str"] == "Jantar"
    assert mapa_sim["IQ3088041"]["turnos_str"] == "Almoço e Jantar"

    res = servico.finalizar_importacao(
        itens, valores_padrao={"almoco": False, "jantar": True}
    )
    assert res["reservas_criadas"] == 2

