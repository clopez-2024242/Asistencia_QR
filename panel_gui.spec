# -*- mode: python ; coding: utf-8 -*-
#
# Antes este archivo tenía la ruta de las DLL de pyzbar fija a una
# máquina específica (C:\Users\usuario\...). Aquí se resuelve en el
# momento de compilar, buscando dónde está pyzbar instalado en la
# máquina que corre `pyinstaller`, sea cual sea.

import os
import pyzbar

carpeta_pyzbar = os.path.dirname(pyzbar.__file__)
binarios_pyzbar = []
for nombre_dll in ("libiconv.dll", "libzbar-64.dll"):
    ruta_dll = os.path.join(carpeta_pyzbar, nombre_dll)
    if os.path.exists(ruta_dll):
        binarios_pyzbar.append((ruta_dll, "pyzbar"))
# En Linux/Mac estas DLL no existen (pyzbar usa la libzbar del sistema),
# así que en esos casos la lista queda vacía y no genera error.

a = Analysis(
    ['panel_gui.py'],
    pathex=[],
    binaries=binarios_pyzbar,
    datas=[],
    hiddenimports=['exportar_asistencia'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AsistenciaQR',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
