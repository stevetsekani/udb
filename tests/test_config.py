"""Tests for the configuration service (YAML + GUI settings)."""

import os

from backend.app_config import get_downloads_default_dir
from backend.services.config_service import (
    DEFAULT_GUI_SETTINGS,
    ConfigService,
    get_downloader_config,
)


def test_first_run_creates_config(config_service):
    assert os.path.isfile(config_service.config_path)
    cfg = config_service.get_config()
    assert 'DownloaderConfig' in cfg
    assert 'LoggerConfig' in cfg
    assert 'Anime (Animepahe)' in cfg
    assert 'Anime, Drama, Movies & TV Shows (Kisskh)' in cfg


def test_default_download_dir_points_at_downloads(config_service):
    cfg = config_service.get_config()
    assert cfg['DownloaderConfig']['download_dir'] == get_downloads_default_dir()


def test_get_settings_has_all_gui_keys(config_service):
    settings = config_service.get_settings()
    for key in ('theme', 'preferred_quality', 'notifications',
                'download_dir', 'max_parallel_downloads', 'log_level'):
        assert key in settings
    assert settings['theme'] == 'dark'


def test_update_settings_maps_to_yaml(config_service):
    updated = config_service.update_settings({
        'max_parallel_downloads': 5,
        'download_dir': r'C:\Media',
        'theme': 'light',
    })
    assert updated['max_parallel_downloads'] == 5
    assert updated['download_dir'] == r'C:\Media'
    assert updated['theme'] == 'light'
    # Verify it persisted to the underlying YAML
    cfg = config_service.get_config()
    assert cfg['DownloaderConfig']['max_parallel_downloads'] == 5


def test_gui_settings_round_trip(config_service):
    config_service.save_gui_settings({'theme': 'light', 'notifications': False})
    loaded = config_service.load_gui_settings()
    assert loaded['theme'] == 'light'
    assert loaded['notifications'] is False
    # Unknown key should not crash persistence
    config_service.save_gui_settings({'theme': 'system', 'made_up_key': 1})
    loaded = config_service.load_gui_settings()
    assert loaded['theme'] == 'system'


def test_get_downloader_config_defaults(config_service):
    dl = get_downloader_config(config_service)
    assert dl['max_parallel_downloads'] >= 1
    assert 'download_dir' in dl
    assert 'request_timeout' in dl


def test_update_settings_reloads(config_service):
    config_service.update_settings({'log_level': 'DEBUG'})
    reloaded = ConfigService(
        config_path=config_service.config_path,
        gui_settings_path=config_service.gui_settings_path,
    )
    assert reloaded.get_settings()['log_level'] == 'DEBUG'

