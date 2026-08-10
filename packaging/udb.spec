# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the UDB desktop application.

Build (from the repository root)::

    pyinstaller --noconfirm packaging/udb.spec

What gets bundled
-----------------
* the Python engine (udb.py, Clients/, Utils/, backend/)
* the built web frontend (frontend/dist)
* the default config (config_udb.yaml)
* FFmpeg static binaries from packaging/ffmpeg/bin, when present
  (fetch them first with ``python packaging/ffmpeg/fetch_ffmpeg.py``)

The entry point is desktop/main.py, which boots the local backend and opens
the PyWebView window. ``console=False`` makes it a windowed (no-console)
application on Windows.
"""

import os
import sys

block_cipher = None

SPEC_DIR = os.path.abspath(SPECPATH)          # .../packaging
REPO_ROOT = os.path.abspath(os.path.join(SPEC_DIR, '..'))

# --------------------------------------------------------------------------- #
# Data files                                                                   #
# --------------------------------------------------------------------------- #
datas = [
    # (source_dir_or_file, target_dir_in_bundle)
    (os.path.join(REPO_ROOT, 'config_udb.yaml'), '.'),
    (os.path.join(REPO_ROOT, 'CHANGELOG.md'), '.'),
    (os.path.join(REPO_ROOT, 'frontend', 'dist'), 'frontend/dist'),
]

# Bundle FFmpeg static binaries when they have been fetched.
ffmpeg_bin = os.path.join(SPEC_DIR, 'ffmpeg', 'bin')
_ffmpeg_names = ('ffmpeg.exe', 'ffprobe.exe') if sys.platform.startswith('win') \
    else ('ffmpeg', 'ffprobe')
if os.path.isdir(ffmpeg_bin) and all(
        os.path.isfile(os.path.join(ffmpeg_bin, n)) for n in _ffmpeg_names):
    datas.append((ffmpeg_bin, 'ffmpeg/bin'))
else:
    print('WARNING: FFmpeg binaries not found in packaging/ffmpeg/bin —',
          'the app will rely on a system FFmpeg or a user-configured path.')

# --------------------------------------------------------------------------- #
# Hidden imports                                                               #
# --------------------------------------------------------------------------- #
hiddenimports = [
    # pywebview loads its GUI backend dynamically at runtime
    'webview.platforms',
    # the downloader loads clients lazily; make sure selenium + quickjs +
    # undetected_chromedriver are always available
    'undetected_chromedriver',
    'selenium',
    'quickjs',
    'Cryptodome',
]

if sys.platform.startswith('win'):
    hiddenimports += [
        'webview.platforms.edgechromium',
        'webview.platforms.mshtml',
        'webview.platforms.cef',
    ]
elif sys.platform.startswith('linux'):
    hiddenimports += [
        'webview.platforms.gtk',
        'webview.platforms.qt',
    ]
elif sys.platform == 'darwin':
    hiddenimports += [
        'webview.platforms.cocoa',
    ]

# --------------------------------------------------------------------------- #
# Analysis / build                                                             #
# --------------------------------------------------------------------------- #
a = Analysis(
    [os.path.join(REPO_ROOT, 'desktop', 'main.py')],
    pathex=[REPO_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'PyQt5.QtWidgets',
        'matplotlib', 'numpy', 'scipy', 'pandas',
        'IPython', 'notebook', 'jupyter', 'pytest',
        'PyInstaller', 'setuptools.extern', 'pip',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='udb',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # reproducible builds; UPX can be enabled for size
    console=False,      # windowed desktop app (no console window)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='udb',
)

