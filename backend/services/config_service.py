r"""
Configuration service.

Manages the user's ``config_udb.yaml`` (the same format consumed by the CLI)
plus a small ``gui_settings.json`` for GUI-only preferences such as theme.

On first run the bundled default config is copied to the platform app-data
directory and the download directory is defaulted to the user's Downloads
folder (the bundled example config points at a developer machine path).
"""

import copy
import json
import os
import shutil

import yaml

from backend.app_config import (
    get_app_data_dir,
    get_config_path,
    get_default_config_path,
    get_downloads_default_dir,
)

# Keys that must exist in a valid config
REQUIRED_SECTIONS = ['DownloaderConfig', 'LoggerConfig']

# The two clients actually wired up in udb.py's ACTIVE_CLIENTS
CLIENT_SECTIONS = ['Anime (Animepahe)', 'Anime, Drama, Movies & TV Shows (Kisskh)']

# CLIENTS dict used by the GUI/API to map a friendly key to the config section
CLIENT_KEYS = {
    'animepahe': 'Anime (Animepahe)',
    'kisskh': 'Anime, Drama, Movies & TV Shows (Kisskh)',
}

DEFAULT_GUI_SETTINGS = {
    'theme': 'dark',               # dark | light | system
    'preferred_quality': '1080',
    'notifications': True,
    'check_updates_on_startup': True,
    'start_minimized': False,
    'ffmpeg_configured_path': None,
}


class ConfigError(Exception):
    pass


