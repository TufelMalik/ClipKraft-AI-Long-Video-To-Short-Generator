"""Shot-local framing and the actual FFmpeg layout used by manual clips."""
import io
import json
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

p = pytest.importorskip("manual_clip_pipeline")
scene_detection = pytest.importorskip("scene_detection")
from scenedetect import FrameTimecode
import reframe_v2


def _metadata(monkeypatch, width=2560, height=1440, frames=12):
    values = {p.cv2.CAP_PROP_FPS: 30.0, p.cv2.CAP_PROP_FRAME_WIDTH: width,
              p.cv2.CAP_PROP_FRAME_HEIGHT: height, p.cv2.CAP_PROP_FRAME_COUNT: frames}
    cap = SimpleNamespace(isOpened=lambda: True, get=lambda key: values[key], release=lambda: None)
    monkeypatch.setattr(p.cv2, "VideoCapture", lambda _: cap)
    monkeypatch.setattr(scene_detection, "detect_scenes", lambda _: (
        [(FrameTimecode(a, 30.0), FrameTimecode(b, 30.0)) for a, b in [(0, 4), (4, 8), (8, 12)]], 30.0))
    monkeypatch.setattr(p.split_layout, "detect_split_scenes", lambda *args, **kwargs: {})


def test_tracking_failure_falls_back_within_each_shot(monkeypatch):
    _metadata(monkeypatch)
    monkeypatch.setitem(sys.modules, "main", SimpleNamespace())
    sampled = []

    def speakers(path, w, h, log_fn, start_frame, end_frame):
        sampled.append((start_frame, end_frame))
        cx = {0: 1100, 4: 1250, 8: 1900}[start_frame]
        return [{'cx': cx, 'box': [cx - 100, 100, 200, 200]}]

    monkeypatch.setattr(p, "detect_candidate_speakers", speakers)
    xs, fps, w, h, cw, ch, switches, splits = p.compute_active_speaker_trajectory("clip", lambda _: None)
    assert sampled == [(0, 4), (4, 8), (8, 12)]
    assert xs == [695] * 4 + [845] * 4 + [1495] * 4
    assert cw == 810 and ch == 1440 and switches == [4, 8]
    assert not splits


def test_partial_tracking_is_rejected_instead_of_repeating_old_shot(monkeypatch):
    _metadata(monkeypatch)
    monkeypatch.setitem(sys.modules, "main", SimpleNamespace(
        SmoothedCameraman=lambda *a, **k: None, SpeakerTracker=lambda **k: None))
    monkeypatch.setattr(reframe_v2, "_analyze_trajectory", lambda *a: [300] * 4)
    monkeypatch.setattr(p, "_shot_fallback", lambda *a: [800] * 12)
    assert p.compute_active_speaker_trajectory("clip", lambda _: None)[0] == [800] * 12


def test_tall_video_has_real_portrait_crop_dimensions(monkeypatch):
    _metadata(monkeypatch, width=720, height=1920)
    monkeypatch.setitem(sys.modules, "main", SimpleNamespace())
    monkeypatch.setattr(p, "detect_candidate_speakers", lambda *a, **k: [])
    result = p.compute_active_speaker_trajectory("clip", lambda _: None)
    assert result[4:6] == (720, 1280)
    for w, h, x, y in p.compute_crop_boxes(result[0], [], 720, 1280, 720, 1920):
        assert w / h == 9 / 16
        assert 0 <= x <= 720 - w and 0 <= y <= 1920 - h


def test_invalid_video_fails_before_render(monkeypatch):
    _metadata(monkeypatch, frames=0)
    with pytest.raises(ValueError, match="invalid"):
        p.compute_active_speaker_trajectory("clip")


def test_split_is_local_and_focus_keeps_audio_attribution(monkeypatch):
    _metadata(monkeypatch)
    monkeypatch.setitem(sys.modules, "main", SimpleNamespace(
        SmoothedCameraman=lambda *a, **k: None, SpeakerTracker=lambda **k: None))
    monkeypatch.setattr(reframe_v2, "_analyze_trajectory", lambda *a: [800] * 12)
    pair = ((600, 300, 200, 200), (1900, 300, 200, 200))
    monkeypatch.setattr(p.split_layout, "detect_split_scenes", lambda *a, **k: {2: pair})
    monkeypatch.setattr(p.active_speaker, "verdicts_for_scene", lambda *a: [1])
    result = p.compute_active_speaker_trajectory("clip", lambda _: None)
    assert result[0][:8] == [800] * 8
    assert result[0][8:] == [1495] * 4
    assert result[7] == {(8, 12): pair}
    graph = p.manual_reframe_filtergraph((810, 1440, 800, 0), "cmd.txt", 1.2,
                                        2560, 1440, 30, 12, result[7])
    assert "gte(t,0.208333333)*lt(t,0.319444444)" in graph
    assert "sendcmd" in graph and "vstack" in graph and "atempo=1.2" in graph


