"""
Testes unitários e de regressão para a classe FachadaRegistro em registro.nucleo.facade.
"""

import pytest
from sqlalchemy.orm import Session

from registro.nucleo.exceptions import ErroSessaoNaoAtiva
from registro.nucleo.facade import FachadaRegistro


def test_facade_iniciar_e_definir_sessao_ativa(
    facade: FachadaRegistro, criar_grupo
):
    """Verifica início de sessão e definição da sessão ativa na fachada."""
    criar_grupo(nome="1º A - MEC")
    dados_sessao = {
        "refeicao": "lanche",
        "periodo": "Manhã",
        "data": "2026-10-21",
        "hora": "09:30",
        "item_servido": "Suco de Laranja",
        "grupos": ["1º A - MEC"],
    }

    id_sessao = facade.iniciar_nova_sessao(dados_sessao)
    assert id_sessao is not None
    assert facade.id_sessao_ativa == id_sessao


def test_facade_registrar_consumo_sem_sessao_ativa_lanca_erro(facade: FachadaRegistro):
    """Lança ErroSessaoNaoAtiva se tentar registrar consumo sem sessão ativa."""
    facade.id_sessao_ativa = None
    with pytest.raises(ErroSessaoNaoAtiva):
        facade.registrar_consumo("IQ3001234")


def test_facade_fluxo_consumo_completo(
    facade: FachadaRegistro, criar_grupo, criar_estudante
):
    """Testa ciclo completo de consumo através da fachada."""
    grupo = criar_grupo(nome="2º A - MEC")
    estudante = criar_estudante(
        prontuario="IQ3008001", nome="Estudante Fachada", grupos=[grupo]
    )

    id_sessao = facade.iniciar_nova_sessao({
        "refeicao": "lanche",
        "periodo": "Tarde",
        "data": "2026-10-21",
        "hora": "15:00",
        "item_servido": "Iogurte",
        "grupos": ["2º A - MEC"],
    })
    assert id_sessao is not None

    # Registrar consumo
    resultado = facade.registrar_consumo("IQ3008001")
    assert resultado["autorizado"] is True
    assert resultado["aluno"] == "Estudante Fachada"

    # Cancelar/desfazer consumo
    consumos = facade.repo_consumo.ler_filtrado(sessao_id=id_sessao)
    assert len(consumos) == 1
    facade.desfazer_consumo(consumos[0].id)
    assert len(facade.repo_consumo.ler_filtrado(sessao_id=id_sessao)) == 0


def test_facade_busca_fuzzy_estudante(facade: FachadaRegistro, criar_estudante):
    """Testa busca aproximada (fuzzy) por nome de estudante."""
    criar_estudante(prontuario="IQ3009001", nome="Guilherme Henrique da Silva")
    criar_estudante(prontuario="IQ3009002", nome="Mariana Albuquerque")

    resultados = facade.listar_estudantes_fuzzy("Guilherm")
    assert len(resultados) >= 1
    assert resultados[0]["prontuario"] == "IQ3009001"


def test_facade_gerenciamento_sessao_ativa(facade: FachadaRegistro, criar_grupo):
    """Verifica obter detalhes, atualizar e deletar sessão ativa pela fachada."""
    criar_grupo(nome="Grupo Sessao Ativa")
    id_sessao = facade.iniciar_nova_sessao({
        "refeicao": "lanche",
        "periodo": "Manhã",
        "data": "2026-10-21",
        "hora": "08:00",
        "item_servido": "Maçã",
        "grupos": ["Grupo Sessao Ativa"],
    })

    detalhes = facade.obter_detalhes_sessao_ativa()
    assert detalhes["id"] == id_sessao
    assert detalhes["refeicao"] == "lanche"
    assert "Grupo Sessao Ativa" in detalhes["grupos"]

    # Atualizar
    facade.atualizar_detalhes_sessao(id_sessao, {"item_servido": "Pera"})
    detalhes_atualizados = facade.obter_detalhes_sessao_ativa()
    assert detalhes_atualizados["item_servido"] == "Pera"

    # Listagens
    assert len(facade.listar_todas_sessoes()) >= 1
    assert len(facade.listar_todos_os_grupos()) >= 1

    # Deletar sessão ativa
    facade.deletar_sessao_ativa()
    assert facade.id_sessao_ativa is None


def test_facade_gerenciador_de_contexto(db_session: Session):
    """Verifica uso da FachadaRegistro como context manager."""
    with FachadaRegistro(sessao_db=db_session) as f:
        assert f._sessao_db is db_session


def test_facade_erros_quando_sem_sessao_ativa(facade: FachadaRegistro):
    """Testa métodos que devem lançar ErroSessaoNaoAtiva quando não há sessão ativa."""
    facade.id_sessao_ativa = None

    with pytest.raises(ErroSessaoNaoAtiva):
        facade.obter_detalhes_sessao_ativa()

    with pytest.raises(ErroSessaoNaoAtiva):
        facade.deletar_sessao_ativa()

    with pytest.raises(ErroSessaoNaoAtiva):
        facade.registrar_consumo_com_reserva("IQ3001234")

    with pytest.raises(ErroSessaoNaoAtiva):
        facade.desfazer_consumo_por_prontuario("IQ3001234")

    with pytest.raises(ErroSessaoNaoAtiva):
        facade.obter_estudantes_para_sessao()

    with pytest.raises(ErroSessaoNaoAtiva):
        facade.atualizar_grupos_sessao(["1º A"])

    with pytest.raises(ErroSessaoNaoAtiva):
        facade.exportar_sessao_para_xlsx()

    with pytest.raises(ErroSessaoNaoAtiva):
        facade.sincronizar_para_google_sheets()

    # obter_estudantes_pesquisaveis_para_sessao retorna [] quando sem sessão ativa
    assert facade.obter_estudantes_pesquisaveis_para_sessao() == []


