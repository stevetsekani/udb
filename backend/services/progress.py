r"""
Progress reporting for the UDB downloader.

The existing downloaders report progress through ``tqdm`` writing to stdout.
For the GUI we inject a lightweight ``ProgressReporter`` (a drop-in replacement
for the bits of the tqdm interface the downloader actually uses) that forwards
progress events to a callback instead of the terminal. The callback is wired to
the download manager which fans events out over Server-Sent Events.

This keeps the downloader core untouched while giving the GUI real progress
(never faked).
"""

import time
from threading import Lock

# Minimum interval (seconds) between callback emissions, to avoid flooding the
# event channel on very fast / very segmented downloads.
MIN_EMIT_INTERVAL = 0.15


class DownloadCancelled(Exception):
    """Raised inside the downloader when the user cancels a download."""

    def __init__(self, message='Download cancelled by user'):
        super().__init__(message)


class ProgressReporter:
    """
    Minimal tqdm-compatible progress bar that calls ``callback(payload)``.

    The UDB downloaders use: ``__init__(**metadata)``, ``.update(n)``,
    ``.set_postfix_str(s, refresh)`` and context-manager semantics.
    """

    def __init__(self, total=None, unit='', desc='', callback=None,
                 postfix=None, **kwargs):
        self.total = total if total is not None else 0
        self.unit = unit or ''
        self.desc = desc or ''
        self.callback = callback
        self.n = 0
        self.postfix = postfix or ''
        self._lock = Lock()
        self._last_emit = 0.0
        self._last_n = 0
        self._last_time = time.time()
        self._started = time.time()

    def __enter__(self):
        self._emit(force=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Emit a final 100% update when the loop completed normally.
        if exc_type is None and self.total and self.n >= self.total:
            self._emit(force=True)

    def update(self, n=1):
        with self._lock:
            self.n += n
        self._emit()

    def set_postfix_str(self, s, refresh=True):
        self.postfix = s
        if refresh:
            self._emit()

    # -- internal ------------------------------------------------------ #
    def _emit(self, force=False):
        if not self.callback:
            return
        now = time.time()
        with self._lock:
            if not force and (now - self._last_emit) < MIN_EMIT_INTERVAL:
                return
            if not force and self.n == self._last_n:
                return
            self._last_emit = now
            delta_n = self.n - self._last_n
            delta_t = now - self._last_time
            self._last_n = self.n
            self._last_time = now

        progress = (self.n / self.total * 100.0) if self.total else 0.0
        speed = (delta_n / delta_t) if delta_t > 0 else 0.0
        payload = {
            'progress': round(min(progress, 100.0), 1),
            'completed': self.n,
            'total': self.total,
            'unit': self.unit,
            'desc': self.desc,
            'postfix': self.postfix,
            'speed': round(speed, 1),
            'elapsed': round(now - self._started, 1),
        }
        self.callback(payload)

    def reset(self):
        with self._lock:
            self.n = 0
            self._last_n = 0
            self._last_time = time.time()


def format_speed(speed, unit='iB'):
    """Return a human-readable speed string for the GUI."""
    if unit == 'iB':
        if speed >= 1024 * 1024:
            return f'{speed / (1024 * 1024):.1f} MB/s'
        if speed >= 1024:
            return f'{speed / 1024:.1f} KB/s'
        return f'{speed:.0f} B/s'
    return f'{speed:.1f} {unit}/s'

