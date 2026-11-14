# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/_facade_consumo.py (Mixin de Consumo e Grade Horária)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""Mixin responsável pelo registro de consumos, grade horária e estatísticas."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from registro.nucleo import constants
from registro.nucleo.exceptions import ErroSessaoNaoAtiva
from registro.nucleo.services import (
    consumo_service,
    grade_horarios_service,
    sessao_service,
    stats_service,
)

if TYPE_CHECKING:
    from registro.nucleo.repository import (
        RepositorioConsumo,
        RepositorioEstudante,
        RepositorioGrupo,
        RepositorioReserva,
        RepositorioSessao,
    )


class _FacadeConsumoMixin:
    """Agrupa operações de consumo, elegibilidade, grade horária e estatísticas."""

    if TYPE_CHECKING:
        _repo_sessao: RepositorioSessao
        _repo_estudante: RepositorioEstudante
        _repo_reserva: RepositorioReserva
        _repo_consumo: RepositorioConsumo
        _repo_grupo: RepositorioGrupo
        id_sessao_ativa: Optional[int]
        excecao_grupos: Set[str]
        ignorar_horario_grade: bool
        dia_semana_grade: Optional[str]

        def listar_todos_os_grupos(self) -> List[Dict[str, Any]]: ...

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

        return consumo_service.registrar_consumo(
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

        return consumo_service.registrar_consumo_com_reserva(
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
        return consumo_service.desfazer_consumo_por_prontuario(
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
        return consumo_service.desfazer_consumo(
            self._repo_consumo, id_consumo, operador=operador, motivo=motivo
        )

    def atualizar_consumo(
        self,
        id_consumo: int,
        hora_consumo: Optional[str] = None,
        prato: Optional[str] = None,
    ) -> bool:
        """Atualiza horário de consumo e/ou prato associado a um registro existente."""
        return consumo_service.atualizar_consumo(
            self._repo_consumo,
            self._repo_reserva,
            id_consumo=id_consumo,
            hora_consumo=hora_consumo,
            prato=prato,
        )

    def obter_dia_semana_atual(self) -> str:
        """Retorna o dia da semana atual no formato da grade (ex.: 'segunda', 'terca')."""
        return grade_horarios_service.obter_dia_semana_atual()

    def obter_turmas_previstas_para_refeicao(
        self,
        refeicao: str,
        dia_semana: Optional[str] = None,
        incluir_categorias: bool = False,
    ) -> List[str]:
        """Retorna as turmas (e opcionalmente categorias) previstas na grade horária."""
        dias_validos = {
            "segunda",
            "terca",
            "quarta",
            "quinta",
            "sexta",
            "sabado",
            "domingo",
            "seg",
            "ter",
            "qua",
            "qui",
            "sex",
            "sab",
            "dom",
        }
        mapa_curto = {
            "seg": "segunda",
            "ter": "terca",
            "qua": "quarta",
            "qui": "quinta",
            "sex": "sexta",
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
        return grade_horarios_service.carregar_grade_horarios()

    def salvar_grade_horarios(self, grade: Dict[str, Any]) -> None:
        """Persiste o dicionário atualizado da grade horária semanal."""
        grade_horarios_service.salvar_grade_horarios(grade)

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

        todos_elegiveis = sessao_service.obter_estudantes_para_sessao(
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

        return sessao_service.obter_estudantes_para_sessao(
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

    def obter_estatisticas_dashboard(self) -> Dict[str, Any]:
        """Retorna estatísticas consolidadas para visualização no dashboard."""
        return stats_service.obter_estatisticas_dashboard(
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

        return stats_service.obter_estatisticas_sessao(
            repo_sessao=self._repo_sessao,
            repo_estudante=self._repo_estudante,
            repo_reserva=self._repo_reserva,
            repo_consumo=self._repo_consumo,
            repo_grupo=self._repo_grupo,
            id_sessao=alvo_id,
            excecao_grupos=self.excecao_grupos,
        )
