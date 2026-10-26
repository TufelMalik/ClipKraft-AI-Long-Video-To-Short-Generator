"""Manual ratio propagation and real encoded outputs (ASR stubbed)."""
import asyncio
import json
import shutil
from types import SimpleNamespace
import subprocess

import pytest


@pytest.mark.parametrize('output_format', ['vertical', 'square', 'horizontal'])
@pytest.mark.parametrize('json_request', [False, True])
def test_endpoint_passes_ratio_to_worker(tmp_path, monkeypatch, output_format, json_request):
    import app
    import manual_clip_worker
    from starlette.requests import Request
    source = tmp_path / 'source.mp4'
    source.touch()
    calls = []
    monkeypatch.setattr(app, 'OUTPUT_DIR', str(tmp_path))
    monkeypatch.setattr(app, 'jobs', {})
    monkeypatch.setattr(manual_clip_worker, 'run_manual_clips_job', lambda **kw: calls.append(kw))
    monkeypatch.setattr(app.threading, 'Thread', lambda target, **kw: SimpleNamespace(start=target))
    async def owner(_):
        return None
    monkeypatch.setattr(app, '_owner_id', owner)
    payload = dict(video_path=str(source), timestamps=[dict(start=0, end=1)], output_format=output_format)
    async def receive():
        return {'type': 'http.request', 'body': json.dumps(payload).encode()}
    request = Request({'type': 'http', 'headers': [(b'content-type', b'application/json' if json_request else b'multipart/form-data')]}, receive)
    asyncio.run(app.manual_clip_endpoint(request, file=None, video_path=str(source), url=None,
        timestamps=json.dumps(payload['timestamps']), speed=1.2, outro_path=None,
        output_format=output_format))
    assert calls[0]['output_format'] == output_format


@pytest.mark.parametrize('output_format,size,script_width', [
    ('square', (1080, 1080), 288), ('horizontal', (1920, 1080), 512),
])
def test_real_manual_ratio_with_portrait_outro(tmp_path, monkeypatch, output_format, size, script_width):
    p = pytest.importorskip('manual_clip_pipeline')
    if not shutil.which('ffmpeg'):
        pytest.skip('FFmpeg required')
    source, outro = tmp_path / 'source.mp4', tmp_path / 'outro.mp4'
    for path, resolution in [(source, '320x180'), (outro, '90x160')]:
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
            f'color=c=blue:s={resolution}:r=30:d=1', '-f', 'lavfi', '-i',
            'sine=frequency=440:duration=1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-shortest', str(path)], check=True)
    monkeypatch.setattr(p, 'transcribe_audio_words', lambda *a, **k: (
        [{'word': 'hello', 'start': 0, 'end': .5}], 'hello', 'en'))
    monkeypatch.setattr(p, 'compute_active_speaker_trajectory', lambda *a, **k: pytest.fail('Nonportrait must preserve the full frame'))
    clean, final = tmp_path / 'clean.mp4', tmp_path / 'final.mp4'
    p.process_single_clip(str(source), dict(start=0, end=1, hook='HELLO'), str(tmp_path),
        str(clean), str(final), outro_path=str(outro), output_format=output_format)
    for path in [clean, final]:
        data = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]))
        video = next(s for s in data['streams'] if s['codec_type'] == 'video')
        assert (video['width'], video['height']) == size
        assert video['sample_aspect_ratio'] == '1:1'
        assert any(s['codec_type'] == 'audio' for s in data['streams'])
        assert 1.7 < float(data['format']['duration']) < 2.1
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'null', '-'], check=True)
    assert f'PlayResX: {script_width}' in (tmp_path / 'subtitles_1.ass').read_text(encoding='utf-8-sig')


def test_default_subtitle_geometry_and_invalid_ratio(tmp_path):
    p = pytest.importorskip('manual_clip_pipeline')
    target = tmp_path / 'default.ass'
    p.build_ass_subtitles([], '', 1, str(target))
    assert 'PlayResX: 162' in target.read_text(encoding='utf-8-sig')
    assert p.manual_output_size('vertical') == (1080, 1920)
    with pytest.raises(ValueError):
        p.manual_output_size('unsupported')
