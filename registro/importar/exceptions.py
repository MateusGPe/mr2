# --- Arquivo: registro/importar/exceptions.py ---

"""Exceções customizadas para o módulo de importação."""


class ErroImportacao(Exception):
    """Classe base para exceções neste módulo."""


class ErroSessaoImportacao(ErroImportacao):
    """
    Erro para quando uma operação é tentada sem que a análise
    tenha sido iniciada.
    """
