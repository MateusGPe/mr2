# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# 1. Coleta arquivos de dados necessários para a interface e funcionalidades
datas = []
datas += collect_data_files('ttkbootstrap')

# 2. Coleta as DLLs do pyzbar que estão causando o WinError 2
binaries = collect_dynamic_libs('pyzbar')

a = Analysis(
    ['registro/gui/app_registro.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=['pyzbar', 'cv2'], 
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [], # Deixamos vazio para o modo onedir
    exclude_binaries=True, # Flag essencial para desativar o OneFile
    name='registrar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False, 
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# 3. Bloco COLLECT: Agrupa tudo em uma pasta na pasta 'dist'
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='registrar',
)