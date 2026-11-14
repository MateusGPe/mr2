"""Testes unitários para as ações puras do módulo de Setup."""

from pathlib import Path
from unittest.mock import patch

from registro.gui.setup import actions


def test_validar_e_montar_regra_grade_valido_e_invalido():
    ok, msg, _ = actions.validar_e_montar_regra_grade("", "12:00", "*", "*")
    assert not ok
    assert "obrigatórios" in msg

    ok, msg, _ = actions.validar_e_montar_regra_grade("xx:yy", "12:00", "*", "*")
    assert not ok
    assert "inválido" in msg

    ok, msg, regra = actions.validar_e_montar_regra_grade(
        "11:30", "12:15", "1º A, 1º B", "TODAS"
    )
    assert ok
    assert msg == ""
    assert regra == {
        "inicio": "11:30",
        "fim": "12:15",
        "turmas": ["1º A", "1º B"],
        "categorias": ["*"],
    }


def test_adicionar_e_remover_regra_grade():
    grade = {}
    regra = {"inicio": "11:00", "fim": "12:00", "turmas": ["*"], "categorias": ["*"]}
    actions.adicionar_regra_grade(grade, "segunda", "almoco", regra)
    assert len(grade["segunda"]["almoco"]) == 1

    assert actions.remover_regra_grade(grade, "segunda", "almoco", 0) is True
    assert grade["segunda"]["almoco"] == []
    assert actions.remover_regra_grade(grade, "segunda", "almoco", 5) is False


def test_criar_atalhos_desktop_dev_e_frozen(tmp_path: Path):
    ok, msg = actions.criar_atalhos_desktop(
        desktop_dir=tmp_path, app_dir=tmp_path, frozen=False
    )
    assert ok
    assert "sucesso" in msg
    assert "uv run autoatendimento" in (
        tmp_path / "Totem Autoatendimento.bat"
    ).read_text(encoding="utf-8")

    ok_f, _ = actions.criar_atalhos_desktop(
        desktop_dir=tmp_path, executable=str(tmp_path / "app.exe"), frozen=True
    )
    assert ok_f
    assert "--auto" in (tmp_path / "Totem Autoatendimento.bat").read_text(
        encoding="utf-8"
    )

    with patch.object(Path, "write_text", side_effect=OSError("negado")):
        ok_err, msg_err = actions.criar_atalhos_desktop(
            desktop_dir=tmp_path, frozen=False
        )
        assert not ok_err
        assert "negado" in msg_err


def test_formatar_status_cards_completo_e_vazio():
    cards_ok = actions.formatar_status_cards(
        {
            "banco_dados": {
                "existe": True,
                "tamanho_kb": 42,
                "total_alunos": 10,
                "total_consumos": 5,
            },
            "google_cloud": {
                "credenciais_ok": True,
                "token_ok": True,
                "planilha_id": "abc123",
            },
            "totem": {"pin_ativo": True},
        }
    )
    assert "42 KB" in cards_ok["db"][0]
    assert "Token ativo" in cards_ok["gcp"][0]
    assert cards_ok["cred"][1] == "success"
    assert cards_ok["sheet"][1] == "abc123"
    assert cards_ok["pin_lbl"][1] == "success"

    cards_vazio = actions.formatar_status_cards(
        {
            "banco_dados": {"existe": False},
            "google_cloud": {
                "credenciais_ok": False,
                "token_ok": False,
                "planilha_id": "",
            },
            "totem": {"pin_ativo": False},
        }
    )
    assert "não criado" in cards_vazio["db"][0]
    assert cards_vazio["cred"][1] == "warning"
    assert cards_vazio["sheet"][1] == ""
    assert cards_vazio["pin_lbl"][1] == "warning"
