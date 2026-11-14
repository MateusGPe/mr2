"""Testes funcionais headless para AppSetup e suas abas."""

import tkinter as tk
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from ttkbootstrap import Style

from registro.gui.setup.app import AppSetup


def test_app_setup_inicializacao_e_acoes_principais(
    app_root, tmp_path: Path, mock_messagebox
):
    status_fake = {
        "banco_dados": {
            "existe": True,
            "tamanho_kb": 12,
            "total_alunos": 3,
            "total_consumos": 2,
        },
        "google_cloud": {
            "credenciais_ok": True,
            "token_ok": False,
            "planilha_id": "sheet123",
        },
        "totem": {"pin_ativo": False},
    }
    grade_fake = {
        "segunda": {
            "almoco": [
                {
                    "inicio": "11:30",
                    "fim": "12:15",
                    "turmas": ["*"],
                    "categorias": ["*"],
                }
            ],
            "jantar": [],
            "lanche": [],
        }
    }

    def _fake_window_init(self, *args, **kwargs):
        top = tk.Toplevel(app_root)
        self.__dict__.update(top.__dict__)
        self._style = Style()

    with (
        patch("ttkbootstrap.Window.__init__", _fake_window_init),
        patch(
            "registro.gui.setup.app.config_service.obter_status_sistema",
            return_value=status_fake,
        ),
        patch(
            "registro.gui.setup.app.config_service.obter_config_totem",
            return_value={
                "fullscreen": False,
                "camera_on_start": True,
                "require_pin_to_exit": False,
                "feedback_delay_ms": 1500,
            },
        ),
        patch(
            "registro.gui.setup.app.config_service.obter_lanches",
            return_value=["Bolo"],
        ),
        patch(
            "registro.gui.setup.app.config_service.salvar_lanches"
        ) as mock_salvar_lanches,
        patch("registro.gui.setup.app.config_service.definir_pin") as mock_def_pin,
        patch(
            "registro.gui.setup.app.config_service.obter_configuracoes",
            return_value={"totem": {}},
        ),
        patch("registro.gui.setup.app.config_service.salvar_configuracoes"),
        patch(
            "registro.gui.setup.app.config_service.salvar_id_planilha",
            return_value="sheet999",
        ),
        patch("registro.gui.setup.app.backup_service.listar_backups", return_value=[]),
        patch(
            "registro.gui.setup.app.backup_service.criar_backup",
            return_value=tmp_path / "b.zip",
        ),
        patch(
            "registro.gui.setup.app.grade_horarios_service.carregar_grade_horarios",
            return_value=grade_fake,
        ),
        patch(
            "registro.gui.setup.app.grade_horarios_service.salvar_grade_horarios",
            return_value=True,
        ),
    ):
        app = AppSetup()
        try:
            assert app.var_planilha_input.get() == "sheet123"

            app.var_planilha_input.set("sheet999")
            app._salvar_id_planilha()

            app.var_mostrar_pin.set(True)
            app._alternar_visibilidade_pin()
            app.var_novo_pin.set("1234")
            app.var_confirma_pin.set("1234")
            app._salvar_pin()
            mock_def_pin.assert_called_once_with("1234")

            app._salvar_preferencias_totem()

            app._adicionar_regra_grade()
            assert len(app._grade_atual["segunda"]["almoco"]) == 2
            app._salvar_grade_horarios()

            app._criar_backup_padrao()

            app.var_novo_lanche.set("Suco")
            app._adicionar_lanche()
            mock_salvar_lanches.assert_called()
        finally:
            app.destroy()


