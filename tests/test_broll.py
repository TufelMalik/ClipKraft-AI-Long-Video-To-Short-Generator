"""Local metadata suggestions, immutable approval and encoded B-roll composition."""
import asyncio
import copy
import io
import subprocess
import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient
from PIL import Image

import broll_search
import composition as c
import edit_assets
import edit_llm
import longform_render
from edit_project import EditError, new_project, apply_suggestions
from edit_projects import build_router
from test_composition import media, project, track
from test_visual_explanations import visual


def placement(p, asset, **changes):
    return {'id': 'broll', 'kind': 'broll', 'asset_id': asset['id'], 'asset_version': 1,
        'anchor': {'type': 'occurrence', 'segment_id': p['segments'][0]['id'],
            'source_start_ms': 1000, 'source_end_ms': 5000}, **changes}


def ingest(store, file):
    return asyncio.run(edit_assets.ingest(store, UploadFile(filename=file.name, file=io.BytesIO(file.read_bytes()))))


@pytest.fixture
def assets(media, tmp_path):
    source, store, _ = media
    picture = tmp_path / 'plan.png'
    image = Image.new('RGB', (600, 100), 'red')
    image.paste('green', (300, 0, 600, 100))
    image.save(picture)
    still = ingest(store, picture)
    video = tmp_path / 'footage.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
        r'color=red:s=100x180:r=25:d=2,drawbox=x=0:y=0:w=100:h=180:c=green:t=fill:enable=gte(t\,1)',
        '-f', 'lavfi', '-i', 'sine=frequency=1200:duration=2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(video)], check=True)
    clip = ingest(store, video)
    edit_assets.metadata(store, still['id'], {'expected_version': 1, 'tags': ['planning', 'work'], 'description': 'Paper planning board', 'usage_notes': 'Test fixture'})
    return source, store, still, clip


def test_search_bilingual_grounded_ids_and_no_match(assets, monkeypatch):
    _, store, still, clip = assets
    assert broll_search.search(store, 'काम योजना')[0]['asset_id'] == still['id']
    assert broll_search.search(store, 'unrelated stars') == []
    t = {'segments': [{'words': [{'word': 'Plan the work.', 'start': 0, 'end': 4}]}]}
    p = new_project('fixture', 6000, 'source', t)
    body = {'segment_id': p['segments'][0]['id'], 'sentence_ids': ['s0'], 'use_llm': True}
    async def generate(data, schema, prompt):
        return {'choices': [{'asset_id': still['id'], 'sufficient': True, 'reason': 'Untrusted pixel claim'}]}
    monkeypatch.setattr(edit_llm, 'generate', generate)
    result = asyncio.run(broll_search.suggest(store, p, t, body))
    assert result['suggestions'][0]['metadata_only']
    assert result['suggestions'][0]['reason'].startswith('Metadata match:')
    assert 'pixel claim' not in str(result)
    async def invalid(*_):
        return {'choices': [{'asset_id': 'made-up', 'sufficient': True}]}
    monkeypatch.setattr(edit_llm, 'generate', invalid)
    with pytest.raises(EditError, match='invalid_model_output'):
        asyncio.run(broll_search.suggest(store, p, t, body))
    async def unavailable(*_):
        raise EditError('model_unavailable')
    monkeypatch.setattr(edit_llm, 'generate', unavailable)
    assert 'unavailable' in asyncio.run(broll_search.suggest(store, p, t, body))['note']
    body['sentence_ids'] = ['missing']
    with pytest.raises(EditError, match='invalid_sentence_selection'):
        asyncio.run(broll_search.suggest(store, p, t, body))


