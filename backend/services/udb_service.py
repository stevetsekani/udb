r"""
UDB service layer.

This module is the bridge between the existing UDB downloader core (clients +
downloaders) and the local API / GUI. It is *not* a rewrite of the downloader —
it wraps the existing clients and the same ``downloader()`` flow used by the
CLI (``udb.py``) so both interfaces share identical logic.

Responsible for:

* creating and caching client instances (AnimePahe / KissKh)
* running searches and fetching episode lists
* preparing download jobs (resolving per-episode m3u8/direct links)
* executing single-episode downloads with optional progress/cancel hooks
"""

import logging
import os
import time
from datetime import datetime

from Utils.commons import PRINT_THEMES

from backend.services.config_service import CLIENT_KEYS, get_downloader_config
from backend.services.progress import DownloadCancelled

logger = logging.getLogger('udb.service')

VALID_CLIENTS = {
    'animepahe': 'Anime (Animepahe)',
    'kisskh': 'Anime, Drama, Movies & TV Shows (Kisskh)',
}

# Map GUI-facing client key to a human label
CLIENT_LABELS = {
    'animepahe': 'Anime (AnimePahe)',
    'kisskh': 'Anime · Drama · Movies · TV (KissKh)',
}

HLS_SIZE_ACCURACY = 0   # GUI does not perform slow size estimation by default


class UDBServiceError(Exception):
    pass


