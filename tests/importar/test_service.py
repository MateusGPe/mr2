"""
Testes unitários para o orquestrador ServicoImportacao em registro.importar.service.
"""

from pathlib import Path
import pytest

from registro.importar.service import ServicoImportacao
from registro.importar.strategies import CarregarCSVComCabecalho
from registro.nucleo.exceptions import ErroImportacaoDados
from registro.nucleo.facade import FachadaRegistro


def test_servico_importacao_preparar_arquivo_vazio(facade: FachadaRegistro, tmp_path: Path):
    """Arquivo vazio ou sem dados válidos deve lançar ErroImportacaoDados."""
    arquivo_vazio = tmp_path / "vazio.csv"
    arquivo_vazio.write_text("", encoding="utf-8")

    servico = ServicoImportacao(facade)
    with pytest.raises(ErroImportacaoDados):
        servico.preparar_importacao(CarregarCSVComCabecalho(), str(arquivo_vazio))


def test_servico_importacao_ciclo_completo(facade: FachadaRegistro, tmp_path: Path):
    """Executa preparar_importacao, simular e finalizar_importacao."""
    csv_file = tmp_path / "importacao.csv"
    csv_file.write_text(
        "Matrícula,Nome,Turma,Data,Refeição\n"
        "IQ3007001,Lucas Silva,1º A - MEC,21/10/2026,Almoço\n",
        encoding="utf-8",
    )

    servico = ServicoImportacao(facade)
    resultado_prep = servico.preparar_importacao(CarregarCSVComCabecalho(), str(csv_file))

    assert "resumo" in resultado_prep
    assert resultado_prep["resumo"]["total_linhas"] == 1

    # Como IQ3007001 ainda não existe no banco, vai para itens_revisao como NOVO_ESTUDANTE
    itens_rev = resultado_prep["itens_revisao"]
    assert len(itens_rev) == 1
    itens_rev[0]["resolucao_escolhida"] = "CRIAR_NOVO"

    # Simular
    simulacao = servico.simular_importacao(itens_rev)
    assert len(simulacao["novos_estudantes"]) == 1
    assert simulacao["novos_estudantes"][0]["prontuario"] == "IQ3007001"

    # Finalizar (persistir no banco)
    res_final = servico.finalizar_importacao(itens_rev)
    assert res_final.get("estudantes_criados", 0) >= 1

    # Verificar que o estudante foi de fato persistido no banco
    estudantes = facade.repo_estudante.por_prontuarios({"IQ3007001"})
    assert len(estudantes) == 1
    assert estudantes[0].nome == "Lucas Silva"


def test_servico_importacao_resolucoes_vincular_e_ignorar(
    facade: FachadaRegistro, criar_estudante
):
    """Testa o processamento de itens de revisão com decisões VINCULAR e IGNORAR."""
    # Cria estudante no banco para vincular
    aluno_existente = criar_estudante(prontuario="IQ3008888", nome="Aluno do Banco")

    servico = ServicoImportacao(facade)

    itens_revisao = [
        # 1. Decisão IGNORAR
        {
            "id_temp": 1,
            "dados_csv": {"prontuario": "IQ9999991", "nome": "Ignorado", "data": "21/10/2026"},
            "resolucao_escolhida": "IGNORAR",
            "id_estudante_vinculo": None,
        },
        # 2. Decisão VINCULAR a estudante existente
        {
            "id_temp": 2,
            "dados_csv": {"prontuario": "IQ3008888", "nome": "Aluno Grafia Errada", "data": "21/10/2026", "prato": "Padrão"},
            "resolucao_escolhida": "VINCULAR",
            "id_estudante_vinculo": aluno_existente.id,
            "candidatos": [{"id": aluno_existente.id, "nome": aluno_existente.nome, "prontuario": aluno_existente.prontuario}],
        },
        # 3. Item sem data (deve ser ignorado na criação de reservas)
        {
            "id_temp": 3,
            "dados_csv": {"prontuario": "IQ9999992", "nome": "Sem Data", "data": None},
            "resolucao_escolhida": "CRIAR_NOVO",
            "id_estudante_vinculo": None,
        },
    ]

    # Simular com valores padrão (preenchendo data para o item 3)
    simulacao = servico.simular_importacao(
        itens_revisao, valores_padrao={"data": "21/10/2026", "prato": "Vegetariano"}
    )
    assert len(simulacao["novos_estudantes"]) == 1  # O item 3 é novo estudante
    assert len(simulacao["reservas"]) == 2          # Itens 2 e 3 têm data preenchida

    # Finalizar
    res = servico.finalizar_importacao(itens_revisao)
    assert res.get("reservas_criadas", 0) == 2

    # Confirma que reserva foi criada para aluno_existente
    reservas = facade.repo_reserva.ler_filtrado(estudante_id=aluno_existente.id)
    assert len(reservas) == 1
    assert reservas[0].data == "21/10/2026"

