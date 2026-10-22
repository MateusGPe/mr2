# ----------------------------------------------------------------------------
# Arquivo: registro/gui/autoatendimento/app.py (Aplicação Autônoma de Autoatendimento)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

import datetime as dt
import logging
import os
import re
import sys
import tkinter as tk
import traceback
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set, Tuple, Union

from fuzzywuzzy import fuzz
from PIL import Image, ImageTk
import ttkbootstrap as ttk
from ttkbootstrap.constants import CENTER, LEFT, NSEW, RIGHT, X, EW, BOTH, HORIZONTAL
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.localization.msgcat import MessageCatalog

from registro.gui.autoatendimento.dialogos import (
    DialogoNovoConsumo,
    DialogoEditarConsumo,
    DialogoDetalhesConsumo,
)
from registro.gui.comum.controles.treeview_simples import TreeviewSimples
from registro.gui.comum.constants import REGEX_LIMPEZA_PRONTUARIO
from registro.gui.registrar.dialogo_sessao import DialogoSessao
from registro.gui.registrar.dialogo_filtro_turmas import DialogoFiltroTurmas
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

    from pyzbar.pyzbar import decode, ZBarSymbol

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
        abrir_controles_callback: Optional[Callable[[], None]] = None,
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
        self.COR_FUNDO_ERRO = "#991B1B"    # Red 800
        self.COR_TEXTO = "#FFFFFF"         # White

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
        if not isinstance(widget, (ttk.Entry, tk.Entry, ttk.Combobox, tk.Text, ttk.Button, tk.Button)):
            self.after(50, self.focar_entrada)

    def _ao_clicar_controles(self, widget: Optional[tk.Widget] = None, event: Optional[Any] = None):
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

                consumidos = self._fachada.obter_estudantes_para_sessao(consumido=True)
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
        btn_controles.config(command=lambda b=btn_controles: self._ao_clicar_controles(widget=b))
        btn_controles.pack(side="left")

        # Clique com o botão direito para exibir o menu de contexto
        self.bind("<Button-3>", lambda e: self._ao_clicar_controles(event=e))
        self._lbl_video.bind("<Button-3>", lambda e: self._ao_clicar_controles(event=e))

        # Frame de Informações e Feedback (Direita) - COBRE TODA A ALTURA DO TOPO AO RODAPÉ
        self._frame_info = tk.Frame(self, bg=self.COR_FUNDO_PADRAO)
        self._frame_info.grid(row=0, column=1, rowspan=2, sticky=NSEW)
        self._frame_info.pack_propagate(False)

        # Top Header
        self._frame_cabecalho = tk.Frame(self._frame_info, bg=self.COR_FUNDO_PADRAO)
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
        self._frame_estudante = tk.Frame(self._frame_info, bg=self.COR_FUNDO_PADRAO)
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
        msg = "Bibliotecas 'opencv-python' e/ou 'pyzbar' não encontradas.\nInstale-as para usar o recurso de câmera."
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
                    frame, (0, 0), (frame.shape[1], frame.shape[0]), (0, 255, 0), 10
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

        logger.info("Processando código (%s): %s", "Manual" if manual else "Cam", codigo)
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

    def _registrar_entrada(self, texto_entrada: str) -> Tuple[bool, str, Dict[str, Any]]:
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
            return False, str(e), {"nome": texto_entrada, "turma": "Erro de Sistema"}

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
        if len(nome_busca) < 3 or not self._fachada or not self._fachada.id_sessao_ativa:
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
            fg_prato = "#FEF08A"  # Amarelo suave em destaque para o prato
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
            fg_mensagem = "#FEF08A"  # Amarelo de alerta para mensagem de erro
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
            fg_prato = "#93C5FD"  # Azul suave para item servido em repouso
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


