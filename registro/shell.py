"""
Fornece um prompt de comando interativo (shell) para interagir com o
sistema de registro de refeições.
"""
import cmd
import datetime
import json
import sys

from registro.nucleo.exceptions import RegistrationCoreError
from registro.nucleo.facade import RegistroFacade
from registro.nucleo.utils import SESSION as SessionData


class InteractiveShell(cmd.Cmd):
    """
    Encapsula o prompt de comando interativo para o sistema de registro.
    """
    intro = ('Bem-vindo ao shell de registro de refeições.'
             ' Digite help ou ? para listar os comandos.\n')
    prompt = '(registro) > '

    def __init__(self):
        super().__init__()
        try:
            self.facade = RegistroFacade()
        except Exception as e:
            print(f"Erro fatal ao inicializar a fachada: {e}", file=sys.stderr)
            sys.exit(1)

    # --- Comandos Básicos do Shell ---

    def do_exit(self, _arg):
        """Sai do shell interativo."""
        print('Até logo!')
        return True

    def do_EOF(self, arg):
        """Sai do shell com Ctrl+D."""
        return self.do_exit(arg)

    def emptyline(self):
        """Não faz nada quando uma linha vazia é inserida."""

    def postloop(self):
        """Limpeza ao sair do loop de comando."""
        print("Fechando conexão com o banco de dados...")
        self.facade.close()

    # --- Comandos da Aplicação ---

    def do_start_session(self, _arg):
        """
        Inicia uma nova sessão de refeição interativamente.
        Uso: start_session
        """
        try:
            print("--- Iniciando Nova Sessão ---")

            def ask(prompt, validator, err_msg, max_attempts=3):
                attempts = 0
                while True:
                    try:
                        val = input(prompt).strip()
                    except (KeyboardInterrupt, EOFError):
                        raise
                    if validator(val):
                        return val
                    attempts += 1
                    print(err_msg, file=sys.stderr)
                    if attempts >= max_attempts:
                        print("Máximo de tentativas excedido. Cancelando operação.", file=sys.stderr)
                        return None

            # Refeição
            refeicao_raw = ask(
                "Refeição (Lanche/Almoço): ",
                lambda v: v.lower() in ("lanche", "almoço", "almoco"),
                "Refeição inválida. Digite 'Lanche' ou 'Almoço'."
            )
            if refeicao_raw is None:
                return
            refeicao_norm = refeicao_raw.lower()
            if refeicao_norm in ("almoço", "almoco"):
                refeicao = "Almoço"
            else:
                refeicao = "Lanche"

            # Nome do lanche (se aplicável)
            lanche = ""
            if refeicao == "Lanche":
                lanche = ask(
                    "Nome do lanche: ",
                    lambda v: len(v.strip()) > 0,
                    "Nome do lanche não pode ser vazio."
                )
                if lanche is None:
                    return

            # Período
            allowed_periods = {"integral", "matutino", "vespertino", "noturno"}
            periodo_raw = ask(
                "Período (Integral/Matutino/Vespertino/Noturno): ",
                lambda v: v.lower() in allowed_periods,
                "Período inválido. Use uma das opções: "
                f"{', '.join(p.capitalize() for p in allowed_periods)}."
            )
            if periodo_raw is None:
                return
            periodo = periodo_raw.capitalize()

            # Data
            def valid_date(v):
                try:
                    datetime.datetime.strptime(v, "%d/%m/%Y")
                    return True
                except ValueError:
                    return False

            data = ask(
                "Data (DD/MM/AAAA): ",
                valid_date,
                "Data inválida. Use o formato DD/MM/AAAA."
            )
            if data is None:
                return

            # Hora
            def valid_time(v):
                try:
                    datetime.datetime.strptime(v, "%H:%M")
                    return True
                except ValueError:
                    return False

            hora = ask(
                "Hora (HH:MM): ",
                valid_time,
                "Hora inválida. Use o formato HH:MM (24h)."
            )
            if hora is None:
                return

            # Turmas
            def valid_turmas(v):
                parts = [p.strip() for p in v.split(",") if p.strip()]
                return len(parts) > 0

            turmas_str = ask(
                "Turmas (separadas por vírgula): ",
                valid_turmas,
                "Entrada inválida. Informe ao menos uma turma,"
                " separadas por vírgula se mais de uma."
            )
            if turmas_str is None:
                return

            session_data: SessionData = {
                'refeição': refeicao, 'lanche': lanche, 'período': periodo,
                'data': data, 'hora': hora,
                'turmas': [t.strip() for t in turmas_str.split(',')]
            }

            session_id = self.facade.start_new_session(session_data)
            if session_id:
                print(f"Sessão iniciada com sucesso. ID da sessão ativa: {session_id}")
            else:
                print("Falha ao iniciar a sessão.")
        except RegistrationCoreError as e:
            print(f"ERRO: {e}", file=sys.stderr)
        except (KeyboardInterrupt, EOFError):
            print("\nCriação de sessão cancelada.")

    def do_set_active(self, arg):
        """
        Define uma sessão existente como ativa.
        Uso: set_active <session_id>
        """
        try:
            session_id = int(arg)
            self.facade.set_active_session(session_id)
            print(f"Sessão {session_id} agora está ativa.")
        except ValueError:
            print("ERRO: ID da sessão deve ser um número.", file=sys.stderr)
        except RegistrationCoreError as e:
            print(f"ERRO: {e}", file=sys.stderr)

    def do_details(self, _arg):
        """Mostra os detalhes da sessão ativa."""
        try:
            details = self.facade.get_active_session_details()
            print(json.dumps(details, indent=2, ensure_ascii=False))
        except RegistrationCoreError as e:
            print(f"ERRO: {e}", file=sys.stderr)

    def do_list(self, arg):
        """
        Lista estudantes para a sessão ativa.
        Uso: list [consumed|unconsumed]
        """
        try:
            consumed = None
            if arg.lower() == 'consumed':
                consumed = True
            elif arg.lower() == 'unconsumed':
                consumed = False

            students = self.facade.get_students_for_session(consumed)
            if not students:
                print("Nenhum estudante encontrado com os critérios fornecidos.")
                return

            for s in students:
                status = "SIM" if s['consumed'] else "NÃO"
                hora = f"às {s['registro_time']}" if s['registro_time'] else ""
                print(
                    f"ID Reserva: {s['reserve_id']:<5} Pront: {s['pront']:<10} "
                    f"Nome: {s['nome']:<30} Turma: {s['turma']:<10} "
                    f"Consumido: {status} {hora}"
                )
        except RegistrationCoreError as e:
            print(f"ERRO: {e}", file=sys.stderr)

    def do_register(self, arg):
        """
        Registra o consumo para uma reserva.
        Uso: register <reserve_id>
        """
        try:
            reserve_id = int(arg)
            if self.facade.register_consumption(reserve_id):
                print("Consumo registrado com sucesso.")
            else:
                print("ERRO: Falha ao registrar o consumo. ID da reserva não encontrado?",
                      file=sys.stderr)
        except ValueError:
            print("ERRO: ID da reserva deve ser um número.", file=sys.stderr)
        except RegistrationCoreError as e:
            print(f"ERRO: {e}", file=sys.stderr)

    def do_undo(self, arg):
        """
        Desfaz o registro de consumo de uma reserva.
        Uso: undo <reserve_id>
        """
        try:
            reserve_id = int(arg)
            self.facade.undo_consumption(reserve_id)
            print("Registro de consumo desfeito.")
        except ValueError:
            print("ERRO: ID da reserva deve ser um número.", file=sys.stderr)
        except RegistrationCoreError as e:
            print(f"ERRO: {e}", file=sys.stderr)

    def do_export(self, _arg):
        """Exporta a sessão ativa para um arquivo XLSX."""
        try:
            filepath = self.facade.export_session_to_xlsx()
            print(f"Dados da sessão exportados para: {filepath}")
        except RegistrationCoreError as e:
            print(f"ERRO: {e}", file=sys.stderr)

    def do_sync_from(self, _arg):
        """Sincroniza a base de dados local a partir do Google Sheets."""
        try:
            print("Iniciando sincronização a partir do Google Sheets..."
                  " Isso pode levar um momento.")
            self.facade.sync_from_google_sheets()
            print("Sincronização concluída com sucesso.")
        except RegistrationCoreError as e:
            print(f"ERRO durante a sincronização: {e}", file=sys.stderr)

    def do_sync_to(self, _arg):
        """Envia os dados de consumo da sessão ativa para o Google Sheets."""
        try:
            print("Enviando dados de consumo para o Google Sheets...")
            self.facade.sync_to_google_sheets()
            print("Envio para o Google Sheets concluído com sucesso.")
        except RegistrationCoreError as e:
            print(f"ERRO durante o envio: {e}", file=sys.stderr)


if __name__ == '__main__':
    InteractiveShell().cmdloop()
