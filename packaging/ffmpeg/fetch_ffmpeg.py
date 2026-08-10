r"""
Download and extract FFmpeg static binaries for bundling with UDB.

Only used by maintainers / CI. End users never run this.

Usage::

    python packaging/ffmpeg/fetch_ffmpeg.py            # current platform
    python packaging/ffmpeg/fetch_ffmpeg.py --platform windows
    python packaging/ffmpeg/fetch_ffmpeg.py --force    # re-download even if present

Outputs (binaries verified to exist after extraction):

* Windows  -> ``packaging/ffmpeg/bin/ffmpeg.exe``, ``ffprobe.exe``
* Linux    -> ``packaging/ffmpeg/bin/ffmpeg``, ``ffprobe``

Sources:

* Windows: BtbN FFmpeg-Builds ``ffmpeg-master-latest-win64-gpl.zip``
  (GPL build, includes ffprobe; min supported version is always newer than
  UDB's floor of 7.1.1)
* Linux:   johnvansickle.com ``ffmpeg-release-amd64-static.tar.xz``
  (static build for x86_64, includes ffprobe)

Override the download URL with ``UDB_FFMPEG_URL`` for a pinned mirror.
"""

import argparse
import os
import shutil
import sys
import tarfile
import tempfile
import zipfile

import requests

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(_THIS_DIR, 'bin')

# Latest-master builds from BtbN (Windows). The version is always well above
# the required minimum (7.1.1) and includes both ffmpeg.exe and ffprobe.exe.
WINDOWS_URL = ('https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/'
               'ffmpeg-master-latest-win64-gpl.zip')

# Static builds from johnvansickle (Linux x86_64). Also includes ffprobe.
LINUX_URL = 'https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz'


def _download(url: str, dest: str) -> None:
    print(f'[ffmpeg] downloading {url}')
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, 'wb') as f:
            shutil.copyfileobj(r.raw, f)
    print(f'[ffmpeg] saved {dest} ({os.path.getsize(dest) // 1024} KiB)')


def _fetch_windows() -> list:
    target = 'ffmpeg.exe', 'ffprobe.exe'
    if all(os.path.isfile(os.path.join(BIN_DIR, t)) for t in target):
        print('[ffmpeg] binaries already present in packaging/ffmpeg/bin — nothing to do')
        return list(target)
    os.makedirs(BIN_DIR, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='udb-ffmpeg-')
    try:
        archive = os.path.join(tmp, 'ffmpeg.zip')
        _download(os.environ.get('UDB_FFMPEG_URL', WINDOWS_URL), archive)
        with zipfile.ZipFile(archive) as z:
            z.extractall(tmp)
        # find ffmpeg.exe under tmp
        found = {}
        for root, _dirs, files in os.walk(tmp):
            for f in files:
                if f in target and f not in found:
                    found[f] = os.path.join(root, f)
        for name, src in found.items():
            shutil.copy2(src, os.path.join(BIN_DIR, name))
        return [os.path.join(BIN_DIR, t) for t in target if os.path.isfile(os.path.join(BIN_DIR, t))]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _fetch_linux() -> list:
    target = 'ffmpeg', 'ffprobe'
    if all(os.path.isfile(os.path.join(BIN_DIR, t)) for t in target):
        print('[ffmpeg] binaries already present in packaging/ffmpeg/bin — nothing to do')
        return list(target)
    os.makedirs(BIN_DIR, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='udb-ffmpeg-')
    try:
        archive = os.path.join(tmp, 'ffmpeg.tar.xz')
        _download(os.environ.get('UDB_FFMPEG_URL', LINUX_URL), archive)
        with tarfile.open(archive, 'r:xz') as t:
            t.extractall(tmp)
        found = {}
        for root, _dirs, files in os.walk(tmp):
            for f in files:
                if f in target and f not in found:
                    found[f] = os.path.join(root, f)
        for name, src in found.items():
            shutil.copy2(src, os.path.join(BIN_DIR, name))
            os.chmod(os.path.join(BIN_DIR, name), 0o755)
        return [os.path.join(BIN_DIR, t) for t in target if os.path.isfile(os.path.join(BIN_DIR, t))]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _verify(platform: str, bins: list) -> int:
    if len(bins) != 2:
        print(f'[ffmpeg] ERROR: expected 2 binaries, found {len(bins)}: {bins}')
        return 1
    for b in bins:
        print(f'[ffmpeg] ok: {b}')
    if platform == 'linux':
        # make sure the static binaries can actually execute (missing glibc
        # deps would show up here)
        for b in bins:
            if os.access(b, os.X_OK):
                try:
                    import subprocess
                    subprocess.run([b, '-version'], check=True, capture_output=True)
                    print(f'[ffmpeg] executes: {os.path.basename(b)}')
                except Exception as exc:
                    print(f'[ffmpeg] WARNING: {b} could not be executed: {exc}')
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Fetch FFmpeg static binaries for UDB')
    parser.add_argument('--platform', choices=['windows', 'linux'], default=None,
                        help='Override platform detection (default: detect)')
    parser.add_argument('--force', action='store_true',
                        help='Re-download even if binaries are already present')
    args = parser.parse_args(argv)

    platform = args.platform or (
        'windows' if sys.platform.startswith('win') else
        'linux' if sys.platform.startswith('linux') else None)
    if platform is None:
        print(f'[ffmpeg] unsupported platform: {sys.platform}')
        return 1

    # --force: clear existing binaries
    if args.force and os.path.isdir(BIN_DIR):
        for name in ('ffmpeg', 'ffprobe', 'ffmpeg.exe', 'ffprobe.exe'):
            p = os.path.join(BIN_DIR, name)
            if os.path.exists(p):
                os.remove(p)

    bins = _fetch_windows() if platform == 'windows' else _fetch_linux()
    return _verify(platform, bins)


if __name__ == '__main__':
    raise SystemExit(main())