def test_app_setup_operacoes_avancadas_backups_grade_pin_e_google(
    app_root, tmp_path: Path, mock_messagebox
):
    status_fake = {
        "banco_dados": {
            "existe": True,
            "tamanho_kb": 12,
            "total_alunos": 3,
            "total_consumos": 2,
        },
        "google_cloud": {
            "credenciais_ok": True,
            "token_ok": True,
            "planilha_id": "sheet123",
        },
        "totem": {"pin_ativo": True},
    }
    grade_fake = {
        "segunda": {
            "almoco": [
                {
                    "inicio": "11:30",
                    "fim": "12:15",
                    "turmas": ["*"],
                    "categorias": ["*"],
                }
            ],
            "jantar": [],
            "lanche": [],
        }
    }
    backup_zip = tmp_path / "backup_01.zip"
    backup_zip.write_bytes(b"zip")
    token_fake = tmp_path / "token.json"
    token_fake.write_text("{}", encoding="utf-8")

    def _fake_window_init(self, *args, **kwargs):
        top = tk.Toplevel(app_root)
        self.__dict__.update(top.__dict__)
        self._style = Style()

    patches = [
        patch("ttkbootstrap.Window.__init__", _fake_window_init),
        patch(
            "registro.gui.setup.app.config_service.obter_status_sistema",
            return_value=status_fake,
        ),
        patch(
            "registro.gui.setup.app.config_service.obter_config_totem",
            return_value={
                "fullscreen": False,
                "camera_on_start": True,
                "require_pin_to_exit": True,
                "feedback_delay_ms": 1500,
            },
        ),
        patch(
            "registro.gui.setup.app.config_service.obter_lanches",
            return_value=["Bolo", "Suco"],
        ),
        patch("registro.gui.setup.app.config_service.salvar_lanches"),
        patch(
            "registro.gui.setup.app.config_service.tem_pin_configurado",
            return_value=True,
        ),
        patch("registro.gui.setup.app.config_service.remover_pin"),
        patch("registro.gui.setup.app.solicitar_pin", return_value=True),
        patch(
            "registro.gui.setup.app.config_service.salvar_arquivo_credenciais",
            return_value=True,
        ),
        patch("registro.gui.setup.app.config_service.limpar_token"),
        patch("registro.gui.setup.app.CAMINHO_TOKEN", token_fake),
        patch(
            "registro.gui.setup.app.backup_service.listar_backups",
            return_value=[
                {
                    "caminho": backup_zip,
                    "nome": backup_zip.name,
                    "data": "2026",
                    "tamanho": "1 KB",
                }
            ],
        ),
        patch(
            "registro.gui.setup.app.backup_service.criar_backup",
            return_value=backup_zip,
        ),
        patch(
            "registro.gui.setup.app.backup_service.restaurar_backup",
            return_value=(True, "Restaurado"),
        ),
        patch(
            "registro.gui.setup.app.backup_service.excluir_backup", return_value=True
        ),
        patch(
            "registro.gui.setup.app.backup_service.redefinir_banco_dados",
            return_value=(True, "Banco redefinido"),
        ),
        patch(
            "registro.gui.setup.app.grade_horarios_service.carregar_grade_horarios",
            return_value=grade_fake,
        ),
        patch(
            "registro.gui.setup.app.grade_horarios_service.salvar_grade_horarios",
            return_value=True,
        ),
        patch(
            "registro.gui.setup.app.setup_actions.criar_atalhos_desktop",
            return_value=(True, "Atalhos OK"),
        ),
        patch(
            "registro.gui.setup.app.filedialog.askopenfilename",
            return_value=str(tmp_path / "cred.json"),
        ),
        patch(
            "registro.gui.setup.app.filedialog.askdirectory", return_value=str(tmp_path)
        ),
    ]

    mock_messagebox.question_response = "Yes"

    with ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in patches]
        mock_salvar_lanches = mocks[4]
        mock_remover_pin = mocks[6]
        mock_limpar_token = mocks[9]

        app = AppSetup()
        try:
            # Credenciais e token
            app._importar_credenciais()
            app._limpar_token()
            mock_limpar_token.assert_called_once()

            # Callbacks de conexao e abas
            app._finalizar_teste_conexao(True, "Conectado")
            app._finalizar_teste_conexao(False, "Falhou")
            app._finalizar_criacao_abas(True, "Criadas", {"criadas": ["Estudantes"]})
            app._finalizar_criacao_abas(False, "Erro abas", {})

            # PIN
            app._remover_pin()
            mock_remover_pin.assert_called_once()

            # Grade de horarios (remover selecionando item + restaurar padrao)
            itens_grade = app.tree_grade.get_children()
            assert itens_grade
            app.tree_grade.selection_set(itens_grade[0])
            app._remover_regra_grade()
            app._restaurar_grade_padrao()

            # Backups (personalizado, restaurar e excluir)
            app._criar_backup_personalizado()
            itens_bkp = app.tree_backups.get_children()
            assert itens_bkp
            app.tree_backups.selection_set(itens_bkp[0])
            app._restaurar_backup_selecionado()
            app.tree_backups.selection_set(itens_bkp[0])
            app._excluir_backup_selecionado()

            # Lanches (remover)
            app.listbox_lanches.selection_set(0)
            app._remover_lanche()
            mock_salvar_lanches.assert_called()

            # Atalhos e redefinicao de banco
            app._criar_atalhos_desktop()
            app._redefinir_banco_dados()
        finally:
            app.destroy()
