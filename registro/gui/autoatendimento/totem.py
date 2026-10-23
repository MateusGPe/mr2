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

import logging
import os
import re
import sys
import tkinter as tk
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple

from fuzzywuzzy import fuzz
from PIL import Image, ImageTk
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, CENTER, EW, NSEW, X

if TYPE_CHECKING:
    from registro.nucleo.facade import FachadaRegistro

logger = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np

    if sys.platform == "win32":
        import pyzbar

        _pyzbar_dll_path = os.add_dll_directory(
            os.path.dirname(pyzbar.__file__)
        )

    from pyzbar.pyzbar import ZBarSymbol, decode

    OPENCV_DISPONIVEL = True
except (ImportError, OSError) as e:
    logger.warning("Bibliotecas de câmera não disponíveis: %s", e)
    OPENCV_DISPONIVEL = False


class FrameSelfService(ttk.Frame):
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
        self._frame_info: Optional[tk.Frame] = None
        self._frame_cabecalho: Optional[tk.Frame] = None
        self._lbl_titulo_cabecalho: Optional[tk.Label] = None
        self._separador: Optional[tk.Frame] = None
        self._frame_estudante: Optional[tk.Frame] = None
        self._frame_manual: Optional[tk.LabelFrame] = None

        self._criar_interface()
        self.recarregar_sessao()

        if OPENCV_DISPONIVEL:
            self._iniciar_camera()
        else:
            self._exibir_erro_dependencia()

    def stop(self):
        """Libera recursos, como a câmera."""
        self._running = False
        if self._cap:
            try:
                self._cap.release()
            except Exception as e:
                logger.warning("Erro ao liberar câmera: %s", e)

    def focar_entrada(self):
        """Garante o foco contínuo no campo de entrada para scanners USB e digitação."""
        try:
            if self._entrada_manual and self._entrada_manual.winfo_exists():
                self._entrada_manual.focus_set()
        except Exception:
            pass

    def _ao_clicar_qualquer_lugar(self, event):
        """Mantém o foco no leitor USB se o clique foi em labels ou planos de fundo."""
        widget = event.widget
        if not isinstance(
            widget,
            (
                ttk.Entry,
                tk.Entry,
                ttk.Combobox,
                tk.Text,
                ttk.Button,
                tk.Button,
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
                refeicao = detalhes.get("refeicao", "Sessão").capitalize()
                hora = detalhes.get("hora", "")
                data = detalhes.get("data", "")
                item = detalhes.get("item_servido") or ""
                texto_item = f" • {item}" if item else ""
                grupos = list(detalhes.get("grupos", []))
                grupos_str = f"{len(grupos)} turmas" if grupos else "Todas"

                if self._lbl_refeicao_ativa:
                    self._lbl_refeicao_ativa.config(
                        text=f"{refeicao} ({hora}){texto_item}"
                    )
                if self._lbl_sessao_topo:
                    self._lbl_sessao_topo.config(
                        text=f"🍲 {refeicao} ({hora}){texto_item} | 📅 {data} | 👥 {grupos_str}"
                    )

                consumidos = self._fachada.obter_estudantes_para_sessao(
                    consumido=True
                )
                self._total_atendidos_sessao = len(consumidos)
                if self._lbl_contador_sessao:
                    self._lbl_contador_sessao.config(
                        text=f"Atendidos nesta sessão: {self._total_atendidos_sessao}"
                    )
            except Exception as e:
                logger.error("Erro ao recarregar detalhes da sessão: %s", e)
        else:
            if self._lbl_refeicao_ativa:
                self._lbl_refeicao_ativa.config(text="Nenhuma sessão ativa")
            if self._lbl_contador_sessao:
                self._lbl_contador_sessao.config(
                    text="Aguardando início de sessão"
                )
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

    def _criar_interface(self):
        """Cria os widgets da interface moderna com 50/50 e painel direito ocupando 100% da altura."""
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)

        # Captura cliques para manter o foco no scanner USB
        self.bind_all("<Button-1>", self._ao_clicar_qualquer_lugar, add="+")

        # Barra Superior de Status da Sessão (Apenas no lado esquerdo, sobre a câmera)
        frame_top_cam = ttk.Frame(self, bootstyle="dark", padding=(12, 8))
        frame_top_cam.grid(row=0, column=0, sticky=EW)
        frame_top_cam.columnconfigure(1, weight=1)

        lbl_logo = ttk.Label(
            frame_top_cam,
            text="🍽️ Totem Autoatendimento",
            font=("Segoe UI", 11, "bold"),
            bootstyle="@dark",
        )
        lbl_logo.grid(row=0, column=0, sticky="w", padx=(0, 10))

        self._lbl_sessao_topo = ttk.Label(
            frame_top_cam,
            text="Carregando sessão...",
            font=("Segoe UI", 10, "bold"),
            bootstyle="@dark",
            anchor="e",
        )
        self._lbl_sessao_topo.grid(row=0, column=1, sticky="ew")

        # Frame da Câmera (Esquerda, abaixo da barra de status)
        frame_cam_container = ttk.Frame(self, padding=8, bootstyle="dark")
        frame_cam_container.grid(row=1, column=0, sticky=NSEW)
        frame_cam_container.rowconfigure(0, weight=1)
        frame_cam_container.rowconfigure(1, weight=0)
        frame_cam_container.columnconfigure(0, weight=1)

        self._lbl_video = ttk.Label(
            frame_cam_container,
            text="Inicializando Câmera...",
            anchor=CENTER,
            bootstyle="@dark",
        )
        self._lbl_video.grid(row=0, column=0, sticky=NSEW, padx=2, pady=2)

        # Barra inferior da câmera com botão discreto de controles
        frame_cam_bottom = ttk.Frame(frame_cam_container, bootstyle="dark")
        frame_cam_bottom.grid(row=1, column=0, sticky="ew", pady=(6, 2))

        btn_controles = ttk.Button(
            frame_cam_bottom,
            text=" ⚙️ Controles ",
            bootstyle="secondary",
            padding=(8, 4),
        )
        btn_controles.config(
            command=lambda b=btn_controles: self._ao_clicar_controles(widget=b)
        )
        btn_controles.pack(side="left")

        # Clique com o botão direito para exibir o menu de contexto
        self.bind("<Button-3>", lambda e: self._ao_clicar_controles(event=e))
        self._lbl_video.bind(
            "<Button-3>", lambda e: self._ao_clicar_controles(event=e)
        )

        # Frame de Informações e Feedback (Direita) - Ocupa 100% da altura
        self._frame_info = tk.Frame(self, bg=self.COR_FUNDO_PADRAO)
        self._frame_info.grid(row=0, column=1, rowspan=2, sticky=NSEW)
        self._frame_info.pack_propagate(False)

        # Top Header
        self._frame_cabecalho = tk.Frame(
            self._frame_info, bg=self.COR_FUNDO_PADRAO
        )
        self._frame_cabecalho.pack(fill=X, padx=24, pady=(24, 12))

        self._lbl_titulo_cabecalho = tk.Label(
            self._frame_cabecalho,
            text="Totem de Autoatendimento",
            font=("Segoe UI", 24, "bold"),
            bg=self.COR_FUNDO_PADRAO,
            fg=self.COR_TEXTO,
            anchor="center",
        )
        self._lbl_titulo_cabecalho.pack(fill=X)

        self._lbl_refeicao_ativa = tk.Label(
            self._frame_cabecalho,
            text="Carregando sessão...",
            font=("Segoe UI", 13),
            bg=self.COR_FUNDO_PADRAO,
            fg="#9CA3AF",
            anchor="center",
        )
        self._lbl_refeicao_ativa.pack(fill=X, pady=(4, 0))

        # Separador visual
        self._separador = tk.Frame(self._frame_info, height=2, bg="#374151")
        self._separador.pack(fill=X, padx=24, pady=(5, 18))

        # Status Badge
        self._lbl_status = tk.Label(
            self._frame_info,
            text="Aguardando QR Code...",
            font=("Segoe UI", 24, "bold"),
            bg=self.COR_FUNDO_PADRAO,
            fg=self.COR_TEXTO,
            anchor="center",
        )
        self._lbl_status.pack(fill=X, pady=(5, 18))

        # Cartão Central do Estudante
        self._frame_estudante = tk.Frame(
            self._frame_info, bg=self.COR_FUNDO_PADRAO
        )
        self._frame_estudante.pack(fill=BOTH, expand=True, padx=24)

        self._lbl_nome = tk.Label(
            self._frame_estudante,
            text="--",
            font=("Segoe UI", 28, "bold"),
            bg=self.COR_FUNDO_PADRAO,
            fg=self.COR_TEXTO,
            wraplength=520,
            justify="center",
            anchor="center",
        )
        self._lbl_nome.pack(fill=X, pady=(6, 2))

        self._lbl_turma = tk.Label(
            self._frame_estudante,
            text="--",
            font=("Segoe UI", 20),
            bg=self.COR_FUNDO_PADRAO,
            fg="#E5E7EB",
            anchor="center",
        )
        self._lbl_turma.pack(fill=X, pady=2)

        self._lbl_prato = tk.Label(
            self._frame_estudante,
            text="",
            font=("Segoe UI", 16, "italic"),
            bg=self.COR_FUNDO_PADRAO,
            fg="#93C5FD",
            anchor="center",
        )
        self._lbl_prato.pack(fill=X, pady=3)

        self._lbl_mensagem = tk.Label(
            self._frame_estudante,
            text="",
            font=("Segoe UI", 15, "bold"),
            bg=self.COR_FUNDO_PADRAO,
            fg="#FCA5A5",
            wraplength=520,
            justify="center",
            anchor="center",
        )
        self._lbl_mensagem.pack(fill=X, pady=(16, 6))

        # Contador de Atendimentos
        self._lbl_contador_sessao = tk.Label(
            self._frame_info,
            text="Atendidos nesta sessão: 0",
            font=("Segoe UI", 12, "bold"),
            bg=self.COR_FUNDO_PADRAO,
            fg="#9CA3AF",
            anchor="center",
        )
        self._lbl_contador_sessao.pack(fill=X, pady=(0, 12))

        # Área de Entrada Manual / Scanner USB (Fixada no rodapé)
        self._frame_manual = tk.LabelFrame(
            self._frame_info,
            text=" Leitor USB / Digitação de Matrícula ",
            bg=self.COR_FUNDO_PADRAO,
            fg="#D1D5DB",
            font=("Segoe UI", 11, "bold"),
            padx=14,
            pady=12,
            relief="flat",
            bd=1,
        )
        self._frame_manual.pack(fill=X, side="bottom", pady=(0, 24), padx=24)
        self._frame_manual.columnconfigure(0, weight=1)

        self._entrada_manual = ttk.Entry(
            self._frame_manual,
            textvariable=self._var_entrada_manual,
            font=("Segoe UI", 16),
        )
        self._entrada_manual.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._entrada_manual.bind("<Return>", self._ao_submeter_manual)
        self._var_entrada_manual.trace_add(
            "write", self._na_mudanca_entrada_manual
        )

        ttk.Button(
            self._frame_manual,
            text="OK",
            command=self._ao_submeter_manual,
            bootstyle="success",
            width=6,
        ).grid(row=0, column=1)

        self._lbl_sugestao_manual = tk.Label(
            self._frame_manual,
            text="💡 Aponte o QR Code para a câmera ou passe o crachá no leitor",
            font=("Segoe UI", 9),
            bg=self.COR_FUNDO_PADRAO,
            fg="#9CA3AF",
            anchor="w",
            justify="left",
            wraplength=480,
        )
        self._lbl_sugestao_manual.grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0)
        )

    def _exibir_erro_dependencia(self):
        msg = (
            "Bibliotecas 'opencv-python' e/ou 'pyzbar' não encontradas.\n"
            "Instale-as para usar o recurso de câmera."
        )
        self._lbl_video.config(text=msg, bootstyle="danger")
        logger.error(msg)

    def _iniciar_camera(self):
        """Inicializa a captura de vídeo."""
        try:
            self._cap = cv2.VideoCapture(0)
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
                cv2.rectangle(
                    frame,
                    (0, 0),
                    (frame.shape[1], frame.shape[0]),
                    (0, 255, 0),
                    10,
                )
                if self._cooldown_frames == 0:
                    self._definir_feedback_visual("padrao")
            else:
                self._detectar_qr_code(frame)

            self._exibir_frame_no_label(frame)

        self.after(100, self._atualizar_frame)

    def _detectar_qr_code(self, frame):
        """Detecta e processa QR Codes no frame."""
        try:
            decoded_objects = decode(frame, symbols=[ZBarSymbol.QRCODE])
            for obj in decoded_objects:
                codigo = obj.data.decode("utf-8").strip()
                if codigo:
                    self._processar_codigo(codigo)
                    pts = obj.polygon
                    if len(pts) == 4:
                        pts = np.array(pts, np.int32)
                        pts = pts.reshape((-1, 1, 2))
                        cv2.polylines(frame, [pts], True, (0, 255, 0), 3)
                    break
        except Exception as e:
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
        except Exception as e:
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

        self._id_after_busca_manual = self.after(
            300, self._atualizar_sugestao_manual
        )

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
            self._cooldown_frames = 20
        else:
            self._lbl_mensagem.config(text=msg)
            self._lbl_nome.config(text=dados.get("nome", "--"))
            self._lbl_turma.config(text=dados.get("turma", "--"))
            self._lbl_prato.config(text="")
            self._definir_feedback_visual("erro")
            self._tocar_som(sucesso=False)
            self._cooldown_frames = 45

        if not self._running:
            self.after(
                self._cooldown_frames * 100,
                lambda: self._definir_feedback_visual("padrao"),
            )
            self._cooldown_frames = 0

        self.after(50, self.focar_entrada)

    @staticmethod
    def formatar_matricula(valor: Any) -> str:
        """Padroniza a matrícula para o formato IQ30XXXXX."""
        texto = str(valor).upper()
        numeros_e_x = re.findall(r"[0-9X]", texto)
        sufixo = "".join(numeros_e_x)[-5:]
        sufixo_formatado = sufixo.zfill(5)
        return f"IQ30{sufixo_formatado}"

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

    def _buscar_por_nome_e_registrar(
        self, nome_busca: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Busca por nome (fuzzy) e tenta registrar se houver correspondência clara."""
        elegiveis = self._fachada.obter_estudantes_para_sessao(
            consumido=False, pular_grupos=True
        )
        correspondencias = []
        nome_lower = nome_busca.lower()
        for estudante in elegiveis:
            nome_estudante = estudante.get("nome", "").lower()
            if not nome_estudante:
                continue
            score = fuzz.partial_ratio(nome_lower, nome_estudante)
            if score >= 90:
                estudante["score"] = score
                correspondencias.append(estudante)

        if not correspondencias:
            return (
                False,
                "Aluno não encontrado",
                {"nome": nome_busca, "turma": "Não Encontrado"},
            )

        correspondencias.sort(key=lambda x: -x["score"])
        melhor_match = correspondencias[0]

        if len(correspondencias) > 1 and (
            melhor_match["score"] < 98
            or (melhor_match["score"] - correspondencias[1]["score"]) < 10
        ):
            return (
                False,
                "Múltiplos resultados. Seja mais específico.",
                {"nome": nome_busca, "turma": "Busca Ambígua"},
            )

        prontuario_encontrado = melhor_match.get("pront")
        if not prontuario_encontrado:
            return (
                False,
                "Prontuário não encontrado para o nome.",
                {"nome": nome_busca, "turma": "Erro Interno"},
            )

        resultado_registro = self._fachada.registrar_consumo(
            prontuario_encontrado, pular_grupos=True
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
        """Busca por nome e retorna o melhor match como sugestão sem registrar."""
        if (
            len(nome_busca) < 3
            or not self._fachada
            or not self._fachada.id_sessao_ativa
        ):
            return None

        try:
            elegiveis = self._fachada.obter_estudantes_para_sessao(
                consumido=False, pular_grupos=True
            )

            correspondencias = []
            nome_lower = nome_busca.lower()

            for estudante in elegiveis:
                nome_estudante = estudante.get("nome", "").lower()
                if not nome_estudante:
                    continue

                score = fuzz.partial_ratio(nome_lower, nome_estudante)
                if score >= 75:
                    estudante["score"] = score
                    correspondencias.append(estudante)

            if not correspondencias:
                return None

            correspondencias.sort(key=lambda x: -x["score"])
            return correspondencias[0]
        except Exception as e:
            logger.error("Erro ao buscar sugestão por nome: %s", e)
            return None

    def _definir_feedback_visual(self, estado: str):
        """Altera as cores do painel de informações para feedback visual."""
        if estado == "sucesso":
            cor_bg = self.COR_FUNDO_SUCESSO
            texto_status = "REGISTRADO COM SUCESSO!"
            fg_titulo = "#FFFFFF"
            fg_refeicao = "#D1FAE5"
            fg_status = "#FFFFFF"
            fg_nome = "#FFFFFF"
            fg_turma = "#D1FAE5"
            fg_prato = "#FEF08A"
            fg_mensagem = "#D1FAE5"
            fg_contador = "#A7F3D0"
            fg_manual_titulo = "#A7F3D0"
            fg_sugestao = "#D1FAE5"
            cor_separador = "#047857"
        elif estado == "erro":
            cor_bg = self.COR_FUNDO_ERRO
            texto_status = "ATENÇÃO: NÃO AUTORIZADO"
            fg_titulo = "#FFFFFF"
            fg_refeicao = "#FEE2E2"
            fg_status = "#FFFFFF"
            fg_nome = "#FFFFFF"
            fg_turma = "#FECACA"
            fg_prato = "#FEE2E2"
            fg_mensagem = "#FEF08A"
            fg_contador = "#FCA5A5"
            fg_manual_titulo = "#FCA5A5"
            fg_sugestao = "#FECACA"
            cor_separador = "#B91C1C"
        else:
            cor_bg = self.COR_FUNDO_PADRAO
            texto_status = "Aguardando Leitura..."
            fg_titulo = "#FFFFFF"
            fg_refeicao = "#9CA3AF"
            fg_status = "#FFFFFF"
            fg_nome = "#FFFFFF"
            fg_turma = "#E5E7EB"
            fg_prato = "#93C5FD"
            fg_mensagem = "#FCA5A5"
            fg_contador = "#9CA3AF"
            fg_manual_titulo = "#D1D5DB"
            fg_sugestao = "#9CA3AF"
            cor_separador = "#374151"

        if self._frame_info:
            self._frame_info.config(bg=cor_bg)
        if self._frame_cabecalho:
            self._frame_cabecalho.config(bg=cor_bg)
        if self._lbl_titulo_cabecalho:
            self._lbl_titulo_cabecalho.config(bg=cor_bg, fg=fg_titulo)
        if self._lbl_refeicao_ativa:
            self._lbl_refeicao_ativa.config(bg=cor_bg, fg=fg_refeicao)
        if self._separador:
            self._separador.config(bg=cor_separador)
        if self._lbl_status:
            self._lbl_status.config(bg=cor_bg, fg=fg_status, text=texto_status)
        if self._frame_estudante:
            self._frame_estudante.config(bg=cor_bg)
        if self._lbl_nome:
            self._lbl_nome.config(bg=cor_bg, fg=fg_nome)
        if self._lbl_turma:
            self._lbl_turma.config(bg=cor_bg, fg=fg_turma)
        if self._lbl_prato:
            self._lbl_prato.config(bg=cor_bg, fg=fg_prato)
        if self._lbl_mensagem:
            self._lbl_mensagem.config(bg=cor_bg, fg=fg_mensagem)
        if self._lbl_contador_sessao:
            self._lbl_contador_sessao.config(bg=cor_bg, fg=fg_contador)
        if self._frame_manual:
            self._frame_manual.config(bg=cor_bg, fg=fg_manual_titulo)
        if self._lbl_sugestao_manual:
            self._lbl_sugestao_manual.config(bg=cor_bg, fg=fg_sugestao)

    def _tocar_som(self, sucesso: bool):
        """Toca som de feedback no Windows."""
        try:
            import winsound

            freq = 1000 if sucesso else 400
            dur = 200 if sucesso else 1000
            winsound.Beep(freq, dur)
        except Exception:
            pass
