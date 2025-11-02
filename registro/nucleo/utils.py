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
from typing import Any, Callable, List, Literal, Optional, Tuple, TypedDict

from fuzzywuzzy import fuzz

CSIDL_PERSONAL: int = 5
SHGFP_TYPE_CURRENT: int = 0

SESSION = TypedDict(
    'SESSION',
    {
        'refeicao': Literal["lanche", "almoço"],
        'item_servido': Optional[str],
        'periodo': Literal["Integral", "Matutino", "Vespertino", "Noturno"],
        'data': str,
        'hora': str,
        'grupos': List[str],
    })
TRANSLATE_DICT = str.maketrans("0123456789Xx", "abcdefghijkk")
REMOVE_IQ = re.compile(r"[Ii][Qq]\d0+")


def to_code(text: str) -> dict[str, str]:
    """Traduz o prontuário para um código de busca simplificado."""
    text = REMOVE_IQ.sub("", text)
    translated = text.translate(TRANSLATE_DICT)
    return {"id": " ".join(translated)}


def get_documents_path() -> str:
    """Retorna o caminho para a pasta 'Documentos' do usuário."""
    if platform.system() == "Windows":
        try:
            buf = ctypes.create_unicode_buffer(getattr(ctypes, 'wintypes').MAX_PATH)
            getattr(ctypes, "windll").shell32.SHGetFolderPathW(
                None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf
            )
            return buf.value
        except (AttributeError, OSError):
            return os.path.expanduser("~/Documents")
    elif platform.system() == "Linux":
        xdg_documents = os.environ.get("XDG_DOCUMENTS_DIR")
        if xdg_documents:
            return xdg_documents.strip('"')
    return os.path.expanduser("~/Documents")


def save_csv(data: list, filename: str) -> bool:
    """Salva dados em um arquivo CSV."""
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(data)
        return True
    except (IOError, csv.Error) as e:
        print(f"Error saving CSV to '{filename}': {e}", file=sys.stderr)
        return False


def find_best_matching_pair(
    target_pair: Tuple, vector_of_pairs: List[Tuple],
    score_function: Callable[[Any, Any], int] = fuzz.ratio
) -> Tuple[Optional[Tuple[str, str]], int]:
    """Encontra o par de strings com melhor correspondência em um vetor."""
    if not vector_of_pairs:
        return None, 0

    best_match = None
    highest_score = -1

    for pair in vector_of_pairs:
        string1_target, string2_target = target_pair
        string1_vector, string2_vector = pair

        score1 = score_function(string1_target, string1_vector)
        score2 = score_function(string2_target, string2_vector)
        overall_score = (score1 + 2 * score2) / 3

        if overall_score > highest_score:
            highest_score = overall_score
            best_match = pair

    return best_match, int(highest_score)


CAPITALIZE_EXCEPTIONS = {
    "a", "o", "as", "os", "de", "dos", "das", "do", "da", "e", "é", "com",
    "sem", "ou", "para", "por", "no", "na", "nos", "nas"
}

TRANSLATE_KEYS = {
    'matrícula iq': 'pront',
    'matrícula': 'pront',
    'prontuário': 'pront',
    'refeição': 'prato'
}


def capitalize(text: str) -> str:
    """Capitaliza uma string, com exceções para certas palavras."""
    text = text.strip()
    if not text:
        return ""
    ltext = text.lower()
    if ltext in CAPITALIZE_EXCEPTIONS:
        return ltext
    return text[0].upper() + ltext[1:]


def adjust_keys(input_dict: dict) -> dict:
    """Ajusta chaves e valores de um dicionário de acordo com regras."""
    adjusted_dict = {}
    for key, value in input_dict.items():
        if isinstance(key, str):
            key = key.strip().lower()
            key = TRANSLATE_KEYS.get(key, key)
            if isinstance(value, str):
                value = value.strip()

            if key in ["nome", "prato"]:
                value = " ".join(capitalize(v) for v in value.split(" "))
            elif key == "pront":
                value = re.sub(r'IQ\d{2}', 'IQ30', value.upper())
            else:
                value = value.strip()

            adjusted_dict[key] = value
        else:
            adjusted_dict[key] = value
    return adjusted_dict
