r"""
Application-level configuration for the UDB desktop application.

Handles platform-appropriate data directories so the packaged application
never depends on the repository working directory.

Windows:
    %APPDATA%\UDB\
Linux:
    ~/.config/udb/
"""

import os
import sys
import platform


def _is_frozen() -> bool:
    """Return True if running inside a PyInstaller bundle."""
    return getattr(sys, 'frozen', False)


def _bundle_root() -> str:
    """Return the directory containing the executable when frozen, else repo root."""
    if _is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_app_name() -> str:
    return 'UDB'


def get_app_data_dir() -> str:
    """
    Return the platform-appropriate application data directory, creating it if
    necessary.
    """
    system = platform.system()
    if system == 'Windows':
        base = os.environ.get('APPDATA') or os.path.expanduser('~')
        data_dir = os.path.join(base, 'UDB')
    elif system == 'Linux':
        base = os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config')
        data_dir = os.path.join(base, 'udb')
    elif system == 'Darwin':
        base = os.environ.get('HOME') or os.path.expanduser('~')
        data_dir = os.path.join(base, 'Library', 'Application Support', 'UDB')
    else:
        data_dir = os.path.join(os.path.expanduser('~'), '.udb')

    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_logs_dir() -> str:
    log_dir = os.path.join(get_app_data_dir(), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def get_config_path() -> str:
    """Path to the user's config_udb.yaml."""
    return os.path.join(get_app_data_dir(), 'config_udb.yaml')


def get_default_config_path() -> str:
    """
    Path to the bundled default config file.

    When frozen this is the ``_internal`` resources dir; when running from
    source it is the repository root ``config_udb.yaml``.
    """
    if _is_frozen():
        # PyInstaller places data files in sys._MEIPASS
        base = getattr(sys, '_MEIPASS', _bundle_root())
        return os.path.join(base, 'config_udb.yaml')
    return os.path.join(_bundle_root(), 'config_udb.yaml')


def get_history_db_path() -> str:
    return os.path.join(get_app_data_dir(), 'history.db')


def get_downloads_default_dir() -> str:
    """Return the user's Downloads directory."""
    system = platform.system()
    if system == 'Windows':
        return os.path.join(os.environ.get('USERPROFILE', os.path.expanduser('~')), 'Downloads')
    return os.path.join(os.path.expanduser('~'), 'Downloads')


def get_ffmpeg_bundle_dir() -> str:
    """
    Return the directory containing bundled FFmpeg binaries (``ffmpeg.exe`` /
    ``ffprobe.exe`` on Windows, ``ffmpeg`` / ``ffprobe`` on Linux), or None.
    """
    candidates = []
    if _is_frozen():
        base = getattr(sys, '_MEIPASS', _bundle_root())
        candidates.append(os.path.join(base, 'ffmpeg', 'bin'))
        candidates.append(os.path.join(base, 'ffmpeg'))
    else:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates.append(os.path.join(repo_root, 'packaging', 'ffmpeg', 'bin'))
        candidates.append(os.path.join(repo_root, 'packaging', 'ffmpeg'))

    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return None


def is_portable() -> bool:
    """Return True when running from a bundled (PyInstaller) application."""
    return _is_frozen()
