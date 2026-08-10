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


def run_server(host='127.0.0.1', port=None, debug=False, services=None,
               write_port_file=True):
    """
    Start the Flask backend. Blocks until the server stops.

    Returns the (host, port) actually used.
    """
    port = port or find_free_port()
    ensure_ffmpeg_on_path()

    app = create_app(services=services)

    if write_port_file:
        port_file = os.path.join(get_app_data_dir(), PORT_FILE)
        os.makedirs(os.path.dirname(port_file), exist_ok=True)
        with open(port_file, 'w', encoding='utf-8') as f:
            json.dump({'host': host, 'port': port}, f)

    logger.info('UDB backend starting on http://%s:%d', host, port)
    # Use threaded=True so SSE streams and downloads run in separate threads.
    app.run(host=host, port=port, debug=debug, threaded=True,
            use_reloader=False, use_debugger=False)
    return host, port


def wait_for_backend(host, port, timeout=30):
    """Poll the health endpoint until the backend responds."""
    import urllib.request

    deadline = time.time() + timeout
    url = f'http://{host}:{port}/api/health'
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def start_backend_thread(host='127.0.0.1', port=None, debug=False, services=None):
    """
    Start the backend in a daemon thread. Returns (host, port, thread).
    """
    port = port or find_free_port()

    def target():
        run_server(host=host, port=port, debug=debug, services=services)

    t = threading.Thread(target=target, name='udb-backend', daemon=True)
    t.start()
    if not wait_for_backend(host, port):
        raise RuntimeError(f'Backend failed to start on {host}:{port}')
    return host, port, t

