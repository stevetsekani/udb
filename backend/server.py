r"""
Backend server runner.

Binds strictly to 127.0.0.1 on an ephemeral port and runs the Flask app. The
desktop shell and the dev scripts use this module to launch the backend.

The chosen port is written to a JSON file in the app-data directory so other
parts of the tooling (e.g. the Vite dev proxy) can discover it.
"""

import json
import logging
import os
import socket
import threading
import time

from backend.app import create_app
from backend.app_config import get_app_data_dir
from backend.services.ffmpeg_service import ensure_ffmpeg_on_path

logger = logging.getLogger('udb.server')

PORT_FILE = 'backend_port.json'


def find_free_port() -> int:
    """Return an ephemeral free port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def make_backend_server(host='127.0.0.1', port=None, services=None):
    """
    Create (but do not start) a shutdown-able Werkzeug server for the backend.

    Returns a 3-tuple ``(server, app, port)``. ``server`` is a
    ``werkzeug.serving.BaseWSGIServer`` whose ``serve_forever()`` /
    ``shutdown()`` methods control the process lifecycle. Threaded mode is
    always on so SSE streams and downloads run in separate threads.
    """
    from werkzeug.serving import make_server

    port = port or find_free_port()
    ensure_ffmpeg_on_path()
    app = create_app(services=services)
    server = make_server(host, port, app, threaded=True)
    return server, app, port


def run_server(host='127.0.0.1', port=None, debug=False, services=None,
               write_port_file=True):
    """
    Start the Flask backend. Blocks until the server stops.

    Returns the (host, port) actually used.
    """
    server, app, port = make_backend_server(host=host, port=port, services=services)

    if write_port_file:
        port_file = os.path.join(get_app_data_dir(), PORT_FILE)
        os.makedirs(os.path.dirname(port_file), exist_ok=True)
        with open(port_file, 'w', encoding='utf-8') as f:
            json.dump({'host': host, 'port': port}, f)

    logger.info('UDB backend starting on http://%s:%d', host, port)
    server.serve_forever()
    return host, port


def wait_for_backend(host, port, timeout=30):
    """Poll the health endpoint until the backend responds."""
    import urllib.request

    # When an auth token is in the environment (desktop shell), the readiness
    # probe must present it or the backend will answer 401 forever.
    token = os.environ.get('UDB_API_TOKEN') or ''
    headers = {'X-UDB-Token': token} if token else {}

    deadline = time.time() + timeout
    url = f'http://{host}:{port}/api/health'
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def start_backend_thread(host='127.0.0.1', port=None, services=None,
                         write_port_file=True):
    """
    Start the backend in a daemon thread.

    Returns a 4-tuple ``(host, port, thread, server)``. The caller may call
    ``server.shutdown()`` (from any thread) to stop the backend cleanly.
    """
    port = port or find_free_port()
    server, app, port = make_backend_server(host=host, port=port, services=services)

    if write_port_file:
        port_file = os.path.join(get_app_data_dir(), PORT_FILE)
        os.makedirs(os.path.dirname(port_file), exist_ok=True)
        with open(port_file, 'w', encoding='utf-8') as f:
            json.dump({'host': host, 'port': port}, f)

    t = threading.Thread(target=server.serve_forever, name='udb-backend', daemon=True)
    t.start()
    if not wait_for_backend(host, port):
        server.shutdown()
        raise RuntimeError(f'Backend failed to start on {host}:{port}')
    return host, port, t, server

