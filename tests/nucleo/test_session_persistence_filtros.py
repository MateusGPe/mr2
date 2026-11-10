"""
Testes para persistência de estado da sessão com filtros de categoria e exceções.
"""

from pathlib import Path
from registro.nucleo.facade import FachadaRegistro
import registro.nucleo.constants as constants


def test_salvar_e_carregar_estado_sessao_com_filtros(facade: FachadaRegistro, tmp_path: Path, monkeypatch):
    """Garante que session.json salva e restaura excecao_grupos e ignorar_horario_grade."""
    arquivo_sessao = tmp_path / "session.json"
    monkeypatch.setattr(constants, "CAMINHO_SESSAO", arquivo_sessao)

    id_sessao = facade.iniciar_nova_sessao({
        "refeicao": "lanche",
        "periodo": "Tarde",
        "data": "2026-11-09",
        "hora": "15:00",
        "item_servido": "Bolo",
        "grupos": ["1INFO"],
    })

    # Define filtros
    facade.definir_excecao_grupos({"2MEC", "3ELT"})
    facade.definir_ignorar_horario_grade(True)

    assert arquivo_sessao.exists()
    conteudo = arquivo_sessao.read_text(encoding="utf-8")
    assert "2MEC" in conteudo
    assert "3ELT" in conteudo
    assert '"ignorar_horario_grade": true' in conteudo

    # Simula reinício de aplicação limpando atributos na memória
    facade.id_sessao_ativa = None
    facade.excecao_grupos = set()
    facade.ignorar_horario_grade = False

    estado_carregado = facade.carregar_estado_sessao()
    assert estado_carregado is not None
    assert facade.id_sessao_ativa == id_sessao
    assert facade.ignorar_horario_grade is True
    assert "2MEC" in facade.excecao_grupos
    assert "3ELT" in facade.excecao_grupos

    # Ao iniciar nova sessão ou limpar estado, ignorar_horario_grade deve voltar a False
    id_sessao_2 = facade.iniciar_nova_sessao({
        "refeicao": "lanche",
        "periodo": "Noite",
        "data": "2026-11-10",
        "hora": "19:00",
        "item_servido": "Chá",
        "grupos": ["1INFO"],
    })
    assert id_sessao_2 != id_sessao
    assert facade.ignorar_horario_grade is False

    # Ativa na sessão 2 e limpa estado -> volta a False
    facade.definir_ignorar_horario_grade(True)
    assert facade.ignorar_horario_grade is True
    facade.limpar_estado_sessao()
    assert facade.ignorar_horario_grade is False


