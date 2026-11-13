# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/utils.py (Utilitários do Núcleo)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>


"""
Funções utilitárias para a aplicação, incluindo manipulação de arquivos,
processamento de texto e tipos de dados customizados.
"""

import csv
import json
import logging
import os
import platform
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, TypedDict, Union

from fuzzywuzzy import fuzz
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def rollback_seguro(sessao: Any, contexto: str = "") -> None:
    """Executa rollback da sessão SQLAlchemy de forma segura, registrando falhas."""
    try:
        sessao.rollback()
    except SQLAlchemyError as e:
        sufixo = f" ({contexto})" if contexto else ""
        logger.warning("Falha ao executar rollback da sessão%s: %s", sufixo, e)


DADOS_SESSAO = TypedDict(
    "DADOS_SESSAO",
    {
        "refeicao": Literal["lanche", "almoço", "jantar"],
        "item_servido": Optional[str],
        "periodo": Literal["Integral", "Matutino", "Vespertino", "Noturno"],
        "data": str,
        "hora": str,
        "grupos": List[str],
    },
)


DICIONARIO_TRADUCAO_PRONTUARIO = str.maketrans("0123456789Xx", "abcdefghijkk")
REGEX_REMOVER_IQ = re.compile(r"[Ii][Qq]\d0+")
EXCECOES_CAPITALIZACAO = {
    "a",
    "o",
    "as",
    "os",
    "de",
    "dos",
    "das",
    "do",
    "da",
    "e",
    "é",
    "com",
    "sem",
    "ou",
    "para",
    "por",
    "no",
    "na",
    "nos",
    "nas",
}
MAPEAMENTO_CHAVES = {
    "matrícula iq": "pront",
    "matrícula": "pront",
    "prontuário": "pront",
    "refeição": "prato",
    "categoria": "categoria",
    "tag": "categoria",
    "tags": "categoria",
    "almoço": "almoco",
    "almoco": "almoco",
    "jantar": "jantar",
    "janta": "jantar",
    "turno": "turno",
    "turnos": "turno",
    "tipo": "turno",
    "tipo refeição": "turno",
    "tipo de refeição": "turno",
    "tipo_refeicao": "turno",
}


def para_codigo(texto: str) -> Dict[str, str]:
    """Traduz o prontuário para um código de busca simplificado."""
    texto_processado = REGEX_REMOVER_IQ.sub("", texto)
    traduzido = texto_processado.translate(DICIONARIO_TRADUCAO_PRONTUARIO)
    return {"id": " ".join(traduzido)}


def obter_caminho_documentos() -> Path:
    """Retorna o caminho para a pasta 'Documentos' do usuário de forma segura."""
    if platform.system() == "Windows":
        try:
            import ctypes
            import ctypes.wintypes

            CSIDL_PERSONAL = 5
            SHGFP_TYPE_CURRENT = 0
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(
                None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf
            )
            return Path(buf.value)
        except (AttributeError, OSError):
            return Path.home() / "Documents"

    # Para Linux, macOS e outros Unix-like
    if xdg_documents := os.environ.get("XDG_DOCUMENTS_DIR"):
        return Path(xdg_documents.strip('"'))

    caminho_pt = Path.home() / "Documentos"
    if caminho_pt.is_dir():
        return caminho_pt

    return Path.home() / "Documents"


def salvar_csv(dados: list, caminho_arquivo: Path) -> bool:
    """Salva uma lista de listas em um arquivo CSV."""
    try:
        with open(caminho_arquivo, "w", newline="", encoding="utf-8") as arquivo_csv:
            escritor = csv.writer(arquivo_csv)
            escritor.writerows(dados)
        return True
    except (IOError, csv.Error) as e:
        print(f"Erro ao salvar CSV em '{caminho_arquivo}': {e}", file=sys.stderr)
        return False


def encontrar_melhor_par_correspondente(
    par_alvo: Tuple[str, str],
    vetor_de_pares: List[Tuple[str, str]],
    funcao_pontuacao: Callable[[str, str], int] = fuzz.ratio,
) -> Tuple[Optional[Tuple[str, str]], int]:
    """Encontra o par de strings com melhor correspondência em um vetor,
    ponderando o segundo item."""
    if not vetor_de_pares:
        return None, 0

    melhor_correspondencia = None
    maior_pontuacao = -1.0

    alvo1, alvo2 = par_alvo
    for par in vetor_de_pares:
        vetor1, vetor2 = par

        pontuacao1 = funcao_pontuacao(alvo1, vetor1)
        pontuacao2 = funcao_pontuacao(alvo2, vetor2)

        # Pondera a segunda string (nome) como mais importante
        pontuacao_geral = (pontuacao1 + 2 * pontuacao2) / 3

        if pontuacao_geral > maior_pontuacao:
            maior_pontuacao = pontuacao_geral
            melhor_correspondencia = par

    return melhor_correspondencia, int(maior_pontuacao)


