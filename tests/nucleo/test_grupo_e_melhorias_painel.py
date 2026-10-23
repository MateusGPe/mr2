# ----------------------------------------------------------------------------
# Arquivo: tests/nucleo/test_grupo_e_melhorias_painel.py
# ----------------------------------------------------------------------------
import pytest
from pathlib import Path
from registro.nucleo.facade import FachadaRegistro


def test_crud_grupo_completo(facade: FachadaRegistro):
    # 1. Criar turma
    g = facade.criar_grupo("3º Informática A", ativo=True)
    assert g["id"] is not None
    assert g["nome"] == "3º Informática A"
    assert g["ativo"] is True

    # Nome duplicado deve lançar ValueError
    with pytest.raises(ValueError, match="já existe"):
        facade.criar_grupo("3º Informática A")

    # 2. Atualizar turma
    ok = facade.atualizar_grupo(g["id"], {"nome": "3º INFO A", "ativo": False})
    assert ok is True

    turmas = facade.listar_turmas_detalhadas("INFO")
    assert len(turmas) == 1
    assert turmas[0]["nome"] == "3º INFO A"
    assert turmas[0]["ativo"] is False

    # 3. Vincular e Desvincular aluno
    aluno = facade.criar_estudante("SP999001", "Aluno Teste Turma")
    vinc = facade.vincular_aluno_turma(g["id"], aluno["id"])
    assert vinc is True

    alunos_turma = facade.listar_alunos_por_turma(g["id"])
    assert len(alunos_turma) == 1
    assert alunos_turma[0]["prontuario"] == "SP999001"

    # Tentativa de deletar sem forçar deve alertar que possui aluno vinculado
    res_del = facade.deletar_grupo(g["id"], forcar=False)
    assert res_del["status"] == "has_relations"

    # Desvincular
    desv = facade.desvincular_aluno_turma(g["id"], aluno["id"])
    assert desv is True
    assert len(facade.listar_alunos_por_turma(g["id"])) == 0

    # Agora pode deletar com segurança
    res_del_ok = facade.deletar_grupo(g["id"], forcar=False)
    assert res_del_ok["status"] == "deleted"


def test_estudante_exclusao_segura_e_status(facade: FachadaRegistro):
    aluno = facade.criar_estudante("SP888001", "Aluno Exclusao Segura")
    id_aluno = aluno["id"]

    # Alternar status
    facade.alternar_status_estudante(id_aluno)
    aluno_db = facade.listar_estudantes(termo_busca="SP888001")[0]
    assert aluno_db["ativo"] is False

    # Sem consumo nem reserva: deve excluir com sucesso
    res = facade.deletar_estudante(id_aluno)
    assert res["status"] == "deleted"

    # Aluno com reserva
    aluno2 = facade.criar_estudante("SP888002", "Aluno Com Reserva")
    facade.criar_reserva("SP888002", {"data": "2026-10-25", "prato": "Vegetariano"})

    res_com_reserva = facade.deletar_estudante(aluno2["id"], forcar_desativacao=False)
    assert res_com_reserva["status"] == "has_records"

    # Forçar desativação
    res_desat = facade.deletar_estudante(aluno2["id"], forcar_desativacao=True)
    assert res_desat["status"] == "deactivated"
    aluno2_db = facade.listar_estudantes(termo_busca="SP888002")[0]
    assert aluno2_db["ativo"] is False


def test_exportacoes_novas(facade: FachadaRegistro, tmp_path: Path):
    facade.criar_grupo("Turma Export", ativo=True)
    aluno = facade.criar_estudante("SP777001", "Aluno Export", grupos=["Turma Export"])
    facade.criar_reserva("SP777001", {"data": "2026-10-25", "prato": "Padrão"})

    # Exportar Alunos para XLSX
    p_alunos_xlsx = tmp_path / "alunos.xlsx"
    facade.exportar_estudantes_para_xlsx(p_alunos_xlsx)
    assert p_alunos_xlsx.exists() and p_alunos_xlsx.stat().st_size > 0

    # Exportar Reservas para XLSX
    p_res_xlsx = tmp_path / "reservas.xlsx"
    facade.exportar_reservas_para_xlsx(p_res_xlsx)
    assert p_res_xlsx.exists() and p_res_xlsx.stat().st_size > 0

    # Exportar Turmas para CSV e XLSX
    p_turmas_csv = tmp_path / "turmas.csv"
    facade.exportar_turmas_para_csv(p_turmas_csv)
    assert p_turmas_csv.exists() and p_turmas_csv.stat().st_size > 0

    p_turmas_xlsx = tmp_path / "turmas.xlsx"
    facade.exportar_turmas_para_xlsx(p_turmas_xlsx)
    assert p_turmas_xlsx.exists() and p_turmas_xlsx.stat().st_size > 0


def test_dashboard_estatisticas_corrigidas(facade: FachadaRegistro):
    stats = facade.obter_estatisticas_dashboard()
    assert "alunos_total" in stats
    assert "alunos_ativos" in stats
    assert "grupos_total" in stats
    assert "distribuicao_pratos" in stats
    assert "distribuicao_turmas" in stats
