# ----------------------------------------------------------------------------
# Arquivo: registro/launcher.py (Despachante e Menu Inicial)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Despachante principal e menu inicial unificado da aplicação.
Permite iniciar Registrar, Painel ou Autoatendimento via flags de linha
de comando (--painel, /painel, --auto, /auto, --reg, /reg) ou via
um menu gráfico se executado sem parâmetros (duplo clique).
"""

import os
import sys
from pathlib import Path
from typing import Callable, List, Optional

# Garante que o diretório de trabalho seja o do executável quando empacotado pelo PyInstaller
if getattr(sys, "frozen", False):
    os.chdir(Path(sys.executable).parent)


def executar_registrar() -> None:
    """Inicia o módulo de Registro de Refeições."""
    from registro.gui.registrar.app import main as app_main

    app_main()


def executar_painel() -> None:
    """Inicia o módulo do Painel Administrativo."""
    from registro.gui.painel.app import main as app_main

    app_main()


def executar_autoatendimento() -> None:
    """Inicia o módulo de Autoatendimento / Totem."""
    from registro.gui.autoatendimento.app import main as app_main

    app_main()


def executar_setup() -> None:
    """Inicia a Central de Configurações e Início Rápido."""
    from registro.gui.setup.app import main as app_main

    app_main()


def exibir_ajuda() -> None:
    """Exibe mensagem de ajuda no console ou caixa de diálogo gráfica."""
    msg = (
        "Sistema de Registro de Refeições\n\n"
        "Uso: registro.exe [OPÇÃO]\n\n"
        "Opções disponíveis:\n"
        "  --reg, /reg, --registrar, /registrar       Abre o Registro de Refeições\n"
        "  --painel, /painel                          Abre o Painel Administrativo\n"
        "  --auto, /auto, --autoatendimento           Abre o Totem de Autoatendimento\n"
        "  --setup, /setup, --config, /config         Abre as Configurações / Início Rápido\n"
        "  --help, /help, /?                          Exibe esta tela de ajuda\n\n"
        "Sem argumentos: Abre o menu gráfico inicial para seleção."
    )
    try:
        from ttkbootstrap.dialogs import Messagebox

        Messagebox.show_info(msg, title="Ajuda - Registro de Refeições")
    except Exception:
        print(msg)


def identificar_alvo_cli(args: List[str]) -> Optional[Callable[[], None]]:
    """Identifica o módulo solicitado via argumentos de linha de comando."""
    args_normalizados = [arg.strip().lower() for arg in args]

    for arg in args_normalizados:
        if arg in ("--painel", "/painel", "-painel", "painel"):
            return executar_painel
        if arg in (
            "--auto",
            "/auto",
            "-auto",
            "auto",
            "--autoatendimento",
            "/autoatendimento",
            "autoatendimento",
        ):
            return executar_autoatendimento
        if arg in (
            "--reg",
            "/reg",
            "-reg",
            "reg",
            "--registrar",
            "/registrar",
            "registrar",
        ):
            return executar_registrar
        if arg in (
            "--setup",
            "/setup",
            "-setup",
            "setup",
            "--config",
            "/config",
            "-config",
            "config",
            "--quickstart",
            "/quickstart",
            "quickstart",
        ):
            return executar_setup
        if arg in ("--help", "/help", "-h", "/?", "help"):
            exibir_ajuda()
            sys.exit(0)

    return None


def abrir_menu_inicial() -> Optional[Callable[[], None]]:
    """
    Exibe a janela de seleção inicial do módulo.
    Retorna a função de inicialização do app escolhido, ou None se a janela for fechada.
    """
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import CENTER, X

    escolha: List[Optional[Callable[[], None]]] = [None]

    root = ttk.Window(
        title="Registro de Refeições",
        themename="sandstone",
        resizable=(False, False),
    )
    largura = 520
    altura = 530

    root.update_idletasks()
    x = max(0, (root.winfo_screenwidth() // 2) - (largura // 2))
    y = max(0, (root.winfo_screenheight() // 2) - (altura // 2))
    root.geometry(f"{largura}x{altura}+{x}+{y}")

    def selecionar(func: Callable[[], None]) -> None:
        escolha[0] = func
        root.destroy()

    container = ttk.Frame(root, padding=25)
    container.pack(fill="both", expand=True)

    lbl_titulo = ttk.Label(
        container,
        text="🍽️ Sistema de Refeitório",
        font=("Segoe UI", 16, "bold"),
        anchor=CENTER,
    )
    lbl_titulo.pack(fill=X, pady=(0, 4))

    lbl_sub = ttk.Label(
        container,
        text="Selecione o módulo que deseja iniciar:",
        font=("Segoe UI", 10),
        bootstyle="secondary",
        anchor=CENTER,
    )
    lbl_sub.pack(fill=X, pady=(0, 20))

    btn_registrar = ttk.Button(
        container,
        text="📝  Registrar Refeições\nControle e registro de consumo em tempo real",
        bootstyle="primary-outline",
        command=lambda: selecionar(executar_registrar),
        cursor="hand2",
    )
    btn_registrar.pack(fill=X, pady=5, ipady=5)

    btn_painel = ttk.Button(
        container,
        text="📊  Painel Administrativo\nGestão de alunos, turmas, reservas e relatórios",
        bootstyle="info-outline",
        command=lambda: selecionar(executar_painel),
        cursor="hand2",
    )
    btn_painel.pack(fill=X, pady=5, ipady=5)

    btn_auto = ttk.Button(
        container,
        text="🤖  Totem de Autoatendimento\nTerminal autônomo com leitor de QR Code / câmera",
        bootstyle="success-outline",
        command=lambda: selecionar(executar_autoatendimento),
        cursor="hand2",
    )
    btn_auto.pack(fill=X, pady=5, ipady=5)

    btn_setup = ttk.Button(
        container,
        text="⚙️  Configurações & Início Rápido\nGoogle Cloud, PIN de segurança, backups e atalhos",
        bootstyle="secondary-outline",
        command=lambda: selecionar(executar_setup),
        cursor="hand2",
    )
    btn_setup.pack(fill=X, pady=5, ipady=5)

    lbl_dica = ttk.Label(
        container,
        text="Dica: Em atalhos, use as flags /painel, /auto, /reg ou /setup para abrir direto.",
        font=("Segoe UI", 8),
        bootstyle="secondary",
        anchor=CENTER,
    )
    lbl_dica.pack(fill=X, side="bottom", pady=(15, 0))

    root.mainloop()
    return escolha[0]


def main() -> None:
    """Ponto de entrada unificado para execução da aplicação."""
    from registro.nucleo.logging_config import configurar_logging

    configurar_logging("launcher")
    alvo = identificar_alvo_cli(sys.argv[1:])
    if alvo is None:
        alvo = abrir_menu_inicial()

    if alvo is not None:
        alvo()


if __name__ == "__main__":
    main()
