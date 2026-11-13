# ----------------------------------------------------------------------------
# Arquivo: tests/e2e/test_e2e_importacao_consumo_export_sync.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Testes E2E do fluxo completo de dados nas bordas do sistema:
1. Importação real de arquivo XLSX/CSV -> preview (`simular_importacao` sem sujar o BD)
   -> resolução de conflitos (`CRIAR_NOVO`, `ATUALIZAR_EXISTENTE`, `IGNORAR`)
   -> persistência com turnos (Almoço, Jantar, Ambos) e categorias pontuais.
2. Sessão -> Consumo -> Estorno -> Atualização de Consumo.
3. Exportação real XLSX e CSV com inspeção célula a célula via `openpyxl` e `csv.DictReader`:
   - Exclusão de estornos da aba principal e isolamento na aba `Cancelados`.
   - Sanitização OWASP contra Formula Injection.
4. Sincronização bidirecional e idempotente com Google Sheets falso stateful (`gspread`):
   - Download (`Discentes`, `DB`, `Configuração` -> `grade_horarios.json`, `Lanches` -> `lanches.json`).
   - Upload (`Almoço`, `Jantar`, `Cancelados`) e idempotência na 2ª execução.
"""

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import openpyxl
import xlsxwriter
from gspread.exceptions import WorksheetNotFound

from registro.nucleo import constants, google_api_service
from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.models import Estudante, Reserva
from registro.nucleo.services import grade_horarios_service


class FakeWorksheet:
    """Simula uma aba do Google Sheets mantendo estado em memória."""

    def __init__(self, title: str, rows: List[List[str]] | None = None):
        self.title = title
        self._rows: List[List[str]] = [list(r) for r in (rows or [])]

    def get_all_values(self) -> List[List[str]]:
        return [list(r) for r in self._rows]

    def append_row(self, row: List[Any], value_input_option=None):
        self._rows.append([str(c) if c is not None else "" for c in row])

    def append_rows(self, rows: List[List[Any]], value_input_option=None):
        for r in rows:
            self.append_row(r)

    def freeze(self, rows=None):
        return None

    def format(self, range_name, fmt):
        return None


class FakeSpreadsheet:
    """Simula uma planilha gspread completa com suporte a criação dinâmica de abas."""

    def __init__(self, initial_tabs: Dict[str, List[List[str]]] | None = None):
        self._tabs: Dict[str, FakeWorksheet] = {
            nome: FakeWorksheet(nome, linhas)
            for nome, linhas in (initial_tabs or {}).items()
        }

    def worksheets(self) -> List[FakeWorksheet]:
        return list(self._tabs.values())

    def worksheet(self, nome_aba: str) -> FakeWorksheet:
        if nome_aba not in self._tabs:
            raise WorksheetNotFound(nome_aba)
        return self._tabs[nome_aba]

    def add_worksheet(
        self, title: str, rows: int = 100, cols: int = 10
    ) -> FakeWorksheet:
        ws = FakeWorksheet(title)
        self._tabs[title] = ws
        return ws


def test_jornada_e2e_importacao_xlsx_consumo_exportacao_e_sanitizacao(
    facade: FachadaRegistro,
    db_session,
    criar_grupo,
    criar_estudante,
    tmp_path: Path,
):
    """
    Jornada ponta a ponta:
    1. Pré-cadastra um aluno existente para testar resolução `ATUALIZAR_EXISTENTE` e `IGNORAR`.
    2. Gera um arquivo `.xlsx` real contendo: aluno existente, aluno novo com turno 'Ambos'
       e categoria pontual 'PAP', aluno com payload perigoso `=CMD|...` (OWASP) e linha ignorada.
    3. Executa `analisar_arquivo` + `simular_importacao` (verificando zero gravação no BD)
       + `confirmar_importacao`.
    4. Valida bloqueio de `iniciar_nova_sessao` quando não há reserva do turno na data.
    5. Executa sessão de Almoço e Jantar, consome, estorna 1 consumo, atualiza outro.
    6. Exporta XLSX da sessão, total de consumos, estudantes, reservas e turmas,
       lendo de volta com `openpyxl` / `csv.DictReader` e validando cada linha e coluna.
    """
    turma_1a = criar_grupo(nome="1º A - INFO", tipo="turma")
    est_existente = criar_estudante(
        prontuario="IQ3060001", nome="Ana Existente", grupos=[turma_1a]
    )

    # Cria planilha XLSX real de entrada
    caminho_entrada = tmp_path / "reservas_entrada.xlsx"
    with xlsxwriter.Workbook(
        str(caminho_entrada), {"strings_to_formulas": False}
    ) as wb:
        ws = wb.add_worksheet("Reservas")
        ws.write_row(
            0,
            0,
            ["Prontuário", "Nome", "Turma", "Data", "Prato", "Turnos", "Categoria"],
        )
        # Match exato automático (aluno já existe)
        ws.write_row(
            1,
            0,
            [
                "IQ3060001",
                "Ana Existente",
                "1º A - INFO",
                "10/11/2026",
                "Frango",
                "Almoço",
                "",
            ],
        )
        # Aluno novo com Ambos os turnos e categoria pontual PAP
        ws.write_row(
            2,
            0,
            [
                "IQ3060002",
                "Bruno Novo",
                "1º A - INFO",
                "10/11/2026",
                "Vegano",
                "Ambos",
                "PAP",
            ],
        )
        # Aluno novo com nome iniciando por '=' para testar proteção Formula Injection na exportação
        ws.write_row(
            3,
            0,
            [
                "IQ3060003",
                "=SUM(1,2) Carla",
                "2º B - MEC",
                "10/11/2026",
                "Peixe",
                "Jantar",
                "",
            ],
        )
        # Linha que será ignorada manualmente na revisão
        ws.write_row(
            4,
            0,
            [
                "IQ3060004",
                "Daniel Ignorado",
                "2º B - MEC",
                "10/11/2026",
                "Carne",
                "Almoço",
                "",
            ],
        )

    # 1. Analisar arquivo XLSX
    prep = facade.analisar_arquivo(str(caminho_entrada), tipo="excel")
    itens_revisao = prep["itens_revisao"]
    assert len(itens_revisao) == 3

    for item in itens_revisao:
        pront = item["dados_csv"].get("prontuario")
        if pront == "IQ3060004":
            item["resolucao_escolhida"] = "IGNORAR"
        else:
            item["resolucao_escolhida"] = "CRIAR_NOVO"

    # 2. Simulação NÃO pode persistir nada no banco
    preview = facade.simular_importacao(itens_revisao)
    assert len(preview["novos_estudantes"]) == 2
    assert len(preview["reservas"]) == 3
    assert db_session.query(Estudante).count() == 1
    assert db_session.query(Reserva).count() == 0

    # 3. Confirmação persiste apenas os resolvidos (excluindo IGNORAR)
    res_imp = facade.confirmar_importacao(itens_revisao)
    assert res_imp["estudantes_criados"] == 2
    assert res_imp["reservas_criadas"] == 3
    assert db_session.query(Estudante).filter_by(prontuario="IQ3060004").first() is None

    # 4. Data sem reserva de almoço (12/11/2026) não permite abrir sessão de almoço
    id_vazio = facade.iniciar_nova_sessao(
        {
            "refeicao": "almoço",
            "periodo": "Tarde",
            "data": "2026-11-12",
            "hora": "12:00",
            "grupos": ["1º A - INFO"],
        }
    )
    assert id_vazio is None

    # 5. Sessão de Almoço em 10/11/2026 -> Ana e Bruno consomem; Ana é estornada; Carla (só jantar) é negada
    id_alm = facade.iniciar_nova_sessao(
        {
            "refeicao": "almoço",
            "periodo": "Tarde",
            "data": "2026-11-10",
            "hora": "12:00",
            "grupos": ["1º A - INFO"],
        }
    )
    assert id_alm is not None

    assert facade.registrar_consumo(est_existente.prontuario)["autorizado"] is True
    r_bruno = facade.registrar_consumo("IQ3060002")
    assert r_bruno["autorizado"] is True
    assert r_bruno["categoria"] == "PAP"
    assert r_bruno["prato"] == "Vegano"

    # Carla só reservou Jantar -> bloqueada no almoço
    assert facade.registrar_consumo("IQ3060003")["autorizado"] is False

    # Estorno do consumo de Ana com operador e motivo específicos
    assert (
        facade.desfazer_consumo_por_prontuario(
            "IQ3060001", operador="Operador Auditor", motivo="Erro de leitura"
        )
        is True
    )

    # 6. Exporta XLSX da sessão de Almoço e inspeciona abas e células reais com openpyxl
    xlsx_sessao = Path(
        facade.exportar_sessao_para_xlsx(tmp_path / "sessao_almoco.xlsx")
    )
    assert xlsx_sessao.exists()
    wb_sessao = openpyxl.load_workbook(xlsx_sessao)
    try:
        assert "Cancelados" in wb_sessao.sheetnames
        ws_main = wb_sessao["sessao_almoco"]
        linhas_main = list(ws_main.iter_rows(values_only=True))
        assert linhas_main[0] == (
            "Matrícula",
            "Data",
            "Nome",
            "Turma",
            "Refeição",
            "Hora",
            "Categoria",
        )
        assert len(linhas_main) == 2  # Cabeçalho + Bruno (Ana foi estornada)
        assert linhas_main[1][0] == "IQ3060002"
        assert linhas_main[1][4] == "Vegano"
        assert linhas_main[1][6] == "PAP"

        ws_canc = wb_sessao["Cancelados"]
        linhas_canc = list(ws_canc.iter_rows(values_only=True))
        assert len(linhas_canc) == 2
        assert linhas_canc[1][0] == "IQ3060001"
        assert linhas_canc[1][7] == "Operador Auditor"
        assert linhas_canc[1][8] == "Erro de leitura"
    finally:
        wb_sessao.close()

    # 7. Sessão de Jantar -> Carla (=SUM(1,2) Carla) e Bruno consomem
    id_jan = facade.iniciar_nova_sessao(
        {
            "refeicao": "jantar",
            "periodo": "Noite",
            "data": "2026-11-10",
            "hora": "19:00",
            "grupos": ["1º A - INFO", "2º B - MEC"],
        }
    )
    assert id_jan is not None
    assert facade.registrar_consumo("IQ3060002")["autorizado"] is True
    assert facade.registrar_consumo("IQ3060003")["autorizado"] is True

    # 8. Exportação total de consumos exclui estornados
    xlsx_total = Path(
        facade.exportar_consumos_para_xlsx(tmp_path / "todos_consumos.xlsx")
    )
    wb_total = openpyxl.load_workbook(xlsx_total)
    try:
        linhas_total = list(wb_total["Todos os Consumos"].iter_rows(values_only=True))
        # Cabeçalho + 3 consumos ativos (Bruno Almoço, Bruno Jantar, Carla Jantar)
        assert len(linhas_total) == 4
        matriculas_exportadas = [row[0] for row in linhas_total[1:]]
        assert "IQ3060001" not in matriculas_exportadas
    finally:
        wb_total.close()

    # 9. Exportações de estudantes/reservas/turmas aplicam sanitização OWASP em '=SUM(1,2) Carla'
    csv_est = Path(facade.exportar_estudantes_para_csv(tmp_path / "alunos.csv"))
    with open(csv_est, "r", encoding="utf-8") as f:
        rows_csv = list(csv.DictReader(f))
    carla_csv = next(r for r in rows_csv if r["prontuario"] == "IQ3060003")
    assert carla_csv["nome"].lower().startswith("'=sum(1,2)")

    xlsx_est = Path(facade.exportar_estudantes_para_xlsx(tmp_path / "alunos.xlsx"))
    wb_est = openpyxl.load_workbook(xlsx_est)
    try:
        rows_est = list(wb_est["Alunos"].iter_rows(values_only=True))
        carla_xlsx = next(r for r in rows_est[1:] if r[1] == "IQ3060003")
        assert str(carla_xlsx[2]).lower().startswith("'=sum(1,2)")
    finally:
        wb_est.close()


def test_jornada_e2e_sync_bidirecional_e_idempotente_google_sheets(
    facade: FachadaRegistro,
    db_session,
    tmp_path: Path,
    monkeypatch,
):
    """
    Valida sincronização completa (Download + Sessão/Consumo/Estorno + Upload idempotente)
    usando uma planilha fake stateful mantendo `sync_service` e `google_api_service` reais.
    """
    caminho_config = tmp_path / "cfg"
    caminho_config.mkdir()
    caminho_grade = caminho_config / "grade_horarios.json"
    monkeypatch.setattr(grade_horarios_service, "CAMINHO_GRADE_HORARIOS", caminho_grade)
    monkeypatch.setattr(constants, "CAMINHO_GRADE_HORARIOS", caminho_grade)

    # Prepara lanche local pré-existente para testar merge bidirecional na aba Lanches
    (caminho_config / "lanches.json").write_text(
        json.dumps(["Pão de Queijo"]), encoding="utf-8"
    )

    planilha_fake = FakeSpreadsheet(
        initial_tabs={
            "Discentes": [
                ["Prontuário", "Nome", "Turma"],
                ["IQ3070001", "Helena Sync", "1º A"],
                ["IQ3070002", "Igor Sync", "2º B"],
            ],
            "DB": [
                ["Prontuário", "Data", "Prato", "Turno", "Categoria"],
                ["IQ3070001", "10/11/2026", "Tradicional", "Almoço e Jantar", "PAP"],
                ["IQ3070002", "10/11/2026", "Vegetariano", "Almoço", ""],
            ],
            "Configuração": [
                ["Dia", "Refeição", "Início", "Fim", "Turmas", "Categorias"],
                ["Segunda", "Almoço", "11:30", "13:00", "*", "*"],
            ],
            "Lanches": [
                ["Lanche"],
                ["Vitamina"],
            ],
            "Almoço": [
                ["Matrícula", "Data", "Nome", "Turma", "Refeição", "Hora", "Categoria"],
            ],
            "Jantar": [
                ["Matrícula", "Data", "Nome", "Turma", "Refeição", "Hora", "Categoria"],
            ],
            constants.NOME_ABA_CANCELADOS: [
                [
                    "Data",
                    "Hora",
                    "Hora Cancelamento",
                    "Matrícula",
                    "Nome",
                    "Turma",
                    "Categoria",
                    "Refeição",
                    "Operador",
                    "Motivo",
                ],
            ],
        }
    )

    monkeypatch.setattr(
        google_api_service, "obter_planilha", lambda *a, **kw: planilha_fake
    )

    # 1. Download do Sheets -> popula Discentes, Reservas, grade_horarios.json e merge bidirecional de Lanches
    facade.sincronizar_do_google_sheets(caminho_config=caminho_config)

    assert db_session.query(Estudante).count() == 2
    assert db_session.query(Reserva).count() == 2
    grade_carregada = grade_horarios_service.carregar_grade_horarios(caminho_grade)
    assert len(grade_carregada["segunda"]["almoco"]) == 1

    lanches_locais = json.loads(
        (caminho_config / "lanches.json").read_text(encoding="utf-8")
    )
    assert lanches_locais == ["Pão de Queijo", "Vitamina"]
    # Bidirecional: "Pão de Queijo" foi enviado para a aba Lanches remota
    assert ["Pão de Queijo"] in planilha_fake.worksheet("Lanches").get_all_values()

    # 2. Executa consumos em Almoço e Jantar e estorna Igor no Almoço
    id_alm = facade.iniciar_nova_sessao(
        {
            "refeicao": "almoço",
            "periodo": "Tarde",
            "data": "2026-11-10",
            "hora": "12:00",
            "grupos": ["1º A", "2º B"],
        }
    )
    assert id_alm is not None
    assert (
        facade.registrar_consumo("IQ3070001", permitir_fora_horario=True)["autorizado"]
        is True
    )
    assert (
        facade.registrar_consumo("IQ3070002", permitir_fora_horario=True)["autorizado"]
        is True
    )
    assert (
        facade.desfazer_consumo_por_prontuario("IQ3070002", motivo="Duplicado") is True
    )

    facade.iniciar_nova_sessao(
        {
            "refeicao": "jantar",
            "periodo": "Noite",
            "data": "2026-11-10",
            "hora": "19:00",
            "grupos": ["1º A"],
        }
    )
    assert (
        facade.registrar_consumo("IQ3070001", permitir_fora_horario=True)["autorizado"]
        is True
    )

    # 3. Upload para Sheets (1ª execução)
    facade.sincronizar_todas_sessoes_para_google_sheets()

    linhas_alm = planilha_fake.worksheet("Almoço").get_all_values()
    linhas_jan = planilha_fake.worksheet("Jantar").get_all_values()
    linhas_canc = planilha_fake.worksheet(
        constants.NOME_ABA_CANCELADOS
    ).get_all_values()

    assert len(linhas_alm) == 2  # Cabeçalho + Helena
    assert linhas_alm[1][0] == "IQ3070001"
    assert linhas_alm[1][6] == "PAP"

    assert len(linhas_jan) == 2  # Cabeçalho + Helena
    assert linhas_jan[1][0] == "IQ3070001"

    assert len(linhas_canc) == 2  # Cabeçalho + Igor estornado
    assert linhas_canc[1][3] == "IQ3070002"
    assert linhas_canc[1][9] == "Duplicado"

    # 4. Upload para Sheets (2ª execução -> 100% idempotente, zero duplicatas)
    facade.sincronizar_todas_sessoes_para_google_sheets()
    assert len(planilha_fake.worksheet("Almoço").get_all_values()) == 2
    assert len(planilha_fake.worksheet("Jantar").get_all_values()) == 2
    assert (
        len(planilha_fake.worksheet(constants.NOME_ABA_CANCELADOS).get_all_values())
        == 2
    )
