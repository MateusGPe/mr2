# --- Arquivo: registro/importar/service.py ---

"""
Gerencia o estado e a lógica de uma sessão de importação de ponta a ponta.
Orquestra o carregamento, análise, resolução e execução da importação.
"""

from typing import Dict, List, Optional

from registro.importar.analyzer import AnalisadorDeLinhas
from registro.importar.definitions import AcaoFinal, LimiaresConfianca, LinhaAnalisada
from registro.importar.exceptions import ErroSessaoImportacao
from registro.importar.strategies import EstrategiaCarregamento
from registro.nucleo.facade import FachadaRegistro


class ServicoImportacao:
    """Gerencia uma única sessão de importação."""

    def __init__(self, fachada_nucleo: FachadaRegistro):
        self._fachada_nucleo = fachada_nucleo
        self._linhas_analisadas: List[LinhaAnalisada] = []
        self._proximo_id_linha = 1

    def iniciar_analise(
        self, estrategia: EstrategiaCarregamento, fonte: str
    ) -> List[LinhaAnalisada]:
        """
        Inicia o processo: carrega os dados usando uma estratégia e os analisa.
        """
        # Limpa o estado de sessões anteriores
        self._linhas_analisadas = []
        self._proximo_id_linha = 1

        dados_brutos = estrategia.carregar(fonte)

        # Configuração dos limiares de confiança para o match
        limiares: LimiaresConfianca = {"match_automatico": 95, "match_ambiguo": 80}

        analisador = AnalisadorDeLinhas(self._fachada_nucleo.repo_estudante, limiares)

        for dados_linha in dados_brutos:
            # Assume que os dados já vêm mapeados pela estratégia
            linha_analisada = analisador.analisar_linha(
                id_linha=self._proximo_id_linha,
                dados_originais=dados_linha,
                dados_mapeados=dados_linha.copy(),
            )
            # A ação final inicial é a mesma que a sugerida
            linha_analisada["acao_final"] = linha_analisada["acao_final_sugerida"]
            self._linhas_analisadas.append(linha_analisada)
            self._proximo_id_linha += 1

        return self._linhas_analisadas

    def obter_linhas_analisadas(self) -> List[LinhaAnalisada]:
        """Retorna o estado atual das linhas analisadas."""
        return self._linhas_analisadas

    def atualizar_acao_linha(
        self,
        id_linha: int,
        acao: AcaoFinal,
        id_estudante_resolvido: Optional[int] = None,
    ):
        """
        Permite que a interface de usuário atualize a ação para uma linha
        específica, por exemplo, após uma escolha manual.
        """
        for linha in self._linhas_analisadas:
            if linha["id_linha"] == id_linha:
                linha["acao_final"] = acao
                if id_estudante_resolvido:
                    # Armazena o ID do estudante escolhido para a criação da reserva
                    linha["dados_mapeados"][
                        "_estudante_id_resolvido"
                    ] = id_estudante_resolvido
                return
        raise ErroSessaoImportacao(f"Linha com ID {id_linha} não encontrada.")

    def executar_importacao(self) -> Dict[str, int]:
        """
        Executa as ações finais definidas para cada linha, persistindo os
        dados no banco de dados de forma otimizada.
        """
        if not self._linhas_analisadas:
            raise ErroSessaoImportacao("Nenhuma análise foi iniciada para executar.")

        reservas_para_criar = []
        estudantes_para_criar = []

        # 1. Separa os dados para criação
        for linha in self._linhas_analisadas:
            acao = linha["acao_final"]
            dados = linha["dados_mapeados"]

            if acao == "IGNORAR":
                continue

            # Prepara a reserva base
            reserva_payload = {
                "prato": dados.get("prato", "Não especificado"),
                "data": dados.get("data"),
                "cancelada": False,
            }

            if acao == "CRIAR_RESERVA":
                id_estudante = dados.get("_estudante_id_resolvido")
                if id_estudante:
                    reserva_payload["estudante_id"] = id_estudante
                    reservas_para_criar.append(reserva_payload)

            elif acao == "CRIAR_ALUNO_E_RESERVA":
                prontuario = dados.get("prontuario")
                novo_estudante = {
                    "prontuario": prontuario,
                    "nome": dados.get("nome"),
                    "ativo": True,
                }
                estudantes_para_criar.append(novo_estudante)

                # Associa a reserva ao prontuário para resolução posterior
                reserva_payload["_prontuario_"] = prontuario
                reservas_para_criar.append(reserva_payload)

        # 2. Executa as operações no banco de dados
        # NOTA: Para máxima eficiência, a FachadaRegistro deveria ter métodos
        # de criação em massa que chamam os `criar_em_massa` dos repositórios.
        # Aqui, estamos chamando diretamente para simplificar.
        if estudantes_para_criar:
            self._fachada_nucleo.repo_estudante.criar_em_massa(estudantes_para_criar)

        # 3. Mapeia prontuários para IDs para as novas reservas
        if any("_prontuario_" in res for res in reservas_para_criar):
            prontuarios = {est["prontuario"] for est in estudantes_para_criar}
            estudantes_criados = self._fachada_nucleo.repo_estudante.por_prontuarios(
                prontuarios
            )
            mapa_prontuario_id = {e.prontuario: e.id for e in estudantes_criados}

            for res in reservas_para_criar:
                if "_prontuario_" in res:
                    pront = res.pop("_prontuario_")
                    res["estudante_id"] = mapa_prontuario_id.get(pront)

        # 4. Cria as reservas
        reservas_finais = [
            res for res in reservas_para_criar if res.get("estudante_id")
        ]
        if reservas_finais:
            self._fachada_nucleo.repo_reserva.criar_em_massa(reservas_finais)

        self._fachada_nucleo.repo_sessao.obter_sessao().commit()

        return {
            "alunos_criados": len(estudantes_para_criar),
            "reservas_criadas": len(reservas_finais),
        }
