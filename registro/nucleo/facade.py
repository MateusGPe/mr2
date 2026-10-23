# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/facade.py (Fachada de Registro Unificada)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Fornece uma Fachada de alto nível para interagir com o subsistema
do núcleo de registro e importação.

Qualquer aplicação cliente (como GUI ou scripts CLI) deve interagir
exclusivamente com a classe FachadaRegistro, que gerencia internamente
a sessão do banco de dados, os repositórios, a lógica de serviço e a importação.
"""

import datetime as dt
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Union

from sqlalchemy.orm import Session

from registro.nucleo import service_logic
from registro.nucleo.exceptions import ErroSessaoNaoAtiva
from registro.nucleo.models import (
    Estudante,
    SessaoLocal,
    criar_banco_de_dados_e_tabelas,
)
from registro.nucleo.repository import (
    RepositorioConsumo,
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
    RepositorioSessao,
)
from registro.nucleo.utils import DADOS_SESSAO

logger = logging.getLogger(__name__)

REGEX_LIMPEZA_PRONTUARIO: re.Pattern[str] = service_logic.REGEX_LIMPEZA_PRONTUARIO


class FachadaRegistro:
    """
    Interface pública unificada para o sistema de registro de refeições.
    Encapsula o banco de dados, repositórios, regras de negócio e importação.
    """

    def __init__(self, sessao_db: Optional[Session] = None):
        """
        Inicializa a Fachada, configurando a conexão com o banco de dados
        e instanciando os repositórios privados. Permite injetar uma sessão
        customizada (por exemplo, em memória para testes).
        """
        if sessao_db is not None:
            self._sessao_db = sessao_db
        else:
            criar_banco_de_dados_e_tabelas()
            self._sessao_db = SessaoLocal()

        self._repo_estudante = RepositorioEstudante(self._sessao_db)
        self._repo_reserva = RepositorioReserva(self._sessao_db)
        self._repo_sessao = RepositorioSessao(self._sessao_db)
        self._repo_consumo = RepositorioConsumo(self._sessao_db)
        self._repo_grupo = RepositorioGrupo(self._sessao_db)

        self.id_sessao_ativa: Optional[int] = None
        self.excecao_grupos: Set[str] = set()
        self._servico_importacao_cache: Optional[Any] = None

    # --- Propriedades de compatibilidade para Repositórios ---

    @property
    def repo_estudante(self) -> RepositorioEstudante:
        """Acesso retrocompatível ao repositório de estudantes."""
        return self._repo_estudante

    @property
    def repo_reserva(self) -> RepositorioReserva:
        """Acesso retrocompatível ao repositório de reservas."""
        return self._repo_reserva

    @property
    def repo_sessao(self) -> RepositorioSessao:
        """Acesso retrocompatível ao repositório de sessões."""
        return self._repo_sessao

    @property
    def repo_consumo(self) -> RepositorioConsumo:
        """Acesso retrocompatível ao repositório de consumos."""
        return self._repo_consumo

    @property
    def repo_grupo(self) -> RepositorioGrupo:
        """Acesso retrocompatível ao repositório de grupos."""
        return self._repo_grupo

    @property
    def excessao_grupos(self) -> Set[str]:
        """Acesso retrocompatível para a grafia anterior 'excessao_grupos'."""
        return self.excecao_grupos

    @excessao_grupos.setter
    def excessao_grupos(self, valor: Set[str]):
        self.excecao_grupos = set(valor)

    # --- Gerenciamento de Conexão e Context Manager ---

    def fechar_conexao(self):
        """Fecha a conexão com o banco de dados."""
        self._sessao_db.close()

    def __enter__(self):
        """Permite o uso da Fachada como um gerenciador de contexto."""
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        """Garante que a conexão com o banco de dados seja fechada."""
        self.fechar_conexao()

    # --- Gestão de Sessões ---

    def iniciar_nova_sessao(self, dados_sessao: DADOS_SESSAO) -> Optional[int]:
        """Inicia uma nova sessão de refeição e a define como ativa."""
        id_sessao = service_logic.iniciar_nova_sessao(
            self._repo_sessao, self._repo_grupo, self._repo_reserva, dados_sessao
        )
        if id_sessao is None:
            return None
        self.id_sessao_ativa = id_sessao
        return id_sessao

    def listar_todas_sessoes(self) -> List[Dict[str, Any]]:
        """Retorna uma lista simplificada de todas as sessões."""
        return service_logic.listar_todas_sessoes(self._repo_sessao)

    def definir_sessao_ativa(self, id_sessao: int):
        """Define uma sessão existente como ativa pelo seu ID."""
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
            "grupos": set(g.nome for g in modelo_sessao.grupos),
        }

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

    def atualizar_grupos_sessao(
        self,
        grupos: List[str],
        excecao_grupos: Optional[Sequence[str]] = None,
        excessao_grupos: Optional[Sequence[str]] = None,
    ):
        """Atualiza a configuração de grupos para a sessão ativa."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")

        filtro_excecao = excecao_grupos if excecao_grupos is not None else excessao_grupos
        if filtro_excecao is not None:
            self.excecao_grupos = set(filtro_excecao)

        service_logic.atualizar_grupos_sessao(
            self._repo_sessao, self._repo_grupo, self.id_sessao_ativa, grupos
        )

    # --- Registro e Cancelamento de Consumo ---

    def registrar_consumo(
        self,
        prontuario: str,
        excecao_grupos: Optional[Set[str]] = None,
        excessao_grupos: Optional[Set[str]] = None,
        pular_grupos: bool = False,
    ) -> Dict[str, Any]:
        """Registra que um estudante consumiu uma refeição, seguindo as regras."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")

        grupos_filtro = excecao_grupos or excessao_grupos or self.excecao_grupos

        return service_logic.registrar_consumo(
            repo_sessao=self._repo_sessao,
            repo_estudante=self._repo_estudante,
            repo_reserva=self._repo_reserva,
            repo_consumo=self._repo_consumo,
            id_sessao=self.id_sessao_ativa,
            prontuario=prontuario,
            excecao_grupos=grupos_filtro,
            pular_grupos=pular_grupos,
        )

    def registrar_consumo_com_reserva(
        self,
        prontuario: str,
        excecao_grupos: Optional[Set[str]] = None,
        excessao_grupos: Optional[Set[str]] = None,
        pular_grupos: bool = False,
    ) -> Dict[str, Any]:
        """Registra consumo de refeição exclusivamente para quem possui reserva."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")

        grupos_filtro = excecao_grupos or excessao_grupos or self.excecao_grupos

        return service_logic.registrar_consumo_com_reserva(
            repo_sessao=self._repo_sessao,
            repo_estudante=self._repo_estudante,
            repo_reserva=self._repo_reserva,
            repo_consumo=self._repo_consumo,
            id_sessao=self.id_sessao_ativa,
            prontuario=prontuario,
            excecao_grupos=grupos_filtro,
            pular_grupos=pular_grupos,
        )

    def desfazer_consumo_por_prontuario(self, prontuario: str):
        """Desfaz o registro de consumo de uma refeição na sessão ativa."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa para desfazer o consumo.")

        service_logic.desfazer_consumo_por_prontuario(
            self._repo_consumo, prontuario, self.id_sessao_ativa
        )

    def desfazer_consumo(self, id_consumo: int):
        """Desfaz o registro de consumo específico pelo ID."""
        service_logic.desfazer_consumo(self._repo_consumo, id_consumo)

    def atualizar_consumo(
        self,
        id_consumo: int,
        hora_consumo: Optional[str] = None,
        prato: Optional[str] = None,
    ) -> bool:
        """Atualiza horário de consumo e/ou prato associado a um registro existente."""
        return service_logic.atualizar_consumo(
            self._repo_consumo,
            self._repo_reserva,
            id_consumo=id_consumo,
            hora_consumo=hora_consumo,
            prato=prato,
        )

    # --- Gestão de Estudantes ---

    def criar_estudante(
        self, prontuario: str, nome: str, grupos: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Cria um novo estudante e associa aos grupos especificados."""
        return service_logic.criar_estudante(
            self._repo_estudante, self._repo_grupo, prontuario, nome, grupos
        )

    def atualizar_estudante(
        self,
        id_estudante: int,
        dados: Dict[str, Any],
        grupos: Optional[List[str]] = None,
    ) -> bool:
        """Atualiza os dados de um estudante e seus grupos associados."""
        return service_logic.atualizar_estudante(
            self._repo_estudante,
            id_estudante,
            dados,
            repo_grupo=self._repo_grupo,
            grupos=grupos,
        )

    def deletar_estudante(
        self, id_estudante: int, forcar_desativacao: bool = False
    ) -> Dict[str, Any]:
        """Exclusão segura de estudante, com opção de desativação se houver histórico."""
        return service_logic.deletar_ou_desativar_estudante(
            self._repo_estudante,
            self._repo_reserva,
            self._repo_consumo,
            id_estudante,
            forcar_desativacao=forcar_desativacao,
        )

    def alternar_status_estudante(self, id_estudante: int) -> bool:
        """Alterna o status de ativo/inativo do estudante."""
        return service_logic.alternar_status_estudante(
            self._repo_estudante, id_estudante
        )

    def listar_todos_os_estudantes(self) -> List[Dict[str, Any]]:
        """Lista todos os estudantes em ordem alfabética."""
        return service_logic.listar_todos_os_estudantes(self._repo_estudante)

    def listar_estudantes(
        self,
        termo_busca: Optional[str] = None,
        turma_nome: Optional[str] = None,
        status_ativo: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Lista estudantes com suporte a filtro textual, por turma e status ativo."""
        return service_logic.listar_estudantes(
            self._repo_estudante,
            termo_busca=termo_busca,
            turma_nome=turma_nome,
            status_ativo=status_ativo,
        )

    def listar_estudantes_fuzzy(
        self,
        termo_busca: Optional[str] = None,
        limite: int = 60,
        turma_nome: Optional[str] = None,
        status_ativo: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Busca estudantes por similaridade aproximada (fuzzy), respeitando filtros."""
        return service_logic.listar_estudantes_fuzzy(
            self._repo_estudante,
            termo_busca=termo_busca,
            limite=limite,
            turma_nome=turma_nome,
            status_ativo=status_ativo,
        )

    def obter_todos_estudantes_com_grupos(self) -> Sequence[Estudante]:
        """Retorna todos os objetos Estudante com grupos pré-carregados."""
        return self._repo_estudante.ler_todos_com_grupos()

    def obter_estudantes_pesquisaveis_para_sessao(
        self,
        excecao_grupos: Optional[Set[str]] = None,
        excessao_grupos: Optional[Set[str]] = None,
        pular_grupos: bool = False,
    ) -> List[Dict[str, str]]:
        """Retorna estudantes elegíveis não consumidos otimizados para busca rápida."""
        if self.id_sessao_ativa is None:
            return []

        grupos_filtro = excecao_grupos or excessao_grupos or self.excecao_grupos

        todos_elegiveis = service_logic.obter_estudantes_para_sessao(
            repo_sessao=self._repo_sessao,
            repo_estudante=self._repo_estudante,
            repo_reserva=self._repo_reserva,
            repo_consumo=self._repo_consumo,
            repo_grupo=self._repo_grupo,
            id_sessao=self.id_sessao_ativa,
            consumido=False,
            excessao_grupos=grupos_filtro,
            pular_grupos=pular_grupos,
        )
        return [
            {"pront": estudante["pront"], "nome": estudante["nome"]}
            for estudante in todos_elegiveis
        ]

    def obter_estudantes_para_sessao(
        self,
        consumido: Optional[bool] = None,
        pular_grupos: bool = False,
        excecao_grupos: Optional[Set[str]] = None,
        excessao_grupos: Optional[Set[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Retorna estudantes para a sessão ativa, com filtro opcional por consumo."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")

        grupos_filtro = excecao_grupos or excessao_grupos or self.excecao_grupos

        return service_logic.obter_estudantes_para_sessao(
            repo_sessao=self._repo_sessao,
            repo_estudante=self._repo_estudante,
            repo_reserva=self._repo_reserva,
            repo_consumo=self._repo_consumo,
            repo_grupo=self._repo_grupo,
            id_sessao=self.id_sessao_ativa,
            consumido=consumido,
            excessao_grupos=grupos_filtro,
            pular_grupos=pular_grupos,
        )

    # --- Gestão de Reservas e Grupos ---

    def listar_todos_os_grupos(self) -> List[Dict[str, Any]]:
        """Retorna uma lista de todos os grupos existentes."""
        return service_logic.listar_todos_os_grupos(self._repo_grupo)

    def criar_reserva(
        self, prontuario_estudante: str, dados_reserva: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Cria uma nova reserva para um estudante."""
        return service_logic.criar_reserva(
            self._repo_estudante, self._repo_reserva, prontuario_estudante, dados_reserva
        )

    def listar_reservas(
        self, filtros: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Lista todas as reservas com suporte a filtros por grupo e data."""
        return service_logic.listar_reservas(
            self._repo_grupo, self._repo_reserva, filtros
        )

    def listar_datas_reservas(self) -> List[str]:
        """Retorna uma lista única de datas de reservas existentes."""
        return service_logic.listar_datas_reservas(self._repo_reserva)

    def atualizar_reserva(self, id_reserva: int, dados: Dict[str, Any]) -> bool:
        """Atualiza os dados de uma reserva existente."""
        return service_logic.atualizar_reserva(
            self._repo_reserva, id_reserva, dados
        )

    def deletar_reserva(self, id_reserva: int) -> bool:
        """Remove uma reserva do sistema."""
        return service_logic.deletar_reserva(self._repo_reserva, id_reserva)

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

    # --- Exportação e Sincronização Externa ---

    def exportar_sessao_para_xlsx(
        self,
        nome_arquivo: Optional[Path] = None,
    ) -> str:
        """Exporta os dados de consumo da sessão ativa para um arquivo XLSX."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")
        return service_logic.exportar_sessao_para_xlsx(
            self._repo_sessao, self._repo_consumo, self.id_sessao_ativa, nome_arquivo
        )

    def exportar_consumos_para_xlsx(
        self,
        nome_arquivo: Optional[Path] = None,
    ) -> str:
        """Exporta todos os dados de consumo para um arquivo XLSX."""
        return service_logic.exportar_todos_os_consumos_para_xlsx(
            self._repo_consumo, nome_arquivo
        )

    def sincronizar_do_google_sheets(self):
        """Sincroniza a base de dados local a partir do Google Sheets."""
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

    def sincronizar_todas_sessoes_para_google_sheets(self):
        """Envia os dados de consumo de todas as sessões para o Google Sheets."""
        service_logic.sincronizar_todas_sessoes_para_google_sheets(
            self._repo_sessao, self._repo_consumo
        )

    def registrar_log_sincronizacao(
        self,
        direction: str,
        status: str,
        message: Optional[str] = None,
        records_affected: Optional[int] = None,
    ) -> bool:
        """Registra um evento de sincronização no banco de dados."""
        from registro.nucleo.models import SyncLog

        logger.info(
            "Registrando log de sincronização: direction=%s, status=%s, records=%s",
            direction,
            status,
            records_affected,
        )
        try:
            log_entry = SyncLog(
                timestamp=dt.datetime.now().isoformat(),
                direction=direction,
                status=status,
                message=message,
                records_affected=records_affected,
            )
            self._sessao_db.add(log_entry)
            self._sessao_db.commit()
            return True
        except Exception as e:
            logger.error("Falha ao registrar log de sincronização no BD: %s", e)
            self._sessao_db.rollback()
            return False

    # --- Subsistema Unificado de Importação ---

    def salvar_importacao_dados(self, dados: List[Dict[str, Any]]) -> Dict[str, int]:
        """Persiste em lote estudantes e reservas decorrentes de um processo de importação."""
        return service_logic.salvar_importacao_dados(
            self._repo_estudante, self._repo_reserva, dados
        )

    def _obter_servico_importacao(self):
        """Instancia e armazena em cache o serviço de importação associado a esta fachada."""
        if self._servico_importacao_cache is None:
            from registro.nucleo.importar.service import ServicoImportacao

            self._servico_importacao_cache = ServicoImportacao(self)
        return self._servico_importacao_cache

    def analisar_arquivo(self, caminho: str, tipo: str = "auto") -> Dict[str, Any]:
        """
        Carrega e analisa um arquivo de importação.
        Retorna resumo e lista de itens para revisão manual.

        Args:
            caminho: Caminho do arquivo ou identificador da fonte.
            tipo: 'simples' (txt), 'header' (csv c/ cabeçalho), 'sheets', ou 'auto'.
        """
        from registro.nucleo.importar.strategies import (
            CarregarCSVComCabecalho,
            CarregarCSVPosicional,
            CarregarGoogleSheets,
            CarregarListaSimples,
        )

        if tipo == "simples":
            estrategia = CarregarListaSimples()
        elif tipo == "header":
            estrategia = CarregarCSVComCabecalho()
        elif tipo == "sheets":
            estrategia = CarregarGoogleSheets()
        else:
            estrategia = CarregarCSVPosicional()

        return self._obter_servico_importacao().preparar_importacao(
            estrategia, caminho
        )

    def simular_importacao(
        self,
        itens_revisados: List[Any],
        valores_padrao: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, List[Dict]]:
        """Gera preview da importação sem salvar alterações no banco de dados."""
        return self._obter_servico_importacao().simular_importacao(
            itens_revisados, valores_padrao
        )

    def confirmar_importacao(
        self,
        itens_resolvidos: List[Any],
        valores_padrao: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, int]:
        """Finaliza a importação aplicando as decisões do usuário e valores padrão."""
        return self._obter_servico_importacao().finalizar_importacao(
            itens_resolvidos, valores_padrao
        )

    # --- Persistência de Estado e Exportações Adicionais ---

    def carregar_estado_sessao(self) -> Optional[Dict[str, Any]]:
        """Carrega o estado da sessão a partir da persistência e ativa a sessão se existir."""
        return service_logic.carregar_estado_sessao(self)

    def salvar_estado_sessao(self, id_sessao: Optional[int] = None) -> bool:
        """Persiste o identificador da sessão ativa."""
        return service_logic.salvar_estado_sessao(self, id_sessao)

    def limpar_estado_sessao(self) -> bool:
        """Remove a persistência de sessão e limpa a sessão ativa."""
        return service_logic.limpar_estado_sessao(self)

    # --- Gestão de Turmas / Grupos ---

    def criar_grupo(self, nome: str, ativo: bool = True) -> Dict[str, Any]:
        """Cria uma nova turma no sistema."""
        return service_logic.criar_grupo(self._repo_grupo, nome, ativo=ativo)

    def atualizar_grupo(self, id_grupo: int, dados: Dict[str, Any]) -> bool:
        """Atualiza nome e/ou status de uma turma."""
        return service_logic.atualizar_grupo(self._repo_grupo, id_grupo, dados)

    def deletar_grupo(self, id_grupo: int, forcar: bool = False) -> Dict[str, Any]:
        """Exclui uma turma (com validação se possui alunos ou sessões vinculadas)."""
        return service_logic.deletar_grupo(self._repo_grupo, id_grupo, forcar=forcar)

    def listar_turmas_detalhadas(
        self, termo_busca: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Lista todas as turmas com quantidade de alunos e status."""
        return service_logic.listar_turmas_detalhadas(
            self._repo_grupo, termo_busca=termo_busca
        )

    def listar_alunos_por_turma(self, id_grupo: int) -> List[Dict[str, Any]]:
        """Lista os alunos vinculados a uma turma específica."""
        return service_logic.listar_alunos_por_turma(self._repo_grupo, id_grupo)

    def vincular_aluno_turma(self, id_grupo: int, id_estudante: int) -> bool:
        """Vincula um aluno a uma turma."""
        return service_logic.vincular_aluno_turma(
            self._repo_grupo, self._repo_estudante, id_grupo, id_estudante
        )

    def desvincular_aluno_turma(self, id_grupo: int, id_estudante: int) -> bool:
        """Desvincula um aluno de uma turma."""
        return service_logic.desvincular_aluno_turma(
            self._repo_grupo, id_grupo, id_estudante
        )

    def exportar_estudantes_para_csv(
        self,
        caminho_arquivo: Union[str, Path],
        estudantes_dados: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Exporta os dados de estudantes cadastrados para um arquivo CSV."""
        return service_logic.exportar_estudantes_para_csv(
            self._repo_estudante, caminho_arquivo, estudantes_dados=estudantes_dados
        )

    def exportar_estudantes_para_xlsx(
        self,
        caminho_arquivo: Union[str, Path],
        estudantes_dados: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Exporta os dados de estudantes cadastrados para um arquivo Excel (.xlsx)."""
        return service_logic.exportar_estudantes_para_xlsx(
            self._repo_estudante, caminho_arquivo, estudantes_dados=estudantes_dados
        )

    def exportar_reservas_para_csv(
        self,
        caminho_arquivo: Union[str, Path],
        reservas_dados: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Exporta os dados de reservas cadastradas para um arquivo CSV."""
        return service_logic.exportar_reservas_para_csv(
            self._repo_grupo,
            self._repo_reserva,
            caminho_arquivo,
            reservas_dados=reservas_dados,
        )

    def exportar_reservas_para_xlsx(
        self,
        caminho_arquivo: Union[str, Path],
        reservas_dados: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Exporta os dados de reservas cadastradas para um arquivo Excel (.xlsx)."""
        return service_logic.exportar_reservas_para_xlsx(
            self._repo_grupo,
            self._repo_reserva,
            caminho_arquivo,
            reservas_dados=reservas_dados,
        )

    def exportar_turmas_para_csv(
        self,
        caminho_arquivo: Union[str, Path],
        turmas_dados: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Exporta turmas para um arquivo CSV."""
        return service_logic.exportar_turmas_para_csv(
            self._repo_grupo, caminho_arquivo, turmas_dados=turmas_dados
        )

    def exportar_turmas_para_xlsx(
        self,
        caminho_arquivo: Union[str, Path],
        turmas_dados: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Exporta turmas para um arquivo Excel (.xlsx)."""
        return service_logic.exportar_turmas_para_xlsx(
            self._repo_grupo, caminho_arquivo, turmas_dados=turmas_dados
        )

    def obter_estatisticas_dashboard(self) -> Dict[str, Any]:
        """Retorna estatísticas consolidadas para visualização no dashboard."""
        return service_logic.obter_estatisticas_dashboard(
            self._repo_estudante,
            self._repo_reserva,
            self._repo_grupo,
            self._repo_consumo,
        )

    def obter_estatisticas_sessao(
        self, id_sessao: Optional[int] = None
    ) -> Dict[str, Any]:
        """Retorna estatísticas detalhadas da sessão (ativa ou especificada)."""
        alvo_id = id_sessao if id_sessao is not None else self.id_sessao_ativa
        if alvo_id is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")

        return service_logic.obter_estatisticas_sessao(
            repo_sessao=self._repo_sessao,
            repo_estudante=self._repo_estudante,
            repo_reserva=self._repo_reserva,
            repo_consumo=self._repo_consumo,
            repo_grupo=self._repo_grupo,
            id_sessao=alvo_id,
            excessao_grupos=self.excecao_grupos,
        )

