"""Tests for platform-specific path resolution in app_config."""

import os

from backend import app_config


def _norm(p):
    # Make path comparisons robust regardless of the host's separator.
    return p.replace('\\', '/') if p else p


def test_app_data_dir_windows(monkeypatch):
    monkeypatch.setattr(app_config.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(app_config.os, 'makedirs', lambda *a, **k: None)
    monkeypatch.setenv('APPDATA', r'C:\Users\Test\AppData\Roaming')
    assert _norm(app_config.get_app_data_dir()) == 'C:/Users/Test/AppData/Roaming/UDB'


def test_app_data_dir_linux(monkeypatch):
    monkeypatch.setattr(app_config.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(app_config.os, 'makedirs', lambda *a, **k: None)
    monkeypatch.setenv('XDG_CONFIG_HOME', '/home/test/.config')
    monkeypatch.delenv('HOME', raising=False)
    assert _norm(app_config.get_app_data_dir()) == '/home/test/.config/udb'


def test_app_data_dir_macos(monkeypatch):
    monkeypatch.setattr(app_config.platform, 'system', lambda: 'Darwin')
    monkeypatch.setattr(app_config.os, 'makedirs', lambda *a, **k: None)
    monkeypatch.setenv('HOME', '/Users/test')
    assert _norm(app_config.get_app_data_dir()) == '/Users/test/Library/Application Support/UDB'


def test_downloads_default_windows(monkeypatch):
    monkeypatch.setattr(app_config.platform, 'system', lambda: 'Windows')
    monkeypatch.setenv('USERPROFILE', r'C:\Users\Test')
    assert _norm(app_config.get_downloads_default_dir()) == 'C:/Users/Test/Downloads'


def test_downloads_default_linux(monkeypatch):
    monkeypatch.setattr(app_config.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(app_config.os.path, 'expanduser', lambda p: '/home/test' + p.lstrip('~'))
    assert _norm(app_config.get_downloads_default_dir()) == '/home/test/Downloads'


def test_is_portable_in_dev(monkeypatch):
    monkeypatch.setattr(app_config, '_is_frozen', lambda: False)
    assert app_config.is_portable() is False


def test_bundle_root_repo():
    # When not frozen, _bundle_root is the repo root.
    root = app_config._bundle_root()
    assert os.path.isfile(os.path.join(root, 'udb.py'))


def test_ffmpeg_bundle_dir_no_crash(monkeypatch):
    monkeypatch.setattr(app_config, '_is_frozen', lambda: False)
    # Returns a path under packaging/ffmpeg (the repo layout) or None; never
    # raises, even when the bin subfolder has not been populated.
    result = app_config.get_ffmpeg_bundle_dir()
    assert result is None or 'packaging' in result

