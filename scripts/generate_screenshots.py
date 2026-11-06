import os
import sys
import tempfile
import datetime as dt
from pathlib import Path
import ctypes
from ctypes import windll, wintypes, Structure, byref, sizeof
import time
import subprocess
import json

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

user32 = windll.user32
gdi32 = windll.gdi32

class BITMAPINFOHEADER(Structure):
    _fields_ = [
        ('biSize', wintypes.DWORD),
        ('biWidth', wintypes.LONG),
        ('biHeight', wintypes.LONG),
        ('biPlanes', wintypes.WORD),
        ('biBitCount', wintypes.WORD),
        ('biCompression', wintypes.DWORD),
        ('biSizeImage', wintypes.DWORD),
        ('biXPelsPerMeter', wintypes.LONG),
        ('biYPelsPerMeter', wintypes.LONG),
        ('biClrUsed', wintypes.DWORD),
        ('biClrImportant', wintypes.DWORD),
    ]

def capture_widget(widget, filename):
    from PIL import Image
    widget.update_idletasks()
    widget.update()
    time.sleep(0.25)
    hwnd = widget.winfo_id()
    parent = user32.GetParent(hwnd)
    target = parent if parent else hwnd

    rect = wintypes.RECT()
    user32.GetWindowRect(target, byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    if w <= 0 or h <= 0:
        print(f"Error: Invalid dimensions for {filename}: {w}x{h}")
        return False

    hdcScreen = user32.GetDC(target)
    hdcMem = gdi32.CreateCompatibleDC(hdcScreen)
    hbm = gdi32.CreateCompatibleBitmap(hdcScreen, w, h)
    gdi32.SelectObject(hdcMem, hbm)

    user32.PrintWindow(target, hdcMem, 2)

    bmi = BITMAPINFOHEADER()
    bmi.biSize = sizeof(BITMAPINFOHEADER)
    bmi.biWidth = w
    bmi.biHeight = -h
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0

    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(hdcMem, hbm, 0, h, buf, byref(bmi), 0)

    im = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1)
    im = im.convert('RGB')
    out_path = BASE_DIR / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path)

    gdi32.DeleteObject(hbm)
    gdi32.DeleteDC(hdcMem)
    user32.ReleaseDC(target, hdcScreen)
    print(f"Successfully captured {filename} ({w}x{h})")
    return True


