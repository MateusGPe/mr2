"""
Testes unitários e de regressão para a classe FachadaRegistro em registro.nucleo.facade.
"""

import datetime as dt
from pathlib import Path
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


def test_facade_repositorio_encapsulamento_e_propriedades(facade: FachadaRegistro):
    """Garante que repositórios são atributos privados e acessíveis por propriedades."""
    assert hasattr(facade, "_repo_estudante")
    assert hasattr(facade, "_repo_reserva")
    assert hasattr(facade, "_repo_sessao")
    assert hasattr(facade, "_repo_consumo")
    assert hasattr(facade, "_repo_grupo")

    assert facade.repo_estudante is facade._repo_estudante
    assert facade.repo_reserva is facade._repo_reserva
    assert facade.repo_sessao is facade._repo_sessao
    assert facade.repo_consumo is facade._repo_consumo
    assert facade.repo_grupo is facade._repo_grupo

    # Teste de propriedade de compatibilidade ortográfica (excecao_grupos / excessao_grupos)
    facade.excessao_grupos = {"GrupoTeste"}
    assert "GrupoTeste" in facade.excecao_grupos
    assert "GrupoTeste" in facade.excessao_grupos

    facade.excecao_grupos = {"GrupoNovo"}
    assert "GrupoNovo" in facade.excessao_grupos


def test_facade_importacao_unificada(facade: FachadaRegistro, tmp_path):
    """Testa o fluxo unificado de importação diretamente pela FachadaRegistro."""
    csv_file = tmp_path / "alunos_import.csv"
    csv_file.write_text(
        "prontuario,nome,prato,data\n"
        "IQ3009999,Novo Importado,Almoço,2026-10-25\n",
        encoding="utf-8",
    )

    # 1. Analisar arquivo diretamente pela FachadaRegistro
    res = facade.analisar_arquivo(str(csv_file), tipo="header")
    assert "resumo" in res
    assert res["resumo"]["total_linhas"] == 1

    # 2. Simular importação
    preview = facade.simular_importacao(res["itens_revisao"])
    assert "novos_estudantes" in preview

    # 3. Confirmar importação
    resultado = facade.confirmar_importacao(res["itens_revisao"])
    assert resultado["estudantes_criados"] == 1
    assert resultado["reservas_criadas"] == 1

    # Verificar que estudante e reserva agora existem no banco
    estudantes = facade.listar_estudantes("IQ3009999")
    assert len(estudantes) == 1
    assert estudantes[0]["nome"] == "Novo Importado"

    reservas = facade.listar_reservas({"data": "25/10/2026"})
    assert len(reservas) == 1
    assert reservas[0]["prontuario_estudante"] == "IQ3009999"


def test_facade_obter_todos_estudantes_com_grupos(
    facade: FachadaRegistro, criar_grupo, criar_estudante
):
    """Testa consulta otimizada de todos os estudantes com grupos para o analisador."""
    grupo = criar_grupo(nome="Grupo Opt")
    criar_estudante(prontuario="IQ3008888", nome="Aluno Opt", grupos=[grupo])

    todos = facade.obter_todos_estudantes_com_grupos()
    prontuarios = [e.prontuario for e in todos]
    assert "IQ3008888" in prontuarios


def test_facade_parametros_grafia_excecao(
    facade: FachadaRegistro, criar_grupo, criar_estudante
):
    """Verifica aceitação de ambos os parâmetros 'excecao_grupos' e 'excessao_grupos'."""
    grupo = criar_grupo(nome="Grupo Grafia")
    criar_estudante(prontuario="IQ3007777", nome="Aluno Grafia", grupos=[grupo])

    id_sessao = facade.iniciar_nova_sessao({
        "refeicao": "lanche",
        "periodo": "Manhã",
        "data": "2026-10-21",
        "hora": "09:00",
        "item_servido": "Fruta",
        "grupos": ["Grupo Grafia"],
    })

    # Atualizar usando o parâmetro corrigido excecao_grupos
    facade.atualizar_grupos_sessao(["Grupo Grafia"], excecao_grupos=["Grupo Outro"])
    assert "Grupo Outro" in facade.excecao_grupos

    # Testar registrar consumo com o parâmetro corrigido
    res = facade.registrar_consumo("IQ3007777", excecao_grupos={"Grupo Grafia"})
    assert res["autorizado"] is True


def test_facade_registrar_log_sincronizacao(facade: FachadaRegistro, db_session: Session):
    """Testa o registro de eventos de sincronização via FachadaRegistro."""
    from registro.nucleo.models import SyncLog

    sucesso = facade.registrar_log_sincronizacao(
        direction="download",
        status="success",
        message="Sincronização concluída com sucesso.",
        records_affected=15,
    )
    assert sucesso is True

    logs = db_session.query(SyncLog).all()
    assert len(logs) == 1
    assert logs[0].direction == "download"
    assert logs[0].status == "success"
    assert logs[0].records_affected == 15
    assert "Sincronização concluída" in logs[0].message


