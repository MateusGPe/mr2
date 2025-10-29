"""
Interface de Usuário de Terminal (TUI) interativa e amigável para o sistema
de registro de refeições.

Versão 2.0 - Corrigida e com persistência de sessão.
"""
import json
import os
import sys
from typing import Dict, List, Optional, Callable

import questionary
from rich.console import Console
from rich.table import Table

from registro.nucleo.exceptions import RegistrationCoreError, SessionError
from registro.nucleo.facade import RegistroFacade
from registro.nucleo.utils import SESSION as SessionData

# Arquivo para salvar o ID da última sessão ativa
SESSION_STATE_FILE = ".session_state.json"


class AppTUI:
    """Encapsula a lógica e o estado da aplicação de terminal."""

    def __init__(self):
        self.facade: Optional[RegistroFacade] = None
        self.console = Console()
        self.active_session_details: Optional[Dict] = None

    def run(self):
        """Inicia o loop principal da aplicação."""
        try:
            self.facade = RegistroFacade()
            self.console.print("[bold cyan]Bem-vindo ao Sistema de Registro de Refeições[/bold cyan]")
            self._load_last_session()

            while True:
                self._show_main_menu()

        except RegistrationCoreError as e:
            self.console.print(f"[bold red]Erro crítico na inicialização: {e}[/bold red]")
            self.shutdown()
        except (KeyboardInterrupt, TypeError):
            self.shutdown()
        finally:
            if self.facade:
                self._save_last_session()
                self.facade.close()

    def shutdown(self):
        """Encerra a aplicação de forma limpa."""
        self.console.print("\n[yellow]Encerrando a aplicação...[/yellow]")
        sys.exit(0)

    # --- Gerenciamento de Estado da Sessão ---

    def _load_last_session(self):
        """Carrega a última sessão ativa a partir de um arquivo de estado."""
        if os.path.exists(SESSION_STATE_FILE):
            try:
                with open(SESSION_STATE_FILE, "r") as f:
                    state = json.load(f)
                    session_id = state.get("active_session_id")
                    if session_id:
                        self.console.print(f"Restaurando sessão anterior (ID: {session_id})...")
                        self.facade.set_active_session(session_id)
                        self.active_session_details = self.facade.get_active_session_details()
            except (json.JSONDecodeError, SessionError):
                self.console.print("[yellow]Não foi possível restaurar a sessão anterior.[/yellow]")
                os.remove(SESSION_STATE_FILE)  # Remove arquivo corrompido

    def _save_last_session(self):
        """Salva o ID da sessão ativa para ser restaurado na próxima execução."""
        if self.active_session_details:
            state = {"active_session_id": self.active_session_details["id"]}
            with open(SESSION_STATE_FILE, "w") as f:
                json.dump(state, f)

    # --- Menus Principais ---

    def _show_main_menu(self):
        """Exibe o menu principal e direciona para a ação escolhida."""
        session_status = (
            f"[green]Sessão Ativa: {self.active_session_details['refeicao'].capitalize()} em {self.active_session_details['data']}[/green]"
            if self.active_session_details
            else "[yellow]Nenhuma sessão ativa[/yellow]"
        )
        self.console.print(f"\n--- MENU PRINCIPAL ({session_status}) ---")

        choices = [
            "Iniciar Nova Sessão",
            "Continuar Sessão Existente",
            questionary.Separator(),
            "Registrar Consumo (Buscar Aluno)",
            "Desfazer Consumo",
            "Listar Alunos",
            questionary.Separator(),
            "Sincronizar com Google Sheets (Download)",
            "Enviar Consumo para Google Sheets (Upload)",
            "Exportar Sessão para XLSX",
            questionary.Separator(),
            "Sair",
        ]

        if not self.active_session_details:
            disabled_options = [3, 4, 5, 8, 9]
            for i in disabled_options:
                choices[i] = questionary.Choice(title=str(choices[i]), disabled="Selecione uma sessão primeiro")

        action = questionary.select("O que você deseja fazer?", choices=choices, use_indicator=True).ask()

        if action == "Iniciar Nova Sessão":
            self._start_new_session()
        elif action == "Continuar Sessão Existente":
            self._select_active_session()
        elif action == "Registrar Consumo (Buscar Aluno)":
            self._search_and_register_consumption()
        elif action == "Desfazer Consumo":
            self._search_and_undo_consumption()
        elif action == "Listar Alunos":
            self._list_students()
        elif action == "Sincronizar com Google Sheets (Download)":
            self._sync_from_sheets()
        elif action == "Enviar Consumo para Google Sheets (Upload)":
            self._sync_to_sheets()
        elif action == "Exportar Sessão para XLSX":
            self._export_to_xlsx()
        elif action == "Sair" or action is None:
            self.shutdown()

    # --- Lógica das Ações ---

    def _start_new_session(self):
        """Guia o usuário para criar uma nova sessão."""
        try:
            refeicao = questionary.select("Qual a refeição?", choices=["Almoço", "Lanche"]).ask()
            if refeicao is None:
                return
            lanche = ""
            if refeicao == "Lanche":
                lanche = questionary.text("Qual o lanche?").ask()
                if lanche is None:
                    return

            periodo = questionary.select("Qual o período?", choices=[
                                         "Integral", "Matutino", "Vespertino", "Noturno"]).ask()
            if periodo is None:
                return
            data = questionary.text("Data (DD/MM/AAAA):").ask()
            if data is None:
                return
            hora = questionary.text("Hora (HH:MM):").ask()
            if hora is None:
                return
            turmas_str = questionary.text("Turmas (separadas por vírgula):", default="Todas").ask()
            if turmas_str is None:
                return

            session_data: SessionData = {
                'refeição': refeicao, 'lanche': lanche, 'período': periodo,
                'data': data, 'hora': hora,
                'turmas': [t.strip() for t in turmas_str.split(',')]
            }

            with self.console.status("[cyan]Criando nova sessão...[/]"):
                session_id = self.facade.start_new_session(session_data)
                self.facade.set_active_session(session_id)
                self.active_session_details = self.facade.get_active_session_details()
            self.console.print(f"[bold green]Sessão {session_id} iniciada e definida como ativa![/bold green]")

        except RegistrationCoreError as e:
            self.console.print(f"[bold red]ERRO ao iniciar sessão: {e}[/bold red]")

    def _select_active_session(self):
        """Permite ao usuário escolher uma sessão existente para torná-la ativa."""
        try:
            sessoes = self.facade.list_all_sessions()
            if not sessoes:
                self.console.print("[yellow]Nenhuma sessão anterior encontrada no banco de dados.[/yellow]")
                return

            choice_map = {
                f"ID {s['id']}: {s['refeicao'].capitalize()} de {s['data']} às {s['hora']}": s['id']
                for s in sorted(sessoes, key=lambda x: x['id'], reverse=True)
            }

            choice = questionary.select(
                "Qual sessão você deseja reativar?", choices=list(choice_map.keys())
            ).ask()

            if choice:
                session_id = choice_map[choice]
                self.facade.set_active_session(session_id)
                self.active_session_details = self.facade.get_active_session_details()
                self.console.print(f"[bold green]Sessão {session_id} está ativa.[/bold green]")

        except RegistrationCoreError as e:
            self.console.print(f"[bold red]ERRO ao selecionar sessão: {e}[/bold red]")

    def _search_and_register_consumption(self):
        """Busca por um aluno e registra seu consumo."""
        self._find_student_and_act(
            prompt_title="--- Registrar Consumo ---",
            status_to_fetch=False,  # Buscar não consumidos
            action_name="registrar consumo",
            action_function=self.facade.register_consumption
        )

    def _search_and_undo_consumption(self):
        """Busca por um aluno e desfaz seu consumo."""
        self._find_student_and_act(
            prompt_title="--- Desfazer Consumo ---",
            status_to_fetch=True,  # Buscar consumidos
            action_name="desfazer consumo",
            action_function=self.facade.undo_consumption
        )

    def _find_student_and_act(self, prompt_title: str, status_to_fetch: bool, action_name: str, action_function: Callable[[int], any]):
        """Função genérica para encontrar um aluno e executar uma ação."""
        self.console.print(prompt_title)
        query = questionary.text("Busque pelo nome ou prontuário do aluno (ou deixe em branco para cancelar):").ask()
        if not query:
            return

        try:
            with self.console.status("[cyan]Buscando...[/]"):
                students = self.facade.get_students_for_session(consumed=status_to_fetch)
                matches = [
                    s for s in students
                    if query.lower() in s['nome'].lower() or query.lower() in s['pront'].lower()
                ]

            if not matches:
                self.console.print("[yellow]Nenhum aluno correspondente encontrado.[/yellow]")
                return

            if len(matches) == 1:
                selected_student = matches[0]
                confirm = questionary.confirm(f"Encontrado: {selected_student['nome']}. Deseja {action_name}?").ask()
                if not confirm:
                    return
            else:
                # Mapeia a string de escolha para o objeto aluno completo (mais robusto)
                choice_map = {
                    f"{s['nome']} ({s['pront']}) - {s['turma']}": s
                    for s in matches
                }
                choice_str = questionary.select("Múltiplos alunos encontrados. Qual deles?",
                                                choices=list(choice_map.keys())).ask()
                if not choice_str:
                    return
                selected_student = choice_map[choice_str]

            action_function(selected_student['reserve_id'])
            self.console.print(
                f"[bold green]Ação '{action_name}' executada com sucesso para {selected_student['nome']}.[/bold green]")

        except RegistrationCoreError as e:
            self.console.print(f"[bold red]ERRO: {e}[/bold red]")

    def _list_students(self):
        """Exibe uma tabela com os alunos da sessão."""
        filter_choice = questionary.select(
            "Quais alunos deseja listar?",
            choices=["Todos", "Apenas os que se serviram", "Apenas os que NÃO se serviram"]
        ).ask()
        if filter_choice is None:
            return

        consumed_filter = None
        if "Apenas os que se serviram" in filter_choice:
            consumed_filter = True
        elif "Apenas os que NÃO se serviram" in filter_choice:
            consumed_filter = False

        try:
            with self.console.status("[cyan]Buscando alunos...[/]"):
                students = self.facade.get_students_for_session(consumed=consumed_filter)

            if not students:
                self.console.print("[yellow]Nenhum aluno encontrado com os critérios fornecidos.[/yellow]")
                return

            table = Table(title=f"Alunos na Sessão - {filter_choice}")
            table.add_column("Prontuário", style="cyan", no_wrap=True)
            table.add_column("Nome", style="magenta")
            table.add_column("Turma", style="yellow")
            table.add_column("Prato")
            table.add_column("Consumido?", justify="center")
            table.add_column("Horário", justify="center")

            for s in students:
                consumed_status = "[green]SIM[/green]" if s['consumed'] else "[red]NÃO[/red]"
                table.add_row(s['pront'], s['nome'], s['turma'], s['prato'], consumed_status, s['registro_time'])

            self.console.print(table)
        except RegistrationCoreError as e:
            self.console.print(f"[bold red]ERRO ao listar alunos: {e}[/bold red]")

    # --- Funções de Sincronização e Exportação (sem alterações significativas) ---

    def _sync_from_sheets(self):
        if not questionary.confirm("Isso irá baixar e sobrescrever os dados locais de alunos e reservas. Deseja continuar?").ask():
            return
        try:
            with self.console.status("[bold green]Sincronizando do Google Sheets...[/]", spinner="dots"):
                self.facade.sync_from_google_sheets()
            self.console.print("[bold green]Base de dados local sincronizada com sucesso![/bold green]")
        except RegistrationCoreError as e:
            self.console.print(f"[bold red]ERRO na sincronização: {e}[/bold red]")

    def _sync_to_sheets(self):
        try:
            with self.console.status("[bold green]Enviando dados para o Google Sheets...[/]", spinner="dots"):
                self.facade.sync_to_google_sheets()
            self.console.print("[bold green]Dados de consumo enviados com sucesso![/bold green]")
        except RegistrationCoreError as e:
            self.console.print(f"[bold red]ERRO no envio: {e}[/bold red]")

    def _export_to_xlsx(self):
        try:
            filepath = self.facade.export_session_to_xlsx()
            self.console.print(f"[bold green]Relatório exportado com sucesso para:[/bold green] {filepath}")
        except RegistrationCoreError as e:
            self.console.print(f"[bold red]ERRO ao exportar: {e}[/bold red]")


if __name__ == "__main__":
    app = AppTUI()
    app.run()
