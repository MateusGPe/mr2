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
from ttkbootstrap.constants import CENTER, NSEW, W, X

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
        _pyzbar_dll_path = os.add_dll_directory(os.path.dirname(pyzbar.__file__))

    from pyzbar.pyzbar import decode

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
    ):
        super().__init__(parent)
        self.title("📷 Autoatendimento")
        self.geometry("900x600")
        self.minsize(800, 500)

        self._callback_registro = callback_registro
        self._cap = None
        self._running = False
        self._cooldown_frames = 0

        self._lbl_video: Optional[ttk.Label] = None
        self._lbl_status: Optional[ttk.Label] = None
        self._lbl_nome: Optional[ttk.Label] = None
        self._lbl_turma: Optional[ttk.Label] = None
        self._lbl_mensagem: Optional[ttk.Label] = None

        self._criar_interface()

        if OPENCV_DISPONIVEL:
            self._iniciar_camera()
        else:
            self._exibir_erro_dependencia()

        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)

    def _criar_interface(self):
        """Cria os widgets da interface."""
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        # Frame da Câmera (Esquerda)
        frame_cam = ttk.Frame(self, padding=10)
        frame_cam.grid(row=0, column=0, sticky=NSEW)
        frame_cam.rowconfigure(0, weight=1)
        frame_cam.columnconfigure(0, weight=1)

        self._lbl_video = ttk.Label(
            frame_cam,
            text="Inicializando Câmera...",
            anchor=CENTER,
            bootstyle="dark",
        )
        self._lbl_video.grid(row=0, column=0, sticky=NSEW)

        # Frame de Informações (Direita)
        frame_info = ttk.Frame(self, padding=20, bootstyle="light")
        frame_info.grid(row=0, column=1, sticky=NSEW)
        frame_info.columnconfigure(0, weight=1)

        ttk.Label(
            frame_info,
            text="Autoatendimento",
            font=("Segoe UI", 24, "bold"),
            bootstyle="inverse-light",
            anchor=CENTER,
        ).pack(fill=X, pady=(0, 20))

        ttk.Separator(frame_info, bootstyle="secondary").pack(fill=X, pady=10)

        self._lbl_status = ttk.Label(
            frame_info,
            text="Aguardando Leitura...",
            font=("Segoe UI", 16),
            bootstyle="info-inverse",
            anchor=CENTER,
            padding=10,
        )
        self._lbl_status.pack(fill=X, pady=20)

        ttk.Label(
            frame_info,
            text="Último Registro:",
            font=("Segoe UI", 12),
            bootstyle="inverse-light",
        ).pack(anchor=W, pady=(20, 5))

        self._lbl_nome = ttk.Label(
            frame_info,
            text="--",
            font=("Segoe UI", 18, "bold"),
            bootstyle="inverse-light",
            wraplength=300,
            justify=CENTER,
        )
        self._lbl_nome.pack(fill=X, pady=5)

        self._lbl_turma = ttk.Label(
            frame_info,
            text="--",
            font=("Segoe UI", 14),
            bootstyle="secondary-inverse",
        )
        self._lbl_turma.pack(pady=5)

        self._lbl_mensagem = ttk.Label(
            frame_info,
            text="",
            font=("Segoe UI", 12),
            bootstyle="danger",
            wraplength=300,
            justify=CENTER,
        )
        self._lbl_mensagem.pack(fill=X, pady=20)

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
                    frame, (0, 0), (frame.shape[1], frame.shape[0]), (0, 255, 0), 10
                )
            else:
                self._detectar_qr_code(frame)

            self._exibir_frame_no_label(frame)

        self.after(20, self._atualizar_frame)

    def _detectar_qr_code(self, frame):
        """Detecta e processa QR Codes no frame."""
        try:
            decoded_objects = decode(frame)
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

    def _processar_codigo(self, codigo: str):
        """Chama o callback de registro e atualiza a UI."""
        if self._cooldown_frames > 0:
            return

        logger.info("Código lido: %s", codigo)
        self._cooldown_frames = 60  # ~1-2 segundos de pausa

        sucesso, msg, dados = self._callback_registro(codigo)

        if sucesso:
            self._lbl_status.config(text="REGISTRADO!", bootstyle="success-inverse")
            self._lbl_nome.config(text=dados.get("nome", "Desconhecido"))
            self._lbl_turma.config(text=dados.get("turma", ""))
            self._lbl_mensagem.config(text="")
            self._tocar_som(sucesso=True)
        else:
            self._lbl_status.config(text="ERRO", bootstyle="danger-inverse")
            self._lbl_mensagem.config(text=msg)
            self._tocar_som(sucesso=False)

    def _tocar_som(self, sucesso: bool):
        """Tenta tocar um som de feedback."""
        try:
            import winsound

            freq = 1000 if sucesso else 400
            dur = 200 if sucesso else 500
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
