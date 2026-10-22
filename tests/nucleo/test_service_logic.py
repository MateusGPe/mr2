"""
Testes unitários para as regras de negócio em registro.nucleo.service_logic.
"""

import pytest
from sqlalchemy.orm import Session

from registro.nucleo import service_logic
from registro.nucleo.exceptions import ErroSessao
from registro.nucleo.repository import (
    RepositorioConsumo,
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
    RepositorioSessao,
)


def test_iniciar_sessao_lanche_sucesso(repos, criar_grupo):
    """Inicia sessão de lanche com grupos associados."""
    g1 = criar_grupo(nome="1º A - MEC")
    dados_sessao = {
        "refeicao": "lanche",
        "periodo": "Tarde",
        "data": "2026-10-21",
        "hora": "15:30",
        "item_servido": "Bolo de Cenoura",
        "grupos": ["1º A - MEC"],
    }

    id_sessao = service_logic.iniciar_nova_sessao(
        repos["sessao"], repos["grupo"], repos["reserva"], dados_sessao
    )

    assert id_sessao is not None
    sessao = service_logic.obter_detalhes_sessao(repos["sessao"], id_sessao)
    assert sessao.refeicao == "lanche"
    assert sessao.data == "21/10/2026"
    assert len(sessao.grupos) == 1
    assert sessao.grupos[0].nome == "1º A - MEC"


def test_iniciar_sessao_almoco_sem_reservas_retorna_none(repos, criar_grupo):
    """Sessão de almoço não deve iniciar se não houver reservas para a data."""
    dados_sessao = {
        "refeicao": "almoço",
        "periodo": "Almoço",
        "data": "2026-10-21",
        "hora": "12:00",
        "grupos": [],
    }

    id_sessao = service_logic.iniciar_nova_sessao(
        repos["sessao"], repos["grupo"], repos["reserva"], dados_sessao
    )
    assert id_sessao is None


def test_iniciar_sessao_almoco_com_reservas_sucesso(repos, criar_estudante, criar_reserva):
    """Sessão de almoço inicia com sucesso quando há reservas na data."""
    estudante = criar_estudante(prontuario="IQ3005001", nome="Aluno Almoço")
    criar_reserva(estudante=estudante, data="21/10/2026", prato="Feijoada")

    dados_sessao = {
        "refeicao": "almoço",
        "periodo": "Almoço",
        "data": "2026-10-21",
        "hora": "12:00",
        "grupos": [],
    }

    id_sessao = service_logic.iniciar_nova_sessao(
        repos["sessao"], repos["grupo"], repos["reserva"], dados_sessao
    )
    assert id_sessao is not None


def test_obter_detalhes_sessao_inexistente_lanca_erro(repos):
    """Verifica lançamento de ErroSessao ao buscar ID inválido."""
    with pytest.raises(ErroSessao):
        service_logic.obter_detalhes_sessao(repos["sessao"], 999999)


def test_registrar_consumo_lanche_estudante_autorizado(repos, criar_grupo, criar_estudante, criar_sessao):
    """Registra consumo com sucesso para estudante da turma da sessão."""
    grupo = criar_grupo(nome="2º A - MEC")
    estudante = criar_estudante(prontuario="IQ3005002", nome="Aluno Autorizado", grupos=[grupo])
    sessao = criar_sessao(refeicao="lanche", grupos=[grupo], item_servido="Fruta")

    resultado = service_logic.registrar_consumo(
        repos["sessao"],
        repos["estudante"],
        repos["reserva"],
        repos["consumo"],
        id_sessao=sessao.id,
        prontuario="IQ3005002",
    )

    assert resultado["autorizado"] is True
    assert resultado["aluno"] == "Aluno Autorizado"
    assert resultado["prato"] == "Fruta"

    # Tentativa de consumo duplicado deve ser bloqueada
    duplicado = service_logic.registrar_consumo(
        repos["sessao"],
        repos["estudante"],
        repos["reserva"],
        repos["consumo"],
        id_sessao=sessao.id,
        prontuario="IQ3005002",
    )
    assert duplicado["autorizado"] is False
    assert "já registrado" in duplicado["motivo"]


