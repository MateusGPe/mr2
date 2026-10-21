"""
Testes unitários para o módulo registro.nucleo.google_api_service com mocks completos.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound
from requests.exceptions import RequestException

from registro.nucleo.exceptions import ErroAPIGoogle
import registro.nucleo.google_api_service as gas


def test_chave_identificadora_linha():
    """Testa geração de chave de identificação de linha."""
    # Menos de 4 itens
    curta = ["IQ30001", "Maria"]
    assert gas._chave_identificadora_linha(curta) == ("IQ30001", "Maria")

    # 4 ou mais itens -> primeiros 2 + últimos 2
    longa = ["IQ30001", "Maria", "Turma A", "Almoço", "12:00"]
    assert gas._chave_identificadora_linha(longa) == ("IQ30001", "Maria", "Almoço", "12:00")


def test_obter_credenciais_token_valido(tmp_path: Path):
    """Testa obtenção de credenciais quando token existe e é válido."""
    caminho_token = tmp_path / "token.json"
    caminho_token.write_text("{}", encoding="utf-8")

    mock_creds = MagicMock()
    mock_creds.valid = True

    with patch.object(gas.Credentials, "from_authorized_user_file", return_value=mock_creds):
        creds = gas._obter_credenciais(caminho_token, tmp_path / "cred.json")
        assert creds == mock_creds


def test_obter_credenciais_token_expirado_com_refresh(tmp_path: Path):
    """Testa refresh de credenciais quando token expirou mas possui refresh_token."""
    caminho_token = tmp_path / "token.json"
    caminho_token.write_text("{}", encoding="utf-8")

    mock_creds = MagicMock()
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = "token123"
    mock_creds.to_json.return_value = '{"refreshed": true}'

    with patch.object(gas.Credentials, "from_authorized_user_file", return_value=mock_creds):
        creds = gas._obter_credenciais(caminho_token, tmp_path / "cred.json")
        mock_creds.refresh.assert_called_once()
        assert creds == mock_creds


def test_obter_credenciais_refresh_falha(tmp_path: Path):
    """Testa falha ao tentar atualizar token expirado."""
    caminho_token = tmp_path / "token.json"
    caminho_token.write_text("{}", encoding="utf-8")

    mock_creds = MagicMock()
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = "token123"
    mock_creds.refresh.side_effect = Exception("Erro rede")

    with patch.object(gas.Credentials, "from_authorized_user_file", return_value=mock_creds):
        with pytest.raises(ErroAPIGoogle, match="Falha ao atualizar token"):
            gas._obter_credenciais(caminho_token, tmp_path / "cred.json")


def test_obter_credenciais_fluxo_oauth_sucesso(tmp_path: Path):
    """Testa fluxo OAuth quando não há token salvo."""
    caminho_token = tmp_path / "subdir" / "token.json"
    caminho_creds = tmp_path / "credentials.json"
    caminho_creds.write_text("{}", encoding="utf-8")

    mock_flow = MagicMock()
    mock_creds = MagicMock()
    mock_creds.to_json.return_value = '{"access": "ok"}'
    mock_flow.run_local_server.return_value = mock_creds

    with patch.object(gas.InstalledAppFlow, "from_client_secrets_file", return_value=mock_flow):
        creds = gas._obter_credenciais(caminho_token, caminho_creds)
        assert creds == mock_creds
        assert caminho_token.exists()


def test_obter_credenciais_arquivo_credenciais_nao_encontrado(tmp_path: Path):
    """Testa erro quando credentials.json não existe."""
    caminho_token = tmp_path / "token.json"
    caminho_creds = tmp_path / "nao_existe.json"

    with pytest.raises(ErroAPIGoogle, match="Arquivo de credenciais não encontrado"):
        gas._obter_credenciais(caminho_token, caminho_creds)


def test_google_sheets_service_inicializacao_e_erros():
    """Testa inicialização do GoogleSheetsService e tratamento de exceções."""
    # Sucesso
    with patch("registro.nucleo.google_api_service._obter_credenciais") as mock_obter_c, \
         patch("gspread.authorize") as mock_auth:
        mock_cliente = MagicMock()
        mock_auth.return_value = mock_cliente
        mock_planilha = MagicMock()
        mock_cliente.open_by_key.return_value = mock_planilha

        service = gas.GoogleSheetsService("fake_key")
        assert service.planilha == mock_planilha

    # SpreadsheetNotFound
    with patch("registro.nucleo.google_api_service._obter_credenciais"), \
         patch("gspread.authorize") as mock_auth:
        mock_cliente = MagicMock()
        mock_auth.return_value = mock_cliente
        mock_cliente.open_by_key.side_effect = SpreadsheetNotFound()

        with pytest.raises(ErroAPIGoogle, match="Falha ao abrir planilha"):
            gas.GoogleSheetsService("fake_key")

    # Erro genérico
    with patch("registro.nucleo.google_api_service._obter_credenciais", side_effect=RuntimeError("Boom")):
        with pytest.raises(ErroAPIGoogle, match="Erro inesperado na inicialização"):
            gas.GoogleSheetsService("fake_key")


def test_google_sheets_service_ler_aba_completa():
    """Testa a leitura de aba completa no GoogleSheetsService."""
    with patch("registro.nucleo.google_api_service._obter_credenciais"), \
         patch("gspread.authorize") as mock_auth:
        mock_cliente = MagicMock()
        mock_auth.return_value = mock_cliente
        mock_planilha = MagicMock()
        mock_aba = MagicMock()
        mock_aba.get_all_values.return_value = [["h1", "h2"], ["v1", "v2"]]
        mock_planilha.worksheet.return_value = mock_aba
        mock_cliente.open_by_key.return_value = mock_planilha

        service = gas.GoogleSheetsService("fake_key")
        valores = service.ler_aba_completa("Discentes")
        assert len(valores) == 2
        assert valores[0] == ["h1", "h2"]

        # Erro WorksheetNotFound
        mock_planilha.worksheet.side_effect = WorksheetNotFound()
        with pytest.raises(ErroAPIGoogle, match="Falha ao ler dados da aba"):
            service.ler_aba_completa("Inexistente")


def test_google_sheets_service_anexar_linhas_unicas():
    """Testa anexar linhas únicas no GoogleSheetsService evitando duplicatas."""
    with patch("registro.nucleo.google_api_service._obter_credenciais"), \
         patch("gspread.authorize") as mock_auth:
        mock_cliente = MagicMock()
        mock_auth.return_value = mock_cliente
        mock_planilha = MagicMock()
        mock_aba = MagicMock()
        # Linha existente no sheet: IQ30001, Maria, Almoço, 12:00
        mock_aba.get_all_values.return_value = [
            ["IQ30001", "Maria", "Turma A", "Almoço", "12:00"]
        ]
        mock_planilha.worksheet.return_value = mock_aba
        mock_cliente.open_by_key.return_value = mock_planilha

        service = gas.GoogleSheetsService("fake_key")

        linhas_novas = [
            ["IQ30001", "Maria", "Turma A", "Almoço", "12:00"],  # Duplicada
            ["IQ30002", "João", "Turma B", "Almoço", "12:05"],   # Nova
        ]
        inseridas = service.anexar_linhas_unicas("Consumos", linhas_novas)
        assert inseridas == 1
        mock_aba.append_rows.assert_called_once()

        # Erro APIError
        mock_aba.append_rows.side_effect = RequestException("Timeout")
        with pytest.raises(ErroAPIGoogle, match="Falha ao anexar linhas"):
            service.anexar_linhas_unicas("Consumos", [["IQ30003", "Ana", "Turma A", "Almoço", "12:10"]])


def test_obter_servico_planilha_padrao_e_erros(monkeypatch, tmp_path: Path):
    """Testa a leitura do arquivo spreadsheet.json para instanciar o serviço padrão."""
    # Sucesso
    caminho_json = tmp_path / "spreadsheet.json"
    caminho_json.write_text(json.dumps({"key": "minha_chave_123"}), encoding="utf-8")
    monkeypatch.setattr(gas, "CAMINHO_PLANILHA_JSON", caminho_json)

    with patch("registro.nucleo.google_api_service.GoogleSheetsService") as mock_gss:
        gas.obter_servico_planilha_padrao()
        mock_gss.assert_called_once_with("minha_chave_123")

    # Arquivo inexistente
    monkeypatch.setattr(gas, "CAMINHO_PLANILHA_JSON", tmp_path / "inexistente.json")
    with pytest.raises(ErroAPIGoogle, match="Falha ao ler config 'spreadsheet.json'"):
        gas.obter_servico_planilha_padrao()


def test_obter_planilha(monkeypatch):
    """Testa a função de conveniência obter_planilha com e sem sheet_key."""
    # Com sheet_key explícita
    with patch("registro.nucleo.google_api_service.GoogleSheetsService") as mock_gss:
        mock_inst = MagicMock()
        mock_gss.return_value = mock_inst
        res = gas.obter_planilha(sheet_key="chave_especifica")
        assert res == mock_inst.planilha

    # Sem sheet_key (singleton)
    gas._ServicoPadrao._instance = None
    with patch("registro.nucleo.google_api_service.obter_servico_planilha_padrao") as mock_obter_padrao:
        mock_inst2 = MagicMock()
        mock_obter_padrao.return_value = mock_inst2
        res2 = gas.obter_planilha()
        assert res2 == mock_inst2.planilha
        # Segunda chamada deve reutilizar singleton
        gas.obter_planilha()
        assert mock_obter_padrao.call_count == 1


def test_buscar_valores_aba_e_anexar_linhas_unicas_funcoes():
    """Testa as funções de módulo buscar_valores_aba e anexar_linhas_unicas."""
    mock_planilha = MagicMock()
    mock_aba = MagicMock()
    mock_planilha.worksheet.return_value = mock_aba
    mock_aba.get_all_values.return_value = [["A", "B", "C", "D"]]

    # buscar_valores_aba sucesso
    valores = gas.buscar_valores_aba(mock_planilha, "Aba1")
    assert valores == [["A", "B", "C", "D"]]

    # buscar_valores_aba erro
    mock_planilha.worksheet.side_effect = WorksheetNotFound()
    with pytest.raises(ErroAPIGoogle, match="Falha ao buscar dados da aba"):
        gas.buscar_valores_aba(mock_planilha, "Aba1")

    # anexar_linhas_unicas modulo sucesso e erro
    mock_planilha.worksheet.side_effect = None
    mock_aba.get_all_values.return_value = [["A", "B", "C", "D"]]
    novas = [["A", "B", "C", "D"], ["X", "Y", "Z", "W"]]
    count = gas.anexar_linhas_unicas(mock_planilha, novas, "Aba1")
    assert count == 1

    mock_aba.append_rows.side_effect = RequestException("Falha conexao")
    with pytest.raises(ErroAPIGoogle, match="Falha ao adicionar linhas"):
        gas.anexar_linhas_unicas(mock_planilha, [["1", "2", "3", "4"]], "Aba1")
