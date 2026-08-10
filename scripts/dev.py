r"""
Development launcher — run the local backend and the Vite dev server together.

The backend binds to 127.0.0.1 on an ephemeral port and writes
``backend_port.json`` so the Vite proxy can find it. The Vite dev server
serves the React frontend with hot reload on http://127.0.0.1:5173.

Usage::

    python scripts/dev.py                # backend + Vite
    python scripts/dev.py --no-vite      # backend only (test the API)
    python scripts/dev.py --port 8000    # fixed backend port

Ctrl+C stops both cleanly.
"""

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_THIS_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import argparse
import subprocess
import threading

from backend.server import start_backend_thread

import urllib.request


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='udb-dev', description='UDB development server')
    parser.add_argument('--no-vite', action='store_true', help='Run the backend only')
    parser.add_argument('--port', type=int, default=None, help='Backend port (default: ephemeral)')
    parser.add_argument('--debug', action='store_true', help='Backend debug logging')
    args = parser.parse_args(argv)

    # Start the backend (writes backend_port.json for the Vite proxy).
    host, port, thread, server = start_backend_thread(host='127.0.0.1', port=args.port)
    print(f'[udb-dev] backend ready at http://{host}:{port}')

    # Verify the health endpoint.
    try:
        with urllib.request.urlopen(f'http://{host}:{port}/api/health', timeout=3) as r:
            print(f'[udb-dev] health check -> {r.status}')
    except Exception as exc:
        print(f'[udb-dev] warning: health check failed: {exc}')

    if args.no_vite:
        print('[udb-dev] backend only. Press Ctrl+C to stop.')
        try:
            stop = threading.Event()
            stop.wait()  # Ctrl+C raises KeyboardInterrupt here (cross-platform)
        except KeyboardInterrupt:
            pass
    else:
        frontend_dir = os.path.join(_REPO_ROOT, 'frontend')
        cmd = ['npm', 'run', 'dev']
        proc = subprocess.Popen(cmd, cwd=frontend_dir)
        print('[udb-dev] Vite dev server starting (Ctrl+C to stop).')
        try:
            proc.wait()
        except KeyboardInterrupt:
            print('\n[udb-dev] stopping…')
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()

    server.shutdown()
    print('[udb-dev] backend stopped.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

