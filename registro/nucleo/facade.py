# --- Arquivo: registro/nucleo/facade.py ---

"""
Fornece uma Fachada de alto nível para interagir com o subsistema
do núcleo de registro.

Qualquer aplicação cliente deve interagir exclusivamente com a classe
FachadaRegistro, que gerencia internamente a sessão do banco de dados,
os repositórios e a lógica de serviço.
"""

from typing import Any, Dict, List, Optional

from registro.nucleo import service_logic
from registro.nucleo.exceptions import ErroSessaoNaoAtiva
from registro.nucleo.models import SessaoLocal, criar_banco_de_dados_e_tabelas
from registro.nucleo.repository import (
    RepositorioConsumo,
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
    RepositorioSessao,
)
from registro.nucleo.utils import DADOS_SESSAO


class FachadaRegistro:
    """
    Interface simplificada para o sistema de registro de refeições.
    """

    def __init__(self):
        """
        Inicializa a Fachada, configurando a conexão com o banco de dados
        e instanciando os repositórios.
        """
        criar_banco_de_dados_e_tabelas()
        self._sessao_db = SessaoLocal()

        self._repo_estudante = RepositorioEstudante(self._sessao_db)
        self._repo_reserva = RepositorioReserva(self._sessao_db)
        self._repo_sessao = RepositorioSessao(self._sessao_db)
        self._repo_consumo = RepositorioConsumo(self._sessao_db)
        self._repo_grupo = RepositorioGrupo(self._sessao_db)

        self.id_sessao_ativa: Optional[int] = None

    def fechar_conexao(self):
        """Fecha a conexão com o banco de dados."""
        self._sessao_db.close()

    def __enter__(self):
        """Permite o uso da Fachada como um gerenciador de contexto."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Garante que a conexão com o banco de dados seja fechada."""
        self.fechar_conexao()

    def iniciar_nova_sessao(self, dados_sessao: DADOS_SESSAO) -> Optional[int]:
        """Inicia uma nova sessão de refeição e a define como ativa."""
        id_sessao = service_logic.iniciar_nova_sessao(
            self._repo_sessao, self._repo_grupo, dados_sessao
        )
        self.id_sessao_ativa = id_sessao
        return id_sessao

    def listar_todas_sessoes(self) -> List[Dict]:
        """Retorna uma lista simplificada de todas as sessões."""
        return service_logic.listar_todas_sessoes(self._repo_sessao)

    def listar_todos_os_grupos(self) -> List[Dict]:
        """Retorna uma lista de todos os grupos existentes."""
        return service_logic.listar_todos_os_grupos(self._repo_grupo)

    def definir_sessao_ativa(self, id_sessao: int):
        """Define uma sessão existente como ativa pelo seu ID."""
        # Valida se a sessão existe antes de defini-la como ativa
        service_logic.obter_detalhes_sessao(self._repo_sessao, id_sessao)
        self.id_sessao_ativa = id_sessao

    def obter_detalhes_sessao_ativa(self) -> Dict[str, Any]:
        """Retorna um dicionário com os detalhes da sessão ativa."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")
        modelo_sessao = service_logic.obter_detalhes_sessao(
            self._repo_sessao, self.id_sessao_ativa
        )
        return {
            "id": modelo_sessao.id,
            "refeicao": modelo_sessao.refeicao,
            "periodo": modelo_sessao.periodo,
            "data": modelo_sessao.data,
            "hora": modelo_sessao.hora,
            "item_servido": modelo_sessao.item_servido,
            "grupos": [g.nome for g in modelo_sessao.grupos],
        }

    def obter_estudantes_pesquisaveis_para_sessao(
        self, grupos_excluidos: Optional[set[str]] = None
    ) -> List[Dict[str, str]]:
        """
        Retorna uma lista de estudantes elegíveis (que não consumiram) para a busca,
        contendo apenas prontuário e nome. Otimizado para autocomplete.
        """
        if self.id_sessao_ativa is None:
            return []

        todos_elegiveis = service_logic.obter_estudantes_para_sessao(
            repo_sessao=self._repo_sessao,
            repo_estudante=self._repo_estudante,
            repo_reserva=self._repo_reserva,
            repo_consumo=self._repo_consumo,
            id_sessao=self.id_sessao_ativa,
            consumido=False,
            grupos_excluidos=grupos_excluidos,
        )
        return [
            {"pront": estudante["pront"], "nome": estudante["nome"]}
            for estudante in todos_elegiveis
        ]

    def cancelar_reserva(self, id_reserva: int):
        """Marca uma reserva de refeição como cancelada."""
        service_logic.atualizar_cancelamento_reserva(
            self._repo_reserva, id_reserva, True
        )

    def reativar_reserva(self, id_reserva: int):
        """Remove a marcação de cancelada de uma reserva."""
        service_logic.atualizar_cancelamento_reserva(
            self._repo_reserva, id_reserva, False
        )

    def deletar_sessao_ativa(self):
        """Deleta a sessão ativa e todos os seus consumos associados."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")
        service_logic.deletar_sessao(self._repo_sessao, self.id_sessao_ativa)
        self.id_sessao_ativa = None

    def deletar_sessao(self, id_sessao: int):
        """Deleta uma sessão específica e todos os seus consumos associados."""
        service_logic.deletar_sessao(self._repo_sessao, id_sessao)
        if self.id_sessao_ativa == id_sessao:
            self.id_sessao_ativa = None

    def atualizar_detalhes_sessao(self, id_sessao: int, dados_sessao: Dict[str, Any]):
        """Atualiza os detalhes de uma sessão (data, hora, etc.)."""
        service_logic.atualizar_sessao(self._repo_sessao, id_sessao, dados_sessao)

    def criar_estudante(self, prontuario: str, nome: str) -> Dict[str, Any]:
        """Cria um novo estudante, evitando duplicatas de prontuário."""
        existente = self._repo_estudante.ler_filtrado(prontuario=prontuario)
        if existente:
            raise ValueError(f"Estudante com prontuário {prontuario} já existe.")

        novo_estudante = self._repo_estudante.criar(
            {"prontuario": prontuario, "nome": nome}
        )
        self._sessao_db.commit()
        return {
            "id": novo_estudante.id,
            "prontuario": novo_estudante.prontuario,
            "nome": novo_estudante.nome,
        }

    def atualizar_estudante(self, id_estudante: int, dados: Dict[str, Any]) -> bool:
        """Atualiza os dados de um estudante (ex: nome, status 'ativo')."""
        estudante = self._repo_estudante.atualizar(id_estudante, dados)
        if estudante:
            self._sessao_db.commit()
            return True
        return False

    def deletar_estudante(self, id_estudante: int) -> bool:
        """
        Remove um estudante do banco de dados.

        CUIDADO: A melhor abordagem é inativar o estudante usando o campo 'ativo'
        através do método `atualizar_estudante`. Deletar pode causar erros de
        integridade de dados se houver consumos ou reservas associadas.
        """
        if self._repo_estudante.deletar(id_estudante):
            self._sessao_db.commit()
            return True
        return False

    def obter_estudantes_para_sessao(
        self,
        consumido: Optional[bool] = None,
        grupos_excluidos: Optional[set[str]] = None,
    ) -> List[Dict]:
        """Retorna estudantes para a sessão ativa, com opção de filtro por consumo."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")
        return service_logic.obter_estudantes_para_sessao(
            repo_sessao=self._repo_sessao,
            repo_estudante=self._repo_estudante,
            repo_reserva=self._repo_reserva,
            repo_consumo=self._repo_consumo,
            id_sessao=self.id_sessao_ativa,
            consumido=consumido,
            grupos_excluidos=grupos_excluidos,
        )

    def registrar_consumo(self, prontuario: str) -> Dict[str, Any]:
        """Registra que um estudante consumiu uma refeição, seguindo as regras."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")
        return service_logic.registrar_consumo(
            repo_sessao=self._repo_sessao,
            repo_estudante=self._repo_estudante,
            repo_reserva=self._repo_reserva,
            repo_consumo=self._repo_consumo,
            id_sessao=self.id_sessao_ativa,
            prontuario=prontuario,
        )

    def desfazer_consumo(self, id_consumo: int):
        """Desfaz o registro de consumo de uma refeição."""
        service_logic.desfazer_consumo(self._repo_consumo, id_consumo)

    def atualizar_grupos_sessao(self, grupos: List[str]):
        """Atualiza a configuração de grupos para a sessão ativa."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")
        service_logic.atualizar_grupos_sessao(
            self._repo_sessao, self._repo_grupo, self.id_sessao_ativa, grupos
        )

    def exportar_sessao_para_xlsx(self) -> str:
        """Exporta os dados de consumo da sessão ativa para um arquivo XLSX."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")
        return service_logic.exportar_sessao_para_xlsx(
            self._repo_sessao, self._repo_consumo, self.id_sessao_ativa
        )

    def sincronizar_do_google_sheets(self):
        """Sincroniza a base de dados local a partir de uma planilha do Google Sheets."""
        service_logic.sincronizar_do_google_sheets(
            self._repo_estudante, self._repo_reserva, self._repo_grupo
        )

    def sincronizar_para_google_sheets(self):
        """Envia os dados de consumo da sessão ativa para a planilha do Google Sheets."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")
        service_logic.sincronizar_para_google_sheets(
            self._repo_sessao, self._repo_consumo, self.id_sessao_ativa
        )
