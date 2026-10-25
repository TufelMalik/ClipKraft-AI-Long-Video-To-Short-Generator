import os
import sys
import json
import re
import math
import shutil
import time
import subprocess
import cv2
import numpy as np

# MediaPipe Tasks Vision for Face Tracking
try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    HAS_MEDIAPIPE = True
except Exception:
    HAS_MEDIAPIPE = False

# YOLO Fallback
try:
    from ultralytics import YOLO
    HAS_YOLO = True
except Exception:
    HAS_YOLO = False

# Faster Whisper for word-level captions
try:
    from faster_whisper import WhisperModel
    HAS_WHISPER = True
except Exception:
    HAS_WHISPER = False

# Active speaker module from pipeline
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
pipe_dir = os.path.join(REPO_ROOT, "backend", "pipeline")
if pipe_dir not in sys.path:
    sys.path.insert(0, pipe_dir)
import active_speaker
import split_layout

DEFAULT_TFLITE = os.path.join(REPO_ROOT, "blaze_face_short_range.tflite")
DEFAULT_YOLO = os.path.join(REPO_ROOT, "yolov8n.pt")
DEFAULT_OUTRO = r"C:\Youtube Channels\Videos\Temp Videos\OUTRO_D_3.5s.mp4"

def safe_print(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        try:
            print(msg.encode("ascii", errors="replace").decode("ascii"))
        except Exception:
            pass

def parse_time_str(val) -> float:
    """Parses timestamps like '03:26', '01:10:21', '206.5', '3m26s' into seconds."""
    if isinstance(val, (int, float)):
        return max(0.0, float(val))
    val_str = str(val).strip()
    if not val_str:
        return 0.0

    if ":" in val_str:
        parts = [float(p) for p in val_str.split(":")]
        if len(parts) == 3:
            return parts[0] * 3600.0 + parts[1] * 60.0 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60.0 + parts[1]
        elif len(parts) == 1:
            return parts[0]

    m = re.match(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?", val_str)
    if m and any(m.groups()):
        h = float(m.group(1) or 0)
        mins = float(m.group(2) or 0)
        s = float(m.group(3) or 0)
        return h * 3600.0 + mins * 60.0 + s

    try:
        return max(0.0, float(val_str))
    except ValueError:
        return 0.0

def format_ts(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int(round((sec - int(sec)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def extract_segment(src_path: str, start_s: float, end_s: float, out_path: str):
    """Cuts segment losslessly or with high-bitrate re-encode for frame-accurate cuts."""
    dur = max(1.0, end_s - start_s)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{start_s:.3f}",
        "-i", src_path,
        "-t", f"{dur:.3f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        out_path
    ]
    subprocess.run(cmd, check=True)

def transcribe_audio_words(video_path: str, log_fn=safe_print):
    """
    Extracts audio to WAV and transcribes using faster-whisper to get word-level timestamps.
    Returns:
      words: list of dicts [{'word': str, 'start': float, 'end': float}], relative to segment
      full_text: string
      language: str (e.g. 'en')
    """
    wav_path = video_path + ".wav"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        wav_path
    ], check=True)

    words = []
    text_pieces = []
    language = "en"
    try:
        from faster_whisper import WhisperModel
        import wave
        log_fn("   🎙️ Transcribing speech with Faster-Whisper...")
        model = WhisperModel("base", device="cpu", compute_type="int8")
        
        # Load audio into numpy float32 array for 100% robust transcription
        with wave.open(wav_path, "rb") as wf:
            raw_bytes = wf.readframes(wf.getnframes())
            audio_array = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            
        segments, info = model.transcribe(audio_array, word_timestamps=True)
        if hasattr(info, 'language'):
            language = info.language
        for seg in segments:
            if seg.text:
                text_pieces.append(seg.text.strip())
            if seg.words:
                for w in seg.words:
                    cleaned = w.word.strip()
                    if cleaned:
                        words.append({
                            "word": cleaned,
                            "raw_word": w.word,
                            "start": round(w.start, 3),
                            "end": round(w.end, 3),
                            "probability": getattr(w, "probability", 0.95)
                        })
        log_fn(f"   ✅ Transcribed {len(words)} words ({language}).")
    except Exception as e:
        log_fn(f"   ⚠️ Faster-Whisper error: {e}")
        import traceback
        log_fn(traceback.format_exc())

    if os.path.exists(wav_path):
        try:
            os.remove(wav_path)
        except Exception:
            pass

    full_text = " ".join(text_pieces)
    return words, full_text, language

def build_ass_subtitles(words, hook_text: str, duration_scaled: float, ass_path: str, speed: float = 1.20):
    """
    Generates ASS subtitles with:
    - 3.0s Top Hook banner with solid black background box and yellow text
    - Word-by-word animated karaoke captions scaled by / speed
    """
    scaled_words = []
    for w in words:
        scaled_words.append({
            'word': w['word'].upper(),
            'start': round(w['start'] / speed, 3),
            'end': round(w['end'] / speed, 3)
        })

    blocks = []
    current_block = []
    current_len = 0

    for w in scaled_words:
        word_txt = w['word']
        if not word_txt:
            continue
        if current_block and (current_len + len(word_txt) > 13 or len(current_block) >= 3 or (w['start'] - current_block[-1]['end'] > (0.45 / speed))):
            blocks.append(current_block)
            current_block = []
            current_len = 0
        current_block.append(w)
        current_len += len(word_txt) + 1
    if current_block:
        blocks.append(current_block)

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 162
PlayResY: 288
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Impact,22,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,2.5,1,2,10,10,48,1
Style: Hook,Impact,20,&H0000E5FF&,&H0000E5FF&,&H00000000&,&H00000000,1,0,0,0,100,100,0,0,3,4,0,8,10,10,32,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []

    # 3.0s Hook Banner with solid black background box and yellow text
    if hook_text and hook_text.strip():
        hook_end = min(3.0, duration_scaled)
        clean_hook = hook_text.strip().upper()
        events.append(f"Dialogue: 1,0:00:00.00,{format_ts(hook_end)},Hook,,0,0,0,,{clean_hook}")

    # Word-by-word karaoke blocks without gap flicker
    for block in blocks:
        for i, active_word in enumerate(block):
            ev_start = block[0]['start'] if i == 0 else active_word['start']
            ev_end = block[i + 1]['start'] if i < len(block) - 1 else block[-1]['end']
            if ev_end <= ev_start:
                ev_end = ev_start + 0.15

            line_parts = []
            for j, w in enumerate(block):
                txt = w['word']
                if j == i:
                    line_parts.append(f"{{\\c&H0000E5FF&\\fscx108\\fscy108\\bord3.0}}{txt}{{\\rDefault}}")
                else:
                    line_parts.append(txt)
            line_text = " ".join(line_parts)
            events.append(f"Dialogue: 0,{format_ts(ev_start)},{format_ts(ev_end)},Default,,0,0,0,,{line_text}")

    with open(ass_path, "w", encoding="utf-8-sig") as f:
        f.write(header + "\n".join(events) + "\n")

def detect_candidate_speakers(video_path: str, orig_w: int, orig_h: int,
                              log_fn=safe_print, start_frame=0, end_frame=None):
    """Discover positions within ONE shot, without cutting faces at mid-frame."""
    cap = cv2.VideoCapture(video_path)
    detector = None
    yolo_model = None
    boxes = []
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 29.97
        end_frame = end_frame or int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if HAS_MEDIAPIPE and os.path.exists(DEFAULT_TFLITE):
            try:
                options = mp_vision.FaceDetectorOptions(
                    base_options=mp_python.BaseOptions(model_asset_path=DEFAULT_TFLITE),
                    min_detection_confidence=0.35)
                detector = mp_vision.FaceDetector.create_from_options(options)
            except Exception:
                pass
        if HAS_YOLO and os.path.exists(DEFAULT_YOLO):
            try:
                yolo_model = YOLO(DEFAULT_YOLO)
            except Exception:
                pass
        count = min(12, max(3, int((end_frame - start_frame) / fps * 1.5)))
        for pos in sorted(set(np.linspace(start_frame, max(start_frame, end_frame - 1),
                                           count).astype(int))):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(pos))
            ok, frame = cap.read()
            if not ok:
                continue
            small = cv2.resize(frame, (640, max(2, round(640 * orig_h / orig_w))))
            sx, sy = orig_w / small.shape[1], orig_h / small.shape[0]
            found = []
            if detector is not None:
                try:
                    res = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                        data=cv2.cvtColor(small, cv2.COLOR_BGR2RGB)))
                    for d in res.detections:
                        b = d.bounding_box
                        found.append([b.origin_x * sx, b.origin_y * sy,
                                      b.width * sx, b.height * sy])
                except Exception:
                    pass
            if not found and yolo_model is not None:
                try:
                    for result in yolo_model(small, classes=[0], verbose=False):
                        for b in result.boxes:
                            x1, y1, x2, y2 = b.xyxy[0].tolist()
                            found.append([x1 * sx, y1 * sy, (x2 - x1) * sx,
                                          (y2 - y1) * sy * 0.4])
                except Exception:
                    pass
            boxes.extend(found)
    finally:
        cap.release()
        if detector is not None:
            detector.close()

    clusters = []
    for box in boxes:
        cx = box[0] + box[2] / 2
        cl = next((c for c in clusters if abs(c['cx'] - cx) < orig_w * 0.08), None)
        if cl is None:
            clusters.append({'cx': cx, 'boxes': [box]})
        else:
            cl['boxes'].append(box)
            cl['cx'] = float(np.median([b[0] + b[2] / 2 for b in cl['boxes']]))
    valid = [c for c in clusters if len(c['boxes']) >= 2] or clusters
    return sorted([{'cx': c['cx'], 'box': np.median(c['boxes'], axis=0).tolist()}
                   for c in valid], key=lambda c: c['cx'])


