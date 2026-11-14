# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/_facade_sessoes.py (Mixin de Sessões da Fachada)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""Mixin responsável pela gestão de sessões, grupos ativos e persistência de estado."""

import logging
import threading
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Set

from registro.nucleo.exceptions import ErroAPIGoogle, ErroSessaoNaoAtiva
from registro.nucleo.services import sessao_service, sync_service
from registro.nucleo.utils import DADOS_SESSAO

if TYPE_CHECKING:
    from registro.nucleo.repository import (
        RepositorioGrupo,
        RepositorioReserva,
        RepositorioSessao,
    )

logger = logging.getLogger(__name__)


class _FacadeSessoesMixin:
    """Agrupa operações de ciclo de vida e configuração da sessão ativa."""

    if TYPE_CHECKING:
        _repo_sessao: RepositorioSessao
        _repo_grupo: RepositorioGrupo
        _repo_reserva: RepositorioReserva
        id_sessao_ativa: Optional[int]
        excecao_grupos: Set[str]
        ignorar_horario_grade: bool
        dia_semana_grade: Optional[str]

    def iniciar_nova_sessao(self, dados_sessao: DADOS_SESSAO) -> Optional[int]:
        """Inicia uma nova sessão de refeição e a define como ativa."""
        id_sessao = sessao_service.iniciar_nova_sessao(
            self._repo_sessao, self._repo_grupo, self._repo_reserva, dados_sessao
        )
        if id_sessao is None:
            return None
        self.id_sessao_ativa = id_sessao
        self.ignorar_horario_grade = False
        self.dia_semana_grade = None
        return id_sessao

    def listar_todas_sessoes(self) -> List[Dict[str, Any]]:
        """Retorna uma lista simplificada de todas as sessões."""
        return sessao_service.listar_todas_sessoes(self._repo_sessao)

    def definir_sessao_ativa(self, id_sessao: int) -> None:
        """Define uma sessão existente como ativa pelo seu ID."""
        sessao_service.obter_detalhes_sessao(self._repo_sessao, id_sessao)
        if self.id_sessao_ativa != id_sessao:
            self.ignorar_horario_grade = False
            self.dia_semana_grade = None
        self.id_sessao_ativa = id_sessao

    def obter_detalhes_sessao_ativa(self) -> Dict[str, Any]:
        """Retorna um dicionário com os detalhes da sessão ativa."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")
        modelo_sessao = sessao_service.obter_detalhes_sessao(
            self._repo_sessao, self.id_sessao_ativa
        )
        return {
            "id": modelo_sessao.id,
            "refeicao": modelo_sessao.refeicao,
            "periodo": modelo_sessao.periodo,
            "data": modelo_sessao.data,
            "hora": modelo_sessao.hora,
            "item_servido": modelo_sessao.item_servido,
            "grupos": {g.nome for g in modelo_sessao.grupos},
        }

    def deletar_sessao_ativa(self) -> None:
        """Deleta a sessão ativa e todos os seus consumos associados."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")
        sessao_service.deletar_sessao(self._repo_sessao, self.id_sessao_ativa)
        self.id_sessao_ativa = None
        self.ignorar_horario_grade = False
        self.dia_semana_grade = None

    def deletar_sessao(self, id_sessao: int) -> None:
        """Deleta uma sessão específica e todos os seus consumos associados."""
        sessao_service.deletar_sessao(self._repo_sessao, id_sessao)
        if self.id_sessao_ativa == id_sessao:
            self.id_sessao_ativa = None
            self.ignorar_horario_grade = False
            self.dia_semana_grade = None

    def atualizar_detalhes_sessao(
        self, id_sessao: int, dados_sessao: Dict[str, Any]
    ) -> None:
        """Atualiza os detalhes de uma sessão (data, hora, etc.)."""
        sessao_service.atualizar_sessao(self._repo_sessao, id_sessao, dados_sessao)

    def atualizar_grupos_sessao(
        self,
        grupos: List[str],
        excecao_grupos: Optional[Sequence[str]] = None,
    ) -> None:
        """Atualiza a configuração de grupos para a sessão ativa."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")

        if excecao_grupos is not None:
            self.excecao_grupos = set(excecao_grupos)

        sessao_service.atualizar_grupos_sessao(
            self._repo_sessao, self._repo_grupo, self.id_sessao_ativa, grupos
        )

    def atualizar_grupos_sessao_ativa(
        self,
        grupos: List[str],
        excecao_grupos: Optional[Sequence[str]] = None,
    ) -> None:
        """
        Alias para atualizar_grupos_sessao (mantém compatibilidade com chamadas legadas da GUI).

        .. deprecated:: 2.0
           Utilize `atualizar_grupos_sessao`.
        """
        self.atualizar_grupos_sessao(
            grupos,
            excecao_grupos=excecao_grupos,
        )

    def definir_excecao_grupos(self, grupos: Set[str]) -> None:
        """Define o conjunto de turmas de exceção para a sessão ativa e persiste o estado."""
        self.excecao_grupos = set(grupos)
        if self.id_sessao_ativa is not None:
            self.salvar_estado_sessao()

    def definir_ignorar_horario_grade(self, ignorar: bool) -> None:
        """
        Define se a trava de horário da grade horária deve ser ignorada na sessão ativa
        (mantendo a validação das turmas/categorias) e persiste o estado em session.json.
        """
        self.ignorar_horario_grade = bool(ignorar)
        if self.id_sessao_ativa is not None:
            self.salvar_estado_sessao()

    def atualizar_sessao_ativa(
        self,
        item_servido: Optional[str] = None,
        turmas: Optional[List[str]] = None,
    ) -> bool:
        """
        Atualiza o cardápio (item servido) e as turmas/categorias participantes
        da sessão atualmente ativa sem precisar fechá-la.
        """
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")

        dados_atualizacao: Dict[str, Any] = {}
        if item_servido is not None:
            dados_atualizacao["item_servido"] = item_servido

        if dados_atualizacao:
            self.atualizar_detalhes_sessao(self.id_sessao_ativa, dados_atualizacao)

        if turmas is not None:
            self.atualizar_grupos_sessao(turmas)

        return True

    def adicionar_novo_lanche_bidirecional(self, item_lanche: str) -> None:
        """
        Envia em background um novo item de lanche para ser salvo na aba
        'Lanches' da planilha do Google Sheets conectada.
        """

        def _worker():
            try:
                sync_service.sincronizar_novo_lanche_para_planilha(item_lanche)
            except (ErroAPIGoogle, OSError, ValueError) as e:
                logger.warning("Falha assíncrona ao sincronizar lanche: %s", e)

        threading.Thread(target=_worker, daemon=True).start()

    def carregar_estado_sessao(self) -> Optional[Dict[str, Any]]:
        """Carrega o estado da sessão a partir da persistência e ativa a sessão se existir."""
        return sessao_service.carregar_estado_sessao(self)

    def salvar_estado_sessao(self, id_sessao: Optional[int] = None) -> bool:
        """Persiste o identificador da sessão ativa."""
        return sessao_service.salvar_estado_sessao(self, id_sessao)

    def limpar_estado_sessao(self) -> bool:
        """Remove a persistência de sessão e limpa a sessão ativa."""
        return sessao_service.limpar_estado_sessao(self)
