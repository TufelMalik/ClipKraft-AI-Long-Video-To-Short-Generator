import asyncio
import copy
import io
import json
import shutil
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient
from edit_project import EditError, new_project, validate, apply_suggestions
from edit_project_store import Store
from edit_projects import build_router
import composition as c
import edit_assets
import longform_render


def project():
    return new_project('fixture', 6000, 'source', {'segments': []})


def track(asset='a' * 32):
    return {'id': 'music', 'kind': 'music', 'asset_id': asset, 'asset_version': 1,
        'anchor': {'type': 'output', 'start_ms': 0, 'end_ms': 6000, 'base_revision': 0}}


def composed():
    return c.draft(project(), {**c.empty(), 'audio_tracks': [track()]})


def test_v1_no_rewrite_and_closed_schema():
    p = project()
    assert 'composition' not in validate(p) and p['schema_version'] == 1
    assert not c.active(p)
    assert not c.active(c.draft(p, c.empty()))
    for bad in ({'version': 2}, {'voice': {'cleanup': 'command'}}, {'audio_tracks': [dict(track(), gain_db=float('nan'))]},
                {'audio_tracks': [dict(track(), asset_in_ms=True)]}, {'visual_layers': [{'kind': 'unknown'}]}):
        with pytest.raises(EditError):
            c.draft(p, {**c.empty(), **bad})
    p['schema_version'] = 3
    with pytest.raises(EditError):
        validate(p)


def test_hash_changes_and_restore(tmp_path):
    p = composed()
    before = c.identity(p)
    for key, value in [('gain_db', -20), ('fade_in_ms', 200), ('loop', True), ('asset_version', 2)]:
        changed = copy.deepcopy(p)
        changed['composition']['audio_tracks'][0][key] = value
        assert c.identity(changed) != before
    store = Store(tmp_path)
    store.put('project', p['project_id'], p)
    updated = store.mutate(p['project_id'], 0, lambda p: c.draft(p, c.empty()))
    # Read the snapshot outside the transaction.
    old = store.get('history', p['project_id'] + ':0')
    restored = store.mutate(p['project_id'], 1, lambda _: old, restore=True)
    assert restored['composition'] == p['composition'] and updated['revision'] == 1


def test_anchor_lineage_and_output_review():
    p = composed()
    s = p['segments'][0]
    occurrence = dict(track(), id='occurrence', anchor={'type': 'occurrence', 'segment_id': s['id'], 'source_start_ms': 4000, 'source_end_ms': 5000})
    p['composition']['audio_tracks'].append(occurrence)
    p = validate(p)
    cut = {'id': 'cut', 'revision': 0, 'transcript_version': p['transcript_version'], 'segment_id': s['id'], 'start_ms': 1000, 'end_ms': 2000}
    after = apply_suggestions(p, [cut], 'smart_cuts')
    assert after['composition']['audio_tracks'][0]['needs_review']
    linked = after['composition']['audio_tracks'][1]
    assert not linked['needs_review'] and c.resolve(after, linked['anchor']) == (3000, 4000)
    cut.update(start_ms=4500, end_ms=5000)
    after = apply_suggestions(p, [cut], 'smart_cuts')
    assert after['composition']['audio_tracks'][1]['needs_review']


@pytest.fixture
def media(tmp_path, monkeypatch):
    if not shutil.which('ffmpeg'):
        pytest.skip('FFmpeg unavailable')
    monkeypatch.setenv('FFMPEG_ENCODER', 'x264')
    source = tmp_path / 'source.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=blue:s=320x180:r=20:d=6',
        '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=6',
        '-af', "volume=enable='between(t,2,4)':volume=0", '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(source)], check=True)
    music = tmp_path / 'music.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=1200:sample_rate=48000:duration=6', str(music)], check=True)
    store = Store(tmp_path / 'output')
    a = asyncio.run(edit_assets.ingest(store, UploadFile(filename='music.wav', file=io.BytesIO(music.read_bytes()))))
    return source, store, a


def test_asset_content_identity_and_reference_deletion(media):
    source, store, a = media
    p = c.draft(project(), {**c.empty(), 'audio_tracks': [track(a['id'])]})
    assert edit_assets.dependencies(store, p)[0]['checksum'] == a['checksum']
    store.put('history', 'test', p)
    with pytest.raises(EditError, match='referenced'):
        edit_assets.delete(store, a['id'])
    edit_assets.path(store, a).write_bytes(b'changed')
    with pytest.raises(EditError, match='checksum'):
        edit_assets.dependencies(store, p)
    with pytest.raises(EditError, match='unsupported'):
        asyncio.run(edit_assets.ingest(store, UploadFile(filename='bad.svg', file=io.BytesIO(b'<svg/>'))))


