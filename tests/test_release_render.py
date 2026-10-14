"""Real FFmpeg smoke checks; skip only when a test FFmpeg is unavailable."""
import shutil
import subprocess
from pathlib import Path

import pytest

from ffmpeg_utils import escape_filter_value
from punch_in import sendcmd_lines, zoom_filter
from subject_framing import BodyCamera, lock_scene_lens


def ffmpeg_binary():
    binary = shutil.which('ffmpeg')
    if binary:
        return binary
    imageio = pytest.importorskip('imageio_ffmpeg')
    return imageio.get_ffmpeg_exe()


def test_dynamic_body_crop_actually_encodes(tmp_path):
    import cv2
    binary = ffmpeg_binary()
    camera = BodyCamera(640, 360, 9/16)
    camera.update((250, 90, 50, 50), (220, 80, 350, 270))
    boxes = [camera.box() for _ in range(10)]
    camera.update((320, 100, 65, 65), (290, 90, 450, 330))
    boxes += [camera.box() for _ in range(20)]
    boxes = lock_scene_lens(boxes, 640, 360, 9/16)
    path = tmp_path / 'commands.txt'
    path.write_text('\n'.join(sendcmd_lines(boxes, 30)))
    w, h, x, y = boxes[0]
    graph = (f"sendcmd=f='{escape_filter_value(str(path))}',"
             f"crop@c=w={w}:h={h}:x={x}:y={y},scale=1080:1920,setsar=1")
    output = str(tmp_path / 'render.mp4')
    result = subprocess.run([binary, '-v', 'error', '-y', '-f', 'lavfi',
        '-i', 'testsrc2=size=640x360:rate=30:duration=1', '-vf', graph,
        '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', output],
        capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    assert b'Error' not in result.stderr and b'Invalid' not in result.stderr
    video = cv2.VideoCapture(output)
    try:
        assert int(video.get(cv2.CAP_PROP_FRAME_WIDTH)) == 1080
        assert int(video.get(cv2.CAP_PROP_FRAME_HEIGHT)) == 1920
        assert int(video.get(cv2.CAP_PROP_FRAME_COUNT)) == 30
    finally:
        video.release()


def test_keyword_zoom_retains_every_frame(tmp_path):
    import cv2
    binary = ffmpeg_binary()
    output = str(tmp_path/'zoom.mp4')
    result = subprocess.run([binary,'-v','error','-y','-f','lavfi','-i',
        'testsrc2=size=640x360:rate=30:duration=2','-vf',
        zoom_filter([.3,1.],0,2,160,284,30),'-c:v','libx264','-preset','ultrafast',output],
        capture_output=True,timeout=30)
    assert result.returncode==0,result.stderr.decode(errors='replace')
    video = cv2.VideoCapture(output)
    try:
        assert int(video.get(cv2.CAP_PROP_FRAME_COUNT))==60
    finally:
        video.release()


@pytest.mark.parametrize('relative_path', [False, True])
@pytest.mark.parametrize('branding', [False, True])
def test_editorial_assembly_preserves_caption_timeline(tmp_path, monkeypatch, relative_path, branding):
    from editorial import assemble, media_info
    binary = ffmpeg_binary()
    monkeypatch.setenv('FFMPEG_BINARY',binary)
    # Jobs pass relative paths under output/. Include quoting and Unicode too.
    monkeypatch.chdir(tmp_path)
    job_dir = tmp_path / 'output' / "job's café"
    job_dir.mkdir(parents=True)
    source_path = job_dir / 'source.mp4'
    source = str(source_path.relative_to(tmp_path) if relative_path else source_path)
    if relative_path:
        # Python 3.11 (the Docker runtime) preserves a relative dir here;
        # Python 3.12 makes it absolute, which hid the production regression.
        from contextlib import contextmanager
        import editorial
        temporary_directory = editorial.tempfile.TemporaryDirectory

        @contextmanager
        def relative_temporary_directory(*args, **kwargs):
            with temporary_directory(*args, **kwargs) as work:
                yield str(Path(work).relative_to(tmp_path))

        monkeypatch.setattr(editorial.tempfile, 'TemporaryDirectory', relative_temporary_directory)
    subprocess.run([binary,'-v','error','-y','-f','lavfi','-i',
        'testsrc2=size=160x284:rate=24:duration=3','-f','lavfi','-i',
        'sine=frequency=440:duration=3','-c:v','libx264','-preset','ultrafast',
        '-c:a','aac','-shortest',source],check=True,capture_output=True,timeout=30)
    transcript = {'language':'en','segments':[{'start':10,'end':13,
        'words':[{'word':' hello','start':10.2,'end':10.6}]}]}
    import json
    with open(source+'.speakers.json','w') as f:
        json.dump([{'start':0,'end':1,'speaker':0},{'start':1,'end':3,'speaker':1}],f)
    output, words, duration, timeline = assemble(source,
        {'branding':branding,'speaker':'Ada','topic':'A useful idea','niche':'tech',
         'sound_design':True,'color_grade':True},
        transcript,10,13)
    intro_seconds = 2.5 if branding else 0.
    assert abs(duration-(3+2*intro_seconds)) < .1
    assert words['segments'][0]['words'][0]['start'] == round(.2+intro_seconds, 3)
    assert timeline['intro_seconds'] == intro_seconds
    assert abs(media_info(output)['duration']-duration) < .15


def test_animated_hook_ends_with_source_and_fades(tmp_path,monkeypatch):
    import cv2
    import hooks
    from PIL import Image
    binary = ffmpeg_binary()
    source = str(tmp_path/'source.mp4')
    output = str(tmp_path/'hook.mp4')
    subprocess.run([binary,'-v','error','-y','-f','lavfi','-i',
        'color=blue:size=160x284:rate=30:duration=2','-c:v','libx264','-preset','ultrafast',source],
        check=True,capture_output=True,timeout=30)
    png = str(tmp_path/'overlay.png')
    Image.new('RGBA',(80,30),'red').save(png)
    monkeypatch.setattr(hooks,'create_hook_image',lambda *a,**k:(png,80,30))
    monkeypatch.setattr(hooks.subprocess,'check_output',lambda *a,**k:b'160x284')
    original_run = subprocess.run
    def run(command,**kwargs):
        return original_run([binary if command[0]=='ffmpeg' else command[0],*command[1:]],**kwargs)
    monkeypatch.setattr(hooks.subprocess,'run',run)
    hooks.add_hook_to_video(source,'A useful hook',output,animated=True,duration=1.2,start_seconds=.2)
    video = cv2.VideoCapture(output)
    try:
        assert int(video.get(cv2.CAP_PROP_FRAME_COUNT))==60
        pixels = []
        for at in [0.,.8,1.6]:
            video.set(cv2.CAP_PROP_POS_MSEC,at*1000)
            ok,frame = video.read()
            assert ok
            pixels.append(frame[60,80].tolist())
        assert pixels[0][0]>200 and pixels[1][2]>200 and pixels[2][0]>200
    finally:
        video.release()