def test_registrar_consumo_estudante_nao_encontrado(repos, criar_sessao):
    """Retorna não autorizado se o prontuário não existir no banco."""
    sessao = criar_sessao()
    resultado = service_logic.registrar_consumo(
        repos["sessao"],
        repos["estudante"],
        repos["reserva"],
        repos["consumo"],
        id_sessao=sessao.id,
        prontuario="NAO_EXISTE",
    )
    assert resultado["autorizado"] is False
    assert "não encontrado" in resultado["motivo"]


def test_registrar_consumo_almoco_com_reserva_e_sem_reserva(
    repos, criar_grupo, criar_estudante, criar_sessao, criar_reserva
):
    """Verifica autorização de almoço com e sem reserva."""
    grupo = criar_grupo(nome="3º A - MAC")
    aluno_com_reserva = criar_estudante(prontuario="IQ3005003", nome="Com Reserva", grupos=[grupo])
    aluno_sem_reserva = criar_estudante(prontuario="IQ3005004", nome="Sem Reserva", grupos=[grupo])

    sessao = criar_sessao(refeicao="almoço", data="21/10/2026", grupos=[grupo])
    criar_reserva(estudante=aluno_com_reserva, data="21/10/2026", prato="Lasanha")

    # Aluno com reserva
    res_com = service_logic.registrar_consumo(
        repos["sessao"],
        repos["estudante"],
        repos["reserva"],
        repos["consumo"],
        id_sessao=sessao.id,
        prontuario="IQ3005003",
    )
    assert res_com["autorizado"] is True
    assert res_com["prato"] == "Lasanha"

    # Aluno sem reserva
    res_sem = service_logic.registrar_consumo(
        repos["sessao"],
        repos["estudante"],
        repos["reserva"],
        repos["consumo"],
        id_sessao=sessao.id,
        prontuario="IQ3005004",
    )
    assert res_sem["autorizado"] is False
    assert res_sem["motivo"] == "Acesso Negado"
    assert res_sem["prato"] == "Sem Reserva"


def test_deletar_e_atualizar_sessao(repos, criar_sessao):
    """Testa atualização e exclusão de sessão."""
    sessao = criar_sessao(item_servido="Pão")

    # Atualizar
    atualizada = service_logic.atualizar_sessao(
        repos["sessao"], sessao.id, {"item_servido": "Biscoito"}
    )
    assert atualizada.item_servido == "Biscoito"

    # Deletar
    service_logic.deletar_sessao(repos["sessao"], sessao.id)
    with pytest.raises(ErroSessao):
        service_logic.obter_detalhes_sessao(repos["sessao"], sessao.id)


def test_obter_estudantes_para_sessao_e_filtros(
    repos, criar_grupo, criar_estudante, criar_sessao, criar_consumo
):
    """Verifica lista de estudantes elegíveis e filtro por consumo realizado."""
    grupo = criar_grupo(nome="1º A - INFO")
    e1 = criar_estudante(prontuario="IQ3009101", nome="Aluno A", grupos=[grupo])
    e2 = criar_estudante(prontuario="IQ3009102", nome="Aluno B", grupos=[grupo])

    sessao = criar_sessao(refeicao="lanche", grupos=[grupo], item_servido="Maçã")
    criar_consumo(estudante=e1, sessao=sessao, hora_consumo="10:00:00")

    # Todos elegíveis
    todos = service_logic.obter_estudantes_para_sessao(
        repos["sessao"],
        repos["estudante"],
        repos["reserva"],
        repos["consumo"],
        repos["grupo"],
        id_sessao=sessao.id,
    )
    assert len(todos) == 2

    # Apenas consumidos
    consumidos = service_logic.obter_estudantes_para_sessao(
        repos["sessao"],
        repos["estudante"],
        repos["reserva"],
        repos["consumo"],
        repos["grupo"],
        id_sessao=sessao.id,
        consumido=True,
    )
    assert len(consumidos) == 1
    assert consumidos[0]["pront"] == "IQ3009101"


def test_desfazer_consumo_e_cancelamento_reserva(
    repos, criar_estudante, criar_sessao, criar_consumo, criar_reserva
):
    """Verifica desfazimento de consumo e cancelamento de reserva."""
    estudante = criar_estudante(prontuario="IQ3009201", nome="Aluno Desfazer")
    sessao = criar_sessao()
    consumo = criar_consumo(estudante=estudante, sessao=sessao)

    reserva = criar_reserva(estudante=estudante, data="21/10/2026", cancelada=False)
    service_logic.atualizar_cancelamento_reserva(
        repos["reserva"], reserva.id, cancelar=True
    )
    assert repos["reserva"].ler_um(reserva.id).cancelada is True

    # Desfazer consumo por prontuário
    desfeito = service_logic.desfazer_consumo_por_prontuario(
        repos["consumo"], "IQ3009201", sessao.id
    )
    assert desfeito is True
    assert len(repos["consumo"].ler_filtrado(sessao_id=sessao.id)) == 0


