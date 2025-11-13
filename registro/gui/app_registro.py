# ----------------------------------------------------------------------------
# Arquivo: registro/view/app_registro.py (Aplicação Principal da UI)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

import json
import logging
import sys
import threading
import tkinter as tk
from threading import Thread
from tkinter import CENTER, TclError
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, cast

import ttkbootstrap as ttk
from ttkbootstrap.constants import HORIZONTAL, LEFT, LIGHT, RIGHT, VERTICAL, X
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.localization.msgcat import MessageCatalog

from registro.gui.constants import CAMINHO_SESSAO, DadosNovaSessao
from registro.gui.dialogo_filtro_turmas import DialogoFiltroTurmas
from registro.gui.dialogo_sessao import DialogoSessao
from registro.gui.painel_acao_busca import PainelAcaoBusca
from registro.gui.painel_status_registrados import PainelStatusRegistrados
from registro.gui.utils import capitalizar
from registro.nucleo.exceptions import ErroSessao, ErroSessaoNaoAtiva
from registro.nucleo.facade import FachadaRegistro
from registro.nucleo.utils import DADOS_SESSAO

logger = logging.getLogger(__name__)


class AppRegistro(tk.Tk):
    """
    Classe principal da aplicação de Registro de Refeições.

    Esta classe herda de tk.Tk e gerencia a janela principal, a inicialização
    dos componentes da UI, a comunicação com a camada de negócio (Fachada)
    e o ciclo de vida da aplicação.
    """

    def __init__(self, title: str = "Registro de Refeições"):
        super().__init__()
        self.title(title)
        self.protocol("WM_DELETE_WINDOW", self.ao_fechar_app)
        self.minsize(1152, 648)

        self._fachada: Optional[FachadaRegistro] = None
        self._barra_superior: Optional[ttk.Frame] = None
        self._janela_principal_dividida: Optional[ttk.Panedwindow] = None
        self._barra_status: Optional[ttk.Frame] = None
        self._painel_acao: Optional[PainelAcaoBusca] = None
        self._painel_status: Optional[PainelStatusRegistrados] = None
        self._label_info_sessao: Optional[ttk.Label] = None
        self._label_barra_status: Optional[ttk.Label] = None
        self._barra_progresso: Optional[ttk.Progressbar] = None
        self.style: Optional[ttk.Style] = None
        self.colors: Optional[Any] = None

        try:
            self._fachada = FachadaRegistro()
            self._configurar_estilo()
            self._configurar_layout_grid()
            self._criar_widgets()
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._tratar_erro_inicializacao("Inicialização da Aplicação", e)
            return

        self._carregar_sessao_inicial()

    def get_fachada(self) -> FachadaRegistro:
        """Retorna a instância da fachada, levantando um erro se não estiver inicializada."""
        if self._fachada is None:
            logger.critical("Tentativa de acessar Fachada não inicializada.")
            raise RuntimeError("FachadaRegistro não foi inicializada.")
        return self._fachada

    # --------------------------------------------------------------------------
    # Métodos de Configuração da UI
    # --------------------------------------------------------------------------

    def _configurar_estilo(self):
        """Configura o estilo da aplicação usando ttkbootstrap."""
        try:
            self.style = ttk.Style(theme="sandstone")
            fonte_padrao = ("Segoe UI", 12)
            fonte_cabecalho = (fonte_padrao[0], 10, "bold")
            fonte_label = (fonte_padrao[0], 11, "bold")
            fonte_pequena = (fonte_padrao[0], 9)

            self.style.configure("TLabelframe.Label", font=fonte_label)
            self.style.configure("Status.TLabel", font=fonte_pequena)
            self.style.configure("Feedback.TLabel", font=fonte_pequena)
            self.style.configure("Preview.TLabel", font=fonte_pequena, justify=LEFT)
            self.style.configure("Count.TLabel", font=fonte_cabecalho, anchor=CENTER)
            self.colors = self.style.colors
        except (TclError, AttributeError) as e:
            logger.warning("Erro ao configurar estilo ttkbootstrap: %s.", e)
            self.style = ttk.Style()
            self.colors = getattr(self.style, "colors", {})

    def _configurar_layout_grid(self):
        """Configura o layout de grid da janela principal."""
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

    def _criar_widgets(self):
        """Cria e posiciona os principais widgets da aplicação."""
        self._criar_barra_superior()
        self._criar_paineis_principais()
        self._criar_barra_status()

    def _criar_barra_superior(self):
        """Cria a barra superior com informações da sessão e botões de ação."""
        self._barra_superior = ttk.Frame(self, padding=(10, 5), bootstyle="dark")
        self._barra_superior.grid(row=0, column=0, sticky="ew")

        self._label_info_sessao = ttk.Label(
            self._barra_superior,
            text="Carregando Sessão...",
            font="-size 14 -weight bold",
            bootstyle="dark-inverse",
        )
        self._label_info_sessao.pack(side=LEFT, padx=(0, 20), anchor="w")

        frame_botoes = ttk.Frame(self._barra_superior, bootstyle="dark")
        frame_botoes.pack(side=RIGHT, anchor="e")

        botoes = [
            ("⚙️", self._abrir_dialogo_sessao),
            ("📊", self._abrir_dialogo_filtro_turmas),
        ]
        for texto, comando in botoes:
            ttk.Button(
                frame_botoes, text=texto, command=comando, bootstyle="dark"
            ).pack(side=RIGHT, padx=3)

        ttk.Separator(frame_botoes, orient=VERTICAL, bootstyle="light").pack(
            side=RIGHT, padx=8, fill="y", pady=3
        )

        botoes_sync = [
            ("📥", self._sincronizar_dados_mestre),
            ("📤", self.sincronizar_sessao_com_planilha),
            ("💾", self.exportar_e_encerrar_sessao),
        ]
        for texto, comando in botoes_sync:
            ttk.Button(
                frame_botoes, text=texto, command=comando, bootstyle="dark"
            ).pack(side=RIGHT, padx=3)

    def _criar_paineis_principais(self):
        """Cria os painéis de ação e de status, divididos por um Panedwindow."""
        if not self._fachada:
            return

        self._janela_principal_dividida = ttk.Panedwindow(
            self, orient=HORIZONTAL, bootstyle="light"
        )
        self._janela_principal_dividida.grid(
            row=1, column=0, sticky="nsew", padx=10, pady=(5, 0)
        )

        self._painel_acao = PainelAcaoBusca(
            self._janela_principal_dividida, self, self._fachada
        )
        self._janela_principal_dividida.add(self._painel_acao, weight=1)

        self._painel_status = PainelStatusRegistrados(
            self._janela_principal_dividida, self, self._fachada
        )
        self._janela_principal_dividida.add(self._painel_status, weight=2)

    def _criar_barra_status(self):
        """Cria a barra de status na parte inferior da janela."""
        self._barra_status = ttk.Frame(self, padding=(5, 3), bootstyle=LIGHT)
        self._barra_status.grid(row=2, column=0, sticky="ew")

        self._label_barra_status = ttk.Label(
            self._barra_status,
            text="Pronto.",
            bootstyle="inverse-light",
            font=("-size 10"),
        )
        self._label_barra_status.pack(side=LEFT, padx=5, anchor="w")

        self._barra_progresso = ttk.Progressbar(
            self._barra_status,
            mode="indeterminate",
            bootstyle="striped-info",
            length=200,
        )

    # --------------------------------------------------------------------------
    # Gerenciamento de Sessão
    # --------------------------------------------------------------------------

    def _carregar_sessao_inicial(self):
        """Tenta carregar uma sessão a partir de um arquivo ou abre o diálogo de sessão."""
        logger.info("Tentando carregar estado inicial da sessão...")
        info_sessao = self._carregar_arquivo_estado_sessao()
        if info_sessao:
            self._configurar_ui_para_sessao_carregada()
        else:
            self.after(100, self._abrir_dialogo_sessao)

    def _carregar_arquivo_estado_sessao(self) -> Optional[Dict[str, Any]]:
        """Lê o arquivo session.json e define a sessão ativa na fachada."""
        if not CAMINHO_SESSAO.exists():
            logger.info(
                "Arquivo de estado da sessão não encontrado: %s", CAMINHO_SESSAO
            )
            return None
        try:
            with open(CAMINHO_SESSAO, "r", encoding="utf-8") as f:
                dados_sessao = json.load(f)
            logger.info("Estado da sessão carregado: %s", CAMINHO_SESSAO)
            if self._fachada:
                self._fachada.definir_sessao_ativa(dados_sessao.get("id_sessao"))
            return dados_sessao
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Erro ao carregar estado da sessão de %s: %s", CAMINHO_SESSAO, e
            )
            return None

    def tratar_resultado_dialogo_sessao(
        self, resultado: Union[DadosNovaSessao, Dict, int, None]
    ) -> bool:
        """
        Callback para tratar o resultado do DialogoSessao (criar ou carregar sessão).
        Retorna True em caso de sucesso, False caso contrário.
        """
        if resultado is None:
            logger.info("Diálogo de sessão cancelado.")
            return True

        if not self._fachada:
            Messagebox.show_error(
                "Erro Interno", "Fachada não encontrada.", parent=self
            )
            return False

        sucesso = False
        desc_acao = ""
        try:
            if isinstance(resultado, int):
                id_sessao = resultado
                desc_acao = f"carregar sessão ID: {id_sessao}"
                self._fachada.definir_sessao_ativa(id_sessao)
                sucesso = True
            elif isinstance(resultado, dict):
                desc_acao = f"criar nova sessão: {resultado.get('refeicao')}"
                id_sessao = self._fachada.iniciar_nova_sessao(
                    cast(DADOS_SESSAO, resultado)
                )
                if id_sessao is None:
                    raise ErroSessao(
                        "Não é possível iniciar sessão sem reservas ativas."
                    )

                CAMINHO_SESSAO.write_text(
                    f'{{"id_sessao": {id_sessao}}}', encoding="utf-8"
                )
                sucesso = True
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Falha ao %s", desc_acao)
            Messagebox.show_error(
                f"Não foi possível {desc_acao}.\nErro: {e}",
                "Operação Falhou",
                parent=self,
            )
            return False

        if sucesso:
            logger.info("Sucesso ao %s.", desc_acao)
            self._configurar_ui_para_sessao_carregada()
        return sucesso

    def exportar_e_encerrar_sessao(self):
        """Exporta os dados da sessão para Excel e, se bem-sucedido, encerra a sessão."""
        if not self._fachada or self._fachada.id_sessao_ativa is None:
            Messagebox.show_warning(
                "Nenhuma Sessão Ativa", "Não há sessão para encerrar.", parent=self
            )
            return

        if Messagebox.yesno(
            "Confirmar Encerramento",
            "Deseja exportar os dados e encerrar esta sessão?",
            icon="warning",
            parent=self,
        ) == MessageCatalog.translate("No"):
            return

        export_ok = self.exportar_sessao_para_excel()
        if not export_ok:
            if Messagebox.yesno(
                "Falha na Exportação",
                "A exportação falhou. Deseja encerrar mesmo assim?",
                icon="error",
                parent=self,
            ) == MessageCatalog.translate("No"):
                return

        CAMINHO_SESSAO.unlink(missing_ok=True)
        self.ao_fechar_app(acionado_por_fim_sessao=True)

    # --------------------------------------------------------------------------
    # Atualização da UI e Notificações
    # --------------------------------------------------------------------------

    def _configurar_ui_para_sessao_carregada(self):
        """Atualiza a UI com os detalhes da sessão ativa."""
        if not self._fachada:
            return

        try:
            detalhes = self._fachada.obter_detalhes_sessao_ativa()
            refeicao = capitalizar(detalhes.get("refeicao", "?"))
            hora = detalhes.get("hora", "??")
            data = detalhes.get("data", "")
            id_sessao = detalhes.get("id")

            titulo = f"Reg: {refeicao} - {data} {hora} [ID:{id_sessao}]"
            self.title(titulo)
            if self._label_info_sessao:
                self._label_info_sessao.config(text=titulo, bootstyle="inverse-dark")

            if self._painel_acao:
                self._painel_acao.habilitar_controles()
                self._painel_acao.atualizar_resultados()
            if self._painel_status:
                self._painel_status.carregar_estudantes_registrados()

            self._focar_janela()
            logger.info("UI configurada para sessão ID: %s", id_sessao)

        except ErroSessaoNaoAtiva:
            logger.error("Não é possível configurar UI: Nenhuma sessão ativa.")
            self.title("Refeições Reg [Sem Sessão]")
            if self._label_info_sessao:
                self._label_info_sessao.config(text="Erro: Nenhuma Sessão Ativa")
            if self._painel_acao:
                self._painel_acao.desabilitar_controles()
            if self._painel_status:
                self._painel_status.limpar_tabela()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Erro ao configurar UI para sessão: %s", e)

    def _atualizar_ui_apos_mudanca_dados(self):
        """Atualiza os painéis após uma alteração nos dados da sessão."""
        logger.info("Atualizando UI após mudança nos dados da sessão...")
        if not self._fachada or self._fachada.id_sessao_ativa is None:
            return

        if self._painel_status:
            self._painel_status.atualizar_contadores()
        if self._painel_acao:
            self._painel_acao.atualizar_resultados()
        logger.debug("Refresh da UI concluído.")

    def notificar_sucesso_registro(self, dados_estudante: Tuple):
        """Callback chamado pelo PainelAcaoBusca após um registro bem-sucedido."""
        logger.debug("Notificação de registro recebida para: %s", dados_estudante[0])
        if self._painel_status:
            self._painel_status.carregar_estudantes_registrados()

    def tratar_delecao_consumo(self, dados_para_logica: Tuple, _iid_para_deletar: str):
        """Callback chamado pelo PainelStatusRegistrados para desfazer um consumo."""
        pront = dados_para_logica[0] if dados_para_logica else None
        nome = dados_para_logica[1] if len(dados_para_logica) > 1 else "N/A"
        logger.info("Solicitação para desfazer consumo: %s (%s)", pront or "?", nome)

        if pront and self._fachada:
            self._fachada.desfazer_consumo_por_prontuario(pront)
            if self._painel_status:
                self._painel_status.carregar_estudantes_registrados()
            self._atualizar_ui_apos_mudanca_dados()

    # --------------------------------------------------------------------------
    # Diálogos
    # --------------------------------------------------------------------------

    def _abrir_dialogo_sessao(self: "AppRegistro"):
        """Abre o diálogo para criar ou selecionar uma sessão."""
        logger.info("Abrindo diálogo de sessão.")
        DialogoSessao(
            title="Selecionar ou Criar Sessão",
            callback=self.tratar_resultado_dialogo_sessao,
            parente_app=self,
        )

    def _abrir_dialogo_filtro_turmas(self):
        """Abre o diálogo para filtrar turmas na sessão ativa."""
        if not self._fachada or self._fachada.id_sessao_ativa is None:
            Messagebox.show_warning(
                "Nenhuma Sessão Ativa", "É necessário iniciar uma sessão.", parent=self
            )
            return

        logger.info("Abrindo diálogo de filtro de turmas.")
        DialogoFiltroTurmas(
            parent=self,
            fachada_nucleo=self._fachada,
            callback_aplicar=self.ao_aplicar_filtro_turmas,
        )

    def ao_aplicar_filtro_turmas(self, identificadores: List[str]):
        """Callback para aplicar os filtros de turma selecionados no diálogo."""
        logger.info("Aplicando filtros de turma: %s", identificadores)
        if not self._fachada:
            return
        try:
            grupos_selecionados = [i for i in identificadores if not i.startswith("#")]
            grupos_excluidos = [i[1:] for i in identificadores if i.startswith("#")]

            self._fachada.atualizar_grupos_sessao(grupos_selecionados, grupos_excluidos)
            logger.info("Filtros de turma aplicados com sucesso.")
            self._atualizar_ui_apos_mudanca_dados()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Falha ao aplicar filtros de turma: %s", e)
            Messagebox.show_error(
                "Erro ao Filtrar",
                f"Não foi possível aplicar os filtros.\nErro: {e}",
                parent=self,
            )

    # --------------------------------------------------------------------------
    # Operações Assíncronas (Sincronização e Exportação)
    # --------------------------------------------------------------------------

    def mostrar_barra_progresso(self, iniciar: bool, texto: Optional[str] = None):
        """Controla a visibilidade e o estado da barra de progresso."""
        if not self._barra_progresso or not self._label_barra_status:
            return
        try:
            if iniciar:
                self._label_barra_status.config(text=texto or "Processando...")
                if not self._barra_progresso.winfo_ismapped():
                    self._barra_progresso.pack(side=RIGHT, padx=5, fill=X, expand=False)
                self._barra_progresso.start(10)
            else:
                if self._barra_progresso.winfo_ismapped():
                    self._barra_progresso.stop()
                    self._barra_progresso.pack_forget()
                self._label_barra_status.config(text="Pronto.")
        except tk.TclError as e:
            logger.error("Erro Tcl ao manipular barra de progresso: %s", e)

    def _sincronizar_dados_mestre(self):
        """Inicia a sincronização dos dados mestre (cadastros)."""
        if not self._fachada:
            return
        if Messagebox.yesno(
            "Confirmar Sincronização",
            "Deseja sincronizar os dados mestre?",
            parent=self,
        ) == MessageCatalog.translate("No"):
            return
        self.mostrar_barra_progresso(True, "Sincronizando cadastros...")
        self._iniciar_thread_sinc(
            self._fachada.sincronizar_do_google_sheets, "Sincronização de Cadastros"
        )

    def sincronizar_sessao_com_planilha(self):
        """Inicia a sincronização dos dados da sessão atual para a planilha."""
        if not self._fachada or self._fachada.id_sessao_ativa is None:
            Messagebox.show_warning(
                "Nenhuma Sessão Ativa",
                "É necessário ter uma sessão ativa.",
                parent=self,
            )
            return
        self.mostrar_barra_progresso(True, "Sincronizando servidos para planilha...")
        self._iniciar_thread_sinc(
            self._fachada.sincronizar_para_google_sheets, "Sincronização de Servidos"
        )

    def _iniciar_thread_sinc(self, funcao_sinc: Callable, nome_tarefa: str):
        """Inicia uma função de sincronização em uma thread separada para não bloquear a UI."""
        thread = Thread(
            target=self._acao_sinc_wrapper, args=(funcao_sinc,), daemon=True
        )
        thread.start()
        self._monitorar_thread_sinc(thread, nome_tarefa)

    def _acao_sinc_wrapper(self, funcao_sinc: Callable):
        """Wrapper que executa a função de sincronização e captura exceções na thread."""
        thread = threading.current_thread()
        setattr(thread, "error", None)
        setattr(thread, "success", False)

        try:
            funcao_sinc()
            setattr(thread, "success", True)
        except Exception as e:  # pylint: disable=broad-exception-caught
            setattr(thread, "error", e)

    def _monitorar_thread_sinc(self, thread: Thread, nome_tarefa: str):
        """Verifica o status da thread de sincronização e exibe o resultado ao final."""
        if thread.is_alive():
            self.after(150, lambda: self._monitorar_thread_sinc(thread, nome_tarefa))
            return

        self.mostrar_barra_progresso(False)
        erro = getattr(thread, "error", None)
        sucesso = getattr(thread, "success", False)

        if erro:
            logger.error("%s falhou: %s", nome_tarefa, erro)
            Messagebox.show_error(
                "Erro na Sincronização", f"{nome_tarefa} falhou:\n{erro}", parent=self
            )
        elif sucesso:
            logger.info("%s concluída com sucesso.", nome_tarefa)
            Messagebox.show_info(
                "Sincronização Concluída",
                f"{nome_tarefa} concluída com sucesso.",
                parent=self,
            )
            self._atualizar_ui_apos_mudanca_dados()
        else:
            logger.warning("%s finalizada com estado indeterminado.", nome_tarefa)
            Messagebox.show_warning(
                "Status Desconhecido",
                f"{nome_tarefa} finalizada, mas o status é incerto.",
                parent=self,
            )

    def exportar_sessao_para_excel(self) -> bool:
        """Exporta os dados da sessão atual para um arquivo XLSX."""
        if not self._fachada:
            return False
        try:
            caminho_arquivo = self._fachada.exportar_sessao_para_xlsx()
            logger.info("Dados da sessão exportados para: %s", caminho_arquivo)
            Messagebox.show_info(
                "Exportação Concluída",
                f"Dados exportados com sucesso para:\n{caminho_arquivo}",
                parent=self,
            )
            return True
        except ErroSessaoNaoAtiva:
            Messagebox.show_warning(
                "Nenhuma Sessão Ativa",
                "Não há sessão ativa para exportar.",
                parent=self,
            )
        except ValueError as ve:
            Messagebox.show_warning("Nada para Exportar", str(ve), parent=self)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Erro inesperado durante a exportação.")
            Messagebox.show_error(
                "Erro na Exportação", f"Ocorreu um erro ao exportar:\n{e}", parent=self
            )
        return False

    # --------------------------------------------------------------------------
    # Ciclo de Vida da Aplicação e Helpers
    # --------------------------------------------------------------------------

    def _tratar_erro_inicializacao(self, componente: str, erro: Exception):
        """Exibe uma mensagem de erro crítico e encerra a aplicação."""
        logger.critical(
            "Erro Crítico de Inicialização - Componente: %s | Erro: %s",
            componente,
            erro,
            exc_info=True,
        )
        try:
            Messagebox.show_error(
                "Erro de Inicialização",
                f"Falha: {componente}\n{erro}\n\nAplicação será encerrada.",
                parent=(self if self.winfo_exists() else None),
            )
        except Exception:  # pylint: disable=broad-exception-caught
            print(f"ERRO CRÍTICO ({componente}): {erro}", file=sys.stderr)

        if self.winfo_exists():
            try:
                self.destroy()
            except tk.TclError:
                pass
        sys.exit(1)

    def _focar_janela(self):
        """Traz a janela da aplicação para o primeiro plano e foca o campo de busca."""
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            if self._painel_acao:
                self._painel_acao.focar_entrada()
        except tk.TclError as e:
            logger.warning("Erro Tcl ao focar/levantar janela: %s", e)

    def ao_fechar_app(self, acionado_por_fim_sessao: bool = False):
        """Executa a sequência de limpeza ao fechar a aplicação."""
        logger.info("Sequência de fechamento da aplicação iniciada...")

        if self._painel_acao and self._painel_acao.id_after_busca is not None:
            try:
                self._painel_acao.after_cancel(self._painel_acao.id_after_busca)
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        if self._fachada:
            id_sessao = self._fachada.id_sessao_ativa
            if not acionado_por_fim_sessao and id_sessao:
                CAMINHO_SESSAO.write_text(
                    f'{{"id_sessao": {id_sessao}}}', encoding="utf-8"
                )
                logger.info("Estado da sessão salvo em %s.", CAMINHO_SESSAO)

            logger.info("Fechando conexão com DB...")
            self._fachada.fechar_conexao()

        logger.debug("Destruindo janela principal...")
        try:
            self.destroy()
        except tk.TclError:
            pass
        logger.info("Aplicação finalizada.")


if __name__ == "__main__":
    app = AppRegistro()
    app.mainloop()
