r"""
API route definitions for the UDB backend.

All routes are JSON in/out except the SSE event stream. Errors are returned as
``{ 'error': { 'message': ..., 'details': ... } }`` with appropriate status
codes so the GUI can render friendly messages instead of tracebacks.
"""

import json
import os
import platform
import sys
import time

from flask import Blueprint, Response, jsonify, request, stream_with_context

from backend import version as version_module
from backend.services.download_manager import STATUS_CANCELLED, STATUS_FAILED

api = Blueprint('api', __name__)


class ApiError(Exception):
    def __init__(self, message, status_code=400, details=''):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


# --------------------------------------------------------------------------- #
# Health / meta                                                               #
# --------------------------------------------------------------------------- #
@api.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'time': int(time.time())})


@api.route('/api/version', methods=['GET'])
def version():
    return jsonify({
        'version': version_module.__version__,
        'app': 'UDB',
    })


@api.route('/api/system', methods=['GET'])
def system():
    return jsonify({
        'os': platform.system(),
        'os_release': platform.release(),
        'arch': platform.machine(),
        'python': sys.version.split()[0],
        'frozen': getattr(sys, 'frozen', False),
        'hostname': platform.node(),
    })


@api.route('/api/ffmpeg', methods=['GET'])
def ffmpeg():
    info = get_services()['ffmpeg'].get_ffmpeg_info(
        get_services()['config'].load_gui_settings().get('ffmpeg_configured_path'))
    return jsonify(info)


# --------------------------------------------------------------------------- #
# Search / inspect                                                            #
# --------------------------------------------------------------------------- #
@api.route('/api/search', methods=['POST'])
def search():
    body = request.get_json(silent=True) or {}
    client_key = _validate_client(body.get('client'))
    query = body.get('query', '')
    try:
        result = get_services()['udb'].search(client_key, query)
    except Exception as exc:
        raise ApiError(str(exc), 502 if _is_network_error(exc) else 400)
    return jsonify(result)


@api.route('/api/inspect', methods=['POST'])
def inspect():
    body = request.get_json(silent=True) or {}
    client_key = _validate_client(body.get('client'))
    result_id = body.get('result_id')
    if not result_id:
        raise ApiError('result_id is required')
    try:
        result = get_services()['udb'].inspect(client_key, result_id)
    except Exception as exc:
        raise ApiError(str(exc), 502 if _is_network_error(exc) else 400)
    return jsonify(result)


# --------------------------------------------------------------------------- #
# Downloads                                                                   #
# --------------------------------------------------------------------------- #
@api.route('/api/download', methods=['POST'])
def create_download():
    body = request.get_json(silent=True) or {}
    ep_session = body.get('episode_session')
    resolution = body.get('resolution') or '1080'
    selection = body.get('selection') or body.get('episodes') or {}
    download_dir = body.get('download_dir') or _default_download_dir()

    if not ep_session:
        raise ApiError('episode_session is required')
    if not selection:
        raise ApiError('Episode selection is required')

    _ensure_dir_exists(download_dir)

    try:
        jobs = get_services()['manager'].create_batch(
            ep_session, resolution, selection, download_dir)
    except Exception as exc:
        raise ApiError(str(exc), 502 if _is_network_error(exc) else 400)

    return jsonify({'jobs': jobs, 'created': len(jobs)})


@api.route('/api/downloads', methods=['GET'])
def downloads():
    status = request.args.get('status')
    limit = int(request.args.get('limit', 200))
    return jsonify({'downloads': get_services()['manager'].list(status=status, limit=limit)})


@api.route('/api/downloads/<job_id>', methods=['GET'])
def download(job_id):
    job = get_services()['manager'].get(job_id)
    if job is None:
        raise ApiError('Download not found', 404)
    return jsonify(job)


@api.route('/api/downloads/<job_id>/cancel', methods=['POST'])
def cancel_download(job_id):
    ok = get_services()['manager'].cancel(job_id)
    if not ok:
        raise ApiError('Download cannot be cancelled', 400)
    return jsonify({'ok': True})


@api.route('/api/downloads/<job_id>/retry', methods=['POST'])
def retry_download(job_id):
    ok = get_services()['manager'].retry(job_id)
    if not ok:
        raise ApiError('Download cannot be retried (expired links). Please re-add it.', 400)
    return jsonify({'ok': True})


