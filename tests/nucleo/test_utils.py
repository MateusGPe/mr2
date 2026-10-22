"""
Testes unitários para o módulo registro.nucleo.utils.
"""

from pathlib import Path
import platform
import pytest

from registro.nucleo.utils import (
    para_codigo,
    obter_caminho_documentos,
    salvar_csv,
    encontrar_melhor_par_correspondente,
    capitalizar_com_excecoes,
    ajustar_chaves_e_valores,
)


def test_para_codigo():
    """Testa a conversão de prontuário para código alfanumérico simplificado."""
    # IQ3000001 -> remove IQ30000 -> 1 -> b
    resultado = para_codigo("IQ3000001")
    assert "id" in resultado
    assert isinstance(resultado["id"], str)

    # Testando com dígitos diretos
    res_digitos = para_codigo("123")
    assert res_digitos["id"] == "b c d"


def test_obter_caminho_documentos_windows(monkeypatch):
    """Testa a obtenção do caminho da pasta Documentos no Windows."""
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    caminho = obter_caminho_documentos()
    assert isinstance(caminho, Path)
    assert caminho.name == "Documents" or "Document" in str(caminho)


def test_obter_caminho_documentos_windows_fallback(monkeypatch):
    """Testa o fallback para Home/Documents se falhar a chamada ctypes no Windows."""
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    # Mocking ctypes to raise AttributeError
    import ctypes
    monkeypatch.setattr(ctypes, "windll", None)
    caminho = obter_caminho_documentos()
    assert caminho == Path.home() / "Documents"


def test_obter_caminho_documentos_linux_xdg(monkeypatch):
    """Testa a obtenção do caminho da pasta Documentos no Linux com XDG_DOCUMENTS_DIR."""
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_DOCUMENTS_DIR", "/custom/docs")
    caminho = obter_caminho_documentos()
    assert caminho == Path("/custom/docs")


def test_obter_caminho_documentos_linux_fallback(monkeypatch):
    """Testa a obtenção do caminho no Linux sem variável de ambiente XDG."""
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.delenv("XDG_DOCUMENTS_DIR", raising=False)
    caminho = obter_caminho_documentos()
    assert caminho == Path.home() / "Documents"


def test_salvar_csv_sucesso(tmp_path):
    """Testa a escrita com sucesso de uma lista de listas para CSV."""
    caminho_csv = tmp_path / "saida.csv"
    dados = [
        ["col1", "col2"],
        ["val1", "val2"],
        ["val3", "val4"],
    ]
    sucesso = salvar_csv(dados, caminho_csv)
    assert sucesso is True
    assert caminho_csv.exists()
    conteudo = caminho_csv.read_text(encoding="utf-8")
    assert "col1,col2" in conteudo
    assert "val1,val2" in conteudo


def test_salvar_csv_falha(tmp_path):
    """Testa a falha ao tentar salvar CSV em diretório inexistente/inválido."""
    caminho_invalido = tmp_path / "diretorio_nao_existente" / "sub" / "arquivo.csv"
    sucesso = salvar_csv([["a", "b"]], caminho_invalido)
    assert sucesso is False


def test_encontrar_melhor_par_correspondente():
    """Testa o algoritmo de busca por melhor par ponderado."""
    # Lista vazia
    par, score = encontrar_melhor_par_correspondente(("alvo1", "alvo2"), [])
    assert par is None
    assert score == 0

    vetor = [
        ("IQ3000001", "João Silva"),
        ("IQ3000002", "Maria Santos"),
        ("IQ3000003", "José Oliveira"),
    ]

    # Busca próxima
    melhor_par, pontuacao = encontrar_melhor_par_correspondente(
        ("IQ3000002", "Maria Santos"), vetor
    )
    assert melhor_par == ("IQ3000002", "Maria Santos")
    assert pontuacao == 100

    # Busca com pequena divergência
    melhor_par2, pontuacao2 = encontrar_melhor_par_correspondente(
        ("IQ3000002", "Maria Santo"), vetor
    )
    assert melhor_par2 == ("IQ3000002", "Maria Santos")
    assert pontuacao2 > 80


def test_capitalizar_com_excecoes():
    """Testa capitalização com exceções de conectivos."""
    assert capitalizar_com_excecoes("") == ""
    assert capitalizar_com_excecoes("   ") == ""
    assert capitalizar_com_excecoes("de") == "de"
    assert capitalizar_com_excecoes("DE") == "de"
    assert capitalizar_com_excecoes("com") == "com"
    assert capitalizar_com_excecoes("maria") == "Maria"
    assert capitalizar_com_excecoes("SILVA") == "Silva"


def test_ajustar_chaves_e_valores():
    """Testa o ajuste e sanitização de dicionários com chaves mapeadas e regras de negócio."""
    dado_bruto = {
        "  MATRÍCULA IQ  ": "iq2300001",
        "  NOME  ": "joão da silva",
        "REFEIÇÃO": "arroz com feijão",
        "TURMA": " 1º A - INFO ",
        "NUMERICO": 123,
    }
    ajustado = ajustar_chaves_e_valores(dado_bruto)

    assert ajustado["pront"] == "IQ3000001"
    assert ajustado["nome"] == "João da Silva"
    assert ajustado["prato"] == "Arroz com Feijão"
    assert ajustado["turma"] == "1º A - INFO"
    assert ajustado["numerico"] == 123