def capitalizar_com_excecoes(texto: str) -> str:
    """Capitaliza uma string (palavra única ou frase), respeitando preposições e artigos."""
    if not texto or not isinstance(texto, str):
        return ""

    def _fmt(palavra: str) -> str:
        palavra_minusc = palavra.lower()
        if palavra_minusc in EXCECOES_CAPITALIZACAO:
            return palavra_minusc
        return palavra.capitalize()

    return " ".join(_fmt(p) for p in texto.split() if p)


def ajustar_chaves_e_valores(dicionario_entrada: Dict) -> Dict:
    """Ajusta chaves e valores de um dicionário de acordo com regras de negócio."""
    dicionario_ajustado = {}
    for chave, valor in dicionario_entrada.items():
        nova_chave = chave
        novo_valor = valor

        if isinstance(chave, str):
            nova_chave = chave.strip().lower()
            nova_chave = MAPEAMENTO_CHAVES.get(nova_chave, nova_chave)

        if isinstance(valor, str):
            novo_valor = valor.strip()
            if nova_chave in ["nome", "prato"]:
                novo_valor = capitalizar_com_excecoes(novo_valor)
            elif nova_chave == "pront":
                novo_valor = re.sub(r"IQ\d{2}", "IQ30", novo_valor.upper())

        dicionario_ajustado[nova_chave] = novo_valor

    return dicionario_ajustado


