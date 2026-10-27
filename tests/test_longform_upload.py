"""Exercise full-video ingest with the real application host contract."""
import asyncio
import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
import longform_render
from edit_projects import build_router


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg required')
def test_upload_creates_real_source_transcript_and_preview(tmp_path, monkeypatch):
    import app as host
    uploads, output = tmp_path / 'uploads', tmp_path / 'output'
    uploads.mkdir()
    output.mkdir()
    source = tmp_path / 'clip.mp4'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
        'color=blue:s=160x90:r=20:d=1', '-f', 'lavfi', '-i', 'sine=duration=1',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(source)], check=True)
    monkeypatch.setattr(host, 'UPLOAD_DIR', str(uploads))
    monkeypatch.setattr(host, 'OUTPUT_DIR', str(output))
    monkeypatch.setattr(host, 'jobs', {})
    monkeypatch.setattr(host, 'BILLING_ENABLED', False)
    monkeypatch.setenv('LONGFORM_EDITING_ENABLED', 'true')
    monkeypatch.setenv('LONGFORM_EXPORT_ENABLED', 'true')
    monkeypatch.delenv('LONGFORM_LOCAL_TOKEN', raising=False)
    command = longform_render.command
    transcript = {'language': 'en', 'segments': [{'text': 'Plan carefully.', 'start': 0, 'end': 1,
        'words': [{'word': 'Plan carefully.', 'start': 0, 'end': 1}]}]}
    calls = []
    async def inference_stub(args, *rest, **kw):
        if any(str(arg).endswith('longform_transcribe.py') for arg in args):
            calls.append(args)
            Path(args[-1]).write_text(json.dumps(transcript), encoding='utf-8')
            return b''
        return await command(args, *rest, **kw)
    monkeypatch.setattr(longform_render, 'command', inference_stub)
    api = FastAPI()
    api.include_router(build_router(host))
    def wait(client, response):
        assert response.status_code == 202, response.text
        for _ in range(300):
            op = client.get('/api/edit-operations/' + response.json()['operation_id']).json()
            if op['state'] not in ('queued', 'running'):
                assert op['state'] == 'completed', op
                return op['result']
            time.sleep(.02)
        pytest.fail('upload operation timed out')
    with TestClient(api) as client:
        project = wait(client, client.post('/api/edit-sources', files={'file': ('clip.mp4', source.read_bytes(), 'video/mp4')}))
        assert calls and host._locate_source(project['job_id'])
        loaded = client.get('/api/edit-projects/' + project['project_id']).json()
        assert loaded['source_available'] and loaded['source_sentences'][0]['text'] == 'Plan carefully.'
        preview = wait(client, client.post('/api/edit-projects/' + project['project_id'] + '/preview', json={'expected_revision': 0}))
        assert preview['duration_ms'] == 1000
        ticket = client.post('/api/edit-exports/' + preview['export_id'] + '/access').json()
        assert client.get(ticket['video']).status_code == 200
