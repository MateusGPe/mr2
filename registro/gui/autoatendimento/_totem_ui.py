# ----------------------------------------------------------------------------
# Arquivo: registro/gui/autoatendimento/_totem_ui.py (UI e Feedback do Totem)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""Mixin de construção de interface e feedback visual do FrameSelfService."""

import logging
import sys
import tkinter as tk
from typing import Any

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, CENTER, EW, NSEW, X

logger = logging.getLogger(__name__)


class _TotemUIMixin:
    """Constrói os painéis do totem e aplica o tema visual de feedback."""

    COR_FUNDO_PADRAO: str
    COR_FUNDO_SUCESSO: str
    COR_FUNDO_ERRO: str
    COR_TEXTO: str

    def _criar_interface(self: Any):
        """Cria os widgets da interface moderna com 50/50 e painel direito ocupando 100% da altura."""
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1, minsize=400)
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
            wraplength=400,
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

        # Barra inferior da câmera com botões de controles e consulta de horários
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

        btn_horarios = ttk.Button(
            frame_cam_bottom,
            text=" 🕒 Horários por Turma ",
            bootstyle="info",
            padding=(8, 4),
            command=self._abrir_dialogo_horarios,
        )
        btn_horarios.pack(side="left", padx=(8, 0))

        # Clique com o botão direito para exibir o menu de contexto
        self.bind("<Button-3>", lambda e: self._ao_clicar_controles(event=e))
        self._lbl_video.bind("<Button-3>", lambda e: self._ao_clicar_controles(event=e))

        # Frame de Informações e Feedback (Direita) - Ocupa 100% da altura
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
            wraplength=400,
        )
        self._lbl_titulo_cabecalho.pack(fill=X)

        self._lbl_refeicao_ativa = tk.Label(
            self._frame_cabecalho,
            text="Carregando sessão...",
            font=("Segoe UI", 13),
            bg=self.COR_FUNDO_PADRAO,
            fg="#9CA3AF",
            anchor="center",
            cursor="hand2",
        )
        self._lbl_refeicao_ativa.pack(fill=X, pady=(4, 0))
        self._lbl_refeicao_ativa.bind(
            "<Button-1>", lambda _e: self._abrir_dialogo_horarios()
        )

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
            wraplength=400,
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
            wraplength=400,
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
            wraplength=400,
        )
        self._lbl_turma.pack(fill=X, pady=2)

        self._lbl_prato = tk.Label(
            self._frame_estudante,
            text="",
            font=("Segoe UI", 16, "italic"),
            bg=self.COR_FUNDO_PADRAO,
            fg="#93C5FD",
            anchor="center",
            wraplength=400,
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
            wraplength=400,
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
        self._var_entrada_manual.trace_add("write", self._na_mudanca_entrada_manual)

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

    def _exibir_erro_dependencia(self: Any):
        dica_so = (
            " (No Linux: sudo apt install libzbar0)" if sys.platform != "win32" else ""
        )
        msg = (
            f"Bibliotecas 'opencv-python' e/ou 'pyzbar' não encontradas{dica_so}.\n"
            "Instale-as para usar o recurso de câmera."
        )
        self._lbl_video.config(text=msg, bootstyle="danger")
        logger.error(msg)

    def _definir_feedback_visual(self: Any, estado: str):
        """Altera as cores do painel de informações para feedback visual."""
        self._ultimo_estado_feedback = estado
        temas = {
            "sucesso": {
                "bg": self.COR_FUNDO_SUCESSO,
                "status": "REGISTRADO COM SUCESSO!",
                "titulo": "#FFFFFF",
                "refeicao": "#D1FAE5",
                "fg_status": "#FFFFFF",
                "nome": "#FFFFFF",
                "turma": "#D1FAE5",
                "prato": "#FEF08A",
                "mensagem": "#D1FAE5",
                "contador": "#A7F3D0",
                "manual_titulo": "#A7F3D0",
                "sugestao": "#D1FAE5",
                "separador": "#047857",
            },
            "erro": {
                "bg": self.COR_FUNDO_ERRO,
                "status": "ATENÇÃO: NÃO AUTORIZADO",
                "titulo": "#FFFFFF",
                "refeicao": "#FEE2E2",
                "fg_status": "#FFFFFF",
                "nome": "#FFFFFF",
                "turma": "#FECACA",
                "prato": "#FEE2E2",
                "mensagem": "#FEF08A",
                "contador": "#FCA5A5",
                "manual_titulo": "#FCA5A5",
                "sugestao": "#FECACA",
                "separador": "#B91C1C",
            },
        }
        t = temas.get(
            estado,
            {
                "bg": self.COR_FUNDO_PADRAO,
                "status": "Aguardando Leitura...",
                "titulo": "#FFFFFF",
                "refeicao": "#9CA3AF",
                "fg_status": "#FFFFFF",
                "nome": "#FFFFFF",
                "turma": "#E5E7EB",
                "prato": "#93C5FD",
                "mensagem": "#FCA5A5",
                "contador": "#9CA3AF",
                "manual_titulo": "#D1D5DB",
                "sugestao": "#9CA3AF",
                "separador": "#374151",
            },
        )
        cor_bg = t["bg"]

        if self._frame_info:
            self._frame_info.config(bg=cor_bg)
        if self._frame_cabecalho:
            self._frame_cabecalho.config(bg=cor_bg)
        if self._lbl_titulo_cabecalho:
            self._lbl_titulo_cabecalho.config(bg=cor_bg, fg=t["titulo"])
        if self._lbl_refeicao_ativa:
            self._lbl_refeicao_ativa.config(bg=cor_bg, fg=t["refeicao"])
        if self._separador:
            self._separador.config(bg=t["separador"])
        if self._lbl_status:
            self._lbl_status.config(bg=cor_bg, fg=t["fg_status"], text=t["status"])
        if self._frame_estudante:
            self._frame_estudante.config(bg=cor_bg)
        if self._lbl_nome:
            self._lbl_nome.config(bg=cor_bg, fg=t["nome"])
        if self._lbl_turma:
            self._lbl_turma.config(bg=cor_bg, fg=t["turma"])
        if self._lbl_prato:
            self._lbl_prato.config(bg=cor_bg, fg=t["prato"])
        if self._lbl_mensagem:
            self._lbl_mensagem.config(bg=cor_bg, fg=t["mensagem"])
        if self._lbl_contador_sessao:
            self._lbl_contador_sessao.config(bg=cor_bg, fg=t["contador"])
        if self._frame_manual:
            self._frame_manual.config(bg=cor_bg, fg=t["manual_titulo"])
        if self._lbl_sugestao_manual:
            self._lbl_sugestao_manual.config(bg=cor_bg, fg=t["sugestao"])
