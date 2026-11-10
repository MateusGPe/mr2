"""
Testes unitários para o fluxo de Jantar com reserva e autorização.
"""

from registro.nucleo.facade import FachadaRegistro


def test_jantar_com_reserva_e_sem_reserva(
    facade: FachadaRegistro, criar_grupo, criar_estudante, criar_sessao, criar_reserva
):
    grupo = criar_grupo(nome="Engenharia Mecânica 1º Semestre")
    estudante_com_reserva = criar_estudante(
        prontuario="IQ3077771", nome="Discente Com Reserva", grupos=[grupo]
    )
    estudante_sem_reserva = criar_estudante(
        prontuario="IQ3077772", nome="Discente Sem Reserva", grupos=[grupo]
    )

    data_jantar = "25/10/2026"
    criar_reserva(
        estudante=estudante_com_reserva,
        data=data_jantar,
        prato="Tradicional",
        almoco=False,
        jantar=True,
    )

    sessao = criar_sessao(
        refeicao="jantar",
        data=data_jantar,
        hora="19:00",
        periodo="Noturno",
        grupos=[grupo],
    )
    facade.id_sessao_ativa = sessao.id

    # 1. Aluno com reserva é autorizado
    res_com = facade.registrar_consumo("IQ3077771")
    assert res_com["autorizado"] is True
    assert res_com["prato"] == "Tradicional"

    # 2. Aluno sem reserva é rejeitado
    res_sem = facade.registrar_consumo("IQ3077772")
    assert res_sem["autorizado"] is False
    assert "Acesso Negado" in res_sem["motivo"]