def test_facade_crud_estudantes(facade: FachadaRegistro):
    """Testa criação, atualização e listagens de estudantes via Fachada."""
    # Criação com turmas
    res_e = facade.criar_estudante("IQ3007001", "Aluno Novo", grupos=["Turma Alpha", "Turma Beta"])
    assert res_e["prontuario"] == "IQ3007001"
    assert res_e["nome"] == "Aluno Novo"

    # Tentativa de duplicata
    with pytest.raises(ValueError, match="já existe"):
        facade.criar_estudante("IQ3007001", "Outro Nome")

    # Atualizar estudante
    atualizado = facade.atualizar_estudante(res_e["id"], {"nome": "Aluno Renomeado", "ativo": False})
    assert atualizado is True

    # Listar todos os estudantes
    todos = facade.listar_todos_os_estudantes()
    assert any(e["prontuario"] == "IQ3007001" for e in todos)

    # Listar estudantes com busca
    filtrados = facade.listar_estudantes("Renomeado")
    assert len(filtrados) == 1
    assert filtrados[0]["nome"] == "Aluno Renomeado"

    # Busca fuzzy sem termo de busca (ordena por nome)
    todos_fuzzy = facade.listar_estudantes_fuzzy()
    assert len(todos_fuzzy) >= 1


def test_facade_crud_reservas(facade: FachadaRegistro):
    """Testa criação, atualização, listagem, cancelamento e reativação de reservas via Fachada."""
    # Cria estudante
    est = facade.criar_estudante("IQ3007101", "Aluno Reserva", grupos=["1º A - MEC"])

    # Cria reserva
    reserva = facade.criar_reserva("IQ3007101", {"data": "21/10/2026", "prato": "Feijoada"})
    assert reserva["prato"] == "Feijoada"
    assert reserva["cancelada"] is False

    # Erro de estudante inexistente
    with pytest.raises(ValueError, match="não encontrado"):
        facade.criar_reserva("IQ9999999", {"data": "21/10/2026", "prato": "Padrão"})

    # Listar datas de reservas
    datas = facade.listar_datas_reservas()
    assert "21/10/2026" in datas

    # Listar reservas sem filtro
    reservas_todas = facade.listar_reservas()
    assert len(reservas_todas) >= 1

    # Listar reservas com filtro de grupos
    reservas_grupo = facade.listar_reservas({"grupos": ["1º A - MEC"], "data": "21/10/2026"})
    assert len(reservas_grupo) >= 1

    # Atualizar reserva
    ok_att = facade.atualizar_reserva(reserva["id"], {"prato": "Vegetariano"})
    assert ok_att is True

    # Cancelar e reativar reserva
    facade.cancelar_reserva(reserva["id"])
    assert facade.repo_reserva.ler_um(reserva["id"]).cancelada is True

    facade.reativar_reserva(reserva["id"])
    assert facade.repo_reserva.ler_um(reserva["id"]).cancelada is False

    # Deletar reserva
    ok_del = facade.deletar_reserva(reserva["id"])
    assert ok_del is True
    assert facade.repo_reserva.ler_um(reserva["id"]) is None


def test_facade_operacoes_sessao_e_delegacoes(facade: FachadaRegistro, tmp_path):
    """Testa deleções específicas de sessão, sincronizações e autocomplete."""
    from unittest.mock import patch

    id_sessao = facade.iniciar_nova_sessao({
        "refeicao": "lanche",
        "periodo": "Manhã",
        "data": "2026-10-21",
        "hora": "09:00",
        "item_servido": "Biscoito",
        "grupos": ["1º A - MEC"],
    })
    facade.definir_sessao_ativa(id_sessao)
    assert facade.id_sessao_ativa == id_sessao

    # Atualizar grupos da sessão com excessao_grupos
    facade.atualizar_grupos_sessao(["1º A - MEC"], excessao_grupos=["2º B - MEC"])
    assert "2º B - MEC" in facade.excessao_grupos

    # Estudantes pesquisáveis para sessão
    pesquisaveis = facade.obter_estudantes_pesquisaveis_para_sessao()
    assert isinstance(pesquisaveis, list)

    # Obter estudantes para sessão
    est_sessao = facade.obter_estudantes_para_sessao()
    assert isinstance(est_sessao, list)

    # Exportar sessao e consumos para xlsx
    arquivo_sessao = tmp_path / "facade_sessao.xlsx"
    caminho = facade.exportar_sessao_para_xlsx(arquivo_sessao)
    assert caminho is not None

    # Deletar sessão por id (id_sessao_ativa deve virar None)
    facade.deletar_sessao(id_sessao)
    assert facade.id_sessao_ativa is None

    # Mocks de sincronização Google Sheets
    with patch("registro.nucleo.service_logic.sincronizar_do_google_sheets") as m_sync_do, \
         patch("registro.nucleo.service_logic.sincronizar_para_google_sheets") as m_sync_para, \
         patch("registro.nucleo.service_logic.sincronizar_todas_sessoes_para_google_sheets") as m_sync_todas:

        facade.sincronizar_do_google_sheets()
        m_sync_do.assert_called_once()

        facade.sincronizar_todas_sessoes_para_google_sheets()
        m_sync_todas.assert_called_once()

        # Ativar nova sessão para sincronizar para google sheets
        nova_sessao = facade.iniciar_nova_sessao({
            "refeicao": "lanche", "periodo": "Manhã", "data": "2026-10-21",
            "hora": "09:00", "grupos": [],
        })
        facade.sincronizar_para_google_sheets()
        m_sync_para.assert_called_once()


