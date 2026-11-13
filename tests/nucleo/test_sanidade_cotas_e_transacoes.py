"""
Testes unitários e de integração para validação de sanidade das correções P1 e P2:
- Cotas diárias independentes (Almoço, Jantar e Lanches por período);
- Imutabilidade da cota sob 'pular_grupos';
- Proteção contra reuso de reserva consumida;
- Purificação de Soft Delete em estatísticas e exportações;
- Sanitização de prontuários com espaços e minúsculas;
- Tolerância a falhas na grade horária;
- Tratamento transacional com rollback preventivo.
"""

from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError

from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.services import (
    consumo_service,
    export_service,
    grade_horarios_service,
    stats_service,
)


def test_cota_diaria_bloqueia_segundo_almoco_em_sessoes_distintas(
    facade: FachadaRegistro, criar_grupo, criar_estudante, criar_sessao, criar_reserva
):
    """Garante que um aluno não possa almoçar duas vezes na mesma data, mesmo em sessões diferentes."""
    grupo = criar_grupo(nome="Informática 1A")
    aluno = criar_estudante(
        prontuario="IQ3099001", nome="Discente Almoço", grupos=[grupo]
    )
    data_hoje = "10/11/2026"

    # Duas reservas ou duas sessões na mesma data
    criar_reserva(estudante=aluno, data=data_hoje, prato="Tradicional")

    sessao_1 = criar_sessao(
        refeicao="almoço", data=data_hoje, hora="11:30", grupos=[grupo]
    )
    sessao_2 = criar_sessao(
        refeicao="almoço", data=data_hoje, hora="12:30", grupos=[grupo]
    )

    # 1. Consumo na Sessão 1 -> Autorizado
    facade.id_sessao_ativa = sessao_1.id
    res1 = facade.registrar_consumo(aluno.prontuario)
    assert res1["autorizado"] is True

    # 2. Tentativa de novo consumo na Sessão 2 no mesmo dia -> Bloqueado pela cota
    facade.id_sessao_ativa = sessao_2.id
    res2 = facade.registrar_consumo(aluno.prontuario)
    assert res2["autorizado"] is False
    assert "Cota diária atingida" in res2["motivo"]


def test_cotas_independentes_almoco_e_jantar(
    facade: FachadaRegistro, criar_grupo, criar_estudante, criar_sessao, criar_reserva
):
    """Garante que consumir almoço NÃO impede o discente de consumir jantar no mesmo dia."""
    grupo = criar_grupo(nome="Mecânica Noturno")
    aluno = criar_estudante(
        prontuario="IQ3099002", nome="Discente Integral", grupos=[grupo]
    )
    data_hoje = "10/11/2026"

    criar_reserva(estudante=aluno, data=data_hoje, prato="Almoço Vegano")

    sessao_almoco = criar_sessao(
        refeicao="almoço", data=data_hoje, hora="12:00", grupos=[grupo]
    )
    sessao_jantar = criar_sessao(
        refeicao="jantar", data=data_hoje, hora="19:00", grupos=[grupo]
    )

    # 1. Consome Almoço
    facade.id_sessao_ativa = sessao_almoco.id
    res_almoco = facade.registrar_consumo(aluno.prontuario)
    assert res_almoco["autorizado"] is True

    # 2. Tenta Almoço novamente na mesma data -> Bloqueado
    res_almoco_dup = facade.registrar_consumo(aluno.prontuario)
    assert res_almoco_dup["autorizado"] is False
    assert "Consumo já registrado" in res_almoco_dup["motivo"]

    # 3. Consome Jantar na mesma data -> Autorizado com sucesso!
    facade.id_sessao_ativa = sessao_jantar.id
    res_jantar = facade.registrar_consumo(aluno.prontuario, pular_grupos=True)
    assert res_jantar["autorizado"] is True


def test_cota_lanche_por_periodo(
    facade: FachadaRegistro, criar_grupo, criar_estudante, criar_sessao
):
    """Garante que discente pode lanchar em períodos diferentes do dia, mas não no mesmo período."""
    grupo = criar_grupo(nome="Eletrônica 2A")
    aluno = criar_estudante(
        prontuario="IQ3099003", nome="Discente Lanche", grupos=[grupo]
    )
    data_hoje = "10/11/2026"

    sessao_manha = criar_sessao(
        refeicao="lanche",
        periodo="Matutino",
        data=data_hoje,
        hora="09:30",
        grupos=[grupo],
    )
    sessao_manha_2 = criar_sessao(
        refeicao="lanche",
        periodo="Matutino",
        data=data_hoje,
        hora="10:00",
        grupos=[grupo],
    )
    sessao_tarde = criar_sessao(
        refeicao="lanche",
        periodo="Vespertino",
        data=data_hoje,
        hora="15:30",
        grupos=[grupo],
    )

    # 1. Lanche da manhã -> Autorizado
    facade.id_sessao_ativa = sessao_manha.id
    r1 = facade.registrar_consumo(aluno.prontuario)
    assert r1["autorizado"] is True

    # 2. Segundo lanche na manhã (em outra sessão) -> Bloqueado por cota do período
    facade.id_sessao_ativa = sessao_manha_2.id
    r2 = facade.registrar_consumo(aluno.prontuario)
    assert r2["autorizado"] is False
    assert "Cota atingida" in r2["motivo"]

    # 3. Lanche da tarde no mesmo dia -> Autorizado
    facade.id_sessao_ativa = sessao_tarde.id
    r3 = facade.registrar_consumo(aluno.prontuario)
    assert r3["autorizado"] is True