def test_listar_sessoes_e_grupos(repos, criar_grupo, criar_sessao):
    """Testa listagens simplificadas de sessões e grupos."""
    g = criar_grupo(nome="Grupo X")
    s = criar_sessao(refeicao="lanche", grupos=[g])

    grupos = service_logic.listar_todos_os_grupos(repos["grupo"])
    assert any(item["nome"] == "Grupo X" for item in grupos)

    sessoes = service_logic.listar_todas_sessoes(repos["sessao"])
    assert any(item["id"] == s.id for item in sessoes)


def test_deletar_e_atualizar_sessao_erros(repos):
    """Testa erros de sessão não encontrada ao deletar e atualizar."""
    with pytest.raises(ErroSessao, match="não encontrada para exclusão"):
        service_logic.deletar_sessao(repos["sessao"], 999999)

    with pytest.raises(ErroSessao, match="não encontrada para atualização"):
        service_logic.atualizar_sessao(repos["sessao"], 999999, {"item_servido": "Novo"})


def test_obter_estudantes_para_sessao_almoco_filtros(
    repos, criar_grupo, criar_estudante, criar_sessao, criar_reserva, criar_consumo
):
    """Testa obter_estudantes_para_sessao com refeição almoço, reservas e filtros consumido=False."""
    g_sessao = criar_grupo(nome="1º A - INFO")
    g_excecao = criar_grupo(nome="2º B - MEC")
    g_fora = criar_grupo(nome="3º C - ELE")

    e1 = criar_estudante(prontuario="IQ3009501", nome="Aluno Grupo Sessao", grupos=[g_sessao])
    e2 = criar_estudante(prontuario="IQ3009502", nome="Aluno Grupo Excecao", grupos=[g_excecao])
    e3 = criar_estudante(prontuario="IQ3009503", nome="Aluno Sem Reserva", grupos=[g_sessao])

    sessao = criar_sessao(refeicao="almoço", data="21/10/2026", grupos=[g_sessao])

    criar_reserva(estudante=e1, data="21/10/2026", prato="Padrão")
    criar_reserva(estudante=e2, data="21/10/2026", prato="Vegetariano")

    criar_consumo(estudante=e1, sessao=sessao)

    # Filtrar apenas não consumidos
    nao_consumidos = service_logic.obter_estudantes_para_sessao(
        repos["sessao"],
        repos["estudante"],
        repos["reserva"],
        repos["consumo"],
        repos["grupo"],
        id_sessao=sessao.id,
        consumido=False,
        excessao_grupos={"2º B - MEC"},
    )
    assert len(nao_consumidos) == 1
    assert nao_consumidos[0]["pront"] == "IQ3009502"

    # Testando com lista vazia de IDs
    resultado_vazio = service_logic.obter_estudantes_para_sessao(
        repos["sessao"],
        repos["estudante"],
        repos["reserva"],
        repos["consumo"],
        repos["grupo"],
        id_sessao=sessao.id,
        pular_grupos=False,
    )
    assert isinstance(resultado_vazio, list)


