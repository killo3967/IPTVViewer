# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
datas = [('resources', 'resources')]
binaries = []
hiddenimports = ['torpy', 'torpy.client', 'torpy.cli.socks', 'torpy.socks', 'torpy.circuit', 'torpy.cells', 'torpy.consesus', 'torpy.guard', 'torpy.cell_socket', 'mpv', 'PyQt6.QtNetwork', 'socks']  # 'socks' (PySocks) se importa dinamicamente desde urllib3 - BUG-01
tmp_ret = collect_all('PyQt6')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    exclude_binaries=False,
    name='IPTVViewer',
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