def setup_demo_environment():
    temp_dir = Path(tempfile.gettempdir()) / "mr2_manual_demo_env"
    temp_dir.mkdir(parents=True, exist_ok=True)
    db_path = temp_dir / "registro_demo.db"
    
    import registro.nucleo.constants as const
    const.DIRETORIO_CONFIG = temp_dir
    const.URL_BANCO_DADOS = f"sqlite:///{db_path}"
    const.CAMINHO_CREDENCIAS = temp_dir / "credentials.json"
    const.CAMINHO_SETTINGS = temp_dir / "settings.json"
    const.CAMINHO_SESSAO = temp_dir / "session.json"
    const.JSON_ID_PLANILHA = temp_dir / "spreadsheet.json"

    with open(const.CAMINHO_SETTINGS, "w", encoding="utf-8") as f:
        json.dump({"pin": "1234", "fullscreen": False, "camera_index": 0}, f)

    with open(const.JSON_ID_PLANILHA, "w", encoding="utf-8") as f:
        json.dump({"spreadsheet_id": "1A2B3C4D5E6F7G8H9I0J_EXEMPLO_GOOGLE_SHEETS"}, f)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import registro.nucleo.models as models

    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    models.motor = engine
    models.SessaoLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.criar_banco_de_dados_e_tabelas()

    from registro.nucleo.models import Estudante, Grupo, Reserva, Sessao, Consumo

    hoje = dt.date.today().strftime("%Y-%m-%d")

    with models.SessaoLocal() as session:
        if session.query(Estudante).count() == 0:
            g1 = Grupo(nome="1º Ano A - Informática")
            g2 = Grupo(nome="2º Ano B - Mecatrônica")
            g3 = Grupo(nome="3º Ano C - Edificações")
            g4 = Grupo(nome="Engenharia de Controle")
            session.add_all([g1, g2, g3, g4])
            session.flush()

            alunos_data = [
                ("SP301001", "Ana Beatriz Silva", [g1]),
                ("SP301002", "Carlos Eduardo Santos", [g1]),
                ("SP301003", "Fernanda Lima Oliveira", [g2]),
                ("SP301004", "Gabriel Rodrigues Costa", [g2]),
                ("SP301005", "Juliana Mendes Pereira", [g3]),
                ("SP301006", "Lucas Martins Souza", [g1, g2]),
                ("SP301007", "Mariana Alves Ribeiro", [g3]),
                ("SP301008", "Rafael Barbosa Lima", [g4]),
                ("SP301009", "Beatriz Castro Ramos", [g4]),
                ("SP301010", "Diego Fernandes Rocha", [g1]),
            ]
            estudantes = []
            for pront, nome, gps in alunos_data:
                e = Estudante(prontuario=pront, nome=nome, grupos=gps, ativo=True)
                session.add(e)
                estudantes.append(e)
            session.flush()

            s1 = Sessao(
                refeicao="Almoço",
                periodo="Tarde",
                data=hoje,
                hora="12:00:00",
                item_servido="Arroz, Feijão, Frango Grelhado e Salada",
                grupos=[g1, g2, g3, g4]
            )
            session.add(s1)
            session.flush()

            dados_sessao = {
                "id": s1.id,
                "refeicao": "Almoço",
                "data": hoje,
                "periodo": "Tarde",
                "hora": "12:00:00",
                "grupos": [g.nome for g in [g1, g2, g3, g4]],
                "item_servido": "Arroz, Feijão, Frango Grelhado e Salada"
            }
            with open(const.CAMINHO_SESSAO, "w", encoding="utf-8") as f:
                json.dump(dados_sessao, f)

            r1 = Reserva(estudante_id=estudantes[0].id, data=hoje, prato="Almoço Regular", cancelada=False)
            r2 = Reserva(estudante_id=estudantes[1].id, data=hoje, prato="Almoço Regular", cancelada=False)
            r3 = Reserva(estudante_id=estudantes[2].id, data=hoje, prato="Opção Vegetariana", cancelada=False)
            r4 = Reserva(estudante_id=estudantes[3].id, data=hoje, prato="Almoço Regular", cancelada=False)
            r5 = Reserva(estudante_id=estudantes[4].id, data=hoje, prato="Almoço Regular", cancelada=False)
            session.add_all([r1, r2, r3, r4, r5])
            session.flush()

            c1 = Consumo(estudante_id=estudantes[0].id, sessao_id=s1.id, hora_consumo="12:04:15", reserva_id=r1.id)
            c2 = Consumo(estudante_id=estudantes[1].id, sessao_id=s1.id, hora_consumo="12:06:30", reserva_id=r2.id)
            c3 = Consumo(estudante_id=estudantes[2].id, sessao_id=s1.id, hora_consumo="12:08:45", reserva_id=r3.id)
            session.add_all([c1, c2, c3])
            session.commit()


def run_group_launcher():
    import tkinter as tk
    import ttkbootstrap as ttk
    root_l = ttk.Window(title="Registro de Refeições", themename="sandstone", resizable=(False, False))
    root_l.geometry("520x530")
    c = ttk.Frame(root_l, padding=25)
    c.pack(fill="both", expand=True)
    ttk.Label(c, text="🍽️ Sistema de Refeitório", font=("Segoe UI", 16, "bold"), anchor="center").pack(fill="x", pady=(0, 4))
    ttk.Label(c, text="Selecione o módulo que deseja iniciar:", font=("Segoe UI", 10), bootstyle="secondary", anchor="center").pack(fill="x", pady=(0, 20))
    ttk.Button(c, text="📝  Registrar Refeições\nControle e registro de consumo em tempo real", bootstyle="primary-outline").pack(fill="x", pady=5, ipady=5)
    ttk.Button(c, text="📊  Painel Administrativo\nGestão de alunos, turmas, reservas e relatórios", bootstyle="info-outline").pack(fill="x", pady=5, ipady=5)
    ttk.Button(c, text="🤖  Totem de Autoatendimento\nTerminal autônomo com leitor de QR Code / câmera", bootstyle="success-outline").pack(fill="x", pady=5, ipady=5)
    ttk.Button(c, text="⚙️  Configurações & Início Rápido\nGoogle Cloud, PIN de segurança, backups e atalhos", bootstyle="secondary-outline").pack(fill="x", pady=5, ipady=5)
    ttk.Label(c, text="Dica: Em atalhos, use as flags /painel, /auto, /reg ou /setup para abrir direto.", font=("Segoe UI", 8), bootstyle="secondary", anchor="center").pack(fill="x", side="bottom", pady=(15, 0))
    capture_widget(root_l, "docs/imagens/01_launcher_principal.png")
    root_l.destroy()


