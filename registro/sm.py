import os
import shutil
from datetime import datetime
from pprint import pprint

# Importa a Facade e os tipos de dados necessários.
# Para este script funcionar, os arquivos do seu projeto devem estar
# em uma estrutura de pacotes Python (com arquivos __init__.py).
# Ex: ./registro/nucleo/__init__.py, ./registro/nucleo/facade.py, etc.
from registro.nucleo.facade import RegistroFacade
from registro.nucleo.utils import SESSION as SessionData

# --- Funções de Apoio para a Simulação ---


def setup_dummy_data():
    """Cria arquivos CSV de exemplo para simular a sincronização inicial."""
    print("--- 1. Configurando ambiente de simulação ---")
    config_dir = os.path.abspath("./config")
    os.makedirs(config_dir, exist_ok=True)

    # Dados de estudantes
    students_data = [
        ["Prontuário", "Nome", "Turma"],
        ["SP3000001", "Alice da Silva", "TAD01"],
        ["SP3000002", "Bruno Costa", "TAD01"],
        ["SP3000003", "Carlos Dias", "LOG02"],
        ["SP3000004", "Daniela Souza", "LOG02"],
        ["SP3000005", "Eduardo Lima", "MEC01"],
    ]

    # Dados de reservas para o dia de hoje
    today_str = datetime.now().strftime("%d/%m/%Y")
    reserves_data = [
        ["Prontuário", "Data", "Refeição"],
        ["SP3000001", today_str, "Prato Principal"],
        ["SP3000003", today_str, "Vegetariano"],
    ]

    # Salva os arquivos CSV
    with open(os.path.join(config_dir, "students.csv"), "w", newline="", encoding="utf-8") as f:
        import csv
        writer = csv.writer(f)
        writer.writerows(students_data)

    with open(os.path.join(config_dir, "reserves.csv"), "w", newline="", encoding="utf-8") as f:
        import csv
        writer = csv.writer(f)
        writer.writerows(reserves_data)

    print("Arquivos 'students.csv' e 'reserves.csv' criados em ./config/")
    print("-" * 40 + "\n")


def cleanup():
    """Remove os arquivos e diretórios criados pela simulação."""
    print("\n--- 11. Limpando ambiente ---")
    config_dir = os.path.abspath("./config")
    # documents_dir = os.path.expanduser("~/Documents") # Ajuste se necessário

    # Remove o banco de dados
    if os.path.exists(os.path.join(config_dir, "registro.db")):
        os.remove(os.path.join(config_dir, "registro.db"))
        print("Banco de dados 'registro.db' removido.")

    # Remove arquivos de configuração (CSVs e token)
    # if os.path.exists(config_dir):
    #     shutil.rmtree(config_dir)
    #     print("Diretório './config' removido.")

    # Remove o arquivo XLSX exportado (o nome é dinâmico)
    # for item in os.listdir(documents_dir):
    #     if item.endswith(".xlsx") and "Almoço" in item:
    #         os.remove(os.path.join(documents_dir, item))
    #         print(f"Relatório '{item}' removido da pasta Documentos.")
    #         break
    print("-" * 40)


# --- Script Principal da Simulação ---

def run_simulation():
    """Executa a simulação completa de uso da RegistroFacade."""
    try:
        # O uso do 'with' garante que a conexão com o DB seja fechada no final
        with RegistroFacade() as facade:
            # 2. Sincroniza os dados dos arquivos CSV para o banco de dados
            print("--- 2. Sincronizando dados iniciais (simulado) ---")
            facade.sync_from_google_sheets()
            print("Sincronização concluída. Estudantes e reservas importados.")
            print("-" * 40 + "\n")

            # 3. Inicia uma nova sessão de almoço para turmas específicas
            print("--- 3. Iniciando uma nova sessão de refeição ---")
            today_str = "04/11/2025"
            session_data: SessionData = {
                "refeicao": "almoço",
                "periodo": "Integral",
                "data": today_str,
                "hora": "12:00",
                "item_servido": "Feijoada",
                "grupos": ["TAD01", "LOG02"]  # Apenas estas turmas estão autorizadas por exceção
            }
            session_id = facade.start_new_session(session_data)
            print(f"Sessão de almoço iniciada com ID: {session_id}")
            print("-" * 40 + "\n")

            # 4. Lista os detalhes da sessão ativa
            print("--- 4. Detalhes da sessão ativa ---")
            active_session_details = facade.get_active_session_details()
            pprint(active_session_details)
            print("-" * 40 + "\n")

            # 5. Lista todos os estudantes autorizados para a sessão (que ainda não consumiram)
            print("--- 5. Estudantes autorizados (não consumiram) ---")
            authorized_students = facade.get_students_for_session(consumed=False)
            pprint(authorized_students)
            print("-" * 40 + "\n")

            # 6. Registra o consumo para alguns estudantes
            print("--- 6. Registrando consumo ---")
            # Alice tem reserva
            result1 = facade.register_consumption("IQ3036448")
            print(f"Registro para IQ3036448 (Luna): {result1}")
            # Bruno não tem reserva mas pertence a um grupo de exceção
            result2 = facade.register_consumption("IQ3037797")
            print(f"Registro para IQ3037797 (Isabelly): {result2}")
            # Eduardo não tem reserva e não pertence a um grupo de exceção
            result3 = facade.register_consumption("IQ3036618")
            print(f"Registro para IQ3036618 (Antonio): {result3}")
            print("-" * 40 + "\n")

            # 7. Lista os estudantes que já consumiram
            print("--- 7. Estudantes que já consumiram ---")
            consumed_students = facade.get_students_for_session(consumed=True)
            pprint(consumed_students)
            print("-" * 40 + "\n")

            # 8. Desfaz um registro de consumo (ex: registro por engano)
            print("--- 8. Desfazendo um registro de consumo ---")
            consumo_id_to_undo = consumed_students[0]['consumo_id']  # Pega o ID do consumo da Alice
            facade.undo_consumption(consumo_id_to_undo)
            print(f"Consumo ID {consumo_id_to_undo} (de Alice) foi desfeito.")
            print("-" * 40 + "\n")

            # Verifica novamente quem consumiu
            print("--- Verificando novamente os que consumiram ---")
            consumed_students_after_undo = facade.get_students_for_session(consumed=True)
            pprint(consumed_students_after_undo)
            print("-" * 40 + "\n")

            # 9. Exporta os dados da sessão para um arquivo Excel
            print("--- 9. Exportando dados para XLSX ---")
            file_path = facade.export_session_to_xlsx()
            print(f"Dados da sessão exportados para: {file_path}")
            print("-" * 40 + "\n")

            # 10. Simula o envio dos dados de consumo para o Google Sheets
            print("--- 10. Sincronizando consumo para o Google Sheets (simulado) ---")
            facade.sync_to_google_sheets()
            print("Sincronização de consumo para a nuvem concluída.")
            print("-" * 40 + "\n")

    except Exception as e:
        print(f"\nOcorreu um erro durante a simulação: {e}")
    finally:
        # Garante que a limpeza seja executada mesmo se ocorrer um erro
        #cleanup()
        pass


if __name__ == "__main__":
    run_simulation()
