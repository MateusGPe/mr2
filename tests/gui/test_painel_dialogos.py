"""Testes funcionais headless para os diálogos do Painel Gerencial."""

import tkinter as tk
from datetime import datetime
from unittest.mock import patch

from registro.gui.painel.dialogos import (
    ReservaDialog,
    SessionDialog,
    StudentDialog,
    TurmaDialog,
    VincularAlunoDialog,
)


def test_student_turma_vincular_reserva_e_sessao_dialogs(
    app_root,
    facade,
    mock_messagebox,
    criar_grupo,
    criar_estudante,
    criar_sessao,
    criar_reserva,
):
    grupo = criar_grupo(nome="1INFO")
    criar_grupo(nome="Bolsista", tipo="categoria")
    est = criar_estudante(prontuario="PR300", nome="Maria Silva", grupos=[grupo])
    hoje = datetime.now().strftime("%d/%m/%Y")
    res = criar_reserva(estudante=est, data=hoje, prato="Padrão")
    criar_sessao(refeicao="Almoço", data=hoje, grupos=[grupo])

    with (
        patch.object(tk.Misc, "grab_set"),
        patch.object(tk.Misc, "wait_window"),
    ):
        # 1. StudentDialog - criacao, validacao e edicao
        dlg_est = StudentDialog(app_root, facade)
        dlg_est._on_save()  # nome/prontuario vazios -> warning
        dlg_est.nome_entry.insert(0, "Joao Novo")
        dlg_est.prontuario_entry.insert(0, "PR301")
        dlg_est.grupo_combobox.set("1INFO")
        dlg_est._on_save()
        assert dlg_est.result is True

        dlg_est_edit = StudentDialog(app_root, facade, student_id=est.id)
        dlg_est_edit.nome_entry.delete(0, tk.END)
        dlg_est_edit.nome_entry.insert(0, "Maria Atualizada")
        dlg_est_edit._on_save()
        assert dlg_est_edit.result is True

        dlg_est_cancel = StudentDialog(app_root, facade)
        dlg_est_cancel._on_cancel()
        assert dlg_est_cancel.result is False

        # 2. TurmaDialog - criacao, validacao e edicao
        dlg_turma = TurmaDialog(app_root, facade)
        dlg_turma._on_save()  # vazio -> warning
        dlg_turma.nome_entry.insert(0, "2INFO")
        dlg_turma.tipo_combobox.set("Turma")
        dlg_turma._on_save()
        assert dlg_turma.result is True

        dlg_turma_edit = TurmaDialog(app_root, facade, turma_id=grupo.id)
        dlg_turma_edit.var_ativo.set(True)
        dlg_turma_edit._on_save()
        assert dlg_turma_edit.result is True

        dlg_turma_cancel = TurmaDialog(app_root, facade)
        dlg_turma_cancel._on_cancel()

        # 3. VincularAlunoDialog
        dlg_vinc = VincularAlunoDialog(
            app_root, facade, turma_id=grupo.id, nome_turma="1INFO"
        )
        dlg_vinc._vincular()  # nada selecionado -> warning
        iids = dlg_vinc.table.view.get_children()
        if iids:
            dlg_vinc.table.view.selection_set(iids[0])
            dlg_vinc._vincular()
            assert dlg_vinc.result is True
        else:
            dlg_vinc.destroy()

        # 4. ReservaDialog - criacao, validacao e edicao
        dlg_res = ReservaDialog(app_root, facade)
        dlg_res._on_save()  # vazio -> warning
        dlg_res.aluno_combobox.set("PR300 - Maria Atualizada")
        dlg_res.data_entry.entry.delete(0, tk.END)
        dlg_res.data_entry.entry.insert(0, "20/11/2026")
        dlg_res.prato_combobox.set("Padrão")
        dlg_res.almoco_var.set(True)
        dlg_res.jantar_var.set(False)
        dlg_res._on_save()
        assert dlg_res.result is True

        dlg_res_edit = ReservaDialog(app_root, facade, reserva_id=res.id)
        dlg_res_edit._on_save()
        assert dlg_res_edit.result is True

        dlg_res_cancel = ReservaDialog(app_root, facade)
        dlg_res_cancel._on_cancel()

        # 5. SessionDialog - selecionar e criar
        dlg_sess = SessionDialog(app_root, facade)
        if dlg_sess.sessoes_map:
            primeira_chave = next(iter(dlg_sess.sessoes_map))
            dlg_sess.sessoes_combobox.set(primeira_chave)
            dlg_sess._on_select()
            assert dlg_sess.result is not None
        else:
            dlg_sess.destroy()

        dlg_sess2 = SessionDialog(app_root, facade)
        for var in dlg_sess2.grupos_vars.values():
            var.set(True)
        dlg_sess2.refeicao_var.set("Almoço")
        dlg_sess2._on_create()
        assert dlg_sess2.result is not None
