# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/_facade_cadastros.py (Mixin de Cadastros, Sync e Exportação)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""Mixin responsável por cadastros (estudantes, turmas, reservas), importação, exportação e sync."""

import datetime as dt
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Union, cast

from sqlalchemy.exc import SQLAlchemyError

from registro.nucleo.exceptions import ErroSessaoNaoAtiva
from registro.nucleo.models import Estudante, SyncLog
from registro.nucleo.services import (
    estudante_service,
    export_service,
    grupo_service,
    reserva_service,
    sessao_service,
    sync_service,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from registro.nucleo.repository import (
        RepositorioConsumo,
        RepositorioEstudante,
        RepositorioGrupo,
        RepositorioReserva,
        RepositorioSessao,
    )

logger = logging.getLogger(__name__)


class _FacadeCadastrosMixin:
    """Agrupa operações de estudantes, grupos/turmas, reservas, exportação, importação e sync."""

    if TYPE_CHECKING:
        _sessao_db: Session
        _deve_fechar_sessao: bool
        _repo_estudante: RepositorioEstudante
        _repo_reserva: RepositorioReserva
        _repo_sessao: RepositorioSessao
        _repo_consumo: RepositorioConsumo
        _repo_grupo: RepositorioGrupo
        id_sessao_ativa: Optional[int]
        _servico_importacao_cache: Optional[Any]

    # --- Gestão de Estudantes ---

    def criar_estudante(
        self,
        prontuario: str,
        nome: str,
        grupos: Optional[List[str]] = None,
        categoria: Optional[str] = None,
        categorias: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Cria um novo estudante e associa às turmas e categorias especificadas."""
        return estudante_service.criar_estudante(
            self._repo_estudante,
            self._repo_grupo,
            prontuario,
            nome,
            grupos,
            categoria=categoria,
            categorias=categorias,
        )

    def atualizar_estudante(
        self,
        id_estudante: int,
        dados: Dict[str, Any],
        grupos: Optional[List[str]] = None,
        categorias: Optional[List[str]] = None,
    ) -> bool:
        """Atualiza os dados de um estudante e suas turmas/categorias associadas."""
        return estudante_service.atualizar_estudante(
            self._repo_estudante,
            id_estudante,
            dados,
            repo_grupo=self._repo_grupo,
            grupos=grupos,
            categorias=categorias,
        )

    def deletar_estudante(
        self, id_estudante: int, forcar_desativacao: bool = False
    ) -> Dict[str, Any]:
        """Exclusão segura de estudante, com opção de desativação se houver histórico."""
        return estudante_service.deletar_ou_desativar_estudante(
            self._repo_estudante,
            self._repo_reserva,
            self._repo_consumo,
            id_estudante,
            forcar_desativacao=forcar_desativacao,
        )

    def alternar_status_estudante(self, id_estudante: int) -> bool:
        """Alterna o status de ativo/inativo do estudante."""
        return estudante_service.alternar_status_estudante(
            self._repo_estudante, id_estudante
        )

    def listar_todos_os_estudantes(self) -> List[Dict[str, Any]]:
        """Lista todos os estudantes em ordem alfabética."""
        return estudante_service.listar_todos_os_estudantes(self._repo_estudante)

    def listar_estudantes(
        self,
        termo_busca: Optional[str] = None,
        turma_nome: Optional[str] = None,
        status_ativo: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Lista estudantes com suporte a filtro textual, por turma e status ativo."""
        return estudante_service.listar_estudantes(
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
        return estudante_service.listar_estudantes_fuzzy(
            self._repo_estudante,
            termo_busca=termo_busca,
            limite=limite,
            turma_nome=turma_nome,
            status_ativo=status_ativo,
        )

    def obter_todos_estudantes_com_grupos(self) -> Sequence[Estudante]:
        """Retorna todos os objetos Estudante com grupos pré-carregados."""
        return self._repo_estudante.ler_todos_com_grupos()

    # --- Gestão de Reservas e Grupos ---

    def listar_todos_os_grupos(self) -> List[Dict[str, Any]]:
        """Retorna uma lista de todos os grupos existentes."""
        return sessao_service.listar_todos_os_grupos(self._repo_grupo)

    def criar_reserva(
        self, prontuario_estudante: str, dados_reserva: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Cria uma nova reserva para um estudante."""
        return reserva_service.criar_reserva(
            self._repo_estudante,
            self._repo_reserva,
            prontuario_estudante,
            dados_reserva,
            repo_grupo=self._repo_grupo,
        )

    def listar_reservas(
        self, filtros: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Lista todas as reservas com suporte a filtros por grupo e data."""
        return reserva_service.listar_reservas(
            self._repo_grupo, self._repo_reserva, filtros
        )

    def listar_datas_reservas(self) -> List[str]:
        """Retorna uma lista única de datas de reservas existentes."""
        return reserva_service.listar_datas_reservas(self._repo_reserva)

    def atualizar_reserva(self, id_reserva: int, dados: Dict[str, Any]) -> bool:
        """Atualiza os dados de uma reserva existente."""
        return reserva_service.atualizar_reserva(
            self._repo_reserva, id_reserva, dados, repo_grupo=self._repo_grupo
        )

    def deletar_reserva(self, id_reserva: int) -> bool:
        """Remove uma reserva do sistema."""
        return reserva_service.deletar_reserva(self._repo_reserva, id_reserva)

    def cancelar_reserva(self, id_reserva: int) -> None:
        """Marca uma reserva de refeição como cancelada."""
        reserva_service.atualizar_cancelamento_reserva(
            self._repo_reserva, id_reserva, True
        )

    def reativar_reserva(self, id_reserva: int) -> None:
        """Remove a marcação de cancelada de uma reserva."""
        reserva_service.atualizar_cancelamento_reserva(
            self._repo_reserva, id_reserva, False
        )

    # --- Exportação e Sincronização Externa ---

    def exportar_sessao_para_xlsx(
        self,
        nome_arquivo: Optional[Any] = None,
    ) -> str:
        """Exporta os dados de consumo da sessão ativa para um arquivo XLSX."""
        if isinstance(nome_arquivo, int):
            id_sessao_alvo: Optional[int] = nome_arquivo
            caminho_destino: Optional[Path] = None
        else:
            id_sessao_alvo = self.id_sessao_ativa
            caminho_destino = Path(nome_arquivo) if nome_arquivo else None

        if id_sessao_alvo is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")
        return export_service.exportar_sessao_para_xlsx(
            self._repo_sessao, self._repo_consumo, id_sessao_alvo, caminho_destino
        )

    def exportar_consumos_para_xlsx(
        self,
        nome_arquivo: Optional[Path] = None,
    ) -> str:
        """Exporta todos os dados de consumo para um arquivo XLSX."""
        return export_service.exportar_todos_os_consumos_para_xlsx(
            self._repo_consumo, nome_arquivo
        )

    def sincronizar_do_google_sheets(self, caminho_config: Optional[Path] = None):
        """Sincroniza a base de dados local a partir do Google Sheets (com isolamento thread-safe)."""
        if (
            threading.current_thread() is not threading.main_thread()
            and self._deve_fechar_sessao
        ):
            from registro.nucleo.facade import FachadaRegistro

            with FachadaRegistro() as fachada_worker:
                return sync_service.sincronizar_do_google_sheets(
                    fachada_worker._repo_estudante,
                    fachada_worker._repo_reserva,
                    fachada_worker._repo_grupo,
                    caminho_config=caminho_config,
                )
        return sync_service.sincronizar_do_google_sheets(
            self._repo_estudante,
            self._repo_reserva,
            self._repo_grupo,
            caminho_config=caminho_config,
        )

    def sincronizar_para_google_sheets(self):
        """
        Envia os dados de consumo da sessão ativa para a planilha do Google Sheets.

        .. note::
           Método de sessão única preservado para compatibilidade. A interface gráfica utiliza
           `sincronizar_todas_sessoes_para_google_sheets` para garantir sincronismo completo de
           qualquer sessão que possa ter ficado pendente.
        """
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")

        if (
            threading.current_thread() is not threading.main_thread()
            and self._deve_fechar_sessao
        ):
            from registro.nucleo.facade import FachadaRegistro

            with FachadaRegistro() as fachada_worker:
                return sync_service.sincronizar_para_google_sheets(
                    fachada_worker._repo_sessao,
                    fachada_worker._repo_consumo,
                    self.id_sessao_ativa,
                )
        return sync_service.sincronizar_para_google_sheets(
            self._repo_sessao, self._repo_consumo, self.id_sessao_ativa
        )

    def sincronizar_todas_sessoes_para_google_sheets(self):
        """Envia os dados de consumo de todas as sessões para o Google Sheets."""
        if (
            threading.current_thread() is not threading.main_thread()
            and self._deve_fechar_sessao
        ):
            from registro.nucleo.facade import FachadaRegistro

            with FachadaRegistro() as fachada_worker:
                return sync_service.sincronizar_todas_sessoes_para_google_sheets(
                    fachada_worker._repo_sessao,
                    fachada_worker._repo_consumo,
                )
        return sync_service.sincronizar_todas_sessoes_para_google_sheets(
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
        except SQLAlchemyError as e:
            logger.error("Falha ao registrar log de sincronização no BD: %s", e)
            self._sessao_db.rollback()
            return False

    # --- Subsistema Unificado de Importação ---

    def salvar_importacao_dados(self, dados: List[Dict[str, Any]]) -> Dict[str, int]:
        """Persiste em lote estudantes e reservas decorrentes de um processo de importação."""
        return reserva_service.salvar_importacao_dados(
            self._repo_estudante,
            self._repo_reserva,
            dados,
            repo_grupo=self._repo_grupo,
        )

    def _obter_servico_importacao(self):
        """Instancia e armazena em cache o serviço de importação associado a esta fachada."""
        if self._servico_importacao_cache is None:
            from registro.nucleo.facade import FachadaRegistro
            from registro.nucleo.importar.service import ServicoImportacao

            self._servico_importacao_cache = ServicoImportacao(
                cast(FachadaRegistro, self)
            )
        return self._servico_importacao_cache

    def analisar_arquivo(self, caminho: str, tipo: str = "auto") -> Dict[str, Any]:
        """
        Carrega e analisa um arquivo de importação.
        Retorna resumo e lista de itens para revisão manual.
        """
        from registro.nucleo.importar.strategies import criar_estrategia_carregamento

        estrategia = criar_estrategia_carregamento(caminho, tipo=tipo)
        return self._obter_servico_importacao().preparar_importacao(estrategia, caminho)

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

    # --- Gestão de Turmas / Grupos e Exportações Tabulares ---

    def criar_grupo(
        self, nome: str, ativo: bool = True, tipo: str = "turma"
    ) -> Dict[str, Any]:
        """Cria uma nova turma ou categoria no sistema."""
        return grupo_service.criar_grupo(self._repo_grupo, nome, ativo=ativo, tipo=tipo)

    def atualizar_grupo(self, id_grupo: int, dados: Dict[str, Any]) -> bool:
        """Atualiza nome, tipo e/ou status de uma turma ou categoria."""
        return grupo_service.atualizar_grupo(self._repo_grupo, id_grupo, dados)

    def deletar_grupo(self, id_grupo: int, forcar: bool = False) -> Dict[str, Any]:
        """Exclui uma turma (com validação se possui alunos ou sessões vinculadas)."""
        return grupo_service.deletar_grupo(self._repo_grupo, id_grupo, forcar=forcar)

    def listar_turmas_detalhadas(
        self, termo_busca: Optional[str] = None, tipo: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Lista grupos (turmas e categorias) com quantidade de alunos, tipo e status."""
        return grupo_service.listar_turmas_detalhadas(
            self._repo_grupo, termo_busca=termo_busca, tipo=tipo
        )

    def listar_alunos_por_turma(self, id_grupo: int) -> List[Dict[str, Any]]:
        """Lista os alunos vinculados a uma turma específica."""
        return grupo_service.listar_alunos_por_turma(self._repo_grupo, id_grupo)

    def vincular_aluno_turma(self, id_grupo: int, id_estudante: int) -> bool:
        """Vincula um aluno a uma turma."""
        return grupo_service.vincular_aluno_turma(
            self._repo_grupo, self._repo_estudante, id_grupo, id_estudante
        )

    def desvincular_aluno_turma(self, id_grupo: int, id_estudante: int) -> bool:
        """Desvincula um aluno de uma turma."""
        return grupo_service.desvincular_aluno_turma(
            self._repo_grupo, id_grupo, id_estudante
        )

    def exportar_estudantes_para_csv(
        self,
        caminho_arquivo: Union[str, Path],
        estudantes_dados: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Exporta os dados de estudantes cadastrados para um arquivo CSV."""
        return export_service.exportar_estudantes_para_csv(
            self._repo_estudante, caminho_arquivo, estudantes_dados=estudantes_dados
        )

    def exportar_estudantes_para_xlsx(
        self,
        caminho_arquivo: Union[str, Path],
        estudantes_dados: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Exporta os dados de estudantes cadastrados para um arquivo Excel (.xlsx)."""
        return export_service.exportar_estudantes_para_xlsx(
            self._repo_estudante, caminho_arquivo, estudantes_dados=estudantes_dados
        )

    def exportar_reservas_para_csv(
        self,
        caminho_arquivo: Union[str, Path],
        reservas_dados: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Exporta os dados de reservas cadastradas para um arquivo CSV."""
        return export_service.exportar_reservas_para_csv(
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
        return export_service.exportar_reservas_para_xlsx(
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
        return export_service.exportar_turmas_para_csv(
            self._repo_grupo, caminho_arquivo, turmas_dados=turmas_dados
        )

    def exportar_turmas_para_xlsx(
        self,
        caminho_arquivo: Union[str, Path],
        turmas_dados: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Exporta turmas para um arquivo Excel (.xlsx)."""
        return export_service.exportar_turmas_para_xlsx(
            self._repo_grupo, caminho_arquivo, turmas_dados=turmas_dados
        )
