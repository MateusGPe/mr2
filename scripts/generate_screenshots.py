import ctypes
from ctypes import Structure, byref, sizeof, windll, wintypes
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

user32 = windll.user32
gdi32 = windll.gdi32


class BITMAPINFOHEADER(Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
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

    hdc_screen = user32.GetDC(target)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbm = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
    gdi32.SelectObject(hdc_mem, hbm)

    user32.PrintWindow(target, hdc_mem, 2)

    bmi = BITMAPINFOHEADER()
    bmi.biSize = sizeof(BITMAPINFOHEADER)
    bmi.biWidth = w
    bmi.biHeight = -h
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0

    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(hdc_mem, hbm, 0, h, buf, byref(bmi), 0)

    im = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    out_path = BASE_DIR / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path)

    gdi32.DeleteObject(hbm)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(target, hdc_screen)
    print(f"Successfully captured {filename} ({w}x{h})")
    return True


def setup_demo_environment():
    temp_dir = Path(tempfile.gettempdir()) / "mr2_manual_demo_env"
    config_dir = temp_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    backups_dir = temp_dir / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = temp_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    # Muda CWD antes do primeiro import de registro.nucleo.constants para que
    # todos os submódulos (inclusive config_service, grade_horarios_service,
    # models e facade) nasçam apontando para o diretório isolado de demonstração.
    os.chdir(temp_dir)
    db_path = config_dir / "registro.db"

    import registro.nucleo.constants as const

    const.DIRETORIO_CONFIG = config_dir
    const.DIRETORIO_BACKUPS = backups_dir
    const.DIRETORIO_LOG = logs_dir
    const.URL_BANCO_DADOS = f"sqlite:///{db_path}"
    const.CAMINHO_CREDENCIAS = config_dir / "credentials.json"
    const.CAMINHO_TOKEN = config_dir / "token.json"
    const.CAMINHO_SETTINGS = config_dir / "settings.json"
    const.CAMINHO_SESSAO = config_dir / "session.json"
    const.JSON_ID_PLANILHA = config_dir / "spreadsheet.json"
    const.CAMINHO_GRADE_HORARIOS = config_dir / "grade_horarios.json"
    const.CAMINHO_JSON_LANCHES = config_dir / "lanches.json"
    const.CAMINHO_JSON_PRESETS_TURMAS = config_dir / "presets_turmas.json"
    const.CAMINHO_JSON_TURMAS_INTEGRADO = config_dir / "turmas_integrado.json"
    const.CAMINHO_CSV_ESTUDANTES = config_dir / "students.csv"
    const.CAMINHO_CSV_RESERVAS = config_dir / "reserves.csv"

    with open(const.CAMINHO_SETTINGS, "w", encoding="utf-8") as f:
        json.dump(
            {
                "pin_hash": "",
                "pin_salt": "",
                "totem": {
                    "fullscreen": False,
                    "camera_on_start": False,
                    "require_pin_to_exit": True,
                    "feedback_delay_ms": 1500,
                    "camera_index": 0,
                },
                "audio": {
                    "habilitado": True,
                    "freq_sucesso": 1000,
                    "dur_sucesso_ms": 200,
                    "freq_erro": 400,
                    "dur_erro_ms": 1000,
                },
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    with open(const.JSON_ID_PLANILHA, "w", encoding="utf-8") as f:
        json.dump(
            {"spreadsheet_id": "1A2B3C4D5E6F7G8H9I0J_EXEMPLO_GOOGLE_SHEETS"},
            f,
            indent=2,
        )

    with open(const.CAMINHO_JSON_LANCHES, "w", encoding="utf-8") as f:
        json.dump(
            [
                "Achocolatado e Biscoito Maisena",
                "Iogurte com Cereais",
                "Salada de Frutas Especial",
                "Suco de Uva e Banana",
            ],
            f,
            indent=2,
            ensure_ascii=False,
        )

    with open(const.CAMINHO_JSON_TURMAS_INTEGRADO, "w", encoding="utf-8") as f:
        json.dump(
            [
                "1º Ano A - Informática",
                "2º Ano B - Mecatrônica",
                "3º Ano C - Edificações",
            ],
            f,
            indent=2,
            ensure_ascii=False,
        )

    from registro.nucleo.services.grade_horarios_service import MAPA_DIAS_SEMANA

    hoje_dia = MAPA_DIAS_SEMANA.get(dt.date.today().weekday(), "segunda")
    grade_demo = {
        dia: {"almoco": [], "jantar": [], "lanche": []}
        for dia in (
            "segunda",
            "terca",
            "quarta",
            "quinta",
            "sexta",
            "sabado",
            "domingo",
        )
    }
    slots_almoco_demo = [
        {
            "inicio": "11:15",
            "fim": "11:35",
            "turmas": ["*"],
            "categorias": ["PAP", "ESP1"],
        },
        {
            "inicio": "11:30",
            "fim": "12:15",
            "turmas": ["1º Ano A - Informática", "2º Ano B - Mecatrônica"],
            "categorias": ["*"],
        },
        {
            "inicio": "12:15",
            "fim": "13:00",
            "turmas": ["3º Ano C - Edificações", "Engenharia de Controle"],
            "categorias": ["*"],
        },
    ]
    for dia_util in ("segunda", "terca", "quarta", "quinta", "sexta"):
        grade_demo[dia_util]["almoco"] = list(slots_almoco_demo)
        grade_demo[dia_util]["lanche"] = [
            {
                "inicio": "15:10",
                "fim": "15:35",
                "turmas": ["1º Ano A - Informática", "2º Ano B - Mecatrônica"],
                "categorias": ["*"],
            }
        ]
    grade_demo[hoje_dia]["almoco"] = list(slots_almoco_demo)

    with open(const.CAMINHO_GRADE_HORARIOS, "w", encoding="utf-8") as f:
        json.dump(grade_demo, f, indent=2, ensure_ascii=False)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import registro.nucleo.models as models

    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    models.motor = engine
    models.SessaoLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    import registro.nucleo.facade as facade_mod

    facade_mod.SessaoLocal = models.SessaoLocal
    models.criar_banco_de_dados_e_tabelas()

    from registro.nucleo.models import Consumo, Estudante, Grupo, Reserva, Sessao

    hoje_br = dt.date.today().strftime("%d/%m/%Y")

    with models.SessaoLocal() as session:
        if session.query(Estudante).count() == 0:
            g1 = Grupo(nome="1º Ano A - Informática", tipo="turma", ativo=True)
            g2 = Grupo(nome="2º Ano B - Mecatrônica", tipo="turma", ativo=True)
            g3 = Grupo(nome="3º Ano C - Edificações", tipo="turma", ativo=True)
            g4 = Grupo(nome="Engenharia de Controle", tipo="turma", ativo=True)
            g_pap = Grupo(nome="PAP", tipo="categoria", ativo=True)
            g_esp = Grupo(nome="ESP1", tipo="categoria", ativo=True)
            session.add_all([g1, g2, g3, g4, g_pap, g_esp])
            session.flush()

            alunos_data = [
                ("SP301001", "Ana Beatriz Silva", [g1, g_pap]),
                ("SP301002", "Carlos Eduardo Santos", [g1]),
                ("SP301003", "Fernanda Lima Oliveira", [g2]),
                ("SP301004", "Gabriel Rodrigues Costa", [g2, g_esp]),
                ("SP301005", "Juliana Mendes Pereira", [g3]),
                ("SP301006", "Lucas Martins Souza", [g1, g2]),
                ("SP301007", "Mariana Alves Ribeiro", [g3, g_pap]),
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
                refeicao="almoço",
                periodo="Integral",
                data=hoje_br,
                hora="12:00",
                item_servido=None,
                grupos=[g1, g2, g3, g4],
            )
            session.add(s1)
            session.flush()

            with open(const.CAMINHO_SESSAO, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "id_sessao": s1.id,
                        "excecao_grupos": [],
                        "ignorar_horario_grade": False,
                    },
                    f,
                    indent=2,
                )

            r1 = Reserva(
                estudante_id=estudantes[0].id,
                data=hoje_br,
                prato="Tradicional",
                almoco=True,
                jantar=False,
                cancelada=False,
            )
            r2 = Reserva(
                estudante_id=estudantes[1].id,
                data=hoje_br,
                prato="Tradicional",
                almoco=True,
                jantar=False,
                cancelada=False,
            )
            r3 = Reserva(
                estudante_id=estudantes[2].id,
                data=hoje_br,
                prato="Vegetariano",
                almoco=True,
                jantar=False,
                cancelada=False,
            )
            r4 = Reserva(
                estudante_id=estudantes[3].id,
                data=hoje_br,
                prato="Vegano",
                almoco=True,
                jantar=False,
                cancelada=False,
            )
            r5 = Reserva(
                estudante_id=estudantes[4].id,
                data=hoje_br,
                prato="Tradicional",
                almoco=True,
                jantar=False,
                cancelada=False,
            )
            session.add_all([r1, r2, r3, r4, r5])
            session.flush()

            c1 = Consumo(
                estudante_id=estudantes[0].id,
                sessao_id=s1.id,
                hora_consumo="12:04:15",
                reserva_id=r1.id,
                ativo=True,
            )
            c2 = Consumo(
                estudante_id=estudantes[1].id,
                sessao_id=s1.id,
                hora_consumo="12:06:30",
                reserva_id=r2.id,
                ativo=True,
            )
            c3 = Consumo(
                estudante_id=estudantes[2].id,
                sessao_id=s1.id,
                hora_consumo="12:08:45",
                reserva_id=r3.id,
                ativo=True,
            )
            session.add_all([c1, c2, c3])
            session.commit()


def run_group_launcher():
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import CENTER, X

    root_l = ttk.Window(
        title="Registro de Refeições",
        themename="sandstone",
        resizable=(False, False),
    )
    root_l.geometry("520x600")
    container = ttk.Frame(root_l, padding=25)
    container.pack(fill="both", expand=True)

    ttk.Label(
        container,
        text="🍽️ Sistema de Refeitório",
        font=("Segoe UI", 16, "bold"),
        anchor=CENTER,
    ).pack(fill=X, pady=(0, 4))
    ttk.Label(
        container,
        text="Selecione o módulo que deseja iniciar:",
        font=("Segoe UI", 10),
        bootstyle="secondary",
        anchor=CENTER,
    ).pack(fill=X, pady=(0, 16))

    ttk.Button(
        container,
        text="📝  Registrar Refeições\nControle e registro de consumo em tempo real",
        bootstyle="primary-outline",
    ).pack(fill=X, pady=4, ipady=4)
    ttk.Button(
        container,
        text="📊  Painel Administrativo\nGestão de alunos, turmas, reservas e relatórios",
        bootstyle="info-outline",
    ).pack(fill=X, pady=4, ipady=4)
    ttk.Button(
        container,
        text="🤖  Totem de Autoatendimento\nTerminal autônomo com leitor de QR Code / câmera",
        bootstyle="success-outline",
    ).pack(fill=X, pady=4, ipady=4)
    ttk.Button(
        container,
        text="💳  Gerador de Crachás & Cartões\nEmissão e impressão de cartões com QR Code",
        bootstyle="warning-outline",
    ).pack(fill=X, pady=4, ipady=4)
    ttk.Button(
        container,
        text="⚙️  Configurações & Início Rápido\nGoogle Cloud, PIN de segurança, backups e grade horária",
        bootstyle="secondary-outline",
    ).pack(fill=X, pady=4, ipady=4)

    ttk.Label(
        container,
        text="Dica: Em atalhos, use as flags /painel, /auto, /reg, /cards ou /setup para abrir direto.",
        font=("Segoe UI", 8),
        bootstyle="secondary",
        anchor=CENTER,
    ).pack(fill=X, side="bottom", pady=(12, 0))

    capture_widget(root_l, "docs/imagens/01_launcher_principal.png")
    root_l.destroy()


def run_group_setup():
    setup_demo_environment()
    import tkinter as tk
    import ttkbootstrap as ttk

    tk.Toplevel.wait_window = lambda self, w=None: None
    ttk.Toplevel.wait_window = lambda self, w=None: None

    from registro.gui.comum.dialogo_pin import DialogoPIN
    from registro.gui.setup.app import AppSetup
    from registro.nucleo.backup_service import criar_backup

    # Cria backup de demonstração para popular a aba de backups
    try:
        criar_backup(prefixo="backup_registro_demo")
    except (OSError, RuntimeError, ValueError) as e:
        print(f"Aviso: falha ao criar backup de demonstração: {e}")

    setup_app = AppSetup()
    setup_app.geometry("980x700")

    setup_app.notebook.select(setup_app.aba_status)
    capture_widget(setup_app, "docs/imagens/02_setup_checklist.png")

    setup_app.notebook.select(setup_app.aba_google)
    capture_widget(setup_app, "docs/imagens/21_setup_google_cloud.png")

    setup_app.notebook.select(setup_app.aba_totem)
    capture_widget(setup_app, "docs/imagens/22_setup_totem_seguranca.png")

    setup_app.notebook.select(setup_app.aba_grade)
    capture_widget(setup_app, "docs/imagens/23_setup_grade_horarios.png")

    setup_app.notebook.select(setup_app.aba_backup)
    setup_app._atualizar_lista_backups()
    capture_widget(setup_app, "docs/imagens/24_setup_backups.png")

    setup_app.notebook.select(setup_app.aba_geral)
    capture_widget(setup_app, "docs/imagens/25_setup_geral_utilitarios.png")

    pin_dialog = DialogoPIN(
        setup_app,
        titulo="🔒 Autenticação do Totem",
        mensagem="Digite o PIN de 4 dígitos para autorizar alterações:",
    )
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
    from registro.gui.painel.dialogos import (
        ReservaDialog,
        StudentDialog,
        TurmaDialog,
        VincularAlunoDialog,
    )
    from registro.nucleo.models import Estudante, Grupo

    painel = PainelApp()
    painel.geometry("1200x750")

    # 04. Aba Alunos
    painel.show_frame("alunos")
    capture_widget(painel, "docs/imagens/04_painel_alunos.png")

    # 05. Diálogo Aluno
    with painel.fachada_nucleo.repo_estudante.obter_sessao() as s:
        e = s.query(Estudante).first()
        eid = e.id if e else None
    st_dialog = StudentDialog(painel, painel.fachada_nucleo, student_id=eid)
    capture_widget(st_dialog, "docs/imagens/05_painel_aluno_dialogo.png")
    st_dialog.destroy()

    # 06. Aba Turmas
    painel.show_frame("turmas")
    capture_widget(painel, "docs/imagens/06_painel_turmas.png")

    # 07. Diálogo Turma & 26. Vincular Aluno
    with painel.fachada_nucleo.repo_grupo.obter_sessao() as s:
        g = s.query(Grupo).first()
        gid = g.id if g else None
        gnome = g.nome if g else "1º Ano A - Informática"

    turma_dialog = TurmaDialog(painel, painel.fachada_nucleo, turma_id=gid)
    capture_widget(turma_dialog, "docs/imagens/07_painel_turma_dialogo.png")
    turma_dialog.destroy()

    vinc_dialog = VincularAlunoDialog(
        painel, painel.fachada_nucleo, turma_id=gid or 1, nome_turma=gnome
    )
    capture_widget(vinc_dialog, "docs/imagens/26_painel_vincular_aluno.png")
    vinc_dialog.destroy()

    # 08. Aba Reservas
    painel.show_frame("reservas")
    capture_widget(painel, "docs/imagens/08_painel_reservas.png")

    # 09. Diálogo Reserva
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

    from registro.gui.comum.dialogo_cancelamento import DialogoConfirmarCancelamento
    from registro.gui.registrar.app import AppRegistro
    from registro.gui.registrar.dialogo_filtro_turmas import DialogoFiltroTurmas
    from registro.gui.registrar.dialogo_sessao import DialogoSessao

    op_app = AppRegistro()
    op_app.geometry("1180x700")

    # 12. Diálogo Abrir Sessão
    sess_dialog = DialogoSessao(
        "Gerenciar Sessão de Refeição",
        callback=lambda d: True,
        parente_app=op_app,
    )
    capture_widget(sess_dialog, "docs/imagens/12_operador_abrir_sessao.png")
    sess_dialog.destroy()

    # 27. Diálogo Filtro de Turmas
    filtro_dialog = DialogoFiltroTurmas(
        op_app, op_app.get_fachada(), callback_aplicar=lambda _g: None
    )
    capture_widget(filtro_dialog, "docs/imagens/27_operador_filtro_turmas.png")
    filtro_dialog.destroy()

    # 28. Diálogo Cancelamento Auditado
    canc_dialog = DialogoConfirmarCancelamento(
        op_app,
        prontuario="SP301001",
        nome="Ana Beatriz Silva",
        operador_padrao="Maria (Refeitório)",
        motivo_padrao="Registro duplicado na fila",
    )
    capture_widget(canc_dialog, "docs/imagens/28_operador_cancelar_consumo.png")
    canc_dialog.destroy()

    # 13. Terminal com Sessão Ativa
    capture_widget(op_app, "docs/imagens/13_operador_terminal_ativo.png")

    # 14. Confirmação de Sucesso
    if op_app._painel_acao and op_app._painel_acao._label_aluno_selecionado:
        op_app._painel_acao._label_aluno_selecionado.config(
            text="Pront: SP301001  [PAP]\nNome: Ana Beatriz Silva\nTurma: 1º Ano A - Informática\nPrato: Tradicional\n\n✅ PRESENÇA CONFIRMADA COM SUCESSO!",
            bootstyle="@success",
        )
    if op_app._label_barra_status:
        op_app._label_barra_status.config(
            text="Consumo registrado com sucesso para Ana Beatriz Silva às 12:05."
        )
    capture_widget(op_app, "docs/imagens/14_operador_confirmacao_sucesso.png")
    op_app.destroy()


def run_group_totem():
    setup_demo_environment()
    import tkinter as tk
    import ttkbootstrap as ttk

    tk.Toplevel.wait_window = lambda self, w=None: None
    ttk.Toplevel.wait_window = lambda self, w=None: None

    from registro.gui.autoatendimento.app import AppSelfService
    from registro.gui.autoatendimento.dialogo_horarios import DialogoGradeHorariosTotem
    from registro.gui.autoatendimento.dialogos import (
        DialogoDetalhesConsumo,
        DialogoNovoConsumo,
    )
    from registro.gui.comum.dialogo_pin import DialogoPIN

    totem_app = AppSelfService()
    totem_app.geometry("1180x750")

    # 15. Tela Inicial Totem
    capture_widget(totem_app, "docs/imagens/15_totem_tela_inicio.png")

    # 29. Totem - Diálogo Horários por Turma (com hora simulada para mostrar badge Ativo + Em Breve)
    horarios_dialog = DialogoGradeHorariosTotem(
        totem_app,
        totem_app.fachada_nucleo,
        timeout_segundos=15,
        hora_simulada="11:45",
    )
    capture_widget(horarios_dialog, "docs/imagens/29_totem_horarios_turma.png")
    horarios_dialog.fechar()

    # 30. Totem - Menu de Contexto / Controles do Operador
    frame_totem = totem_app.frames.get("selfservice")
    if frame_totem:
        totem_app.update_idletasks()
        totem_app.update()
        # Captura estado visual de sucesso
        frame_totem._lbl_nome.config(text="Ana Beatriz Silva")
        frame_totem._lbl_turma.config(text="1º Ano A - Informática")
        frame_totem._lbl_prato.config(text="Prato: Tradicional")
        frame_totem._lbl_mensagem.config(text="Bom apetite! Refeição confirmada.")
        frame_totem._definir_feedback_visual("sucesso")
        capture_widget(totem_app, "docs/imagens/16_totem_feedback_sucesso.png")
        frame_totem._definir_feedback_visual("padrao")

    # 30. Diálogo visual simulado / janela real de controles via janela flutuante se aplicável:
    # Em Windows PrintWindow sobre menu tk.Menu nativo pode não aparecer no PrintWindow da janela pai,
    # então renderizamos um preview fiel do menu sobreposto ao Totem usando um Toplevel leve apenas para a captura.
    menu_preview = tk.Toplevel(totem_app)
    menu_preview.title("Menu de Controles do Operador (F2 / Ctrl+M)")
    menu_preview.geometry("320x340")
    menu_frame = ttk.Frame(menu_preview, padding=10)
    menu_frame.pack(fill="both", expand=True)
    for item_txt, bold in [
        ("🤖  Modo Totem (Leitura)", True),
        ("📋  Consumos Registrados", False),
        ("📊  Dashboard & Estatísticas", False),
        ("---", False),
        ("📆  Trocar / Abrir Sessão...", False),
        ("🕒  Horários das Turmas...", False),
        ("☑️  Filtrar Turmas da Sessão...", False),
        ("☐  Modo Horário Livre (Desativado)", False),
        ("---", False),
        ("📥  Baixar Cadastros (Google Sheets)", False),
        ("📤  Enviar Consumos (Google Sheets)", False),
        ("---", False),
        ("🖥️  Alternar Tela Cheia (F11)", False),
        ("❌  Sair do Totem", False),
    ]:
        if item_txt == "---":
            ttk.Separator(menu_frame, orient="horizontal").pack(fill="x", pady=4)
        else:
            ttk.Label(
                menu_frame,
                text=item_txt,
                font=("Segoe UI", 9, "bold" if bold else "normal"),
                anchor="w",
            ).pack(fill="x", padx=6, pady=2)
    capture_widget(menu_preview, "docs/imagens/30_totem_menu_controles.png")
    menu_preview.destroy()

    # 17. PIN de Acesso Operador (F2)
    totem_pin = DialogoPIN(
        totem_app,
        titulo="🔒 Totem - Acesso do Operador",
        mensagem="Insira o PIN de segurança para acessar os controles operacionais:",
    )
    totem_pin._adicionar_digito("1")
    totem_pin._adicionar_digito("2")
    totem_pin._adicionar_digito("3")
    capture_widget(totem_pin, "docs/imagens/17_totem_pin_acesso.png")
    totem_pin.destroy()

    # 18. Totem Aba Consumos
    totem_app.show_frame("consumos")
    capture_widget(totem_app, "docs/imagens/18_totem_painel_consumos.png")

    # 31. Totem - Diálogo Novo Consumo Manual
    novo_cons_dialog = DialogoNovoConsumo(totem_app, totem_app.fachada_nucleo)
    capture_widget(novo_cons_dialog, "docs/imagens/31_totem_novo_consumo.png")
    novo_cons_dialog.destroy()

    # 32. Totem - Diálogo Detalhes do Consumo
    detalhes_dialog = DialogoDetalhesConsumo(
        totem_app,
        dados_consumo={
            "id_consumo": 1,
            "pront": "SP301001",
            "nome": "Ana Beatriz Silva",
            "turma": "1º Ano A - Informática",
            "hora_consumo": "12:04:15",
            "prato": "Tradicional",
        },
        on_editar=lambda: None,
        on_excluir=lambda: None,
    )
    capture_widget(detalhes_dialog, "docs/imagens/32_totem_detalhes_consumo.png")
    detalhes_dialog.destroy()

    # 19. Totem Aba Dashboard Interno
    totem_app.show_frame("dashboard")
    capture_widget(totem_app, "docs/imagens/19_totem_dashboard_interno.png")

    totem_app.destroy()


def run_group_cards():
    setup_demo_environment()
    import tkinter as tk
    from registro.cards.app import CardsApp

    cards_app = CardsApp()
    cards_app.geometry("1000x700")
    cards_app.students_raw = [
        {
            "register": "SP301001",
            "name": "Ana Beatriz Silva",
            "turma": "1º Ano A - Informática",
        },
        {
            "register": "SP301002",
            "name": "Carlos Eduardo Santos",
            "turma": "1º Ano A - Informática",
        },
        {
            "register": "SP301003",
            "name": "Fernanda Lima Oliveira",
            "turma": "2º Ano B - Mecatrônica",
        },
        {
            "register": "SP301004",
            "name": "Gabriel Rodrigues Costa",
            "turma": "2º Ano B - Mecatrônica",
        },
        {
            "register": "SP301005",
            "name": "Juliana Mendes Pereira",
            "turma": "3º Ano C - Edificações",
        },
    ]
    cards_app.todas_turmas = [
        "1º Ano A - Informática",
        "2º Ano B - Mecatrônica",
        "3º Ano C - Edificações",
    ]
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
        temp_dir = Path(tempfile.gettempdir()) / "mr2_manual_demo_env"
        shutil.rmtree(temp_dir, ignore_errors=True)
        groups = ["launcher", "setup", "painel", "operador", "totem", "cards"]
        for g in groups:
            print(f"--- Running module capture: {g} ---")
            p = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), g],
                capture_output=True,
                text=True,
            )
            print(p.stdout)
            if p.stderr:
                print(f"[{g} STDERR]:", p.stderr)
