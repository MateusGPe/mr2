"""
Testes unitários para o padrão de soft delete e auditoria de consumos.
"""

from sqlalchemy.orm import Session

from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.models import Consumo


def test_soft_delete_preserva_registro_e_permite_repassagem(
    facade: FachadaRegistro, db_session: Session, criar_grupo, criar_estudante, criar_sessao
):
    grupo = criar_grupo(nome="3º A - INF")
    estudante = criar_estudante(prontuario="IQ3099990", nome="Aluno Auditoria", grupos=[grupo])
    sessao = criar_sessao(refeicao="lanche", grupos=[grupo])
    facade.id_sessao_ativa = sessao.id

    # 1. Primeiro registro
    resultado = facade.registrar_consumo("IQ3099990")
    assert resultado["autorizado"] is True

    consumos_ativos = facade.repo_consumo.ler_filtrado(sessao_id=sessao.id)
    assert len(consumos_ativos) == 1
    id_consumo_original = consumos_ativos[0].id

    # 2. Desfazer consumo (Soft delete)
    sucesso_desfazer = facade.desfazer_consumo(
        id_consumo_original, operador="Fiscal01", motivo="Digitado errado"
    )
    assert sucesso_desfazer is True

    # ler_filtrado por padrão não deve retornar consumos cancelados
    assert len(facade.repo_consumo.ler_filtrado(sessao_id=sessao.id)) == 0

    # Mas o registro ainda existe fisicamente no banco com ativo=False
    registro_db = db_session.query(Consumo).filter_by(id=id_consumo_original).first()
    assert registro_db is not None
    assert registro_db.ativo is False
    assert registro_db.deletado_por == "Fiscal01"
    assert registro_db.motivo_cancelamento == "Digitado errado"
    assert registro_db.deletado_em is not None

    # 3. O aluno passa novamente na mesma sessão -> Deve autorizar e criar novo consumo ativo
    resultado_novo = facade.registrar_consumo("IQ3099990")
    assert resultado_novo["autorizado"] is True

    consumos_ativos_novo = facade.repo_consumo.ler_filtrado(sessao_id=sessao.id)
    assert len(consumos_ativos_novo) == 1
    assert consumos_ativos_novo[0].id != id_consumo_original

    # No banco agora existem exatamente 2 registros (1 inativo e 1 ativo)
    total_db = db_session.query(Consumo).filter_by(sessao_id=sessao.id).count()
    assert total_db == 2


def test_soft_delete_por_prontuario(
    facade: FachadaRegistro, db_session: Session, criar_grupo, criar_estudante, criar_sessao
):
    grupo = criar_grupo(nome="1º BEM")
    estudante = criar_estudante(prontuario="IQ3088880", nome="Aluno Por Prontuario", grupos=[grupo])
    sessao = criar_sessao(refeicao="lanche", grupos=[grupo])
    facade.id_sessao_ativa = sessao.id

    facade.registrar_consumo("IQ3088880")
    assert len(facade.repo_consumo.ler_filtrado(sessao_id=sessao.id)) == 1

    sucesso = facade.desfazer_consumo_por_prontuario("IQ3088880")
    assert sucesso is True
    assert len(facade.repo_consumo.ler_filtrado(sessao_id=sessao.id)) == 0

