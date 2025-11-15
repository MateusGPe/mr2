import regex as re
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
    "data": "data",
    "nome": "nome",
    "turma": "turma",
    "dia da semana": "dia_semana",
    "refeição": "prato",
}


def capitalizar_com_excecoes(texto: str) -> str:
    """Capitaliza uma string, com exceções para certas palavras (preposições, artigos)."""

    def fmt(palavra):
        palavra = palavra.strip()
        if not palavra:
            return ""
        texto_minusc = palavra.lower()
        if texto_minusc in EXCECOES_CAPITALIZACAO:
            return texto_minusc
        return palavra.capitalize()

    return " ".join(fmt(p) for p in texto.split())


def checar_prontuario(texto: Any) -> Optional[str]:
    """
    Verifica se o texto corresponde ao padrão de matrícula.
    (Padrão original do seu código, mais robusto a variações de prefixo).
    """
    if not texto or not isinstance(texto, str):
        return None
    texto = texto.strip().upper()
    return texto if (re.match(r"^[A-Za-z]{2}[a-zA-Z0-9]{7}$", texto)) else None


def checar_nome(texto: Any) -> Optional[str]:
    """
    Verifica se o texto parece ser um nome de pessoa.
    """
    if not texto or not isinstance(texto, str):
        return None

    texto_limpo = texto.strip()

    if " " not in texto_limpo:
        return None

    texto_limpo = capitalizar_com_excecoes(texto_limpo)

    if "Prato" in texto_limpo or "Vegeta" in texto_limpo or "Proteina" in texto_limpo:
        return None
    # Garante que a string inteira é composta apenas por letras e espaços.
    return texto_limpo if re.match(r"^[\p{L}\s]+$", texto_limpo) else None


def checar_data(texto_data: Any) -> Optional[str]:
    """
    Detecta uma data em vários formatos e retorna a data em 'dd/mm/aaaa' ou None.
    """
    if not texto_data or not isinstance(texto_data, str):
        return None

    texto_limpo = texto_data.strip()
    formatos_para_tentar = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d"]
    for formato in formatos_para_tentar:
        try:
            data_obj = datetime.strptime(texto_limpo, formato)

            return data_obj.strftime("%d/%m/%Y")
        except ValueError:
            continue
    return None


def checar_turma(texto: Any) -> Optional[str]:
    """
    Verifica se o texto corresponde ao padrão de turma.
    (Padrão original do seu código, mais flexível a diferentes formatos).
    """
    if not texto or not isinstance(texto, str):
        return None
    # Expressão regular para validar o formato da turma (case-insensitive para letras).
    texto = texto.strip()

    return (
        texto
        if re.match(r"^[A-Z\d]+[ºª]\s[A-Z]\s-\s[A-Z]{3}$", texto, re.IGNORECASE)
        else None
    )


def checar_dia_semana(texto: Any) -> Optional[str]:
    """Verifica se o texto é um dia da semana válido."""
    if not texto or not isinstance(texto, str):
        return None
    dias_semana = {
        "segunda-feira",
        "terça-feira",
        "quarta-feira",
        "quinta-feira",
        "sexta-feira",
        "sábado",
        "domingo",
    }
    res = texto.strip().lower()
    return res if res in dias_semana else None


def detectar_tipo_coluna(
    amostra_coluna: Sequence[str], limiar: float = 0.85
) -> Optional[str]:
    """
    Detecta o tipo de dado de uma coluna, seguindo a ordem do mais específico
    para o mais genérico para evitar falsos positivos.

    Args:
        amostra_coluna: Uma lista de strings como amostra dos dados da coluna.
        limiar: Percentual mínimo de correspondência para definir um tipo (padrão 85%).

    Returns:
        O nome padronizado do tipo de dado (ex: "pront", "data", "nome").
    """
    if not amostra_coluna:
        return None

    amostra_valida = [str(v) for v in amostra_coluna if v and str(v).strip()]
    total_valores = len(amostra_valida)
    if total_valores == 0:
        return None

    verificadores = {
        "matrícula": checar_prontuario,
        "data": checar_data,
        "nome": checar_nome,
        "dia da semana": checar_dia_semana,
        "turma": checar_turma,
    }

    for nome_tipo, funcao_verificacao in verificadores.items():
        correspondencias = sum(
            1 for valor in amostra_valida if funcao_verificacao(valor)
        )
        if (correspondencias / total_valores) >= limiar:
            return MAPEAMENTO_CHAVES.get(nome_tipo, None)

    return None


def detectar_tipo_valor(valor: Optional[str]) -> tuple[Optional[str], ...]:
    """
    Detecta o tipo de dado de um valor, seguindo a ordem do mais específico
    para o mais genérico para evitar falsos positivos.

    Args:
        valor: Um string com o valor a ser analisado.

    Returns:
        O nome padronizado do tipo de dado (ex: "pront", "data", "nome").
    """
    if not valor or len(valor) == 0:
        return None, None

    verificadores = {
        "matrícula": checar_prontuario,
        "data": checar_data,
        "nome": checar_nome,
        "dia da semana": checar_dia_semana,
        "turma": checar_turma,
    }

    for nome_tipo, funcao_verificacao in verificadores.items():
        if res := funcao_verificacao(valor):
            return MAPEAMENTO_CHAVES.get(nome_tipo, ""), res

    return "prato", valor


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
            if nova_chave in ["nome", "prato", "dia_semana"]:
                novo_valor = capitalizar_com_excecoes(novo_valor)
            elif nova_chave == "pront":
                novo_valor = novo_valor.upper()
        dicionario_ajustado[nova_chave] = novo_valor

    return dicionario_ajustado