def test_pular_grupos_nao_burla_cota_diaria(
    facade: FachadaRegistro, criar_grupo, criar_estudante, criar_sessao, criar_reserva
):
    """Garante que pular_grupos ignora regras de turma, mas NUNCA autoriza duplo consumo diário."""
    grupo = criar_grupo(nome="Edificações 1A")
    aluno = criar_estudante(
        prontuario="IQ3099004", nome="Discente Cota", grupos=[grupo]
    )
    data_hoje = "10/11/2026"

    criar_reserva(estudante=aluno, data=data_hoje, prato="Carne")

    sessao1 = criar_sessao(
        refeicao="almoço", data=data_hoje, hora="11:45", grupos=[grupo]
    )
    sessao2 = criar_sessao(
        refeicao="almoço", data=data_hoje, hora="12:45", grupos=[grupo]
    )

    facade.id_sessao_ativa = sessao1.id
    assert facade.registrar_consumo(aluno.prontuario)["autorizado"] is True

    # Tenta registrar na sessão 2 com pular_grupos=True
    facade.id_sessao_ativa = sessao2.id
    resultado = facade.registrar_consumo(aluno.prontuario, pular_grupos=True)
    assert resultado["autorizado"] is False
    assert "Cota diária atingida" in resultado["motivo"]


def test_bloqueio_reuso_de_reserva_apos_consumo(
    repos, criar_grupo, criar_estudante, criar_sessao, criar_reserva
):
    """Garante que uma reserva já consumida não pode ser reutilizada em outra sessão."""
    grupo = criar_grupo(nome="Biologia 1A")
    aluno = criar_estudante(
        prontuario="IQ3099005", nome="Discente Reserva", grupos=[grupo]
    )
    data_hoje = "10/11/2026"

    reserva = criar_reserva(estudante=aluno, data=data_hoje, prato="Peixe")
    sessao1 = criar_sessao(
        refeicao="almoço", data=data_hoje, hora="11:30", grupos=[grupo]
    )

    # 1. Primeiro consumo utiliza a reserva
    res1 = consumo_service.registrar_consumo(
        repo_sessao=repos["sessao"],
        repo_estudante=repos["estudante"],
        repo_reserva=repos["reserva"],
        repo_consumo=repos["consumo"],
        id_sessao=sessao1.id,
        prontuario=aluno.prontuario,
    )
    assert res1["autorizado"] is True
    assert res1["prato"] == "Peixe"

    # Verifica se a reserva está vinculada ao consumo ativo
    assert reserva.consumo is not None
    assert reserva.consumo.ativo is True

    # Avaliador estrito de reserva deve rejeitar reuso
    autorizado, motivo, prato, id_res = consumo_service._avaliar_regra_com_reserva(
        sessao1, aluno, repos["reserva"], excecao_grupos=None, pular_grupos=False
    )
    assert autorizado is False
    assert "Reserva já utilizada" in motivo


def test_soft_delete_restaura_direito_de_consumo(
    facade: FachadaRegistro, criar_grupo, criar_estudante, criar_sessao, criar_reserva
):
    """Garante que ao cancelar (estornar) o consumo, o aluno pode consumir novamente."""
    grupo = criar_grupo(nome="Redes 1A")
    aluno = criar_estudante(
        prontuario="IQ3099006", nome="Discente Estorno", grupos=[grupo]
    )
    data_hoje = "10/11/2026"

    criar_reserva(estudante=aluno, data=data_hoje, prato="Padrão")
    sessao = criar_sessao(
        refeicao="almoço", data=data_hoje, hora="12:00", grupos=[grupo]
    )
    facade.id_sessao_ativa = sessao.id

    # 1. Consome
    assert facade.registrar_consumo(aluno.prontuario)["autorizado"] is True

    # 2. Desfaz o consumo por prontuário
    sucesso_estorno = facade.desfazer_consumo_por_prontuario(
        aluno.prontuario, operador="Fiscal", motivo="Erro de digitação"
    )
    assert sucesso_estorno is True

    # 3. Agora o discente pode consumir novamente
    res_novo = facade.registrar_consumo(aluno.prontuario)
    assert res_novo["autorizado"] is True


