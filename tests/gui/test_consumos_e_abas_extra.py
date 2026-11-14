"""Testes funcionais headless para FrameConsumos e AbaImportacao."""

import tkinter as tk
from pathlib import Path
from unittest.mock import MagicMock, patch

from registro.gui.autoatendimento.consumos import AbaConsumos
from registro.gui.painel.abas.aba_importacao import AbaImportacao
from registro.nucleo.importar.definitions import ItemRevisao, ResumoImportacao


def test_frame_consumos_operacoes(
    app_root,
    facade,
    mock_messagebox,
    criar_grupo,
    criar_estudante,
    criar_sessao,
    criar_reserva,
    tmp_path: Path,
):
    grupo = criar_grupo(nome="1INFO")
    est = criar_estudante(prontuario="PR500", nome="Lucas Dias", grupos=[grupo])
    criar_reserva(estudante=est, data="13/11/2026", prato="Padrão")
    sessao = criar_sessao(refeicao="Almoço", data="13/11/2026", grupos=[grupo])
    facade.definir_sessao_ativa(sessao.id)
    facade.definir_ignorar_horario_grade(True)
    facade.registrar_consumo("PR500")

    top = tk.Toplevel(app_root)
    try:
        mudancas = []
        frame = AbaConsumos(
            top,
            fachada=facade,
            id_sessao=sessao.id,
            notificar_mudanca_callback=lambda: mudancas.append(1),
        )
        iids = frame.tree.view.get_children()
        assert len(iids) == 1
        iid = iids[0]

        # Filtro de busca
        frame.var_busca.set("Lucas")
        frame._ao_digitar_busca()
        assert len(frame.tree.view.get_children()) == 1
        frame.var_busca.set("")
        frame._ao_digitar_busca()
        iid = frame.tree.view.get_children()[0]

        # Exibir detalhes, novo e editar (com dialogos mockados)
        with (
            patch(
                "registro.gui.autoatendimento.consumos.DialogoDetalhesConsumo"
            ) as mock_det,
            patch(
                "registro.gui.autoatendimento.consumos.DialogoNovoConsumo"
            ) as mock_cad,
            patch(
                "registro.gui.autoatendimento.consumos.DialogoEditarConsumo"
            ) as mock_ed,
        ):
            frame.exibir_detalhes(iid)
            mock_det.assert_called_once()
            frame.novo_registro()
            mock_cad.assert_called_once()
            frame.editar_registro(iid)
            mock_ed.assert_called_once()

        # Exportar xlsx (direciona Path.home para tmp_path)
        (tmp_path / "Documents").mkdir(exist_ok=True)
        with patch("pathlib.Path.home", return_value=tmp_path):
            frame.exportar_xlsx()

        # Excluir registro com confirmacao
        mock_messagebox.yesno_response = "Yes"
        with patch(
            "registro.gui.comum.dialogo_cancelamento.solicitar_cancelamento_consumo",
            return_value=(True, "Admin", "Teste"),
        ):
            frame.excluir_registro(iid)
            assert mudancas
    finally:
        top.destroy()


def test_aba_importacao_fluxo_wizard_e_exportacao(
    app_root,
    facade,
    mock_messagebox,
    tmp_path: Path,
):
    top = tk.Toplevel(app_root)
    try:
        aba = AbaImportacao(top, fachada_nucleo=facade)
        csv_fake = tmp_path / "alunos.csv"
        csv_fake.write_text("prontuario,nome\nPR600,Ana\n", encoding="utf-8")

        with patch(
            "registro.gui.painel.abas.aba_importacao.filedialog.askopenfilename",
            return_value=str(csv_fake),
        ):
            aba._selecionar_arquivo()
            assert aba.file_path_var.get() == str(csv_fake)

        resumo = ResumoImportacao(
            total_linhas=1,
            automaticos=0,
            invalidos=0,
            para_revisao=1,
        )
        itens = [
            ItemRevisao(
                id_temp=1,
                dados_csv={"nome": "Ana", "prontuario": "PR600", "turma": "1A"},
                tipo_conflito="NOVO_ESTUDANTE",
                candidatos=[],
                resolucao_escolhida="CRIAR_NOVO",
                id_estudante_vinculo=None,
            )
        ]
        aba.resumo_analise = resumo
        aba.itens_revisao = itens
        aba._preencher_passo_2()

        mock_imp = MagicMock()
        mock_imp.gerar_preview.return_value = {
            "novos_estudantes": [
                {"prontuario": "PR600", "nome": "Ana", "grupos": ["1A"]}
            ],
            "novas_reservas": [],
        }
        mock_imp.executar_importacao.return_value = {"estudantes": 1, "reservas": 0}
        aba.fachada_importacao = mock_imp

        aba._ir_para_preview()
        aba._executar_salvamento()
        aba._resetar_tudo()

        # Exportacao CSV/XLSX
        out_csv = tmp_path / "export_est.csv"
        with patch(
            "registro.gui.painel.abas.aba_importacao.filedialog.asksaveasfilename",
            return_value=str(out_csv),
        ):
            aba._exportar_dados("alunos_csv")
            aba._exportar_dados("turmas_csv")
            aba._exportar_dados("reservas_csv")
    finally:
        top.destroy()
