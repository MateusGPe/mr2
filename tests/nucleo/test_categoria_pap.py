"""
Testes unitários para importação e contagem segregada de categoria PAP vs REGULAR.
"""

from pathlib import Path
from registro.nucleo.facade import FachadaRegistro
from registro.nucleo import importers_service


def test_importar_estudantes_com_categoria_pap(
    facade: FachadaRegistro, tmp_path: Path, criar_sessao, criar_reserva
):
    csv_file = tmp_path / "students_pap.csv"
    csv_content = (
        "Matrícula,Nome,Turma,Categoria\n"
        "IQ3011111,Aluno Bolsista,1º BEM,PAP\n"
        "IQ3022222,Aluno Regular,1º BEM,REGULAR\n"
        "IQ3033333,Aluno Sem Coluna,1º BEM,\n"
    )
    csv_file.write_text(csv_content, encoding="utf-8")

    importers_service.importar_estudantes_csv(
        facade.repo_estudante, facade.repo_grupo, csv_file
    )

    aluno_pap = facade.repo_estudante.ler_filtrado(prontuario="IQ3011111")[0]
    assert aluno_pap is not None
    assert aluno_pap.categoria == "PAP"

    aluno_reg = facade.repo_estudante.ler_filtrado(prontuario="IQ3022222")[0]
    assert aluno_reg is not None
    assert aluno_reg.categoria == "REGULAR"

    aluno_vazio = facade.repo_estudante.ler_filtrado(prontuario="IQ3033333")[0]
    assert aluno_vazio is not None
    assert aluno_vazio.categoria == "REGULAR"

    # Consumo e agregação em estatísticas
    data = "26/10/2026"
    criar_reserva(estudante=aluno_pap, data=data, prato="Padrão")
    criar_reserva(estudante=aluno_reg, data=data, prato="Padrão")

    grupo_db = facade.repo_grupo.por_nome("1º BEM")
    sessao = criar_sessao(refeicao="almoço", data=data, grupos=[grupo_db])
    facade.id_sessao_ativa = sessao.id

    res_pap = facade.registrar_consumo("IQ3011111")
    assert res_pap["autorizado"] is True
    assert res_pap["categoria"] == "PAP"

    res_reg = facade.registrar_consumo("IQ3022222")
    assert res_reg["autorizado"] is True
    assert res_reg["categoria"] == "REGULAR"

    stats = facade.obter_estatisticas_sessao(sessao.id)
    assert stats["total_consumidos"] == 2
    assert stats["total_pap"] == 1
    assert stats["total_regular"] == 1