@api.route('/api/downloads/<job_id>', methods=['DELETE'])
def remove_download(job_id):
    ok = get_services()['manager'].remove(job_id)
    if not ok:
        raise ApiError('Download not found', 404)
    return jsonify({'ok': True})


@api.route('/api/downloads/<job_id>/open-folder', methods=['POST'])
def open_folder(job_id):
    ok = get_services()['manager'].open_folder(job_id)
    if not ok:
        raise ApiError('Folder not available', 400)
    return jsonify({'ok': True})


# --------------------------------------------------------------------------- #
# History                                                                     #
# --------------------------------------------------------------------------- #
@api.route('/api/history', methods=['GET'])
def history():
    status = request.args.get('status')
    search = request.args.get('search')
    limit = int(request.args.get('limit', 200))
    sort_by = request.args.get('sort_by', 'date')
    order = request.args.get('order', 'desc')
    items = get_services()['history'].list(
        status=status, search=search, limit=limit, sort_by=sort_by, order=order)
    return jsonify({'history': items})


@api.route('/api/history/stats', methods=['GET'])
def history_stats():
    counts = get_services()['history'].counts()
    total = get_services()['history'].total_downloaded()
    return jsonify({'counts': counts, 'total_downloaded_bytes': total})


@api.route('/api/history/<record_id>', methods=['DELETE'])
def delete_history(record_id):
    ok = get_services()['history'].delete(record_id)
    if not ok:
        raise ApiError('History record not found', 404)
    return jsonify({'ok': True})


@api.route('/api/history', methods=['DELETE'])
def clear_history():
    get_services()['history'].clear()
    return jsonify({'ok': True})


@api.route('/api/history/<record_id>/retry', methods=['POST'])
def retry_history(record_id):
    record = get_services()['history'].get(record_id)
    if not record:
        raise ApiError('History record not found', 404)
    details = (record.get('extra') or {}).get('ep_details')
    if not details:
        raise ApiError('This download cannot be retried automatically. Please re-add it.', 400)
    job = get_services()['manager'].add_retry_job(record, details)
    return jsonify({'ok': True, 'job': job})


# --------------------------------------------------------------------------- #
# Settings                                                                    #
# --------------------------------------------------------------------------- #
@api.route('/api/settings', methods=['GET'])
def settings():
    return jsonify(get_services()['config'].get_settings())


@api.route('/api/settings', methods=['PUT'])
def update_settings():
    patch = request.get_json(silent=True) or {}
    if not isinstance(patch, dict):
        raise ApiError('Invalid settings payload')
    updated = get_services()['config'].update_settings(patch)
    return jsonify(updated)


@api.route('/api/logs', methods=['GET'])
def logs():
    log_dir = get_services()['logs_dir']
    entries = []
    try:
        files = sorted(
            [f for f in os.listdir(log_dir) if f.endswith('.log')],
            reverse=True)[:10]
        for fname in files:
            path = os.path.join(log_dir, fname)
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()[-20000:]
                entries.append({'name': fname, 'content': content})
            except OSError:
                continue
    except OSError:
        pass
    return jsonify({'logs': entries})


# --------------------------------------------------------------------------- #
# SSE event stream                                                            #
# --------------------------------------------------------------------------- #
@api.route('/api/events', methods=['GET'])
def events():
    bus = get_services()['event_bus']
    q = bus.subscribe()

    def gen():
        try:
            # immediate ping so the client knows the stream is alive
            yield 'event: hello\ndata: {}\n\n'
            while True:
                try:
                    event = q.get(timeout=15)
                    yield f"event: {event.get('type', 'message')}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                except Exception:
                    # heartbeat to keep the connection open
                    yield ': keep-alive\n\n'
        finally:
            bus.unsubscribe(q)

    return Response(stream_with_context(gen()), mimetype='text/event-stream')


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def get_services():
    from flask import current_app
    return current_app.config['UDB_SERVICES']


def _validate_client(client_key):
    if not client_key:
        raise ApiError('client is required (animepahe | kisskh)')
    if client_key not in ('animepahe', 'kisskh'):
        raise ApiError('Unknown client', 400)
    return client_key


def _default_download_dir():
    from backend.app_config import get_downloads_default_dir
    return get_downloads_default_dir()


def _ensure_dir_exists(path):
    if not path:
        return
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as exc:
        raise ApiError(f'Download directory is not writable: {exc}', 400)


def _is_network_error(exc):
    message = str(exc).lower()
    return any(k in message for k in ('timed out', 'connection', 'http', 'status code', 'ssl', 'socket'))

