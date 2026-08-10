r"""
Shared pytest fixtures for the UDB backend test-suite.

All tests run against throwaway temp dirs — never the real app-data directory —
and a fake UDB service so no network requests or browsers are ever opened.
"""

import os
import sys

import pytest

# Make the repository root importable regardless of how pytest is invoked.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.services.config_service import ConfigService  # noqa: E402
from backend.services.download_manager import DownloadManager  # noqa: E402
from backend.services.events import EventBus  # noqa: E402
from backend.services.history import HistoryService  # noqa: E402


class FakeUDBService:
    """
    Stand-in for backend.services.udb_service.UDBService with no network or
    browser involvement. Implements exactly the surface DownloadManager and
    the API routes consume.
    """

    def __init__(self, config_service):
        self.config_service = config_service
        self.episodes = [
            {'episode': 1, 'episodeName': 'Episode 1', 'type': 'tv', 'season': 1},
            {'episode': 2, 'episodeName': 'Episode 2', 'type': 'tv', 'season': 1},
            {'episode': 3, 'episodeName': 'Episode 3', 'type': 'tv', 'season': 1},
        ]
        self.target = {'title': 'Test Series', 'year': 2026}
        self.fail_next_prepare = False
        # When True, run_download blocks until the cancel event is set (used to
        # make cancellation tests deterministic).
        self.block_until_cancel = False

    def get_episode_session(self, ep_session):
        return {
            'client': 'kisskh',
            'target': self.target,
            'episodes': self.episodes,
        }

    def prepare_downloads(self, ep_session, resolution, selection, download_dir):
        if self.fail_next_prepare:
            raise RuntimeError('simulated preparation failure')
        from backend.services.download_manager import _filter_episodes
        selected = _filter_episodes(self.episodes, selection)
        out = []
        for ep in selected:
            out.append({
                'episode': ep['episode'],
                'episodeName': ep['episodeName'],
                'downloadLink': f'https://example.test/ep{ep["episode"]}.mp4',
                'downloadType': 'mp4',
                'series_title': self.target['title'],
                'type': 'tv',
                'season': ep.get('season', 1),
            })
        return out

    def get_downloader_config(self, client_key):
        cfg = {'download_dir': os.path.expanduser('~'), 'request_timeout': 30}
        if client_key == 'kisskh':
            cfg['use_http_client'] = True
        return cfg

    def run_download(self, ep_details, dl_config):
        # Mirrors real run_download(): DownloadCancelled is handled internally
        # and surfaces as a cancelled=True result dict, never as an exception.
        from backend.services.progress import DownloadCancelled
        cancel = dl_config.get('cancel_event')
        cancelled = False
        if self.block_until_cancel:
            import time
            deadline = time.time() + 10
            while time.time() < deadline:
                if cancel is not None and cancel.is_set():
                    cancelled = True
                    break
                time.sleep(0.01)
            if not cancelled:
                raise RuntimeError('fake download timed out without cancel')
        elif cancel is not None and cancel.is_set():
            cancelled = True

        if cancelled:
            return {
                'status': 1,
                'message': 'Download cancelled by user',
                'out_file': ep_details['episodeName'],
                'out_dir': dl_config.get('download_dir', ''),
                'skipped': False,
                'cancelled': True,
            }
        return {
            'status': 0,
            'message': 'Completed in 1s',
            'out_file': ep_details['episodeName'],
            'out_dir': dl_config.get('download_dir', ''),
            'skipped': False,
            'cancelled': False,
        }


@pytest.fixture
def config_service(tmp_path):
    """ConfigService backed by temp config + GUI settings files."""
    return ConfigService(
        config_path=str(tmp_path / 'config_udb.yaml'),
        gui_settings_path=str(tmp_path / 'gui_settings.json'),
    )


@pytest.fixture
def history_service(tmp_path):
    """HistoryService backed by a temp SQLite database."""
    return HistoryService(db_path=str(tmp_path / 'history.db'))


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def udb_service(config_service):
    return FakeUDBService(config_service)


@pytest.fixture
def manager(event_bus, history_service, udb_service):
    return DownloadManager(event_bus, history_service, udb_service)


@pytest.fixture
def app(tmp_path, config_service, history_service, event_bus, udb_service, manager):
    """Fully-wired Flask app with fake services; no real app-data touched."""
    from backend import app as app_module
    import backend.services.ffmpeg_service as ffmpeg_service
    logs_dir = tmp_path / 'logs'
    logs_dir.mkdir(exist_ok=True)
    services = {
        'config': config_service,
        'history': history_service,
        'event_bus': event_bus,
        'udb': udb_service,
        'manager': manager,
        'logs_dir': str(logs_dir),
        'ffmpeg': ffmpeg_service,
    }
    flask_app = app_module.create_app(services=services)
    flask_app.config['TESTING'] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()