class UDBService:
    def __init__(self, config_service):
        self.config_service = config_service
        self._clients = {}          # client_key -> client instance
        self._search_cache = {}     # session_id -> {'client': key, 'results': {idx: raw}}
        self._episode_cache = {}    # session_id -> {'client': key, 'episodes': [...]}
        self._session_counter = 0

    # ------------------------------------------------------------------ #
    # Client management                                                  #
    # ------------------------------------------------------------------ #
    def _get_client(self, client_key: str):
        """Return a cached client instance for the given key."""
        if client_key not in VALID_CLIENTS:
            raise UDBServiceError(f'Unknown client: {client_key}')
        if client_key not in self._clients:
            self._clients[client_key] = self._create_client(client_key)
        return self._clients[client_key]

    def _create_client(self, client_key: str):
        section = VALID_CLIENTS[client_key]
        config = self.config_service.get_config()
        client_config = dict(config.get(section, {}))
        client_config.update({'hls_size_accuracy': HLS_SIZE_ACCURACY})

        if client_key == 'animepahe':
            from Clients.AnimePaheClient import AnimePaheClient
            client = AnimePaheClient(client_config)
        elif client_key == 'kisskh':
            from Clients.KissKhClient import KissKhClient
            client = KissKhClient(client_config)
        else:
            raise UDBServiceError(f'Unknown client: {client_key}')

        logger.debug('Created client %s', client_key)
        return client

    def cleanup(self) -> None:
        """Clean up all cached clients (close browsers etc.)."""
        for key, client in self._clients.items():
            try:
                client.cleanup()
            except Exception as exc:
                logger.warning('Error cleaning up client %s: %s', key, exc)
        self._clients.clear()
        self._search_cache.clear()
        self._episode_cache.clear()

    # ------------------------------------------------------------------ #
    # Search & inspect                                                   #
    # ------------------------------------------------------------------ #
    def search(self, client_key: str, query: str) -> dict:
        """
        Run a search and return a normalized, JSON-friendly result:
        {
          'session_id': ...,
          'client': client_key,
          'query': ...,
          'results': [ {id, title, year, type, episodes, status, detail} ]
        }
        The raw result dicts are cached server-side for later inspect/download.
        """
        if not query or not query.strip():
            raise UDBServiceError('Search query must not be empty')
        client = self._get_client(client_key)
        raw_results = client.search(query.strip())
        if not raw_results:
            return {'session_id': None, 'client': client_key, 'query': query,
                    'results': []}

        self._session_counter += 1
        session_id = f'search-{self._session_counter}'
        self._search_cache[session_id] = {
            'client': client_key,
            'results': dict(raw_results),
        }

        normalized = []
        for idx, raw in raw_results.items():
            item = self._normalize_search_result(idx, raw)
            item['id'] = f'{session_id}:{idx}'
            normalized.append(item)

        return {
            'session_id': session_id,
            'client': client_key,
            'query': query,
            'results': normalized,
        }

    def _normalize_search_result(self, idx, raw: dict) -> dict:
        title = raw.get('title', 'Unknown')
        year = raw.get('year')
        return {
            'index': idx,
            'title': title,
            'year': str(year) if year else None,
            'type': raw.get('type') or raw.get('series_type') or '',
            'episodes': raw.get('episodes') or raw.get('episodesCount'),
            'status': raw.get('status') or '',
            'detail': raw.get('country') or '',
        }

    def get_search_result(self, result_id: str):
        """
        Look up a cached raw search result from an id like 'search-1:3'.
        """
        if ':' not in result_id:
            raise UDBServiceError('Invalid search result id')
        session_id, idx = result_id.rsplit(':', 1)
        cache = self._search_cache.get(session_id)
        if not cache:
            raise UDBServiceError('Search session expired. Please search again.')
        try:
            idx = int(idx)
        except ValueError:
            raise UDBServiceError('Invalid search result id')
        if idx not in cache['results']:
            raise UDBServiceError('Search result not found. Please search again.')
        return cache['client'], cache['results'][idx]

    def inspect(self, client_key: str, result_id: str) -> dict:
        """
        Fetch the episode list for a search result. Returns normalized episodes
        plus season ranges when the client provides them.
        """
        client = self._get_client(client_key)
        _, target = self.get_search_result(result_id)
        episodes = client.fetch_episodes_list(target)
        if not episodes:
            raise UDBServiceError('No episodes found for the selected title.')

        self._session_counter += 1
        ep_session = f'ep-{self._session_counter}'
        self._episode_cache[ep_session] = {
            'client': client_key,
            'target': target,
            'episodes': episodes,
        }

        normalized = []
        for ep in episodes:
            normalized.append({
                'episode': ep.get('episode'),
                'name': ep.get('episodeName') or f'Episode {ep.get("episode")}',
                'extra': _summarize_episode(ep),
            })

        season_ranges = {}
        if hasattr(client, 'get_season_ep_ranges'):
            try:
                season_ranges = client.get_season_ep_ranges(episodes)
            except Exception as exc:
                logger.warning('get_season_ep_ranges failed: %s', exc)

        is_tv = episodes[0].get('type', '') == 'tv'

        return {
            'episode_session': ep_session,
            'client': client_key,
            'title': target.get('title', 'Unknown'),
            'year': target.get('year'),
            'episodes': normalized,
            'total_episodes': len(normalized),
            'season_ranges': season_ranges,
            'is_tv': is_tv,
        }

    def get_episode_session(self, ep_session: str):
        cache = self._episode_cache.get(ep_session)
        if not cache:
            raise UDBServiceError('Episode session expired. Please search again.')
        return cache

    # ------------------------------------------------------------------ #
    # Download preparation                                               #
    # ------------------------------------------------------------------ #
    def prepare_downloads(self, ep_session: str, resolution, selection,
                          download_dir: str) -> list:
        """
        Resolve per-episode download links for the requested selection and
        return a list of ep_details dicts (one per episode) ready to download.

        ``selection`` is either:
          {'start':..,'end':..,'specific_no':[..]}   (simple range)
        or for TV:
          {season: {'start':..,'end':..,'specific_no':[..]}}
        """
        cache = self.get_episode_session(ep_session)
        client = self._get_client(cache['client'])
        episodes = cache['episodes']
        target = cache['target']

        # Reset any accumulated state so we only prepare the requested selection
        client.udb_episode_dict = {}

        is_tv = episodes[0].get('type', '') == 'tv'
        if is_tv and isinstance(selection, dict) and not _is_simple_range(selection):
            selected_eps = selection
        else:
            if not selection:
                raise UDBServiceError('No episode selection provided')
            # A single range applies to every season (original behavior)
            if is_tv and hasattr(client, 'get_season_ep_ranges'):
                ranges = client.get_season_ep_ranges(episodes)
                selected_eps = {
                    season: selection for season in ranges
                }
            else:
                selected_eps = selection

        # Mirror udb.py's episode range parsing
        ep_ranges = _normalize_range(selected_eps)

        logger.info('Fetching episode links for selection %s', ep_ranges)
        target_ep_links = client.fetch_episode_links(episodes, ep_ranges)
        if not target_ep_links:
            raise UDBServiceError('No episodes are available for download.')

        series_title, episode_prefix = client.set_out_names(target)
        logger.info('Fetching m3u8/direct links for resolution %s', resolution)
        target_dl_links = client.fetch_m3u8_links(target_ep_links, str(resolution), episode_prefix)

        # Filter to the episodes we actually selected (the client may hold stale
        # entries from earlier operations).
        valid_keys = set(target_ep_links.keys())
        selected_dl = {k: v for k, v in target_dl_links.items() if k in valid_keys}

        ep_details_list = []
        for ep, details in selected_dl.items():
            if 'downloadLink' not in details:
                ep_details_list.append({
                    'episode': ep,
                    'episodeName': details.get('episodeName', f'Episode {ep}'),
                    'error': details.get('error', 'No download link available'),
                    'failed': True,
                })
                continue
            details = dict(details)
            details['episode'] = ep
            details['series_title'] = series_title
            # tag as tv when the episode carries season info
            if is_tv:
                details.setdefault('type', 'tv')
                season = details.get('season') or _season_from_episode(ep)
                if season is not None:
                    details['season'] = season
            ep_details_list.append(details)

        return ep_details_list

    # ------------------------------------------------------------------ #
    # Download execution                                                 #
    # ------------------------------------------------------------------ #
    def run_download(self, ep_details: dict, dl_config: dict):
        """
        Download a single episode. Mirrors ``udb.py``'s ``downloader()``.

        Returns a dict:
          {status: 0|1, message, out_file, out_dir, skipped: bool, cancelled: bool}
        """
        out_file = ep_details['episodeName']
        start_epoch = int(time.time())

        if 'downloadLink' not in ep_details:
            return {
                'status': 1,
                'message': ep_details.get('error', 'Unknown'),
                'out_file': out_file,
                'out_dir': dl_config.get('download_dir', ''),
                'skipped': True,
                'cancelled': False,
            }

        download_type = ep_details['downloadType']
        out_dir = dl_config['download_dir']
        if ep_details.get('type', '') == 'tv':
            out_dir = os.path.join(out_dir, f"Season-{ep_details.get('season')}")

        logger.info('Creating download client for %s (%s)', out_file, download_type)
        if download_type == 'hls':
            from Utils.HLSDownloader import HLSDownloader
            dl_client = HLSDownloader(dl_config, ep_details)
        elif download_type == 'mp4':
            from Utils.BaseDownloader import BaseDownloader
            dl_client = BaseDownloader(dl_config, ep_details)
        else:
            return {
                'status': 1,
                'message': f'Unknown download type [{download_type}]',
                'out_file': out_file,
                'out_dir': out_dir,
                'skipped': True,
                'cancelled': False,
            }

        logger.info('Download started for %s...', out_file)
        full_path = os.path.join(out_dir, out_file)
        if os.path.isfile(full_path) and os.path.getsize(full_path) > 0:
            logger.info('Download skipped for %s. File already exists!', out_file)
            return {
                'status': 0,
                'message': 'File already exists',
                'out_file': out_file,
                'out_dir': out_dir,
                'skipped': True,
                'cancelled': False,
            }

        cancelled = False
        try:
            status, msg = dl_client.start_download(ep_details['downloadLink'])
        except DownloadCancelled:
            status, msg, cancelled = 1, 'Download cancelled by user', True
        except Exception as exc:
            status, msg = 1, str(exc)

        try:
            dl_client._cleanup_out_dirs()
        except Exception:
            pass

        elapsed = int(time.time() - start_epoch)
        return {
            'status': status,
            'message': msg if status != 0 else f'Completed in {elapsed}s',
            'out_file': out_file,
            'out_dir': out_dir,
            'skipped': False,
            'cancelled': cancelled,
        }

    def get_downloader_config(self, client_key: str) -> dict:
        """Build the dl_config for a specific client + global settings."""
        cfg = get_downloader_config(self.config_service)
        if client_key == 'kisskh':
            cfg['use_http_client'] = True
        # Resolve a per-client download_dir override
        section = VALID_CLIENTS.get(client_key)
        if section:
            client_cfg = self.config_service.get_config().get(section, {})
            if client_cfg.get('download_dir'):
                cfg['download_dir'] = client_cfg['download_dir']
        return cfg


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _is_simple_range(selection: dict) -> bool:
    return any(k in selection for k in ('start', 'end', 'specific_no'))


