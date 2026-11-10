# ----------------------------------------------------------------------------
# Arquivo: tests/gui/test_gui_painel_funcional.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Testes funcionais e de casos de uso para o Painel Administrativo
(AbaAlunos, AbaTurmas, AbaDashboard e PainelApp), integrando com SQLite em memória.
"""

from unittest.mock import MagicMock, patch
import pytest

from registro.gui.painel.abas.aba_alunos import AbaAlunos
from registro.gui.painel.abas.aba_dashboard import AbaDashboard
from registro.gui.painel.abas.aba_turmas import AbaTurmas
from registro.gui.painel.app import App as PainelApp


@pytest.fixture
def painel_dados(facade, criar_grupo, criar_estudante, criar_sessao, criar_reserva, criar_consumo):
    """Popula o SQLite com dados realistas para o Painel Administrativo."""
    grupo_info = criar_grupo(nome="1INFO", ativo=True)
    grupo_mec = criar_grupo(nome="2MEC", ativo=True)

    aluno1 = criar_estudante(
        prontuario="IQ3000001",
        nome="Alice Ferreira",
        ativo=True,
        grupos=[grupo_info],
    )
    aluno2 = criar_estudante(
        prontuario="IQ3000002",
        nome="Bruno Silveira",
        ativo=True,
        grupos=[grupo_info, grupo_mec],
    )
    aluno3 = criar_estudante(
        prontuario="IQ3000003",
        nome="Carla Inativa",
        ativo=False,
        grupos=[grupo_mec],
    )

    data_hoje = "21/10/2026"
    sessao = criar_sessao(
        refeicao="almoço",
        data=data_hoje,
        hora="12:00",
        grupos=[grupo_info, grupo_mec],
    )
    reserva1 = criar_reserva(estudante=aluno1, data=data_hoje, prato="Padrão")
    criar_consumo(estudante=aluno1, sessao=sessao, reserva=reserva1)

    return {
        "facade": facade,
        "grupo_info": grupo_info,
        "grupo_mec": grupo_mec,
        "aluno1": aluno1,
        "aluno2": aluno2,
        "aluno3": aluno3,
        "sessao": sessao,
    }


def test_painel_aba_alunos_listagem_e_filtros(app_root, painel_dados, mock_messagebox):
    """Cenário Provável: AbaAlunos carrega dados do banco e responde a filtros de busca e status."""
    facade = painel_dados["facade"]

    aba = AbaAlunos(parent=app_root, fachada_nucleo=facade)
    aba.pack()
    app_root.update()

    # 1. Total inicial de alunos listados (todos os 3)
    assert len(aba.dados_alunos_atuais) == 3

    # 2. Filtro por nome
    aba.search_aluno_var.set("Alice")
    aba._carregar_alunos()
    app_root.update()
    assert len(aba.dados_alunos_atuais) == 1
    assert aba.dados_alunos_atuais[0]["prontuario"] == "IQ3000001"

    # 3. Limpa busca e filtra por status 'Inativos'
    aba.search_aluno_var.set("")
    aba.filter_status_var.set("Inativos")
    aba._carregar_alunos()
    app_root.update()
    assert len(aba.dados_alunos_atuais) == 1
    assert aba.dados_alunos_atuais[0]["nome"] == "Carla Inativa"

    # 4. Filtra por status 'Ativos'
    aba.filter_status_var.set("Ativos")
    aba._carregar_alunos()
    app_root.update()
    assert len(aba.dados_alunos_atuais) == 2

    aba.destroy()


def test_painel_aba_turmas_contagem_alunos(app_root, painel_dados, mock_messagebox):
    """Cenário Provável: AbaTurmas lista grupos e contagem associada de estudantes."""
    facade = painel_dados["facade"]

    aba = AbaTurmas(parent=app_root, fachada_nucleo=facade)
    aba.pack()
    app_root.update()

    # Verifica se as turmas foram carregadas
    turmas_tree = aba.turmas_table
    iids = turmas_tree.obter_iids_filhos()
    assert len(iids) >= 2

    aba.destroy()


def test_painel_aba_dashboard_estatisticas_reais(app_root, painel_dados, mock_messagebox):
    """Cenário Provável: AbaDashboard exibe estatísticas calculadas pelo backend real."""
    facade = painel_dados["facade"]

    aba = AbaDashboard(parent=app_root, fachada_nucleo=facade)
    aba.pack()
    app_root.update()

    # Validações dos cards executivos
    assert aba.lbl_alunos_val["text"] == "2"  # 2 alunos ativos
    assert "1 inativo" in aba.lbl_alunos_sub["text"].lower()
    assert aba.lbl_turmas_val["text"] == "2"  # 2 turmas ativas

    aba.destroy()


def test_painel_app_navegacao_entre_abas(app_root, painel_dados, mock_messagebox):
    """Cenário Provável: Inicialização da janela principal PainelApp e alternância entre abas."""
    facade = painel_dados["facade"]

    with patch("ttkbootstrap.window._require_single_root"):
        app = PainelApp(fachada_nucleo=facade)
        app.withdraw()
        app.update()

        assert app.fachada_nucleo is facade
        assert "dashboard" in app.frames
        assert "alunos" in app.frames
        assert "turmas" in app.frames

        # Navega para a aba de alunos
        app.show_frame("alunos")
        app.update()
        assert app.selected == "alunos"

        # Navega para a aba de turmas
        app.show_frame("turmas")
        app.update()
        assert app.selected == "turmas"

        app.destroy()


def test_painel_dialogs_turma_tipo_e_reserva_categoria_pontual(
    app_root, painel_dados, mock_messagebox
):
    """Testa TurmaDialog (tipo Categoria), ReservaDialog (vínculo pontual sem alterar aluno) e AbaReservas."""
    from registro.gui.painel.abas.aba_reservas import AbaReservas
    from registro.gui.painel.dialogos import ReservaDialog, TurmaDialog

    facade = painel_dados["facade"]

    with patch.object(TurmaDialog, "grab_set"), \
         patch.object(TurmaDialog, "transient"), \
         patch.object(TurmaDialog, "wait_window"):
        dlg_turma = TurmaDialog(app_root, facade)
        dlg_turma.nome_entry.insert(0, "ESP1")
        dlg_turma.tipo_combobox.set("Categoria (Optativa / Programa / Evento)")
        dlg_turma._on_save()
        assert dlg_turma.result is True

    grupos_esp1 = [g for g in facade.listar_todos_os_grupos() if g["nome"] == "ESP1"]
    assert len(grupos_esp1) == 1
    assert grupos_esp1[0]["tipo"] == "categoria"

    # Cria reserva para aluno Bruno Silveira (IQ3000002) vinculando ESP1 e LIB0 na reserva
    with patch.object(ReservaDialog, "grab_set"), \
         patch.object(ReservaDialog, "transient"), \
         patch.object(ReservaDialog, "wait_window"):
        dlg_res = ReservaDialog(app_root, facade)
        dlg_res.aluno_combobox.set("IQ3000002 - Bruno Silveira")
        dlg_res.data_entry.entry.delete(0, "end")
        dlg_res.data_entry.entry.insert(0, "25/11/2026")
        dlg_res.prato_combobox.set("Vegetariano")
        dlg_res.seletor_categorias_reserva.definir_selecionadas(["ESP1", "LIB0"])
        dlg_res._on_save()
        assert dlg_res.result is True

    # Verifica que o estudante NÃO recebeu ESP1/LIB0 permanentemente
    bruno = facade.repo_estudante.por_prontuarios_com_grupos({"IQ3000002"})[0]
    assert bruno.categorias_nomes == []

    # Verifica que a reserva aparece na AbaReservas com as categorias
    aba_res = AbaReservas(app_root, facade)
    aba_res.var_data.set("25/11/2026")
    aba_res._filtrar_reservas()
    app_root.update()
    assert len(aba_res.dados_reservas_atuais) == 1
    assert aba_res.dados_reservas_atuais[0]["categorias"] == ["ESP1", "LIB0"]
    aba_res.destroy()


def test_painel_reserva_dialog_almoco_jantar_e_aba_reservas(
    app_root, painel_dados, mock_messagebox
):
    """Testa seleção de Almoço e/ou Jantar em ReservaDialog, validação e exibição na AbaReservas."""
    from registro.gui.painel.abas.aba_reservas import AbaReservas
    from registro.gui.painel.dialogos import ReservaDialog

    facade = painel_dados["facade"]

    with patch.object(ReservaDialog, "grab_set"), \
         patch.object(ReservaDialog, "transient"), \
         patch.object(ReservaDialog, "wait_window"):
        dlg = ReservaDialog(app_root, facade)
        dlg.aluno_combobox.set("IQ3000001 - Alice Ferreira")
        dlg.data_entry.entry.delete(0, "end")
        dlg.data_entry.entry.insert(0, "26/11/2026")

        # Desmarcar ambos deve exibir aviso e impedir salvamento
        dlg.almoco_var.set(False)
        dlg.jantar_var.set(False)
        dlg._on_save()
        assert dlg.result is False
        assert len(mock_messagebox.warning_calls) == 1

        # Marcar ambos salva corretamente
        dlg.almoco_var.set(True)
        dlg.jantar_var.set(True)
        dlg._on_save()
        assert dlg.result is True

    aba_res = AbaReservas(app_root, facade)
    aba_res.var_data.set("26/11/2026")
    aba_res._filtrar_reservas()
    app_root.update()
    assert len(aba_res.dados_reservas_atuais) == 1
    assert aba_res.dados_reservas_atuais[0]["almoco"] is True
    assert aba_res.dados_reservas_atuais[0]["jantar"] is True
    assert aba_res.dados_reservas_atuais[0]["turnos_str"] == "Almoço e Jantar"
    aba_res.destroy()
