# ----------------------------------------------------------------------------
# Arquivo: tests/test_config_service.py
# ----------------------------------------------------------------------------
"""
Testes unitários para o módulo de configurações, segurança por PIN e utilitários GCP.
"""

from unittest.mock import MagicMock, patch

import pytest

from registro.nucleo import config_service


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Redireciona os caminhos de configuração para diretório temporário isolado."""
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()

    settings_file = cfg_dir / "settings.json"
    lanches_file = cfg_dir / "lanches.json"
    presets_file = cfg_dir / "presets_turmas.json"
    turmas_file = cfg_dir / "turmas_integrado.json"
    mapeamento_file = cfg_dir / "mapeamento_colunas.json"
    spreadsheet_file = cfg_dir / "spreadsheet.json"
    credentials_file = cfg_dir / "credentials.json"
    token_file = cfg_dir / "token.json"

    monkeypatch.setattr(config_service, "DIRETORIO_CONFIG", cfg_dir)
    monkeypatch.setattr(config_service, "CAMINHO_SETTINGS", settings_file)
    monkeypatch.setattr(config_service, "CAMINHO_JSON_LANCHES", lanches_file)
    monkeypatch.setattr(config_service, "CAMINHO_JSON_PRESETS_TURMAS", presets_file)
    monkeypatch.setattr(config_service, "CAMINHO_JSON_TURMAS_INTEGRADO", turmas_file)
    monkeypatch.setattr(config_service, "CAMINHO_JSON_MAPEAMENTO_COLUNAS", mapeamento_file)
    monkeypatch.setattr(config_service, "JSON_ID_PLANILHA", spreadsheet_file)
    monkeypatch.setattr(config_service, "CAMINHO_CREDENCIAS", credentials_file)
    monkeypatch.setattr(config_service, "CAMINHO_TOKEN", token_file)

    return cfg_dir


def test_pin_lifecycle(temp_config_dir):
    # Inicialmente sem PIN
    assert not config_service.tem_pin_configurado()
    assert config_service.verificar_pin("qualquer_coisa") is True

    # Definir PIN
    config_service.definir_pin("1234")
    assert config_service.tem_pin_configurado()
    assert config_service.verificar_pin("1234") is True
    assert config_service.verificar_pin("9999") is False
    assert config_service.verificar_pin("") is False

    # Remover PIN
    config_service.remover_pin()
    assert not config_service.tem_pin_configurado()
    assert config_service.verificar_pin("1234") is True


def test_totem_config_get_and_update(temp_config_dir):
    cfg = config_service.obter_config_totem()
    assert cfg["fullscreen"] is False
    assert cfg["camera_on_start"] is True

    config_service.atualizar_config_totem("fullscreen", True)
    config_service.atualizar_config_totem("feedback_delay_ms", 2500)

    cfg_atualizada = config_service.obter_config_totem()
    assert cfg_atualizada["fullscreen"] is True
    assert cfg_atualizada["feedback_delay_ms"] == 2500


def test_extrair_id_planilha():
    url_completa = "https://docs.google.com/spreadsheets/d/1x78c5OyyzvwQB-El0PjnfOwLYKa4M-MlJVNEWaG_3YQ/edit?gid=0#gid=0"
    id_esperado = "1x78c5OyyzvwQB-El0PjnfOwLYKa4M-MlJVNEWaG_3YQ"
    assert config_service.extrair_id_planilha(url_completa) == id_esperado

    # ID bruto
    assert config_service.extrair_id_planilha("1x78c5OyyzvwQB-El0PjnfOwLYKa4M-MlJVNEWaG_3YQ") == id_esperado
    assert config_service.extrair_id_planilha("  1x78c5OyyzvwQB-El0PjnfOwLYKa4M-MlJVNEWaG_3YQ  ") == id_esperado


def test_salvar_e_obter_id_planilha(temp_config_dir):
    assert config_service.obter_id_planilha() is None

    config_service.salvar_id_planilha("https://docs.google.com/spreadsheets/d/PLANILHA_TESTE_123/edit")
    assert config_service.obter_id_planilha() == "PLANILHA_TESTE_123"


def test_lanches_e_presets(temp_config_dir):
    lanches = ["Maçã", "Suco de Uva"]
    config_service.salvar_lanches(lanches)
    assert config_service.obter_lanches() == lanches

    presets = {"manha": {"seg": ["1A", "1B"]}}
    config_service.salvar_presets_turmas(presets)
    assert config_service.obter_presets_turmas() == presets


def test_salvar_arquivo_credenciais(temp_config_dir, tmp_path):
    origem = tmp_path / "cred_origem.json"
    origem.write_text('{"type": "service_account"}', encoding="utf-8")

    assert config_service.salvar_arquivo_credenciais(origem) is True
    assert config_service.CAMINHO_CREDENCIAS.exists()
    assert "service_account" in config_service.CAMINHO_CREDENCIAS.read_text(encoding="utf-8")


def test_limpar_token(temp_config_dir):
    config_service.CAMINHO_TOKEN.write_text('{"token": "xyz"}', encoding="utf-8")
    assert config_service.CAMINHO_TOKEN.exists()

    assert config_service.limpar_token() is True
    assert not config_service.CAMINHO_TOKEN.exists()


def test_testar_conexao_google_sheets_sem_arquivos(temp_config_dir):
    sucesso, msg = config_service.testar_conexao_google_sheets()
    assert sucesso is False
    assert "credentials.json" in msg

    # Cria credentials mas sem spreadsheet.json
    config_service.CAMINHO_CREDENCIAS.write_text("{}", encoding="utf-8")
    sucesso, msg = config_service.testar_conexao_google_sheets()
    assert sucesso is False
    assert "spreadsheet.json" in msg


def test_inicializar_estrutura_planilha(temp_config_dir):
    # Sem credentials.json
    sucesso, msg, detalhes = config_service.inicializar_estrutura_planilha()
    assert sucesso is False
    assert "credentials.json" in msg

    # Cria credentials mas sem spreadsheet.json
    config_service.CAMINHO_CREDENCIAS.write_text("{}", encoding="utf-8")
    sucesso, msg, detalhes = config_service.inicializar_estrutura_planilha()
    assert sucesso is False
    assert "spreadsheet.json" in msg

    # Com spreadsheet.json e mock do serviço
    config_service.salvar_id_planilha("dummy_sheet_id")
    with patch("registro.nucleo.google_api_service.GoogleSheetsService") as mock_gss:
        mock_inst = MagicMock()
        mock_gss.return_value = mock_inst
        mock_inst.criar_abas_necessarias.return_value = {
            "criadas": ["Almoço"],
            "atualizadas_vazias": ["DB"],
            "mantidas": ["Discentes"],
        }
        sucesso, msg, detalhes = config_service.inicializar_estrutura_planilha()
        assert sucesso is True
        assert "Almoço" in msg
        assert "DB" in msg
        assert "Discentes" in msg
        assert detalhes["criadas"] == ["Almoço"]

    # Com exceção durante a chamada
    with patch("registro.nucleo.google_api_service.GoogleSheetsService", side_effect=RuntimeError("Erro simulado")):
        sucesso, msg, detalhes = config_service.inicializar_estrutura_planilha()
        assert sucesso is False
        assert "Erro simulado" in msg



def test_obter_status_sistema_com_contagem_sql(temp_config_dir, monkeypatch):
    """Garante que obter_status_sistema consulte contagens reais via SQL sem lançar AttributeError."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import registro.nucleo.models as models_mod

    db_path = temp_config_dir / "registro.db"
    engine_tmp = create_engine(f"sqlite:///{db_path}")
    models_mod.Base.metadata.create_all(bind=engine_tmp)
    SessaoTmp = sessionmaker(bind=engine_tmp)

    with SessaoTmp() as s:
        s.add(models_mod.Estudante(prontuario="IQ1001", nome="Teste Status"))
        s.commit()

    monkeypatch.setattr(models_mod, "SessaoLocal", SessaoTmp)

    status = config_service.obter_status_sistema()
    assert status["banco_dados"]["existe"] is True
    assert status["banco_dados"]["total_alunos"] == 1
    assert status["banco_dados"]["total_consumos"] == 0
    engine_tmp.dispose()