def run_group_setup():
    setup_demo_environment()
    import tkinter as tk
    import ttkbootstrap as ttk
    tk.Toplevel.wait_window = lambda self, w=None: None
    ttk.Toplevel.wait_window = lambda self, w=None: None

    from registro.gui.setup.app import AppSetup
    setup_app = AppSetup()
    setup_app.geometry("980x700")
    setup_app.notebook.select(setup_app.aba_status)
    capture_widget(setup_app, "docs/imagens/02_setup_checklist.png")

    from registro.gui.comum.dialogo_pin import DialogoPIN
    pin_dialog = DialogoPIN(setup_app, titulo="🔒 Autenticação do Totem", mensagem="Digite o PIN de 4 dígitos para autorizar alterações:")
    pin_dialog._adicionar_digito("1")
    pin_dialog._adicionar_digito("2")
    capture_widget(pin_dialog, "docs/imagens/03_setup_pin_modal.png")
    pin_dialog.destroy()
    setup_app.destroy()


def run_group_painel():
    setup_demo_environment()
    import tkinter as tk
    import ttkbootstrap as ttk
    tk.Toplevel.wait_window = lambda self, w=None: None
    ttk.Toplevel.wait_window = lambda self, w=None: None

    from registro.gui.painel.app import App as PainelApp
    painel = PainelApp()
    painel.geometry("1200x750")

    # 04. Aba Alunos
    painel.show_frame("alunos")
    capture_widget(painel, "docs/imagens/04_painel_alunos.png")

    # 05. Diálogo Aluno
    from registro.gui.painel.dialogos import StudentDialog
    from registro.nucleo.models import Estudante
    with painel.fachada_nucleo.repo_estudante.obter_sessao() as s:
        e = s.query(Estudante).first()
        eid = e.id if e else None
    st_dialog = StudentDialog(painel, painel.fachada_nucleo, student_id=eid)
    capture_widget(st_dialog, "docs/imagens/05_painel_aluno_dialogo.png")
    st_dialog.destroy()

    # 06. Aba Turmas
    painel.show_frame("turmas")
    capture_widget(painel, "docs/imagens/06_painel_turmas.png")

    # 07. Diálogo Turma
    from registro.gui.painel.dialogos import TurmaDialog
    from registro.nucleo.models import Grupo
    with painel.fachada_nucleo.repo_grupo.obter_sessao() as s:
        g = s.query(Grupo).first()
        gid = g.id if g else None
    turma_dialog = TurmaDialog(painel, painel.fachada_nucleo, turma_id=gid)
    capture_widget(turma_dialog, "docs/imagens/07_painel_turma_dialogo.png")
    turma_dialog.destroy()

    # 08. Aba Reservas
    painel.show_frame("reservas")
    capture_widget(painel, "docs/imagens/08_painel_reservas.png")

    # 09. Diálogo Reserva
    from registro.gui.painel.dialogos import ReservaDialog
    reserva_dialog = ReservaDialog(painel, painel.fachada_nucleo)
    if reserva_dialog.student_display_list:
        reserva_dialog.aluno_combobox.current(0)
    reserva_dialog.prato_combobox.set("Tradicional")
    capture_widget(reserva_dialog, "docs/imagens/09_painel_reserva_dialogo.png")
    reserva_dialog.destroy()

    # 10. Aba Importação
    painel.show_frame("importacao")
    capture_widget(painel, "docs/imagens/10_painel_importacao.png")

    # 11. Aba Dashboard
    painel.show_frame("dashboard")
    capture_widget(painel, "docs/imagens/11_painel_dashboard.png")

    painel.destroy()


def run_group_operador():
    setup_demo_environment()
    import tkinter as tk
    import ttkbootstrap as ttk
    tk.Toplevel.wait_window = lambda self, w=None: None
    ttk.Toplevel.wait_window = lambda self, w=None: None

    from registro.gui.registrar.app import AppRegistro
    from registro.gui.registrar.dialogo_sessao import DialogoSessao

    op_app = AppRegistro()
    op_app.geometry("1180x700")

    # 12. Diálogo Abrir Sessão
    sess_dialog = DialogoSessao("Abertura de Sessão de Refeição", callback=lambda d: True, parente_app=op_app)
    sess_dialog._combobox_refeicao.set("Almoço")
    sess_dialog._combobox_lanche.set("Arroz, Feijão, Frango Grelhado e Salada")
    capture_widget(sess_dialog, "docs/imagens/12_operador_abrir_sessao.png")
    sess_dialog.destroy()

    # 13. Terminal com Sessão Ativa
    capture_widget(op_app, "docs/imagens/13_operador_terminal_ativo.png")

    # 14. Confirmação de Sucesso
    if op_app._painel_acao and op_app._painel_acao._label_aluno_selecionado:
        op_app._painel_acao._label_aluno_selecionado.config(
            text="Pront: SP301001\nNome: Ana Beatriz Silva\nTurma: 1º Ano A - Informática\nPrato: Almoço Regular\n\n✅ PRESENÇA CONFIRMADA COM SUCESSO!",
            bootstyle="@success"
        )
    if op_app._label_barra_status:
        op_app._label_barra_status.config(text="Consumo registrado com sucesso para Ana Beatriz Silva às 12:05.")
    capture_widget(op_app, "docs/imagens/14_operador_confirmacao_sucesso.png")
    op_app.destroy()


