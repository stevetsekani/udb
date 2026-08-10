r"""
UDB desktop shell — PyWebView launcher.

Starts the local backend on 127.0.0.1, opens a native window pointing at the
bundled web frontend, and shuts everything down cleanly when the window is
closed.

Run from source::

    python desktop/main.py

Run with the dev server on http://127.0.0.1:5173 instead of the built bundle::

    python desktop/main.py --dev-url http://127.0.0.1:5173
"""

import os
import sys

# --------------------------------------------------------------------------- #
# sys.path bootstrap so this module can be executed directly or as a package  #
# --------------------------------------------------------------------------- #
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_THIS_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import argparse
import logging
import logging.handlers
import platform
import secrets
import subprocess
import threading
import time

from backend import version as version_module
from backend.app_config import get_app_data_dir, get_logs_dir, is_portable
from backend.server import start_backend_thread

logger = logging.getLogger('udb.desktop')

TOKEN_FILE = 'auth_token'


# --------------------------------------------------------------------------- #
# Logging                                                                      #
# --------------------------------------------------------------------------- #
def _setup_logging(verbose: bool) -> str:
    """Configure console + rotating file logging. Returns the log directory."""
    log_dir = get_logs_dir()
    fmt = logging.Formatter('%(asctime)s %(levelname)-7s %(name)s: %(message)s')

    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'udb-desktop.log'),
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8',
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    logging.getLogger().addHandler(console)

    logging.getLogger().setLevel(logging.DEBUG)
    return log_dir


# --------------------------------------------------------------------------- #
# Local auth token                                                             #
# --------------------------------------------------------------------------- #
def _get_auth_token() -> str:
    """
    Return a persisted per-install token so API calls from the served page are
    accepted. The token is random and only ever exposed to the local webview.
    """
    token_path = os.path.join(get_app_data_dir(), TOKEN_FILE)
    try:
        with open(token_path, 'r', encoding='utf-8') as f:
            token = f.read().strip()
            if token:
                return token
    except OSError:
        pass
    token = secrets.token_urlsafe(24)
    try:
        with open(token_path, 'w', encoding='utf-8') as f:
            f.write(token)
    except OSError:
        logger.warning('Could not persist auth token; using ephemeral token')
    return token


# --------------------------------------------------------------------------- #
# JS bridge exposed to the frontend                                           #
# --------------------------------------------------------------------------- #
class _Api:
    """Python methods callable from the webview via ``window.pywebview.api``."""

    def open_folder(self, path: str) -> bool:
        """Open the containing folder for a path (file or directory)."""
        if not path:
            return False
        path = os.path.expanduser(os.path.abspath(path))
        if os.path.isfile(path):
            path = os.path.dirname(path)
        if not os.path.isdir(path):
            logger.warning('open_folder: not a directory: %s', path)
            return False
        try:
            if platform.system() == 'Windows':
                os.startfile(path)  # type: ignore[attr-defined]
            elif platform.system() == 'Darwin':
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
            return True
        except Exception as exc:  # pragma: no cover - OS specific
            logger.error('open_folder failed for %s: %s', path, exc)
            return False

    def quit(self) -> None:
        """Ask the desktop shell to exit (used by the About page)."""
        import webview
        try:
            for window in webview.windows:
                window.destroy()
        except Exception as exc:  # pragma: no cover
            logger.warning('quit request ignored: %s', exc)


# --------------------------------------------------------------------------- #
# Error dialogs                                                                #
# --------------------------------------------------------------------------- #
def _show_error(title: str, message: str) -> None:
    """Show a native error dialog where possible, otherwise print to stderr."""
    system = platform.system()
    if system == 'Windows':
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
            return
        except Exception:
            pass
    elif system == 'Darwin':
        try:
            subprocess.run(['osascript', '-e',
                            f'display alert "{title}" message "{message}"'], check=False)
            return
        except Exception:
            pass
    else:
        for cmd in (['zenity', '--error', '--title', title, '--text', message],
                    ['kdialog', '--error', message]):
            try:
                subprocess.run(cmd, check=False)
                return
            except Exception:
                continue
    print(f'ERROR: {title}: {message}', file=sys.stderr)


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='udb-desktop', description='UDB desktop app')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode (dev tools, verbose logs)')
    parser.add_argument('--dev-url', default=None, metavar='URL',
                        help='Point the window at a running frontend dev server (e.g. http://127.0.0.1:5173)')
    parser.add_argument('--port', type=int, default=None, help='Force a backend port (default: ephemeral)')
    parser.add_argument('--version', action='store_true', help='Print version and exit')
    args = parser.parse_args(argv)

    if args.version:
        print(f'UDB {version_module.__version__}')
        return 0

    _setup_logging(args.debug)
    logger.info('UDB %s desktop shell starting (frozen=%s, portable=%s)',
                version_module.__version__, is_portable(), is_portable())

    # Auth token must be in the environment *before* create_app() reads it.
    os.environ['UDB_API_TOKEN'] = _get_auth_token()

    # ------------------------------------------------------------------ #
    # Start the local backend                                             #
    # ------------------------------------------------------------------ #
    try:
        host, port, thread, server = start_backend_thread(host='127.0.0.1', port=args.port)
    except Exception as exc:
        message = f'Failed to start the local backend:\n{exc}\n\nPlease check the logs in:\n{get_logs_dir()}'
        logger.exception('Backend startup failed')
        _show_error('UDB could not start', message)
        return 1

    url = args.dev_url or f'http://{host}:{port}'
    logger.info('Backend ready at http://%s:%d (thread=%s)', host, port, thread.name)

    # ------------------------------------------------------------------ #
    # Launch the webview                                                  #
    # ------------------------------------------------------------------ #
    try:
        import webview
    except ImportError:
        logger.exception('PyWebView is not installed')
        _show_error(
            'UDB could not start',
            'The desktop UI component (PyWebView) is missing.\n\n'
            f'The backend is still running at:\n{url}\n\n'
            'Install it with: pip install pywebview\n'
            'or open the URL above in a browser.',
        )
        server.shutdown()
        return 1

    api = _Api()
    window = webview.create_window(
        'UDB',
        url,
        js_api=api,
        width=1200,
        height=820,
        min_size=(920, 600),
        background_color='#101318',
    )

    def _on_closed():
        logger.info('Webview window closed; shutting down backend')
        server.shutdown()

    try:
        window.events.closed += _on_closed
    except Exception:
        logger.debug('No closed event available; will shut down after webview.start returns')

    try:
        webview.start(debug=args.debug, gui=None)
    except Exception as exc:
        # GUI failed (e.g. missing GTK/WebKit on Linux). Keep the backend alive
        # so the user can still use the URL in a browser, but tell them why.
        logger.exception('Could not open desktop window')
        _show_error(
            'UDB window could not open',
            f'{exc}\n\nThe backend is still running.\nOpen this URL in your browser:\n{url}',
        )
        # Poll until interrupted so the backend keeps serving; the user can
        # close the terminal to stop everything.
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    finally:
        try:
            server.shutdown()
        except Exception:
            pass
        logger.info('Backend shut down. Goodbye.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
