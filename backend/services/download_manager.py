r"""
Download queue / job manager.

Owns the lifecycle of every download in the GUI:

    queued -> preparing -> downloading -> completed | failed | cancelled

The underlying UDB downloader does not support true pause/resume, so this
manager intentionally exposes Cancel, Retry, Remove and Open-folder operations
only. Cancel is reliable (the download loop checks a per-job event between
segments/chunks); Retry reuses already-downloaded segments/chunks.

Progress events are emitted through the EventBus; job state changes are
persisted to the HistoryService.
"""

import os
import threading
import time
import traceback
import uuid
from datetime import datetime

from backend.services.progress import format_speed
from backend.services.udb_service import UDBServiceError

STATUS_QUEUED = 'queued'
STATUS_PREPARING = 'preparing'
STATUS_DOWNLOADING = 'downloading'
STATUS_COMPLETED = 'completed'
STATUS_FAILED = 'failed'
STATUS_CANCELLED = 'cancelled'
STATUS_RETRYING = 'retrying'

ALL_STATUSES = [STATUS_QUEUED, STATUS_PREPARING, STATUS_DOWNLOADING,
                STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED, STATUS_RETRYING]


class DownloadManager:
    def __init__(self, event_bus, history, udb_service):
        self.event_bus = event_bus
        self.history = history
        self.udb_service = udb_service
        self.jobs = {}                # job_id -> job dict
        self.batches = {}             # batch_id -> batch dict
        self._semaphore = None
        self._lock = threading.RLock()
        self._update_max_parallel()
        self._job_events = {}         # job_id -> threading.Event (cancel)

    # ------------------------------------------------------------------ #
    # Concurrency                                                        #
    # ------------------------------------------------------------------ #
    def _update_max_parallel(self) -> None:
        try:
            cfg = self.udb_service.config_service.get_settings()
            max_parallel = int(cfg.get('max_parallel_downloads', 2))
        except Exception:
            max_parallel = 2
        max_parallel = max(1, min(max_parallel, 10))
        self._semaphore = threading.BoundedSemaphore(max_parallel)

    # ------------------------------------------------------------------ #
    # Job creation                                                       #
    # ------------------------------------------------------------------ #
    def _new_job(self, batch_id, title, ep, season, quality, client_key,
                 download_dir, episode_name) -> dict:
        job_id = f'dl-{uuid.uuid4().hex[:12]}'
        job = {
            'id': job_id,
            'batch_id': batch_id,
            'title': title,
            'episode': ep,
            'season': season,
            'quality': quality,
            'client': client_key,
            'status': STATUS_QUEUED,
            'progress': 0.0,
            'speed': 0.0,
            'speed_str': '',
            'completed': 0,
            'total': 0,
            'unit': '',
            'destination': download_dir,
            'error': '',
            'episodeName': episode_name,
            'ep_details': None,
            'created': datetime.now().isoformat(timespec='seconds'),
            'started': None,
            'finished': None,
        }
        return job

    def create_batch(self, ep_session: str, resolution, selection,
                     download_dir: str) -> list:
        """
        Create a queued job for every episode in the selection and start a
        background preparation thread that resolves per-episode links.

        Returns the list of created job dicts (without ep_details).
        """
        self._update_max_parallel()
        cache = self.udb_service.get_episode_session(ep_session)
        client_key = cache['client']
        episodes = cache['episodes']
        title = cache['target'].get('title', 'Unknown')

        selected_eps = _filter_episodes(episodes, selection)
        if not selected_eps:
            raise UDBServiceError('No episodes matched the requested selection.')

        batch_id = f'batch-{uuid.uuid4().hex[:10]}'
        jobs = []
        for ep in selected_eps:
            ep_no = ep.get('episode')
            season = ep.get('season')
            if season is None and cache['target'].get('series_type'):
                # KissKh movies/parts carry no explicit season
                season = None
            job = self._new_job(
                batch_id=batch_id,
                title=title,
                episode=ep_no,
                season=season,
                quality=str(resolution),
                client_key=client_key,
                download_dir=download_dir,
                episode_name=ep.get('episodeName') or f'Episode {ep_no}',
            )
            self.jobs[job['id']] = job
            self._job_events[job['id']] = threading.Event()
            jobs.append(job)

        batch = {
            'id': batch_id,
            'ep_session': ep_session,
            'client': client_key,
            'resolution': str(resolution),
            'selection': selection,
            'download_dir': download_dir,
            'jobs': jobs,
            'status': STATUS_PREPARING,
        }
        self.batches[batch_id] = batch

        thread = threading.Thread(target=self._prepare_batch, args=(batch,),
                                  name=f'udb-prep-{batch_id}', daemon=True)
        thread.start()

        return [self.get(job['id']) for job in jobs]

    # ------------------------------------------------------------------ #
    # Background preparation                                             #
    # ------------------------------------------------------------------ #
    def _prepare_batch(self, batch: dict) -> None:
        try:
            ep_details_list = self.udb_service.prepare_downloads(
                batch['ep_session'],
                batch['resolution'],
                batch['selection'],
                batch['download_dir'],
            )
        except Exception as exc:
            logger.error('Batch preparation failed: %s', traceback.format_exc())
            for job in batch['jobs']:
                self._fail_job(job, f'Preparation failed: {exc}')
            return

        by_ep = {}
        for details in ep_details_list:
            try:
                by_ep[float(details.get('episode'))] = details
            except (TypeError, ValueError):
                continue

        for job in batch['jobs']:
            try:
                ep_no = float(job['episode'])
            except (TypeError, ValueError):
                self._fail_job(job, 'Invalid episode number')
                continue
            details = by_ep.get(ep_no)
            if details is None:
                self._fail_job(job, 'Episode link could not be resolved')
                continue
            if details.get('failed'):
                self._fail_job(job, details.get('error', 'Episode link could not be resolved'))
                continue
            with self._lock:
                job['ep_details'] = details
                job['episodeName'] = details.get('episodeName', job['episodeName'])
                if details.get('season') is not None:
                    job['season'] = details.get('season')
            self._start_download(job)

    # ------------------------------------------------------------------ #
    # Download execution                                                 #
    # ------------------------------------------------------------------ #
    def _start_download(self, job: dict) -> None:
        if not self._semaphore.acquire(blocking=False):
            # max concurrency reached -> stay queued, wait for a slot
            self._set_status(job, STATUS_QUEUED)
            thread = threading.Thread(target=self._run_when_slot_free, args=(job,),
                                      name=f'udb-q-{job["id"]}', daemon=True)
            thread.start()
            return
        thread = threading.Thread(target=self._run_job, args=(job,),
                                  name=f'udb-dl-{job["id"]}', daemon=True)
        thread.start()

    def _run_when_slot_free(self, job: dict) -> None:
        self._semaphore.acquire()
        self._run_job(job)

    def _run_job(self, job: dict) -> None:
        self._set_status(job, STATUS_DOWNLOADING)
        job['started'] = datetime.now().isoformat(timespec='seconds')
        cancel_event = self._job_events.get(job['id'])

        dl_config = self.udb_service.get_downloader_config(job['client'])
        dl_config['download_dir'] = job['destination']
        dl_config['progress_callback'] = self._make_progress_callback(job)
        dl_config['cancel_event'] = cancel_event

        try:
            result = self.udb_service.run_download(job['ep_details'], dl_config)
        except Exception as exc:
            self._fail_job(job, f'Unexpected error: {exc}')
            self._semaphore.release()
            return

        try:
            self._semaphore.release()
        except ValueError:
            pass

        job['finished'] = datetime.now().isoformat(timespec='seconds')
        if result.get('cancelled'):
            self._set_status(job, STATUS_CANCELLED)
            self._record_history(job, STATUS_CANCELLED, error='Cancelled by user')
        elif result.get('status') == 0:
            self._set_status(job, STATUS_COMPLETED, progress=100.0)
            self._record_history(job, STATUS_COMPLETED, message=result.get('message', ''))
        else:
            self._fail_job(job, result.get('message', 'Download failed'))

    def _make_progress_callback(self, job: dict):
        def callback(payload):
            with self._lock:
                job['progress'] = payload.get('progress', 0)
                job['completed'] = payload.get('completed', 0)
                job['total'] = payload.get('total', 0)
                job['unit'] = payload.get('unit', '')
                job['speed'] = payload.get('speed', 0)
                job['speed_str'] = format_speed(payload.get('speed', 0), payload.get('unit', 'iB'))
            self.event_bus.publish({
                'type': 'download_progress',
                'download_id': job['id'],
                'progress': job['progress'],
                'speed': job['speed_str'],
                'downloaded': job['completed'],
                'total': job['total'],
                'unit': job['unit'],
            })
        return callback

    # ------------------------------------------------------------------ #
    # Job control                                                        #
    # ------------------------------------------------------------------ #
    def cancel(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if not job:
            return False
        with self._lock:
            if job['status'] in (STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED):
                return False
            event = self._job_events.get(job_id)
            if event:
                event.set()
        return True

    def retry(self, job_id: str) -> bool:
        """
        Re-run a failed/cancelled job whose ep_details are still cached. Returns
        True when a retry was scheduled.
        """
        job = self.jobs.get(job_id)
        if not job:
            return False
        with self._lock:
            if job['status'] not in (STATUS_FAILED, STATUS_CANCELLED):
                return False
            if not job.get('ep_details'):
                return False
            job['progress'] = 0.0
            job['speed'] = 0.0
            job['speed_str'] = ''
            job['completed'] = 0
            job['total'] = 0
            job['error'] = ''
            job['finished'] = None
            event = self._job_events.setdefault(job_id, threading.Event())
            event.clear()
        self._set_status(job, STATUS_RETRYING)
        self._start_download(job)
        return True

    def remove(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if not job:
            return False
        self.cancel(job_id)
        with self._lock:
            self.jobs.pop(job_id, None)
            self._job_events.pop(job_id, None)
        return True

    def add_retry_job(self, record: dict, ep_details: dict) -> dict:
        """
        Re-create a download job from a history record (retry from History page).
        The stored ep_details must contain downloadLink etc.
        """
        if not ep_details.get('downloadLink'):
            raise UDBServiceError('This download cannot be retried automatically. Please re-add it.')
        job_id = f'dl-{uuid.uuid4().hex[:12]}'
        job = {
            'id': job_id,
            'batch_id': f'retry-{uuid.uuid4().hex[:8]}',
            'title': record.get('title', ''),
            'episode': record.get('episode'),
            'season': record.get('season'),
            'quality': record.get('quality', ''),
            'client': record.get('client', ''),
            'status': STATUS_QUEUED,
            'progress': 0.0,
            'speed': 0.0,
            'speed_str': '',
            'completed': 0,
            'total': 0,
            'unit': '',
            'destination': os.path.dirname(record.get('destination') or ''),
            'error': '',
            'episodeName': ep_details.get('episodeName', ''),
            'ep_details': ep_details,
            'created': datetime.now().isoformat(timespec='seconds'),
            'started': None,
            'finished': None,
        }
        with self._lock:
            self.jobs[job_id] = job
            self._job_events[job_id] = threading.Event()
        self._start_download(job)
        return self._public_job(job)

    def open_folder(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if not job:
            return False
        folder = job.get('destination', '')
        if folder and os.path.isdir(folder):
            _open_folder(folder)
            return True
        return False

    # ------------------------------------------------------------------ #
    # Querying                                                           #
    # ------------------------------------------------------------------ #
    def list(self, status: str = None, limit: int = 200) -> list:
        with self._lock:
            items = list(self.jobs.values())
        if status:
            items = [j for j in items if j['status'] == status]
        items.sort(key=lambda j: j.get('created', ''), reverse=True)
        return [self._public_job(j) for j in items[:limit]]

    def get(self, job_id: str):
        job = self.jobs.get(job_id)
        return self._public_job(job) if job else None

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for j in self.jobs.values() if j['status'] in (STATUS_QUEUED, STATUS_PREPARING, STATUS_DOWNLOADING))

    def summary(self) -> dict:
        with self._lock:
            counts = {status: 0 for status in ALL_STATUSES}
            for job in self.jobs.values():
                counts[job['status']] = counts.get(job['status'], 0) + 1
        return {
            'active': counts[STATUS_QUEUED] + counts[STATUS_PREPARING] + counts[STATUS_DOWNLOADING],
            'queued': counts[STATUS_QUEUED],
            'downloading': counts[STATUS_DOWNLOADING],
            'completed': counts[STATUS_COMPLETED],
            'failed': counts[STATUS_FAILED],
            'cancelled': counts[STATUS_CANCELLED],
        }

    def _public_job(self, job: dict) -> dict:
        out = {k: v for k, v in job.items() if k != 'ep_details'}
        # Resolve full destination path
        if out.get('episodeName'):
            out['output_path'] = os.path.join(out.get('destination', ''), out['episodeName'])
        return out

    # ------------------------------------------------------------------ #
    # Internals                                                          #
    # ------------------------------------------------------------------ #
    def _set_status(self, job, status, progress=None):
        with self._lock:
            job['status'] = status
            if progress is not None:
                job['progress'] = progress
        self.event_bus.publish({
            'type': 'download_status',
            'download_id': job['id'],
            'status': status,
            'progress': job.get('progress', 0),
        })

    def _fail_job(self, job, error: str) -> None:
        with self._lock:
            job['error'] = error
            job['finished'] = datetime.now().isoformat(timespec='seconds')
        self._set_status(job, STATUS_FAILED)
        self._record_history(job, STATUS_FAILED, error=error)

    def _record_history(self, job, status, error='', message='') -> None:
        size = ''
        output_path = job.get('episodeName')
        if status == STATUS_COMPLETED and output_path:
            full = os.path.join(job['destination'], output_path)
            try:
                if os.path.isfile(full):
                    size = f'{os.path.getsize(full) / (1024 * 1024):.1f} MB'
            except OSError:
                size = ''
        record = {
            'id': job['id'],
            'title': job['title'],
            'episode': job['episode'],
            'season': job.get('season'),
            'quality': job['quality'],
            'source': job['client'],
            'status': status,
            'destination': os.path.join(job['destination'], job.get('episodeName') or ''),
            'file_size': size,
            'date': job.get('finished') or datetime.now().isoformat(timespec='seconds'),
            'error': error,
            'client': job['client'],
            'extra': {'ep_details': _prune_ep_details(job.get('ep_details'))},
        }
        try:
            self.history.add(record)
        except Exception as exc:
            logger.error('Failed to write history: %s', exc)


def _filter_episodes(episodes, selection):
    """Filter an episode list by a simple range or season-range selection."""
    if isinstance(selection, dict) and any(k in selection for k in ('start', 'end', 'specific_no')):
        start = float(selection.get('start', 1))
        end = float(selection.get('end', start))
        specific = [float(x) for x in selection.get('specific_no', [])]
        result = []
        for ep in episodes:
            try:
                ep_no = float(ep['episode'])
            except (TypeError, ValueError, KeyError):
                continue
            if (start <= ep_no <= end) or ep_no in specific:
                result.append(ep)
        return result
    # Season-based selection (TV shows when the client reports seasons)
    result = []
    for ep in episodes:
        season = ep.get('season')
        value = selection.get(str(season)) if season is not None else None
        if value is None:
            continue
        if isinstance(value, dict):
            start = float(value.get('start', 1))
            end = float(value.get('end', start))
            specific = [float(x) for x in value.get('specific_no', [])]
            try:
                ep_no = float(ep['episode'])
            except (TypeError, ValueError, KeyError):
                continue
            if (start <= ep_no <= end) or ep_no in specific:
                result.append(ep)
        else:
            try:
                if float(ep['episode']) == float(value):
                    result.append(ep)
            except (TypeError, ValueError, KeyError):
                continue
    return result


def _prune_ep_details(details):
    """Keep only the fields needed to re-run a download (for history retry)."""
    if not details:
        return None
    keys = ['episode', 'episodeName', 'downloadLink', 'downloadType',
            'refererLink', 'audio', 'subtitles', 'encrypted_subs_details',
            'season', 'type']
    return {k: details.get(k) for k in keys if details.get(k) is not None}


def _open_folder(folder: str) -> None:
    import platform
    import subprocess
    try:
        system = platform.system()
        if system == 'Windows':
            os.startfile(folder)  # noqa
        elif system == 'Darwin':
            subprocess.Popen(['open', folder])
        else:
            subprocess.Popen(['xdg-open', folder])
    except Exception:
        pass


import logging
logger = logging.getLogger('udb.manager')

