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
    """Testa a aplicação de filtros alterando categoria para PAP e selecionando turmas."""
    facade = ambiente_gui["facade"]
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

        # 1. Altera categoria para PAP
        dialogo._var_categoria.set("PAP")

        # 2. Seleciona apenas 1º MEC
        dialogo._ao_limpar_todas()
        for ident, var, _ in dialogo._dados_checkbox:
            if ident == "1º MEC":
                var.set(True)

        # 3. Clica em Aplicar
        dialogo._ao_aplicar()
        app_root.update()

        # Verifica efeitos
        assert len(aplicados) == 1
        assert "1º MEC" in aplicados[0]
        assert facade.filtro_categoria_sessao == "PAP"


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