def test_cut_without_detection_does_not_frame_previous_shot():
    m = pytest.importorskip("main")
    cam = m.SmoothedCameraman(1080, 1920, 2560, 1440)
    cam.begin_scene()
    cam.update_target([1800, 200, 200, 200])
    cam.begin_scene()
    x1, _, x2, _ = cam.get_crop_box()
    assert (x1 + x2) / 2 == 1280
    cam.update_target([1000, 200, 200, 200])
    x1, _, x2, _ = cam.get_crop_box()
    assert (x1 + x2) / 2 == 1100


def test_decoder_failure_is_not_accepted_as_partial_trajectory(monkeypatch):
    monkeypatch.setitem(sys.modules, "main", SimpleNamespace())
    proc = SimpleNamespace(stdout=io.BytesIO(), poll=lambda: 1, wait=lambda: 1)
    monkeypatch.setattr(reframe_v2.subprocess, "Popen", lambda *a, **k: proc)
    with pytest.raises(RuntimeError, match="decoder failed"):
        reframe_v2._analyze_trajectory("clip", [(0, 10)], ['TRACK'], 30, 640, 360, None, None)


@pytest.mark.parametrize("layout", ["focus", "split"])
@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg is required")
def test_real_manual_render_keeps_captions_audio_speed_and_outro(tmp_path, monkeypatch, layout):
    source = tmp_path / "source.mp4"
    outro = tmp_path / "outro.mp4"
    for path, size, duration in [(source, '640x360', '1.5'), (outro, '1080x1920', '0.5')]:
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i',
                        f'color=c=red:s={size}:r=24:d={duration}', '-f', 'lavfi', '-i',
                        f'sine=frequency=440:duration={duration}', '-c:v', 'libx264',
                        '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                        '-shortest', str(path)], check=True)
    monkeypatch.setattr(p, 'transcribe_audio_words', lambda *a, **k: (
        [{'word': 'Framing', 'start': 0.0, 'end': 0.6},
         {'word': 'works', 'start': 0.6, 'end': 1.4}], 'Framing works', 'en'))
    pair = ((150, 100, 80, 80), (490, 100, 80, 80))
    monkeypatch.setattr(p, 'compute_active_speaker_trajectory', lambda *a, **k: (
        [218] * 36, 24.0, 640, 360, 202, 360, [12, 24], {(12, 24): pair}))
    clean, captioned = tmp_path / 'clean.mp4', tmp_path / 'captioned.mp4'
    result = p.process_single_clip(str(source), {'id': '1', 'start': 0, 'end': 1.5,
        'hook': 'FRAMING CHECK', 'layout': layout}, str(tmp_path), str(clean), str(captioned),
        speed=1.2, outro_path=str(outro), log_fn=lambda _: None)
    assert result[1:] == ('Framing works', 'en')
    for path in [clean, captioned]:
        probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
                           '-show_format', '-of', 'json', str(path)], text=True))
        video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        assert (video['width'], video['height']) == (1080, 1920)
        assert any(s['codec_type'] == 'audio' for s in probe['streams'])
        assert abs(float(probe['format']['duration']) - 1.75) < 0.15
    ass = (tmp_path / 'subtitles_1.ass').read_text(encoding='utf-8-sig')
    assert 'FRAMING CHECK' in ass and 'FRAMING' in ass and 'WORKS' in ass
    assert clean.read_bytes() != captioned.read_bytes()


@pytest.mark.parametrize("layout", ["focus", "split"])
@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg is required")
def test_crop_and_split_change_on_the_exact_cut_frame(tmp_path, layout):
    source, rendered = tmp_path / 'two_colours.mp4', tmp_path / 'rendered.mp4'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i',
        'color=red:s=640x360:r=24:d=1.5,drawbox=x=320:y=0:w=320:h=360:color=blue:t=fill',
        '-f', 'lavfi', '-i', 'sine=duration=1.5', '-c:v', 'libx264', '-preset',
        'ultrafast', '-c:a', 'aac', '-shortest', str(source)], check=True)
    # A focus cut moves from the red left half to the blue right half.
    xs = [0] * 12 + [438] * 12 + [0] * 12
    boxes = p.compute_crop_boxes(xs, [], 202, 360, 640, 360)
    commands = tmp_path / 'commands.txt'
    p.generate_sendcmd_boxes(boxes, 24, str(commands), speed=1.2)
    pair = ((150, 150, 80, 80), (490, 150, 80, 80))
    graph = p.manual_reframe_filtergraph(boxes[0], str(commands), 1.2, 640, 360,
                                        24, 36, {(12, 24): pair} if layout == 'split' else None)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(source),
        '-filter_complex', graph, '-map', '[v]', '-map', '[a]', '-fps_mode', 'passthrough',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', str(rendered)], check=True)
    cap = p.cv2.VideoCapture(str(rendered))
    frames = []
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frames.append((frame[400, 540].tolist(), frame[1500, 540].tolist()))
    finally:
        cap.release()
    assert len(frames) == 36
    red = lambda c: c[2] > 200 and c[0] < 40
    blue = lambda c: c[0] > 200 and c[2] < 40
    assert all(red(c) for c in frames[11])
    assert all(red(c) for c in frames[24])
    for frame in [frames[12], frames[23]]:
        assert blue(frame[1])
        assert (red if layout == 'split' else blue)(frame[0])
