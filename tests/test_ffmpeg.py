"""Tests for FFmpeg discovery logic (no real FFmpeg required)."""

import os

from backend.services import ffmpeg_service as ffmpeg


def test_configured_path_wins(tmp_path, monkeypatch):
    exe = tmp_path / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
    exe.write_bytes(b'fake')
    found = ffmpeg.get_ffmpeg_path(str(exe))
    assert found == str(exe)


def test_configured_directory_finds_binary(tmp_path):
    exe = tmp_path / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
    exe.write_bytes(b'fake')
    found = ffmpeg.get_ffmpeg_path(str(tmp_path))
    assert found == str(exe)


def test_missing_configured_falls_back(tmp_path):
    # Nonexistent configured path falls through to system PATH lookup (None here).
    found = ffmpeg.get_ffmpeg_path(str(tmp_path / 'missing' / 'ffmpeg'))
    assert found is None or os.path.isfile(found)


def test_version_parsing(monkeypatch, tmp_path):
    # Feed a fake binary that reports a modern version via stdout.
    import types

    exe = tmp_path / 'ffmpeg-fake'
    exe.write_bytes(b'fake')

    def fake_run(cmd, **kwargs):
        return types.SimpleNamespace(
            stdout='ffmpeg version 7.1.1-full_build-www.gyan.dev Copyright (c) 2000-2024 the FFmpeg developers')

    monkeypatch.setattr(ffmpeg.subprocess, 'run', fake_run)
    version = ffmpeg.get_ffmpeg_version(str(exe))
    assert version == (7, 1, 1)


def test_is_ffmpeg_valid():
    assert ffmpeg.is_ffmpeg_valid((7, 1, 1)) is True
    assert ffmpeg.is_ffmpeg_valid((7, 0, 0)) is False
    assert ffmpeg.is_ffmpeg_valid((0, 0, 0)) is False


def test_get_ffmpeg_info_missing(tmp_path):
    # A bogus configured path -> missing, invalid, no crash.
    info = ffmpeg.get_ffmpeg_info(str(tmp_path / 'does-not-exist' / 'ffmpeg'))
    assert 'path' in info
    assert 'version' in info
    assert 'min_required' in info
    assert 'valid' in info
    assert info['source'] in ('missing', 'configured', 'bundled', 'system')


def test_ensure_ffmpeg_on_path_prepends(tmp_path, monkeypatch):
    exe = tmp_path / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
    exe.write_bytes(b'fake')
    monkeypatch.setenv('PATH', '/usr/bin')
    result = ffmpeg.ensure_ffmpeg_on_path(str(exe))
    assert result == str(exe)
    assert os.environ['PATH'].startswith(str(tmp_path))