def test_registrar_consumo_estudante_fluxo_agendado(
    repos, criar_grupo, criar_estudante, criar_sessao, criar_reserva, criar_consumo
):
    """Testa todas as regras de negócio do fluxo agendado de consumo."""
    g_sessao = criar_grupo(nome="Turma Sessao")
    g_excecao = criar_grupo(nome="Turma Excecao")
    g_outro = criar_grupo(nome="Outra Turma")

    e_ok = criar_estudante(prontuario="IQ3009601", nome="Aluno OK", grupos=[g_sessao])
    e_exc = criar_estudante(prontuario="IQ3009602", nome="Aluno Excecao", grupos=[g_excecao])
    e_sem_res = criar_estudante(prontuario="IQ3009603", nome="Aluno Sem Res", grupos=[g_sessao])
    e_outro = criar_estudante(prontuario="IQ3009604", nome="Aluno Outro Grupo", grupos=[g_outro])

    sessao = criar_sessao(refeicao="almoço", data="21/10/2026", grupos=[g_sessao])

    criar_reserva(estudante=e_ok, data="21/10/2026", prato="Feijoada")
    criar_reserva(estudante=e_exc, data="21/10/2026", prato="Salada")
    criar_reserva(estudante=e_outro, data="21/10/2026", prato="Padrão")

    # 1. Estudante não encontrado
    res1 = service_logic.registrar_consumo_com_reserva(
        repos["sessao"], repos["estudante"], repos["reserva"], repos["consumo"],
        id_sessao=sessao.id, prontuario="IQ9999999",
    )
    assert res1["autorizado"] is False
    assert "Estudante não encontrado" in res1["motivo"]

    # 2. Estudante sem reserva
    res2 = service_logic.registrar_consumo_com_reserva(
        repos["sessao"], repos["estudante"], repos["reserva"], repos["consumo"],
        id_sessao=sessao.id, prontuario="IQ3009603",
    )
    assert res2["autorizado"] is False
    assert "Sem reserva válida" in res2["motivo"]

    # 3. Com reserva mas sem permissão de grupo
    res3 = service_logic.registrar_consumo_com_reserva(
        repos["sessao"], repos["estudante"], repos["reserva"], repos["consumo"],
        id_sessao=sessao.id, prontuario="IQ3009604",
    )
    assert res3["autorizado"] is False
    assert "sem permissão de grupo" in res3["motivo"]

    # 4. Com reserva e grupo da sessão (autorizado)
    res4 = service_logic.registrar_consumo_com_reserva(
        repos["sessao"], repos["estudante"], repos["reserva"], repos["consumo"],
        id_sessao=sessao.id, prontuario="IQ3009601",
    )
    assert res4["autorizado"] is True
    assert "grupo da sessão" in res4["motivo"]
    assert res4["prato"] == "Feijoada"

    # 5. Tentativa de consumo duplicado
    res5 = service_logic.registrar_consumo_com_reserva(
        repos["sessao"], repos["estudante"], repos["reserva"], repos["consumo"],
        id_sessao=sessao.id, prontuario="IQ3009601",
    )
    assert res5["autorizado"] is False
    assert "Consumo já registrado" in res5["motivo"]

    # 6. Autorizado via grupo de exceção
    res6 = service_logic.registrar_consumo_com_reserva(
        repos["sessao"], repos["estudante"], repos["reserva"], repos["consumo"],
        id_sessao=sessao.id, prontuario="IQ3009602", excecao_grupos={"Turma Excecao"},
    )
    assert res6["autorizado"] is True
    assert "grupo de exceção" in res6["motivo"]

    # 7. Autorizado pulando grupos
    res7 = service_logic.registrar_consumo_com_reserva(
        repos["sessao"], repos["estudante"], repos["reserva"], repos["consumo"],
        id_sessao=sessao.id, prontuario="IQ3009604", pular_grupos=True,
    )
    assert res7["autorizado"] is True
    assert "grupos ignorados" in res7["motivo"]


def test_exportar_consumos_para_xlsx(
    repos, criar_estudante, criar_sessao, criar_consumo, tmp_path
):
    """Testa exportação de consumos para arquivo XLSX."""
    from pathlib import Path
    e = criar_estudante(prontuario="IQ3009701", nome="Aluno Planilha")
    s = criar_sessao(refeicao="lanche")
    criar_consumo(estudante=e, sessao=s, hora_consumo="10:15:00")

    # Exportar sessão
    arquivo_sessao = tmp_path / "sessao.xlsx"
    caminho_res1 = service_logic.exportar_sessao_para_xlsx(
        repos["sessao"], repos["consumo"], s.id, nome_arquivo_arg=arquivo_sessao
    )
    assert Path(caminho_res1).exists()

    # Exportar todos os consumos
    arquivo_todos = tmp_path / "todos.xlsx"
    caminho_res2 = service_logic.exportar_todos_os_consumos_para_xlsx(
        repos["consumo"], nome_arquivo_arg=arquivo_todos
    )
    assert Path(caminho_res2).exists()


def test_exportar_todos_os_consumos_vazio_lanca_erro(repos):
    """Testa que exportar quando não há consumos lança ValueError."""
    with pytest.raises(ValueError, match="Nenhum consumo registrado"):
        service_logic.exportar_todos_os_consumos_para_xlsx(repos["consumo"])


