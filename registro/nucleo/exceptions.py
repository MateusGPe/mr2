# --- Arquivo: registro/nucleo/exceptions.py ---

"""Exceções customizadas para a camada de serviço."""


class ErroNucleoRegistro(Exception):
    """Classe base para exceções neste módulo."""


class ErroSessao(ErroNucleoRegistro):
    """Erro relacionado ao gerenciamento de sessões de refeição."""


class ErroSessaoNaoAtiva(ErroSessao):
    """
    Erro para quando uma operação requer uma sessão ativa,
    mas não há nenhuma.
    """


class ErroImportacaoDados(ErroNucleoRegistro):
    """Erro durante a importação de dados de arquivos (CSV, etc.)."""


class ErroAPIGoogle(ErroNucleoRegistro):
    """Erro na comunicação com as APIs do Google (Sheets, Drive)."""