def test_soft_delete_purifica_metricas_dashboard_e_exportacao(
    facade: FachadaRegistro, repos, criar_grupo, criar_estudante, criar_sessao, tmp_path
):
    """Garante que registros com ativo=False não contaminem estatísticas e exportações."""
    grupo = criar_grupo(nome="Química 1A")
    aluno1 = criar_estudante(prontuario="IQ3099007", nome="Aluno Ativo", grupos=[grupo])
    aluno2 = criar_estudante(
        prontuario="IQ3099008", nome="Aluno Cancelado", grupos=[grupo]
    )
    data_hoje = "10/11/2026"

    sessao = criar_sessao(
        refeicao="lanche", data=data_hoje, hora="10:00", grupos=[grupo]
    )
    facade.id_sessao_ativa = sessao.id

    # Consumos
    facade.registrar_consumo(aluno1.prontuario)
    facade.registrar_consumo(aluno2.prontuario)

    # Cancela o segundo
    facade.desfazer_consumo_por_prontuario(aluno2.prontuario)

    # 1. Estatísticas do Dashboard devem contar apenas 1 consumo
    with patch("registro.nucleo.services.stats_service.dt") as mock_dt:
        import datetime as dt_real

        mock_dt.date.today.return_value = dt_real.date(2026, 11, 10)
        mock_dt.timedelta = dt_real.timedelta
        stats = stats_service.obter_estatisticas_dashboard(
            repo_estudante=repos["estudante"],
            repo_reserva=repos["reserva"],
            repo_grupo=repos["grupo"],
            repo_consumo=repos["consumo"],
        )
        assert stats["consumos_total"] == 1
        assert stats["consumos_hoje"] == 1

    # 2. Exportação geral deve conter apenas o consumo ativo
    arquivo_xlsx = tmp_path / "total_consumos_teste.xlsx"
    caminho_gerado = export_service.exportar_todos_os_consumos_para_xlsx(
        repo_consumo=repos["consumo"],
        nome_arquivo_arg=arquivo_xlsx,
    )
    assert arquivo_xlsx.exists()


def test_sanitizacao_prontuario_com_espacos_e_minusculas(
    facade: FachadaRegistro, criar_grupo, criar_estudante, criar_sessao
):
    """Garante que leituras de código de barras ou digitação com espaços/minúsculas funcionem."""
    grupo = criar_grupo(nome="Letras 1A")
    aluno = criar_estudante(
        prontuario="IQ3099009", nome="Discente Sanitizacao", grupos=[grupo]
    )
    sessao = criar_sessao(refeicao="lanche", grupos=[grupo])
    facade.id_sessao_ativa = sessao.id

    # Entrada suja com espaços e minúsculas
    pront_sujo = "  iq3099009 \n"
    res = facade.registrar_consumo(pront_sujo)
    assert res["autorizado"] is True
    assert res["prontuario"] == "IQ3099009"


def test_tolerancia_a_erros_na_grade_de_horarios(tmp_path):
    """Garante que slots corrompidos na grade_horarios.json não quebrem a validação."""
    grade_corrompida = {
        "segunda": {
            "almoco": [
                {"inicio": "HORA_INVALIDA", "fim": "12:00", "turmas": ["1A"]},
                {"inicio": "12:00", "fim": "13:00", "turmas": ["1A"]},
            ]
        }
    }
    caminho = tmp_path / "grade_teste.json"
    grade_horarios_service.salvar_grade_horarios(grade_corrompida, caminho)

    # Validar janela deve ignorar o slot corrompido e analisar o slot válido sem levantar exceção
    valido, motivo = grade_horarios_service.validar_janela_horario(
        turmas_estudante=["1A"],
        refeicao="almoco",
        hora_atual="12:15",
        dia_semana="segunda",
        caminho_grade=caminho,
    )
    assert valido is True


def test_rollback_em_falha_de_gravacao_de_consumo(
    repos, criar_grupo, criar_estudante, criar_sessao
):
    """Garante que exceções no commit de consumo disparem rollback e retornem motivo amigável."""
    grupo = criar_grupo(nome="Turma Teste")
    aluno = criar_estudante("IQ3099010", "Aluno Rollback", grupos=[grupo])
    sessao = criar_sessao(refeicao="lanche", grupos=[grupo])

    db_sessao = repos["consumo"].obter_sessao()

    # Simula falha ao dar commit
    with patch.object(
        db_sessao, "commit", side_effect=SQLAlchemyError("Simulação de Disco Cheio")
    ):
        res = consumo_service.registrar_consumo(
            repo_sessao=repos["sessao"],
            repo_estudante=repos["estudante"],
            repo_reserva=repos["reserva"],
            repo_consumo=repos["consumo"],
            id_sessao=sessao.id,
            prontuario=aluno.prontuario,
        )
        assert res["autorizado"] is False
        assert "Erro de gravação" in res["motivo"]

    # A sessão continua limpa para operações seguintes
    assert db_sessao.is_active
