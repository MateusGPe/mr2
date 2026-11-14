"""Testes unitários para a lógica pura do Totem."""

from registro.gui.autoatendimento import totem_logica


def test_formatar_matricula():
    assert totem_logica.formatar_matricula("12345") == "IQ3012345"
    assert totem_logica.formatar_matricula("iq300012x") == "IQ300012X"
    assert totem_logica.formatar_matricula("7") == "IQ3000007"


def test_filtrar_e_resolver_match_nome():
    candidatos = [
        {"nome": "Maria Silva", "pront": "IQ3000001"},
        {"nome": "Mariana Souza", "pront": "IQ3000002"},
        {"nome": "", "pront": "IQ3000003"},
    ]
    corresp = totem_logica.filtrar_correspondencias_nome(
        candidatos, "Maria Silva", score_minimo=90
    )
    assert len(corresp) == 1
    ok, pront, dados = totem_logica.resolver_match_nome(corresp, "Maria Silva")
    assert ok is True
    assert pront == "IQ3000001"
    assert dados["nome"] == "Maria Silva"

    ok_vazio, msg_vazio, _ = totem_logica.resolver_match_nome([], "Desconhecido")
    assert ok_vazio is False
    assert "não encontrado" in msg_vazio.lower()

    ambiguos = [
        {"nome": "Ana A", "pront": "1", "score": 95},
        {"nome": "Ana B", "pront": "2", "score": 92},
    ]
    ok_amb, msg_amb, _ = totem_logica.resolver_match_nome(ambiguos, "Ana")
    assert ok_amb is False
    assert "Múltiplos resultados" in msg_amb

    sem_pront = [{"nome": "Sem Pront", "score": 100}]
    ok_sp, msg_sp, _ = totem_logica.resolver_match_nome(sem_pront, "Sem Pront")
    assert ok_sp is False
    assert "Prontuário não encontrado" in msg_sp


def test_formatar_resumo_sessao_topo():
    ref, topo = totem_logica.formatar_resumo_sessao_topo(
        {
            "refeicao": "almoco",
            "hora": "11:30",
            "data": "10/03/2026",
            "item_servido": "Arroz",
            "grupos": ["1º A", "1º B"],
        },
        qtd_exc=1,
        ignorar_horario_grade=True,
    )
    assert ref == "Almoco (11:30) • Arroz"
    assert "2 turmas (+1 exc.)" in topo
    assert "Horário Livre" in topo

    _, topo_todas = totem_logica.formatar_resumo_sessao_topo(
        {"refeicao": "lanche", "hora": "15:00", "data": "10/03/2026", "grupos": []},
        qtd_exc=0,
        ignorar_horario_grade=False,
    )
    assert "👥 Todas" in topo_todas
