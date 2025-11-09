# --- Arquivo: registro/nucleo/utils.py ---

"""
Funções utilitárias para a aplicação, incluindo manipulação de arquivos,
processamento de texto e tipos de dados customizados.
"""
import csv
import ctypes
import os
import platform
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, TypedDict

from fuzzywuzzy import fuzz

# --- Tipos de Dados ---

DADOS_SESSAO = TypedDict(
    "DADOS_SESSAO",
    {
        "refeicao": Literal["lanche", "almoço"],
        "item_servido": Optional[str],
        "periodo": Literal["Integral", "Matutino", "Vespertino", "Noturno"],
        "data": str,
        "hora": str,
        "grupos": List[str],
    },
)

# --- Constantes para Processamento de Texto ---

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
    """Encontra o par de strings com melhor correspondência em um vetor, ponderando o segundo item."""
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
    """Capitaliza uma string, com exceções para certas palavras (preposições, artigos)."""
    texto = texto.strip()
    if not texto:
        return ""
    texto_minusc = texto.lower()
    if texto_minusc in EXCECOES_CAPITALIZACAO:
        return texto_minusc
    return texto.capitalize()


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
                novo_valor = " ".join(
                    capitalizar_com_excecoes(p) for p in novo_valor.split()
                )
            elif nova_chave == "pront":
                novo_valor = re.sub(r"IQ\d{2}", "IQ30", novo_valor.upper())

        dicionario_ajustado[nova_chave] = novo_valor

    return dicionario_ajustado