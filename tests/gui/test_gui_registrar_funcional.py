# ----------------------------------------------------------------------------
# Arquivo: tests/gui/test_gui_registrar_funcional.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Testes funcionais e de casos de uso (prováveis e improváveis) para o
módulo de Registro Operacional (AppRegistro, PainelAcaoBusca, PainelStatusRegistrados),
integrando com SQLite em memória e FachadaRegistro real.
"""

from unittest.mock import MagicMock, patch

import pytest

from registro.gui.registrar.app import AppRegistro
from registro.gui.registrar.painel_acao_busca import PainelAcaoBusca
from registro.gui.registrar.painel_status_registrados import PainelStatusRegistrados


@pytest.fixture
def registrar_dados(facade, criar_grupo, criar_estudante, criar_sessao):
    """Cria dados básicos no SQLite para teste do Registrar."""
    grupo_info = criar_grupo(nome="1INFO", ativo=True)
    grupo_mec = criar_grupo(nome="1MEC", ativo=True)

    estudante1 = criar_estudante(
        prontuario="IQ3000001",
        nome="Lucas Fernandes",
        ativo=True,
        grupos=[grupo_info],
    )
    estudante2 = criar_estudante(
        prontuario="IQ3000002",
        nome="Juliana Santos",
        ativo=True,
        grupos=[grupo_mec],
    )
    sessao = criar_sessao(
        refeicao="lanche",
        data="21/10/2026",
        hora="09:30",
        item_servido="Biscoito",
        grupos=[grupo_info, grupo_mec],
    )
    facade.definir_sessao_ativa(sessao.id)

    return {
        "facade": facade,
        "estudante1": estudante1,
        "estudante2": estudante2,
        "grupo_info": grupo_info,
        "grupo_mec": grupo_mec,
        "sessao": sessao,
    }


def test_painel_busca_e_registro_sucesso(app_root, registrar_dados, mock_messagebox):
    """Cenário Provável: Busca por prontuário encontra estudante e registra consumo no SQLite."""
    facade = registrar_dados["facade"]
    estudante1 = registrar_dados["estudante1"]

    painel_mock_app = MagicMock()
    painel = PainelAcaoBusca(
        master=app_root,
        app=painel_mock_app,
        fachada_nucleo=facade,
    )
    painel.pack()
    app_root.update()

    # 1. Digita prontuário no campo de busca e executa
    painel._var_entrada_busca.set("IQ3000001")
    painel._executar_busca_real()
    app_root.update()

    assert len(painel._dados_correspondencias_elegiveis_atuais) == 1
    assert painel._dados_elegivel_selecionado is not None
    assert painel._dados_elegivel_selecionado["Pront"] == "IQ3000001"

    # 2. Confirma o registro do estudante selecionado
    painel._registrar_elegivel_selecionado()
    app_root.update()

    # Valida persistência no SQLite
    consumidos = facade.obter_estudantes_para_sessao(consumido=True)
    assert len(consumidos) == 1
    assert consumidos[0]["pront"] == "IQ3000001"
    painel_mock_app.notificar_sucesso_registro.assert_called_once()

    painel.destroy()


def test_painel_busca_estudante_inexistente_improvavel(app_root, registrar_dados, mock_messagebox):
    """Cenário Improvável: Busca por estudante que não existe no banco de dados."""
    facade = registrar_dados["facade"]

    painel = PainelAcaoBusca(
        master=app_root,
        app=MagicMock(),
        fachada_nucleo=facade,
    )
    painel.pack()
    app_root.update()

    painel._var_entrada_busca.set("ZZ9999999")
    painel._executar_busca_real()
    app_root.update()

    assert len(painel._dados_correspondencias_elegiveis_atuais) == 0
    assert painel._dados_elegivel_selecionado is None

    painel.destroy()


def test_painel_duplo_registro_gera_aviso(app_root, registrar_dados, mock_messagebox):
    """Cenário Provável: Tentativa de registrar o mesmo estudante duas vezes aciona diálogo de aviso."""
    facade = registrar_dados["facade"]
    estudante1 = registrar_dados["estudante1"]

    painel_app = MagicMock()
    painel = PainelAcaoBusca(
        master=app_root,
        app=painel_app,
        fachada_nucleo=facade,
    )
    painel.pack()
    app_root.update()

    # Primeiro registro (sucesso)
    painel._var_entrada_busca.set(estudante1.prontuario)
    painel._executar_busca_real()
    app_root.update()
    painel._ao_selecionar_estudante_elegivel()
    painel._registrar_elegivel_selecionado()
    app_root.update()
    assert len(facade.obter_estudantes_para_sessao(consumido=True)) == 1

    # Tenta registrar novamente
    painel._dados_elegivel_selecionado = {
        "Pront": estudante1.prontuario,
        "Nome": estudante1.nome,
        "Categoria": "REGULAR",
    }
    painel._registrar_elegivel_selecionado()
    app_root.update()

    # Verifica que exibiu aviso de Já Registrado
    assert len(mock_messagebox.warning_calls) >= 1
    aviso = mock_messagebox.warning_calls[0]
    assert "Já Registrado" in aviso["title"] or "já consumiu" in aviso["message"].lower() or "já registrado" in aviso["message"].lower()

    painel.destroy()


def test_painel_status_registrados_cancelamento_consumo(app_root, registrar_dados, mock_messagebox):
    """Cenário Provável: Cancelar/excluir um consumo registrado reverte a persistência no SQLite."""
    facade = registrar_dados["facade"]
    estudante1 = registrar_dados["estudante1"]

    # Registra o consumo no banco
    facade.registrar_consumo(estudante1.prontuario)
    assert len(facade.obter_estudantes_para_sessao(consumido=True)) == 1

    mock_app = MagicMock()
    # Configura mock_app.tratar_delecao_consumo para chamar a fachada como AppRegistro faz
    def fake_tratar_delecao(dados_para_logica, _iid):
        pront = dados_para_logica[0]
        facade.desfazer_consumo_por_prontuario(pront)
        painel_status.carregar_estudantes_registrados()

    mock_app.tratar_delecao_consumo.side_effect = fake_tratar_delecao

    painel_status = PainelStatusRegistrados(
        master=app_root,
        app=mock_app,
        fachada_nucleo=facade,
    )
    painel_status.pack()
    app_root.update()

    # Recarrega a lista com dados da fachada
    painel_status.carregar_estudantes_registrados()
    app_root.update()

    iids = painel_status._tabela_estudantes_registrados.obter_iids_filhos()
    assert len(iids) == 1

    # Simula seleção e confirmação de exclusão
    view = painel_status._tabela_estudantes_registrados.view
    view.selection_set(iids[0])
    view.focus(iids[0])

    # Executa exclusão
    painel_status._ao_teclar_delete()
    app_root.update()

    # Confirma que foi removido do banco SQLite
    consumidos_depois = facade.obter_estudantes_para_sessao(consumido=True)
    assert len(consumidos_depois) == 0

    painel_status.destroy()


def test_app_registro_janela_completa(facade, registrar_dados, mock_messagebox, tmp_path, monkeypatch):
    """Garante inicialização integrada da janela AppRegistro com a Fachada real injetada."""
    import registro.nucleo.constants as constants

    monkeypatch.setattr(constants, "CAMINHO_SESSAO", tmp_path / "session.json")
    with patch("ttkbootstrap.window._require_single_root"):
        app = AppRegistro(fachada_nucleo=facade)
        app.withdraw()
        app.update()

        assert app.get_fachada() is facade
        assert app._painel_acao is not None
        assert app._painel_status is not None
        assert app._btn_horario_livre is not None
        assert facade.ignorar_horario_grade is False

        # Alterna Horário Livre pela barra superior
        app._var_horario_livre.set(True)
        app._ao_alternar_horario_livre()
        app.update()
        assert facade.ignorar_horario_grade is True
        assert "Horário Livre" in app._label_info_sessao.cget("text")

        app._var_horario_livre.set(False)
        app._ao_alternar_horario_livre()
        app.update()
        assert facade.ignorar_horario_grade is False
        assert "Horário Livre" not in app._label_info_sessao.cget("text")

        app.destroy()
