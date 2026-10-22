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

from registro.gui.registrar.dialogo_sessao import DialogoSessao
from registro.gui.registrar.dialogo_filtro_turmas import DialogoFiltroTurmas
from registro.gui.registrar.painel_acao_busca import PainelAcaoBusca
from registro.gui.registrar.painel_status_registrados import PainelStatusRegistrados
from registro.gui.painel.abas.aba_dashboard import AbaDashboard
from registro.gui.painel.abas.aba_importacao import AbaImportacao
from registro.gui.painel.abas.aba_reservas import AbaReservas


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


def test_frame_self_service_inicializacao(app_root, mock_fachada):
    """Testa a instanciação e métodos do FrameSelfService no totem de autoatendimento."""
    from registro.gui.autoatendimento.app import FrameSelfService

    callback_mock = MagicMock()
    with patch.object(FrameSelfService, "_iniciar_camera"):
        frame = FrameSelfService(
            master=app_root,
            fachada=mock_fachada,
            notification_callback=callback_mock,
        )
        assert frame is not None
        assert hasattr(frame, "focar_entrada")
        assert hasattr(frame, "recarregar_sessao")

        # Teste de formatação de matrícula
        assert FrameSelfService.formatar_matricula("12345") == "IQ3012345"
        assert FrameSelfService.formatar_matricula("IQ3000123") == "IQ3000123"

        frame.recarregar_sessao()
        frame.incrementar_contador()

        # Testar atualização consistente de cores dos itens no feedback visual
        frame._definir_feedback_visual("sucesso")
        assert frame._lbl_status["text"] == "REGISTRADO COM SUCESSO!"
        assert frame._frame_estudante["bg"] == frame.COR_FUNDO_SUCESSO
        assert frame._lbl_prato["fg"] == "#FEF08A"

        frame._definir_feedback_visual("erro")
        assert frame._lbl_status["text"] == "ATENÇÃO: NÃO AUTORIZADO"
        assert frame._frame_estudante["bg"] == frame.COR_FUNDO_ERRO
        assert frame._lbl_mensagem["fg"] == "#FEF08A"

        frame._definir_feedback_visual("padrao")
        assert frame._lbl_status["text"] == "Aguardando Leitura..."
        assert frame._frame_estudante["bg"] == frame.COR_FUNDO_PADRAO
        assert frame._lbl_prato["fg"] == "#93C5FD"

        frame.stop()
        frame.destroy()


def test_autoatendimento_dashboard_e_consumos(app_root, mock_fachada):
    """Testa as abas de Dashboard e Consumos do autoatendimento com troca dinâmica de sessão."""
    from registro.gui.autoatendimento.app import AbaDashboard as AbaDashAuto, AbaConsumos as AbaConsAuto

    mock_fachada.obter_estudantes_para_sessao.return_value = [
        {"pront": "IQ30001", "nome": "Aluno Teste", "turma": "1INFO", "hora_consumo": "12:05", "prato": "Almoço"}
    ]

    dash = AbaDashAuto(master=app_root, fachada=mock_fachada, id_sessao=1)
    assert dash is not None
    dash.definir_sessao(2)
    dash.destroy()

    consumos = AbaConsAuto(master=app_root, fachada=mock_fachada, id_sessao=1)
    assert consumos is not None
    consumos.definir_sessao(2)
    consumos.adicionar_consumo(("IQ30002", "Outro Aluno", "2INFO", "12:10", "Almoço"))
    consumos.destroy()


