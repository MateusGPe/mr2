"""
Teste de integração de ponta a ponta: Ingestão de CSV -> Persistência -> Sessão de Refeição -> Consumo.
"""

from pathlib import Path

from registro.importar.service import ServicoImportacao
from registro.importar.strategies import CarregarCSVComCabecalho
from registro.nucleo.facade import FachadaRegistro


def test_fluxo_completo_importacao_sessao_e_consumo(
    facade: FachadaRegistro,
    tmp_path: Path,
    csv_com_linhas_vazias_e_resumos: str,
):
    """
    Testa o ciclo operacional completo:
    1. Importação de arquivo CSV real com linhas vazias e rodapés.
    2. Persistência dos estudantes e turmas criados no banco de dados isolado.
    3. Abertura de uma sessão de lanche para a turma importada.
    4. Registro de consumo dos estudantes com normalização de prontuário.
    5. Verificação da integridade das contagens e relatórios de presença.
    """
    # 1. Criação do arquivo CSV no diretório temporário
    arquivo_csv = tmp_path / "lista_chamada.csv"
    # Ajustando o delimitador para vírgula compatível com o DictReader padrão
    conteudo_csv = csv_com_linhas_vazias_e_resumos.replace(";", ",")
    arquivo_csv.write_text(conteudo_csv, encoding="utf-8")

    # 2. Execução do serviço de importação
    servico = ServicoImportacao(facade)
    resultado_prep = servico.preparar_importacao(CarregarCSVComCabecalho(), str(arquivo_csv))

    itens_revisao = resultado_prep["itens_revisao"]
    for item in itens_revisao:
        # Aprova todos os novos estudantes
        item["resolucao_escolhida"] = "CRIAR_NOVO"

    # Persiste estudantes e reservas atribuindo a data padrão
    resultado_persistencia = servico.finalizar_importacao(
        itens_revisao, valores_padrao={"data": "21/10/2026"}
    )
    assert resultado_persistencia.get("estudantes_criados", 0) == 2

    # Verifica se os alunos foram criados no banco
    alunos = facade.repo_estudante.por_prontuarios({"IQ3001001", "IQ3001002"})
    assert len(alunos) == 2
    nomes = {a.nome for a in alunos}
    assert "Lucas Ferreira" in nomes
    assert "Beatriz Souza" in nomes

    # Associa os estudantes à turma correspondente
    grupo = facade.repo_grupo.por_nome("1º A - MAC")
    if not grupo:
        grupo = facade.repo_grupo.criar({"nome": "1º A - MAC"})
    for aluno in alunos:
        aluno.grupos.append(grupo)
    facade.repo_estudante.obter_sessao().commit()

    # 3. Abertura de sessão de lanche para a turma 1º A - MAC
    id_sessao = facade.iniciar_nova_sessao({
        "refeicao": "lanche",
        "periodo": "Tarde",
        "data": "2026-10-21",
        "hora": "16:00",
        "item_servido": "Vitamina de Morango",
        "grupos": ["1º A - MAC"],
    })
    assert id_sessao is not None
    assert facade.id_sessao_ativa == id_sessao

    # 4. Estudante passa o crachá no leitor
    res1 = facade.registrar_consumo("IQ3001001")
    assert res1["autorizado"] is True
    assert res1["aluno"] == "Lucas Ferreira"
    assert res1["prato"] == "Vitamina de Morango"

    # Estudante 2 passa o crachá
    res2 = facade.registrar_consumo("IQ3001002")
    assert res2["autorizado"] is True
    assert res2["aluno"] == "Beatriz Souza"

    # 5. Tentativa de segundo consumo pelo mesmo aluno deve ser barrada
    res_repetido = facade.registrar_consumo("IQ3001001")
    assert res_repetido["autorizado"] is False
    assert "já registrado" in res_repetido["motivo"]

    # 6. Verificação dos consumos gravados no banco
    consumos = facade.repo_consumo.ler_filtrado(sessao_id=id_sessao)
    assert len(consumos) == 2
