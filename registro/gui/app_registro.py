# ----------------------------------------------------------------------------
# Arquivo: registro/view/app_registro.py (Aplicação Principal da UI)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>
import json
import logging
import sys
import tkinter as tk
from threading import Thread
from tkinter import CENTER, TclError, messagebox
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import ttkbootstrap as ttk
from ttkbootstrap.constants import HORIZONTAL, LEFT, LIGHT, RIGHT, VERTICAL, X

from registro.nucleo.exceptions import ErroSessaoNaoAtiva
from registro.nucleo.facade import FachadaRegistro
from registro.gui.painel_acao_busca import PainelAcaoBusca
from registro.gui.dialogo_filtro_turmas import DialogoFiltroTurmas
from registro.gui.constants import CAMINHO_SESSAO
from registro.gui.dialogo_sessao import DialogoSessao
from registro.gui.painel_status_registrados import PainelStatusRegistrados
from registro.gui.utils import capitalizar

logger = logging.getLogger(__name__)


class AppRegistro(tk.Tk):
    def __init__(self, title: str = "Registro de Refeições"):
        super().__init__()
        self.title(title)
        self.protocol("WM_DELETE_WINDOW", self.ao_fechar_app)
        self.minsize(1152, 648)

        self._fachada: Optional[FachadaRegistro] = None
        try:
            self._fachada = FachadaRegistro()
        except Exception as e:
            self._tratar_erro_inicializacao("Fachada do Núcleo", e)
            return

        self._barra_superior: Optional[ttk.Frame] = None
        self._janela_principal_dividida: Optional[ttk.PanedWindow] = None
        self._barra_status: Optional[ttk.Frame] = None
        self._painel_acao: Optional[PainelAcaoBusca] = None
        self._painel_status: Optional[PainelStatusRegistrados] = None
        self._label_info_sessao: Optional[ttk.Label] = None
        self._label_barra_status: Optional[ttk.Label] = None
        self._barra_progresso: Optional[ttk.Progressbar] = None
        self.style: Optional[ttk.Style] = None
        self.colors: Optional[Any] = None

        try:
            self._configurar_estilo()
            self._configurar_layout_grid()
            self._criar_barra_superior()
            self._criar_paineis_principais(self._fachada)
            self._criar_barra_status()
        except Exception as e:
            self._tratar_erro_inicializacao("Construção da UI", e)
            return

        self._carregar_sessao_inicial()

    def get_fachada(self) -> FachadaRegistro:
        if self._fachada is None:
            logger.critical("Tentativa de acessar Fachada não inicializada.")
            raise RuntimeError("FachadaRegistro não foi inicializada.")
        return self._fachada

    def _tratar_erro_inicializacao(self, componente: str, erro: Exception):
        logger.critical(
            "Erro Crítico de Inicialização - Componente: %s | Erro: %s",
            componente,
            erro,
            exc_info=True,
        )
        try:
            temp_root = None
            if not hasattr(tk, "_default_root") or not tk._default_root:  # type: ignore
                temp_root = tk.Tk()
                temp_root.withdraw()

            messagebox.showerror(
                "Erro de Inicialização",
                f"Falha: {componente}\n{erro}\n\nAplicação será encerrada.",
                parent=(self if self.winfo_exists() else None),
            )
            if temp_root:
                temp_root.destroy()
        except Exception as mb_error:
            print(f"ERRO CRÍTICO ({componente}): {erro}", file=sys.stderr)
            print(f"(Erro ao exibir messagebox: {mb_error})", file=sys.stderr)

        if self.winfo_exists():
            try:
                self.destroy()
            except tk.TclError:
                pass
        sys.exit(1)

    def _configurar_estilo(self):
        try:
            self.style = ttk.Style(theme="minty")
            fonte_padrao = ("Segoe UI", 12)
            fonte_cabecalho = (fonte_padrao[0], 10, "bold")
            fonte_label = (fonte_padrao[0], 11, "bold")
            fonte_pequena = (fonte_padrao[0], 9)
            self.style.configure(
                "Custom.Treeview", font=(fonte_padrao[0], 9), rowheight=30
            )
            self.style.configure(
                "Custom.Treeview.Heading",
                font=fonte_cabecalho,
                background=self.style.colors.light,
                foreground=self.style.colors.get_foreground("light"),
            )
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
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

    def _criar_barra_superior(self):
        self._barra_superior = ttk.Frame(self, padding=(10, 5), bootstyle=LIGHT)  # type: ignore
        self._barra_superior.grid(row=0, column=0, sticky="ew")

        self._label_info_sessao = ttk.Label(
            self._barra_superior,
            text="Carregando Sessão...",
            font="-size 14 -weight bold",
            bootstyle="inverse-light",  # type: ignore
        )
        self._label_info_sessao.pack(side=LEFT, padx=(0, 20), anchor="w")

        frame_botoes = ttk.Frame(self._barra_superior, bootstyle=LIGHT)  # type: ignore
        frame_botoes.pack(side=RIGHT, anchor="e")

        ttk.Button(
            frame_botoes,
            text="💾 Exportar e Encerrar",
            command=self.exportar_e_encerrar_sessao,
            bootstyle="light",  # type: ignore
        ).pack(side=RIGHT, padx=(10, 0))
        ttk.Button(
            frame_botoes,
            text="📤 Sincronizar Servidos",
            command=self.sincronizar_sessao_com_planilha,
            bootstyle="light",  # type: ignore
        ).pack(side=RIGHT, padx=3)
        ttk.Button(
            frame_botoes,
            text="🔄 Sincronizar Cadastros",
            command=self._sincronizar_dados_mestre,
            bootstyle="light",  # type: ignore
        ).pack(side=RIGHT, padx=3)
        ttk.Separator(frame_botoes, orient=VERTICAL).pack(
            side=RIGHT, padx=8, fill="y", pady=3
        )
        ttk.Button(
            frame_botoes,
            text="📊 Filtrar Turmas",
            command=self._abrir_dialogo_filtro_turmas,
            bootstyle="light",  # type: ignore
        ).pack(side=RIGHT, padx=3)
        ttk.Button(
            frame_botoes,
            text="⚙️ Alterar Sessão",
            command=self._abrir_dialogo_sessao,
            bootstyle="light",  # type: ignore
        ).pack(side=RIGHT, padx=3)

    def _criar_paineis_principais(self, fachada: FachadaRegistro):
        self._janela_principal_dividida = ttk.PanedWindow(
            self, orient=HORIZONTAL, bootstyle="light"  # type: ignore
        )
        self._janela_principal_dividida.grid(
            row=1, column=0, sticky="nsew", padx=10, pady=(5, 0)
        )
        self._painel_acao = PainelAcaoBusca(
            self._janela_principal_dividida, self, fachada
        )
        self._janela_principal_dividida.add(self._painel_acao, weight=1)
        self._painel_status = PainelStatusRegistrados(
            self._janela_principal_dividida, self, fachada
        )
        self._janela_principal_dividida.add(self._painel_status, weight=2)

    def _criar_barra_status(self):
        self._barra_status = ttk.Frame(
            self, padding=(5, 3), bootstyle=LIGHT, name="statusBarFrame"  # type: ignore
        )
        self._barra_status.grid(row=2, column=0, sticky="ew")

        self._label_barra_status = ttk.Label(
            self._barra_status,
            text="Pronto.",
            bootstyle="inverse-light",  # type: ignore
            font=("-size 10"),
        )
        self._label_barra_status.pack(side=LEFT, padx=5, anchor="w")

        self._barra_progresso = ttk.Progressbar(
            self._barra_status,
            mode="indeterminate",
            bootstyle="striped-info",  # type: ignore
            length=200,
        )

    def _carregar_arquivo_estado_sessao(self) -> Optional[Dict[str, Any]]:
        if not CAMINHO_SESSAO.exists():
            logger.info(
                "Arquivo de estado da sessão não encontrado: %s", CAMINHO_SESSAO
            )
            return None
        try:
            with open(CAMINHO_SESSAO, "r", encoding="utf-8") as f:
                dados_sessao = json.load(f)
            logger.info("Estado da sessão carregado: %s", CAMINHO_SESSAO)
            assert self._fachada is not None
            self._fachada.definir_sessao_ativa(dados_sessao.get("id_sessao"))
            return dados_sessao
        except Exception as e:
            logger.error(
                "Erro ao carregar estado da sessão de %s: %s", CAMINHO_SESSAO, e
            )
            return None

    def _carregar_sessao_inicial(self):
        logger.info("Tentando carregar estado inicial da sessão...")
        info_sessao = self._carregar_arquivo_estado_sessao()
        if info_sessao:
            self._configurar_ui_para_sessao_carregada()
        else:
            self.after(100, self._abrir_dialogo_sessao)

    def tratar_resultado_dialogo_sessao(
        self, resultado: Union[Dict, int, None]
    ) -> bool:
        if resultado is None:
            logger.info("Diálogo de sessão cancelado.")
            if not self._fachada or self._fachada.id_sessao_ativa is None:
                logger.warning("Diálogo cancelado sem sessão ativa.")
            return True

        sucesso = False
        desc_acao = ""
        if not self._fachada:
            messagebox.showerror("Erro Interno", "Fachada não encontrada.", parent=self)
            return False

        try:
            if isinstance(resultado, int):
                id_sessao = resultado
                desc_acao = f"carregar sessão ID: {id_sessao}"
                self._fachada.definir_sessao_ativa(id_sessao)
                sucesso = True
            elif isinstance(resultado, dict):
                desc_acao = f"criar nova sessão: {resultado.get('refeicao')}"
                id_sessao = self._fachada.iniciar_nova_sessao(resultado)  # type: ignore
                logger.info("Nova sessão criada com ID: %s", id_sessao)
                if id_sessao:
                    if CAMINHO_SESSAO.exists():
                        CAMINHO_SESSAO.unlink()
                    CAMINHO_SESSAO.write_text(
                        f'{{"id_sessao": {id_sessao}}}', encoding="utf-8"
                    )
                    sucesso = True
        except Exception as e:
            logger.exception("Falha ao %s: %s", desc_acao, e)
            messagebox.showerror(
                "Operação Falhou",
                f"Não foi possível {desc_acao}.\nErro: {e}",
                parent=self,
            )
            return False

        if sucesso:
            logger.info("Sucesso ao %s.", desc_acao)
            self._configurar_ui_para_sessao_carregada()
            return True
        return False

    def _configurar_ui_para_sessao_carregada(self):
        logger.debug("Configurando UI para sessão ativa...")
        if not self._fachada:
            return

        try:
            detalhes_sessao = self._fachada.obter_detalhes_sessao_ativa()
        except ErroSessaoNaoAtiva:
            logger.error("Não é possível configurar UI: Nenhuma sessão ativa.")
            self.title("Refeições Reg [Sem Sessão]")
            if self._label_info_sessao:
                self._label_info_sessao.config(
                    text="Erro: Nenhuma Sessão Ativa", bootstyle="inverse-danger"  # type: ignore
                )
            if self._painel_acao:
                self._painel_acao.desabilitar_controles()
            if self._painel_status:
                self._painel_status.limpar_tabela()
            return

        if not all(
            [
                detalhes_sessao,
                self._label_info_sessao,
                self._painel_acao,
                self._painel_status,
            ]
        ):
            logger.error("Componentes da UI ou detalhes da sessão ausentes.")
            return

        try:
            refeicao_exibicao = capitalizar(detalhes_sessao.get("refeicao", "?"))
            hora_exibicao = detalhes_sessao.get("hora", "??")
            data_raw = detalhes_sessao.get("data", "")
            data_exibicao = data_raw
            id_sessao = detalhes_sessao.get("id")
            titulo = (
                f"Reg: {refeicao_exibicao} - {data_exibicao} {hora_exibicao} "
                f"[ID:{id_sessao}]"
            )
            self.title(titulo)
            self._label_info_sessao.config(text=titulo, bootstyle="inverse-light")  # type: ignore
        except Exception as e:
            logger.exception("Erro ao formatar detalhes da sessão para UI: %s", e)
            self.title("RU Registro [Erro na Sessão]")
            if self._label_info_sessao:
                self._label_info_sessao.config(
                    text="Erro ao carregar detalhes", bootstyle="inverse-danger"  # type: ignore
                )
            return

        logger.debug("Habilitando painéis e carregando dados...")
        if self._painel_acao:
            self._painel_acao.habilitar_controles()
        if self._painel_status:
            self._painel_status.carregar_estudantes_registrados()
        if self._painel_acao:
            self._painel_acao.atualizar_resultados()

        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            if self._painel_acao:
                self._painel_acao.focar_entrada()
        except tk.TclError as e:
            logger.warning("Erro Tcl ao focar/levantar janela: %s", e)
        logger.info("UI configurada para sessão ID: %s", detalhes_sessao.get("id"))

    def _atualizar_ui_apos_mudanca_dados(self):
        logger.info("Atualizando UI após mudança nos dados da sessão...")
        if not self._fachada or self._fachada.id_sessao_ativa is None:
            logger.warning("Nenhuma sessão ativa para atualizar a UI.")
            return
        if self._painel_status:
            self._painel_status.atualizar_contadores()
        if self._painel_acao:
            self._painel_acao.atualizar_resultados()
        logger.debug("Refresh da UI concluído.")

    def notificar_sucesso_registro(self, dados_estudante: Tuple):
        logger.debug("Notificação de registro recebida para: %s", dados_estudante[0])
        if self._painel_status:
            self._painel_status.carregar_estudantes_registrados()

    def tratar_delecao_consumo(self, dados_para_logica: Tuple, _iid_para_deletar: str):
        pront = dados_para_logica[0] if dados_para_logica else None
        nome = dados_para_logica[1] if len(dados_para_logica) > 1 else "N/A"
        logger.info("Solicitação para desfazer consumo: %s (%s)", pront or "?", nome)
        if pront and self._fachada:
            self._fachada.desfazer_consumo_por_prontuario(pront)
            if self._painel_status:
                self._painel_status.carregar_estudantes_registrados()
            self._atualizar_ui_apos_mudanca_dados()

    def _abrir_dialogo_sessao(self: "AppRegistro"):
        logger.info("Abrindo diálogo de sessão.")
        DialogoSessao(
            title="Selecionar ou Criar Sessão",
            callback=self.tratar_resultado_dialogo_sessao,  # type: ignore
            app_pai=self,
        )

    def _abrir_dialogo_filtro_turmas(self):
        if not self._fachada or self._fachada.id_sessao_ativa is None:
            messagebox.showwarning(
                "Nenhuma Sessão Ativa", "É necessário iniciar uma sessão.", parent=self
            )
            return
        logger.info("Abrindo diálogo de filtro de turmas.")
        DialogoFiltroTurmas(
            parent=self,
            fachada_nucleo=self._fachada,
            callback_aplicar=self.ao_aplicar_filtro_turmas,
        )  # type: ignore

    def ao_aplicar_filtro_turmas(self, identificadores_selecionados: List[str]):
        logger.info("Aplicando filtros de turma: %s", identificadores_selecionados)
        if not self._fachada:
            return
        try:
            grupos_selecionados = [
                ident
                for ident in identificadores_selecionados
                if not ident.startswith("#")
            ]
            grupos_excluidos = [
                ident[1:]
                for ident in identificadores_selecionados
                if ident.startswith("#")
            ]
            self._fachada.atualizar_grupos_sessao(grupos_selecionados, grupos_excluidos)
            logger.info("Filtros de turma aplicados com sucesso.")
            self._atualizar_ui_apos_mudanca_dados()
        except Exception as e:
            logger.exception("Falha ao aplicar filtros de turma: %s", e)
            messagebox.showerror(
                "Erro ao Filtrar",
                f"Não foi possível aplicar os filtros.\nErro: {e}",
                parent=self,
            )

    def mostrar_barra_progresso(self, iniciar: bool, texto: Optional[str] = None):
        if not self._barra_progresso or not self._label_barra_status:
            return
        try:
            if iniciar:
                texto_progresso = texto or "Processando..."
                self._label_barra_status.config(text=texto_progresso)
                if not self._barra_progresso.winfo_ismapped():
                    self._barra_progresso.pack(
                        side=RIGHT, padx=5, pady=0, fill=X, expand=False
                    )
                self._barra_progresso.start(10)
            else:
                if self._barra_progresso.winfo_ismapped():
                    self._barra_progresso.stop()
                    self._barra_progresso.pack_forget()
                self._label_barra_status.config(text="Pronto.")
        except tk.TclError as e:
            logger.error("Erro Tcl ao manipular barra de progresso: %s", e)

    def _sincronizar_dados_mestre(self):
        if not self._fachada:
            return
        if not messagebox.askyesno(
            "Confirmar Sincronização",
            "Deseja sincronizar os dados mestre?",
            parent=self,
        ):
            return
        self.mostrar_barra_progresso(True, "Sincronizando cadastros...")
        self._iniciar_thread_sinc(
            self._fachada.sincronizar_do_google_sheets, "Sincronização de Cadastros"
        )

    def sincronizar_sessao_com_planilha(self):
        if not self._fachada or self._fachada.id_sessao_ativa is None:
            messagebox.showwarning(
                "Nenhuma Sessão Ativa",
                "É necessário ter uma sessão ativa para sincronizar.",
                parent=self,
            )
            return
        self.mostrar_barra_progresso(True, "Sincronizando servidos para planilha...")
        self._iniciar_thread_sinc(
            self._fachada.sincronizar_para_google_sheets, "Sincronização de Servidos"
        )

    def _iniciar_thread_sinc(self, funcao_sinc: Callable, nome_tarefa: str):
        class ThisThread(Thread):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.error: Optional[Exception] = None
                self.success: bool = False

        thread: ThisThread

        def acao_sinc():
            thread.error = None
            thread.success = False
            try:
                funcao_sinc()
                thread.success = True
            except Exception as e:
                thread.error = e

        thread = ThisThread(target=acao_sinc, daemon=True)
        thread.error = None
        thread.success = False  # type: ignore
        thread.start()
        self._monitorar_thread_sinc(thread, nome_tarefa)

    def _monitorar_thread_sinc(self, thread: Thread, nome_tarefa: str):
        if thread.is_alive():
            self.after(150, lambda: self._monitorar_thread_sinc(thread, nome_tarefa))
            return

        self.mostrar_barra_progresso(False)
        erro = getattr(thread, "error", None)
        sucesso = getattr(thread, "success", False)

        if erro:
            logger.error("%s falhou: %s", nome_tarefa, erro)
            messagebox.showerror(
                "Erro na Sincronização", f"{nome_tarefa} falhou:\n{erro}", parent=self
            )
        elif sucesso:
            logger.info("%s concluída com sucesso.", nome_tarefa)
            messagebox.showinfo(
                "Sincronização Concluída",
                f"{nome_tarefa} concluída com sucesso.",
                parent=self,
            )
            self._atualizar_ui_apos_mudanca_dados()
        else:
            logger.warning("%s finalizada com estado indeterminado.", nome_tarefa)
            messagebox.showwarning(
                "Status Desconhecido",
                f"{nome_tarefa} finalizada, mas o status é incerto.",
                parent=self,
            )

    def exportar_sessao_para_excel(self) -> bool:
        if not self._fachada:
            return False
        try:
            caminho_arquivo = self._fachada.exportar_sessao_para_xlsx()
            logger.info("Dados da sessão exportados para: %s", caminho_arquivo)
            messagebox.showinfo(
                "Exportação Concluída",
                f"Dados exportados com sucesso para:\n{caminho_arquivo}",
                parent=self,
            )
            return True
        except ErroSessaoNaoAtiva:
            messagebox.showwarning(
                "Nenhuma Sessão Ativa",
                "Não há sessão ativa para exportar.",
                parent=self,
            )
        except ValueError as ve:
            messagebox.showwarning("Nada para Exportar", str(ve), parent=self)
        except Exception as e:
            logger.exception("Erro inesperado durante a exportação.")
            messagebox.showerror(
                "Erro na Exportação", f"Ocorreu um erro ao exportar:\n{e}", parent=self
            )
        return False

    def exportar_e_encerrar_sessao(self):
        if not self._fachada or self._fachada.id_sessao_ativa is None:
            messagebox.showwarning(
                "Nenhuma Sessão Ativa",
                "Não há sessão ativa para encerrar.",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "Confirmar Encerramento",
            "Deseja exportar os dados e encerrar esta sessão?",
            icon="warning",
            parent=self,
        ):
            return

        exportacao_bem_sucedida = self.exportar_sessao_para_excel()
        if not exportacao_bem_sucedida:
            if not messagebox.askyesno(
                "Falha na Exportação",
                "A exportação falhou. Deseja encerrar mesmo assim?",
                icon="error",
                parent=self,
            ):
                return

        CAMINHO_SESSAO.unlink(missing_ok=True)
        self.ao_fechar_app(acionado_por_fim_sessao=True)

    def ao_fechar_app(self, acionado_por_fim_sessao: bool = False):
        logger.info("Sequência de fechamento da aplicação iniciada...")

        if self._painel_acao and self._painel_acao.id_after_busca is not None:
            try:
                self._painel_acao.after_cancel(self._painel_acao.id_after_busca)
            except Exception:
                pass

        if self._fachada:
            id_sessao = self._fachada.id_sessao_ativa
            if not acionado_por_fim_sessao and id_sessao:
                if CAMINHO_SESSAO.exists():
                    CAMINHO_SESSAO.unlink()
                CAMINHO_SESSAO.write_text(
                    f'{{"id_sessao": {id_sessao}}}', encoding="utf-8"
                )
                logger.info("Estado da sessão salvo em %s.", str(CAMINHO_SESSAO))
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
