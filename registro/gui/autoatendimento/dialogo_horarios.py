# ----------------------------------------------------------------------------
# Arquivo: registro/gui/autoatendimento/dialogo_horarios.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Diálogo de consulta visual de horários e turmas ativas/desativadas para o Totem.
Exibe uma linha do tempo (timeline) dos slots da refeição atual com status
dinâmico (Liberado Agora, Em Breve, Encerrado), fechamento automático por
inatividade e integração com leituras rápidas (QR Code / Scanner USB).
"""

from datetime import datetime
import logging
import tkinter as tk
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

import ttkbootstrap as ttk
from ttkbootstrap import ScrolledFrame
from ttkbootstrap.constants import BOTH, CENTER, EW, LEFT, NSEW, RIGHT, VERTICAL, X, YES

from registro.nucleo.services import grade_horarios_service

if TYPE_CHECKING:
    from registro.nucleo.facade import FachadaRegistro

logger = logging.getLogger(__name__)

MAPA_NOMES_DIAS = {
    "segunda": "Segunda-feira",
    "terca": "Terça-feira",
    "quarta": "Quarta-feira",
    "quinta": "Quinta-feira",
    "sexta": "Sexta-feira",
    "sabado": "Sábado",
    "domingo": "Domingo",
}

MAPA_NOMES_REFEICOES = {
    "almoco": "Almoço",
    "jantar": "Jantar",
    "lanche": "Lanche",
}


class DialogoGradeHorariosTotem(ttk.Toplevel):
    """
    Diálogo moderno e touch-friendly exibindo a escala de horários das turmas
    para a refeição corrente no totem de autoatendimento.
    """

    # Identificador para o totem reconhecer que este diálogo permite leitura de código
    permite_leitura_totem: bool = True

    def __init__(
        self,
        parent: tk.Widget,
        fachada: "FachadaRegistro",
        on_codigo_lido: Optional[Callable[[str], None]] = None,
        timeout_segundos: int = 15,
        hora_simulada: Optional[str] = None,
    ):
        super().__init__(parent)
        self.transient(parent)
        self.title("🕒 Horários das Turmas - Refeição Ativa")
        self.geometry("720x620")
        self.minsize(560, 480)

        self._fachada = fachada
        self._on_codigo_lido = on_codigo_lido
        self._timeout_total = max(1, int(timeout_segundos))
        self._tempo_restante = self._timeout_total
        self._hora_simulada = hora_simulada

        self._buffer_leitor: str = ""
        self._timer_id: Optional[str] = None
        self._cards_widgets: List[Dict[str, Any]] = []

        self._lbl_relogio: Optional[ttk.Label] = None
        self._lbl_subtitulo: Optional[ttk.Label] = None
        self._lbl_timer: Optional[ttk.Label] = None
        self._barra_fechamento: Optional[ttk.Progressbar] = None
        self._frame_cards_container: Optional[ttk.Frame] = None

        self._criar_interface()
        self._carregar_dados_grade()
        self._centralizar(parent)

        # Captura de teclado / leitor USB
        self.bind("<Key>", self._ao_pressionar_tecla)
        self.bind("<Escape>", lambda _e: self.fechar())

        # Inicia contagem regressiva e atualização a cada 1 segundo
        self._iniciar_temporizador()

        self.protocol("WM_DELETE_WINDOW", self.fechar)
        try:
            self.focus_force()
        except Exception:
            pass

    def _centralizar(self, parent: tk.Widget):
        """Centraliza a janela sobre o elemento pai."""
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            w = self.winfo_width()
            h = self.winfo_height()
            x = max(10, px + (pw - w) // 2)
            y = max(10, py + (ph - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def _criar_interface(self):
        """Constrói os elementos visuais do diálogo."""
        frame_raiz = ttk.Frame(self, padding=20)
        frame_raiz.pack(fill=BOTH, expand=YES)
        frame_raiz.rowconfigure(1, weight=1)
        frame_raiz.columnconfigure(0, weight=1)

        # 1. Cabeçalho com Título, Subtítulo e Relógio Digital
        frame_cabecalho = ttk.Frame(frame_raiz)
        frame_cabecalho.grid(row=0, column=0, sticky=EW, pady=(0, 15))
        frame_cabecalho.columnconfigure(0, weight=1)
        frame_cabecalho.columnconfigure(1, weight=0)

        frame_titulos = ttk.Frame(frame_cabecalho)
        frame_titulos.grid(row=0, column=0, sticky="w")

        lbl_titulo = ttk.Label(
            frame_titulos,
            text="🕒 Horários de Acesso por Turma",
            font=("Segoe UI", 18, "bold"),
            bootstyle="primary",
        )
        lbl_titulo.pack(anchor="w")

        self._lbl_subtitulo = ttk.Label(
            frame_titulos,
            text="Carregando programação...",
            font=("Segoe UI", 12),
            bootstyle="secondary",
        )
        self._lbl_subtitulo.pack(anchor="w", pady=(2, 0))

        # Relógio grande à direita (estilo suave, harmonizando com o cabeçalho)
        self._lbl_relogio = ttk.Label(
            frame_cabecalho,
            text="--:--:--",
            font=("Segoe UI", 16, "bold"),
            bootstyle="@light",
            padding=(12, 6),
        )
        self._lbl_relogio.grid(row=0, column=1, sticky="e")

        ttk.Separator(frame_raiz, orient="horizontal").grid(
            row=0, column=0, sticky="sew", pady=(0, 0)
        )

        # 2. Área Central com Linha do Tempo Rolável
        self._scroll_frame = ScrolledFrame(frame_raiz, padding=8, auto_hide=True)
        self._scroll_frame.grid(row=1, column=0, sticky=NSEW, pady=(10, 15))
        self._scroll_frame.columnconfigure(0, weight=1)
        self._frame_cards_container = self._scroll_frame

        # 3. Rodapé com Contador de Fechamento Automático, Barra e Botão Fechar
        frame_rodape = ttk.Frame(frame_raiz)
        frame_rodape.grid(row=2, column=0, sticky=EW)
        frame_rodape.columnconfigure(0, weight=1)
        frame_rodape.columnconfigure(1, weight=0)

        frame_info_timer = ttk.Frame(frame_rodape)
        frame_info_timer.grid(row=0, column=0, sticky=EW, padx=(0, 15))
        frame_info_timer.columnconfigure(0, weight=1)

        self._lbl_timer = ttk.Label(
            frame_info_timer,
            text=f"Fechando automaticamente em {self._tempo_restante}s...",
            font=("Segoe UI", 10),
            bootstyle="secondary",
        )
        self._lbl_timer.grid(row=0, column=0, sticky="w", pady=(0, 4))

        self._barra_fechamento = ttk.Progressbar(
            frame_info_timer,
            maximum=self._timeout_total,
            value=self._tempo_restante,
            bootstyle="primary",
        )
        self._barra_fechamento.grid(row=1, column=0, sticky=EW)

        btn_fechar = ttk.Button(
            frame_rodape,
            text=" ✖️ Fechar (Esc) ",
            bootstyle="secondary-outline",
            command=self.fechar,
            padding=(18, 10),
        )
        btn_fechar.grid(row=0, column=1, rowspan=2, sticky="e")

    def _obter_hora_e_minutos_atuais(self) -> (str, int):
        """Retorna (hora_formatada_str, total_minutos)."""
        if self._hora_simulada:
            partes = self._hora_simulada.split(":")
            h, m = int(partes[0]), int(partes[1])
            return f"{h:02d}:{m:02d}:00", h * 60 + m
        agora = datetime.now()
        minutos = agora.hour * 60 + agora.minute
        return agora.strftime("%H:%M:%S"), minutos

    def _carregar_dados_grade(self):
        """Lê a sessão ativa e a grade horária semanal para montar os cartões."""
        # Limpa widgets anteriores
        for w in self._frame_cards_container.winfo_children():
            w.destroy()
        self._cards_widgets.clear()

        hora_str, minutos_atuais = self._obter_hora_e_minutos_atuais()
        if self._lbl_relogio:
            self._lbl_relogio.config(text=f"🕒 {hora_str}")

        # 1. Verifica se há sessão ativa
        detalhes_sessao = self._fachada.obter_detalhes_sessao_ativa()
        if not detalhes_sessao or not self._fachada.id_sessao_ativa:
            if self._lbl_subtitulo:
                self._lbl_subtitulo.config(
                    text="Nenhuma sessão em andamento no momento",
                    bootstyle="danger",
                )
            self._exibir_aviso_informativo(
                icone="⚠️",
                titulo="Nenhuma sessão em andamento no momento",
                mensagem="O refeitório não está com atendimentos ativos no momento.\nConsulte os horários com o operador responsável.",
                bootstyle="secondary",
            )
            return

        refeicao_bruta = detalhes_sessao.get("refeicao", "almoco")
        refeicao_norm = grade_horarios_service._normalizar_chave(refeicao_bruta)
        dia_norm = grade_horarios_service.obter_dia_semana_atual()

        nome_dia = MAPA_NOMES_DIAS.get(dia_norm, dia_norm.capitalize())
        nome_ref = MAPA_NOMES_REFEICOES.get(refeicao_norm, refeicao_bruta.capitalize())

        if self._lbl_subtitulo:
            self._lbl_subtitulo.config(
                text=f"Refeição: {nome_ref} • {nome_dia}",
                bootstyle="secondary",
            )

        # 2. Carrega a grade horária
        grade = self._fachada.obter_grade_horarios()
        slots_brutos = grade.get(dia_norm, {}).get(refeicao_norm, [])

        if not slots_brutos:
            self._exibir_aviso_informativo(
                icone="ℹ️",
                titulo="Sem restrição de horários para esta refeição",
                mensagem=f"O acesso está livre para todas as turmas durante o período de {nome_ref}.\nNão há escalonamento programado na grade para hoje.",
                bootstyle="info",
            )
            return

        # Ordena slots cronologicamente pelo horário de início
        try:
            slots_ordenados = sorted(
                slots_brutos,
                key=lambda s: grade_horarios_service._hora_para_minutos(s.get("inicio", "00:00")),
            )
        except Exception:
            slots_ordenados = slots_brutos

        # Renderiza a lista de cartões da linha do tempo
        for index, slot in enumerate(slots_ordenados):
            self._criar_card_slot(slot, index, minutos_atuais)

        self._atualizar_estados_slots(minutos_atuais)

    def _exibir_aviso_informativo(
        self, icone: str, titulo: str, mensagem: str, bootstyle: str = "info"
    ):
        """Exibe uma mensagem informativa amigável no centro da tela."""
        frame_aviso = ttk.Frame(
            self._frame_cards_container, padding=25, bootstyle=bootstyle
        )
        frame_aviso.pack(fill=X, expand=YES, pady=30, padx=20)

        lbl_ico = ttk.Label(
            frame_aviso,
            text=icone,
            font=("Segoe UI", 32),
            anchor=CENTER,
        )
        lbl_ico.pack(fill=X, pady=(0, 10))

        lbl_tit = ttk.Label(
            frame_aviso,
            text=titulo,
            font=("Segoe UI", 14, "bold"),
            anchor=CENTER,
        )
        lbl_tit.pack(fill=X, pady=(0, 8))

        lbl_msg = ttk.Label(
            frame_aviso,
            text=mensagem,
            font=("Segoe UI", 11),
            anchor=CENTER,
            justify=CENTER,
        )
        lbl_msg.pack(fill=X)

    def _criar_card_slot(
        self, slot: Dict[str, Any], index: int, minutos_atuais: int
    ):
        """Cria o cartão visual correspondente a um slot de horário."""
        ini_str = str(slot.get("inicio", "--:--")).strip()
        fim_str = str(slot.get("fim", "--:--")).strip()

        try:
            ini_m = grade_horarios_service._hora_para_minutos(ini_str)
            fim_m = grade_horarios_service._hora_para_minutos(fim_str)
        except Exception:
            ini_m = 0
            fim_m = 1440

        style = ttk.Style.get_instance() or ttk.Style()
        cor_bg = style.colors.bg if hasattr(style, "colors") else "#ffffff"
        cor_border = style.colors.border if hasattr(style, "colors") else "#d6d6d6"

        frame_card = tk.Frame(
            self._frame_cards_container,
            bg=cor_bg,
            highlightbackground=cor_border,
            highlightcolor=cor_border,
            highlightthickness=1,
            padx=16,
            pady=12,
        )
        frame_card.pack(fill=X, expand=YES, pady=6, padx=4)
        frame_card.columnconfigure(0, weight=1)
        frame_card.columnconfigure(1, weight=0)

        # Linha Superior: Horário + Badge de Status
        frame_topo_card = ttk.Frame(frame_card)
        frame_topo_card.grid(row=0, column=0, columnspan=2, sticky=EW)
        frame_topo_card.columnconfigure(0, weight=1)
        frame_topo_card.columnconfigure(1, weight=0)

        lbl_horario = ttk.Label(
            frame_topo_card,
            text=f"⏰  {ini_str}  às  {fim_str}",
            font=("Segoe UI", 15, "bold"),
            bootstyle="primary",
        )
        lbl_horario.grid(row=0, column=0, sticky="w")

        lbl_badge = ttk.Label(
            frame_topo_card,
            text="...",
            font=("Segoe UI", 10, "bold"),
            padding=(10, 4),
            bootstyle="@secondary",
        )
        lbl_badge.grid(row=0, column=1, sticky="e")

        # Linha de Detalhes do Status (Contagem regressiva / Tempo restante)
        lbl_substatus = ttk.Label(
            frame_card,
            text="",
            font=("Segoe UI", 10),
            bootstyle="secondary",
        )
        lbl_substatus.grid(row=1, column=0, columnspan=2, sticky="w", pady=(3, 8))

        # Divisor interno sutil
        ttk.Separator(frame_card, orient="horizontal").grid(
            row=2, column=0, columnspan=2, sticky=EW, pady=(0, 8)
        )

        # Turmas autorizadas
        turmas_raw = slot.get("turmas", [])
        if not turmas_raw or "*" in turmas_raw or "TODAS" in [str(t).upper() for t in turmas_raw]:
            texto_turmas = "Todas as turmas estão autorizadas neste horário."
            estilo_turmas = "success"
        else:
            texto_turmas = ", ".join(turmas_raw)
            estilo_turmas = "default"

        frame_turmas = ttk.Frame(frame_card)
        frame_turmas.grid(row=3, column=0, columnspan=2, sticky=EW)

        lbl_rotulo_turmas = ttk.Label(
            frame_turmas,
            text="👥 Turmas:",
            font=("Segoe UI", 10, "bold"),
            bootstyle="secondary",
        )
        lbl_rotulo_turmas.pack(side=LEFT, anchor="w", padx=(0, 6))

        lbl_conteudo_turmas = ttk.Label(
            frame_turmas,
            text=texto_turmas,
            font=("Segoe UI", 11),
            bootstyle=estilo_turmas,
            wraplength=600,
        )
        lbl_conteudo_turmas.pack(side=LEFT, fill=X, expand=YES, anchor="w")

        # Categorias autorizadas (se restrito)
        cats_raw = slot.get("categorias", [])
        if cats_raw and "*" not in cats_raw and "TODAS" not in [str(c).upper() for c in cats_raw]:
            frame_cats = ttk.Frame(frame_card)
            frame_cats.grid(row=4, column=0, columnspan=2, sticky=EW, pady=(4, 0))

            lbl_rotulo_cats = ttk.Label(
                frame_cats,
                text="🏷️ Categorias:",
                font=("Segoe UI", 9, "bold"),
                bootstyle="warning",
            )
            lbl_rotulo_cats.pack(side=LEFT, anchor="w", padx=(0, 6))

            lbl_conteudo_cats = ttk.Label(
                frame_cats,
                text=", ".join(cats_raw),
                font=("Segoe UI", 9),
                bootstyle="warning",
            )
            lbl_conteudo_cats.pack(side=LEFT, fill=X, expand=YES, anchor="w")

        self._cards_widgets.append(
            {
                "slot": slot,
                "ini_m": ini_m,
                "fim_m": fim_m,
                "ini_str": ini_str,
                "fim_str": fim_str,
                "frame_card": frame_card,
                "horario": lbl_horario,
                "badge": lbl_badge,
                "substatus": lbl_substatus,
            }
        )

    def _atualizar_estados_slots(self, minutos_atuais: int):
        """Avalia e atualiza visualmente os badges e textos de cada slot."""
        tolerancia_min = 5
        style = ttk.Style.get_instance() or ttk.Style()
        cor_success = style.colors.success if hasattr(style, "colors") else "#769e3c"
        cor_border = style.colors.border if hasattr(style, "colors") else "#d6d6d6"

        for item in self._cards_widgets:
            ini_m = item["ini_m"]
            fim_m = item["fim_m"]
            ini_str = item["ini_str"]
            fim_str = item["fim_str"]
            frame_card = item["frame_card"]
            lbl_badge = item["badge"]
            lbl_substatus = item["substatus"]
            lbl_horario = item.get("horario")

            # 1. Slot Encerrado
            if minutos_atuais > fim_m + tolerancia_min:
                lbl_badge.config(
                    text="⚪  ENCERRADO",
                    bootstyle="@secondary",
                )
                lbl_substatus.config(
                    text=f"Horário finalizado às {fim_str}",
                    bootstyle="secondary",
                )
                if lbl_horario:
                    lbl_horario.config(bootstyle="secondary")
                frame_card.config(
                    highlightbackground=cor_border,
                    highlightthickness=1,
                )

            # 2. Slot Ativo Agora (considerando tolerância de validação)
            elif (ini_m - tolerancia_min) <= minutos_atuais <= (fim_m + tolerancia_min):
                minutos_restantes = max(0, fim_m - minutos_atuais)
                if minutos_atuais < ini_m:
                    txt_tempo = f"Liberado (Tolerância inicial) • Restam {minutos_restantes} min"
                else:
                    txt_tempo = f"Restam {minutos_restantes} min até o término ({fim_str})"

                lbl_badge.config(
                    text="●  LIBERADO AGORA",
                    bootstyle="@success",
                )
                lbl_substatus.config(
                    text=txt_tempo,
                    bootstyle="success",
                )
                if lbl_horario:
                    lbl_horario.config(bootstyle="primary")
                frame_card.config(
                    highlightbackground=cor_success,
                    highlightthickness=2,
                )

            # 3. Slot Futuro / Em Breve
            else:
                minutos_espera = ini_m - minutos_atuais
                if minutos_espera <= 60:
                    txt_espera = f"Inicia em {minutos_espera} min (às {ini_str})"
                else:
                    horas = minutos_espera // 60
                    mins = minutos_espera % 60
                    txt_espera = f"Inicia em {horas}h{mins:02d}min (às {ini_str})"

                lbl_badge.config(
                    text="⏳  EM BREVE",
                    bootstyle="@warning",
                )
                lbl_substatus.config(
                    text=txt_espera,
                    bootstyle="secondary",
                )
                if lbl_horario:
                    lbl_horario.config(bootstyle="primary")
                frame_card.config(
                    highlightbackground=cor_border,
                    highlightthickness=1,
                )

    def _iniciar_temporizador(self):
        """Dispara a atualização contínua de 1 segundo."""
        self._timer_id = self.after(1000, self._ciclo_segundo)

    def _ciclo_segundo(self):
        """Executa a atualização de status a cada 1 segundo e decrementa o timer de fechamento."""
        if not self.winfo_exists():
            return

        hora_str, minutos_atuais = self._obter_hora_e_minutos_atuais()
        if self._lbl_relogio and self._lbl_relogio.winfo_exists():
            self._lbl_relogio.config(text=f"🕒 {hora_str}")

        if self._cards_widgets:
            self._atualizar_estados_slots(minutos_atuais)

        # Atualiza a contagem regressiva de auto-close
        self._tempo_restante -= 1
        if self._barra_fechamento and self._barra_fechamento.winfo_exists():
            self._barra_fechamento["value"] = max(0, self._tempo_restante)
        if self._lbl_timer and self._lbl_timer.winfo_exists():
            self._lbl_timer.config(
                text=f"Fechando automaticamente em {max(0, self._tempo_restante)}s..."
            )

        if self._tempo_restante <= 0:
            self.fechar()
            return

        self._timer_id = self.after(1000, self._ciclo_segundo)

    def _ao_pressionar_tecla(self, event: tk.Event):
        """
        Intercepta leitura do leitor de código de barras USB ou tecla de fechamento.
        Caso detecte a finalização de um código (Enter), fecha a janela imediatamente
        e repassa o código para processamento no totem.
        """
        if event.keysym in ("Escape",):
            self.fechar()
            return "break"

        if event.keysym in ("Return", "KP_Enter"):
            codigo = self._buffer_leitor.strip()
            self._buffer_leitor = ""
            if codigo:
                callback = self._on_codigo_lido
                self.fechar()
                if callback:
                    callback(codigo)
                return "break"
            return None

        if event.char and event.char.isprintable():
            self._buffer_leitor += event.char
            return None

        return None

    def fechar(self):
        """Encerra com segurança o diálogo liberando o temporizador."""
        if self._timer_id:
            try:
                self.after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None

        try:
            self.destroy()
        except Exception:
            pass
