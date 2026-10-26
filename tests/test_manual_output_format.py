"""Manual ratio propagation and real encoded outputs (ASR stubbed)."""
import asyncio
import json
import shutil
from types import SimpleNamespace
import subprocess

import pytest


@pytest.mark.parametrize('output_format', [None, 'vertical', 'square', 'horizontal', 'invalid'])
@pytest.mark.parametrize('json_request', [False, True])
def test_endpoint_passes_ratio_to_worker(tmp_path, monkeypatch, output_format, json_request):
    import app
    import manual_clip_worker
    import httpx
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
    payload = dict(video_path=str(source), timestamps=[dict(start=0, end=1)])
    if output_format is not None:
        payload['output_format'] = output_format
    async def send():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app), base_url='http://testserver') as client:
            if json_request:
                return await client.post('/api/manual-clip/process', json=payload)
            fields = {**payload, 'timestamps': json.dumps(payload['timestamps'])}
            return await client.post('/api/manual-clip/process', files={k: (None, v) for k, v in fields.items()})
    response = asyncio.run(send())
    if output_format == 'invalid':
        assert response.status_code == 400
        assert not calls
    else:
        assert response.status_code == 200, response.text
        assert calls[0]['output_format'] == (output_format or 'vertical')


@pytest.mark.parametrize('output_format,size,script_width', [
    ('vertical', (1080, 1920), 162),
    ('square', (1080, 1080), 288), ('horizontal', (1920, 1080), 512),
])
@pytest.mark.parametrize('with_outro', [False, True])
def test_real_manual_ratio_with_portrait_outro(tmp_path, monkeypatch, output_format, size, script_width, with_outro):
    p = pytest.importorskip('manual_clip_pipeline')
    if not shutil.which('ffmpeg'):
        pytest.skip('FFmpeg required')
    source, outro = tmp_path / 'source.mp4', tmp_path / 'outro.mp4'
    for path, resolution in [(source, '320x180'), (outro, '1080x1920')]:
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
            f'color=c=blue:s={resolution}:r=30:d=1', '-f', 'lavfi', '-i',
            'sine=frequency=440:duration=1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-shortest', str(path)], check=True)
    monkeypatch.setattr(p, 'transcribe_audio_words', lambda *a, **k: (
        [{'word': 'hello', 'start': 0, 'end': .5}], 'hello', 'en'))
    if output_format == 'vertical':
        monkeypatch.setattr(p, 'compute_active_speaker_trajectory', lambda *a, **k:
            ([110] * 30, 30, 320, 180, 100, 180, [], None))
    else:
        monkeypatch.setattr(p, 'compute_active_speaker_trajectory', lambda *a, **k: pytest.fail('Nonportrait must preserve the full frame'))
    clean, final = tmp_path / 'clean.mp4', tmp_path / 'final.mp4'
    p.process_single_clip(str(source), dict(start=0, end=1, hook='HELLO'), str(tmp_path),
        str(clean), str(final), outro_path=str(outro) if with_outro else '', output_format=output_format)
    for path in [clean, final]:
        data = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]))
        video = next(s for s in data['streams'] if s['codec_type'] == 'video')
        assert (video['width'], video['height']) == size
        assert video['sample_aspect_ratio'] == '1:1'
        assert any(s['codec_type'] == 'audio' for s in data['streams'])
        assert abs(float(data['format']['duration']) - (1 / 1.2 + int(with_outro))) < .2
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'null', '-'], check=True)
    assert f'PlayResX: {script_width}' in (tmp_path / 'subtitles_1.ass').read_text(encoding='utf-8-sig')
    # Actual decoded pixels must change when the hook/captions are burned in.
    frame_args = ['ffmpeg', '-v', 'error', '-ss', '0.2', '-i']
    frame_tail = ['-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    assert subprocess.check_output(frame_args + [str(clean)] + frame_tail) != subprocess.check_output(frame_args + [str(final)] + frame_tail)


def test_default_subtitle_geometry_and_invalid_ratio(tmp_path):
    p = pytest.importorskip('manual_clip_pipeline')
    target = tmp_path / 'default.ass'
    p.build_ass_subtitles([], '', 1, str(target))
    assert 'PlayResX: 162' in target.read_text(encoding='utf-8-sig')
    assert p.manual_output_size('vertical') == (1080, 1920)
    with pytest.raises(ValueError):
        p.manual_output_size('unsupported')