def _shot_fallback(video_path, boundaries, fps, orig_w, orig_h, crop_w, log_fn):
    """Degrade per shot: never reuse coordinates from another camera angle."""
    xs = []
    for start, end in boundaries:
        speakers = detect_candidate_speakers(video_path, orig_w, orig_h,
            log_fn=log_fn, start_frame=start, end_frame=end)
        cx = max(speakers, key=lambda s: s['box'][2] * s['box'][3])['cx'] if speakers else orig_w / 2
        x = max(0, min(round(cx - crop_w / 2), orig_w - crop_w))
        shot_xs = [x] * (end - start)
        if len(speakers) == 2:
            centres = [(s['cx'], s['box'][1] + s['box'][3] / 2,
                        s['box'][2], s['box'][3]) for s in speakers]
            try:
                held = active_speaker.hold(active_speaker.verdicts_for_scene(
                    video_path, start, end, fps, centres))
                if any(v is not None for v in held):
                    shot_xs = active_speaker.speaker_xs(
                        held, centres, crop_w, orig_w, end - start, fps)
            except Exception as exc:
                log_fn(f"   Speaker attribution unavailable in shot {start}: {exc}")
        xs.extend(shot_xs)
    return xs


def compute_active_speaker_trajectory(video_path: str, log_fn=safe_print):
    """Return a shot-local camera path and split layouts keyed by frame ranges."""
    cap = cv2.VideoCapture(video_path)
    try:
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        fps = cap.get(cv2.CAP_PROP_FPS)
        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps <= 0 or min(orig_w, orig_h, total_frames) <= 0:
            raise ValueError("Video has invalid dimensions, frame rate or frame count")
    finally:
        cap.release()

    crop_w = min(orig_w, int(orig_h * 9 / 16))
    crop_w -= crop_w % 2
    crop_h = orig_h if orig_w >= int(orig_h * 9 / 16) else int(crop_w * 16 / 9)
    crop_h -= crop_h % 2
    if min(crop_w, crop_h) < 2:
        raise ValueError("Video is too small to crop")
    max_x = orig_w - crop_w

    import scene_detection
    try:
        scenes, _ = scene_detection.detect_scenes(video_path)
    except Exception as exc:
        log_fn(f"   Scene detector unavailable ({exc}); trying content detection")
        scenes, _ = scene_detection._detect_pyscenedetect(video_path)
    # Include the lead-in and tail even when a detector omits them.
    cuts = sorted({0, total_frames} | {
        max(0, min(total_frames, t.get_frames())) for scene in scenes for t in scene})
    boundaries = [(a, b) for a, b in zip(cuts, cuts[1:]) if b > a]
    splits = {}
    try:
        import main as m
        import reframe_v2
        cameraman = m.SmoothedCameraman(1080, 1920, orig_w, orig_h, aspect_ratio=9 / 16)
        tracker = m.SpeakerTracker(cooldown_frames=max(1, round(fps)))
        raw_xs = reframe_v2._analyze_trajectory(video_path, boundaries,
            ['TRACK'] * len(boundaries), fps, orig_w, orig_h, cameraman, tracker)
        if len(raw_xs) != total_frames or any(x is None or not math.isfinite(x) for x in raw_xs):
            raise RuntimeError("Incomplete camera trajectory")
        xs = [max(0, min(round(x), max_x)) for x in raw_xs]
    except Exception as exc:
        log_fn(f"   Shot tracking unavailable ({exc}); using shot-local fallback")
        xs = _shot_fallback(video_path, boundaries, fps, orig_w, orig_h, crop_w, log_fn)

    # Require simultaneous speakers within each shot. Alternating close-ups
    # must never qualify as a two-person layout based on pooled positions.
    try:
        from scenedetect import FrameTimecode
        normalized = [(FrameTimecode(a, fps), FrameTimecode(b, fps)) for a, b in boundaries]
        found = split_layout.detect_split_scenes(video_path, normalized,
                                                 ['GENERAL'] * len(normalized), enabled=True)
        for idx, centres in found.items():
            start, end = boundaries[idx]
            splits[(start, end)] = centres
            try:
                held = active_speaker.hold(active_speaker.verdicts_for_scene(
                    video_path, start, end, fps, centres))
                if any(v is not None for v in held):
                    xs[start:end] = active_speaker.speaker_xs(
                        held, centres, crop_w, orig_w, end - start, fps)
            except Exception as exc:
                log_fn(f"   Speaker attribution unavailable in shot {start}: {exc}")
    except Exception as exc:
        log_fn(f"   Split layout analysis unavailable ({exc}); retaining focus framing")

    switches = sorted({a for a, _ in boundaries if a > 0} |
                      {f for f in range(1, len(xs)) if abs(xs[f] - xs[f - 1]) >= 80})
    log_fn(f"   Shot-aware camera path: {len(boundaries)} shots, {len(splits)} two-shots")
    return xs, fps, orig_w, orig_h, crop_w, crop_h, switches, splits


