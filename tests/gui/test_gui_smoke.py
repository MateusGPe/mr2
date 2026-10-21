# ----------------------------------------------------------------------------
# Arquivo: tests/gui/test_gui_smoke.py
# ----------------------------------------------------------------------------
"""
Testes de fumaça (smoke tests) para componentes e diálogos da interface gráfica (GUI).

Garante que diálogos, painéis e abas possam ser instanciados e inicializados sem
erros de referências indefinidas (NameError), atributos inexistentes ou falhas
de integração entre a GUI e a Fachada.
"""

import tkinter as tk
from unittest.mock import MagicMock, patch
import pytest

from registro.gui.dialogo_sessao import DialogoSessao
from registro.gui.dialogo_filtro_turmas import DialogoFiltroTurmas
from registro.gui.painel_acao_busca import PainelAcaoBusca
from registro.gui.painel_status_registrados import PainelStatusRegistrados
from registro.abas.aba_dashboard import AbaDashboard
from registro.abas.aba_importacao import AbaImportacao
from registro.abas.aba_reservas import AbaReservas


@pytest.fixture(scope="module")
def app_root():
    """Cria uma raiz Tk ocultada para permitir a instanciação de widgets nos testes."""
    try:
        root = tk.Tk()
        root.withdraw()
        yield root
        try:
            root.destroy()
        except Exception:
            pass
    except tk.TclError:
        pytest.skip("Ambiente sem display Tkinter disponível")


@pytest.fixture
def mock_fachada():
    """Fachada mockada com métodos comuns necessários para a renderização da GUI."""
    fachada = MagicMock()
    fachada.listar_todas_sessoes.return_value = []
    fachada.listar_estudantes.return_value = []
    fachada.listar_estudantes_fuzzy.return_value = []
    fachada.listar_reservas.return_value = []
    fachada.listar_consumos_por_sessao.return_value = []
    fachada.obter_estatisticas_dashboard.return_value = {
        "alunos_ativos": 100,
        "refeicoes_servidas_hoje": 50,
        "reservas_ativas": 30,
    }
    fachada.id_sessao_ativa = 1
    fachada.obter_sessao_ativa.return_value = {
        "id": 1,
        "refeicao": "almoço",
        "data": "21/10/2026",
        "hora": "12:00",
    }
    return fachada


def test_dialogo_sessao_inicializacao(app_root, mock_fachada):
    """Testa a instanciação do DialogoSessao e seus métodos de carregamento de presets e opções."""
    app_root.get_fachada = MagicMock(return_value=mock_fachada)

    with patch.object(DialogoSessao, "grab_set"), \
         patch.object(DialogoSessao, "transient"), \
         patch.object(DialogoSessao, "deiconify"), \
         patch.object(DialogoSessao, "_centralizar_janela"):
        dialogo = DialogoSessao(
            title="Teste Sessão",
            callback=lambda res: True,
            parente_app=app_root,
        )
        assert dialogo is not None

        # Verifica se os métodos internos executaram com sucesso
        opcoes, lista = dialogo._carregar_opcoes_lanche()
        assert isinstance(opcoes, set)
        assert isinstance(lista, list)

        dialogo._carregar_presets_turmas()
        assert hasattr(dialogo, "_presets_turmas")

        dialogo.destroy()


def test_dialogo_filtro_turmas_inicializacao(app_root, mock_fachada):
    """Testa a instanciação do DialogoFiltroTurmas."""
    with patch.object(DialogoFiltroTurmas, "grab_set"), \
         patch.object(DialogoFiltroTurmas, "transient"), \
         patch.object(DialogoFiltroTurmas, "deiconify"):
        dialogo = DialogoFiltroTurmas(
            parent=app_root,
            fachada_nucleo=mock_fachada,
            callback_aplicar=lambda t: None,
        )
        assert dialogo is not None
        dialogo.destroy()


def test_painel_acao_busca_inicializacao(app_root, mock_fachada):
    """Testa a instanciação do PainelAcaoBusca."""
    app_root.colors = {}
    painel = PainelAcaoBusca(master=app_root, app=app_root, fachada_nucleo=mock_fachada)
    assert painel is not None
    painel.destroy()


def test_painel_status_registrados_inicializacao(app_root, mock_fachada):
    """Testa a instanciação do PainelStatusRegistrados."""
    app_root.colors = {}
    painel = PainelStatusRegistrados(master=app_root, app=app_root, fachada_nucleo=mock_fachada)
    assert painel is not None
    painel.destroy()


def test_aba_dashboard_inicializacao(app_root, mock_fachada):
    """Testa a instanciação da AbaDashboard."""
    aba = AbaDashboard(parent=app_root, fachada_nucleo=mock_fachada)
    assert aba is not None
    aba.destroy()


def test_aba_importacao_inicializacao(app_root, mock_fachada):
    """Testa a instanciação da AbaImportacao."""
    aba = AbaImportacao(parent=app_root, fachada_nucleo=mock_fachada)
    assert aba is not None
    aba.destroy()


def test_aba_reservas_inicializacao(app_root, mock_fachada):
    """Testa a instanciação da AbaReservas."""
    aba = AbaReservas(parent=app_root, fachada_nucleo=mock_fachada)
    assert aba is not None
    aba.destroy()
