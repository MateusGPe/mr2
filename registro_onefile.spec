# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# 1. Coleta de recursos compartilhados (dados e DLLs)
datas = []
datas += collect_data_files('ttkbootstrap')

if Path('roboto.ttf').exists():
    datas.append(('roboto.ttf', '.'))

binaries = []
binaries += collect_dynamic_libs('pyzbar')

hidden_imports = [
    'pyzbar',
    'cv2',
    'PIL',
    'ttkbootstrap',
    'registro.launcher',
    'registro.gui.registrar.app',
    'registro.gui.painel.app',
    'registro.gui.autoatendimento.app',
]

# 2. Análise da aplicação completa a partir do despachante unificado
a = Analysis(
    ['registro/launcher.py'],
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
    name='registro',
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
    version='version_info.txt',
)
