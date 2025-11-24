"""
Funções utilitárias para detecção de padrões e tipos de dados em strings.
Utilizado para inferir colunas em arquivos sem cabeçalho.
"""

import re
from datetime import datetime
from typing import Any, Dict, Optional, Sequence

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
    "matrícula iq": "prontuario",
    "matrícula": "prontuario",
    "prontuário": "prontuario",
    "pront": "prontuario",
    "data": "data",
    "nome": "nome",
    "aluno": "nome",
    "estudante": "nome",
    "turma": "turma",
    "grupo": "turma",
    "dia da semana": "dia_semana",
    "refeição": "prato",
}


def capitalizar_com_excecoes(texto: str) -> str:
    """Capitaliza texto respeitando preposições."""

    def fmt(palavra):
        palavra = palavra.strip()
        if not palavra:
            return ""
        if palavra.lower() in EXCECOES_CAPITALIZACAO:
            return palavra.lower()
        return palavra.capitalize()

    return " ".join(fmt(p) for p in texto.split())


def checar_prontuario(texto: Any) -> Optional[str]:
    """Verifica se o texto parece um prontuário (Ex: AB1234567)."""
    if not texto or not isinstance(texto, str):
        return None
    texto = texto.strip().upper()
    # Regex ajustada para maior tolerância (2 letras + digitos)
    if re.match(r"^[A-Z]{2,3}[\dX]{5,9}$", texto):
        return texto
    return None


def checar_nome(texto: Any) -> Optional[str]:
    """Verifica se o texto parece ser um nome de pessoa."""
    if not texto or not isinstance(texto, str):
        return None
    texto_limpo = texto.strip()
    if " " not in texto_limpo or any(char.isdigit() for char in texto_limpo):
        return None

    palavras_invalidas = ["prato", "vegetariano", "proteina", "refeição"]
    if any(p in texto_limpo.lower() for p in palavras_invalidas):
        return None

    return capitalizar_com_excecoes(texto_limpo)


def obter_data(texto_data: Any) -> Optional[datetime]:
    """Tenta converter string para data DD/MM/AAAA."""
    if not texto_data or not isinstance(texto_data, str):
        return None
    texto_limpo = texto_data.strip()[:10]  # Pega apenas a data se tiver hora
    formatos = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d", "%m/%d/%y", "%m-%d-%y"]

    for fmt in formatos:
        try:
            data_obj = datetime.strptime(texto_limpo, fmt)
            return data_obj
        except ValueError:
            continue
    return None


def checar_data(texto_data: Any) -> Optional[str]:
    """Tenta converter string para data DD/MM/AAAA."""
    data_obj = obter_data(texto_data)
    return data_obj.strftime("%d/%m/%Y") if data_obj else None


def checar_turma(texto: Any) -> Optional[str]:
    """Valida formato comum de turma (Ex: 1º A - EMI)."""
    if not texto or not isinstance(texto, str):
        return None
    texto = texto.strip()
    # Regex genérica para turmas
    if re.search(r"\d+[ºª].*[A-Z]", texto, re.IGNORECASE):
        return texto
    return None


def detectar_tipo_coluna(
    amostra_coluna: Sequence[str], limiar: float = 0.80
) -> Optional[str]:
    """
    Analisa verticalmente uma lista de valores para inferir o tipo da coluna.
    Retorna a chave padronizada (ex: 'prontuario', 'data') ou None.
    """
    amostra_valida = [v for v in amostra_coluna if v and str(v).strip()]
    total = len(amostra_valida)
    if total == 0:
        return None

    verificadores = {
        "prontuario": checar_prontuario,
        "data": checar_data,
        "nome": checar_nome,
        "turma": checar_turma,
    }

    for tipo, funcao in verificadores.items():
        matches = sum(1 for v in amostra_valida if funcao(v))
        if (matches / total) >= limiar:
            return tipo
    return None


def ajustar_chaves_e_valores(dicionario_entrada: Dict) -> Dict:
    """Normaliza chaves e valores de um dicionário."""
    dicionario_ajustado = {}
    for chave, valor in dicionario_entrada.items():
        nova_chave = str(chave).strip().lower()
        nova_chave = MAPEAMENTO_CHAVES.get(nova_chave, nova_chave)

        novo_valor = valor
        if isinstance(valor, str):
            novo_valor = valor.strip()
            if nova_chave in ["nome", "prato"]:
                novo_valor = capitalizar_com_excecoes(novo_valor)
            elif nova_chave == "prontuario":
                novo_valor = novo_valor.upper()
            elif nova_chave == "data":
                data_fmt = checar_data(novo_valor)
                if data_fmt:
                    novo_valor = data_fmt

        dicionario_ajustado[nova_chave] = novo_valor

    return dicionario_ajustado