def test_broll_validation_dependencies_and_reconciliation(assets):
    _, store, still, clip = assets
    p = project()
    layer = placement(p, still)
    with pytest.raises(EditError, match='overlapping_broll_covers'):
        c.draft(p, {**c.empty(), 'visual_layers': [layer, dict(layer, id='other')]})
    for bad in [dict(layer, loop=True, freeze=True), dict(layer, crop_x=1.1), dict(layer, command='unsafe')]:
        with pytest.raises(EditError):
            c.draft(p, {**c.empty(), 'visual_layers': [bad]})
    full = c.draft(p, {**c.empty(), 'visual_layers': [placement(p, clip)]})
    with pytest.raises(EditError, match='asset_too_short'):
        edit_assets.dependencies(store, full)
    full['composition']['visual_layers'][0]['freeze'] = True
    assert edit_assets.dependencies(store, full)
    full['composition']['visual_layers'][0]['asset_id'] = next(a['id'] for a in store.all('asset') if a['type'] == 'audio')
    with pytest.raises(EditError, match='broll_video_or_image_required'):
        edit_assets.dependencies(store, full)
    linked = c.draft(p, {**c.empty(), 'visual_layers': [layer]})
    cut = {'id': 'cut', 'revision': 0, 'transcript_version': p['transcript_version'], 'segment_id': p['segments'][0]['id'], 'start_ms': 2000, 'end_ms': 3000}
    assert apply_suggestions(linked, [cut], 'smart_cuts')['composition']['visual_layers'][0]['needs_review']
    deps = edit_assets.dependencies(store, linked)
    before = c.identity(linked, deps)
    edit_assets.metadata(store, still['id'], {'expected_version': 2, 'tags': ['changed']})
    assert before != c.identity(linked, edit_assets.dependencies(store, linked))


def decode(file, *options):
    return subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(file), *options])


@pytest.mark.parametrize('kind', ['image', 'loop', 'freeze', 'inset', 'crop'])
def test_real_broll_narration_timing_parity(assets, tmp_path, kind):
    source, store, still, clip = assets
    p = project()
    layer = placement(p, still if kind in ('image', 'inset', 'crop') else clip)
    if kind in ('loop', 'freeze'):
        layer.update(asset_in_ms=1000, **{kind: True})
    if kind == 'inset':
        layer.update(mode='inset')
    if kind == 'crop':
        layer.update(fit='crop', crop_x=0., crop_y=1.)
    proposed = c.draft(p, {**c.empty(), 'visual_layers': [layer]})
    base = asyncio.run(longform_render.render(p, source, {}, tmp_path, 'base', asset_store=store))
    first = asyncio.run(longform_render.render(proposed, source, {}, tmp_path, 'preview', asset_store=store))
    second = asyncio.run(longform_render.render(proposed, source, {}, tmp_path, 'export', asset_store=store))
    audio = ['-t', '6', '-map', '0:a:0', '-f', 'hash', '-hash', 'sha256', '-']
    assert decode(tmp_path / base['filename'], *audio) == decode(tmp_path / first['filename'], *audio)
    streams = ['-map', '0:v:0', '-f', 'hash', '-hash', 'sha256', '-']
    assert decode(tmp_path / first['filename'], *streams) == decode(tmp_path / second['filename'], *streams)
    assert first['duration_ms'] == 6000 and first['composition_hash'] == second['composition_hash']
    def pixel(at, x=160, y=90):
        return decode(tmp_path / first['filename'], '-ss', str(at), '-frames:v', '1', '-vf', f'crop=2:2:{x}:{y}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-')
    assert pixel(.5) == pixel(5.5)
    assert pixel(.5) != (pixel(2, 250, 30) if kind == 'inset' else pixel(2))
    if kind == 'inset':
        assert pixel(.5) == pixel(2)  # center of main video remains visible
    if kind == 'crop':
        alternative = copy.deepcopy(proposed)
        alternative['composition']['visual_layers'][0]['crop_x'] = 1.
        opposite = asyncio.run(longform_render.render(alternative, source, {}, tmp_path, 'opposite', asset_store=store))
        other_pixel = decode(tmp_path / opposite['filename'], '-ss', '2', '-frames:v', '1', '-vf', 'crop=2:2:160:90', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-')
        assert pixel(2)[0] > pixel(2)[1] + 100
        assert other_pixel[1] > other_pixel[0] + 30
    if kind in ('loop', 'freeze'):
        # in-point begins in the green half; red frames must never recur.
        for at in (1.2, 2.5, 4.8):
            color = pixel(at)
            assert color[1] > color[0] + 30
    assert first['dependencies']


def test_combined_audio_visual_broll_and_silent_source(assets, tmp_path):
    source, store, still, _ = assets
    p = project()
    composed = c.draft(p, {**c.empty(), 'audio_tracks': [track(next(a['id'] for a in store.all('asset') if a['type'] == 'audio'))],
        'visual_layers': [visual(p), placement(p, still)]})
    rendered = asyncio.run(longform_render.render(composed, source, {}, tmp_path, 'combined', asset_store=store))
    assert rendered['template_dependencies'] and rendered['audio_measurement']
    silent = tmp_path / 'silent.mp4'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(source), '-an', '-c:v', 'copy', str(silent)], check=True)
    p = c.draft(p, {**c.empty(), 'visual_layers': [placement(p, still)]})
    rendered = asyncio.run(longform_render.render(p, silent, {}, tmp_path, 'silent', asset_store=store))
    probe = asyncio.run(longform_render.probe(tmp_path / rendered['filename']))
    assert not any(s['codec_type'] == 'audio' for s in probe['streams'])


