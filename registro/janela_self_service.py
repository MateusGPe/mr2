# ----------------------------------------------------------------------------
# Arquivo: registro/gui/janela_self_service.py (Janela de Autoatendimento)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

import logging
import tkinter as tk
import traceback
import re
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple

from fuzzywuzzy import fuzz
import ttkbootstrap as ttk
from PIL import Image, ImageTk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.constants import CENTER, LEFT, NSEW, RIGHT, X

from registro.controles.treeview_simples import TreeviewSimples
from registro.gui.constants import REGEX_LIMPEZA_PRONTUARIO
from registro.nucleo.facade import FachadaRegistro

if TYPE_CHECKING:
    from registro.gui.app_registro import AppRegistro

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


class FrameSelfService(ttk.Frame):
    """
    Frame dedicado ao autoatendimento via leitura de QR Code pela webcam.
    """

    def __init__(
        self,
        master: tk.Widget,
        fachada: "FachadaRegistro",
        notification_callback: Callable[[Tuple[str, ...]], None],
    ):
        super().__init__(master)

        self._fachada = fachada
        self._notification_callback = notification_callback
        assert self._fachada.id_sessao_ativa is not None
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

    def stop(self):
        """Libera recursos, como a câmera."""
        self._running = False
        if self._cap:
            self._cap.release()

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
            font=("Segoe UI", 18),
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
        if not termo_busca or not self._lbl_sugestao_manual:
            return

        melhor_match = self._buscar_melhor_match_por_nome(termo_busca)

        if melhor_match:
            nome = melhor_match.get("nome", "Desconhecido")
            turma = melhor_match.get("turma", "N/A")
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

        sucesso, msg, dados = self._registrar_entrada(codigo)

        if sucesso:
            self._lbl_nome.config(text=dados.get("nome", "Desconhecido"))
            self._lbl_turma.config(text=dados.get("turma", ""))
            self._lbl_mensagem.config(text="")
            self._definir_feedback_visual("sucesso")
            self._tocar_som(sucesso=True)
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

    @staticmethod
    def formatar_matricula(valor):
        """
        Padroniza a matrícula para o formato IQ30XXXXX.
        Tenta extrair os últimos 5 dígitos ou 'X' de um valor de entrada.
        """
        texto = str(valor).upper()
        # Extrai todos os dígitos e 'X' da string
        numeros_e_x = re.findall(r'[0-9X]', texto)
        # Pega os últimos 5 caracteres extraídos
        sufixo = "".join(numeros_e_x)[-5:]
        # Garante que o sufixo tenha 5 caracteres, preenchendo com zeros à esquerda
        sufixo_formatado = sufixo.zfill(5)
        return f"IQ30{sufixo_formatado}"

    def _registrar_entrada(self, texto_entrada: str) -> Tuple[bool, str, Dict[str, Any]]:
        """Processa a entrada e tenta registrar o consumo usando a lógica estrita."""
        try:  # Tenta primeiro com o código como prontuário
            prontuario = FrameSelfService.formatar_matricula(texto_entrada)
            resultado = self._fachada.registrar_consumo(
                prontuario, excecao_grupos=self._fachada.excessao_grupos
            )

            if resultado.get("autorizado"):
                return True, "Sucesso", resultado

            motivo = resultado.get("motivo", "Não autorizado")
            # Se o motivo do erro NÃO for "não encontrado", retorna o erro direto.
            if "não encontrado" not in motivo.lower():
                return False, motivo, resultado

            # Se "Estudante não encontrado", tenta busca por nome
            # como fallback.
            return self._buscar_por_nome_e_registrar(texto_entrada)

        except Exception as e:
            logger.exception("Erro ao processar entrada self-service: %s", e)
            return False, str(e), {"nome": texto_entrada, "turma": "Erro de Sistema"}

    def _buscar_por_nome_e_registrar(
        self, nome_busca: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Busca por nome (fuzzy), e se encontrar um match claro, tenta registrar."""
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
            return False, "Aluno não encontrado", {"nome": nome_busca, "turma": "Não Encontrado"}

        correspondencias.sort(key=lambda x: -x["score"])
        melhor_match = correspondencias[0]

        if len(correspondencias) > 1 and (
            melhor_match["score"] < 98
            or (melhor_match["score"] - correspondencias[1]["score"]) < 10
        ):
            msg = "Múltiplos resultados. Seja mais específico."
            return False, msg, {"nome": nome_busca, "turma": "Busca Ambigua"}

        prontuario_encontrado = melhor_match.get("pront")
        if not prontuario_encontrado:
            return False, "Prontuário não encontrado para o nome.", {"nome": nome_busca, "turma": "Erro Interno"}

        # Usa registrar_consumo com pular_grupos=True para consistência com a busca
        # que também ignora grupos.
        resultado_registro = self._fachada.registrar_consumo(
            prontuario_encontrado, pular_grupos=True
        )
        if resultado_registro.get("autorizado"):
            return True, "Sucesso", resultado_registro

        return False, resultado_registro.get("motivo", "Não autorizado"), resultado_registro

    def _buscar_melhor_match_por_nome(
        self, nome_busca: str
    ) -> Optional[Dict[str, Any]]:
        """Busca por nome e retorna o melhor match como sugestão, sem registrar."""
        if len(nome_busca) < 3:
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
                if score >= 75:  # Limiar mais baixo para sugestões
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
            # Módulo winsound não disponível em sistemas não-Windows.
            logger.debug(
                "Módulo winsound não disponível, sem som de feedback.")
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning("Não foi possível tocar som de feedback: %s", e)


class AbaDashboard(ttk.Frame):
    """Painel com as métricas da sessão de autoatendimento."""

    def __init__(self, master: tk.Widget, fachada: "FachadaRegistro", id_sessao: int):
        super().__init__(master, padding=20)
        self.fachada = fachada
        self.id_sessao = id_sessao

        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="Dashboard da Sessão", font=("Segoe UI", 24, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 20)
        )

        card_total = ttk.Frame(self, bootstyle="primary", padding=20)
        card_total.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        ttk.Label(card_total, text="Consumos Registrados", font=(
            "Segoe UI", 12), bootstyle="inverse-primary").pack()
        self.lbl_total_consumos = ttk.Label(
            card_total, text="0", font=("Segoe UI", 48, "bold"), bootstyle="inverse-primary"
        )
        self.lbl_total_consumos.pack(expand=True)

        card_ultimo = ttk.Frame(self, bootstyle="info", padding=20)
        card_ultimo.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        ttk.Label(card_ultimo, text="Último Registro", font=(
            "Segoe UI", 12), bootstyle="inverse-info").pack()
        self.lbl_ultimo_consumo_nome = ttk.Label(
            card_ultimo, text="--", font=("Segoe UI", 22, "bold"), bootstyle="inverse-info", wraplength=300
        )
        self.lbl_ultimo_consumo_nome.pack(expand=True)
        self.lbl_ultimo_consumo_hora = ttk.Label(
            card_ultimo, text="", font=("Segoe UI", 14), bootstyle="inverse-info"
        )
        self.lbl_ultimo_consumo_hora.pack()

        self.atualizar_dados()

    def atualizar_dados(self, ultimo_consumo: Optional[Tuple[str, ...]] = None):
        """Atualiza os contadores e informações no dashboard."""
        try:
            consumidos = self.fachada.obter_estudantes_para_sessao(
                consumido=True)
            self.lbl_total_consumos.config(text=str(len(consumidos)))

            if ultimo_consumo:
                # (prontuario, nome, turma, hora, prato)
                nome = ultimo_consumo[1]
                hora = ultimo_consumo[3]
                self.lbl_ultimo_consumo_nome.config(text=nome)
                self.lbl_ultimo_consumo_hora.config(text=f"às {hora}")
        except Exception as e:
            logger.error("Erro ao atualizar dashboard: %s", e)


class AbaConsumos(ttk.Frame):
    """Painel com a lista de consumos registrados na sessão."""

    def __init__(self, master: tk.Widget, fachada: "FachadaRegistro", id_sessao: int):
        super().__init__(master)
        self.fachada = fachada
        self.id_sessao = id_sessao

        self.pack_propagate(False)

        colunas = [
            {"text": "Prontuário", "iid": "pront", "width": 120},
            {"text": "Nome", "iid": "nome", "width": 300, "stretch": True},
            {"text": "Turma", "iid": "turma", "width": 200},
            {"text": "Hora", "iid": "hora", "width": 100},
            {"text": "Prato/Item", "iid": "prato", "width": 150},
        ]
        self.tree = TreeviewSimples(self, dados_colunas=colunas, height=20)
        self.tree.pack(fill="both", expand=True)

        self.carregar_consumos()

    def carregar_consumos(self):
        """Carrega a lista inicial de estudantes que já consumiram."""
        try:
            consumidos = self.fachada.obter_estudantes_para_sessao(
                consumido=True)
            consumidos.sort(key=lambda x: x.get(
                "hora_consumo", ""), reverse=True)

            dados_tabela = [
                (c.get("pront"), c.get("nome"), c.get("turma"),
                 c.get("hora_consumo"), c.get("prato"))
                for c in consumidos
            ]
            self.tree.construir_dados_tabela(dados_tabela)
        except Exception as e:
            logger.error("Erro ao carregar consumos: %s", e)

    def adicionar_consumo(self, dados_estudante: Tuple[str, ...]):
        """Adiciona uma nova linha no topo da tabela de consumos."""
        self.tree.view.insert("", 0, values=dados_estudante)
        self.tree.apply_zebra_striping()


class SessionSelectionDialog(tk.Toplevel):
    """Diálogo para seleção da sessão de trabalho."""

    def __init__(self, parent, sessoes: list[dict[str, Any]]):
        super().__init__(parent)
        self.title("Selecionar Sessão")
        self.geometry("450x350")
        self.transient(parent)
        self.grab_set()

        self.selected_id = None
        self.sessoes = sessoes

        label = ttk.Label(
            self, text="Selecione uma sessão para iniciar:", font=("Segoe UI", 12))
        label.pack(pady=10)

        self.listbox = tk.Listbox(self, font=("Segoe UI", 10), height=10)
        self.listbox.pack(pady=5, padx=10, fill="both", expand=True)

        for sessao in self.sessoes:
            texto = f"{sessao['refeicao'].capitalize()} - {sessao['data']} {sessao['hora']}"
            self.listbox.insert(tk.END, texto)

        if self.sessoes:
            self.listbox.selection_set(len(self.sessoes) - 1)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)

        ok_btn = ttk.Button(btn_frame, text="OK",
                            command=self._on_ok, bootstyle="success")
        ok_btn.pack(side="left", padx=5)

        cancel_btn = ttk.Button(
            btn_frame, text="Cancelar", command=self._on_cancel, bootstyle="secondary")
        cancel_btn.pack(side="left", padx=5)

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.listbox.bind("<Double-1>", self._on_ok)

    def _on_ok(self, _=None):
        selection = self.listbox.curselection()
        if selection:
            self.selected_id = self.sessoes[selection[0]]['id']
        self.destroy()

    def _on_cancel(self):
        self.selected_id = None
        self.destroy()


class AppSelfService(ttk.Window):
    """Aplicação de autoatendimento."""

    def __init__(self):
        super().__init__(themename="sandstone", title="📷 Autoatendimento")
        self.geometry("1280x800")
        self.minsize(900, 600)

        try:
            self.fachada_nucleo = FachadaRegistro()
        except Exception:
            Messagebox.show_error(
                "Erro Fatal", "Não foi possível iniciar o backend. Verifique o console.")
            traceback.print_exc()
            self.destroy()
            return

        self.id_sessao_ativa = self._selecionar_sessao()
        if not self.id_sessao_ativa:
            self.after(100, self.destroy)
            return

        self.fachada_nucleo.id_sessao_ativa = self.id_sessao_ativa

        self.selected_frame_name: str = ""
        self.buttons: Dict[str, ttk.Button] = {}
        self.frames: Dict[str, ttk.Frame] = {}

        self._criar_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _selecionar_sessao(self) -> Optional[int]:
        sessoes = self.fachada_nucleo.listar_todas_sessoes()
        if not sessoes:
            Messagebox.show_warning(
                "Nenhuma Sessão", "Nenhuma sessão de refeição foi encontrada no banco de dados.")
            return None

        dialog = SessionSelectionDialog(self, sessoes)
        self.wait_window(dialog)
        return dialog.selected_id

    def _criar_widgets(self):
        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        navigation_frame = ttk.Frame(
            self, bootstyle="dark", padding=(5, 5, 5, 5))
        navigation_frame.grid(row=0, column=0, sticky=NSEW)
        navigation_frame.rowconfigure(4, weight=1)

        self.content_frame = ttk.Frame(self, padding=0)
        self.content_frame.grid(row=0, column=1, sticky=NSEW)
        self.content_frame.rowconfigure(0, weight=1)
        self.content_frame.columnconfigure(0, weight=1)

        self.frames["selfservice"] = FrameSelfService(
            self.content_frame, self.fachada_nucleo, self.notificar_sucesso_registro)
        self.frames["dashboard"] = AbaDashboard(
            self.content_frame, self.fachada_nucleo, self.id_sessao_ativa)
        self.frames["consumos"] = AbaConsumos(
            self.content_frame, self.fachada_nucleo, self.id_sessao_ativa)

        paginas = {
            "selfservice": ("📷", "Câmera"),
            "dashboard": ("📊", "Dashboard"),
            "consumos": ("📋", "Registros"),
        }

        for i, (nome, (icone, texto)) in enumerate(paginas.items()):
            btn = ttk.Button(
                navigation_frame,
                text=f" {icone} {texto}",
                command=lambda n=nome: self.show_frame(n),
                bootstyle="dark",
                padding=(10, 10),
            )
            btn.grid(row=i, column=0, sticky="EW", pady=(0, 5))
            self.buttons[nome] = btn

        btn_sair = ttk.Button(
            navigation_frame,
            text="❌ Sair",
            command=self._on_closing,
            bootstyle="dark",
            padding=(10, 10),
        )
        btn_sair.grid(row=5, column=0, sticky="sew")

        self.show_frame("selfservice")

    def show_frame(self, nome_pagina: str):
        if self.selected_frame_name == nome_pagina:
            return

        if self.selected_frame_name and self.selected_frame_name in self.frames:
            self.frames[self.selected_frame_name].grid_remove()
            self.buttons[self.selected_frame_name].config(bootstyle="dark")

        self.buttons[nome_pagina].config(bootstyle="light")
        self.selected_frame_name = nome_pagina
        frame_ativo = self.frames[nome_pagina]
        frame_ativo.grid(row=0, column=0, sticky=NSEW)

    def notificar_sucesso_registro(self, dados_estudante: Tuple[str, ...]):
        self.frames["consumos"].adicionar_consumo(dados_estudante)
        self.frames["dashboard"].atualizar_dados(
            ultimo_consumo=dados_estudante)

    def _on_closing(self):
        if "selfservice" in self.frames:
            self.frames["selfservice"].stop()
        try:
            self.fachada_nucleo.fechar_conexao()
        except Exception as e:
            logger.warning("Erro ao fechar conexão com DB: %s", e)
        self.destroy()


def main():
    """Ponto de entrada para a aplicação de autoatendimento."""
    log_format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_format)
    logging.getLogger().setLevel(logging.INFO)

    try:
        app = AppSelfService()
        if app.id_sessao_ativa:
            app.mainloop()
    except Exception:
        logger.critical(
            "Erro fatal ao iniciar a aplicação de autoatendimento.")
        logger.critical(traceback.format_exc())
        Messagebox.show_error(
            "Erro Crítico",
            "A aplicação encontrou um erro irrecuperável e será fechada. "
            "Verifique os logs para mais detalhes.",
        )


if __name__ == "__main__":
    main()
