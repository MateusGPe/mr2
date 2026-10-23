# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

# 1. Coleta de recursos compartilhados (dados de temas e fontes)
datas = []
datas += collect_data_files('ttkbootstrap')

if Path('roboto.ttf').exists():
    datas.append(('roboto.ttf', '.'))

binaries = []

hidden_imports = [
    'reportlab',
    'reportlab.pdfgen',
    'reportlab.pdfbase',
    'reportlab.pdfbase.ttfonts',
    'reportlab.lib',
    'reportlab.lib.pagesizes',
    'reportlab.lib.units',
    'qrcode',
    'PIL',
    'openpyxl',
    'ttkbootstrap',
    'registro.cards',
    'registro.cards.generator',
    'registro.cards.app',
]

# 2. Análise da aplicação de crachás
a = Analysis(
    ['cards.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=2,
)

pyz = PYZ(a.pure)

# 3. Executável Onefile autocontido
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='cards',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
