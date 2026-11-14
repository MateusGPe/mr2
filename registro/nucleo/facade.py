# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/facade.py (Fachada de Registro Unificada)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Fornece uma Fachada de alto nível para interagir com o subsistema
do núcleo de registro e importação.

Qualquer aplicação cliente (como GUI ou scripts CLI) deve interagir
exclusivamente com a classe FachadaRegistro, que gerencia internamente
a sessão do banco de dados, os repositórios, a lógica de serviço e a importação.
"""

import logging
import re
from typing import Any, Optional, Set

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from registro.nucleo._facade_cadastros import _FacadeCadastrosMixin
from registro.nucleo._facade_consumo import _FacadeConsumoMixin
from registro.nucleo._facade_sessoes import _FacadeSessoesMixin
from registro.nucleo.models import SessaoLocal, criar_banco_de_dados_e_tabelas
from registro.nucleo.repository import (
    RepositorioConsumo,
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
    RepositorioSessao,
)
from registro.nucleo.services.estudante_service import (
    REGEX_LIMPEZA_PRONTUARIO as _REGEX_LIMPEZA_PRONTUARIO,
)

logger = logging.getLogger(__name__)

REGEX_LIMPEZA_PRONTUARIO: re.Pattern[str] = _REGEX_LIMPEZA_PRONTUARIO


class FachadaRegistro(
    _FacadeSessoesMixin,
    _FacadeConsumoMixin,
    _FacadeCadastrosMixin,
):
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
            self._deve_fechar_sessao = False
        else:
            criar_banco_de_dados_e_tabelas()
            self._sessao_db = SessaoLocal()
            self._deve_fechar_sessao = True

        self._repo_estudante = RepositorioEstudante(self._sessao_db)
        self._repo_reserva = RepositorioReserva(self._sessao_db)
        self._repo_sessao = RepositorioSessao(self._sessao_db)
        self._repo_consumo = RepositorioConsumo(self._sessao_db)
        self._repo_grupo = RepositorioGrupo(self._sessao_db)

        self.id_sessao_ativa: Optional[int] = None
        self.excecao_grupos: Set[str] = set()
        self.ignorar_horario_grade: bool = False
        self.dia_semana_grade: Optional[str] = None
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

    # --- Gerenciamento de Conexão e Context Manager ---

    def fechar_conexao(self) -> None:
        """Fecha a conexão com o banco de dados."""
        self._sessao_db.close()

    def expirar_cache_sessao(self) -> None:
        """Invalida o cache em memória da sessão SQLAlchemy (após gravações em worker threads)."""
        try:
            self._sessao_db.expire_all()
        except SQLAlchemyError as e:
            logger.warning("Falha ao expirar cache da sessão SQLAlchemy: %s", e)

    def __enter__(self):
        """Permite o uso da Fachada como um gerenciador de contexto."""
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        """Garante que a conexão com o banco de dados seja fechada."""
        self.fechar_conexao()
