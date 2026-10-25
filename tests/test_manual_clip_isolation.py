import io
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest
import manual_clip_worker as worker


def _process(monkeypatch, lines, code=0):
    calls = []
    proc = SimpleNamespace(stdout=io.StringIO(lines), wait=lambda: code, poll=lambda: code)
    monkeypatch.setattr(worker.subprocess, 'Popen', lambda *a, **k: calls.append((a, k)) or proc)
    return calls


def test_native_crash_is_a_failed_job_not_an_api_exit(tmp_path, monkeypatch):
    calls = _process(monkeypatch, 'Tracking faces...\nWindows fatal exception: access violation\n', 3221225477)
    job = {'status': 'queued', 'logs': [], 'user_id': 'owner'}
    worker.run_manual_clips_job('manual_test', 'source.mp4', [], str(tmp_path), jobs_dict={'manual_test': job})
    assert job['status'] == 'failed'
    assert '0xC0000005' in job['error']
    assert 'Tracking faces...' in job['logs']
    assert calls[0][0][0][:4] == [sys.executable, '-X', 'faulthandler', '-u']
    assert calls[0][1]['cwd'] == worker._REPO_ROOT
    state = worker.load_manual_job_state('manual_test', str(tmp_path))
    assert state['status'] == 'failed' and state['user_id'] == 'owner'


def test_child_publishes_progress_and_completed_result(tmp_path, monkeypatch):
    result = {'clips': [{'video_url': '/videos/manual_test/clip.mp4'}]}
    lines = '\n'.join([worker._STATE_PREFIX + json.dumps({'status': 'processing'}),
        '[manual_test] Rendering clip 1', worker._STATE_PREFIX + json.dumps({
            'status': 'completed', 'result': result, 'ready_files': {'0': 'clip.mp4'}})])
    _process(monkeypatch, lines)
    job = {'status': 'queued', 'logs': [], 'user_id': 'owner'}
    worker.run_manual_clips_job('manual_test', 'source.mp4', [], str(tmp_path), jobs_dict={'manual_test': job})
    assert job['status'] == 'completed' and job['result'] == result
    assert job['logs'] == ['Rendering clip 1']
    assert json.loads((tmp_path / 'manual_request.json').read_text())['src_video'] == os.path.abspath('source.mp4')


def test_successful_exit_without_completion_is_failed(tmp_path, monkeypatch):
    _process(monkeypatch, 'Incomplete render\n')
    job = {'status': 'queued', 'logs': []}
    worker.run_manual_clips_job('manual_test', 'source.mp4', [], str(tmp_path), jobs_dict={'manual_test': job})
    assert job['status'] == 'failed'
    assert 'did not produce' in job['error']


def test_restart_turns_orphaned_processing_into_visible_failure(tmp_path):
    (tmp_path / 'manual_status.json').write_text(json.dumps({
        'job_id': 'manual_test', 'status': 'processing', 'logs': [],
        'supervisor_pid': -1, 'user_id': 'owner'}))
    state = worker.load_manual_job_state('manual_test', str(tmp_path))
    assert state['status'] == 'failed'
    assert 'interrupted' in state['error']
    assert state['user_id'] == 'owner'


def test_api_worker_module_import_does_not_load_native_pipeline():
    script = f"import sys; sys.path.insert(0, {os.path.dirname(worker.__file__)!r}); import manual_clip_worker; assert 'manual_clip_pipeline' not in sys.modules; assert 'mediapipe' not in sys.modules; assert 'torch' not in sys.modules"
    subprocess.run([sys.executable, '-c', script], check=True)


def test_recovery_preserves_manual_job_owner_and_failure(tmp_path, monkeypatch):
    app = pytest.importorskip('app')
    job_id = 'manual_crash_recovery_test'
    directory = tmp_path / job_id
    directory.mkdir()
    (directory / 'manual_status.json').write_text(json.dumps({
        'job_id': job_id, 'status': 'failed', 'logs': ['native worker failed'],
        'error': '0xC0000005', 'user_id': 'owner'}))
    monkeypatch.setattr(app, 'OUTPUT_DIR', str(tmp_path))
    monkeypatch.setattr(app, 'jobs', {})
    app._recover_jobs_from_disk()
    assert app.jobs[job_id]['status'] == 'failed'
    assert app.jobs[job_id]['user_id'] == 'owner'
    assert app._job_view_from_disk(job_id)['error'] == '0xC0000005'


def test_api_health_and_job_status_survive_native_worker_failure(tmp_path, monkeypatch):
    import asyncio
    import httpx
    app = pytest.importorskip('app')
    job_id = 'manual_native_crash_test'
    _process(monkeypatch, 'Tracking faces\n', 3221225477)
    job = {'status': 'queued', 'logs': [], 'user_id': None}
    monkeypatch.setattr(app, 'jobs', {job_id: job})
    worker.run_manual_clips_job(job_id, 'source.mp4', [], str(tmp_path), jobs_dict=app.jobs)
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app), base_url='http://testserver') as client:
            health = await client.get('/health')
            status = await client.get('/api/status/' + job_id)
            assert health.status_code == 200
            assert status.status_code == 200
            assert status.json()['status'] == 'failed'
    asyncio.run(check())
