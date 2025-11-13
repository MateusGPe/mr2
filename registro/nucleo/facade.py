# --- Arquivo: registro/nucleo/facade.py ---

"""
Fornece uma Fachada de alto nível para interagir com o subsistema
do núcleo de registro.

Qualquer aplicação cliente deve interagir exclusivamente com a classe
FachadaRegistro, que gerencia internamente a sessão do banco de dados,
os repositórios e a lógica de serviço.
"""

import re
from typing import Any, Dict, List, Optional, Sequence, Set

from fuzzywuzzy import fuzz

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

REGEX_LIMPEZA_PRONTUARIO: re.Pattern[str] = re.compile(r"^[Ii][Qq]30+")


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

        self.repo_estudante = RepositorioEstudante(self._sessao_db)
        self.repo_reserva = RepositorioReserva(self._sessao_db)
        self.repo_sessao = RepositorioSessao(self._sessao_db)
        self.repo_consumo = RepositorioConsumo(self._sessao_db)
        self.repo_grupo = RepositorioGrupo(self._sessao_db)

        self.id_sessao_ativa: Optional[int] = None
        self.excessao_grupos: Set[str] = set()

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
            self.repo_sessao, self.repo_grupo, self.repo_reserva, dados_sessao
        )
        if id_sessao is None:
            return None
        self.id_sessao_ativa = id_sessao
        return id_sessao

    def listar_todas_sessoes(self) -> List[Dict[str, Any]]:
        """Retorna uma lista simplificada de todas as sessões."""
        return service_logic.listar_todas_sessoes(self.repo_sessao)

    def listar_todos_os_grupos(self) -> List[Dict[str, Any]]:
        """Retorna uma lista de todos os grupos existentes."""
        return service_logic.listar_todos_os_grupos(self.repo_grupo)

    def definir_sessao_ativa(self, id_sessao: int):
        """Define uma sessão existente como ativa pelo seu ID."""
        service_logic.obter_detalhes_sessao(self.repo_sessao, id_sessao)
        self.id_sessao_ativa = id_sessao

    def obter_detalhes_sessao_ativa(self) -> Dict[str, Any]:
        """Retorna um dicionário com os detalhes da sessão ativa."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")
        modelo_sessao = service_logic.obter_detalhes_sessao(
            self.repo_sessao, self.id_sessao_ativa
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
        service_logic.deletar_sessao(self.repo_sessao, self.id_sessao_ativa)
        self.id_sessao_ativa = None

    def deletar_sessao(self, id_sessao: int):
        """Deleta uma sessão específica e todos os seus consumos associados."""
        service_logic.deletar_sessao(self.repo_sessao, id_sessao)
        if self.id_sessao_ativa == id_sessao:
            self.id_sessao_ativa = None

    def atualizar_detalhes_sessao(self, id_sessao: int, dados_sessao: Dict[str, Any]):
        """Atualiza os detalhes de uma sessão (data, hora, etc.)."""
        service_logic.atualizar_sessao(self.repo_sessao, id_sessao, dados_sessao)

    def registrar_consumo(
        self,
        prontuario: str,
        excecao_grupos: Optional[Set[str]] = None,
        pular_grupos: bool = False,
    ) -> Dict[str, Any]:
        """Registra que um estudante consumiu uma refeição, seguindo as regras."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")
        return service_logic.registrar_consumo(
            repo_sessao=self.repo_sessao,
            repo_estudante=self.repo_estudante,
            repo_reserva=self.repo_reserva,
            repo_consumo=self.repo_consumo,
            id_sessao=self.id_sessao_ativa,
            prontuario=prontuario,
            excecao_grupos=excecao_grupos or self.excessao_grupos,
            pular_grupos=pular_grupos,
        )

    def desfazer_consumo_por_prontuario(self, prontuario: str):
        """Desfaz o registro de consumo de uma refeição."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa para desfazer o consumo.")

        service_logic.desfazer_consumo_por_prontuario(
            self.repo_consumo, prontuario, self.id_sessao_ativa
        )

    def desfazer_consumo(self, id_consumo: int):
        """Desfaz o registro de consumo de uma refeição."""
        service_logic.desfazer_consumo(self.repo_consumo, id_consumo)

    def criar_estudante(
        self, prontuario: str, nome: str, grupos: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Cria um novo estudante, evitando duplicatas de prontuário."""
        existente = self.repo_estudante.ler_filtrado(prontuario=prontuario)
        if existente:
            raise ValueError(f"Estudante com prontuário {prontuario} já existe.")

        novo_estudante = self.repo_estudante.criar(
            {"prontuario": prontuario, "nome": nome}
        )

        if grupos:
            for grupo_nome in grupos:
                grupo = self.repo_grupo.por_nome(grupo_nome)
                if not grupo:
                    grupo = self.repo_grupo.criar({"nome": grupo_nome})
                novo_estudante.grupos.append(grupo)
        self._sessao_db.commit()
        return {
            "id": novo_estudante.id,
            "prontuario": novo_estudante.prontuario,
            "nome": novo_estudante.nome,
        }

    def atualizar_estudante(self, id_estudante: int, dados: Dict[str, Any]) -> bool:
        """Atualiza os dados de um estudante (ex: nome, status 'ativo')."""
        estudante = self.repo_estudante.atualizar(id_estudante, dados)
        if estudante:
            self._sessao_db.commit()
            return True
        return False

    def listar_estudantes_fuzzy(
        self, termo_busca: Optional[str] = None, limite: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Lista estudantes. Se um termo de busca é fornecido, realiza uma busca
        fuzzy com fuzzywuzzy por nome ou prontuário e ordena por relevância.
        """

        if not termo_busca or not termo_busca.strip():
            todos_estudantes = self.repo_estudante.ler_todos_com_grupos()
            estudantes_ordenados = sorted(todos_estudantes, key=lambda e: e.nome)
            estudantes = estudantes_ordenados
        else:
            termo_lower = termo_busca.lower().strip()
            pront_lower = REGEX_LIMPEZA_PRONTUARIO.sub("", termo_lower)
            candidatos = self.repo_estudante.ler_todos_com_grupos()
            resultados_com_score = []
            for est in candidatos:
                score_nome = fuzz.partial_ratio(termo_lower, est.nome.lower())
                score_pront = fuzz.ratio(
                    pront_lower,
                    REGEX_LIMPEZA_PRONTUARIO.sub("", est.prontuario.lower()),
                )

                final_score = max(score_nome, score_pront)

                if final_score >= limite:
                    resultados_com_score.append(
                        {"estudante": est, "score": final_score}
                    )

            resultados_com_score.sort(key=lambda x: x["score"], reverse=True)
            estudantes = [item["estudante"] for item in resultados_com_score]

        return [
            {
                "id": est.id,
                "prontuario": est.prontuario,
                "nome": est.nome,
                "ativo": est.ativo,
                "grupos": [g.nome for g in est.grupos],
            }
            for est in estudantes
        ]

    def listar_estudantes(
        self, termo_busca: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Lista todos os estudantes, com opção de busca por nome ou prontuário.
        """
        query = self._sessao_db.query(Estudante)
        if termo_busca:
            termo_like = f"%{termo_busca}%"

            query = query.filter(
                (Estudante.nome.ilike(termo_like))
                | (Estudante.prontuario.ilike(termo_like))
            )

        estudantes = query.order_by(Estudante.nome).all()

        return [
            {
                "id": est.id,
                "prontuario": est.prontuario,
                "nome": est.nome,
                "ativo": est.ativo,
                "grupos": [g.nome for g in est.grupos],
            }
            for est in estudantes
        ]

    def criar_reserva(
        self, prontuario_estudante: str, dados_reserva: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Cria uma nova reserva para um estudante.
        """
        estudantes = self.repo_estudante.ler_filtrado(prontuario=prontuario_estudante)
        if not estudantes:
            raise ValueError(
                f"Estudante com prontuário {prontuario_estudante} não encontrado."
            )

        payload = dados_reserva.copy()
        payload["estudante_id"] = estudantes[0].id

        nova_reserva = self.repo_reserva.criar(payload)
        self._sessao_db.commit()

        return {
            "id": nova_reserva.id,
            "estudante_id": nova_reserva.estudante_id,
            "prato": nova_reserva.prato,
            "data": nova_reserva.data,
            "cancelada": nova_reserva.cancelada,
        }

    def listar_reservas(
        self, filtros: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Lista todas as reservas, com suporte a filtros.
        """
        filtros = filtros or {}
        if "grupos" in filtros or "grupo" in filtros:
            grupos = set(filtros.get("grupos", [])) or set(
                filtros.get("grupo", ""),
            )
            grupos_ids = [g.id for g in self.repo_grupo.por_nomes(grupos)]
            reservas = self.repo_reserva.por_data_e_grupos(
                grupos_ids=grupos_ids, data_formatada=filtros.get("data")
            )
        else:
            reservas = self.repo_reserva.ler_filtrado(**filtros)

        return [
            {
                "id": res.id,
                "prontuario_estudante": res.estudante.prontuario,
                "nome_estudante": res.estudante.nome,
                "prato": res.prato,
                "data": res.data,
                "cancelada": res.cancelada,
            }
            for res in reservas
        ]

    def atualizar_reserva(self, id_reserva: int, dados: Dict[str, Any]) -> bool:
        """
        Atualiza os dados de uma reserva existente (ex: prato, data, status).
        """
        reserva = self.repo_reserva.atualizar(id_reserva, dados)
        if reserva:
            self._sessao_db.commit()
            return True
        return False

    def deletar_reserva(self, id_reserva: int) -> bool:
        """
        Remove uma reserva do sistema.
        """
        if self.repo_reserva.deletar(id_reserva):
            self._sessao_db.commit()
            return True
        return False

    def cancelar_reserva(self, id_reserva: int):
        """Marca uma reserva de refeição como cancelada."""
        service_logic.atualizar_cancelamento_reserva(
            self.repo_reserva, id_reserva, True
        )

    def reativar_reserva(self, id_reserva: int):
        """Remove a marcação de cancelada de uma reserva."""
        service_logic.atualizar_cancelamento_reserva(
            self.repo_reserva, id_reserva, False
        )

    def obter_estudantes_pesquisaveis_para_sessao(
        self, excessao_grupos: Optional[Set[str]] = None, pular_grupos: bool = False
    ) -> List[Dict[str, str]]:
        """
        Retorna uma lista de estudantes elegíveis (que não consumiram) para a busca,
        contendo apenas prontuário e nome. Otimizado para autocomplete.
        """
        if self.id_sessao_ativa is None:
            return []

        todos_elegiveis = service_logic.obter_estudantes_para_sessao(
            repo_sessao=self.repo_sessao,
            repo_estudante=self.repo_estudante,
            repo_reserva=self.repo_reserva,
            repo_consumo=self.repo_consumo,
            repo_grupo=self.repo_grupo,
            id_sessao=self.id_sessao_ativa,
            consumido=False,
            excessao_grupos=excessao_grupos or self.excessao_grupos,
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
    ) -> List[Dict[str, Any]]:
        """Retorna estudantes para a sessão ativa, com opção de filtro por consumo."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")
        return service_logic.obter_estudantes_para_sessao(
            repo_sessao=self.repo_sessao,
            repo_estudante=self.repo_estudante,
            repo_reserva=self.repo_reserva,
            repo_consumo=self.repo_consumo,
            repo_grupo=self.repo_grupo,
            id_sessao=self.id_sessao_ativa,
            consumido=consumido,
            excessao_grupos=self.excessao_grupos,
            pular_grupos=pular_grupos,
        )

    def atualizar_grupos_sessao(
        self, grupos: List[str], excessao_grupos: Optional[Sequence[str]] = None
    ):
        """Atualiza a configuração de grupos para a sessão ativa."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")

        if excessao_grupos is not None:
            self.excessao_grupos = set(excessao_grupos)

        service_logic.atualizar_grupos_sessao(
            self.repo_sessao, self.repo_grupo, self.id_sessao_ativa, grupos
        )

    def exportar_sessao_para_xlsx(self) -> str:
        """Exporta os dados de consumo da sessão ativa para um arquivo XLSX."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")
        return service_logic.exportar_sessao_para_xlsx(
            self.repo_sessao, self.repo_consumo, self.id_sessao_ativa
        )

    def sincronizar_do_google_sheets(self):
        """Sincroniza a base de dados local a partir de uma planilha do Google Sheets."""
        service_logic.sincronizar_do_google_sheets(
            self.repo_estudante, self.repo_reserva, self.repo_grupo
        )

    def sincronizar_para_google_sheets(self):
        """Envia os dados de consumo da sessão ativa para a planilha do Google Sheets."""
        if self.id_sessao_ativa is None:
            raise ErroSessaoNaoAtiva("Nenhuma sessão ativa definida.")
        service_logic.sincronizar_para_google_sheets(
            self.repo_sessao, self.repo_consumo, self.id_sessao_ativa
        )
