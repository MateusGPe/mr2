"""Exceções customizadas para o módulo de importação."""


class ErroImportacao(Exception):
    """Classe base para exceções neste módulo."""


class ErroSessaoImportacao(ErroImportacao):
    """Erro operado quando o fluxo da sessão de importação é violado."""