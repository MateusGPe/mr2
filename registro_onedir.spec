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

hidden_imports = ['pyzbar', 'cv2', 'PIL', 'ttkbootstrap']

# 2. Análise do app 'registrar'
a_registrar = Analysis(
    ['registro/gui/registrar/app.py'],
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
pyz_registrar = PYZ(a_registrar.pure)
exe_registrar = EXE(
    pyz_registrar,
    a_registrar.scripts,
    [],
    exclude_binaries=True,
    name='registrar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.txt',
)

# 3. Análise do app 'painel'
a_painel = Analysis(
    ['registro/gui/painel/app.py'],
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
pyz_painel = PYZ(a_painel.pure)
exe_painel = EXE(
    pyz_painel,
    a_painel.scripts,
    [],
    exclude_binaries=True,
    name='painel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.txt',
)

# 4. Análise do app 'autoatendimento'
a_autoatendimento = Analysis(
    ['registro/gui/autoatendimento/app.py'],
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
pyz_autoatendimento = PYZ(a_autoatendimento.pure)
exe_autoatendimento = EXE(
    pyz_autoatendimento,
    a_autoatendimento.scripts,
    [],
    exclude_binaries=True,
    name='autoatendimento',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.txt',
)

# 5. Agrupamento em um único diretório compartilhado ('dist/registro')
coll = COLLECT(
    exe_registrar,
    a_registrar.binaries,
    a_registrar.zipfiles,
    a_registrar.datas,
    exe_painel,
    a_painel.binaries,
    a_painel.zipfiles,
    a_painel.datas,
    exe_autoatendimento,
    a_autoatendimento.binaries,
    a_autoatendimento.zipfiles,
    a_autoatendimento.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='registro',
)