def carregar_json(nome_arquivo: Union[str, Path]) -> Optional[Any]:
    """Carrega dados de um arquivo JSON de forma segura."""
    logger.debug("Carregando JSON de: %s", nome_arquivo)
    try:
        with open(nome_arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        logger.error("Erro ao carregar JSON de %s: %s", nome_arquivo, e)
        return None


def salvar_json(nome_arquivo: Union[str, Path], dados: Union[Dict, List, Any]) -> bool:
    """Salva dados em um arquivo JSON com formatação legível."""
    logger.debug("Salvando JSON em: %s", nome_arquivo)
    try:
        caminho = Path(nome_arquivo)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        return True
    except (OSError, TypeError, ValueError) as e:
        logger.error("Erro ao salvar JSON em %s: %s", nome_arquivo, e)
        return False


def carregar_csv_como_dict(
    nome_arquivo: Union[str, Path],
) -> Optional[List[Dict[str, str]]]:
    """Lê um arquivo CSV e o retorna como uma lista de dicionários."""
    logger.debug("Carregando CSV como dict de: %s", nome_arquivo)
    try:
        with open(nome_arquivo, "r", newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except (OSError, csv.Error, UnicodeDecodeError) as e:
        logger.error("Erro ao ler CSV de %s: %s", nome_arquivo, e)
        return None


def salvar_csv_de_lista(
    dados: List[List[Any]], nome_arquivo: Union[str, Path], **kwargs
) -> bool:
    """Salva uma lista de listas em um arquivo CSV."""
    logger.debug("Salvando lista para CSV: %s", nome_arquivo)
    if not dados:
        logger.warning("Nenhum dado para salvar em: %s.", nome_arquivo)
        return True
    try:
        caminho = Path(nome_arquivo)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, **kwargs)
            writer.writerows(dados)
        logger.info("%s linhas salvas no CSV: %s", len(dados), nome_arquivo)
        return True
    except (OSError, csv.Error, TypeError) as e:
        logger.error("Erro ao salvar CSV em %s: %s", nome_arquivo, e)
        return False


_CATEGORIAS_IGNORADAS = {"", "-", "n/a", "regular", "none", "null", "nenhuma"}


def normalizar_lista_categorias(valor: Any) -> List[str]:
    """
    Converte uma string separada por vírgula/ponto-e-vírgula ou iterável
    em uma lista limpa e sem duplicatas de nomes de categorias/tags.
    Ignora marcadores vazios ou legados como 'REGULAR' e '-'.
    """
    if not valor:
        return []

    itens_brutos: List[str] = []
    if isinstance(valor, str):
        itens_brutos = re.split(r"[,;]", valor)
    elif isinstance(valor, (list, tuple, set)):
        for elem in valor:
            if isinstance(elem, str):
                itens_brutos.extend(re.split(r"[,;]", elem))
            elif elem is not None:
                itens_brutos.append(str(elem))
    else:
        itens_brutos = re.split(r"[,;]", str(valor))

    resultado: List[str] = []
    vistos_lower: set[str] = set()
    for item in itens_brutos:
        limpo = item.strip()
        chave = limpo.lower()
        if chave in _CATEGORIAS_IGNORADAS or chave in vistos_lower:
            continue
        vistos_lower.add(chave)
        resultado.append(limpo)
    return resultado


def extrair_turmas_e_categorias(
    estudante: Any, reserva: Any = None
) -> Tuple[List[str], List[str]]:
    """
    Separa os grupos do estudante (e opcionalmente de uma reserva ativa na data)
    em duas listas ordenadas: (turmas_reais, categorias).
    """
    turmas: set[str] = set()
    categorias: set[str] = set()

    grupos_est = getattr(estudante, "grupos", None) or []
    for g in grupos_est:
        if getattr(g, "eh_categoria", False):
            categorias.add(g.nome)
        else:
            turmas.add(g.nome)

    if reserva is not None and not getattr(reserva, "cancelada", False):
        grupos_res = getattr(reserva, "grupos", None) or []
        for g in grupos_res:
            if getattr(g, "eh_categoria", False):
                categorias.add(g.nome)
            else:
                turmas.add(g.nome)

    return sorted(turmas), sorted(categorias)


def formatar_turma_e_categoria(
    estudante: Any, reserva: Any = None, turma_vazia: str = "N/A"
) -> Tuple[str, str]:
    """Retorna strings formatadas (turmas_str, categorias_str) para exibição/exportação."""
    turmas, categorias = extrair_turmas_e_categorias(estudante, reserva)
    turmas_str = ", ".join(turmas) if turmas else turma_vazia
    cats_str = ", ".join(categorias) if categorias else "-"
    return turmas_str, cats_str


_VALORES_VERDADEIROS = {
    "1",
    "true",
    "sim",
    "s",
    "yes",
    "y",
    "x",
    "ok",
    "ativo",
    "ativa",
}
_VALORES_FALSOS = {"0", "false", "nao", "não", "n", "no", "inativo", "inativa"}


def interpretar_booleano(valor: Any, padrao: Optional[bool] = None) -> Optional[bool]:
    """Converte representações comuns de texto/número em bool, retornando `padrao` se vazio/inválido."""
    if valor is None:
        return padrao
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        return bool(valor)
    texto = str(valor).strip().lower()
    if not texto:
        return padrao
    if texto in _VALORES_VERDADEIROS:
        return True
    if texto in _VALORES_FALSOS:
        return False
    return padrao


def _normalizar_texto_turno(texto: str) -> str:
    """Remove acentuação básica de almoço/jantar para comparação uniforme."""
    return (
        texto.strip()
        .lower()
        .replace("ç", "c")
        .replace("ã", "a")
        .replace("á", "a")
        .replace("â", "a")
    )


def resolver_turnos_reserva(
    dados: Dict[str, Any],
    default_almoco: bool = True,
    default_jantar: bool = False,
) -> Tuple[bool, bool]:
    """
    Resolve os flags (almoco, jantar) de um dicionário de reserva/importação.
    Suporta chaves booleanas (`almoco`/`almoço`, `jantar`) e/ou coluna textual `turno`/`tipo_refeicao`.
    Colunas explícitas prevalecem sobre os defaults informados.
    """
    alm_raw = dados.get("almoco") if "almoco" in dados else dados.get("almoço")
    jan_raw = dados.get("jantar")
    turno_raw = (
        dados.get("turno")
        if dados.get("turno") not in (None, "")
        else dados.get("tipo_refeicao")
    )

    alm_parsed = interpretar_booleano(alm_raw, padrao=None)
    jan_parsed = interpretar_booleano(jan_raw, padrao=None)

    turno_alm: Optional[bool] = None
    turno_jan: Optional[bool] = None
    if turno_raw is not None and str(turno_raw).strip():
        t_norm = _normalizar_texto_turno(str(turno_raw))
        if t_norm in {
            "ambos",
            "ambas",
            "todos",
            "todas",
            "almoco e jantar",
            "almoco/jantar",
            "almoco, jantar",
        }:
            turno_alm, turno_jan = True, True
        else:
            tem_alm = "almoco" in t_norm
            tem_jan = "jantar" in t_norm or "janta" in t_norm
            if tem_alm or tem_jan:
                turno_alm = tem_alm
                turno_jan = tem_jan

    if alm_parsed is not None or jan_parsed is not None:
        almoco = (
            alm_parsed
            if alm_parsed is not None
            else (turno_alm if turno_alm is not None else default_almoco)
        )
        jantar = (
            jan_parsed
            if jan_parsed is not None
            else (turno_jan if turno_jan is not None else default_jantar)
        )
        return bool(almoco), bool(jantar)

    if turno_alm is not None and turno_jan is not None:
        return turno_alm, turno_jan

    return bool(default_almoco), bool(default_jantar)


def formatar_turnos_reserva(almoco: bool, jantar: bool) -> str:
    """Retorna rótulo legível para os turnos de uma reserva."""
    if almoco and jantar:
        return "Almoço e Jantar"
    if almoco:
        return "Almoço"
    if jantar:
        return "Jantar"
    return "-"
