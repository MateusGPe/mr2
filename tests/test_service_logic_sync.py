from types import SimpleNamespace

from registro.nucleo import google_api_service, service_logic


class FakeRepoSessao:
    def __init__(self, sessoes):
        self._sessoes = sessoes

    def ler_todos(self):
        return list(self._sessoes)


class FakeRepoConsumo:
    def __init__(self, consumos_por_sessao):
        self._consumos_por_sessao = consumos_por_sessao

    def ler_filtrado(self, opcoes_carregamento=None, sessao_id=None):
        return list(self._consumos_por_sessao.get(sessao_id, []))


def test_sincronizar_todas_sessoes_para_google_sheets_processa_todas_as_sessoes(monkeypatch):
    sessao1 = SimpleNamespace(
        id=1,
        refeicao="almoço",
        data="01/01/2026",
        item_servido="Arroz",
    )
    sessao2 = SimpleNamespace(
        id=2,
        refeicao="lanche",
        data="02/01/2026",
        item_servido=None,
    )
    repo_sessao = FakeRepoSessao([sessao1, sessao2])

    consumo1 = SimpleNamespace(
        estudante=SimpleNamespace(
            prontuario="123",
            nome="Ana",
            grupos=[SimpleNamespace(nome="A")],
        ),
        reserva=SimpleNamespace(prato="Feijoada"),
        hora_consumo="12:00",
    )
    consumo2 = SimpleNamespace(
        estudante=SimpleNamespace(
            prontuario="456",
            nome="Bruno",
            grupos=[],
        ),
        reserva=None,
        hora_consumo="15:00",
    )
    repo_consumo = FakeRepoConsumo({1: [consumo1], 2: [consumo2]})

    chamadas = []

    def fake_obter_detalhes_sessao(repo_sessao, id_sessao):
        return repo_sessao.ler_todos()[id_sessao - 1]

    def fake_obter_planilha():
        return object()

    def fake_anexar_linhas_unicas(planilha, linhas, nome_aba):
        chamadas.append((nome_aba, linhas))
        return len(linhas)

    monkeypatch.setattr(service_logic, "obter_detalhes_sessao", fake_obter_detalhes_sessao)
    monkeypatch.setattr(service_logic.google_api_service, "obter_planilha", fake_obter_planilha)
    monkeypatch.setattr(
        service_logic.google_api_service,
        "anexar_linhas_unicas",
        fake_anexar_linhas_unicas,
    )

    service_logic.sincronizar_todas_sessoes_para_google_sheets(repo_sessao, repo_consumo)

    assert len(chamadas) == 2
    assert chamadas[0][0] == "Almoço"
    assert chamadas[1][0] == "Lanche"


def test_anexar_linhas_unicas_ignora_duplicatas_pelo_identificador_de_colunas():
    linhas_existentes = [
        ["123", "01/01/2026", "Ana", "A", "Almoço", "12:00"],
    ]

    linhas_novas = [
        ["123", "01/01/2026", "Bruno", "B", "Almoço", "12:00"],
        ["123", "01/01/2026", "Carlos", "C", "Jantar", "13:00"],
    ]

    append_calls = []

    class FakeWorksheet:
        def get_all_values(self):
            return linhas_existentes

        def append_rows(self, values, value_input_option=None):
            append_calls.append(values)

    class FakePlanilha:
        def worksheet(self, nome_aba):
            return FakeWorksheet()

    resultado = google_api_service.anexar_linhas_unicas(
        FakePlanilha(), linhas_novas, "Almoço"
    )

    assert resultado == 1
    assert append_calls == [
        [["123", "01/01/2026", "Carlos", "C", "Jantar", "13:00"]]
    ]