def _normalize_range(selection):
    """
    Accept either a simple range dict or a dict of season -> range dict and
    return a range dict in the shape udb.py expects: {start, end, specific_no}.
    """
    if _is_simple_range(selection):
        start = float(selection.get('start', 1))
        end = float(selection.get('end', start))
        specific = [float(x) for x in selection.get('specific_no', [])]
        return {'start': start, 'end': end, 'specific_no': specific}
    # Multiple seasons: build a combined range for clients that don't natively
    # support seasons (current clients). Each value may itself be a range dict.
    starts, ends, specific = [], [], []
    for season, value in selection.items():
        if _is_simple_range(value):
            starts.append(float(value.get('start', 1)))
            ends.append(float(value.get('end', 1)))
            specific.extend(float(x) for x in value.get('specific_no', []))
        else:
            starts.append(float(value))
            ends.append(float(value))
    return {
        'start': min(starts) if starts else 1,
        'end': max(ends) if ends else 1,
        'specific_no': specific,
    }


def _season_from_episode(ep) -> int:
    """Best-effort season extraction from an episode key like 's1e5'."""
    try:
        key = str(ep).lower()
        if key.startswith('s') and 'e' in key:
            return int(key.split('e')[0].replace('s', ''))
    except (ValueError, IndexError):
        pass
    return None


def _summarize_episode(ep: dict) -> str:
    parts = []
    for key in ('audio', 'duration', 'created_at'):
        if ep.get(key):
            parts.append(str(ep[key]))
    return ' | '.join(parts)

