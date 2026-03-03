# ----------------------------------------------------------------------------
# Arquivo: registro/gui/janela_self_service.py (Janela de Autoatendimento)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

import logging
import tkinter as tk
from typing import Any, Callable, Dict, Optional, Tuple

import ttkbootstrap as ttk
from PIL import Image, ImageTk
from ttkbootstrap.constants import CENTER, LEFT, NSEW, RIGHT, X

logger = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np

    # Correção para Windows: adicionar diretório do pyzbar ao caminho de busca de DLLs
    # Isso ajuda a resolver problemas de caminho longo e dependências (libiconv.dll)
    import sys
    import os
    if sys.platform == "win32":
        import pyzbar
        # Adiciona o diretório do pacote (onde estão as DLLs) à busca
        # Atribuímos a uma variável para evitar que o Garbage Collector remova o caminho
        _pyzbar_dll_path = os.add_dll_directory(
            os.path.dirname(pyzbar.__file__))

    from pyzbar.pyzbar import decode, ZBarSymbol

    OPENCV_DISPONIVEL = True
except (ImportError, OSError) as e:
    logger.warning("Bibliotecas de câmera não disponíveis: %s", e)
    OPENCV_DISPONIVEL = False


class JanelaSelfService(tk.Toplevel):
    """
    Janela dedicada ao autoatendimento via leitura de QR Code pela webcam.
    """

    def __init__(
        self,
        parent: tk.Widget,
        callback_registro: Callable[[str], Tuple[bool, str, Dict[str, Any]]],
        callback_busca: Callable[[str], Optional[Dict[str, Any]]],
    ):
        super().__init__(parent)
        self.title("📷 Autoatendimento")
        self.geometry("900x600")
        self.minsize(800, 500)

        self._callback_registro = callback_registro
        self._callback_busca = callback_busca
        self._cap = None
        self._running = False
        self._cooldown_frames = 0

        # Cores e Estilos (Design Moderno e Feedback Visual)
        self.COR_FUNDO_PADRAO = "#111827"  # Gray 900
        self.COR_FUNDO_SUCESSO = "#065F46"  # Emerald 800
        self.COR_FUNDO_ERRO = "#991B1B"    # Red 800
        self.COR_TEXTO = "#FFFFFF"         # White

        self._lbl_video: Optional[ttk.Label] = None
        self._lbl_status: Optional[tk.Label] = None
        self._lbl_nome: Optional[tk.Label] = None
        self._lbl_turma: Optional[tk.Label] = None
        self._lbl_mensagem: Optional[tk.Label] = None
        self._lbl_sugestao_manual: Optional[tk.Label] = None
        self._entrada_manual: Optional[ttk.Entry] = None
        self._var_entrada_manual = tk.StringVar()
        self._id_after_busca_manual: Optional[str] = None
        self._frame_info: Optional[tk.Frame] = None

        self._criar_interface()

        if OPENCV_DISPONIVEL:
            self._iniciar_camera()
        else:
            self._exibir_erro_dependencia()

        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)

    def _criar_interface(self):
        """Cria os widgets da interface."""
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        # Frame da Câmera (Esquerda)
        frame_cam = ttk.Frame(self, padding=10, bootstyle="dark")
        frame_cam.grid(row=0, column=0, sticky=NSEW)
        frame_cam.rowconfigure(0, weight=1)
        frame_cam.columnconfigure(0, weight=1)

        self._lbl_video = ttk.Label(
            frame_cam,
            text="Inicializando Câmera...",
            anchor=CENTER,
            bootstyle="inverse-dark",
        )
        self._lbl_video.grid(row=0, column=0, sticky=NSEW, padx=2, pady=2)

        # Frame de Informações (Direita)
        self._frame_info = tk.Frame(self, bg=self.COR_FUNDO_PADRAO)
        self._frame_info.grid(row=0, column=1, sticky=NSEW)
        self._frame_info.pack_propagate(False)

        # Header
        tk.Label(
            self._frame_info,
            text="Autoatendimento",
            font=("Segoe UI", 24, "bold"),
            bg=self.COR_FUNDO_PADRAO,
            fg=self.COR_TEXTO,
            anchor="center",
        ).pack(fill=X, pady=(0, 10))

        # Separador visual
        tk.Frame(self._frame_info, height=2, bg="#374151").pack(
            fill=X, pady=(0, 20))

        # Status
        self._lbl_status = tk.Label(
            self._frame_info,
            text="Aguardando...",
            font=("Segoe UI", 22, "bold"),
            bg=self.COR_FUNDO_PADRAO,
            fg=self.COR_TEXTO,
            anchor="center",
        )
        self._lbl_status.pack(fill=X, pady=(10, 20))

        # Nome do Aluno
        self._lbl_nome = tk.Label(
            self._frame_info,
            text="--",
            font=("Segoe UI", 26, "bold"),
            bg=self.COR_FUNDO_PADRAO,
            fg=self.COR_TEXTO,
            wraplength=280,
            justify="center",
            anchor="center",
        )
        self._lbl_nome.pack(fill=X, pady=5)

        # Turma
        self._lbl_turma = tk.Label(
            self._frame_info,
            text="--",
            font=("Segoe UI", 18),
            bg=self.COR_FUNDO_PADRAO,
            fg=self.COR_TEXTO,
            anchor="center",
        )
        self._lbl_turma.pack(pady=5)

        # Mensagem de Erro/Detalhe
        self._lbl_mensagem = tk.Label(
            self._frame_info,
            text="",
            font=("Segoe UI", 14, "bold"),
            bg=self.COR_FUNDO_PADRAO,
            fg=self.COR_TEXTO,
            wraplength=280,
            justify="center",
            anchor="center",
        )
        self._lbl_mensagem.pack(fill=X, pady=(20, 0))

        # Área de Entrada Manual
        frame_manual = tk.LabelFrame(
            self._frame_info,
            text="Digitar Código / Scanner USB",
            bg=self.COR_FUNDO_PADRAO,
            fg=self.COR_TEXTO,
            font=("Segoe UI", 10),
            padx=10, pady=10,
            relief="flat",
            bd=1
        )
        frame_manual.pack(fill=X, side="bottom", pady=20, padx=20)
        frame_manual.columnconfigure(0, weight=1)

        self._entrada_manual = ttk.Entry(
            frame_manual,
            textvariable=self._var_entrada_manual,
            font=("Segoe UI", 12),
        )
        self._entrada_manual.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self._entrada_manual.bind("<Return>", self._ao_submeter_manual)
        self._var_entrada_manual.trace_add(
            "write", self._na_mudanca_entrada_manual)

        ttk.Button(
            frame_manual,
            text="OK",
            command=self._ao_submeter_manual,
            bootstyle="secondary",
        ).grid(row=0, column=1)

        self._lbl_sugestao_manual = tk.Label(
            frame_manual,
            text="",
            font=("Segoe UI", 9),
            bg=self.COR_FUNDO_PADRAO,
            fg="#A9A9A9",  # DarkGray
            anchor="w",
            justify="left",
        )
        self._lbl_sugestao_manual.grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0)
        )

    def _exibir_erro_dependencia(self):
        msg = "Bibliotecas 'opencv-python' e/ou 'pyzbar' não encontradas.\nInstale-as para usar o recurso de câmera."
        self._lbl_video.config(text=msg, bootstyle="danger")
        logger.error(msg)

    def _iniciar_camera(self):
        """Inicializa a captura de vídeo."""
        try:
            self._cap = cv2.VideoCapture(0)
            if not self._cap.isOpened():
                self._lbl_video.config(
                    text="Não foi possível acessar a webcam.", bootstyle="danger"
                )
                return

            self._running = True
            self._atualizar_frame()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Erro ao iniciar câmera: %s", e)
            self._lbl_video.config(text=f"Erro: {e}", bootstyle="danger")

    def _atualizar_frame(self):
        """Loop de atualização do frame da câmera."""
        if not self._running:
            return

        ret, frame = self._cap.read()
        if ret:
            if self._cooldown_frames > 0:
                self._cooldown_frames -= 1
                # Indicador visual de sucesso/processamento (borda verde)
                cv2.rectangle(
                    frame, (0, 0), (frame.shape[1],
                                    frame.shape[0]), (0, 255, 0), 10
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
                    # Desenha caixa em volta do QR Code
                    pts = obj.polygon
                    if len(pts) == 4:
                        pts = np.array(pts, np.int32)
                        pts = pts.reshape((-1, 1, 2))
                        cv2.polylines(frame, [pts], True, (0, 255, 0), 3)
                    break  # Processa apenas um por vez
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Erro ao decodificar frame: %s", e)

    def _exibir_frame_no_label(self, frame):
        """Converte o frame do OpenCV para Tkinter e exibe."""
        try:
            cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(cv2image)

            # Ajuste simples de tamanho para caber no label se necessário
            w_req = self._lbl_video.winfo_width()
            h_req = self._lbl_video.winfo_height()
            if w_req > 10 and h_req > 10:
                img.thumbnail((w_req, h_req))

            imgtk = ImageTk.PhotoImage(image=img)
            self._lbl_video.imgtk = imgtk
            self._lbl_video.configure(image=imgtk, text="")
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Erro ao exibir frame: %s", e)

    def _ao_submeter_manual(self, _=None):
        """Trata a submissão manual do código."""
        codigo = self._var_entrada_manual.get().strip()
        if codigo:
            if self._lbl_sugestao_manual:
                self._lbl_sugestao_manual.config(text="")
            self._processar_codigo(codigo, manual=True)
            self._var_entrada_manual.set("")
            if self._entrada_manual:
                self._entrada_manual.focus_set()

    def _na_mudanca_entrada_manual(self, *_):
        """Callback para quando o texto da entrada manual muda. Inicia busca com debounce."""
        if self._id_after_busca_manual:
            self.after_cancel(self._id_after_busca_manual)

        termo = self._var_entrada_manual.get()
        if len(termo) < 3:
            if self._lbl_sugestao_manual:
                self._lbl_sugestao_manual.config(text="")
            return

        self._id_after_busca_manual = self.after(
            300, self._atualizar_sugestao_manual)

    def _atualizar_sugestao_manual(self):
        """Executa a busca por sugestão e atualiza o label."""
        self._id_after_busca_manual = None
        termo_busca = self._var_entrada_manual.get()
        if not termo_busca or not self._callback_busca or not self._lbl_sugestao_manual:
            return

        melhor_match = self._callback_busca(termo_busca)

        if melhor_match:
            nome = melhor_match.get("nome", "Desconhecido")
            turma = melhor_match.get("turma", "")
            self._lbl_sugestao_manual.config(
                text=f"Sugestão: {nome} ({turma})")
        else:
            self._lbl_sugestao_manual.config(text="")

    def _processar_codigo(self, codigo: str, manual: bool = False):
        """Chama o callback de registro e atualiza a UI."""
        if not manual and self._cooldown_frames > 0:
            return

        logger.info("Processando código (%s): %s",
                    "Manual" if manual else "Cam", codigo)
        # Cooldown inicial preventivo
        self._cooldown_frames = 30

        sucesso, msg, dados = self._callback_registro(codigo)

        if sucesso:
            self._lbl_nome.config(text=dados.get("nome", "Desconhecido"))
            self._lbl_turma.config(text=dados.get("turma", ""))
            self._lbl_mensagem.config(text="")
            self._definir_feedback_visual("sucesso")
            self._tocar_som(sucesso=True)
            self._cooldown_frames = 20
        else:
            self._lbl_mensagem.config(text=msg)
            # Exibe os dados retornados mesmo em caso de erro (ex: nome do aluno sem reserva)
            self._lbl_nome.config(text=dados.get("nome", "--"))
            self._lbl_turma.config(text=dados.get("turma", "--"))
            self._definir_feedback_visual("erro")
            self._tocar_som(sucesso=False)
            self._cooldown_frames = 45

        if not self._running:
            self.after(self._cooldown_frames * 100,
                       lambda: self._definir_feedback_visual("padrao"))
            self._cooldown_frames = 0

    def _definir_feedback_visual(self, estado: str):
        """Altera as cores do painel de informações para dar feedback visual."""
        if estado == "sucesso":
            cor_bg = self.COR_FUNDO_SUCESSO
            texto_status = "REGISTRADO!"
        elif estado == "erro":
            cor_bg = self.COR_FUNDO_ERRO
            texto_status = "ERRO"
        else:
            cor_bg = self.COR_FUNDO_PADRAO
            texto_status = "Aguardando..."

        # Atualiza background do frame principal e widgets filhos compatíveis
        self._frame_info.config(bg=cor_bg)
        for widget in self._frame_info.winfo_children():
            if isinstance(widget, (tk.Label, tk.LabelFrame)):
                widget.config(bg=cor_bg, fg=self.COR_TEXTO)
            elif isinstance(widget, tk.Frame):
                # Oculta o separador (mesma cor do fundo) nos estados de alerta para reduzir ruído
                widget.config(bg=cor_bg if estado != "padrao" else "#374151")

        self._lbl_status.config(text=texto_status)

    def _tocar_som(self, sucesso: bool):
        """Tenta tocar um som de feedback."""
        try:
            import winsound

            freq = 1000 if sucesso else 400
            dur = 200 if sucesso else 1000
            winsound.Beep(freq, dur)
        except ImportError:
            pass
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def _ao_fechar(self):
        """Limpa recursos ao fechar a janela."""
        self._running = False
        if self._cap:
            self._cap.release()
        self.destroy()

