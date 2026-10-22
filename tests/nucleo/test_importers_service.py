"""
Testes unitários e de integração para o serviço de importação (registro.nucleo.importers_service).
"""

from pathlib import Path
import pytest
from sqlalchemy.orm import Session

from registro.nucleo.exceptions import ErroImportacaoDados
from registro.nucleo.importers_service import (
    _obter_ou_criar_grupos,
    importar_estudantes_csv,
    importar_reservas_csv,
)
from registro.nucleo.models import Estudante, Grupo, Reserva
from registro.nucleo.repository import (
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
)


def test_obter_ou_criar_grupos_novos_e_existentes(db_session: Session):
    """Testa a criação e recuperação de grupos existentes e novos."""
    # Pré-cria um grupo
    g_antigo = Grupo(nome="1º A - INFO")
    db_session.add(g_antigo)
    db_session.commit()

    nomes = {"1º A - INFO", "2º B - MEC"}
    mapa = _obter_ou_criar_grupos(db_session, nomes)

    assert "1º A - INFO" in mapa
    assert "2º B - MEC" in mapa
    assert mapa["1º A - INFO"] == g_antigo.id
    assert isinstance(mapa["2º B - MEC"], int)

    # Chamando novamente apenas com grupos já existentes
    mapa_mesmo = _obter_ou_criar_grupos(db_session, {"1º A - INFO"})
    assert mapa_mesmo == {"1º A - INFO": g_antigo.id}


def test_importar_estudantes_csv_criacao_atualizacao_e_grupos(
    db_session: Session, tmp_path: Path
):
    """Testa o fluxo completo de importar estudantes: criação, atualização e vinculação de turmas."""
    repo_est = RepositorioEstudante(db_session)
    repo_grp = RepositorioGrupo(db_session)

    # Pré-cria um estudante que terá o nome atualizado
    est_antigo = Estudante(prontuario="IQ3000001", nome="Nome Antigo")
    db_session.add(est_antigo)
    db_session.commit()

    csv_conteudo = (
        "prontuário,nome,turma\n"
        "IQ3000001,Nome Atualizado,1º A - INFO\n"  # Atualização de nome + grupo
        "IQ3000002,Novo Aluno,1º A - INFO\n"      # Criação
        "IQ3000002,Novo Aluno,2º B - ELE\n"       # Mesmo prontuário em outro grupo
        ",Sem Prontuario,1º A - INFO\n"           # Linha ignorada
    )
    arquivo_csv = tmp_path / "estudantes.csv"
    arquivo_csv.write_text(csv_conteudo, encoding="utf-8")

    criados = importar_estudantes_csv(repo_est, repo_grp, arquivo_csv)

    assert criados == 1  # Apenas IQ3000002 foi criado (IQ3000001 foi atualizado)

    # Verifica atualização do primeiro estudante
    est1 = repo_est.ler_um(est_antigo.id)
    assert est1.nome == "Nome Atualizado"
    assert len(est1.grupos) == 1
    assert est1.grupos[0].nome == "1º A - INFO"

    # Verifica novo estudante e seus dois grupos
    est2 = repo_est.ler_filtrado(prontuario="IQ3000002")[0]
    assert est2.nome == "Novo Aluno"
    nomes_grupos = {g.nome for g in est2.grupos}
    assert nomes_grupos == {"1º A - INFO", "2º B - ELE"}


def test_importar_estudantes_csv_arquivo_inexistente(db_session: Session, tmp_path: Path):
    """Testa que erro ao abrir arquivo inexistente lança ErroImportacaoDados."""
    repo_est = RepositorioEstudante(db_session)
    repo_grp = RepositorioGrupo(db_session)

    arquivo_fantasma = tmp_path / "nao_existe.csv"
    with pytest.raises(ErroImportacaoDados, match="Falha ao importar estudantes"):
        importar_estudantes_csv(repo_est, repo_grp, arquivo_fantasma)


def test_importar_reservas_csv_fluxo_completo(
    db_session: Session, tmp_path: Path
):
    """Testa a importação de reservas com validação de dados, duplicatas e ignorados."""
    repo_est = RepositorioEstudante(db_session)
    repo_res = RepositorioReserva(db_session)

    # Cria estudantes
    e1 = Estudante(prontuario="IQ3000001", nome="Aluno Um")
    e2 = Estudante(prontuario="IQ3000002", nome="Aluno Dois")
    db_session.add_all([e1, e2])
    db_session.commit()

    # Cria uma reserva prévia no banco para 21/10/2026 para e1
    res_antiga = Reserva(estudante_id=e1.id, data="21/10/2026", prato="Padrão")
    db_session.add(res_antiga)
    db_session.commit()

    csv_conteudo = (
        "prontuário,data,refeição\n"
        "IQ3000001,21/10/2026,Padrão\n"           # Já existe no DB -> deve ignorar
        "IQ3000002,21/10/2026,Vegetariano\n"      # Válida -> deve inserir
        "IQ3000002,21/10/2026,Vegetariano\n"      # Duplicada no CSV -> deve ignorar segunda
        "IQ9999999,21/10/2026,Padrão\n"           # Estudante inexistente -> deve ignorar
        "IQ3000001,,Padrão\n"                      # Sem data -> deve ignorar
    )
    arquivo_csv = tmp_path / "reservas.csv"
    arquivo_csv.write_text(csv_conteudo, encoding="utf-8")

    inseridas = importar_reservas_csv(repo_est, repo_res, arquivo_csv)
    assert inseridas == 1

    # Verifica no banco
    reservas_e2 = repo_res.ler_filtrado(estudante_id=e2.id)
    assert len(reservas_e2) == 1
    assert reservas_e2[0].prato == "Vegetariano"
    assert reservas_e2[0].data == "21/10/2026"


def test_importar_reservas_csv_arquivo_inexistente(db_session: Session, tmp_path: Path):
    """Testa que erro ao abrir arquivo inexistente lança ErroImportacaoDados."""
    repo_est = RepositorioEstudante(db_session)
    repo_res = RepositorioReserva(db_session)

    arquivo_fantasma = tmp_path / "nao_existe.csv"
    with pytest.raises(ErroImportacaoDados, match="Falha ao importar reservas"):
        importar_reservas_csv(repo_est, repo_res, arquivo_fantasma)
