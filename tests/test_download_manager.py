"""Tests for the DownloadManager job lifecycle."""

import time

from backend.services.download_manager import (
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_FAILED,
)


def _wait_for_status(manager, job_id, statuses, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = manager.get(job_id)
        if job and job['status'] in statuses:
            return job
        time.sleep(0.05)
    job = manager.get(job_id)
    raise AssertionError(f'job {job_id} did not reach {statuses}: {job and job["status"]}')


def test_create_batch_downloads_and_completes(manager):
    jobs = manager.create_batch('ep-1', '1080', {'start': 1, 'end': 2}, 'C:/tmp')
    assert len(jobs) == 2
    for job in jobs:
        # Do not assert the transient initial status — a fast machine may have
        # already finished the background prep + download by the time
        # create_batch returns. Just verify each job reaches a terminal state.
        final = _wait_for_status(manager, job['id'], [STATUS_COMPLETED, STATUS_FAILED])
        assert final['status'] == STATUS_COMPLETED
        assert final['progress'] == 100.0


def test_batch_creates_history_records(manager, history_service):
    jobs = manager.create_batch('ep-1', '1080', {'start': 1, 'end': 1}, 'C:/tmp')
    _wait_for_status(manager, jobs[0]['id'], [STATUS_COMPLETED, STATUS_FAILED])
    items = history_service.list()
    assert len(items) == 1
    assert items[0]['title'] == 'Test Series'
    assert items[0]['episode'] == 1.0 or int(items[0]['episode']) == 1


def test_cancel_stops_job(manager, udb_service):
    # Force the fake downloader to block until cancelled so the race is won.
    udb_service.block_until_cancel = True
    jobs = manager.create_batch('ep-1', '1080', {'start': 1, 'end': 1}, 'C:/tmp')
    first = jobs[0]
    assert manager.cancel(first['id']) is True
    final = _wait_for_status(manager, first['id'], [STATUS_CANCELLED, STATUS_FAILED, STATUS_COMPLETED])
    assert final['status'] == STATUS_CANCELLED
    # Cancelling a completed/failed job returns False
    assert manager.cancel(first['id']) is False


def test_remove_drops_job(manager):
    jobs = manager.create_batch('ep-1', '1080', {'start': 1, 'end': 1}, 'C:/tmp')
    job_id = jobs[0]['id']
    assert manager.remove(job_id) is True
    assert manager.get(job_id) is None
    assert manager.remove('nope') is False


def test_summary_and_list(manager):
    jobs = manager.create_batch('ep-1', '720', {'start': 1, 'end': 3}, 'C:/tmp')
    summary = manager.summary()
    assert summary['active'] >= 0
    assert len(manager.list(limit=10)) >= 1
    assert manager.get(jobs[0]['id']) is not None


def test_prepare_failure_marks_jobs_failed(manager, udb_service):
    udb_service.fail_next_prepare = True
    jobs = manager.create_batch('ep-1', '1080', {'start': 1, 'end': 1}, 'C:/tmp')
    final = _wait_for_status(manager, jobs[0]['id'], [STATUS_FAILED, STATUS_COMPLETED])
    assert final['status'] == STATUS_FAILED
    assert 'simulated preparation failure' in final['error']