def run_group_totem():
    setup_demo_environment()
    import tkinter as tk
    import ttkbootstrap as ttk
    tk.Toplevel.wait_window = lambda self, w=None: None
    ttk.Toplevel.wait_window = lambda self, w=None: None

    from registro.gui.autoatendimento.app import AppSelfService
    from registro.gui.comum.dialogo_pin import DialogoPIN

    totem_app = AppSelfService()
    totem_app.geometry("1180x750")

    # 15. Tela Inicial Totem
    capture_widget(totem_app, "docs/imagens/15_totem_tela_inicio.png")

    # 16. Totem - Tela de Feedback Positivo / Registro Liberado
    frame_totem = totem_app.frames.get("selfservice")
    if frame_totem:
        frame_totem._lbl_nome.config(text="Ana Beatriz Silva")
        frame_totem._lbl_turma.config(text="1º Ano A - Informática")
        frame_totem._lbl_prato.config(text="Prato: Almoço Regular")
        frame_totem._lbl_mensagem.config(text="Bom apetite! Refeição confirmada.")
        frame_totem._definir_feedback_visual("sucesso")
        capture_widget(totem_app, "docs/imagens/16_totem_feedback_sucesso.png")

    # 17. PIN de Acesso Operador (F2)
    totem_pin = DialogoPIN(totem_app, titulo="🔒 Totem - Acesso do Operador", mensagem="Insira o PIN de segurança para acessar os controles operacionais:")
    totem_pin._adicionar_digito("1")
    totem_pin._adicionar_digito("2")
    totem_pin._adicionar_digito("3")
    capture_widget(totem_pin, "docs/imagens/17_totem_pin_acesso.png")
    totem_pin.destroy()

    # 18. Totem Aba Consumos
    totem_app.show_frame("consumos")
    capture_widget(totem_app, "docs/imagens/18_totem_painel_consumos.png")

    # 19. Totem Aba Dashboard Interno
    totem_app.show_frame("dashboard")
    capture_widget(totem_app, "docs/imagens/19_totem_dashboard_interno.png")

    totem_app.destroy()


def run_group_cards():
    setup_demo_environment()
    import tkinter as tk
    import ttkbootstrap as ttk
    from registro.cards.app import CardsApp
    cards_app = CardsApp()
    cards_app.geometry("1000x700")
    cards_app.students_raw = [
        {"register": "SP301001", "name": "Ana Beatriz Silva", "turma": "1º Ano A - Informática"},
        {"register": "SP301002", "name": "Carlos Eduardo Santos", "turma": "1º Ano A - Informática"},
        {"register": "SP301003", "name": "Fernanda Lima Oliveira", "turma": "2º Ano B - Mecatrônica"},
        {"register": "SP301004", "name": "Gabriel Rodrigues Costa", "turma": "2º Ano B - Mecatrônica"},
        {"register": "SP301005", "name": "Juliana Mendes Pereira", "turma": "3º Ano C - Edificações"},
    ]
    cards_app.todas_turmas = ["1º Ano A - Informática", "2º Ano B - Mecatrônica", "3º Ano C - Edificações"]
    for t in cards_app.todas_turmas:
        cards_app.turmas_vars[t] = tk.BooleanVar(value=True)
    cards_app._filtrar_estudantes()
    cards_app.status_var.set("5 estudantes carregados para emissão de crachás.")
    capture_widget(cards_app, "docs/imagens/20_cards_gerador.png")
    cards_app.destroy()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "launcher":
            run_group_launcher()
        elif cmd == "setup":
            run_group_setup()
        elif cmd == "painel":
            run_group_painel()
        elif cmd == "operador":
            run_group_operador()
        elif cmd == "totem":
            run_group_totem()
        elif cmd == "cards":
            run_group_cards()
    else:
        # Master runner launching each group in separate subprocess
        groups = ["launcher", "setup", "painel", "operador", "totem", "cards"]
        for g in groups:
            print(f"--- Running module capture: {g} ---")
            p = subprocess.run([sys.executable, str(Path(__file__).resolve()), g], capture_output=True, text=True)
            print(p.stdout)
            if p.stderr:
                print(f"[{g} STDERR]:", p.stderr)
