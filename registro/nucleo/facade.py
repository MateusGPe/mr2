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

import datetime as dt
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Union

from sqlalchemy.exc import SQLAlchemyError
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

    def fechar_conexao(self):
        """Fecha a conexão com o banco de dados."""
        self._sessao_db.close()

    def expirar_cache_sessao(self):
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

    # --- Gestão de Sessões ---

    def iniciar_nova_sessao(self, dados_sessao: DADOS_SESSAO) -> Optional[int]:
        """Inicia uma nova sessão de refeição e a define como ativa."""
        id_sessao = service_logic.iniciar_nova_sessao(
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
        return service_logic.listar_todas_sessoes(self._repo_sessao)

    def definir_sessao_ativa(self, id_sessao: int):
        """Define uma sessão existente como ativa pelo seu ID."""
        service_logic.obter_detalhes_sessao(self._repo_sessao, id_sessao)
        if self.id_sessao_ativa != id_sessao:
            self.ignorar_horario_grade = False
            self.dia_semana_grade = None
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
        self.ignorar_horario_grade = False
        self.dia_semana_grade = None

    def deletar_sessao(self, id_sessao: int):
        """Deleta uma sessão específica e todos os seus consumos associados."""
        service_logic.deletar_sessao(self._repo_sessao, id_sessao)
        if self.id_sessao_ativa == id_sessao:
            self.id_sessao_ativa = None
            self.ignorar_horario_grade = False
            self.dia_semana_grade = None

    def atualizar_detalhes_sessao(self, id_sessao: int, dados_sessao: Dict[str, Any]):
        """Atualiza os detalhes de uma sessão (data, hora, etc.)."""
        service_logic.atualizar_sessao(self._repo_sessao, id_sessao, dados_sessao)

    def atualizar_grupos_sessao(
        self,
        grupos: List[str],
        excecao_grupos: Optional[Sequence[str]] = None,
    ):
        """Atualiza a configuração de grupos para a sessão ativa."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")

        if excecao_grupos is not None:
            self.excecao_grupos = set(excecao_grupos)

        service_logic.atualizar_grupos_sessao(
            self._repo_sessao, self._repo_grupo, self.id_sessao_ativa, grupos
        )

    def atualizar_grupos_sessao_ativa(
        self,
        grupos: List[str],
        excecao_grupos: Optional[Sequence[str]] = None,
    ):
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

        dados_atualizacao = {}
        if item_servido is not None:
            dados_atualizacao["item_servido"] = item_servido

        if dados_atualizacao:
            self.atualizar_detalhes_sessao(self.id_sessao_ativa, dados_atualizacao)

        if turmas is not None:
            self.atualizar_grupos_sessao(turmas)

        return True

    def adicionar_novo_lanche_bidirecional(self, item_lanche: str):
        """
        Envia em background um novo item de lanche para ser salvo na aba
        'Lanches' da planilha do Google Sheets conectada.
        """
        import threading

        from registro.nucleo.services import sync_service

        def _worker():
            from registro.nucleo.exceptions import ErroAPIGoogle

            try:
                sync_service.sincronizar_novo_lanche_para_planilha(item_lanche)
            except (ErroAPIGoogle, OSError, ValueError) as e:
                logger.warning("Falha assíncrona ao sincronizar lanche: %s", e)

        threading.Thread(target=_worker, daemon=True).start()

    # --- Registro e Cancelamento de Consumo ---

    def registrar_consumo(
        self,
        prontuario: str,
        excecao_grupos: Optional[Set[str]] = None,
        pular_grupos: bool = False,
        permitir_fora_horario: bool = False,
    ) -> Dict[str, Any]:
        """Registra que um estudante consumiu uma refeição, seguindo as regras."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")

        prontuario_limpo = (prontuario or "").strip().upper()
        grupos_filtro = excecao_grupos or self.excecao_grupos

        return service_logic.registrar_consumo(
            repo_sessao=self._repo_sessao,
            repo_estudante=self._repo_estudante,
            repo_reserva=self._repo_reserva,
            repo_consumo=self._repo_consumo,
            id_sessao=self.id_sessao_ativa,
            prontuario=prontuario_limpo,
            excecao_grupos=grupos_filtro,
            pular_grupos=pular_grupos,
            permitir_fora_horario=permitir_fora_horario,
            ignorar_horario_grade=self.ignorar_horario_grade,
            dia_semana_grade=self.dia_semana_grade,
        )

    def registrar_consumo_com_reserva(
        self,
        prontuario: str,
        excecao_grupos: Optional[Set[str]] = None,
        pular_grupos: bool = False,
        permitir_fora_horario: bool = False,
    ) -> Dict[str, Any]:
        """Registra consumo de refeição exclusivamente para quem possui reserva."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")

        prontuario_limpo = (prontuario or "").strip().upper()
        grupos_filtro = excecao_grupos or self.excecao_grupos

        return service_logic.registrar_consumo_com_reserva(
            repo_sessao=self._repo_sessao,
            repo_estudante=self._repo_estudante,
            repo_reserva=self._repo_reserva,
            repo_consumo=self._repo_consumo,
            id_sessao=self.id_sessao_ativa,
            prontuario=prontuario_limpo,
            excecao_grupos=grupos_filtro,
            pular_grupos=pular_grupos,
            permitir_fora_horario=permitir_fora_horario,
            ignorar_horario_grade=self.ignorar_horario_grade,
            dia_semana_grade=self.dia_semana_grade,
        )

    def desfazer_consumo_por_prontuario(
        self,
        prontuario: str,
        operador: str = "Operador",
        motivo: str = "Cancelado pelo operador",
    ) -> bool:
        """Desfaz logicamente o registro de consumo de uma refeição na sessão ativa."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa para desfazer o consumo.")

        prontuario_limpo = (prontuario or "").strip().upper()
        return service_logic.desfazer_consumo_por_prontuario(
            self._repo_consumo,
            prontuario_limpo,
            self.id_sessao_ativa,
            operador=operador,
            motivo=motivo,
        )

    def desfazer_consumo(
        self,
        id_consumo: int,
        operador: str = "Operador",
        motivo: str = "Cancelado pelo operador",
    ) -> bool:
        """Desfaz logicamente o registro de consumo específico pelo ID."""
        return service_logic.desfazer_consumo(
            self._repo_consumo, id_consumo, operador=operador, motivo=motivo
        )

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
        self,
        prontuario: str,
        nome: str,
        grupos: Optional[List[str]] = None,
        categoria: Optional[str] = None,
        categorias: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Cria um novo estudante e associa às turmas e categorias especificadas."""
        return service_logic.criar_estudante(
            self._repo_estudante,
            self._repo_grupo,
            prontuario,
            nome,
            grupos,
            categoria=categoria,
            categorias=categorias,
        )

    # --- Gestão de Grade Horária e Escalonamento ---

    def obter_dia_semana_atual(self) -> str:
        """Retorna o dia da semana atual no formato da grade (ex.: 'segunda', 'terca')."""
        from registro.nucleo.services import grade_horarios_service

        return grade_horarios_service.obter_dia_semana_atual()

    def obter_turmas_previstas_para_refeicao(
        self,
        refeicao: str,
        dia_semana: Optional[str] = None,
        incluir_categorias: bool = False,
    ) -> List[str]:
        """Retorna as turmas (e opcionalmente categorias) previstas na grade horária."""
        from registro.nucleo import constants
        from registro.nucleo.services import grade_horarios_service

        dias_validos = {
            "segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo",
            "seg", "ter", "qua", "qui", "sex", "sab", "dom",
        }
        mapa_curto = {
            "seg": "segunda", "ter": "terca", "qua": "quarta", "qui": "quinta", "sex": "sexta"
        }

        arg1 = (refeicao or "").strip().lower()
        arg2 = (dia_semana or "").strip().lower() if dia_semana else ""

        if arg1 in dias_validos and (not arg2 or arg2 not in dias_validos):
            dia_final = mapa_curto.get(arg1, arg1)
            ref_final = arg2 or "lanche"
        else:
            dia_final = (
                mapa_curto.get(arg2, arg2)
                if arg2
                else grade_horarios_service.obter_dia_semana_atual()
            )
            ref_final = arg1 or "lanche"
        ref_final = ref_final.replace("ç", "c")

        grupos_cadastrados = self.listar_todos_os_grupos()
        turmas_disponiveis = [
            g["nome"]
            for g in grupos_cadastrados
            if g.get("nome") and g.get("tipo") != constants.TIPO_GRUPO_CATEGORIA
        ]
        categorias_disponiveis = [
            g["nome"]
            for g in grupos_cadastrados
            if g.get("nome") and g.get("tipo") == constants.TIPO_GRUPO_CATEGORIA
        ]

        return grade_horarios_service.obter_turmas_previstas_para_refeicao(
            dia_semana=dia_final,
            refeicao=ref_final,
            incluir_categorias=incluir_categorias,
            turmas_disponiveis=turmas_disponiveis,
            categorias_disponiveis=categorias_disponiveis,
        )

    def obter_grade_horarios(self) -> Dict[str, Any]:
        """Carrega e retorna o dicionário completo da grade horária semanal."""
        from registro.nucleo.services import grade_horarios_service

        return grade_horarios_service.carregar_grade_horarios()

    def salvar_grade_horarios(self, grade: Dict[str, Any]) -> None:
        """Persiste o dicionário atualizado da grade horária semanal."""
        from registro.nucleo.services import grade_horarios_service

        grade_horarios_service.salvar_grade_horarios(grade)

    def atualizar_estudante(
        self,
        id_estudante: int,
        dados: Dict[str, Any],
        grupos: Optional[List[str]] = None,
        categorias: Optional[List[str]] = None,
    ) -> bool:
        """Atualiza os dados de um estudante e suas turmas/categorias associadas."""
        return service_logic.atualizar_estudante(
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
        pular_grupos: bool = False,
    ) -> List[Dict[str, str]]:
        """
        Retorna estudantes elegíveis não consumidos em formato simplificado (apenas prontuário e nome).

        .. note::
           Método preservado para compatibilidade. A interface gráfica consome
           `obter_estudantes_para_sessao`, que fornece o conjunto completo com turmas,
           categoria e status de atendimento.
        """
        if self.id_sessao_ativa is None:
            return []

        grupos_filtro = excecao_grupos or self.excecao_grupos

        todos_elegiveis = service_logic.obter_estudantes_para_sessao(
            repo_sessao=self._repo_sessao,
            repo_estudante=self._repo_estudante,
            repo_reserva=self._repo_reserva,
            repo_consumo=self._repo_consumo,
            repo_grupo=self._repo_grupo,
            id_sessao=self.id_sessao_ativa,
            consumido=False,
            excecao_grupos=grupos_filtro,
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
    ) -> List[Dict[str, Any]]:
        """Retorna estudantes para a sessão ativa, com filtro opcional por consumo."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")

        grupos_filtro = excecao_grupos or self.excecao_grupos

        return service_logic.obter_estudantes_para_sessao(
            repo_sessao=self._repo_sessao,
            repo_estudante=self._repo_estudante,
            repo_reserva=self._repo_reserva,
            repo_consumo=self._repo_consumo,
            repo_grupo=self._repo_grupo,
            id_sessao=self.id_sessao_ativa,
            consumido=consumido,
            excecao_grupos=grupos_filtro,
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
        return service_logic.listar_reservas(
            self._repo_grupo, self._repo_reserva, filtros
        )

    def listar_datas_reservas(self) -> List[str]:
        """Retorna uma lista única de datas de reservas existentes."""
        return service_logic.listar_datas_reservas(self._repo_reserva)

    def atualizar_reserva(self, id_reserva: int, dados: Dict[str, Any]) -> bool:
        """Atualiza os dados de uma reserva existente."""
        return service_logic.atualizar_reserva(
            self._repo_reserva, id_reserva, dados, repo_grupo=self._repo_grupo
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
        return service_logic.exportar_sessao_para_xlsx(
            self._repo_sessao, self._repo_consumo, id_sessao_alvo, caminho_destino
        )

    def exportar_consumos_para_xlsx(
        self,
        nome_arquivo: Optional[Path] = None,
    ) -> str:
        """Exporta todos os dados de consumo para um arquivo XLSX."""
        return service_logic.exportar_todos_os_consumos_para_xlsx(
            self._repo_consumo, nome_arquivo
        )

    def sincronizar_do_google_sheets(self, caminho_config: Optional[Path] = None):
        """Sincroniza a base de dados local a partir do Google Sheets (com isolamento thread-safe)."""
        import threading

        if threading.current_thread() is not threading.main_thread() and self._deve_fechar_sessao:
            with FachadaRegistro() as fachada_worker:
                return service_logic.sincronizar_do_google_sheets(
                    fachada_worker._repo_estudante,
                    fachada_worker._repo_reserva,
                    fachada_worker._repo_grupo,
                    caminho_config=caminho_config,
                )
        return service_logic.sincronizar_do_google_sheets(
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
        import threading

        if threading.current_thread() is not threading.main_thread() and self._deve_fechar_sessao:
            with FachadaRegistro() as fachada_worker:
                return service_logic.sincronizar_para_google_sheets(
                    fachada_worker._repo_sessao,
                    fachada_worker._repo_consumo,
                    self.id_sessao_ativa,
                )
        return service_logic.sincronizar_para_google_sheets(
            self._repo_sessao, self._repo_consumo, self.id_sessao_ativa
        )

    def sincronizar_todas_sessoes_para_google_sheets(self):
        """Envia os dados de consumo de todas as sessões para o Google Sheets."""
        import threading

        if threading.current_thread() is not threading.main_thread() and self._deve_fechar_sessao:
            with FachadaRegistro() as fachada_worker:
                return service_logic.sincronizar_todas_sessoes_para_google_sheets(
                    fachada_worker._repo_sessao,
                    fachada_worker._repo_consumo,
                )
        return service_logic.sincronizar_todas_sessoes_para_google_sheets(
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
        except SQLAlchemyError as e:
            logger.error("Falha ao registrar log de sincronização no BD: %s", e)
            self._sessao_db.rollback()
            return False

    # --- Subsistema Unificado de Importação ---

    def salvar_importacao_dados(self, dados: List[Dict[str, Any]]) -> Dict[str, int]:
        """Persiste em lote estudantes e reservas decorrentes de um processo de importação."""
        return service_logic.salvar_importacao_dados(
            self._repo_estudante,
            self._repo_reserva,
            dados,
            repo_grupo=self._repo_grupo,
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
            tipo: 'simples' (txt), 'header' (csv c/ cabeçalho), 'excel' (.xlsx), 'sheets', ou 'auto'.
        """
        from registro.nucleo.importar.strategies import criar_estrategia_carregamento

        estrategia = criar_estrategia_carregamento(caminho, tipo=tipo)
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

    def criar_grupo(
        self, nome: str, ativo: bool = True, tipo: str = "turma"
    ) -> Dict[str, Any]:
        """Cria uma nova turma ou categoria no sistema."""
        return service_logic.criar_grupo(
            self._repo_grupo, nome, ativo=ativo, tipo=tipo
        )

    def atualizar_grupo(self, id_grupo: int, dados: Dict[str, Any]) -> bool:
        """Atualiza nome, tipo e/ou status de uma turma ou categoria."""
        return service_logic.atualizar_grupo(self._repo_grupo, id_grupo, dados)

    def deletar_grupo(self, id_grupo: int, forcar: bool = False) -> Dict[str, Any]:
        """Exclui uma turma (com validação se possui alunos ou sessões vinculadas)."""
        return service_logic.deletar_grupo(self._repo_grupo, id_grupo, forcar=forcar)

    def listar_turmas_detalhadas(
        self, termo_busca: Optional[str] = None, tipo: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Lista grupos (turmas e categorias) com quantidade de alunos, tipo e status."""
        return service_logic.listar_turmas_detalhadas(
            self._repo_grupo, termo_busca=termo_busca, tipo=tipo
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
            excecao_grupos=self.excecao_grupos,
        )