def test_sincronizacao_google_sheets(repos, tmp_path, monkeypatch):
    """Testa a sincronização de entrada e saída com o Google Sheets."""
    from unittest.mock import MagicMock, patch
    from registro.nucleo.exceptions import ErroNucleoRegistro

    # Sincronizar de Google Sheets
    with patch("registro.nucleo.google_api_service.obter_planilha") as mock_pl, \
         patch("registro.nucleo.google_api_service.buscar_valores_aba") as mock_buscar, \
         patch("registro.nucleo.utils.salvar_csv", return_value=True), \
         patch("registro.nucleo.importers_service.importar_estudantes_csv") as mock_imp_e, \
         patch("registro.nucleo.importers_service.importar_reservas_csv") as mock_imp_r:

        mock_buscar.side_effect = lambda pl, aba: [["col1"]] if aba in ["Discentes", "DB"] else []
        service_logic.sincronizar_do_google_sheets(
            repos["estudante"], repos["reserva"], repos["grupo"]
        )
        mock_imp_e.assert_called_once()
        mock_imp_r.assert_called_once()

    # Sincronizar para Google Sheets
    from registro.nucleo.models import Estudante, Sessao, Consumo
    e = Estudante(prontuario="IQ3009801", nome="Aluno Sync")
    s = Sessao(refeicao="lanche", data="21/10/2026", hora="09:00")
    repos["estudante"].obter_sessao().add_all([e, s])
    repos["estudante"].obter_sessao().commit()

    c = Consumo(estudante_id=e.id, sessao_id=s.id, hora_consumo="09:10:00")
    repos["consumo"].obter_sessao().add(c)
    repos["consumo"].obter_sessao().commit()

    with patch("registro.nucleo.google_api_service.obter_planilha"), \
         patch("registro.nucleo.google_api_service.anexar_linhas_unicas") as mock_anexar:
        # Sessão específica
        service_logic.sincronizar_para_google_sheets(repos["sessao"], repos["consumo"], s.id)
        mock_anexar.assert_called_once()

        # Todas as sessões
        mock_anexar.reset_mock()
        service_logic.sincronizar_todas_sessoes_para_google_sheets(repos["sessao"], repos["consumo"])
        mock_anexar.assert_called_once()


def test_service_logic_estudante_crud(repos):
    """Testa criação, atualização e listagem de estudantes via service_logic."""
    # Criar estudante
    res = service_logic.criar_estudante(
        repos["estudante"], repos["grupo"], "IQ3006001", "Aluno Service", ["Grupo SL"]
    )
    assert res["prontuario"] == "IQ3006001"
    assert res["nome"] == "Aluno Service"

    # Tentativa de criar duplicado deve falhar
    with pytest.raises(ValueError, match="já existe"):
        service_logic.criar_estudante(
            repos["estudante"], repos["grupo"], "IQ3006001", "Duplicado"
        )

    # Atualizar estudante
    atualizado = service_logic.atualizar_estudante(
        repos["estudante"], res["id"], {"nome": "Aluno Service Atualizado"}
    )
    assert atualizado is True

    # Listar todos os estudantes
    todos = service_logic.listar_todos_os_estudantes(repos["estudante"])
    assert any(e["prontuario"] == "IQ3006001" for e in todos)

    # Listar com filtro
    filtrados = service_logic.listar_estudantes(repos["estudante"], "Atualizado")
    assert len(filtrados) == 1
    assert filtrados[0]["nome"] == "Aluno Service Atualizado"

    # Listar fuzzy
    fuzzy = service_logic.listar_estudantes_fuzzy(repos["estudante"], "aluno service")
    assert len(fuzzy) >= 1
    assert fuzzy[0]["prontuario"] == "IQ3006001"


