"""
Testes unitários para a classificação e matching de dados em registro.importar.analyzer.
"""

from sqlalchemy.orm import Session

from registro.importar.analyzer import AnalisadorSimplificado
from registro.nucleo.repository import RepositorioEstudante


def test_analisador_match_exato_por_prontuario(
    db_session: Session, criar_estudante, criar_grupo
):
    """Verifica que linhas com prontuário existente são classificadas como automáticas."""
    grupo = criar_grupo(nome="1º A - MEC")
    criar_estudante(prontuario="IQ3001001", nome="João da Silva", grupos=[grupo])

    repo = RepositorioEstudante(db_session)
    analisador = AnalisadorSimplificado(repo)

    dados_brutos = [
        {"prontuario": "IQ3001001", "nome": "João da Silva", "turma": "1º A - MEC"},
    ]

    autos, revisao, invalidos = analisador.processar_lote(dados_brutos)

    assert len(autos) == 1
    assert autos[0]["prontuario"] == "IQ3001001"
    assert len(revisao) == 0
    assert len(invalidos) == 0


def test_analisador_linha_invalida_sem_identificacao(db_session: Session):
    """Linhas sem prontuário e sem nome devem ser categorizadas como inválidas."""
    repo = RepositorioEstudante(db_session)
    analisador = AnalisadorSimplificado(repo)

    dados_brutos = [
        {"prontuario": "", "nome": "", "turma": "1º A - MEC"},
        {"prontuario": None, "nome": None, "turma": ""},
    ]

    autos, revisao, invalidos = analisador.processar_lote(dados_brutos)

    assert len(autos) == 0
    assert len(revisao) == 0
    assert len(invalidos) == 2


def test_analisador_novo_estudante_para_revisao(db_session: Session):
    """Estudante com prontuário novo (não cadastrado) deve ir para revisão."""
    repo = RepositorioEstudante(db_session)
    analisador = AnalisadorSimplificado(repo)

    dados_brutos = [
        {"prontuario": "IQ3099999", "nome": "Novo Aluno Desconhecido", "turma": "1º B"},
    ]

    autos, revisao, invalidos = analisador.processar_lote(dados_brutos)

    assert len(autos) == 0
    assert len(revisao) == 1
    assert revisao[0]["tipo_conflito"] == "NOVO_ESTUDANTE"
    assert revisao[0]["dados_csv"]["prontuario"] == "IQ3099999"


def test_analisador_match_exato_sem_nome(db_session: Session, criar_estudante):
    """Quando o prontuário bate exatamente e não há nome no CSV, preenche com o nome do DB e aceita."""
    criar_estudante(prontuario="IQ3001002", nome="Carlos Andrade")
    repo = RepositorioEstudante(db_session)
    analisador = AnalisadorSimplificado(repo)

    dados = [{"prontuario": "IQ3001002", "nome": ""}]
    autos, revisao, invalidos = analisador.processar_lote(dados)
    assert len(autos) == 1
    assert autos[0]["nome"] == "Carlos Andrade"
    assert autos[0]["_id_banco"] is not None


def test_analisador_match_exato_nome_divergente(db_session: Session, criar_estudante):
    """Quando o prontuário bate exatamente mas o nome é muito diferente, vai para DADOS_DIVERGENTES."""
    criar_estudante(prontuario="IQ3001003", nome="Beatriz Lima")
    repo = RepositorioEstudante(db_session)
    analisador = AnalisadorSimplificado(repo)

    dados = [{"prontuario": "IQ3001003", "nome": "Fernando Souza"}]
    autos, revisao, invalidos = analisador.processar_lote(dados)
    assert len(autos) == 0
    assert len(revisao) == 1
    assert revisao[0]["tipo_conflito"] == "DADOS_DIVERGENTES"
    assert len(revisao[0]["candidatos"]) == 1


def test_analisador_fuzzy_nome_match_automatico_e_ajuste_score(
    db_session: Session, criar_estudante
):
    """Testa busca aproximada por nome com match exato/ajustado por prontuário."""
    e1 = criar_estudante(prontuario="IQ3001004", nome="Guilherme Henrique Pereira")
    e2 = criar_estudante(prontuario="IQ3001005", nome="Guilherme Henrique Silva")
    repo = RepositorioEstudante(db_session)
    analisador = AnalisadorSimplificado(repo)

    # 1. Match perfeito por nome (sem prontuário no CSV)
    dados_auto = [{"prontuario": "", "nome": "Guilherme Henrique Pereira"}]
    autos, revisao, _ = analisador.processar_lote(dados_auto)
    assert len(autos) == 1
    assert autos[0]["_id_banco"] == e1.id

    # 2. Match com múltiplos candidatos parecidos -> MULTIPLOS_MATCHES
    dados_multi = [{"prontuario": "", "nome": "Guilherme Henrique"}]
    _, revisao_multi, _ = analisador.processar_lote(dados_multi)
    assert len(revisao_multi) == 1
    assert revisao_multi[0]["tipo_conflito"] == "MULTIPLOS_MATCHES"

    # 3. Match refinado com prontuário (bônus quando prontuário parecido, penalidade quando divergente)
    score_sem_pront = analisador._calcular_score_ajustado(70, "IQ3001004", None)
    assert score_sem_pront == 70

    score_com_bonus = analisador._calcular_score_ajustado(70, "IQ3001004", "IQ3001004")
    assert score_com_bonus >= analisador.SCORE_BONUS_PRONTUARIO

    score_com_penalidade = analisador._calcular_score_ajustado(70, "IQ3001004", "XYZ999999")
    assert score_com_penalidade < 70


def test_analisador_somente_prontuario_com_candidatos(
    db_session: Session, criar_estudante
):
    """Testa linha que possui apenas prontuário (sem nome)."""
    criar_estudante(prontuario="IQ3001006", nome="Estudante Sem Turma")
    repo = RepositorioEstudante(db_session)
    analisador = AnalisadorSimplificado(repo)

    # Prontuário parecido com existente (candidato encontrado)
    dados = [{"prontuario": "IQ300100", "nome": ""}]
    autos, revisao, _ = analisador.processar_lote(dados)
    assert len(revisao) == 1
    assert revisao[0]["dados_csv"]["nome"] == analisador.NOME_DECONHECIDO
    assert revisao[0]["resolucao_escolhida"] == "IGNORAR"