class AbaDashboard(ttk.Frame):
    """
    Painel avançado com estatísticas consolidadas e métricas em tempo real
    da sessão de autoatendimento.
    """

    def __init__(
        self,
        master: tk.Widget,
        fachada: "FachadaRegistro",
        id_sessao: Optional[int],
        voltar_callback: Optional[Callable[[], None]] = None,
        abrir_controles_callback: Optional[Callable[..., None]] = None,
        navegar_callback: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(master, padding=(16, 12))
        self.fachada = fachada
        self.id_sessao = id_sessao
        self.voltar_callback = voltar_callback
        self.abrir_controles_callback = abrir_controles_callback
        self.navegar_callback = navegar_callback

        self.rowconfigure(1, weight=0)  # Linha dos KPI Cards
        self.rowconfigure(2, weight=1)  # Linha das Análises e Distribuições
        self.columnconfigure(0, weight=1)

        self._construir_interface()
        self.atualizar_dados()

    def _construir_interface(self):
        """Constrói a interface com navegação, cards KPI e painéis analíticos."""
        # --- Barra Superior de Navegação ---
        frame_topo = ttk.Frame(self)
        frame_topo.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        frame_topo.columnconfigure(1, weight=1)

        frame_nav_esq = ttk.Frame(frame_topo)
        frame_nav_esq.grid(row=0, column=0, sticky="w")

        if self.voltar_callback:
            ttk.Button(
                frame_nav_esq,
                text=" ⬅ Voltar ao Totem ",
                command=self.voltar_callback,
                bootstyle="primary",
                padding=(10, 6),
            ).pack(side=LEFT, padx=(0, 6))

        if self.navegar_callback:
            ttk.Button(
                frame_nav_esq,
                text=" 📋 Ver Registros (CRUD) ",
                command=lambda: self.navegar_callback("consumos"),
                bootstyle="info-outline",
                padding=(10, 6),
            ).pack(side=LEFT)

        ttk.Label(
            frame_topo,
            text="📊 Dashboard & Estatísticas da Sessão",
            font=("Segoe UI", 18, "bold"),
            anchor="center",
        ).grid(row=0, column=1, sticky="ew")

        frame_nav_dir = ttk.Frame(frame_topo)
        frame_nav_dir.grid(row=0, column=2, sticky="e")

        ttk.Button(
            frame_nav_dir,
            text=" 🔄 Atualizar ",
            command=self.atualizar_dados,
            bootstyle="secondary-outline",
            padding=(8, 6),
        ).pack(side=LEFT, padx=(0, 6))

        if self.abrir_controles_callback:
            btn_ctrl = ttk.Button(
                frame_nav_dir,
                text=" ⚙️ Controles ",
                bootstyle="secondary",
                padding=(8, 6),
            )
            btn_ctrl.config(
                command=lambda b=btn_ctrl: self.abrir_controles_callback(widget=b)
            )
            btn_ctrl.pack(side=LEFT)

        # --- Linha 1: Cards KPI Principais ---
        frame_kpis = ttk.Frame(self)
        frame_kpis.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        for col in range(5):
            frame_kpis.columnconfigure(col, weight=1)

        # 1. Total Consumos
        card_total = ttk.Frame(frame_kpis, bootstyle="primary", padding=(12, 12))
        card_total.grid(row=0, column=0, sticky="nsew", padx=4)
        ttk.Label(
            card_total, text="Refeições Servidas", font=("Segoe UI", 10), bootstyle="@primary"
        ).pack(anchor="center")
        self.lbl_total_consumos = ttk.Label(
            card_total, text="0", font=("Segoe UI", 36, "bold"), bootstyle="@primary"
        )
        self.lbl_total_consumos.pack(expand=True)
        self.lbl_total_sub = ttk.Label(
            card_total, text="Atendimentos registrados", font=("Segoe UI", 8), bootstyle="@primary"
        )
        self.lbl_total_sub.pack(anchor="center")

        # 2. Restantes
        card_rest = ttk.Frame(frame_kpis, bootstyle="warning", padding=(12, 12))
        card_rest.grid(row=0, column=1, sticky="nsew", padx=4)
        ttk.Label(
            card_rest, text="Alunos Restantes", font=("Segoe UI", 10), bootstyle="@warning"
        ).pack(anchor="center")
        self.lbl_restantes = ttk.Label(
            card_rest, text="0", font=("Segoe UI", 36, "bold"), bootstyle="@warning"
        )
        self.lbl_restantes.pack(expand=True)
        self.lbl_restantes_sub = ttk.Label(
            card_rest, text="Aguardando atendimento", font=("Segoe UI", 8), bootstyle="@warning"
        )
        self.lbl_restantes_sub.pack(anchor="center")

        # 3. Taxa de Adesão
        card_adesao = ttk.Frame(frame_kpis, bootstyle="success", padding=(12, 12))
        card_adesao.grid(row=0, column=2, sticky="nsew", padx=4)
        ttk.Label(
            card_adesao, text="Taxa de Adesão", font=("Segoe UI", 10), bootstyle="@success"
        ).pack(anchor="center")
        self.lbl_adesao = ttk.Label(
            card_adesao, text="0%", font=("Segoe UI", 36, "bold"), bootstyle="@success"
        )
        self.lbl_adesao.pack(expand=True)
        self.progress_adesao = ttk.Progressbar(
            card_adesao, value=0, maximum=100, bootstyle="success-striped"
        )
        self.progress_adesao.pack(fill=X, padx=10, pady=(2, 4))
        self.lbl_esperados = ttk.Label(
            card_adesao, text="0 de 0 esperados", font=("Segoe UI", 8), bootstyle="@success"
        )
        self.lbl_esperados.pack(anchor="center")

        # 4. Reservas vs Avulsos
        card_reserva = ttk.Frame(frame_kpis, bootstyle="info", padding=(12, 12))
        card_reserva.grid(row=0, column=3, sticky="nsew", padx=4)
        ttk.Label(
            card_reserva, text="Com Reserva / Avulso", font=("Segoe UI", 10), bootstyle="@info"
        ).pack(anchor="center")
        self.lbl_reserva_info = ttk.Label(
            card_reserva, text="0 / 0", font=("Segoe UI", 28, "bold"), bootstyle="@info"
        )
        self.lbl_reserva_info.pack(expand=True)
        self.lbl_reserva_sub = ttk.Label(
            card_reserva, text="Planejados vs Exceções", font=("Segoe UI", 8), bootstyle="@info"
        )
        self.lbl_reserva_sub.pack(anchor="center")

        # 5. Último Atendimento
        card_ultimo = ttk.Frame(frame_kpis, bootstyle="secondary", padding=(12, 12))
        card_ultimo.grid(row=0, column=4, sticky="nsew", padx=4)
        ttk.Label(
            card_ultimo, text="Último Registro", font=("Segoe UI", 10), bootstyle="@secondary"
        ).pack(anchor="center")
        self.lbl_ultimo_consumo_nome = ttk.Label(
            card_ultimo,
            text="--",
            font=("Segoe UI", 13, "bold"),
            bootstyle="@secondary",
            wraplength=180,
            anchor="center",
            justify="center",
        )
        self.lbl_ultimo_consumo_nome.pack(expand=True)
        self.lbl_ultimo_consumo_hora = ttk.Label(
            card_ultimo, text="", font=("Segoe UI", 11), bootstyle="@secondary"
        )
        self.lbl_ultimo_consumo_hora.pack(anchor="center")

        # --- Linha 2: Painéis de Distribuição e Desempenho Analítico ---
        frame_analises = ttk.Frame(self)
        frame_analises.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        frame_analises.columnconfigure((0, 1, 2), weight=1)
        frame_analises.rowconfigure(0, weight=1)

        # Painel A: Distribuição por Prato
        self.card_pratos = ttk.LabelFrame(
            frame_analises, text=" 🍽️ Distribuição por Cardápio / Prato ", padding=12
        )
        self.card_pratos.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.card_pratos.rowconfigure(0, weight=1)
        self.card_pratos.columnconfigure(0, weight=1)

        self.frame_lista_pratos = ttk.Frame(self.card_pratos)
        self.frame_lista_pratos.grid(row=0, column=0, sticky="nsew")
        self.frame_lista_pratos.columnconfigure(1, weight=1)

        # Painel B: Top Turmas
        self.card_turmas = ttk.LabelFrame(
            frame_analises, text=" 👥 Top Turmas Atendidas ", padding=12
        )
        self.card_turmas.grid(row=0, column=1, sticky="nsew", padx=4)
        self.card_turmas.rowconfigure(0, weight=1)
        self.card_turmas.columnconfigure(0, weight=1)

        self.frame_lista_turmas = ttk.Frame(self.card_turmas)
        self.frame_lista_turmas.grid(row=0, column=0, sticky="nsew")
        self.frame_lista_turmas.columnconfigure(1, weight=1)

        # Painel C: Fluxo e Performance
        self.card_fluxo = ttk.LabelFrame(
            frame_analises, text=" ⏱️ Ritmo de Atendimento & Horários ", padding=12
        )
        self.card_fluxo.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        self.card_fluxo.rowconfigure(4, weight=1)
        self.card_fluxo.columnconfigure(0, weight=1)

        self.lbl_pico_horario = ttk.Label(
            self.card_fluxo,
            text="🔥 Horário de Pico: --",
            font=("Segoe UI", 10, "bold"),
            bootstyle="primary",
        )
        self.lbl_pico_horario.grid(row=0, column=0, sticky="w", pady=2)

        self.lbl_velocidade = ttk.Label(
            self.card_fluxo,
            text="⚡ Velocidade: -- atendimentos/minuto",
            font=("Segoe UI", 9),
        )
        self.lbl_velocidade.grid(row=1, column=0, sticky="w", pady=2)

        self.lbl_primeiro_consumo = ttk.Label(
            self.card_fluxo,
            text="🚩 Início da Fila: --",
            font=("Segoe UI", 9),
            bootstyle="secondary",
        )
        self.lbl_primeiro_consumo.grid(row=2, column=0, sticky="w", pady=2)

        ttk.Separator(self.card_fluxo, orient=HORIZONTAL).grid(
            row=3, column=0, sticky="ew", pady=6
        )

        ttk.Label(
            self.card_fluxo, text="Faixas de Horário (Intervalos):", font=("Segoe UI", 9, "bold")
        ).grid(row=4, column=0, sticky="w", pady=(0, 4))

        self.frame_lista_faixas = ttk.Frame(self.card_fluxo)
        self.frame_lista_faixas.grid(row=5, column=0, sticky="nsew")
        self.frame_lista_faixas.columnconfigure(1, weight=1)

        # --- Rodapé da Sessão ---
        frame_rodape = ttk.Frame(self)
        frame_rodape.grid(row=3, column=0, sticky="ew")
        frame_rodape.columnconfigure(0, weight=1)

        self.lbl_info_sessao = ttk.Label(
            frame_rodape,
            text="Sessão não iniciada",
            font=("Segoe UI", 9),
            bootstyle="secondary",
        )
        self.lbl_info_sessao.grid(row=0, column=0, sticky="w")

        ttk.Button(
            frame_rodape,
            text=" 📥 Exportar Relatório de Sessão (XLSX) ",
            command=self._exportar_relatorio,
            bootstyle="secondary-outline",
            padding=(10, 4),
        ).grid(row=0, column=1, sticky="e")

    def definir_sessao(self, id_sessao: Optional[int]):
        """Atualiza a sessão ativa exibida no dashboard."""
        self.id_sessao = id_sessao
        self.atualizar_dados()

    def atualizar_dados(self, ultimo_consumo: Optional[Tuple[str, ...]] = None):
        """Calcula e atualiza os contadores, gráficos e distribuições no dashboard."""
        if not self.id_sessao or not self.fachada or not self.fachada.id_sessao_ativa:
            self.lbl_total_consumos.config(text="0")
            self.lbl_restantes.config(text="0")
            self.lbl_adesao.config(text="0%")
            self.progress_adesao.config(value=0)
            self.lbl_esperados.config(text="Sem Sessão Ativa")
            self.lbl_reserva_info.config(text="0 / 0")
            self.lbl_ultimo_consumo_nome.config(text="Sem Sessão")
            self.lbl_ultimo_consumo_hora.config(text="")
            self.lbl_info_sessao.config(text="⚠️ Nenhuma sessão ativa no momento.")
            self._limpar_paineis_analiticos()
            return

        try:
            stats = None
            if hasattr(self.fachada, "obter_estatisticas_sessao"):
                try:
                    stats = self.fachada.obter_estatisticas_sessao(self.id_sessao)
                except Exception as ex_stats:
                    logger.debug("Falha em obter_estatisticas_sessao: %s", ex_stats)

            if not stats:
                consumidos = self.fachada.obter_estudantes_para_sessao(consumido=True)
                stats = {
                    "total_consumidos": len(consumidos),
                    "total_restantes": 0,
                    "total_esperado": len(consumidos),
                    "taxa_adesao": 100.0 if consumidos else 0.0,
                    "total_com_reserva": len(consumidos),
                    "total_sem_reserva": 0,
                    "distribuicao_pratos": {},
                    "distribuicao_turmas": {},
                    "distribuicao_horarios": {},
                    "horario_pico": None,
                    "primeiro_consumo": None,
                    "ultimo_consumo": None,
                    "velocidade_por_minuto": 0.0,
                }

            # Atualiza KPI Cards
            tot_cons = stats.get("total_consumidos", 0)
            tot_rest = stats.get("total_restantes", 0)
            tot_esp = stats.get("total_esperado", 0)
            taxa = stats.get("taxa_adesao", 0.0)
            c_res = stats.get("total_com_reserva", 0)
            s_res = stats.get("total_sem_reserva", 0)

            self.lbl_total_consumos.config(text=str(tot_cons))
            self.lbl_restantes.config(text=str(tot_rest))
            self.lbl_adesao.config(text=f"{taxa:.1f}%")
            self.progress_adesao.config(value=taxa)
            self.lbl_esperados.config(text=f"{tot_cons} de {tot_esp} esperados")
            self.lbl_reserva_info.config(text=f"{c_res} / {s_res}")
            pct_res = f"{(c_res / tot_cons * 100):.0f}% com reserva" if tot_cons > 0 else "--"
            self.lbl_reserva_sub.config(text=pct_res)

            # Último consumo
            if ultimo_consumo and len(ultimo_consumo) >= 4:
                self.lbl_ultimo_consumo_nome.config(text=str(ultimo_consumo[1]))
                self.lbl_ultimo_consumo_hora.config(text=f"às {ultimo_consumo[3]}")
            else:
                uc = stats.get("ultimo_consumo")
                if uc:
                    self.lbl_ultimo_consumo_nome.config(text=str(uc.get("nome", "--")))
                    self.lbl_ultimo_consumo_hora.config(
                        text=f"às {uc.get('hora_consumo', '')}"
                    )
                else:
                    self.lbl_ultimo_consumo_nome.config(text="--")
                    self.lbl_ultimo_consumo_hora.config(text="")

            # Atualiza Distribuição de Pratos
            self._atualizar_painel_pratos(stats.get("distribuicao_pratos", {}), tot_cons)

            # Atualiza Top Turmas
            self._atualizar_painel_turmas(stats.get("distribuicao_turmas", {}), tot_cons)

            # Atualiza Ritmo de Atendimento
            self._atualizar_painel_fluxo(stats)

            # Rodapé informativo da sessão
            refeicao = str(stats.get("refeicao", "Sessão")).capitalize()
            data = str(stats.get("data", ""))
            hora_prev = str(stats.get("hora_prevista", ""))
            item = str(stats.get("item_servido") or "")
            item_txt = f" • Item: {item}" if item else ""
            self.lbl_info_sessao.config(
                text=f"🍲 {refeicao} ({hora_prev}){item_txt} | 📅 Data: {data} | ID Sessão: {self.id_sessao}"
            )

        except Exception as e:
            logger.error("Erro ao atualizar dashboard analítico: %s", e)

    def _limpar_paineis_analiticos(self):
        for widget in self.frame_lista_pratos.winfo_children():
            widget.destroy()
        for widget in self.frame_lista_turmas.winfo_children():
            widget.destroy()
        for widget in self.frame_lista_faixas.winfo_children():
            widget.destroy()

    def _atualizar_painel_pratos(self, dist_pratos: Dict[str, int], total: int):
        for widget in self.frame_lista_pratos.winfo_children():
            widget.destroy()

        if not dist_pratos:
            ttk.Label(
                self.frame_lista_pratos,
                text="Nenhum prato registrado ainda.",
                font=("Segoe UI", 9, "italic"),
                bootstyle="secondary",
            ).pack(anchor="w", pady=6)
            return

        for idx, (prato, count) in enumerate(dist_pratos.items()):
            pct = (count / total * 100) if total > 0 else 0
            frame_item = ttk.Frame(self.frame_lista_pratos)
            frame_item.pack(fill=X, pady=3)
            frame_item.columnconfigure(1, weight=1)

            ttk.Label(
                frame_item,
                text=f"{prato}:",
                font=("Segoe UI", 9, "bold"),
                width=16,
                anchor="w",
            ).grid(row=0, column=0, sticky="w")

            prog = ttk.Progressbar(
                frame_item, value=pct, maximum=100, bootstyle="info"
            )
            prog.grid(row=0, column=1, sticky="ew", padx=6)

            ttk.Label(
                frame_item,
                text=f"{count} ({pct:.0f}%)",
                font=("Segoe UI", 9),
                width=10,
                anchor="e",
            ).grid(row=0, column=2, sticky="e")

    def _atualizar_painel_turmas(self, dist_turmas: Dict[str, int], total: int):
        for widget in self.frame_lista_turmas.winfo_children():
            widget.destroy()

        if not dist_turmas:
            ttk.Label(
                self.frame_lista_turmas,
                text="Nenhum atendimento por turma.",
                font=("Segoe UI", 9, "italic"),
                bootstyle="secondary",
            ).pack(anchor="w", pady=6)
            return

        # Exibe as top 6 turmas com mais consumos
        top_turmas = list(dist_turmas.items())[:6]
        max_turma = top_turmas[0][1] if top_turmas else 1

        for idx, (turma, count) in enumerate(top_turmas):
            pct_bar = (count / max_turma * 100) if max_turma > 0 else 0
            frame_item = ttk.Frame(self.frame_lista_turmas)
            frame_item.pack(fill=X, pady=3)
            frame_item.columnconfigure(1, weight=1)

            ttk.Label(
                frame_item,
                text=turma[:18],
                font=("Segoe UI", 9, "bold"),
                width=18,
                anchor="w",
            ).grid(row=0, column=0, sticky="w")

            prog = ttk.Progressbar(
                frame_item, value=pct_bar, maximum=100, bootstyle="success"
            )
            prog.grid(row=0, column=1, sticky="ew", padx=6)

            ttk.Label(
                frame_item,
                text=f"{count}",
                font=("Segoe UI", 9, "bold"),
                width=6,
                anchor="e",
            ).grid(row=0, column=2, sticky="e")

    def _atualizar_painel_fluxo(self, stats: Dict[str, Any]):
        pico = stats.get("horario_pico")
        if pico:
            self.lbl_pico_horario.config(
                text=f"🔥 Horário de Pico: {pico[0]} ({pico[1]} refeições)"
            )
        else:
            self.lbl_pico_horario.config(text="🔥 Horário de Pico: Em cálculo...")

        vel = stats.get("velocidade_por_minuto", 0.0)
        self.lbl_velocidade.config(text=f"⚡ Velocidade Média: {vel:.1f} atendimentos/min")

        pc = stats.get("primeiro_consumo")
        if pc:
            self.lbl_primeiro_consumo.config(
                text=f"🚩 Primeiro Atendimento: às {pc.get('hora_consumo', '')} ({pc.get('nome', '')[:20]})"
            )
        else:
            self.lbl_primeiro_consumo.config(text="🚩 Primeiro Atendimento: --")

        # Faixas de Horário
        for widget in self.frame_lista_faixas.winfo_children():
            widget.destroy()

        dist_horarios = stats.get("distribuicao_horarios", {})
        if not dist_horarios:
            ttk.Label(
                self.frame_lista_faixas,
                text="Sem dados temporais disponíveis.",
                font=("Segoe UI", 8, "italic"),
                bootstyle="secondary",
            ).pack(anchor="w")
            return

        for faixa, qtd in list(dist_horarios.items())[-5:]:
            f_row = ttk.Frame(self.frame_lista_faixas)
            f_row.pack(fill=X, pady=1)
            f_row.columnconfigure(1, weight=1)

            ttk.Label(
                f_row, text=faixa, font=("Segoe UI", 8), width=18, anchor="w"
            ).grid(row=0, column=0, sticky="w")
            ttk.Label(
                f_row, text=f"{qtd} atendimentos", font=("Segoe UI", 8, "bold"), anchor="e"
            ).grid(row=0, column=1, sticky="e")

    def _exportar_relatorio(self):
        """Exporta os dados de consumo e resumo da sessão para arquivo Excel."""
        if not self.id_sessao or not self.fachada:
            Messagebox.show_warning("Aviso", "Nenhuma sessão ativa para exportar.", parent=self)
            return

        try:
            caminho = self.fachada.exportar_sessao_para_xlsx(self.id_sessao)
            Messagebox.show_info(
                "Exportação Concluída",
                f"Relatório exportado com sucesso para:\n{caminho}",
                parent=self,
            )
        except Exception as e:
            logger.exception("Erro ao exportar planilha de sessão: %s", e)
            Messagebox.show_error("Erro na Exportação", f"Não foi possível exportar:\n{e}", parent=self)


class AbaConsumos(ttk.Frame):
    """
    Painel de Gestão Completa (CRUD) dos registros de consumo da sessão:
    - Create: Adicionar novo consumo manual (com ou sem reserva)
    - Read: Pesquisa em tempo real, visualização tabular ordenada e detalhes
    - Update: Edição de horário e prato
    - Delete: Exclusão com confirmação segura e reversão no banco
    """

    ID_COLUNA_ACAO = "coluna_acao"
    TEXTO_COLUNA_ACAO = "❌"

    def __init__(
        self,
        master: tk.Widget,
        fachada: "FachadaRegistro",
        id_sessao: Optional[int],
        voltar_callback: Optional[Callable[[], None]] = None,
        abrir_controles_callback: Optional[Callable[..., None]] = None,
        navegar_callback: Optional[Callable[[str], None]] = None,
        notificar_mudanca_callback: Optional[Callable[[], None]] = None,
    ):
        super().__init__(master, padding=(14, 12))
        self.fachada = fachada
        self.id_sessao = id_sessao
        self.voltar_callback = voltar_callback
        self.abrir_controles_callback = abrir_controles_callback
        self.navegar_callback = navegar_callback
        self.notificar_mudanca_callback = notificar_mudanca_callback

        self._consumos_raw: List[Dict[str, Any]] = []
        self._mapa_iid_para_consumo: Dict[str, Dict[str, Any]] = {}

        self.pack_propagate(False)
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        self._construir_interface()
        self.carregar_consumos()

    def _construir_interface(self):
        """Constrói a barra de ferramentas CRUD, campo de busca e a tabela de registros."""
        # --- Linha 0: Barra Superior de Navegação ---
        frame_topo = ttk.Frame(self)
        frame_topo.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        frame_topo.columnconfigure(1, weight=1)

        frame_nav_esq = ttk.Frame(frame_topo)
        frame_nav_esq.grid(row=0, column=0, sticky="w")

        if self.voltar_callback:
            ttk.Button(
                frame_nav_esq,
                text=" ⬅ Voltar ao Totem ",
                command=self.voltar_callback,
                bootstyle="primary",
                padding=(10, 6),
            ).pack(side=LEFT, padx=(0, 6))

        if self.navegar_callback:
            ttk.Button(
                frame_nav_esq,
                text=" 📊 Ver Dashboard & Estatísticas ",
                command=lambda: self.navegar_callback("dashboard"),
                bootstyle="info-outline",
                padding=(10, 6),
            ).pack(side=LEFT)

        frame_titulo = ttk.Frame(frame_topo)
        frame_titulo.grid(row=0, column=1, sticky="ew")

        ttk.Label(
            frame_titulo,
            text="📋 Gestão de Registros de Consumo",
            font=("Segoe UI", 18, "bold"),
            anchor="center",
        ).pack(side=LEFT, expand=True)

        self.lbl_badge_total = ttk.Label(
            frame_titulo,
            text="0 registros",
            font=("Segoe UI", 9, "bold"),
            bootstyle="secondary",
        )
        self.lbl_badge_total.pack(side=LEFT, padx=(4, 0))

        frame_nav_dir = ttk.Frame(frame_topo)
        frame_nav_dir.grid(row=0, column=2, sticky="e")

        ttk.Button(
            frame_nav_dir,
            text=" 🔄 Atualizar ",
            command=self.carregar_consumos,
            bootstyle="secondary-outline",
            padding=(8, 6),
        ).pack(side=LEFT, padx=(0, 6))

        if self.abrir_controles_callback:
            btn_ctrl = ttk.Button(
                frame_nav_dir,
                text=" ⚙️ Controles ",
                bootstyle="secondary",
                padding=(8, 6),
            )
            btn_ctrl.config(
                command=lambda b=btn_ctrl: self.abrir_controles_callback(widget=b)
            )
            btn_ctrl.pack(side=LEFT)

        # --- Linha 1: Barra de Ações CRUD e Filtro de Pesquisa ---
        frame_toolbar = ttk.Frame(self)
        frame_toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        frame_toolbar.columnconfigure(1, weight=1)

        # Botões de Ação CRUD
        frame_acoes = ttk.Frame(frame_toolbar)
        frame_acoes.grid(row=0, column=0, sticky="w")

        ttk.Button(
            frame_acoes,
            text=" ➕ Novo Registro ",
            command=self.novo_registro,
            bootstyle="success",
            padding=(10, 6),
        ).pack(side=LEFT, padx=(0, 6))

        ttk.Button(
            frame_acoes,
            text=" ✏️ Editar ",
            command=self.editar_registro,
            bootstyle="primary-outline",
            padding=(8, 6),
        ).pack(side=LEFT, padx=(0, 6))

        ttk.Button(
            frame_acoes,
            text=" 🗑️ Excluir ",
            command=self.excluir_registro,
            bootstyle="danger-outline",
            padding=(8, 6),
        ).pack(side=LEFT, padx=(0, 6))

        ttk.Button(
            frame_acoes,
            text=" 🔍 Detalhes ",
            command=self.exibir_detalhes,
            bootstyle="info-outline",
            padding=(8, 6),
        ).pack(side=LEFT, padx=(0, 6))

        ttk.Button(
            frame_acoes,
            text=" 📥 Exportar XLSX ",
            command=self.exportar_xlsx,
            bootstyle="secondary-outline",
            padding=(8, 6),
        ).pack(side=LEFT)

        # Campo de Pesquisa em Tempo Real
        frame_busca = ttk.Frame(frame_toolbar)
        frame_busca.grid(row=0, column=1, sticky="e")

        ttk.Label(frame_busca, text="🔍", font=("Segoe UI", 11)).pack(
            side=LEFT, padx=(0, 4)
        )
        self.var_busca = tk.StringVar()
        self.var_busca.trace_add("write", lambda *_: self._ao_digitar_busca())
        self.entry_busca = ttk.Entry(
            frame_busca,
            textvariable=self.var_busca,
            width=28,
            font=("Segoe UI", 9),
        )
        self.entry_busca.pack(side=LEFT, padx=(0, 6))

        self.var_filtro_tipo = tk.StringVar(value="Todos")
        combo_filtro = ttk.Combobox(
            frame_busca,
            textvariable=self.var_filtro_tipo,
            values=["Todos", "Com Reserva", "Sem Reserva"],
            state="readonly",
            width=14,
            font=("Segoe UI", 9),
        )
        combo_filtro.pack(side=LEFT)
        combo_filtro.bind("<<ComboboxSelected>>", lambda _: self._ao_digitar_busca())

        # --- Linha 2: Tabela de Registros de Consumo (Treeview) ---
        colunas = [
            {"text": "🆔 Prontuário", "iid": "pront", "width": 110, "minwidth": 80},
            {"text": "👤 Nome", "iid": "nome", "width": 280, "stretch": True, "minwidth": 150},
            {"text": "👥 Turma", "iid": "turma", "width": 170, "minwidth": 100},
            {"text": "⏱️ Hora", "iid": "hora", "width": 90, "anchor": CENTER, "minwidth": 70},
            {"text": "🍽️ Prato / Status", "iid": "prato", "width": 140, "minwidth": 90},
            {
                "text": self.TEXTO_COLUNA_ACAO,
                "iid": self.ID_COLUNA_ACAO,
                "width": 45,
                "anchor": CENTER,
                "stretch": False,
            },
        ]
        self.tree = TreeviewSimples(
            self,
            dados_colunas=colunas,
            height=20,
            enable_hover=True,
            enable_sorting=True,
        )
        self.tree.frame.grid(row=2, column=0, sticky="nsew")

        # Vinculações de Eventos na Tabela
        self.tree.view.bind("<Button-1>", self._ao_clicar_tabela)
        self.tree.view.bind("<Double-1>", self._ao_duplo_clique)
        self.tree.view.bind("<Delete>", lambda _: self.excluir_registro())
        self.tree.view.bind("<BackSpace>", lambda _: self.excluir_registro())
        self.tree.view.bind("<Button-3>", self._ao_menu_contexto)

    def definir_sessao(self, id_sessao: Optional[int]):
        """Atualiza a sessão ativa e recarrega a tabela de consumos."""
        self.id_sessao = id_sessao
        self.carregar_consumos()

    def carregar_consumos(self):
        """Carrega a lista completa de estudantes que consumiram na sessão ativa."""
        if not self.id_sessao or not self.fachada or not self.fachada.id_sessao_ativa:
            self._consumos_raw = []
            self._mapa_iid_para_consumo.clear()
            self.tree.construir_dados_tabela([])
            self.lbl_badge_total.config(text="0 registros")
            return

        try:
            consumidos = self.fachada.obter_estudantes_para_sessao(
                consumido=True, pular_grupos=True
            )
            consumidos.sort(
                key=lambda x: str(x.get("hora_consumo", "")), reverse=True
            )
            self._consumos_raw = consumidos
            self._aplicar_filtro_e_renderizar()
        except Exception as e:
            logger.error("Erro ao carregar consumos no painel CRUD: %s", e)

    def _aplicar_filtro_e_renderizar(self):
        """Filtra a lista de consumos em memória e atualiza as linhas da Treeview."""
        termo = self.var_busca.get().strip().lower()
        filtro_tipo = self.var_filtro_tipo.get()

        self._mapa_iid_para_consumo.clear()
        self.tree.deletar_linhas()

        total_filtrados = 0
        for c in self._consumos_raw:
            pront = str(c.get("pront", ""))
            nome = str(c.get("nome", ""))
            turma = str(c.get("turma", ""))
            hora = str(c.get("hora_consumo", ""))
            prato = str(c.get("prato") or "Sem Reserva")

            if filtro_tipo == "Com Reserva" and (
                prato == "Sem Reserva" or c.get("status") == "Sem Reserva"
            ):
                continue
            if filtro_tipo == "Sem Reserva" and not (
                prato == "Sem Reserva" or c.get("status") == "Sem Reserva"
            ):
                continue

            if termo:
                if (
                    termo not in pront.lower()
                    and termo not in nome.lower()
                    and termo not in turma.lower()
                    and termo not in prato.lower()
                ):
                    continue

            valores = (pront, nome, turma, hora, prato, self.TEXTO_COLUNA_ACAO)
            iid = self.tree.view.insert("", "end", values=valores)
            self._mapa_iid_para_consumo[iid] = c
            total_filtrados += 1

        self.tree.apply_zebra_striping()
        total_total = len(self._consumos_raw)
        if total_filtrados == total_total:
            self.lbl_badge_total.config(text=f"{total_total} registros")
        else:
            self.lbl_badge_total.config(
                text=f"{total_filtrados} de {total_total} registros"
            )

    def _ao_digitar_busca(self):
        self._aplicar_filtro_e_renderizar()

    def adicionar_consumo(self, dados_estudante: Tuple[str, ...]):
        """Adiciona imediatamente uma nova linha no topo da tabela de consumos."""
        if len(dados_estudante) >= 5:
            valores = tuple(dados_estudante[:5]) + (self.TEXTO_COLUNA_ACAO,)
        else:
            valores = dados_estudante
        iid = self.tree.view.insert("", 0, values=valores)
        self.tree.apply_zebra_striping()

        # Insere no cache
        novo_dict = {
            "pront": dados_estudante[0] if len(dados_estudante) > 0 else "",
            "nome": dados_estudante[1] if len(dados_estudante) > 1 else "",
            "turma": dados_estudante[2] if len(dados_estudante) > 2 else "",
            "hora_consumo": dados_estudante[3] if len(dados_estudante) > 3 else "",
            "prato": dados_estudante[4] if len(dados_estudante) > 4 else "Almoço",
        }
        self._consumos_raw.insert(0, novo_dict)
        self._mapa_iid_para_consumo[iid] = novo_dict
        self.lbl_badge_total.config(text=f"{len(self._consumos_raw)} registros")

    # --- Operações CRUD ---

    def novo_registro(self):
        """[Create] Abre o diálogo para registrar um novo consumo manualmente."""
        if not self.id_sessao or not self.fachada or not self.fachada.id_sessao_ativa:
            Messagebox.show_warning(
                "Aviso", "Inicie ou selecione uma sessão antes de registrar.", parent=self
            )
            return

        def _ao_sucesso(_res):
            self.carregar_consumos()
            self._notificar_mudanca()

        DialogoNovoConsumo(self, self.fachada, on_sucesso=_ao_sucesso)

    def editar_registro(self, iid: Optional[str] = None):
        """[Update] Abre o diálogo de edição para o registro selecionado."""
        alvo_iid = iid or self.tree.obter_iid_selecionado()
        if not alvo_iid:
            Messagebox.show_warning(
                "Atenção", "Selecione um registro na tabela para editar.", parent=self
            )
            return

        dados = self._obter_dados_de_iid(alvo_iid)
        if not dados:
            return

        id_consumo = dados.get("id_consumo")
        if not id_consumo:
            # Tenta localizar o id_consumo pelo prontuario e sessão
            try:
                c_db = self.fachada.repo_consumo.por_prontuario_e_sessao(
                    dados["pront"], self.id_sessao
                )
                if c_db:
                    id_consumo = c_db.id
            except Exception as e:
                logger.error("Erro ao buscar id_consumo: %s", e)

        if not id_consumo:
            Messagebox.show_error(
                "Erro", "Não foi possível localizar o ID do consumo para edição.", parent=self
            )
            return

        def _ao_sucesso(_res):
            self.carregar_consumos()
            self._notificar_mudanca()

        DialogoEditarConsumo(
            self, self.fachada, id_consumo=id_consumo, dados_consumo=dados, on_sucesso=_ao_sucesso
        )

    def excluir_registro(self, iid: Optional[str] = None):
        """[Delete] Solicita confirmação e remove o registro de consumo."""
        alvo_iid = iid or self.tree.obter_iid_selecionado()
        if not alvo_iid:
            Messagebox.show_warning(
                "Atenção", "Selecione um registro na tabela para excluir.", parent=self
            )
            return

        dados = self._obter_dados_de_iid(alvo_iid)
        if not dados:
            return

        pront = dados.get("pront", "")
        nome = dados.get("nome", "")

        msg = f"Deseja realmente remover o registro de consumo para:\n{pront} - {nome}?"
        resp = Messagebox.yesno(
            "Confirmar Remoção de Consumo", msg, icon="warning", parent=self
        )
        if resp == MessageCatalog.translate("Yes"):
            try:
                id_consumo = dados.get("id_consumo")
                if id_consumo:
                    self.fachada.desfazer_consumo(id_consumo)
                else:
                    self.fachada.desfazer_consumo_por_prontuario(pront)

                logger.info("Consumo de %s removido com sucesso.", pront)
                self.carregar_consumos()
                self._notificar_mudanca()
                Messagebox.show_info(
                    "Removido", f"Registro de {nome} removido com sucesso.", parent=self
                )
            except Exception as e:
                logger.exception("Erro ao excluir consumo: %s", e)
                Messagebox.show_error(
                    "Erro ao Excluir", f"Não foi possível remover:\n{e}", parent=self
                )

    def exibir_detalhes(self, iid: Optional[str] = None):
        """[Read] Exibe os detalhes completos do atendimento selecionado."""
        alvo_iid = iid or self.tree.obter_iid_selecionado()
        if not alvo_iid:
            Messagebox.show_warning(
                "Atenção", "Selecione um registro para ver os detalhes.", parent=self
            )
            return

        dados = self._obter_dados_de_iid(alvo_iid)
        if not dados:
            return

        DialogoDetalhesConsumo(
            self,
            dados_consumo=dados,
            on_editar=lambda: self.editar_registro(alvo_iid),
            on_excluir=lambda: self.excluir_registro(alvo_iid),
        )

    def exportar_xlsx(self):
        """Exporta os registros de consumo atuais para XLSX."""
        if not self.id_sessao or not self.fachada:
            Messagebox.show_warning("Aviso", "Nenhuma sessão ativa para exportar.", parent=self)
            return

        try:
            caminho = self.fachada.exportar_sessao_para_xlsx(self.id_sessao)
            Messagebox.show_info(
                "Exportação Concluída",
                f"Consumos exportados com sucesso para:\n{caminho}",
                parent=self,
            )
        except Exception as e:
            logger.exception("Erro ao exportar consumos: %s", e)
            Messagebox.show_error("Erro na Exportação", f"Falha ao exportar:\n{e}", parent=self)

    # --- Handlers de Eventos ---

    def _obter_dados_de_iid(self, iid: str) -> Optional[Dict[str, Any]]:
        """Recupera o dicionário de dados associado a um IID da Treeview."""
        if iid in self._mapa_iid_para_consumo:
            return dict(self._mapa_iid_para_consumo[iid])

        # Se não estiver no mapa, extrai diretamente dos valores da linha
        vals = self.tree.obter_valores_linha(iid)
        if vals and len(vals) >= 5:
            return {
                "pront": vals[0],
                "nome": vals[1],
                "turma": vals[2],
                "hora_consumo": vals[3],
                "prato": vals[4],
            }
        return None

    def _ao_clicar_tabela(self, event: tk.Event):
        """Detecta se a coluna de ação ❌ foi clicada diretamente."""
        iid, id_col = self.tree.identificar_celula_clicada(event)
        if iid and id_col == self.ID_COLUNA_ACAO:
            self.excluir_registro(iid)

    def _ao_duplo_clique(self, event: tk.Event):
        """Abre os detalhes/edição ao dar duplo clique em uma linha."""
        iid, id_col = self.tree.identificar_celula_clicada(event)
        if iid and id_col != self.ID_COLUNA_ACAO:
            self.exibir_detalhes(iid)

    def _ao_menu_contexto(self, event: tk.Event):
        """Exibe menu de contexto com clique com o botão direito na linha."""
        iid = self.tree.view.identify_row(event.y)
        if not iid:
            return

        self.tree.view.selection_set(iid)
        menu = tk.Menu(self, tearoff=False, font=("Segoe UI", 9))
        menu.add_command(
            label="🔍  Ver Detalhes do Registro",
            command=lambda: self.exibir_detalhes(iid),
        )
        menu.add_command(
            label="✏️  Editar Horário / Prato",
            command=lambda: self.editar_registro(iid),
        )
        menu.add_separator()
        menu.add_command(
            label="🗑️  Excluir Registro",
            command=lambda: self.excluir_registro(iid),
        )
        menu.tk_popup(event.x_root, event.y_root)

    def _notificar_mudanca(self):
        """Notifica o App e demais componentes de que houve alteração nos consumos."""
        if self.notificar_mudanca_callback:
            try:
                self.notificar_mudanca_callback()
            except Exception as e:
                logger.error("Erro no callback de notificação de mudança: %s", e)


class AppSelfService(ttk.Window):
    """
    Aplicação 100% autônoma de autoatendimento para totens ou terminais dedicados.
    Permite gerenciar sessões e filtros de turma on-the-fly via menu de contexto.
    """

    def __init__(self):
        super().__init__(themename="sandstone", title="🍽️ Totem de Autoatendimento")
        self.geometry("1280x800")
        self.minsize(960, 620)

        try:
            self.fachada_nucleo = FachadaRegistro()
        except Exception:
            Messagebox.show_error(
                "Erro Fatal", "Não foi possível iniciar o backend. Verifique o console."
            )
            traceback.print_exc()
            self.destroy()
            return

        self.id_sessao_ativa: Optional[int] = None
        self._fullscreen: bool = False
        self.selected_frame_name: str = ""
        self.frames: Dict[str, ttk.Frame] = {}

        # Identificação e Inicialização de Sessão
        self._detectar_e_carregar_sessao_inicial()

        self._criar_widgets()
        self._configurar_atalhos_teclado()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Se após a inicialização não houver sessão ativa, abre o diálogo de sessão
        if not self.id_sessao_ativa:
            self.after(300, self._abrir_dialogo_sessao)

    def get_fachada(self) -> FachadaRegistro:
        """Compatibilidade para componentes que requisitam a fachada."""
        return self.fachada_nucleo

    def mostrar_barra_progresso(self, iniciar: bool, texto: Optional[str] = None):
        """Suporte a diálogos que notificam progresso."""
        pass

    def _configurar_atalhos_teclado(self):
        """Configura atalhos de tela cheia, menu de contexto e captura inteligente de teclas."""
        self.bind("<F11>", lambda e: self._toggle_fullscreen())
        self.bind("<Escape>", lambda e: self._definir_fullscreen(False))
        self.bind("<F2>", lambda e: self.exibir_menu_contexto())
        self.bind("<Control-m>", lambda e: self.exibir_menu_contexto())
        self.bind_all("<Button-3>", self._ao_clique_botao_direito_global, add="+")

        # Redireciona teclas alfanuméricas para a entrada manual se o foco estiver perdido
        self.bind("<Key>", self._ao_pressionar_tecla_global, add="+")

    def _ao_clique_botao_direito_global(self, event):
        """Exibe o menu de contexto nativo ao clicar com o botão direito em qualquer área."""
        self.exibir_menu_contexto(event=event)

    def _ao_pressionar_tecla_global(self, event):
        """
        Redireciona digitações para o campo do scanner caso o usuário tenha clicado fora.
        Evita que scanners USB de código de barras ou RFID percam a leitura.
        """
        widget = event.widget
        if isinstance(widget, (ttk.Entry, tk.Entry, ttk.Combobox, tk.Text)):
            return

        # Teclas de controle (F1-F12, Escape, Alt, Tab, etc.) não são redirecionadas
        if event.keysym in (
            "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
            "Escape", "Alt_L", "Alt_R", "Control_L", "Control_R", "Shift_L", "Shift_R", "Tab"
        ):
            return

        if "selfservice" in self.frames and hasattr(self.frames["selfservice"], "_entrada_manual"):
            frame_ss = self.frames["selfservice"]
            if hasattr(frame_ss, "focar_entrada"):
                frame_ss.focar_entrada()
                if event.char and event.char.isprintable():
                    frame_ss._entrada_manual.insert(tk.END, event.char)

    def _toggle_fullscreen(self):
        """Alterna entre tela cheia e modo janela."""
        self._definir_fullscreen(not self._fullscreen)

    def _definir_fullscreen(self, ativo: bool):
        """Define o estado de tela cheia."""
        self._fullscreen = ativo
        self.attributes("-fullscreen", self._fullscreen)

    def _detectar_e_carregar_sessao_inicial(self):
        """
        Detecta sessão ativa persistida ou seleciona automaticamente a sessão mais
        recente de hoje, garantindo inicialização autônoma sem cliques desnecessários.
        """
        try:
            # 1. Tenta carregar sessão salva em session.json
            self.fachada_nucleo.carregar_estado_sessao()
            if self.fachada_nucleo.id_sessao_ativa:
                self.id_sessao_ativa = self.fachada_nucleo.id_sessao_ativa
                logger.info("Sessão persistida carregada: ID %s", self.id_sessao_ativa)
                return

            # 2. Se não houver, busca se existe sessão criada para a data de hoje
            hoje_str = dt.date.today().strftime("%d/%m/%Y")
            sessoes = self.fachada_nucleo.listar_todas_sessoes()
            sessoes_hoje = [s for s in sessoes if s.get("data") == hoje_str]
            if sessoes_hoje:
                sessoes_hoje.sort(key=lambda s: s.get("hora", ""), reverse=True)
                sessao_recente = sessoes_hoje[0]
                self.fachada_nucleo.definir_sessao_ativa(sessao_recente["id"])
                self.fachada_nucleo.salvar_estado_sessao(sessao_recente["id"])
                self.id_sessao_ativa = sessao_recente["id"]
                logger.info(
                    "Sessão de hoje detectada automaticamente: ID %s", self.id_sessao_ativa
                )
        except Exception as e:
            logger.error("Erro na detecção inicial de sessão: %s", e)

    def exibir_menu_contexto(
        self,
        *args,
        widget: Optional[tk.Widget] = None,
        event: Optional[Any] = None,
        **kwargs,
    ):
        """Exibe o menu de contexto nativo com os controles do operador."""
        if args:
            if isinstance(args[0], tk.Event):
                event = args[0]
            elif isinstance(args[0], tk.Widget):
                widget = args[0]

        menu = tk.Menu(self, tearoff=False, font=("Segoe UI", 10))

        # Modos de Visualização
        menu.add_command(
            label="📷  Autoatendimento (Totem)",
            command=lambda: self.show_frame("selfservice"),
        )
        menu.add_command(
            label="📊  Dashboard da Sessão",
            command=lambda: self.show_frame("dashboard"),
        )
        menu.add_command(
            label="📋  Registros de Consumo",
            command=lambda: self.show_frame("consumos"),
        )
        menu.add_separator()

        # Ações de Sessão e Filtros
        menu.add_command(
            label="🔄  Gerenciar / Criar Sessão",
            command=self._abrir_dialogo_sessao,
        )
        menu.add_command(
            label="🎯  Filtros de Turmas e Exceções",
            command=self._abrir_dialogo_filtro_turmas,
        )
        menu.add_separator()

        # Sistema
        label_fs = (
            "🗗  Janela Normal" if self._fullscreen else "⛶  Tela Cheia (F11)"
        )
        menu.add_command(
            label=label_fs,
            command=self._toggle_fullscreen,
        )
        menu.add_command(
            label="❌  Sair do Totem",
            command=self._on_closing,
        )

        # Determina a posição de exibição do menu de contexto
        if event and hasattr(event, "x_root") and hasattr(event, "y_root"):
            x, y = event.x_root, event.y_root
        elif widget:
            try:
                widget.update_idletasks()
                if widget.winfo_rooty() > self.winfo_screenheight() // 2:
                    x = widget.winfo_rootx()
                    y = max(10, widget.winfo_rooty() - 250)
                else:
                    x = widget.winfo_rootx()
                    y = widget.winfo_rooty() + widget.winfo_height() + 2
            except Exception:
                x = widget.winfo_rootx()
                y = widget.winfo_rooty()
        else:
            x = self.winfo_rootx() + 30
            y = max(10, self.winfo_rooty() + self.winfo_height() - 260)

        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _criar_widgets(self):
        """Constrói a interface limpa sem barras laterais, com tela cheia para o totem e controles via menu de contexto."""
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.content_frame = ttk.Frame(self, padding=0)
        self.content_frame.grid(row=0, column=0, sticky=NSEW)
        self.content_frame.rowconfigure(0, weight=1)
        self.content_frame.columnconfigure(0, weight=1)

        # Criação das Abas
        self.frames["selfservice"] = FrameSelfService(
            self.content_frame,
            self.fachada_nucleo,
            self.notificar_sucesso_registro,
            abrir_controles_callback=self.exibir_menu_contexto,
        )
        self.frames["dashboard"] = AbaDashboard(
            self.content_frame,
            self.fachada_nucleo,
            self.id_sessao_ativa,
            voltar_callback=lambda: self.show_frame("selfservice"),
            abrir_controles_callback=self.exibir_menu_contexto,
            navegar_callback=self.show_frame,
        )
        self.frames["consumos"] = AbaConsumos(
            self.content_frame,
            self.fachada_nucleo,
            self.id_sessao_ativa,
            voltar_callback=lambda: self.show_frame("selfservice"),
            abrir_controles_callback=self.exibir_menu_contexto,
            navegar_callback=self.show_frame,
            notificar_mudanca_callback=self._ao_alterar_consumo,
        )

        self.show_frame("selfservice")

    def _ao_alterar_consumo(self):
        """Notificação de que registros foram adicionados, editados ou excluídos."""
        self._atualizar_barra_sessao()

    def show_frame(self, nome_pagina: str):
        """Alterna a página em exibição."""
        if self.selected_frame_name == nome_pagina:
            return

        if self.selected_frame_name and self.selected_frame_name in self.frames:
            self.frames[self.selected_frame_name].grid_remove()

        self.selected_frame_name = nome_pagina
        frame_ativo = self.frames[nome_pagina]
        frame_ativo.grid(row=0, column=0, sticky=NSEW)

        if nome_pagina == "selfservice" and hasattr(frame_ativo, "focar_entrada"):
            frame_ativo.focar_entrada()

    def _abrir_dialogo_sessao(self):
        """Abre o diálogo de gerenciamento completo de sessões (criar nova ou carregar existente)."""
        logger.info("Abrindo gerenciamento de sessão on-the-fly.")
        DialogoSessao(
            title="Gerenciar Sessão de Refeição",
            callback=self.tratar_resultado_dialogo_sessao,
            parente_app=self,
        )

    def tratar_resultado_dialogo_sessao(
        self, resultado: Union[Dict[str, Any], int, None]
    ) -> bool:
        """Trata a escolha de carregar ou criar sessão vinda do DialogoSessao."""
        if resultado is None:
            logger.info("Diálogo de sessão fechado sem alteração.")
            return True

        sucesso = False
        desc_acao = ""
        try:
            if isinstance(resultado, int):
                id_sessao = resultado
                desc_acao = f"carregar sessão ID: {id_sessao}"
                self.fachada_nucleo.definir_sessao_ativa(id_sessao)
                self.fachada_nucleo.salvar_estado_sessao(id_sessao)
                sucesso = True
            elif isinstance(resultado, dict):
                desc_acao = f"criar nova sessão: {resultado.get('refeicao')}"
                id_sessao = self.fachada_nucleo.iniciar_nova_sessao(resultado)
                if id_sessao is None:
                    Messagebox.show_warning(
                        "Sessão Vazia",
                        "Não foi possível iniciar a sessão sem reservas ativas.",
                        parent=self,
                    )
                    return False
                self.fachada_nucleo.salvar_estado_sessao(id_sessao)
                sucesso = True
        except Exception as e:
            logger.exception("Falha ao %s: %s", desc_acao, e)
            Messagebox.show_error(
                "Falha na Sessão",
                f"Não foi possível {desc_acao}.\nErro: {e}",
                parent=self,
            )
            return False

        if sucesso:
            self.id_sessao_ativa = self.fachada_nucleo.id_sessao_ativa
            logger.info("Sessão ativada com sucesso: ID %s", self.id_sessao_ativa)
            self._atualizar_apos_mudanca_sessao()
        return sucesso

    def _abrir_dialogo_filtro_turmas(self):
        """Abre o diálogo de filtros de turma on-the-fly."""
        if not self.fachada_nucleo or self.fachada_nucleo.id_sessao_ativa is None:
            Messagebox.show_warning(
                "Nenhuma Sessão Ativa",
                "É necessário iniciar ou selecionar uma sessão antes de ajustar os filtros.",
                parent=self,
            )
            return

        logger.info("Abrindo diálogo de filtros de turma.")
        DialogoFiltroTurmas(
            parent=self,
            fachada_nucleo=self.fachada_nucleo,
            callback_aplicar=self.ao_aplicar_filtro_turmas,
        )

    def ao_aplicar_filtro_turmas(self, identificadores: List[str]):
        """Aplica os novos filtros de turmas e exceções em tempo real."""
        logger.info("Aplicando filtros de turmas on-the-fly: %s", identificadores)
        try:
            grupos_normais = [
                ident for ident in identificadores if not ident.startswith("#")
            ]
            grupos_excecao = {
                ident.lstrip("#") for ident in identificadores if ident.startswith("#")
            }

            self.fachada_nucleo.atualizar_grupos_sessao_ativa(grupos_normais)
            self.fachada_nucleo.excecao_grupos = grupos_excecao

            self._atualizar_barra_sessao()
            if "dashboard" in self.frames:
                self.frames["dashboard"].atualizar_dados()

            Messagebox.show_info(
                "Filtros Atualizados",
                "Os filtros de turma e exceções foram aplicados com sucesso à sessão ativa.",
                parent=self,
            )
        except Exception as e:
            logger.exception("Erro ao aplicar filtros de turma: %s", e)
            Messagebox.show_error(
                "Erro ao Filtrar", f"Não foi possível aplicar filtros:\n{e}", parent=self
            )

    def _atualizar_apos_mudanca_sessao(self):
        """Propaga a nova sessão ativa para todos os frames e atualiza o cabeçalho."""
        self._atualizar_barra_sessao()

        if "selfservice" in self.frames:
            self.frames["selfservice"].recarregar_sessao()

        if "dashboard" in self.frames:
            self.frames["dashboard"].definir_sessao(self.id_sessao_ativa)

        if "consumos" in self.frames:
            self.frames["consumos"].definir_sessao(self.id_sessao_ativa)

    def _atualizar_barra_sessao(self):
        """Atualiza a exibição da sessão ativa em todos os componentes."""
        if "selfservice" in self.frames:
            self.frames["selfservice"].recarregar_sessao()
        if "dashboard" in self.frames:
            self.frames["dashboard"].atualizar_dados()
        if "consumos" in self.frames:
            self.frames["consumos"].carregar_consumos()

    def notificar_sucesso_registro(self, dados_estudante: Tuple[str, ...]):
        """Notificação de registro executado com sucesso."""
        if "consumos" in self.frames:
            self.frames["consumos"].adicionar_consumo(dados_estudante)
        if "dashboard" in self.frames:
            self.frames["dashboard"].atualizar_dados(ultimo_consumo=dados_estudante)

    def _on_closing(self):
        """Encerramento seguro de recursos."""
        logger.info("Encerrando aplicação de autoatendimento...")
        if "selfservice" in self.frames:
            self.frames["selfservice"].stop()
        try:
            self.fachada_nucleo.fechar_conexao()
        except Exception as e:
            logger.warning("Erro ao fechar conexão com DB: %s", e)
        self.destroy()


def main():
    """Ponto de entrada para a aplicação autônoma de autoatendimento."""
    log_format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_format)
    logging.getLogger().setLevel(logging.INFO)

    try:
        app = AppSelfService()
        app.mainloop()
    except Exception:
        logger.critical("Erro fatal ao iniciar a aplicação de autoatendimento.")
        logger.critical(traceback.format_exc())
        Messagebox.show_error(
            "Erro Crítico",
            "A aplicação encontrou um erro irrecuperável e será fechada. "
            "Verifique os logs para mais detalhes.",
        )


if __name__ == "__main__":
    main()
