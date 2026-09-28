# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Linux onefile build."""

import os

datas = [('src', 'src')]
for icon in ('icon.png', 'icon.ico'):
    if os.path.exists(icon):
        datas.append((icon, '.'))

# PyInstaller finds everything reachable from main.py on its own. Only modules
# imported dynamically need to be listed here.
hiddenimports = [
    'socks',
    'sockshandler',
]

# Qt ships far more than this application uses, and PyInstaller bundles a
# module as soon as anything references it. Dropping the unused ones is the
# single biggest lever on the size of the binary.
excludes = [
    'tkinter',
    '_tkinter',
    'PIL',
    'pystray',
    'Xlib',
    'win10toast',
    'win32api',
    'win32con',
    'win32gui',
    'win32process',
    'pywin32',
    'PySide6.Qt3DAnimation',
    'PySide6.Qt3DCore',
    'PySide6.Qt3DExtras',
    'PySide6.Qt3DInput',
    'PySide6.Qt3DLogic',
    'PySide6.Qt3DRender',
    'PySide6.QtBluetooth',
    'PySide6.QtCharts',
    'PySide6.QtDataVisualization',
    'PySide6.QtDesigner',
    'PySide6.QtHelp',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
    'PySide6.QtNfc',
    'PySide6.QtOpenGL',
    'PySide6.QtOpenGLWidgets',
    'PySide6.QtPdf',
    'PySide6.QtPdfWidgets',
    'PySide6.QtPositioning',
    'PySide6.QtQml',
    'PySide6.QtQuick',
    'PySide6.QtQuick3D',
    'PySide6.QtQuickControls2',
    'PySide6.QtQuickWidgets',
    'PySide6.QtRemoteObjects',
    'PySide6.QtScxml',
    'PySide6.QtSensors',
    'PySide6.QtSerialPort',
    'PySide6.QtSpatialAudio',
    'PySide6.QtSql',
    'PySide6.QtTest',
    'PySide6.QtTextToSpeech',
    'PySide6.QtWebChannel',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineQuick',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebSockets',
    'PySide6.QtXml',
    'PySide6.scripts',
    'shiboken6_generator',
]

a = Analysis(
    ['main.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='anime-updater',
    debug=False,
    bootloader_ignore_signals=False,
    # Stripping Qt libraries has produced unusable binaries on some distros.
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
    icon='icon.png' if os.path.exists('icon.png') else None,
)
