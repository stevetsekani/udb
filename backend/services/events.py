r"""
Minimal in-process pub/sub event bus.

The backend fans real download progress, job state changes and other events out
to the web UI via Server-Sent Events. Each SSE client registers a
``queue.Queue``; the API layer drains queues and streams them as SSE.
"""

import queue
import threading
from collections import defaultdict


class EventBus:
    def __init__(self):
        self._subscribers = set()
        self._lock = threading.Lock()

    def subscribe(self) -> 'queue.Queue':
        """Register a new subscriber and return its event queue."""
        q = queue.Queue(maxsize=2000)
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q) -> None:
        with self._lock:
            self._subscribers.discard(q)

    def publish(self, event: dict) -> None:
        """
        Publish an event dict to every subscriber. Subscribers whose queues are
        full are dropped (a slow client must not stall downloads).
        """
        with self._lock:
            subscribers = list(self._subscribers)
        for q in subscribers:
            try:
                q.put_nowait(event)
            except queue.Full:
                with self._lock:
                    self._subscribers.discard(q)
            except Exception:
                pass

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

