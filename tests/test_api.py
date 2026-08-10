"""HTTP-level tests for the Flask API."""

import json
import time


def _dl_dir(tmp_path):
    d = tmp_path / 'downloads'
    d.mkdir(exist_ok=True)
    return str(d)


def test_health(client):
    res = client.get('/api/health')
    assert res.status_code == 200
    assert res.json['status'] == 'ok'


def test_version(client):
    res = client.get('/api/version')
    assert res.status_code == 200
    assert res.json['app'] == 'UDB'
    assert res.json['version']


def test_system(client):
    res = client.get('/api/system')
    assert res.status_code == 200
    assert res.json['os']
    assert 'python' in res.json


def test_settings_round_trip(client):
    res = client.get('/api/settings')
    assert res.status_code == 200
    settings = res.json
    assert settings['theme'] == 'dark'
    assert settings['max_parallel_downloads'] >= 1

    res = client.put('/api/settings', json={'theme': 'light', 'max_parallel_downloads': 4})
    assert res.status_code == 200
    assert res.json['theme'] == 'light'
    assert res.json['max_parallel_downloads'] == 4

    res = client.get('/api/settings')
    assert res.json['theme'] == 'light'


def test_downloads_flow(client, tmp_path):
    # create a batch
    res = client.post('/api/download', json={
        'episode_session': 'ep-1',
        'resolution': '1080',
        'selection': {'start': 1, 'end': 1},
        'download_dir': _dl_dir(tmp_path),
    })
    assert res.status_code == 200
    jobs = res.json['jobs']
    assert len(jobs) == 1
    job_id = jobs[0]['id']

    # list
    res = client.get('/api/downloads')
    assert res.status_code == 200
    assert any(d['id'] == job_id for d in res.json['downloads'])

    # single
    res = client.get(f'/api/downloads/{job_id}')
    assert res.status_code == 200

    # cancel
    res = client.post(f'/api/downloads/{job_id}/cancel')
    assert res.status_code in (200, 400)  # 400 if already finished

    # remove
    res = client.delete(f'/api/downloads/{job_id}')
    assert res.status_code == 200
    res = client.get(f'/api/downloads/{job_id}')
    assert res.status_code == 404


def test_download_validation(client):
    res = client.post('/api/download', json={'episode_session': 'ep-1'})
    assert res.status_code == 400
    body = res.json
    assert 'selection' in body['error']['message'].lower() or 'required' in body['error']['message'].lower()


def test_history_flow(client, tmp_path):
    # seed via a completed download
    res = client.post('/api/download', json={
        'episode_session': 'ep-1',
        'resolution': '1080',
        'selection': {'start': 1, 'end': 1},
        'download_dir': _dl_dir(tmp_path),
    })
    assert res.status_code == 200, res.json
    job_id = res.json['jobs'][0]['id']

    # wait for completion
    for _ in range(100):
        j = client.get(f'/api/downloads/{job_id}').json
        if j['status'] in ('completed', 'failed', 'cancelled'):
            break
        time.sleep(0.05)

    res = client.get('/api/history')
    assert res.status_code == 200
    assert len(res.json['history']) >= 1

    res = client.get('/api/history/stats')
    assert res.status_code == 200
    assert 'counts' in res.json

    # clear
    res = client.delete('/api/history')
    assert res.status_code == 200
    res = client.get('/api/history')
    assert res.json['history'] == []


def test_unknown_client_rejected(client):
    res = client.post('/api/search', json={'client': 'bogus', 'query': 'x'})
    assert res.status_code == 400


def test_unknown_route_returns_json(client):
    res = client.get('/api/nope')
    assert res.status_code == 404
    assert 'error' in res.json


def test_logs_endpoint(client):
    res = client.get('/api/logs')
    assert res.status_code == 200
    assert 'logs' in res.json