def test_service_logic_reserva_crud_e_listagem(repos):
    """Testa operações de criação, atualização, listagem e exclusão de reservas."""
    # Criar estudante para reserva
    est = service_logic.criar_estudante(
        repos["estudante"], repos["grupo"], "IQ3006002", "Aluno Reserva"
    )

    # Criar reserva com estudante existente
    reserva = service_logic.criar_reserva(
        repos["estudante"],
        repos["reserva"],
        "IQ3006002",
        {"prato": "Vegetariano", "data": "22/10/2026", "cancelada": False},
    )
    assert reserva["prato"] == "Vegetariano"
    assert reserva["data"] == "22/10/2026"

    # Criar reserva com estudante inexistente
    with pytest.raises(ValueError, match="não encontrado"):
        service_logic.criar_reserva(
            repos["estudante"], repos["reserva"], "IQ9999999", {"prato": "Normal", "data": "22/10/2026"}
        )

    # Listar datas de reservas
    datas = service_logic.listar_datas_reservas(repos["reserva"])
    assert "22/10/2026" in datas

    # Listar reservas
    lista_res = service_logic.listar_reservas(
        repos["grupo"], repos["reserva"], {"data": "22/10/2026"}
    )
    assert len(lista_res) >= 1
    assert lista_res[0]["prontuario_estudante"] == "IQ3006002"

    # Atualizar reserva
    ok_att = service_logic.atualizar_reserva(
        repos["reserva"], reserva["id"], {"prato": "Vegano"}
    )
    assert ok_att is True

    # Deletar reserva
    ok_del = service_logic.deletar_reserva(repos["reserva"], reserva["id"])
    assert ok_del is True


def test_service_logic_salvar_importacao_dados(repos):
    """Testa salvar_importacao_dados para persistência em lote de novos estudantes e reservas."""
    dados_import = [
        {
            "prontuario": "IQ3006003",
            "nome": "Estudante Batch",
            "data": "23/10/2026",
            "prato": "Geral",
        }
    ]

    resultado = service_logic.salvar_importacao_dados(
        repos["estudante"], repos["reserva"], dados_import
    )
    assert resultado["estudantes_criados"] == 1
    assert resultado["reservas_criadas"] == 1

    # Verificar existência
    est = repos["estudante"].por_prontuarios({"IQ3006003"})
    assert len(est) == 1
    assert est[0].nome == "Estudante Batch"


def test_atualizar_consumo_e_estatisticas_sessao(repos, criar_estudante, criar_reserva, criar_grupo):
    """Testa atualizar_consumo e a geração detalhada de obter_estatisticas_sessao."""
    grupo = criar_grupo(nome="1INFO")
    est1 = criar_estudante(prontuario="IQ3099901", nome="Estudante Alpha", grupos=[grupo])
    est2 = criar_estudante(prontuario="IQ3099902", nome="Estudante Beta", grupos=[grupo])

    # Cria sessão
    dados_sessao = {
        "refeicao": "almoço",
        "periodo": "Almoço",
        "data": "2026-10-22",
        "hora": "12:00",
        "grupos": ["1INFO"],
    }
    criar_reserva(estudante=est1, data="22/10/2026", prato="Padrão")
    criar_reserva(estudante=est2, data="22/10/2026", prato="Vegetariano")

    id_sessao = service_logic.iniciar_nova_sessao(
        repos["sessao"], repos["grupo"], repos["reserva"], dados_sessao
    )
    assert id_sessao is not None

    # Registra consumo para est1
    res = service_logic.registrar_consumo(
        repos["sessao"], repos["estudante"], repos["reserva"], repos["consumo"],
        id_sessao=id_sessao, prontuario="IQ3099901"
    )
    assert res.get("autorizado") is True
    consumo = repos["consumo"].por_prontuario_e_sessao("IQ3099901", id_sessao)
    assert consumo is not None
    id_consumo = consumo.id

    # Testa atualizar_consumo
    ok_att = service_logic.atualizar_consumo(
        repos["consumo"], repos["reserva"],
        id_consumo=id_consumo, hora_consumo="12:15:30", prato="Vegano"
    )
    assert ok_att is True

    # Verifica atualização
    consumo_db = repos["consumo"].ler_um(id_consumo)
    assert consumo_db.hora_consumo == "12:15:30"
    assert consumo_db.reserva.prato == "Vegano"

    # Testa estatísticas da sessão
    stats = service_logic.obter_estatisticas_sessao(
        repos["sessao"], repos["estudante"], repos["reserva"],
        repos["consumo"], repos["grupo"], id_sessao=id_sessao
    )
    assert stats["id_sessao"] == id_sessao
    assert stats["total_consumidos"] == 1
    assert stats["total_restantes"] == 1
    assert stats["total_esperado"] == 2
    assert stats["taxa_adesao"] == 50.0
    assert stats["total_com_reserva"] == 1
    assert "Vegano" in stats["distribuicao_pratos"]
    assert "1INFO" in stats["distribuicao_turmas"]



