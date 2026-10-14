import json

import pytest
from fastapi.testclient import TestClient

import app


@pytest.mark.parametrize('source', ['url', 'file'])
@pytest.mark.parametrize('channel', [None, 'tech'])
@pytest.mark.parametrize('confirmation', [None, False])
def test_processing_needs_no_content_permission(tmp_path, monkeypatch, source, channel, confirmation):
    monkeypatch.setattr(app, 'BILLING_ENABLED', False)
    monkeypatch.setattr(app, 'OUTPUT_DIR', str(tmp_path/'output'))
    monkeypatch.setattr(app, 'UPLOAD_DIR', str(tmp_path/'uploads'))
    (tmp_path/'uploads').mkdir()
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    monkeypatch.setenv('CHANNEL_SAFETY_REQUIRED', '1')  # obsolete setting must not block
    profiles = tmp_path/'channels.json'
    profiles.write_text(json.dumps({'channels': [{'id': 'tech', 'niche': 'tech'}]}))
    monkeypatch.setenv('CHANNEL_PROFILES_PATH', str(profiles))
    monkeypatch.setattr(app, '_media_duration_seconds', lambda path: 60.)
    async def skip(*args):
        return None
    monkeypatch.setattr(app, '_validate_source_url', skip)
    monkeypatch.setattr(app, '_quality_gate', skip)
    fields = {'output_format': 'vertical'}
    if channel:
        fields['channel_id'] = channel
    if confirmation is not None:
        fields['acknowledged'] = confirmation if source == 'url' else 'false'
    client = TestClient(app.app)
    headers = {'X-Gemini-Key': 'test-key'}
    if source == 'url':
        response = client.post('/api/process', json={'url': 'https://example.com/video.mp4', **fields}, headers=headers)
    else:
        response = client.post('/api/process', data=fields,
            files={'file': ('video.mp4', b'test-video', 'video/mp4')}, headers=headers)
    assert response.status_code == 200, response.text
    job = app.jobs.pop(response.json()['job_id'])
    assert 'attestation' not in job
    assert ('-u' if source == 'url' else '-i') in job['cmd']
    assert job['cmd'][-2:] == ['--format', 'vertical']
    if channel:
        assert job['env']['CHANNEL_ID'] == 'tech'


def test_channel_profile_updates_accept_creators_without_permissions(tmp_path,monkeypatch):
    monkeypatch.setattr(app,'BILLING_ENABLED',False)
    monkeypatch.setenv('CHANNEL_PROFILES_PATH',str(tmp_path/'channels.json'))
    client = TestClient(app.app)
    config = {'channels':[{'id':'tech','niche':'tech','creators':[]}]}
    assert client.put('/api/channel-profiles',json=config).status_code==200
    assert client.get('/api/channel-profiles').json()['channels'][0]['creators']==[]
    config['channels'][0]['creators'] = [{'id':'creator-a'}]
    assert client.put('/api/channel-profiles',json=config).status_code==200
    config['channels'][0]['creators'] = [{'id':''}]
    assert client.put('/api/channel-profiles',json=config).status_code==400


def test_pending_or_blocked_export_is_not_delivered_even_if_intermediate_exists(tmp_path):
    (tmp_path/'source_clip_1.mp4').write_bytes(b'video')
    for status in ['pending','failed']:
        kept,missing = app._clips_actually_rendered('job',str(tmp_path),'source',[{'export_status':status}])
        assert kept==[] and missing==1


def test_surviving_clip_keeps_its_metadata_index(tmp_path):
    (tmp_path/'source_clip_2.mp4').write_bytes(b'video')
    clips = [{'export_status':'failed'},{'export_status':'ready'}]
    kept,_ = app._clips_actually_rendered('job',str(tmp_path),'source',clips)
    assert kept[0]['metadata_index']==1
    assert app._memory_clip({'result':{'clips':kept}},1) is kept[0]


@pytest.fixture
def broll_client(tmp_path,monkeypatch):
    monkeypatch.setattr(app,'OUTPUT_DIR',str(tmp_path))
    root = tmp_path/'job'
    root.mkdir()
    metadata = root/'source_metadata.json'
    metadata.write_text(json.dumps({'shorts':[{'start':0,'end':10}]}))
    monkeypatch.setitem(app.jobs,'job',{'result':{'clips':[{'start':0,'end':10}]}})
    async def allow(*args):
        pass
    monkeypatch.setattr(app,'_ensure_job_files',allow)
    monkeypatch.setattr(app,'_assert_job_owner',allow)
    return TestClient(app.app),metadata


def test_broll_notes_are_saved_with_export_timestamps(broll_client):
    client,metadata = broll_client
    points = [{'start':2,'end':4.5,'label':'Show the chart'}]
    response = client.post('/api/clip/broll',json={'job_id':'job','clip_index':0,'points':points})
    assert response.status_code==200
    assert json.loads(metadata.read_text())['shorts'][0]['broll_points']==points


def test_invalid_broll_notes_do_not_change_metadata(broll_client):
    client,metadata = broll_client
    before = metadata.read_text()
    response = client.post('/api/clip/broll',json={'job_id':'job','clip_index':0,
        'points':[{'start':8,'end':12,'label':'outside'}]})
    assert response.status_code==400 and metadata.read_text()==before