def test_real_audio_mix_duration_and_encoded_measurement(media, tmp_path):
    source, store, a = media
    p = c.draft(project(), {**c.empty(), 'audio_tracks': [dict(track(a['id']), duck_under_voice=True, fade_in_ms=300, fade_out_ms=300)]})
    one = asyncio.run(longform_render.render(p, source, {}, tmp_path, 'preview', asset_store=store))
    two = asyncio.run(longform_render.render(p, source, {}, tmp_path, 'export', asset_store=store))
    assert one['composition_hash'] == two['composition_hash']
    def decoded_hash(filename, stream):
        return subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(tmp_path / filename), '-map', stream, '-c:v', 'rawvideo', '-c:a', 'pcm_s16le', '-f', 'hash', '-'])
    for stream in ('0:v', '0:a'):
        assert decoded_hash(one['filename'], stream) == decoded_hash(two['filename'], stream)
    assert abs(one['media_duration_ms'] - 6000) < 100
    assert float(one['audio_measurement']['true_peak_dbtp']) < 0
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(tmp_path / two['filename']), '-f', 'null', '-'], check=True)
    # Frequency-isolate music; detector silence should release it audibly.
    import numpy as np
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(tmp_path / two['filename']), '-ac', '1', '-ar', '48000', '-f', 'f32le', '-'])
    samples = np.frombuffer(raw, dtype='<f4')
    def power(at):
        sample = samples[int(at * 48000):int((at + .4) * 48000)]
        spectrum = abs(np.fft.rfft(sample))
        bins = np.fft.rfftfreq(len(sample), 1 / 48000)
        return float(np.sum(spectrum[(bins > 1180) & (bins < 1220)] ** 2))
    assert power(3.4) > power(1) * 2
    assert not list(tmp_path.glob('temp_longform_*'))


def test_no_audio_and_short_asset(media, tmp_path):
    source, store, a = media
    silent = tmp_path / 'silent.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(source), '-an', '-c:v', 'copy', str(silent)], check=True)
    p = c.draft(project(), {**c.empty(), 'audio_tracks': [dict(track(a['id']), duck_under_voice=True)]})
    with pytest.raises(EditError, match='ducking_requires'):
        asyncio.run(longform_render.render(p, silent, {}, tmp_path, 'invalid', asset_store=store))
    p['composition']['audio_tracks'][0].update(duck_under_voice=False, asset_in_ms=2000)
    with pytest.raises(EditError, match='too_short'):
        edit_assets.dependencies(store, p)
    p['composition']['audio_tracks'][0]['loop'] = True
    out = asyncio.run(longform_render.render(p, silent, {}, tmp_path, 'silent', asset_store=store))
    assert out['audio_measurement']


def test_preview_approval_tampering_and_asset_tickets(media, tmp_path, monkeypatch):
    source, store, a = media
    for flag in ('LONGFORM_EDITING_ENABLED', 'LONGFORM_AUDIO_ENABLED', 'LONGFORM_EXPORT_ENABLED'):
        monkeypatch.setenv(flag, 'true')
    monkeypatch.setenv('LONGFORM_LOCAL_TOKEN', 'test')
    p = project()
    p['source']['fingerprint'] = longform_render.fingerprint(source)
    store.put('project', p['project_id'], p)
    store.put('transcript', p['project_id'], {})
    output = tmp_path / 'output'
    (output / p['job_id']).mkdir(parents=True)
    app = FastAPI()
    app.include_router(build_router(SimpleNamespace(OUTPUT_DIR=str(output), BILLING_ENABLED=False, _locate_source=lambda _: str(source))))
    def wait(client, response):
        assert response.status_code == 202, response.text
        for _ in range(300):
            op = client.get('/api/edit-operations/' + response.json()['operation_id']).json()
            if op['state'] not in ('queued', 'running'):
                assert op['state'] == 'completed', op
                return op['result']
            time.sleep(.02)
        pytest.fail('timed out')
    with TestClient(app, headers={'X-Longform-Token': 'test'}) as client:
        url = '/api/edit-projects/' + p['project_id'] + '/composition'
        value = c.draft(p, {**c.empty(), 'audio_tracks': [track(a['id'])]})['composition']
        result = wait(client, client.post(url + '/preview', json={'expected_revision': 0, 'composition': value}))
        body = {'expected_revision': 0, 'approved': True, 'preview_id': result['export_id'], 'composition_hash': result['composition_hash']}
        assert client.post(url + '/apply', json={**body, 'composition_hash': 'wrong'}).status_code == 400
        assert client.post(url + '/apply', json={**body, 'composition': value}).status_code == 400
        assert client.post(url + '/apply', json=body).status_code == 200
        assert client.post(url + '/apply', json=body).status_code == 409
        ticket = client.post('/api/edit-assets/' + a['id'] + '/access').json()
        client.headers.pop('X-Longform-Token')
        assert client.get(ticket['media']).status_code == 200
        assert client.get('/api/edit-assets/' + a['id'] + '/media').status_code == 401