def compute_dynamic_motion_zooms(n_frames: int, fps: float, speaker_switches: list = None,
                                 max_zoom: float = 1.035, playback_speed: float = 1.0):
    """A restrained push on long uninterrupted shots, held until the next cut.

    Timings are in delivered-video seconds. Short conversational turns remain
    still; long shots get one slow push instead of repeated zoom-in/out cycles.
    """
    zooms = [1.0] * max(0, n_frames)
    if not zooms:
        return zooms
    if not math.isfinite(fps) or fps <= 0 or not math.isfinite(playback_speed) or playback_speed <= 0:
        raise ValueError("Frame rate and playback speed must be positive")
    if not math.isfinite(max_zoom):
        raise ValueError("Zoom must be finite")
    # Keep automatic motion below 4%, even if an old caller supplies 1.13.
    peak = max(1.0, min(max_zoom, 1.04))
    delivered_fps = fps * playback_speed
    cuts = sorted({0, n_frames} | {
        int(f) for f in (speaker_switches or []) if 0 < f < n_frames})
    for start, end in zip(cuts, cuts[1:]):
        duration = (end - start) / delivered_fps
        if duration < 6.0 or peak <= 1.0:
            continue
        settle_seconds = 1.5
        push_seconds = min(5.0, duration - settle_seconds - 1.0)
        for frame in range(start, end):
            elapsed = (frame - start) / delivered_fps
            progress = max(0.0, min(1.0, (elapsed - settle_seconds) / push_seconds))
            eased = progress * progress * (3.0 - 2.0 * progress)
            zooms[frame] = 1.0 + (peak - 1.0) * eased
    return zooms


