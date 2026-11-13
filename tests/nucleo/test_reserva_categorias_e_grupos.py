"""
Testes para separação de Turmas vs. Categorias em Grupo e vínculo pontual
de múltiplas Categorias em Reservas sem vincular ao Estudante.
"""

from pathlib import Path
from unittest.mock import patch

from registro.nucleo import constants, importers_service
from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.services import grade_horarios_service, sync_service


def test_reserva_com_categorias_pontuais_sem_vincular_estudante(
    facade: FachadaRegistro, criar_grupo, criar_estudante, tmp_path: Path, monkeypatch
):
    """Categorias vinculadas à reserva valem para o dia inteiro (Almoço e Lanche) sem alterar o cadastro do aluno."""
    caminho_grade = tmp_path / "grade.json"
    monkeypatch.setattr(grade_horarios_service, "CAMINHO_GRADE_HORARIOS", caminho_grade)
    monkeypatch.setattr(constants, "CAMINHO_GRADE_HORARIOS", caminho_grade)
    monkeypatch.setattr(
        grade_horarios_service, "obter_dia_semana_atual", lambda: "segunda"
    )

    grade = {
        "segunda": {
            "almoco": [
                {
                    "inicio": "12:00",
                    "fim": "13:00",
                    "turmas": ["*"],
                    "categorias": ["ESP1"],
                }
            ],
            "lanche": [],
            "jantar": [],
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho_grade)

    turma_2a = criar_grupo(nome="2º A - MAC", tipo="turma")
    est = criar_estudante(
        prontuario="IQ3050001", nome="João Optativa", grupos=[turma_2a]
    )

    data_evento = "10/11/2026"
    res_criada = facade.criar_reserva(
        "IQ3050001",
        {
            "data": data_evento,
            "prato": "Tradicional",
            "cancelada": False,
            "categorias": ["ESP1", "LIB0"],
        },
    )
    assert res_criada["categorias"] == ["ESP1", "LIB0"]

    # 1. Estudante continua tendo apenas sua turma real (sem ESP1/LIB0 permanentes)
    est_db = facade.repo_estudante.por_prontuarios_com_grupos({"IQ3050001"})[0]
    assert est_db.turmas_nomes == ["2º A - MAC"]
    assert est_db.categorias_nomes == []

    # 2. Filtro de reservas por categoria encontra a reserva
    encontradas = facade.listar_reservas({"data": data_evento, "grupos": ["ESP1"]})
    assert len(encontradas) == 1
    assert encontradas[0]["categorias"] == ["ESP1", "LIB0"]

    # 3. Sessão de Almoço filtrada apenas para ESP1 autoriza dentro do horário de ESP1
    cat_esp1 = facade.repo_grupo.por_nome("ESP1")
    assert cat_esp1 is not None and cat_esp1.eh_categoria is True

    id_almoco = facade.iniciar_nova_sessao(
        {
            "refeicao": "almoço",
            "periodo": "Integral",
            "data": "2026-11-10",
            "hora": "12:00",
            "grupos": ["ESP1"],
        }
    )
    assert id_almoco is not None

    with (
        patch("registro.nucleo.services.consumo_service.datetime") as mock_dt,
        patch(
            "registro.nucleo.services.grade_horarios_service.datetime"
        ) as mock_dt_grade,
    ):
        mock_dt.now.return_value.strftime.side_effect = lambda fmt: (
            "12:15" if "%H:%M" in fmt else "12:15:00"
        )
        mock_dt_grade.now.return_value.strftime.side_effect = lambda fmt: (
            "12:15" if "%H:%M" in fmt else "12:15:00"
        )
        mock_dt_grade.now.return_value.weekday.return_value = 0

        reg_almoco = facade.registrar_consumo_com_reserva("IQ3050001")
        assert reg_almoco["autorizado"] is True
        assert reg_almoco["turma"] == "2º A - MAC"
        assert reg_almoco["categoria"] == "ESP1, LIB0"

    # 4. Na mesma data, sessão de Lanche filtrada para LIB0 também reconhece a categoria da reserva
    id_lanche_mesmo_dia = facade.iniciar_nova_sessao(
        {
            "refeicao": "lanche",
            "periodo": "Tarde",
            "data": "2026-11-10",
            "hora": "15:30",
            "item_servido": "Fruta",
            "grupos": ["LIB0"],
        }
    )
    assert id_lanche_mesmo_dia is not None
    elegiveis_lanche = facade.obter_estudantes_para_sessao(consumido=False)
    assert any(e["pront"] == "IQ3050001" for e in elegiveis_lanche)

    reg_lanche = facade.registrar_consumo("IQ3050001")
    assert reg_lanche["autorizado"] is True
    assert reg_lanche["categoria"] == "ESP1, LIB0"

    # 5. Exportação para Sheets (_montar_linhas_para_sessao) e XLSX inclui categorias da reserva
    sessao_obj = facade.repo_sessao.ler_um(id_lanche_mesmo_dia)
    assert sessao_obj is not None
    consumos = facade.repo_consumo.ler_filtrado(sessao_id=id_lanche_mesmo_dia)
    mapa_res = sync_service._carregar_reservas_ativas_sessao(
        facade.repo_consumo, sessao_obj.data
    )
    linhas = sync_service._montar_linhas_para_sessao(
        sessao_obj, consumos, mapa_reservas_dia=mapa_res
    )
    assert linhas[0][3] == "2º A - MAC"
    assert linhas[0][6] == "ESP1, LIB0"

    xlsx_path = tmp_path / "sessao.xlsx"
    facade.exportar_sessao_para_xlsx(xlsx_path)
    assert xlsx_path.exists()

    # 6. Em outra data sem reserva vinculada a LIB0, estudante não possui essa categoria
    id_outro_dia = facade.iniciar_nova_sessao(
        {
            "refeicao": "lanche",
            "periodo": "Tarde",
            "data": "2026-11-11",
            "hora": "15:30",
            "item_servido": "Bolo",
            "grupos": ["LIB0"],
        }
    )
    assert id_outro_dia is not None
    reg_outro_dia = facade.registrar_consumo("IQ3050001")
    assert reg_outro_dia["autorizado"] is False


def test_reserva_cancelada_nao_concede_categoria_pontual(
    facade: FachadaRegistro, criar_grupo, criar_estudante
):
    """Se a reserva pontual for cancelada, sua categoria não autoriza o aluno na data."""
    turma = criar_grupo(nome="1º A - MEC", tipo="turma")
    criar_estudante(prontuario="IQ3050002", nome="Maria Evento", grupos=[turma])

    res = facade.criar_reserva(
        "IQ3050002",
        {
            "data": "12/11/2026",
            "prato": "Vegetariano",
            "cancelada": False,
            "categorias": ["EVENTO_ROBOTICA"],
        },
    )
    facade.cancelar_reserva(res["id"])

    facade.iniciar_nova_sessao(
        {
            "refeicao": "lanche",
            "periodo": "Tarde",
            "data": "2026-11-12",
            "hora": "15:30",
            "item_servido": "Suco",
            "grupos": ["EVENTO_ROBOTICA"],
        }
    )
    tentativa = facade.registrar_consumo("IQ3050002")
    assert tentativa["autorizado"] is False


def test_importar_reservas_csv_vincula_categorias_somente_na_reserva(
    facade: FachadaRegistro, tmp_path: Path, criar_grupo, criar_estudante
):
    """Importação de reservas CSV aceita coluna Categoria sem vincular o estudante."""
    turma = criar_grupo(nome="3º A - MAC", tipo="turma")
    criar_estudante(prontuario="IQ3050003", nome="Pedro CSV", grupos=[turma])

    csv_reservas = tmp_path / "reservas.csv"
    csv_reservas.write_text(
        'DATA,MATRÍCULA,REFEIÇÃO,Categoria\n13/11/2026,IQ3050003,Tradicional,"ESP1, PAP"\n',
        encoding="utf-8",
    )

    qtd = importers_service.importar_reservas_csv(
        facade.repo_estudante,
        facade.repo_reserva,
        csv_reservas,
        repo_grupo=facade.repo_grupo,
    )
    assert qtd == 1

    est = facade.repo_estudante.por_prontuarios_com_grupos({"IQ3050003"})[0]
    assert est.categorias_nomes == []

    reservas = facade.listar_reservas({"data": "13/11/2026"})
    assert len(reservas) == 1
    assert reservas[0]["categorias"] == ["ESP1", "PAP"]


def test_grade_horarios_regra_ou_com_coringa(tmp_path: Path):
    """Valida regra OU entre turmas e categorias e comportamento do coringa '*'."""
    caminho = tmp_path / "grade_ou.json"
    grade = {
        "segunda": {
            "almoco": [
                # Caso 1: apenas turma específica, categoria '*' -> só 1º A
                {
                    "inicio": "11:30",
                    "fim": "12:00",
                    "turmas": ["1º A"],
                    "categorias": ["*"],
                },
                # Caso 2: turma específica E categoria específica -> regra OU (1º B OU ESP1)
                {
                    "inicio": "12:00",
                    "fim": "12:30",
                    "turmas": ["1º B"],
                    "categorias": ["ESP1"],
                },
                # Caso 3: turma '*', categoria específica -> só quem tem LIB0
                {
                    "inicio": "12:30",
                    "fim": "13:00",
                    "turmas": ["*"],
                    "categorias": ["LIB0"],
                },
            ]
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho)

    # Caso 1: 1º A passa, 2º A bloqueia
    assert (
        grade_horarios_service.validar_janela_horario(
            ["1º A"],
            "almoço",
            hora_atual="11:45",
            dia_semana="segunda",
            categorias_estudante=[],
            caminho_grade=caminho,
        )[0]
        is True
    )
    assert (
        grade_horarios_service.validar_janela_horario(
            ["2º A"],
            "almoço",
            hora_atual="11:45",
            dia_semana="segunda",
            categorias_estudante=["ESP1"],
            caminho_grade=caminho,
        )[0]
        is False
    )

    # Caso 2 (OU): 1º B sem categoria passa; 2º A com ESP1 passa; 2º A sem categoria bloqueia
    assert (
        grade_horarios_service.validar_janela_horario(
            ["1º B"],
            "almoço",
            hora_atual="12:15",
            dia_semana="segunda",
            categorias_estudante=[],
            caminho_grade=caminho,
        )[0]
        is True
    )
    assert (
        grade_horarios_service.validar_janela_horario(
            ["2º A"],
            "almoço",
            hora_atual="12:15",
            dia_semana="segunda",
            categorias_estudante=["ESP1"],
            caminho_grade=caminho,
        )[0]
        is True
    )
    assert (
        grade_horarios_service.validar_janela_horario(
            ["2º A"],
            "almoço",
            hora_atual="12:15",
            dia_semana="segunda",
            categorias_estudante=[],
            caminho_grade=caminho,
        )[0]
        is False
    )

    # Caso 3: qualquer turma com LIB0 passa, sem LIB0 bloqueia
    assert (
        grade_horarios_service.validar_janela_horario(
            ["3º C"],
            "almoço",
            hora_atual="12:45",
            dia_semana="segunda",
            categorias_estudante=["LIB0"],
            caminho_grade=caminho,
        )[0]
        is True
    )
    assert (
        grade_horarios_service.validar_janela_horario(
            ["1º A"],
            "almoço",
            hora_atual="12:45",
            dia_semana="segunda",
            categorias_estudante=[],
            caminho_grade=caminho,
        )[0]
        is False
    )
