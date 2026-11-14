# ----------------------------------------------------------------------------
# Arquivo: registro/gui/autoatendimento/totem.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Componente FrameSelfService para o Totem de Autoatendimento.
Gerencia captura por webcam, decodificação de QR Code, leitor USB,
digitação manual com busca incremental e feedback audiovisual.
"""

import contextlib
import logging
import tkinter as tk
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple

import ttkbootstrap as ttk
from PIL import Image, ImageTk
from sqlalchemy.exc import SQLAlchemyError

from registro.gui.autoatendimento._totem_ui import _TotemUIMixin
from registro.gui.autoatendimento.totem_camera import (
    OPENCV_DISPONIVEL,
    cv2,
    decodificar_primeiro_qr,
)
from registro.gui.autoatendimento.totem_logica import (
    filtrar_correspondencias_nome,
    formatar_resumo_sessao_topo,
    resolver_match_nome,
)
from registro.gui.autoatendimento.totem_logica import (
    formatar_matricula as _formatar_matricula_logica,
)
from registro.gui.comum.utils import emitir_feedback_sonoro
from registro.nucleo.config_service import obter_config_totem

if TYPE_CHECKING:
    from registro.nucleo.facade import FachadaRegistro

logger = logging.getLogger(__name__)


class FrameSelfService(ttk.Frame, _TotemUIMixin):
    """
    Frame dedicado ao autoatendimento via leitura de QR Code pela webcam
    ou scanner USB / digitação manual de matrícula.
    """

    def __init__(
        self,
        master: tk.Widget,
        fachada: "FachadaRegistro",
        notification_callback: Callable[[Tuple[str, ...]], None],
        abrir_controles_callback: Optional[Callable[..., None]] = None,
    ):
        super().__init__(master)

        self._fachada = fachada
        self._notification_callback = notification_callback
        self._abrir_controles_callback = abrir_controles_callback
        self._cap = None
        self._running = False
        self._cooldown_frames = 0
        self._total_atendidos_sessao = 0

        # Cores e Estilos (Design Moderno e Feedback Visual)
        self.COR_FUNDO_PADRAO = "#111827"  # Gray 900
        self.COR_FUNDO_SUCESSO = "#065F46"  # Emerald 800
        self.COR_FUNDO_ERRO = "#991B1B"  # Red 800
        self.COR_TEXTO = "#FFFFFF"  # White

        self._lbl_video: Optional[ttk.Label] = None
        self._lbl_sessao_topo: Optional[ttk.Label] = None
        self._lbl_status: Optional[tk.Label] = None
        self._lbl_refeicao_ativa: Optional[tk.Label] = None
        self._lbl_nome: Optional[tk.Label] = None
        self._lbl_turma: Optional[tk.Label] = None
        self._lbl_prato: Optional[tk.Label] = None
        self._lbl_mensagem: Optional[tk.Label] = None
        self._lbl_contador_sessao: Optional[tk.Label] = None
        self._lbl_sugestao_manual: Optional[tk.Label] = None
        self._entrada_manual: Optional[ttk.Entry] = None
        self._var_entrada_manual = tk.StringVar()
        self._id_after_busca_manual: Optional[str] = None
        self._id_after_feedback: Optional[str] = None
        self._ultimo_estado_feedback: str = "padrao"
        self._frame_info: Optional[tk.Frame] = None
        self._frame_cabecalho: Optional[tk.Frame] = None
        self._lbl_titulo_cabecalho: Optional[tk.Label] = None
        self._separador: Optional[tk.Frame] = None
        self._frame_estudante: Optional[tk.Frame] = None
        self._frame_manual: Optional[tk.LabelFrame] = None
        self._dialogo_horarios: Optional[Any] = None

        self._criar_interface()
        self.recarregar_sessao()

        self._totem_cfg = obter_config_totem()
        self._feedback_frames = max(
            5, int(self._totem_cfg.get("feedback_delay_ms", 1500) / 100)
        )

        if OPENCV_DISPONIVEL and self._totem_cfg.get("camera_on_start", True):
            self._iniciar_camera()
        elif OPENCV_DISPONIVEL:
            self._lbl_video.config(
                text="📷 Câmera desativada nas configurações.\nO leitor USB e a busca manual estão prontos.",
                bootstyle="secondary",
            )
        else:
            self._exibir_erro_dependencia()

    def stop(self):
        """Libera recursos, como a câmera e timers pendentes."""
        self._running = False
        self._cancelar_timer_feedback()
        if self._id_after_busca_manual:
            with contextlib.suppress(tk.TclError):
                self.after_cancel(self._id_after_busca_manual)
            self._id_after_busca_manual = None
        self.fechar_dialogo_horarios()
        if self._cap:
            try:
                self._cap.release()
            except (OSError, RuntimeError, AttributeError) as e:
                logger.warning("Erro ao liberar câmera: %s", e)

    def _cancelar_timer_feedback(self):
        """Cancela timer pendente de retorno ao estado visual padrão."""
        if self._id_after_feedback:
            with contextlib.suppress(tk.TclError):
                self.after_cancel(self._id_after_feedback)
            self._id_after_feedback = None

    def _pode_processar_leitura(self) -> bool:
        """Verifica se o totem está ativo na tela e sem diálogos modais bloqueando."""
        try:
            if not self.winfo_exists() or not self.winfo_ismapped():
                return False
            topo = self.winfo_toplevel()
            # Se houver diálogo Toplevel aberto e visível, o totem está em segundo plano
            for w in topo.winfo_children():
                if (
                    isinstance(w, tk.Toplevel)
                    and w.winfo_exists()
                    and w.winfo_viewable()
                ):
                    if getattr(w, "permite_leitura_totem", False):
                        continue
                    return False
            return True
        except tk.TclError:
            return False

    def focar_entrada(self):
        """Garante o foco contínuo no campo de entrada para scanners USB e digitação."""
        with contextlib.suppress(tk.TclError):
            if not self._pode_processar_leitura():
                return
            if self._entrada_manual and self._entrada_manual.winfo_exists():
                self._entrada_manual.focus_set()

    def _ao_clicar_qualquer_lugar(self, event):
        """Mantém o foco no leitor USB se o clique foi em labels ou planos de fundo do totem."""
        if not self._pode_processar_leitura():
            return
        widget = getattr(event, "widget", None)
        if not widget:
            return
        # Apenas processa se o clique foi dentro da própria árvore do FrameSelfService
        try:
            if not str(widget).startswith(str(self)):
                return
        except tk.TclError:
            return
        if not isinstance(
            widget,
            (
                ttk.Entry,
                tk.Entry,
                ttk.Combobox,
                tk.Text,
                ttk.Button,
                tk.Button,
                ttk.Checkbutton,
                tk.Checkbutton,
                ttk.Radiobutton,
                tk.Radiobutton,
                ttk.Treeview,
                tk.Listbox,
            ),
        ):
            self.after(50, self.focar_entrada)

    def _ao_clicar_controles(
        self,
        widget: Optional[tk.Widget] = None,
        event: Optional[Any] = None,
    ):
        """Dispara a exibição do menu de contexto de controles do operador."""
        if self._abrir_controles_callback:
            self._abrir_controles_callback(widget=widget, event=event)

    def _abrir_dialogo_horarios(self):
        """Abre o diálogo de consulta de horários e turmas ativas/desativadas pelo horário."""
        if self._dialogo_horarios and self._dialogo_horarios.winfo_exists():
            with contextlib.suppress(tk.TclError):
                self._dialogo_horarios.lift()
                self._dialogo_horarios.focus_set()
                return

        from registro.gui.autoatendimento.dialogo_horarios import (
            DialogoGradeHorariosTotem,
        )

        topo = self.winfo_toplevel()
        self._dialogo_horarios = DialogoGradeHorariosTotem(
            parent=topo,
            fachada=self._fachada,
            on_codigo_lido=self.processar_codigo_externo,
            timeout_segundos=15,
        )

    def fechar_dialogo_horarios(self):
        """Fecha o diálogo de horários caso esteja aberto."""
        if self._dialogo_horarios and self._dialogo_horarios.winfo_exists():
            with contextlib.suppress(tk.TclError, AttributeError):
                self._dialogo_horarios.fechar()
            self._dialogo_horarios = None

    def processar_codigo_externo(self, codigo: str):
        """Permite que diálogos ou periféricos externos injetem um código para processamento rápido."""
        self.fechar_dialogo_horarios()
        self._processar_codigo(codigo, manual=True)

    def recarregar_sessao(self):
        """Atualiza a UI com base na sessão ativa na fachada."""
        self._definir_feedback_visual("padrao")
        if self._lbl_nome:
            self._lbl_nome.config(text="--")
        if self._lbl_turma:
            self._lbl_turma.config(text="--")
        if self._lbl_prato:
            self._lbl_prato.config(text="")
        if self._lbl_mensagem:
            self._lbl_mensagem.config(text="")

        if self._fachada and self._fachada.id_sessao_ativa:
            try:
                detalhes = self._fachada.obter_detalhes_sessao_ativa()
                qtd_exc = (
                    len(self._fachada.excecao_grupos)
                    if getattr(self._fachada, "excecao_grupos", None)
                    else 0
                )
                ignorar_horario = (
                    getattr(self._fachada, "ignorar_horario_grade", False) is True
                )
                texto_refeicao, texto_topo = formatar_resumo_sessao_topo(
                    detalhes, qtd_exc, ignorar_horario
                )

                if self._lbl_refeicao_ativa:
                    self._lbl_refeicao_ativa.config(text=texto_refeicao)
                if self._lbl_sessao_topo:
                    self._lbl_sessao_topo.config(text=texto_topo)

                consumidos = self._fachada.obter_estudantes_para_sessao(consumido=True)
                self._total_atendidos_sessao = len(consumidos)
                if self._lbl_contador_sessao:
                    self._lbl_contador_sessao.config(
                        text=f"Atendidos nesta sessão: {self._total_atendidos_sessao}"
                    )
            except (SQLAlchemyError, tk.TclError, ValueError, KeyError) as e:
                logger.error("Erro ao recarregar detalhes da sessão: %s", e)
        else:
            if self._lbl_refeicao_ativa:
                self._lbl_refeicao_ativa.config(text="Nenhuma sessão ativa")
            if self._lbl_contador_sessao:
                self._lbl_contador_sessao.config(text="Aguardando início de sessão")
            if self._lbl_sessao_topo:
                self._lbl_sessao_topo.config(
                    text="⚠️ Nenhuma sessão ativa no momento — Clique em '⚙️ Controles'"
                )

        self.after(100, self.focar_entrada)

    def incrementar_contador(self):
        """Incrementa o contador de atendimentos visual."""
        self._total_atendidos_sessao += 1
        if self._lbl_contador_sessao:
            self._lbl_contador_sessao.config(
                text=f"Atendidos nesta sessão: {self._total_atendidos_sessao}"
            )

    def _iniciar_camera(self):
        """Inicializa a captura de vídeo."""
        try:
            indice_camera = int(self._totem_cfg.get("camera_index", 0))
            self._cap = cv2.VideoCapture(indice_camera)
            if not self._cap.isOpened():
                self._lbl_video.config(
                    text="Não foi possível acessar a webcam.\nO leitor USB continua funcionando normalmente.",
                    bootstyle="warning",
                )
                return

            self._running = True
            self._atualizar_frame()
        except Exception as e:
            logger.exception("Erro ao iniciar câmera: %s", e)
            self._lbl_video.config(text=f"Erro na câmera: {e}", bootstyle="danger")

    def _atualizar_frame(self):
        """Loop de atualização do frame da câmera."""
        if not self._running:
            return

        ret, frame = self._cap.read()
        if ret:
            if self._cooldown_frames > 0:
                self._cooldown_frames -= 1
                cor_borda = (
                    (0, 0, 255)
                    if self._ultimo_estado_feedback == "erro"
                    else (0, 255, 0)
                )
                cv2.rectangle(
                    frame,
                    (0, 0),
                    (frame.shape[1], frame.shape[0]),
                    cor_borda,
                    10,
                )
                if self._cooldown_frames == 0:
                    self._definir_feedback_visual("padrao")
            elif self._pode_processar_leitura():
                self._detectar_qr_code(frame)

            self._exibir_frame_no_label(frame)

        self.after(100, self._atualizar_frame)

    def _detectar_qr_code(self, frame):
        """Detecta e processa QR Codes no frame."""
        try:
            codigo = decodificar_primeiro_qr(frame)
            if codigo:
                self.fechar_dialogo_horarios()
                self._processar_codigo(codigo)
        except (ValueError, TypeError, RuntimeError, UnicodeDecodeError) as e:
            logger.error("Erro ao decodificar frame: %s", e)

    def _exibir_frame_no_label(self, frame):
        """Converte o frame do OpenCV para Tkinter e exibe."""
        try:
            cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(cv2image)

            w_req = self._lbl_video.winfo_width()
            h_req = self._lbl_video.winfo_height()
            if w_req > 10 and h_req > 10:
                img.thumbnail((w_req, h_req))

            imgtk = ImageTk.PhotoImage(image=img)
            self._lbl_video.imgtk = imgtk
            self._lbl_video.configure(image=imgtk, text="")
        except (tk.TclError, OSError, ValueError) as e:
            logger.error("Erro ao exibir frame: %s", e)

    def _ao_submeter_manual(self, _=None):
        """Trata a submissão manual do código."""
        codigo = self._var_entrada_manual.get().strip()
        if codigo:
            if self._lbl_sugestao_manual:
                self._lbl_sugestao_manual.config(
                    text="💡 Aponte o QR Code para a câmera ou passe o crachá no leitor"
                )
            self._processar_codigo(codigo, manual=True)
            self._var_entrada_manual.set("")
        self.focar_entrada()

    def _na_mudanca_entrada_manual(self, *_):
        """Debounce de busca por nome na entrada manual."""
        if self._id_after_busca_manual:
            self.after_cancel(self._id_after_busca_manual)

        termo = self._var_entrada_manual.get()
        if len(termo) < 3:
            if self._lbl_sugestao_manual:
                self._lbl_sugestao_manual.config(
                    text="💡 Aponte o QR Code para a câmera ou passe o crachá no leitor"
                )
            return

        self._id_after_busca_manual = self.after(300, self._atualizar_sugestao_manual)

    def _atualizar_sugestao_manual(self):
        """Busca por sugestão de estudante e exibe dica."""
        self._id_after_busca_manual = None
        termo_busca = self._var_entrada_manual.get()
        if not termo_busca or not self._lbl_sugestao_manual:
            return

        melhor_match = self._buscar_melhor_match_por_nome(termo_busca)
        if melhor_match:
            nome = melhor_match.get("nome", "Desconhecido")
            turma = melhor_match.get("turma", "N/A")
            self._lbl_sugestao_manual.config(text=f"Sugestão: {nome} ({turma})")
        else:
            self._lbl_sugestao_manual.config(
                text="💡 Aponte o QR Code para a câmera ou passe o crachá no leitor"
            )

    def _processar_codigo(self, codigo: str, manual: bool = False):
        """Processa o código lido, executa validação e atualiza a interface."""
        if not manual and self._cooldown_frames > 0:
            return

        logger.info(
            "Processando código (%s): %s",
            "Manual" if manual else "Cam",
            codigo,
        )
        self._cooldown_frames = 30

        sucesso, msg, dados = self._registrar_entrada(codigo)

        if sucesso:
            self._lbl_nome.config(text=dados.get("nome", "Desconhecido"))
            self._lbl_turma.config(text=dados.get("turma", ""))
            prato = dados.get("prato") or ""
            self._lbl_prato.config(text=f"Item: {prato}" if prato else "")
            self._lbl_mensagem.config(text="")
            self._definir_feedback_visual("sucesso")
            self._tocar_som(sucesso=True)
            self.incrementar_contador()

            tupla_estudante = (
                str(dados.get("prontuario", "")),
                str(dados.get("nome", "Desconhecido")),
                str(dados.get("turma", "")),
                str(dados.get("hora_consumo", "")),
                str(dados.get("prato", "")),
            )
            self._notification_callback(tupla_estudante)
            self._cooldown_frames = self._feedback_frames
        else:
            self._lbl_mensagem.config(text=msg)
            self._lbl_nome.config(text=dados.get("nome", "--"))
            self._lbl_turma.config(text=dados.get("turma", "--"))
            self._lbl_prato.config(text="")
            self._definir_feedback_visual("erro")
            self._tocar_som(sucesso=False)
            self._cooldown_frames = 45

        self._cancelar_timer_feedback()
        if not self._running:
            self._id_after_feedback = self.after(
                self._cooldown_frames * 100,
                self._resetar_feedback_apos_timer,
            )
            self._cooldown_frames = 0

        self.after(50, self.focar_entrada)

    def _resetar_feedback_apos_timer(self):
        """Callback de timeout para restaurar visual padrão no modo sem câmera."""
        self._id_after_feedback = None
        if not self.winfo_exists():
            return
        self._definir_feedback_visual("padrao")

    @staticmethod
    def formatar_matricula(valor: Any) -> str:
        """Padroniza a matrícula para o formato IQ30XXXXX."""
        return _formatar_matricula_logica(valor)

    def _registrar_entrada(
        self, texto_entrada: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Processa a entrada e tenta registrar o consumo."""
        if not self._fachada or self._fachada.id_sessao_ativa is None:
            return (
                False,
                "Nenhuma sessão ativa. Inicie uma sessão primeiro nos controles superiores.",
                {"nome": "Sem Sessão Ativa", "turma": "--"},
            )

        try:
            if any(ch.isdigit() for ch in texto_entrada):
                prontuario = FrameSelfService.formatar_matricula(texto_entrada)
                resultado = self._fachada.registrar_consumo(
                    prontuario, excecao_grupos=self._fachada.excecao_grupos
                )

                if resultado.get("autorizado"):
                    return True, "Sucesso", resultado

                motivo = resultado.get("motivo", "Não autorizado")
                if "não encontrado" not in motivo.lower():
                    return False, motivo, resultado

            return self._buscar_por_nome_e_registrar(texto_entrada)

        except Exception as e:
            logger.exception("Erro ao processar entrada self-service: %s", e)
            return (
                False,
                str(e),
                {"nome": texto_entrada, "turma": "Erro de Sistema"},
            )

    @staticmethod
    def _filtrar_correspondencias_nome(
        candidatos: Any, nome_busca: str, score_minimo: int
    ) -> list[Dict[str, Any]]:
        """Ordena candidatos por similaridade parcial de nome acima do limiar."""
        return filtrar_correspondencias_nome(candidatos, nome_busca, score_minimo)

    def _buscar_por_nome_e_registrar(
        self, nome_busca: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Busca por nome (fuzzy) e registra seguindo estritamente as mesmas regras do QR Code."""
        excecoes = self._fachada.excecao_grupos
        elegiveis = self._fachada.obter_estudantes_para_sessao(
            consumido=False,
            pular_grupos=False,
            excecao_grupos=excecoes,
        )
        correspondencias = self._filtrar_correspondencias_nome(
            elegiveis, nome_busca, score_minimo=90
        )

        # Fallback apenas para identificar prontuário de aluno já atendido/inelegível
        # e retornar o motivo real da negação via registrar_consumo(pular_grupos=False).
        if not correspondencias:
            todos_ativos = self._fachada.obter_estudantes_para_sessao(
                consumido=None, pular_grupos=True
            )
            correspondencias = self._filtrar_correspondencias_nome(
                todos_ativos, nome_busca, score_minimo=90
            )

        ok, msg_ou_pront, dados = resolver_match_nome(correspondencias, nome_busca)
        if not ok:
            return False, msg_ou_pront, dados

        resultado_registro = self._fachada.registrar_consumo(
            msg_ou_pront,
            excecao_grupos=excecoes,
            pular_grupos=False,
        )
        if resultado_registro.get("autorizado"):
            return True, "Sucesso", resultado_registro

        return (
            False,
            resultado_registro.get("motivo", "Não autorizado"),
            resultado_registro,
        )

    def _buscar_melhor_match_por_nome(
        self, nome_busca: str
    ) -> Optional[Dict[str, Any]]:
        """Busca por nome e retorna o melhor match elegível como sugestão sem registrar."""
        if (
            len(nome_busca) < 3
            or not self._fachada
            or not self._fachada.id_sessao_ativa
        ):
            return None

        try:
            elegiveis = self._fachada.obter_estudantes_para_sessao(
                consumido=False,
                pular_grupos=False,
                excecao_grupos=self._fachada.excecao_grupos,
            )
            correspondencias = self._filtrar_correspondencias_nome(
                elegiveis, nome_busca, score_minimo=75
            )
            return correspondencias[0] if correspondencias else None
        except (SQLAlchemyError, ValueError, KeyError, TypeError) as e:
            logger.error("Erro ao buscar sugestão por nome: %s", e)
            return None

    def _tocar_som(self, sucesso: bool):
        """Toca som de feedback compatível com Windows e Linux."""
        emitir_feedback_sonoro(sucesso, widget=self)
