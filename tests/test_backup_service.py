# ----------------------------------------------------------------------------
# Arquivo: tests/test_backup_service.py
# ----------------------------------------------------------------------------
"""
Testes unitários para o módulo de backup, restauração e salvaguardas.
"""

import zipfile

import pytest

from registro.nucleo import backup_service


@pytest.fixture
def temp_backup_env(tmp_path, monkeypatch):
    """Configura ambiente temporário para testes de backup e config."""
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    bkp_dir = tmp_path / "backups"
    bkp_dir.mkdir()

    # Cria alguns arquivos de teste na pasta config
    (cfg_dir / "registro.db").write_text("DADOS_DO_BANCO_SQLITE", encoding="utf-8")
    (cfg_dir / "settings.json").write_text('{"pin_hash": "teste"}', encoding="utf-8")
    (cfg_dir / "spreadsheet.json").write_text('{"key": "abc"}', encoding="utf-8")

    monkeypatch.setattr(backup_service, "DIRETORIO_CONFIG", cfg_dir)
    monkeypatch.setattr(backup_service, "DIRETORIO_BACKUPS", bkp_dir)
    monkeypatch.setattr(backup_service, "URL_BANCO_DADOS", f"sqlite:///{cfg_dir}/registro.db")

    return cfg_dir, bkp_dir


def test_criar_e_listar_backup(temp_backup_env):
    cfg_dir, bkp_dir = temp_backup_env

    # Criação do backup na pasta padrão
    zip_path = backup_service.criar_backup()
    assert zip_path.exists()
    assert zip_path.parent == bkp_dir
    assert zipfile.is_zipfile(zip_path)

    with zipfile.ZipFile(zip_path, "r") as zf:
        nomes = zf.namelist()
        assert "config/registro.db" in nomes
        assert "config/settings.json" in nomes
        assert "config/spreadsheet.json" in nomes

    # Listagem de backups
    lista = backup_service.listar_backups()
    assert len(lista) == 1
    assert lista[0]["nome"] == zip_path.name
    assert lista[0]["caminho"] == zip_path


def test_criar_backup_personalizado(temp_backup_env, tmp_path):
    pasta_custom = tmp_path / "pen_drive"
    zip_path = backup_service.criar_backup(destino_personalizado=pasta_custom)
    assert zip_path.exists()
    assert zip_path.parent == pasta_custom


def test_restaurar_backup(temp_backup_env):
    cfg_dir, bkp_dir = temp_backup_env

    # Cria o backup inicial
    zip_path = backup_service.criar_backup()

    # Modifica os dados locais
    (cfg_dir / "registro.db").write_text("CONTEUDO_ALTERADO", encoding="utf-8")
    (cfg_dir / "settings.json").write_text('{"pin_hash": "modificado"}', encoding="utf-8")

    # Restaura o backup
    sucesso, msg = backup_service.restaurar_backup(zip_path, criar_salvaguarda=True)
    assert sucesso is True
    assert "sucesso" in msg.lower()

    # Verifica se os arquivos voltaram ao estado do backup
    assert (cfg_dir / "registro.db").read_text(encoding="utf-8") == "DADOS_DO_BANCO_SQLITE"
    assert (cfg_dir / "settings.json").read_text(encoding="utf-8") == '{"pin_hash": "teste"}'

    # Verifica se uma salvaguarda prévia foi gerada
    salvaguardas = list(bkp_dir.glob("backup_pre_restauracao_*.zip"))
    assert len(salvaguardas) == 1


def test_excluir_backup(temp_backup_env):
    cfg_dir, bkp_dir = temp_backup_env
    zip_path = backup_service.criar_backup()
    assert zip_path.exists()

    assert backup_service.excluir_backup(zip_path) is True
    assert not zip_path.exists()
    assert backup_service.excluir_backup(zip_path) is False


def test_restaurar_backup_invalido(temp_backup_env, tmp_path):
    falso_zip = tmp_path / "falso.zip"
    falso_zip.write_text("nao_eh_zip", encoding="utf-8")

    sucesso, msg = backup_service.restaurar_backup(falso_zip)
    assert sucesso is False
    assert "não é um arquivo zip" in msg.lower()


def test_criar_backup_ignora_temporarios_e_wal(temp_backup_env):
    cfg_dir, _ = temp_backup_env
    (cfg_dir / "temp.tmp").write_text("tmp", encoding="utf-8")
    (cfg_dir / "app.lock").write_text("lock", encoding="utf-8")
    (cfg_dir / "registro.db-wal").write_text("wal", encoding="utf-8")
    (cfg_dir / "registro.db-shm").write_text("shm", encoding="utf-8")

    zip_path = backup_service.criar_backup()
    with zipfile.ZipFile(zip_path, "r") as zf:
        nomes = set(zf.namelist())
        assert "config/registro.db" in nomes
        assert "config/temp.tmp" not in nomes
        assert "config/app.lock" not in nomes
        assert "config/registro.db-wal" not in nomes
        assert "config/registro.db-shm" not in nomes


def test_listar_backups_diretorio_inexistente(tmp_path):
    assert backup_service.listar_backups(tmp_path / "nao_existe") == []


def test_restaurar_backup_inexistente(temp_backup_env, tmp_path):
    sucesso, msg = backup_service.restaurar_backup(tmp_path / "ausente.zip")
    assert sucesso is False
    assert "não encontrado" in msg.lower()


def test_restaurar_backup_protege_contra_zip_slip(temp_backup_env, tmp_path):
    cfg_dir, _ = temp_backup_env
    zip_malicioso = tmp_path / "malicioso.zip"
    with zipfile.ZipFile(zip_malicioso, "w") as zf:
        zf.writestr("../../fora.txt", "conteudo_seguro_nome_limpo")

    sucesso, _ = backup_service.restaurar_backup(zip_malicioso, criar_salvaguarda=False)
    assert sucesso is True
    assert not (tmp_path / "fora.txt").exists()
    assert (cfg_dir / "fora.txt").read_text(encoding="utf-8") == "conteudo_seguro_nome_limpo"


def test_excluir_backup_erro_oserror(temp_backup_env, monkeypatch):
    zip_path = backup_service.criar_backup()
    monkeypatch.setattr(type(zip_path), "unlink", lambda _self: (_ for _ in ()).throw(OSError("permissão negada")))
    assert backup_service.excluir_backup(zip_path) is False


def test_redefinir_banco_dados(temp_backup_env):
    cfg_dir, bkp_dir = temp_backup_env
    (cfg_dir / "registro.db").unlink()

    sucesso, msg = backup_service.redefinir_banco_dados(criar_backup_previo=True)
    assert sucesso is True
    assert "sucesso" in msg.lower()
    assert (cfg_dir / "registro.db").exists()
    assert len(list(bkp_dir.glob("backup_pre_redefinicao_*.zip"))) == 1