def test_turmas_integrado_lifecycle(temp_config_dir):
    """Testa leitura com fallback e persistência de turmas integradas em JSON."""
    # Inicialmente o arquivo não existe no temp_config_dir -> fallback para padrão
    turmas_padrao = config_service.obter_turmas_integrado()
    assert isinstance(turmas_padrao, list)
    assert len(turmas_padrao) > 0
    assert "1º A - MAC" in turmas_padrao

    # Salva nova lista
    novas_turmas = ["Turma X", "Turma Y"]
    config_service.salvar_turmas_integrado(novas_turmas)

    # Lê novamente
    carregadas = config_service.obter_turmas_integrado()
    assert carregadas == novas_turmas


def test_mapeamento_colunas_lifecycle(temp_config_dir):
    """Testa leitura com fallback e persistência de mapeamento de colunas em JSON."""
    # Inicialmente o arquivo não existe no temp_config_dir -> fallback para padrão
    mapa_padrao = config_service.obter_mapeamento_colunas()
    assert isinstance(mapa_padrao, dict)
    assert mapa_padrao["matrícula"] == "pront"
    assert mapa_padrao["curso"] == "turma"

    # Salva novo mapeamento
    novo_mapa = {"codigo": "pront", "turma": "turma"}
    config_service.salvar_mapeamento_colunas(novo_mapa)

    carregado = config_service.obter_mapeamento_colunas()
    assert carregado == novo_mapa


def test_config_audio_get_and_totem_camera(temp_config_dir):
    """Testa obtenção de configurações de áudio e índice de câmera do totem."""
    audio_cfg = config_service.obter_config_audio()
    assert audio_cfg["habilitado"] is True
    assert audio_cfg["freq_sucesso"] == 1000
    assert audio_cfg["dur_sucesso_ms"] == 200

    totem_cfg = config_service.obter_config_totem()
    assert totem_cfg.get("camera_index", 0) == 0