def test_api_broll_approval_metadata_stale_and_independent_flag(assets, monkeypatch):
    source, store, still, _ = assets
    for flag in ('LONGFORM_EDITING_ENABLED', 'LONGFORM_BROLL_ENABLED', 'LONGFORM_EXPORT_ENABLED'):
        monkeypatch.setenv(flag, 'true')
    monkeypatch.setenv('LONGFORM_VISUALS_ENABLED', 'false')
    monkeypatch.setenv('LONGFORM_AUDIO_ENABLED', 'false')
    monkeypatch.delenv('LONGFORM_LOCAL_TOKEN', raising=False)
    t = {'segments': [{'words': [{'word': 'Plan the work.', 'start': 1, 'end': 5}]}]}
    p = new_project('fixture', 6000, longform_render.fingerprint(source), t)
    store.put('project', p['project_id'], p)
    store.put('transcript', p['project_id'], t)
    app = FastAPI()
    app.include_router(build_router(SimpleNamespace(OUTPUT_DIR=str(store.root.parent.parent / store.root.name), BILLING_ENABLED=False, _locate_source=lambda _: str(source))))
    # Store root is output/.longform/output; use the exact original output argument.
    def wait(client, response):
        assert response.status_code == 202, response.text
        for _ in range(500):
            op = client.get('/api/edit-operations/' + response.json()['operation_id']).json()
            if op['state'] not in ('queued', 'running'):
                assert op['state'] == 'completed', op
                return op['result']
            time.sleep(.02)
        pytest.fail('operation timeout')
    with TestClient(app) as client:
        path = '/api/edit-projects/' + p['project_id']
        assert client.get('/api/edit-projects/capabilities').json()['broll']
        analysis = wait(client, client.post(path + '/broll/analyze', json={'expected_revision': 0, 'segment_id': p['segments'][0]['id'], 'sentence_ids': ['s0']}))
        proposal = analysis['suggestions'][0]
        layer = placement(p, still, proposal_id=proposal['id'])
        value = c.draft(p, {**c.empty(), 'visual_layers': [layer]})['composition']
        preview = wait(client, client.post(path + '/composition/preview', json={'expected_revision': 0, 'composition': value}))
        approval = {'expected_revision': 0, 'approved': True, 'preview_id': preview['export_id'], 'composition_hash': preview['composition_hash']}
        assert client.post(path + '/composition/apply', json={**approval, 'composition_hash': 'wrong'}).status_code == 400
        edit_assets.metadata(store, still['id'], {'expected_version': 2, 'description': 'Updated metadata'})
        assert client.post(path + '/composition/apply', json=approval).status_code == 400
        value['visual_layers'][0]['proposal_id'] = None
        preview = wait(client, client.post(path + '/composition/preview', json={'expected_revision': 0, 'composition': value}))
        approval.update(preview_id=preview['export_id'], composition_hash=preview['composition_hash'])
        assert client.post(path + '/composition/apply', json=approval).status_code == 200
        assert client.delete('/api/edit-assets/' + still['id']).status_code == 400
        monkeypatch.setenv('LONGFORM_BROLL_ENABLED', 'false')
        assert client.post(path + '/broll/analyze', json={'expected_revision': 1}).status_code == 404
