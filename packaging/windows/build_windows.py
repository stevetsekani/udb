r"""
Build the Windows portable UDB application.

Steps
-----
1. Build the frontend (``npm ci && npm run build``) — skipped with --skip-frontend
2. Fetch FFmpeg static binaries — skipped with --skip-ffmpeg
3. Run PyInstaller with ``packaging/udb.spec``
4. Zip the ``dist/udb`` bundle into ``dist/UDB-Windows-x64.zip``

Usage::

    python packaging/windows/build_windows.py
    python packaging/windows/build_windows.py --skip-ffmpeg   # use system FFmpeg
"""

import argparse
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
FRONTEND = os.path.join(ROOT, 'frontend')
SPEC = os.path.join(ROOT, 'packaging', 'udb.spec')
DIST = os.path.join(ROOT, 'dist', 'udb')
ZIP_NAME = 'UDB-Windows-x64.zip'


def run(cmd, cwd=None):
    print(f'[build] $ {cmd}')
    # On Windows there is no npm.exe on PATH (only npm.cmd); Python's
    # subprocess cannot launch a .cmd shim without routing through the shell.
    # python/pip are real .exe files so they work either way.
    subprocess.run(cmd, cwd=cwd, check=True, shell=(os.name == 'nt'))


def build_frontend():
    if not os.path.isdir(os.path.join(FRONTEND, 'node_modules')):
        run(['npm', 'ci'], cwd=FRONTEND)
    run(['npm', 'run', 'build'], cwd=FRONTEND)


def fetch_ffmpeg():
    script = os.path.join(ROOT, 'packaging', 'ffmpeg', 'fetch_ffmpeg.py')
    run([sys.executable, script, '--platform', 'windows'])


def pyinstaller_build():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])
    run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', SPEC])


def make_zip():
    os.makedirs(DIST, exist_ok=True)
    zip_path = os.path.join(ROOT, 'dist', ZIP_NAME)
    if os.path.exists(zip_path):
        os.remove(zip_path)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, _dirs, files in os.walk(DIST):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.join('UDB', os.path.relpath(full, DIST))
                z.write(full, rel)
    print(f'[build] created {zip_path}')
    print(f'[build] size: {os.path.getsize(zip_path) / (1024 * 1024):.1f} MiB')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Build UDB for Windows (x64)')
    parser.add_argument('--skip-frontend', action='store_true',
                        help='Use the existing frontend/dist build')
    parser.add_argument('--skip-ffmpeg', action='store_true',
                        help='Do not download FFmpeg (system FFmpeg required at runtime)')
    parser.add_argument('--no-zip', action='store_true',
                        help='Do not create the portable ZIP')
    args = parser.parse_args(argv)

    if not args.skip_frontend:
        build_frontend()
    if not args.skip_ffmpeg:
        fetch_ffmpeg()
    pyinstaller_build()
    if not args.no_zip:
        make_zip()
    print('[build] Windows build complete.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

