#!/usr/bin/env python3
# ----------------------------------------------------------------------------
# Arquivo: scripts/gerar_dados_teste.py
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Script para geração de massa de dados complexa, válida e realista para testes do
Sistema de Registro de Refeições (mr2), com opção de envio direto ao Google Sheets.

Gera dados coerentes para todas as abas:
  - Discentes: Estudantes com prontuários, nomes, turmas reais e categorias/tags (PAP, ESP1, LIB0, etc.).
  - Configuração: Grade semanal de horários com turnos de almoço, jantar e lanche.
  - Lanches: Cardápio com opções diversificadas de lanches.
  - DB: Reservas de refeições com pratos variados, dias da semana e categorias pontuais opcionais.
  - Almoço, Jantar, Lanche: Consumos realistas com estudantes com reserva e exceções.
  - Consumo_Cancelados: Auditoria de cancelamentos de consumos (soft deletes).
"""

import argparse
import logging
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Garante importação do pacote registro caso executado da raiz do projeto
DIRETORIO_RAIZ = Path(__file__).resolve().parent.parent
if str(DIRETORIO_RAIZ) not in sys.path:
    sys.path.insert(0, str(DIRETORIO_RAIZ))

from gspread.utils import ValueInputOption

from registro.nucleo.constants import (
    CABECALHO_CANCELADOS,
    CABECALHO_CONFIGURACAO,
    CABECALHO_DISCENTES,
    CABECALHO_EXPORTACAO,
    CABECALHO_LANCHES,
    CABECALHO_RESERVAS,
    NOME_ABA_CANCELADOS,
    NOME_ABA_CONFIGURACAO,
    NOME_ABA_ESTUDANTES,
    NOME_ABA_LANCHES,
    NOME_ABA_RESERVAS,
)
from registro.nucleo.google_api_service import obter_servico_planilha_padrao

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gerador_dados_teste")

# -----------------------------------------------------------------------------
# Constantes e Bancos de Nomes / Sobrenomes Realistas
# -----------------------------------------------------------------------------

NOMES_PRIMEIROS = [
    "Ana", "Beatriz", "Camila", "Daniela", "Eduarda", "Fernanda", "Gabriela", "Helena",
    "Isabela", "Juliana", "Larissa", "Mariana", "Natalia", "Patricia", "Rafaela", "Sofia",
    "Arthur", "Bernardo", "Caio", "Davi", "Eduardo", "Felipe", "Gabriel", "Heitor",
    "Igor", "Joao", "Lucas", "Mateus", "Nicolas", "Pedro", "Rafael", "Thiago", "Vinicius",
    "Alice", "Clara", "Leticia", "Luiza", "Manuela", "Valentina", "Enzo", "Gustavo",
    "Leonardo", "Matheus", "Samuel", "Guilherme", "Vitor", "Renan", "Murilo", "Diego"
]

SOBRENOMES = [
    "Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira", "Alves", "Pereira",
    "Lima", "Gomes", "Costa", "Ribeiro", "Martins", "Carvalho", "Almeida", "Lopes",
    "Soares", "Fernandes", "Vieira", "Barbosa", "Rocha", "Dias", "Nascimento", "Andrade",
    "Moreira", "Nunes", "Marques", "Machado", "Mendes", "Freitas", "Cardoso", "Ramos",
    "Goncalves", "Santana", "Teixeira", "Moraes", "Borges", "Pinheiro", "Pinto", "Campos"
]

TURMAS_PADRAO = [
    "1º A - MAC",
    "1º A - MEC",
    "1º B - MEC",
    "2º A - MAC",
    "2º A - MEC",
    "2º B - MEC",
    "3º A - MAC",
    "3º A - MEC",
    "3º B - MEC",
]

CATEGORIAS_PERMANENTES_OPCOES = [
    [],
    [],
    [],
    ["PAP"],
    ["ESP1"],
    ["LIB0"],
    ["PAP", "ESP1"],
    ["PAP", "LIB0"],
]

CATEGORIAS_PONTUAIS_RESERVA = [
    "ESP1",
    "LIB0",
    "EVENTO_ESPORTIVO",
    "VISITA_TECNICA",
]

PRATOS_ALMOCO = [
    "Arroz, Feijão Carioca, Filé de Frango Grelhado e Salada de Alface",
    "Arroz, Feijão Preto, Carne Moída com Legumes e Purê de Batatas",
    "Arroz, Feijão Carioca, Bife Bovino Acebolado e Vinagrete",
    "Arroz Integral, Feijão, Isca de Peixe Empanada e Legumes no Vapor",
    "Opção Vegetariana: Strogonoff de Cogumelos e Batata Palha",
    "Opção Vegetariana: Quiche de Ricota com Espinafre e Salada",
    "Dieta Especial: Sem Glúten - Frango Cozido com Batatas e Salada",
    "Dieta Especial: Sem Lactose - Filé de Frango com Arroz e Legumes",
]

PRATOS_JANTAR = [
    "Sopa de Legumes com Carne e Torradas Integrais",
    "Arroz, Feijão, Omelete com Queijo e Tomate e Salada de Rúcula",
    "Macarrão à Bolonhesa e Salada Verde",
    "Arroz, Feijão, Frango Desfiado com Milho e Salada Colorida",
    "Opção Vegetariana: Macarrão com Molho de Tomates Frescos e Manjericão",
    "Opção Vegetariana: Torta de Legumes e Mix de Folhas",
]

ITENS_LANCHE = [
    "Iogurte com Cereais",
    "Iogurte e Banana Desidratada",
    "Achocolatado e Biscoito Maisena",
    "Achocolatado e Biscoito Cream Cracker",
    "Suco de Uva e Biscoito Maisena",
    "Suco de Laranja e Banana Desidratada",
    "Suco de Maçã e Barra de Cereais",
    "Vitamina de Morango e Biscoito Cream Cracker",
    "Salada de Frutas Especial",
    "Suco Misto de Uva e Maçã e Barra de Cereal",
]

DIAS_SEMANA_PT = {
    0: "SEGUNDA-FEIRA",
    1: "TERÇA-FEIRA",
    2: "QUARTA-FEIRA",
    3: "QUINTA-FEIRA",
    4: "SEXTA-FEIRA",
    5: "SÁBADO",
    6: "DOMINGO",
}

DIAS_GRADE = [
    ("Segunda", "segunda"),
    ("Terça", "terca"),
    ("Quarta", "quarta"),
    ("Quinta", "quinta"),
    ("Sexta", "sexta"),
]

MOTIVOS_CANCELAMENTO = [
    "Leitura duplicada acidental no leitor óptico",
    "Discente desistiu da refeição antes da entrega",
    "Matrícula digitada incorretamente pelo operador",
    "Troca de tipo de refeição solicitada na fila",
    "Passagem acidental com crachá em teste",
]

OPERADORES_CANCELAMENTO = ["Operador 01", "Operador 02", "Totem Autoatendimento", "Administrador"]


# -----------------------------------------------------------------------------
# Classes e Geradores de Dados
# -----------------------------------------------------------------------------

class GeradorDadosTeste:
    """Gera um conjunto completo, consistente e realista de dados para o sistema."""

    def __init__(self, qtd_alunos: int = 60, seed: int = 42):
        self.qtd_alunos = qtd_alunos
        self.rng = random.Random(seed)
        self.estudantes: List[Dict[str, str]] = []

    def gerar_estudantes(self) -> List[List[str]]:
        """Gera discentes com matrícula, nome, turma real e categorias/tags permanentes."""
        self.estudantes = []
        linhas = []
        matricula_base = 3010000

        for i in range(self.qtd_alunos):
            matricula = f"SP{matricula_base + i + 1:07d}"
            primeiro = self.rng.choice(NOMES_PRIMEIROS)
            sobrenome1 = self.rng.choice(SOBRENOMES)
            sobrenome2 = self.rng.choice(SOBRENOMES)
            if sobrenome2 == sobrenome1:
                sobrenome2 = "Ferreira"
            nome_completo = f"{primeiro} {sobrenome1} {sobrenome2}"
            turma = self.rng.choice(TURMAS_PADRAO)

            cats_perm = sorted(self.rng.choice(CATEGORIAS_PERMANENTES_OPCOES))
            categoria_str = ", ".join(cats_perm) if cats_perm else "-"

            estudante_info: Dict[str, Any] = {
                "matricula": matricula,
                "nome": nome_completo,
                "turma": turma,
                "categorias_perm": cats_perm,
                "categoria": categoria_str,
            }
            self.estudantes.append(estudante_info)
            linhas.append([matricula, nome_completo, turma, categoria_str])

        return linhas

    def gerar_configuracao(self) -> List[List[str]]:
        """
        Gera as linhas da aba 'Configuração' com a grade semanal oficial:
        Lanche Manhã, Almoço, Lanche Tarde, Jantar.
        """
        linhas = []
        for dia_nome, _ in DIAS_GRADE:
            # Lanche Manhã
            linhas.append([dia_nome, "Lanche", "09:30", "10:00", "TODAS", "TODAS"])
            # Almoço
            linhas.append([dia_nome, "Almoço", "11:30", "13:30", "TODAS", "TODAS"])
            # Lanche Tarde
            linhas.append([dia_nome, "Lanche", "15:30", "16:00", "TODAS", "TODAS"])
            # Jantar
            linhas.append([dia_nome, "Jantar", "17:45", "19:15", "TODAS", "TODAS"])

        # Sábado letivo / apoio
        linhas.append(["Sábado", "Lanche", "09:30", "10:00", "TODAS", "TODAS"])
        linhas.append(["Sábado", "Almoço", "11:30", "13:00", "TODAS", "TODAS"])
        return linhas

    def gerar_lanches(self) -> List[List[str]]:
        """Gera as opções disponíveis de lanche para a aba 'Lanches'."""
        return [[item] for item in ITENS_LANCHE]

    def _obter_dias_uteis(self, data_ref: date, dias_passados: int = 3, dias_futuros: int = 2) -> List[date]:
        """Calcula uma lista ordenada de dias úteis em torno da data de referência."""
        dias: List[date] = []
        # Passados
        delta = 1
        while len([d for d in dias if d < data_ref]) < dias_passados:
            d = data_ref - timedelta(days=delta)
            if d.weekday() < 5:  # Segunda a Sexta
                dias.insert(0, d)
            delta += 1

        # Hoje (ou mais próximo dia útil)
        dias.append(data_ref)

        # Futuros
        delta = 1
        while len([d for d in dias if d > data_ref]) < dias_futuros:
            d = data_ref + timedelta(days=delta)
            if d.weekday() < 5:
                dias.append(d)
            delta += 1

        return sorted(dias)

    def gerar_reservas(self, dias: List[date]) -> List[List[str]]:
        """
        Gera as reservas para a aba 'DB'.
        Formato: [DATA, MATRÍCULA, NOME, TURMA, REFEIÇÃO, DIA DA SEMANA, CATEGORIA, ALMOÇO, JANTAR]
        """
        linhas = []
        for d in dias:
            data_str = d.strftime("%Y-%m-%d")
            dia_semana_str = DIAS_SEMANA_PT[d.weekday()]

            # 65% a 85% dos discentes realizam reserva para o dia
            qtd_reservas = int(len(self.estudantes) * self.rng.uniform(0.65, 0.85))
            alunos_sorteados = self.rng.sample(self.estudantes, qtd_reservas)

            for aluno in alunos_sorteados:
                sorteio_turno = self.rng.random()
                if sorteio_turno < 0.65:
                    tem_almoco, tem_jantar = True, False
                elif sorteio_turno < 0.85:
                    tem_almoco, tem_jantar = True, True
                else:
                    tem_almoco, tem_jantar = False, True

                prato = (
                    self.rng.choice(PRATOS_JANTAR)
                    if (tem_jantar and not tem_almoco)
                    else self.rng.choice(PRATOS_ALMOCO)
                )
                cat_reserva = ""
                if self.rng.random() < 0.20:
                    qtd_tags = 1 if self.rng.random() < 0.80 else 2
                    tags = sorted(self.rng.sample(CATEGORIAS_PONTUAIS_RESERVA, qtd_tags))
                    cat_reserva = ", ".join(tags)
                linhas.append([
                    data_str,
                    aluno["matricula"],
                    aluno["nome"],
                    aluno["turma"],
                    prato,
                    dia_semana_str,
                    cat_reserva,
                    "Sim" if tem_almoco else "Não",
                    "Sim" if tem_jantar else "Não",
                ])

        return linhas

    def _categoria_efetiva_no_dia(
        self,
        aluno: Dict[str, Any],
        data_str: str,
        cats_reserva_por_data_matr: Dict[Tuple[str, str], List[str]],
    ) -> str:
        """Combina categorias permanentes do aluno com categorias pontuais da reserva na data."""
        cats = set(aluno.get("categorias_perm", []))
        cats.update(cats_reserva_por_data_matr.get((data_str, aluno["matricula"]), []))
        return ", ".join(sorted(cats)) if cats else "-"

    def gerar_consumos(
        self,
        dias: List[date],
        reservas_por_data_matr: Dict[Tuple[str, str], Any],
        cats_reserva_por_data_matr: Dict[Tuple[str, str], List[str]] | None = None,
    ) -> Dict[str, List[List[str]]]:
        """
        Gera os consumos realizados para os dias passados e presente (até horário atual).
        Retorna dicionário com listas para:
          - 'Almoço'
          - 'Jantar'
          - 'Lanche'
        """
        consumos_almoco: List[List[str]] = []
        consumos_jantar: List[List[str]] = []
        consumos_lanche: List[List[str]] = []
        cats_res_mapa = cats_reserva_por_data_matr or {}

        def _info_reserva(data_s: str, matr: str) -> Optional[Dict[str, Any]]:
            val = reservas_por_data_matr.get((data_s, matr))
            if val is None:
                return None
            if isinstance(val, dict):
                return val
            return {"prato": str(val), "almoco": True, "jantar": False}

        # Apenas dias até hoje
        hoje = date.today()
        dias_consumo = [d for d in dias if d <= hoje]

        for d in dias_consumo:
            data_str = d.strftime("%Y-%m-%d")

            # 1. Almoço (entre 80% e 95% dos que tinham reserva de almoço comparecem)
            alunos_com_almoco = [
                a for a in self.estudantes
                if (info := _info_reserva(data_str, a["matricula"])) and info.get("almoco")
            ]
            qtd_comp_alm = int(len(alunos_com_almoco) * self.rng.uniform(0.80, 0.95))
            for aluno in self.rng.sample(alunos_com_almoco, qtd_comp_alm):
                hora = self._gerar_horario_aleatorio(11, 35, 13, 25)
                info = _info_reserva(data_str, aluno["matricula"]) or {}
                prato = info.get("prato", "Padrão")
                cat_efetiva = self._categoria_efetiva_no_dia(aluno, data_str, cats_res_mapa)
                consumos_almoco.append([
                    aluno["matricula"],
                    data_str,
                    aluno["nome"],
                    aluno["turma"],
                    prato,
                    hora,
                    cat_efetiva,
                ])

            # Exceções: alunos sem reserva de almoço que almoçaram (3 a 6 alunos)
            alunos_sem_almoco = [
                a for a in self.estudantes
                if not ((info := _info_reserva(data_str, a["matricula"])) and info.get("almoco"))
            ]
            if alunos_sem_almoco:
                qtd_excecao = min(len(alunos_sem_almoco), self.rng.randint(3, 6))
                for aluno in self.rng.sample(alunos_sem_almoco, qtd_excecao):
                    hora = self._gerar_horario_aleatorio(12, 10, 13, 15)
                    cat_efetiva = self._categoria_efetiva_no_dia(aluno, data_str, cats_res_mapa)
                    consumos_almoco.append([
                        aluno["matricula"],
                        data_str,
                        aluno["nome"],
                        aluno["turma"],
                        "Sem Reserva (Exceção)",
                        hora,
                        cat_efetiva,
                    ])

            # 2. Lanche (Manhã e Tarde)
            # 40% a 60% dos estudantes tomam lanche
            qtd_lanche = int(len(self.estudantes) * self.rng.uniform(0.40, 0.60))
            for aluno in self.rng.sample(self.estudantes, qtd_lanche):
                item = self.rng.choice(ITENS_LANCHE)
                turno_manha = self.rng.random() < 0.60
                if turno_manha:
                    hora = self._gerar_horario_aleatorio(9, 32, 9, 58)
                else:
                    hora = self._gerar_horario_aleatorio(15, 32, 15, 58)

                cat_efetiva = self._categoria_efetiva_no_dia(aluno, data_str, cats_res_mapa)
                consumos_lanche.append([
                    aluno["matricula"],
                    data_str,
                    aluno["nome"],
                    aluno["turma"],
                    item,
                    hora,
                    cat_efetiva,
                ])

            # 3. Jantar (entre 80% e 95% dos que tinham reserva de jantar comparecem + 1 a 3 exceções)
            alunos_com_jantar = [
                a for a in self.estudantes
                if (info := _info_reserva(data_str, a["matricula"])) and info.get("jantar")
            ]
            qtd_comp_jan = int(len(alunos_com_jantar) * self.rng.uniform(0.80, 0.95))
            for aluno in self.rng.sample(alunos_com_jantar, qtd_comp_jan):
                hora = self._gerar_horario_aleatorio(17, 50, 19, 10)
                info = _info_reserva(data_str, aluno["matricula"]) or {}
                prato = info.get("prato") or self.rng.choice(PRATOS_JANTAR)
                cat_efetiva = self._categoria_efetiva_no_dia(aluno, data_str, cats_res_mapa)
                consumos_jantar.append([
                    aluno["matricula"],
                    data_str,
                    aluno["nome"],
                    aluno["turma"],
                    prato,
                    hora,
                    cat_efetiva,
                ])

            alunos_sem_jantar = [
                a for a in self.estudantes
                if not ((info := _info_reserva(data_str, a["matricula"])) and info.get("jantar"))
            ]
            if alunos_sem_jantar:
                qtd_excecao_jan = min(len(alunos_sem_jantar), self.rng.randint(1, 3))
                for aluno in self.rng.sample(alunos_sem_jantar, qtd_excecao_jan):
                    hora = self._gerar_horario_aleatorio(18, 20, 19, 5)
                    cat_efetiva = self._categoria_efetiva_no_dia(aluno, data_str, cats_res_mapa)
                    consumos_jantar.append([
                        aluno["matricula"],
                        data_str,
                        aluno["nome"],
                        aluno["turma"],
                        "Sem Reserva (Exceção)",
                        hora,
                        cat_efetiva,
                    ])

        # Ordenar cada refeição cronologicamente por (Data, Hora)
        for lista in (consumos_almoco, consumos_jantar, consumos_lanche):
            lista.sort(key=lambda item: (item[1], item[5]))

        return {
            "Almoço": consumos_almoco,
            "Jantar": consumos_jantar,
            "Lanche": consumos_lanche,
        }

    def gerar_cancelados(self, consumos_almoco: List[List[str]]) -> List[List[str]]:
        """
        Gera casos de auditoria de consumos cancelados a partir de uma amostra do almoço.
        Formato:
        [Data, Hora Original, Hora Cancelamento, Matrícula, Nome, Turma, Categoria, Refeição, Cancelado Por, Motivo]
        """
        linhas = []
        if not consumos_almoco:
            return linhas

        # Seleciona de 3 a 5 registros para simular cancelamentos
        qtd = min(len(consumos_almoco), self.rng.randint(3, 5))
        amostra = self.rng.sample(consumos_almoco, qtd)

        for c in amostra:
            matricula, data_str, nome, turma, refeicao, hora_orig, categoria = c
            # Hora cancelamento alguns segundos ou minutos depois
            h_orig_dt = datetime.strptime(hora_orig, "%H:%M:%S")
            delta_seg = self.rng.randint(45, 300)
            h_canc_dt = h_orig_dt + timedelta(seconds=delta_seg)
            hora_canc = h_canc_dt.strftime("%H:%M:%S")

            cancelado_por = self.rng.choice(OPERADORES_CANCELAMENTO)
            motivo = self.rng.choice(MOTIVOS_CANCELAMENTO)

            linhas.append([
                data_str,
                hora_orig,
                hora_canc,
                matricula,
                nome,
                turma,
                categoria,
                refeicao,
                cancelado_por,
                motivo,
            ])

        linhas.sort(key=lambda x: (x[0], x[2]))
        return linhas

    def _gerar_horario_aleatorio(self, h_ini: int, m_ini: int, h_fim: int, m_fim: int) -> str:
        """Gera um horário aleatório formatado HH:MM:SS dentro de um intervalo."""
        minuto_total_ini = h_ini * 60 + m_ini
        minuto_total_fim = h_fim * 60 + m_fim
        minuto_sorteado = self.rng.randint(minuto_total_ini, minuto_total_fim)
        segundo_sorteado = self.rng.randint(0, 59)
        h = minuto_sorteado // 60
        m = minuto_sorteado % 60
        return f"{h:02d}:{m:02d}:{segundo_sorteado:02d}"

    def gerar_massa_completa(
        self,
        dias_passados: int = 3,
        dias_futuros: int = 2,
    ) -> Dict[str, Tuple[List[str], List[List[str]]]]:
        """
        Retorna dicionário mapeando cada nome de aba para (cabeçalho, lista_de_linhas).
        """
        dias = self._obter_dias_uteis(date.today(), dias_passados, dias_futuros)

        # 1. Discentes
        linhas_discentes = self.gerar_estudantes()

        # 2. Configuração & Lanches
        linhas_config = self.gerar_configuracao()
        linhas_lanches = self.gerar_lanches()

        # 3. Reservas (DB)
        linhas_reservas = self.gerar_reservas(dias)
        mapa_reservas = {
            (r[0], r[1]): {
                "prato": r[4],
                "almoco": r[7] == "Sim",
                "jantar": r[8] == "Sim",
            }
            for r in linhas_reservas
        }
        mapa_cats_reservas = {
            (r[0], r[1]): [c.strip() for c in r[6].split(",") if c.strip()]
            for r in linhas_reservas
            if len(r) > 6 and r[6]
        }

        # 4. Consumos
        consumos = self.gerar_consumos(dias, mapa_reservas, mapa_cats_reservas)

        # 5. Cancelados
        linhas_cancelados = self.gerar_cancelados(consumos["Almoço"])

        return {
            NOME_ABA_ESTUDANTES: (CABECALHO_DISCENTES, linhas_discentes),
            NOME_ABA_CONFIGURACAO: (CABECALHO_CONFIGURACAO, linhas_config),
            NOME_ABA_LANCHES: (CABECALHO_LANCHES, linhas_lanches),
            NOME_ABA_RESERVAS: (CABECALHO_RESERVAS, linhas_reservas),
            "Almoço": (CABECALHO_EXPORTACAO, consumos["Almoço"]),
            "Jantar": (CABECALHO_EXPORTACAO, consumos["Jantar"]),
            "Lanche": (CABECALHO_EXPORTACAO, consumos["Lanche"]),
            NOME_ABA_CANCELADOS: (CABECALHO_CANCELADOS, linhas_cancelados),
        }


# -----------------------------------------------------------------------------
# Upload e Persistência
# -----------------------------------------------------------------------------

def fazer_upload_para_google_sheets(
    dados_massa: Dict[str, Tuple[List[str], List[List[str]]]],
    sobrescrever: bool = True,
) -> None:
    """
    Envia todos os dados gerados para a planilha Google Sheets configurada.
    """
    logger.info("Conectando ao Google Sheets...")
    servico = obter_servico_planilha_padrao()
    planilha = servico.planilha
    logger.info("Planilha conectada: '%s' (ID: %s)", planilha.title, planilha.id)

    # Garante que todas as abas existam
    servico.criar_abas_necessarias()
    worksheets = {ws.title: ws for ws in planilha.worksheets()}

    for nome_aba, (cabecalho, linhas) in dados_massa.items():
        aba = worksheets.get(nome_aba)
        if not aba:
            aba = planilha.worksheet(nome_aba)

        logger.info(
            "Atualizando aba '%s' com %d registros...",
            nome_aba,
            len(linhas),
        )

        if sobrescrever:
            # Substitui todo o conteúdo com cabeçalho + novas linhas
            linhas_completas = [cabecalho] + linhas
            aba.clear()
            aba.update(
                linhas_completas,
                value_input_option=ValueInputOption.user_entered,
            )
            try:
                aba.freeze(rows=1)
                aba.format("1:1", {"textFormat": {"bold": True}})
            except Exception:
                pass
        else:
            # Apenas anexa linhas únicas
            adicionados = servico.anexar_linhas_unicas(nome_aba, linhas)
            logger.info("Aba '%s': %d linhas anexadas.", nome_aba, adicionados)

    logger.info("Sucesso! Upload concluído para todas as abas.")


def salvar_amostra_local(
    dados_massa: Dict[str, Tuple[List[str], List[List[str]]]],
    diretorio_destino: Path,
) -> None:
    """Salva os dados gerados em arquivos CSV locais para inspeção."""
    import csv

    diretorio_destino.mkdir(parents=True, exist_ok=True)
    for nome_aba, (cabecalho, linhas) in dados_massa.items():
        caminho_csv = diretorio_destino / f"{nome_aba.lower().replace(' ', '_')}.csv"
        with open(caminho_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(cabecalho)
            writer.writerows(linhas)
    logger.info("Arquivos CSV locais salvos em: %s", diretorio_destino.resolve())


# -----------------------------------------------------------------------------
# Interface de Linha de Comando (CLI)
# -----------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera massa complexa de dados de teste e realiza upload para o Google Sheets."
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Realiza o upload direto dos dados para o Google Sheets configurado.",
    )
    parser.add_argument(
        "--sobrescrever",
        action="store_true",
        default=True,
        help="Sobrescreve os dados existentes nas abas, mantendo os cabeçalhos (padrão: True).",
    )
    parser.add_argument(
        "--anexar",
        action="store_true",
        help="Apenas anexa novos registros sem limpar dados existentes (anula --sobrescrever).",
    )
    parser.add_argument(
        "--qtd-alunos",
        type=int,
        default=60,
        help="Quantidade de discentes a serem gerados (padrão: 60).",
    )
    parser.add_argument(
        "--dias-passados",
        type=int,
        default=3,
        help="Quantidade de dias úteis anteriores a gerar (padrão: 3).",
    )
    parser.add_argument(
        "--dias-futuros",
        type=int,
        default=2,
        help="Quantidade de dias úteis futuros para reservas (padrão: 2).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Semente pseudoaleatória para reprodutibilidade dos dados (padrão: 42).",
    )
    parser.add_argument(
        "--salvar-local",
        type=str,
        default=None,
        help="Caminho do diretório para salvar cópia local em CSV (ex: 'dados_teste').",
    )

    args = parser.parse_args()

    sobrescrever = not args.anexar

    logger.info("Iniciando geração de dados de teste...")
    logger.info("Configuração: %d alunos, %d dias passados, %d dias futuros, seed=%d",
                args.qtd_alunos, args.dias_passados, args.dias_futuros, args.seed)

    gerador = GeradorDadosTeste(qtd_alunos=args.qtd_alunos, seed=args.seed)
    dados = gerador.gerar_massa_completa(
        dias_passados=args.dias_passados,
        dias_futuros=args.dias_futuros,
    )

    print("\n" + "=" * 60)
    print(" RESUMO DA MASSA DE DADOS GERADA")
    print("=" * 60)
    for aba, (cab, lin) in dados.items():
        print(f" • {aba:<20} : {len(lin):>4} registros (Colunas: {len(cab)})")
    print("=" * 60 + "\n")

    if args.salvar_local:
        salvar_amostra_local(dados, Path(args.salvar_local))

    if args.upload:
        fazer_upload_para_google_sheets(dados, sobrescrever=sobrescrever)
    else:
        logger.info(
            "Modo visualização concluído sem upload. Para enviar à planilha, utilize a flag --upload."
        )


if __name__ == "__main__":
    main()