def compute_crop_boxes(xs, zooms, crop_w, crop_h, orig_w, orig_h):
    """Computes frame (w, h, x, y) ensuring natural headroom and centered speaker framing."""
    boxes = []
    for i, x in enumerate(xs):
        z = zooms[i] if i < len(zooms) else 1.0
        w = int(crop_w / z)
        h = int(crop_h / z)
        w -= w % 2
        h -= h % 2
        w = max(2, min(w, orig_w))
        h = max(2, min(h, orig_h))

        # Center X on speaker
        cx = x + crop_w / 2.0
        nx = int(round(cx - w / 2.0))
        nx = max(0, min(nx, orig_w - w))

        # Preserve natural headroom (keep y slightly elevated in frame)
        ny = int(round((orig_h - h) * 0.45))
        ny = max(0, min(ny, orig_h - h))

        boxes.append((w, h, nx - (nx % 2), ny - (ny % 2)))
    return boxes

def generate_sendcmd_boxes(boxes, fps, cmd_path, speed=1.0):
    lines = []
    prev = None
    for i, box in enumerate(boxes):
        if box == prev:
            continue
        # Place commands between frames. Rounding an exact frame timestamp up
        # can defer a scene-cut crop until the NEXT frame (especially after
        # setpts speed scaling quantizes the input time base).
        t = max(0.0, (i - 0.5) / fps / speed)
        w, h, x, y = box
        pw, ph, px, py = prev if prev else (None, None, None, None)
        if w != pw:
            lines.append(f"{t:.9f} crop@c w {w};")
        if h != ph:
            lines.append(f"{t:.9f} crop@c h {h};")
        if x != px:
            lines.append(f"{t:.9f} crop@c x {x};")
        if y != py:
            lines.append(f"{t:.9f} crop@c y {y};")
        prev = box
    with open(cmd_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def manual_reframe_filtergraph(first_box, command_path, speed, orig_w, orig_h,
                              fps, total_frames, splits=None):
    """Use focus framing on close-ups and stack only validated two-shots."""
    from ffmpeg_utils import escape_filter_value
    if not math.isfinite(speed) or speed <= 0:
        raise ValueError("Playback speed must be positive")
    if splits and not isinstance(splits, dict):  # legacy single-shot caller
        splits = {(0, total_frames): splits}
    splits = splits or {}
    count = len(splits)
    w, h, x, y = first_box
    source = f"[0:v]setpts=(PTS-STARTPTS)/{speed}"
    source += (f",split={count + 1}[focus]" +
               ''.join(f"[shot{i}]" for i in range(count)) if count else "[focus]")
    parts = [source + ';',
             f"[focus]sendcmd=f='{escape_filter_value(command_path)}',"
             f"crop@c=w={w}:h={h}:x={x}:y={y},"
             "scale=1080:1920:flags=lanczos,setsar=1[base0];"]
    for i, ((start, end), (left, right)) in enumerate(sorted(splits.items())):
        tw, th, tx, ty, half = split_layout.split_geometry(orig_w, orig_h, 1080, 1920, left)
        bw, bh, bx, by, _ = split_layout.split_geometry(orig_w, orig_h, 1080, 1920, right)
        parts.extend([
            f"[shot{i}]split=2[top{i}][bot{i}];",
            f"[top{i}]crop={tw}:{th}:{tx}:{ty},scale=1080:{half}[t{i}];",
            f"[bot{i}]crop={bw}:{bh}:{bx}:{by},scale=1080:{half}[b{i}];",
            f"[t{i}][b{i}]vstack=inputs=2,pad=1080:1920:0:0,setsar=1[stack{i}];",
            f"[base{i}][stack{i}]overlay=enable='gte(t,{max(0, start - 0.5) / fps / speed:.9f})*"
            f"lt(t,{(end - 0.5) / fps / speed:.9f})'[base{i+1}];"])
    parts.extend([f"[base{count}]null[v];", f"[0:a]atempo={speed}[a]"])
    return ''.join(parts)


def process_single_clip(src_video: str, clip_data: dict, work_dir: str,
                        clean_out_video: str, subtitled_out_video: str,
                        speed: float = 1.20, outro_path: str = DEFAULT_OUTRO, log_fn=safe_print):
    """
    Renders one manual clip with:
    - Active speaker face detection & smooth cinematic tracking
    - Subtle, shot-aware camera motion
    - 1.20x speed scaling
    - 3.0s black-box yellow hook banner
    - Animated word-by-word karaoke captions
    - Appended outro video
    Outputs:
    - clean_out_video: clean 9:16 video without subtitles (for /api/subtitle restyling)
    - subtitled_out_video: 9:16 video with Hook + Captions burned in
    Returns:
    - (words, full_text, language)
    """
    hook_text = clip_data.get("hook", "")
    start_s = parse_time_str(clip_data.get("start", 0))
    end_s = parse_time_str(clip_data.get("end", 0))
    clip_id = clip_data.get("id", "1")

    log_fn(f"✂️ Cutting segment {format_ts(start_s)} -> {format_ts(end_s)} ({end_s - start_s:.1f}s)...")
    raw_segment = os.path.join(work_dir, f"segment_{clip_id}.mp4")
    extract_segment(src_video, start_s, end_s, raw_segment)

    # 1. Word-level transcription
    words, full_text, language = transcribe_audio_words(raw_segment, log_fn=log_fn)

    # 2. Active speaker detection and dynamic framing
    log_fn("🔍 Performing active speaker face detection & camera tracking...")
    res = compute_active_speaker_trajectory(raw_segment, log_fn=log_fn)
    if len(res) == 8:
        xs, fps, orig_w, orig_h, crop_w, crop_h, speaker_switches, split_pair = res
    else:
        xs, fps, orig_w, orig_h, crop_w, crop_h, speaker_switches = res
        split_pair = None
    duration_orig = len(xs) / fps
    duration_scaled = duration_orig / speed

    # 3. Restrained motion, timed to the final playback speed and speaker cuts.
    log_fn("🎥 Applying subtle camera motion on longer shots...")
    zooms = compute_dynamic_motion_zooms(len(xs), fps, speaker_switches, playback_speed=speed)
    boxes = compute_crop_boxes(xs, zooms, crop_w, crop_h, orig_w, orig_h)

    # 4. ASS Subtitles (Hook with yellow text + black background box, and karaoke captions)
    ass_path = os.path.join(work_dir, f"subtitles_{clip_id}.ass")
    build_ass_subtitles(words, hook_text, duration_scaled, ass_path, speed=speed)

    # 5. sendcmd commands for dynamic w/h/x/y
    cmd_path = os.path.join(work_dir, f"cmd_{clip_id}.txt")
    generate_sendcmd_boxes(boxes, fps, cmd_path, speed=speed)

    # 6. Reframe to 9:16 vertical video & 1.20x speedup (clean baseline)
    reframed_path = os.path.join(work_dir, f"reframed_{clip_id}.mp4")
    rel_cmd = os.path.relpath(cmd_path, REPO_ROOT).replace("\\", "/")

    filtergraph = manual_reframe_filtergraph(
        boxes[0], rel_cmd, speed, orig_w, orig_h, fps, len(xs),
        split_pair if clip_data.get("layout", "focus") == "split" else None)

    log_fn(f"🎬 Rendering vertical 9:16 short at {speed}x speed with active speaker framing...")
    reframe_cmd = [
        "ffmpeg", "-y", "-loglevel", "warning",
        "-i", raw_segment,
        "-filter_complex", filtergraph,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        reframed_path
    ]
    subprocess.run(reframe_cmd, check=True, cwd=REPO_ROOT)

    # 7. Append Outro Video to clean video
    has_outro = outro_path and os.path.exists(outro_path)
    if has_outro:
        log_fn(f"🔗 Appending Outro: {os.path.basename(outro_path)}...")
        concat_filter = (
            "[0:v]fps=30,setsar=1[v0];"
            "[1:v]fps=30,setsar=1[v1];"
            "[0:a]aformat=sample_rates=48000:channel_layouts=stereo[a0];"
            "[1:a]aformat=sample_rates=48000:channel_layouts=stereo[a1];"
            "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]"
        )
        final_cmd = [
            "ffmpeg", "-y", "-loglevel", "warning",
            "-i", reframed_path,
            "-i", outro_path,
            "-filter_complex", concat_filter,
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            clean_out_video
        ]
        subprocess.run(final_cmd, check=True)
    else:
        if os.path.exists(clean_out_video):
            os.remove(clean_out_video)
        shutil.copyfile(reframed_path, clean_out_video)

    # 8. Burn ASS Subtitles (Hook + Karaoke) onto clean_out_video -> subtitled_out_video
    log_fn("🎨 Burning eye-catching Hook and Karaoke captions...")
    rel_ass = os.path.relpath(ass_path, REPO_ROOT).replace("\\", "/")
    burn_cmd = [
        "ffmpeg", "-y", "-loglevel", "warning",
        "-i", clean_out_video,
        "-vf", f"ass={rel_ass}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "copy",
        subtitled_out_video
    ]
    subprocess.run(burn_cmd, check=True, cwd=REPO_ROOT)

    log_fn(f"✅ Finished Clip {clip_id}: {os.path.basename(subtitled_out_video)}")
    return words, full_text, language