def test_facade_session_persistence(facade: FachadaRegistro, tmp_path, monkeypatch):
    """Testa salvar, carregar e limpar o estado da sessão via fachada."""
    session_file = tmp_path / "session.json"
    import registro.nucleo.constants as constants
    monkeypatch.setattr(constants, "CAMINHO_SESSAO", session_file)

    # Iniciar sessão
    estudante = facade.criar_estudante("IQ3009999", "Aluno Sessao", grupos=["Grupo Teste"])
    facade.criar_reserva(estudante["prontuario"], {"data": "2026-10-21", "prato": "Geral"})
    id_sessao = facade.iniciar_nova_sessao({
        "refeicao": "lanche",
        "periodo": "Integral",
        "data": "2026-10-21",
        "hora": "09:00",
        "item_servido": "Bolo",
        "grupos": ["Grupo Teste"],
    })

    # Salvar estado
    assert facade.salvar_estado_sessao(id_sessao) is True
    assert session_file.exists()

    # Carregar estado
    facade.id_sessao_ativa = None
    estado = facade.carregar_estado_sessao()
    assert estado is not None
    assert estado.get("id_sessao") == id_sessao
    assert facade.id_sessao_ativa == id_sessao

    # Limpar estado
    assert facade.limpar_estado_sessao() is True
    assert not session_file.exists()
    assert facade.id_sessao_ativa is None


def test_facade_exportar_estudantes_e_reservas_para_csv(facade: FachadaRegistro, tmp_path):
    """Testa exportação de estudantes e reservas para CSV através da fachada."""
    e1 = facade.criar_estudante("IQ3001111", "Estudante Export 1", grupos=["Turma A"])
    e2 = facade.criar_estudante("IQ3002222", "Estudante Export 2", grupos=["Turma B"])
    facade.criar_reserva(e1["prontuario"], {"data": "2026-10-21", "prato": "Tradicional"})
    facade.criar_reserva(e2["prontuario"], {"data": "2026-10-22", "prato": "Vegetariano"})

    csv_alunos = tmp_path / "alunos.csv"
    res_alunos = facade.exportar_estudantes_para_csv(csv_alunos)
    assert Path(res_alunos).exists()
    conteudo_alunos = Path(res_alunos).read_text(encoding="utf-8")
    assert "Estudante Export 1" in conteudo_alunos
    assert "IQ3002222" in conteudo_alunos

    csv_reservas = tmp_path / "reservas.csv"
    res_reservas = facade.exportar_reservas_para_csv(csv_reservas)
    assert Path(res_reservas).exists()
    conteudo_reservas = Path(res_reservas).read_text(encoding="utf-8")
    assert "Tradicional" in conteudo_reservas
    assert "Vegetariano" in conteudo_reservas


def test_facade_obter_estatisticas_dashboard(facade: FachadaRegistro):
    """Testa obtenção de estatísticas para o dashboard."""
    estudante = facade.criar_estudante("IQ3003333", "Estudante Dash", grupos=["Turma Dash"])
    hoje_iso = dt.date.today().isoformat()
    facade.criar_reserva(estudante["prontuario"], {"data": hoje_iso, "prato": "Geral"})

    stats = facade.obter_estatisticas_dashboard()
    assert "alunos_ativos" in stats
    assert "reservas_hoje" in stats
    assert "consumo_ontem" in stats
    assert "grupos_total" in stats
    assert stats["alunos_ativos"] >= 1
    assert stats["reservas_hoje"] >= 1


def test_facade_listar_datas_reservas_ordenadas(facade: FachadaRegistro):
    """Testa se as datas de reservas são retornadas em ordem cronológica decrescente."""
    est = facade.criar_estudante("IQ3004444", "Estudante Datas", grupos=["Turma Datas"])
    facade.criar_reserva(est["prontuario"], {"data": "10/01/2026", "prato": "P1"})
    facade.criar_reserva(est["prontuario"], {"data": "25/12/2026", "prato": "P2"})
    facade.criar_reserva(est["prontuario"], {"data": "05/06/2026", "prato": "P3"})

    datas = facade.listar_datas_reservas()
    assert len(datas) >= 3
    idx_dez = datas.index("25/12/2026")
    idx_jun = datas.index("05/06/2026")
    idx_jan = datas.index("10/01/2026")
    assert idx_dez < idx_jun < idx_jan
