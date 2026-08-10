r"""
Flask application factory for the UDB local backend.

Responsibilities:
* wire together the service layer (config, history, event bus, UDB service,
  download manager, FFmpeg)
* register the local API blueprint
* serve the built frontend (production) so the desktop shell can point the
  webview at a single local origin
* bind strictly to 127.0.0.1 (enforced by the server run code)
* optionally require a local auth token injected into the served page
"""

import logging
import os
import sys

from flask import Flask, Response, jsonify, request, send_from_directory

from backend import version as version_module
from backend.api.routes import ApiError, api
from backend.services.config_service import ConfigService
from backend.services.download_manager import DownloadManager
from backend.services.events import EventBus
from backend.services.ffmpeg_service import ensure_ffmpeg_on_path
from backend.services.history import HistoryService
from backend.services.udb_service import UDBService

logger = logging.getLogger('udb.api')


def _find_frontend_dist():
    """Locate the built frontend directory (frontend/dist) in dev or bundle."""
    candidates = []
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        candidates.append(os.path.join(base, 'frontend', 'dist'))
        candidates.append(os.path.join(base, 'dist'))
        candidates.append(os.path.join(os.path.dirname(sys.executable), 'frontend', 'dist'))
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates.append(os.path.join(repo_root, 'frontend', 'dist'))
    for candidate in candidates:
        index = os.path.join(candidate, 'index.html')
        if os.path.isfile(index):
            return candidate
    return None


def create_app(services: dict = None) -> Flask:
    """
    Create and configure the Flask application.

    ``services`` may be injected for testing. Otherwise the default service
    graph is created.
    """
    app = Flask(__name__, static_folder=None)
    app.config['JSON_SORT_KEYS'] = False
    app.config['UDB_SERVICES'] = services or _default_services()

    # Expose version for templates / injection
    app.config['UDB_VERSION'] = version_module.__version__
    app.config['UDB_API_TOKEN'] = os.environ.get('UDB_API_TOKEN') or ''

    app.register_blueprint(api)

    # ------------------------------------------------------------------ #
    # Error handling — never leak tracebacks to the UI                    #
    # ------------------------------------------------------------------ #
    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return jsonify({'error': {'message': err.message, 'details': err.details}}), err.status_code

    @app.errorhandler(404)
    def handle_404(err):
        # Let SPA routes fall through to index.html when serving the frontend
        dist = _find_frontend_dist()
        if dist and not request.path.startswith('/api/'):
            return _serve_index(app, dist)
        return jsonify({'error': {'message': 'Not found'}}), 404

    @app.errorhandler(Exception)
    def handle_exception(err):
        logger.error('Unhandled API error: %s', err, exc_info=True)
        return jsonify({'error': {'message': 'An unexpected error occurred. Please check the logs for details.'}}), 500

    # ------------------------------------------------------------------ #
    # Local auth token (optional)                                        #
    # ------------------------------------------------------------------ #
    token = app.config['UDB_API_TOKEN']

    @app.before_request
    def check_token():
        if not token:
            return None
        if request.path.startswith('/api/'):
            supplied = request.headers.get('X-UDB-Token') or request.args.get('token')
            if supplied != token:
                return jsonify({'error': {'message': 'Unauthorized'}}), 401
        return None

    # ------------------------------------------------------------------ #
    # CORS for local development (frontend dev server on localhost)       #
    # ------------------------------------------------------------------ #
    @app.after_request
    def allow_local_cors(response):
        origin = request.headers.get('Origin', '')
        if origin and _is_local_origin(origin):
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-UDB-Token'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response

    @app.route('/api/config', methods=['GET'])
    def api_config():
        return jsonify({
            'version': version_module.__version__,
            'token_required': bool(token),
            'token': token,   # localhost-only; used by the desktop shell to auth
        })

    # ------------------------------------------------------------------ #
    # Production frontend serving                                        #
    # ------------------------------------------------------------------ #
    dist = _find_frontend_dist()
    app.config['UDB_DIST'] = dist

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def spa(path):
        if request.path.startswith('/api/'):
            return jsonify({'error': {'message': 'Not found'}}), 404
        dist = app.config.get('UDB_DIST') or _find_frontend_dist()
        if not dist:
            return Response('UDB backend is running. Frontend not built.', mimetype='text/plain'), 200
        full_path = os.path.join(dist, path)
        if path and os.path.isfile(full_path):
            return send_from_directory(dist, path)
        return _serve_index(app, dist)

    return app


def _serve_index(app, dist):
    index_path = os.path.join(dist, 'index.html')
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            html = f.read()
    except OSError:
        return Response('Frontend index.html not found.', mimetype='text/plain'), 404
    token = app.config.get('UDB_API_TOKEN') or ''
    if token:
        import re
        if re.search(r'<meta[^>]+name="udb-token"', html):
            html = re.sub(r'<meta[^>]+name="udb-token"[^>]*>',
                          f'<meta name="udb-token" content="{token}">', html)
        else:
            html = html.replace('</head>',
                                f'<meta name="udb-token" content="{token}"></head>')
    return Response(html, mimetype='text/html')


def _default_services() -> dict:
    """
    Build the default service graph. Ensures bundled FFmpeg is first on PATH
    before any downloader runs.
    """
    config = ConfigService()
    history = HistoryService()
    event_bus = EventBus()
    udb = UDBService(config)
    manager = DownloadManager(event_bus, history, udb)

    # Make sure ffmpeg/ffprobe resolve to bundled binaries if present
    gui = config.load_gui_settings()
    ensure_ffmpeg_on_path(gui.get('ffmpeg_configured_path'))

    from backend.app_config import get_logs_dir
    return {
        'config': config,
        'history': history,
        'event_bus': event_bus,
        'udb': udb,
        'manager': manager,
        'logs_dir': get_logs_dir(),
        'ffmpeg': __import__('backend.services.ffmpeg_service', fromlist=['ffmpeg_service']),
    }


def _is_local_origin(origin: str) -> bool:
    host = origin.split('://')[-1].split('/')[0]
    if host.startswith('localhost') or host.startswith('127.0.0.1'):
        return True
    if host.startswith('[') and '::1' in host:
        return True
    return False

