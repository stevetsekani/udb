"""Tests for the in-process EventBus (SSE backing store)."""

from backend.services.events import EventBus


def test_publish_delivers_to_subscribers():
    bus = EventBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    bus.publish({'type': 'download_progress', 'progress': 42})
    assert q1.get_nowait()['progress'] == 42
    assert q2.get_nowait()['progress'] == 42


def test_unsubscribe_stops_delivery():
    bus = EventBus()
    q = bus.subscribe()
    bus.unsubscribe(q)
    bus.publish({'type': 'x'})
    assert bus.subscriber_count() == 0
    assert q.empty()


def test_subscriber_count():
    bus = EventBus()
    assert bus.subscriber_count() == 0
    bus.subscribe()
    bus.subscribe()
    assert bus.subscriber_count() == 2


def test_slow_subscriber_is_dropped():
    bus = EventBus()
    q = bus.subscribe()
    # Fill the queue (maxsize 2000) so publishes start failing
    for _ in range(2000):
        bus.publish({'type': 'spam', 'i': 1})
    bus.publish({'type': 'final'})
    # The slow subscriber should have been dropped
    assert bus.subscriber_count() == 0
    assert q.full() or q.empty() is False

