# ----------------------------------------------------------------------------
# Arquivo: tests/gui/test_gui_dialogos_sessao_filtro.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Testes funcionais de GUI para os diálogos de sessão e filtros de turmas:
- DialogoFiltroTurmas (seleções, grade do dia, categorias, inversões, busca)
- DialogoSessao (criação, edição de sessão ativa, atalhos, validações)
"""

from unittest.mock import MagicMock, patch

import pytest

from registro.gui.registrar.dialogo_filtro_turmas import DialogoFiltroTurmas
from registro.gui.registrar.dialogo_sessao import DialogoSessao
from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.services import grade_horarios_service


@pytest.fixture
def ambiente_gui(facade: FachadaRegistro, criar_grupo, criar_estudante, criar_sessao):
    """Prepara o banco SQLite em memória com turmas e sessão ativa para os diálogos."""
    g_1a = criar_grupo(nome="1º BEM", ativo=True)
    g_2a = criar_grupo(nome="2º BEM", ativo=True)
    g_mec = criar_grupo(nome="1º MEC", ativo=True)
    g_ads = criar_grupo(nome="ADS", ativo=True)

    sessao = criar_sessao(
        refeicao="lanche",
        item_servido="Fruta",
        grupos=[g_1a, g_2a],
    )
    facade.definir_sessao_ativa(sessao.id)

    return {
        "facade": facade,
        "grupos": [g_1a, g_2a, g_mec, g_ads],
        "sessao": sessao,
    }


# ============================================================================
# 1. Testes de DialogoFiltroTurmas
# ============================================================================


def test_dialogo_filtro_turmas_acoes_botoes(app_root, ambiente_gui, mock_messagebox):
    """Testa botões Marcar Todas, Limpar, Inverter e Integrado."""
    facade = ambiente_gui["facade"]
    app_parente = MagicMock()
    callback_chamado = []

    def ao_aplicar(selecionados):
        callback_chamado.append(selecionados)

    with patch.object(DialogoFiltroTurmas, "grab_set"), \
         patch.object(DialogoFiltroTurmas, "transient"), \
         patch.object(DialogoFiltroTurmas, "deiconify"), \
         patch.object(DialogoFiltroTurmas, "_centralizar_janela"):

        dialogo = DialogoFiltroTurmas(
            parent=app_root,
            fachada_nucleo=facade,
            callback_aplicar=ao_aplicar,
        )
        app_root.update()

        # 1. Verifica estado inicial: 1º BEM e 2º BEM devem estar marcados
        marcados_inicial = {ident for ident, var, _ in dialogo._dados_checkbox if var.get()}
        assert "1º BEM" in marcados_inicial
        assert "2º BEM" in marcados_inicial

        # 2. Clicar em "⚪ Limpar"
        dialogo._ao_limpar_todas()
        app_root.update()
        assert all(not var.get() for _, var, _ in dialogo._dados_checkbox)

        # 3. Clicar em "✅ Marcar Todas"
        dialogo._ao_marcar_todas()
        app_root.update()
        marcados_todos = {ident for ident, var, _ in dialogo._dados_checkbox if var.get() and not ident.startswith("#")}
        assert "1º BEM" in marcados_todos
        assert "1º MEC" in marcados_todos

        # 4. Clicar em "🔄 Inverter"
        dialogo._ao_inverter_selecoes()
        app_root.update()
        # As turmas com reserva que estavam True agora devem ser False
        assert all(not var.get() for ident, var, _ in dialogo._dados_checkbox if not ident.startswith("#"))

        # 5. Fechar diálogo
        dialogo.destroy()


def test_dialogo_filtro_turmas_grade_do_dia_com_e_sem_previsao(app_root, ambiente_gui, mock_messagebox, tmp_path, monkeypatch):
    """Testa o botão '🕒 Grade do Dia' quando há e quando não há turmas na grade."""
    facade = ambiente_gui["facade"]
    caminho_grade = tmp_path / "grade_gui.json"

    # Grade com previsão apenas para 1º BEM no lanche
    grade = {
        "segunda": {
            "lanche": [{"inicio": "09:30", "fim": "10:00", "turmas": ["1º BEM"]}]
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho_grade)

    monkeypatch.setattr(grade_horarios_service, "CAMINHO_GRADE_HORARIOS", caminho_grade)
    monkeypatch.setattr(grade_horarios_service, "obter_dia_semana_atual", lambda: "segunda")

    with patch.object(DialogoFiltroTurmas, "grab_set"), \
         patch.object(DialogoFiltroTurmas, "transient"), \
         patch.object(DialogoFiltroTurmas, "deiconify"), \
         patch.object(DialogoFiltroTurmas, "_centralizar_janela"):

        dialogo = DialogoFiltroTurmas(
            parent=app_root,
            fachada_nucleo=facade,
            callback_aplicar=lambda s: None,
        )
        app_root.update()

        # Clica em Grade do Dia com previsão existente
        dialogo._ao_selecionar_grade()
        app_root.update()

        marcados = {ident for ident, var, _ in dialogo._dados_checkbox if var.get() and not ident.startswith("#")}
        assert marcados == {"1º BEM"}

        # Agora simula dia sem previsão (ex: domingo)
        monkeypatch.setattr(grade_horarios_service, "obter_dia_semana_atual", lambda: "domingo")
        dialogo._ao_selecionar_grade()
        app_root.update()

        # Deve disparar aviso via Messagebox
        assert len(mock_messagebox.info_calls) > 0
        assert any(
            "Nenhuma turma prevista" in call["message"] or "Nenhuma turma prevista" in call["title"]
            for call in mock_messagebox.info_calls
        )

        dialogo.destroy()


def test_dialogo_filtro_turmas_aplicar_categoria_e_turmas(app_root, ambiente_gui, mock_messagebox):
    """Testa a aplicação de filtros selecionando turmas e categorias separadas na mesma lista."""
    facade = ambiente_gui["facade"]
    facade.criar_grupo("PAP", tipo="categoria")
    aplicados = []

    with patch.object(DialogoFiltroTurmas, "grab_set"), \
         patch.object(DialogoFiltroTurmas, "transient"), \
         patch.object(DialogoFiltroTurmas, "deiconify"), \
         patch.object(DialogoFiltroTurmas, "_centralizar_janela"):

        dialogo = DialogoFiltroTurmas(
            parent=app_root,
            fachada_nucleo=facade,
            callback_aplicar=lambda selec: aplicados.append(selec),
        )
        app_root.update()

        # Seleciona 1º MEC e a categoria PAP
        dialogo._ao_limpar_todas()
        for ident, var, _ in dialogo._dados_checkbox:
            if ident in ("1º MEC", "PAP"):
                var.set(True)

        # Clica em Aplicar
        dialogo._ao_aplicar()
        app_root.update()

        # Verifica efeitos
        assert len(aplicados) == 1
        assert "1º MEC" in aplicados[0]
        assert "PAP" in aplicados[0]


def test_dialogo_filtro_turmas_horario_livre(app_root, ambiente_gui, mock_messagebox, tmp_path, monkeypatch):
    """Testa a ativação e persistência da opção Horário Livre via DialogoFiltroTurmas."""
    import registro.nucleo.constants as constants

    monkeypatch.setattr(constants, "CAMINHO_SESSAO", tmp_path / "session.json")
    facade = ambiente_gui["facade"]
    assert facade.ignorar_horario_grade is False

    with patch.object(DialogoFiltroTurmas, "grab_set"), \
         patch.object(DialogoFiltroTurmas, "transient"), \
         patch.object(DialogoFiltroTurmas, "deiconify"), \
         patch.object(DialogoFiltroTurmas, "_centralizar_janela"):

        dialogo = DialogoFiltroTurmas(
            parent=app_root,
            fachada_nucleo=facade,
            callback_aplicar=lambda selec: None,
        )
        app_root.update()

        assert dialogo._var_ignorar_horario.get() is False
        dialogo._var_ignorar_horario.set(True)
        dialogo._ao_aplicar()
        app_root.update()

        assert facade.ignorar_horario_grade is True


# ============================================================================
# 2. Testes de DialogoSessao (Edição de Sessão Ativa)
# ============================================================================


def test_dialogo_sessao_editar_sessao_ativa(app_root, ambiente_gui, mock_messagebox):
    """Testa aba de edição da sessão ativa, modificando turmas e item servido."""
    facade = ambiente_gui["facade"]
    app_root.fachada_nucleo = facade

    with patch.object(DialogoSessao, "grab_set"), \
         patch.object(DialogoSessao, "transient"), \
         patch.object(DialogoSessao, "deiconify"), \
         patch.object(DialogoSessao, "_centralizar_janela"):

        dialogo = DialogoSessao(
            title="Sessão",
            callback=lambda sid: True,
            parente_app=app_root,
        )
        app_root.update()

        # 1. Como há sessão ativa no início, a aba ativa inicial é 'Editar Sessão Ativa'
        assert dialogo._sessao_ativa_info is not None
        assert dialogo._combobox_lanche_editar is not None

        # 2. Altera item servido no combobox
        dialogo._combobox_lanche_editar.set("Salada de Frutas Especial")

        # 3. Limpa turmas e tenta salvar -> deve disparar aviso
        dialogo._ao_limpar_turmas(modo_edicao=True)
        dialogo._processar_editar_sessao()
        app_root.update()
        assert len(mock_messagebox.warning_calls) > 0
        assert any("Selecione pelo menos uma turma" in str(c) for c in mock_messagebox.warning_calls)

        # 4. Seleciona apenas 2º BEM e salva
        for nome, var, _ in dialogo._dados_checkbox_turmas_editar:
            if nome == "2º BEM":
                var.set(True)

        dialogo._processar_editar_sessao()
        app_root.update()

        # 5. Verifica se as alterações foram salvas na fachada e no banco
        detalhes = facade.obter_detalhes_sessao_ativa()
        assert detalhes["item_servido"] == "Salada de Frutas Especial"
        assert set(detalhes["grupos"]) == {"2º BEM"}


def test_grade_do_dia_com_coringa_seleciona_todas_turmas_e_categorias(
    app_root, ambiente_gui, mock_messagebox, tmp_path, monkeypatch
):
    """Garante que '*' / '*' na grade preenche todas as turmas e categorias nos diálogos."""
    facade = ambiente_gui["facade"]
    facade.criar_grupo("PAP", tipo="categoria")
    app_root.fachada_nucleo = facade

    caminho_grade = tmp_path / "grade_coringa_gui.json"
    grade = {
        "terca": {
            "almoco": [
                {"inicio": "11:30", "fim": "13:30", "turmas": ["*"], "categorias": ["*"]}
            ],
            "lanche": [
                {"inicio": "09:30", "fim": "10:00", "turmas": ["*"], "categorias": ["*"]}
            ],
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho_grade)
    monkeypatch.setattr(grade_horarios_service, "CAMINHO_GRADE_HORARIOS", caminho_grade)
    monkeypatch.setattr(grade_horarios_service, "obter_dia_semana_atual", lambda: "terca")

    with patch.object(DialogoFiltroTurmas, "grab_set"), \
         patch.object(DialogoFiltroTurmas, "transient"), \
         patch.object(DialogoFiltroTurmas, "deiconify"), \
         patch.object(DialogoFiltroTurmas, "_centralizar_janela"):

        dialogo_filtro = DialogoFiltroTurmas(
            parent=app_root,
            fachada_nucleo=facade,
            callback_aplicar=lambda s: None,
        )
        app_root.update()

        dialogo_filtro._ao_limpar_todas()
        dialogo_filtro._ao_selecionar_grade()
        app_root.update()

        assert mock_messagebox.info_calls == []
        marcados_filtro = {
            ident
            for ident, var, _ in dialogo_filtro._dados_checkbox
            if var.get() and not ident.startswith("#")
        }
        assert {"1º BEM", "2º BEM", "1º MEC", "PAP"}.issubset(marcados_filtro)
        dialogo_filtro.destroy()

    with patch.object(DialogoSessao, "grab_set"), \
         patch.object(DialogoSessao, "transient"), \
         patch.object(DialogoSessao, "deiconify"), \
         patch.object(DialogoSessao, "_centralizar_janela"):

        dialogo_sessao = DialogoSessao(
            title="Sessão",
            callback=lambda sid: True,
            parente_app=app_root,
        )
        app_root.update()

        dialogo_sessao._notebook.select(1)
        dialogo_sessao._combobox_refeicao.set("Almoço")
        dialogo_sessao._ao_limpar_turmas(modo_edicao=False)
        dialogo_sessao._ao_selecionar_grade_do_dia(modo_edicao=False)
        app_root.update()

        assert mock_messagebox.info_calls == []
        marcados_sessao = {
            nome for nome, var, _ in dialogo_sessao._dados_checkbox_turmas if var.get()
        }
        assert {"1º BEM", "2º BEM", "1º MEC", "PAP"}.issubset(marcados_sessao)
        dialogo_sessao.destroy()


def test_dialogo_sessao_slots_grade_busca_e_horario_livre(
    app_root, ambiente_gui, mock_messagebox, tmp_path, monkeypatch
):
    """Valida clique em slot da grade, filtro de busca, Com Reserva e Horário Livre."""
    facade = ambiente_gui["facade"]
    app_root.fachada_nucleo = facade

    caminho_grade = tmp_path / "grade_slots_gui.json"
    grade = {
        "quarta": {
            "almoco": [
                {"inicio": "11:30", "fim": "12:00", "turmas": ["1º BEM"], "categorias": []},
                {"inicio": "12:00", "fim": "12:30", "turmas": ["1º MEC"], "categorias": []},
            ]
        }
    }
    grade_horarios_service.salvar_grade_horarios(grade, caminho_grade)
    monkeypatch.setattr(grade_horarios_service, "CAMINHO_GRADE_HORARIOS", caminho_grade)
    monkeypatch.setattr(grade_horarios_service, "obter_dia_semana_atual", lambda: "quarta")

    with patch.object(DialogoSessao, "grab_set"), \
         patch.object(DialogoSessao, "transient"), \
         patch.object(DialogoSessao, "deiconify"), \
         patch.object(DialogoSessao, "_centralizar_janela"):

        dialogo = DialogoSessao(
            title="Sessão",
            callback=lambda res: True,
            parente_app=app_root,
        )
        app_root.update()

        # Muda para aba Nova Sessão e seleciona Almoço
        dialogo._notebook.select(1)
        dialogo._combobox_refeicao.set("Almoço")
        dialogo._ao_alterar_data_ou_refeicao(aplicar_grade=True)
        app_root.update()

        # Deve ter marcado todas as turmas da grade do dia (1º BEM e 1º MEC)
        marcados = {n for n, v, _ in dialogo._dados_checkbox_turmas if v.get()}
        assert marcados == {"1º BEM", "1º MEC"}

        # Clicar no 2º slot deve filtrar apenas 1º MEC
        dialogo._ao_clicar_slot_grade(modo_edicao=False, idx=1)
        app_root.update()
        marcados_slot = {n for n, v, _ in dialogo._dados_checkbox_turmas if v.get()}
        assert marcados_slot == {"1º MEC"}
        assert dialogo._contextos["nova"]["slot_selecionado_idx"] == 1

        # Voltar para todos os horários da grade
        dialogo._ao_selecionar_grade_do_dia(modo_edicao=False)
        app_root.update()
        assert dialogo._contextos["nova"]["slot_selecionado_idx"] is None
        marcados_todos = {n for n, v, _ in dialogo._dados_checkbox_turmas if v.get()}
        assert marcados_todos == {"1º BEM", "1º MEC"}

        # Busca textual filtra checkboxes visíveis mantendo estado
        dialogo._contextos["nova"]["var_busca"].set("MEC")
        dialogo._filtrar_checkboxes(modo_edicao=False)
        visiveis = [
            nome
            for nome, cb, _sec in dialogo._contextos["nova"]["widgets_turma"]
            if cb.winfo_manager() != ""
        ]
        assert visiveis == ["1º MEC"]

        # Limpar busca restaura visibilidade
        dialogo._limpar_busca_turmas(modo_edicao=False)
        visiveis_apos = [
            nome
            for nome, cb, _sec in dialogo._contextos["nova"]["widgets_turma"]
            if cb.winfo_manager() != ""
        ]
        assert len(visiveis_apos) == 4

        # Horário Livre na aba Editar persiste na fachada ao salvar
        dialogo._notebook.select(0)
        dialogo._contextos["editar"]["var_horario_livre"].set(True)
        dialogo._processar_editar_sessao()
        app_root.update()
        assert facade.ignorar_horario_grade is True


def test_dialogo_sessao_com_reserva_e_busca_carregar(
    app_root, ambiente_gui, criar_estudante, criar_reserva, mock_messagebox
):
    """Valida atalho 'Com Reserva' e filtro/colunas na aba Carregar Sessão Existente."""
    facade = ambiente_gui["facade"]
    g_ads = ambiente_gui["grupos"][3]  # ADS
    est = criar_estudante(prontuario="IQ90001", nome="Aluno ADS", ativo=True, grupos=[g_ads])
    criar_reserva(estudante=est, data="15/11/2026", almoco=True, jantar=False, cancelada=False)
    app_root.fachada_nucleo = facade

    with patch.object(DialogoSessao, "grab_set"), \
         patch.object(DialogoSessao, "transient"), \
         patch.object(DialogoSessao, "deiconify"), \
         patch.object(DialogoSessao, "_centralizar_janela"):

        dialogo = DialogoSessao(
            title="Sessão",
            callback=lambda res: True,
            parente_app=app_root,
        )
        app_root.update()

        dialogo._notebook.select(1)
        dialogo._entrada_data.entry.delete(0, "end")
        dialogo._entrada_data.entry.insert(0, "15/11/2026")
        dialogo._combobox_refeicao.set("Almoço")
        dialogo._ao_alterar_data_ou_refeicao(aplicar_grade=False)
        dialogo._ao_selecionar_com_reserva(modo_edicao=False)
        app_root.update()

        marcados = {n for n, v, _ in dialogo._dados_checkbox_turmas if v.get()}
        assert marcados == {"ADS"}

        # Valida aba Carregar Sessão Existente (colunas + filtro)
        dialogo._notebook.select(2)
        assert len(dialogo._todas_sessoes_linhas) >= 1
        dialogo._var_busca_sessoes.set("Fruta")
        dialogo._filtrar_treeview_sessoes()
        iids_fruta = dialogo._treeview_sessoes.obter_iids_filhos()
        assert len(iids_fruta) == 1

        dialogo._var_busca_sessoes.set("InexistenteXYZ")
        dialogo._filtrar_treeview_sessoes()
        assert len(dialogo._treeview_sessoes.obter_iids_filhos()) == 0

        dialogo.destroy()
