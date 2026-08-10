r"""
Build the Linux UDB application as an AppImage.

Steps
-----
1. Build the frontend (``npm ci && npm run build``) — skipped with --skip-frontend
2. Fetch FFmpeg static binaries — skipped with --skip-ffmpeg
3. Run PyInstaller with ``packaging/udb.spec``
4. Assemble an AppDir (AppRun, .desktop, icon, bundled PyInstaller output)
5. Package it with ``appimagetool`` into ``dist/UDB-x86_64.AppImage``

Requires ``libfuse2`` (or ``--appimage-extract-and-run``) at build time for
appimagetool, and a working C compiler toolchain is *not* needed (the PyInstaller
bootloader ships prebuilt).

Usage::

    python packaging/linux/build_linux.py
    python packaging/linux/build_linux.py --skip-ffmpeg
"""

import argparse
import binascii
import os
import shutil
import struct
import subprocess
import sys
import zlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
FRONTEND = os.path.join(ROOT, 'frontend')
SPEC = os.path.join(ROOT, 'packaging', 'udb.spec')
DIST = os.path.join(ROOT, 'dist')
PYINST_DIST = os.path.join(DIST, 'udb')
APP_IMAGE = os.path.join(DIST, 'UDB-x86_64.AppImage')
APPIMAGETOOL = os.path.join(DIST, 'appimagetool-x86_64.AppImage')
APPIMAGETOOL_URL = ('https://github.com/AppImage/appimagetool/releases/download/continuous/'
                    'appimagetool-x86_64.AppImage')


def run(cmd, cwd=None):
    print(f'[build] $ {cmd}')
    subprocess.run(cmd, cwd=cwd, check=True)


def build_frontend():
    if not os.path.isdir(os.path.join(FRONTEND, 'node_modules')):
        run(['npm', 'ci'], cwd=FRONTEND)
    run(['npm', 'run', 'build'], cwd=FRONTEND)


def fetch_ffmpeg():
    script = os.path.join(ROOT, 'packaging', 'ffmpeg', 'fetch_ffmpeg.py')
    run([sys.executable, script, '--platform', 'linux'])


def pyinstaller_build():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])
    run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', SPEC])


# --------------------------------------------------------------------------- #
# Minimal icon (solid colour PNG with a centred "U")                           #
# --------------------------------------------------------------------------- #
def _make_icon(path, size=256, color=(0x6D, 0x28, 0xD9)):
    """Write a minimal valid PNG icon (solid colour) to ``path``."""
    # 1x1-ish is enough; we upscale with 24-bit RGB rows.
    rows = b''
    for y in range(size):
        row = b'\x00' + bytes(color) * size
        rows += row
    raw = zlib.compress(rows)
    def chunk(tag, data):
        c = tag + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', binascii.crc32(c) & 0xffffffff)
    ihdr = struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)  # 8-bit RGB
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', raw) + chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(png)


def assemble_appdir(appdir):
    """Populate an AppDir with AppRun + desktop entry + PyInstaller bundle."""
    if os.path.isdir(appdir):
        shutil.rmtree(appdir)
    usr_lib = os.path.join(appdir, 'usr', 'lib', 'udb')
    os.makedirs(usr_lib)

    # Copy the PyInstaller one-dir bundle into the AppDir
    shutil.copytree(PYINST_DIST, usr_lib, dirs_exist_ok=True)

    # AppRun
    apprun = os.path.join(appdir, 'AppRun')
    with open(apprun, 'w', encoding='utf-8') as f:
        f.write('#!/bin/sh\n')
        f.write('exec "$APPDIR/usr/lib/udb/udb" "$@"\n')
    os.chmod(apprun, 0o755)

    # Desktop entry
    desktop = os.path.join(appdir, 'udb.desktop')
    with open(desktop, 'w', encoding='utf-8') as f:
        f.write('[Desktop Entry]\n')
        f.write('Type=Application\n')
        f.write('Name=UDB\n')
        f.write('Comment=Download anime, drama, movies and TV shows\n')
        f.write('Exec=udb\n')
        f.write('Icon=udb\n')
        f.write('Terminal=false\n')
        f.write('Categories=AudioVideo;Network;\n')

    # Icon
    icon_path = os.path.join(appdir, 'udb.png')
    _make_icon(icon_path)
    print('[build] wrote AppDir:', appdir)


def make_appimage():
    if not os.path.isfile(APPIMAGETOOL):
        import urllib.request
        print(f'[build] downloading appimagetool -> {APPIMAGETOOL}')
        urllib.request.urlretrieve(APPIMAGETOOL_URL, APPIMAGETOOL)
        os.chmod(APPIMAGETOOL, 0o755)

    if os.path.exists(APP_IMAGE):
        os.remove(APP_IMAGE)

    appdir = os.path.join(DIST, 'UDB.AppDir')
    assemble_appdir(appdir)

    env = dict(os.environ)
    env['ARCH'] = 'x86_64'
    # Some CI images cannot mount FUSE; fall back to extract-and-run.
    cmd = [APPIMAGETOOL, '--appimage-extract-and-run', appdir, APP_IMAGE]
    try:
        subprocess.run(cmd, check=True, env=env)
    except subprocess.CalledProcessError:
        print('[build] appimagetool failed with extract-and-run; trying plain run')
        subprocess.run([APPIMAGETOOL, appdir, APP_IMAGE], check=True, env=env)

    if os.path.isfile(APP_IMAGE):
        print(f'[build] created {APP_IMAGE} ({os.path.getsize(APP_IMAGE) / (1024 * 1024):.1f} MiB)')
    else:
        print('[build] ERROR: AppImage not produced')
        return 1
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Build UDB for Linux (x86_64 AppImage)')
    parser.add_argument('--skip-frontend', action='store_true')
    parser.add_argument('--skip-ffmpeg', action='store_true')
    args = parser.parse_args(argv)

    if not args.skip_frontend:
        build_frontend()
    if not args.skip_ffmpeg:
        fetch_ffmpeg()
    pyinstaller_build()
    rc = make_appimage()
    print('[build] Linux build complete.')
    return rc


if __name__ == '__main__':
    raise SystemExit(main())

