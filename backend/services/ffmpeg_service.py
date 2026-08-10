"""
FFmpeg discovery service.

The packaged UDB application bundles FFmpeg so end users never need to install
it. This module implements a robust discovery order:

1. Bundled FFmpeg (inside the application bundle / packaging dir)
2. Explicitly configured path (stored in user settings)
3. System FFmpeg (``ffmpeg`` on PATH)

``ensure_ffmpeg_on_path()`` prepends the bundled directory to ``PATH`` so the
existing downloader code (which shells out to ``ffmpeg``/``ffprobe``) resolves
to the bundled binaries automatically.
"""

import os
import re
import shutil
import subprocess
import sys

from backend.app_config import get_ffmpeg_bundle_dir

MIN_FFMPEG_VERSION = (7, 1, 1)
VALID_FFMPEG_VERSION = MIN_FFMPEG_VERSION  # CLI uses this constant name

_FFMPEG_EXE = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
_FFPROBE_EXE = 'ffprobe.exe' if os.name == 'nt' else 'ffprobe'


def _find_in_dir(directory: str, exe: str):
    """Return path to ``exe`` inside ``directory`` if it exists."""
    if not directory or not os.path.isdir(directory):
        return None
    candidate = os.path.join(directory, exe)
    return candidate if os.path.isfile(candidate) else None


def get_ffmpeg_path(configured_path: str = None) -> str:
    """
    Return the full path to the FFmpeg binary to use, or None.

    Discovery order: configured path > bundled > system PATH.
    """
    # 1. Explicitly configured path
    if configured_path:
        if os.path.isfile(configured_path):
            return configured_path
        # Allow the configured value to point at a directory containing ffmpeg
        if os.path.isdir(configured_path):
            found = _find_in_dir(configured_path, _FFMPEG_EXE)
            if found:
                return found

    # 2. Bundled FFmpeg
    bundle_dir = get_ffmpeg_bundle_dir()
    found = _find_in_dir(bundle_dir, _FFMPEG_EXE)
    if found:
        return found

    # 3. System PATH
    return shutil.which(_FFMPEG_EXE)


def get_ffprobe_path(configured_path: str = None) -> str:
    """Return the full path to the FFprobe binary to use, or None."""
    ffmpeg_path = get_ffmpeg_path(configured_path)
    if ffmpeg_path:
        sibling = os.path.join(os.path.dirname(ffmpeg_path), _FFPROBE_EXE)
        if os.path.isfile(sibling):
            return sibling
    return shutil.which(_FFPROBE_EXE)


def ensure_ffmpeg_on_path(configured_path: str = None) -> str:
    """
    Prepend the directory containing the discovered FFmpeg binary to
    ``os.environ['PATH']``. Returns the chosen ffmpeg path (or None).

    This is required because the existing UDB downloader invokes ``ffmpeg`` and
    ``ffprobe`` via ``shell=True`` and we want the bundled binary to win.
    """
    ffmpeg_path = get_ffmpeg_path(configured_path)
    if ffmpeg_path:
        bin_dir = os.path.dirname(ffmpeg_path)
        if bin_dir and os.environ.get('PATH', '').split(os.pathsep)[0] != bin_dir:
            os.environ['PATH'] = bin_dir + os.pathsep + os.environ.get('PATH', '')
    return ffmpeg_path


def get_ffmpeg_version(ffmpeg_path: str = None) -> tuple:
    """
    Return the FFmpeg version as a tuple of ints, e.g. ``(7, 1, 1)``.
    Returns ``(0, 0, 0)`` when the version cannot be determined.
    """
    exe = ffmpeg_path or get_ffmpeg_path()
    if not exe:
        return (0, 0, 0)
    try:
        out = subprocess.run([exe, '-version'], capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return (0, 0, 0)
    match = re.search(r'ffmpeg version ([^\s]+)', out)
    version = match.group(1) if match else 'unknown'
    numbers = re.findall(r'\d+', version)[:3]
    if not numbers:
        return (0, 0, 0)
    return tuple(map(int, numbers))


def is_ffmpeg_valid(version: tuple) -> bool:
    """Return True when the version tuple meets the minimum requirement."""
    return version >= VALID_FFMPEG_VERSION


def get_ffmpeg_info(configured_path: str = None) -> dict:
    """Return a dict describing FFmpeg status for the Settings/Diagnostics page."""
    path = get_ffmpeg_path(configured_path)
    version = get_ffmpeg_version(path)
    return {
        'available': path is not None and is_ffmpeg_valid(version),
        'path': path,
        'version': '.'.join(map(str, version)) if version != (0, 0, 0) else 'unknown',
        'version_tuple': list(version),
        'min_required': '.'.join(map(str, VALID_FFMPEG_VERSION)),
        'valid': is_ffmpeg_valid(version),
        'source': _get_ffmpeg_source(path, configured_path),
    }


def _get_ffmpeg_source(path, configured_path) -> str:
    if not path:
        return 'missing'
    if configured_path and (path == configured_path or os.path.dirname(path) == os.path.dirname(configured_path)):
        return 'configured'
    bundle_dir = get_ffmpeg_bundle_dir()
    if bundle_dir and os.path.dirname(path) == bundle_dir:
        return 'bundled'
    return 'system'


def set_ffmpeg_bundled_env() -> None:
    """
    Convenience used at backend startup: ensure bundled FFmpeg is first on PATH
    before any downloader runs.
    """
    ensure_ffmpeg_on_path()