class ConfigService:
    def __init__(self, config_path: str = None, gui_settings_path: str = None):
        self.config_path = config_path or get_config_path()
        self.gui_settings_path = gui_settings_path or os.path.join(get_app_data_dir(), 'gui_settings.json')
        self._config = None
        self._gui = None
        self.ensure_initialized()

    # ------------------------------------------------------------------ #
    # Initialization                                                     #
    # ------------------------------------------------------------------ #
    def ensure_initialized(self) -> None:
        """Copy the default config into the app-data dir on first run."""
        if not os.path.isfile(self.config_path):
            default_path = get_default_config_path()
            if os.path.isfile(default_path):
                shutil.copyfile(default_path, self.config_path)
                # Default the download dir to the user's Downloads folder
                try:
                    with open(self.config_path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f) or {}
                    dl = data.setdefault('DownloaderConfig', {})
                    dl['download_dir'] = get_downloads_default_dir()
                    # Ensure both active clients have sensible sections
                    for section in CLIENT_SECTIONS:
                        client = data.setdefault(section, {})
                        client.setdefault('download_dir', get_downloads_default_dir())
                        client.setdefault('request_timeout', 30)
                        client.setdefault('alternate_resolution_selector', 'lowest')
                    with open(self.config_path, 'w', encoding='utf-8') as f:
                        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
                except Exception as exc:
                    raise ConfigError(f'Failed to initialize config: {exc}')
            else:
                # No default config available (e.g. unusual bundle); create a minimal one
                self._create_minimal_config()
        self.load()

    def _create_minimal_config(self) -> None:
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        downloads = get_downloads_default_dir()
        data = {
            'Anime (Animepahe)': {
                'download_dir': downloads, 'request_timeout': 30,
                'alternate_resolution_selector': 'lowest',
            },
            'Anime, Drama, Movies & TV Shows (Kisskh)': {
                'download_dir': downloads, 'request_timeout': 30,
                'alternate_resolution_selector': 'lowest',
            },
            'DownloaderConfig': {
                'download_dir': downloads, 'temp_download_dir': 'auto',
                'concurrency_per_file': 'auto', 'request_timeout': 30,
                'max_parallel_downloads': 2,
            },
            'LoggerConfig': {
                'log_level': 'INFO', 'log_dir': 'logs',
                'max_log_size_in_kb': 100, 'log_backup_count': 3,
                'log_retention_days': 7,
            },
        }
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)

    # ------------------------------------------------------------------ #
    # Loading / Saving                                                   #
    # ------------------------------------------------------------------ #
    def load(self) -> dict:
        with open(self.config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        # Ensure required sections exist
        for section in REQUIRED_SECTIONS + CLIENT_SECTIONS:
            data.setdefault(section, {})
        self._config = data
        return data

    def save(self) -> None:
        if self._config is None:
            self.load()
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(self._config, f, sort_keys=False, allow_unicode=True)

    def get_config(self) -> dict:
        if self._config is None:
            self.load()
        return self._config

    # ------------------------------------------------------------------ #
    # GUI settings                                                       #
    # ------------------------------------------------------------------ #
    def load_gui_settings(self) -> dict:
        if os.path.isfile(self.gui_settings_path):
            try:
                with open(self.gui_settings_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return {**DEFAULT_GUI_SETTINGS, **data}
            except (OSError, ValueError):
                pass
        return copy.deepcopy(DEFAULT_GUI_SETTINGS)

    def save_gui_settings(self, settings: dict) -> None:
        merged = {**DEFAULT_GUI_SETTINGS, **settings}
        os.makedirs(os.path.dirname(self.gui_settings_path), exist_ok=True)
        with open(self.gui_settings_path, 'w', encoding='utf-8') as f:
            json.dump(merged, f, indent=2)

    # ------------------------------------------------------------------ #
    # Normalized settings API (used by the GUI)                          #
    # ------------------------------------------------------------------ #
    def get_settings(self) -> dict:
        """Return a flat, normalized settings dict for the GUI."""
        cfg = self.get_config()
        dl = cfg.get('DownloaderConfig', {})
        lg = cfg.get('LoggerConfig', {})
        ap = cfg.get('Anime (Animepahe)', {})
        kk = cfg.get('Anime, Drama, Movies & TV Shows (Kisskh)', {})
        gui = self.load_gui_settings()

        return {
            # Downloader
            'download_dir': dl.get('download_dir', get_downloads_default_dir()),
            'temp_download_dir': dl.get('temp_download_dir', 'auto'),
            'concurrency_per_file': dl.get('concurrency_per_file', 'auto'),
            'request_timeout': dl.get('request_timeout', 30),
            'max_parallel_downloads': dl.get('max_parallel_downloads', 2),
            # Logger
            'log_level': lg.get('log_level', 'INFO'),
            'log_retention_days': lg.get('log_retention_days', 7),
            'log_backup_count': lg.get('log_backup_count', 3),
            'log_max_size_kb': lg.get('max_log_size_in_kb', 100),
            # Client: AnimePahe
            'animepahe_download_dir': ap.get('download_dir'),
            'animepahe_request_timeout': ap.get('request_timeout', 30),
            'animepahe_selector': ap.get('alternate_resolution_selector', 'lowest'),
            # Client: KissKh
            'kisskh_download_dir': kk.get('download_dir'),
            'kisskh_request_timeout': kk.get('request_timeout', 30),
            'kisskh_selector': kk.get('alternate_resolution_selector', 'lowest'),
            'kisskh_search_limit': kk.get('search_limit', 5),
            # GUI-only
            'theme': gui.get('theme', 'dark'),
            'preferred_quality': gui.get('preferred_quality', '1080'),
            'notifications': gui.get('notifications', True),
            'check_updates_on_startup': gui.get('check_updates_on_startup', True),
            'start_minimized': gui.get('start_minimized', False),
            'ffmpeg_configured_path': gui.get('ffmpeg_configured_path'),
        }

    def update_settings(self, patch: dict) -> dict:
        """
        Apply a partial settings patch to the underlying YAML + GUI settings.
        Returns the full normalized settings after update.
        """
        cfg = self.get_config()
        dl = cfg.setdefault('DownloaderConfig', {})
        lg = cfg.setdefault('LoggerConfig', {})
        ap = cfg.setdefault('Anime (Animepahe)', {})
        kk = cfg.setdefault('Anime, Drama, Movies & TV Shows (Kisskh)', {})

        # Downloader mappings
        mapping = {
            'download_dir': (dl, 'download_dir'),
            'temp_download_dir': (dl, 'temp_download_dir'),
            'concurrency_per_file': (dl, 'concurrency_per_file'),
            'request_timeout': (dl, 'request_timeout'),
            'max_parallel_downloads': (dl, 'max_parallel_downloads'),
            'log_level': (lg, 'log_level'),
            'log_retention_days': (lg, 'log_retention_days'),
            'log_backup_count': (lg, 'log_backup_count'),
            'log_max_size_kb': (lg, 'max_log_size_in_kb'),
            'animepahe_download_dir': (ap, 'download_dir'),
            'animepahe_request_timeout': (ap, 'request_timeout'),
            'animepahe_selector': (ap, 'alternate_resolution_selector'),
            'kisskh_download_dir': (kk, 'download_dir'),
            'kisskh_request_timeout': (kk, 'request_timeout'),
            'kisskh_selector': (kk, 'alternate_resolution_selector'),
            'kisskh_search_limit': (kk, 'search_limit'),
        }

        gui_patch = {}
        for key, value in patch.items():
            if key in mapping:
                section, yaml_key = mapping[key]
                section[yaml_key] = value
            elif key in DEFAULT_GUI_SETTINGS:
                gui_patch[key] = value
            # Ignore unknown keys

        self.save()

        # Persist GUI-only settings
        if gui_patch:
            merged = {**self.load_gui_settings(), **gui_patch}
            self.save_gui_settings(merged)

        return self.get_settings()


def get_downloader_config(config_service: ConfigService) -> dict:
    """
    Return the ``DownloaderConfig`` dict (with defaults) used when constructing
    downloader clients.
    """
    cfg = config_service.get_config()
    dl = dict(cfg.get('DownloaderConfig', {}))
    dl.setdefault('download_dir', get_downloads_default_dir())
    dl.setdefault('temp_download_dir', 'auto')
    dl.setdefault('concurrency_per_file', 'auto')
    dl.setdefault('request_timeout', 30)
    dl.setdefault('max_parallel_downloads', 2)
    return dl

