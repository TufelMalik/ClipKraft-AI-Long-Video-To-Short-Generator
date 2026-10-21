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
sys.path.insert(0, os.path.join(REPO_ROOT, "backend", "pipeline"))
import active_speaker

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

def detect_candidate_speakers(video_path: str, orig_w: int, orig_h: int, log_fn=safe_print):
    """
    Samples frames across the video to discover all seated/present face clusters.
    Returns list of speaker cluster dicts: [{ 'cx': float, 'box': [x,y,w,h] }, ...]
    """
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 29.97
    total_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 100)
    dur_s = total_f / fps

    detector = None
    if HAS_MEDIAPIPE and os.path.exists(DEFAULT_TFLITE):
        try:
            base_options = mp_python.BaseOptions(model_asset_path=DEFAULT_TFLITE)
            options = mp_vision.FaceDetectorOptions(base_options=base_options, min_detection_confidence=0.35)
            detector = mp_vision.FaceDetector.create_from_options(options)
        except Exception:
            pass

    yolo_model = None
    if detector is None and HAS_YOLO and os.path.exists(DEFAULT_YOLO):
        try:
            yolo_model = YOLO(DEFAULT_YOLO)
        except Exception:
            pass

    # Sample up to 15 frames evenly
    sample_count = min(15, max(3, int(dur_s * 1.5)))
    step_f = max(1, total_f // sample_count)

    detected_boxes = []
    small_w = 640
    small_h = int(640 * (orig_h / orig_w))
    scale_factor = orig_w / float(small_w)

    for i in range(sample_count):
        f_pos = i * step_f
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_pos)
        ret, frame = cap.read()
        if not ret:
            continue
        small = cv2.resize(frame, (small_w, small_h))

        if detector:
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            res = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
            for d in res.detections:
                b = d.bounding_box
                detected_boxes.append([
                    b.origin_x * scale_factor,
                    b.origin_y * scale_factor,
                    b.width * scale_factor,
                    b.height * scale_factor
                ])
        elif yolo_model:
            y_res = yolo_model(small, classes=[0], verbose=False)
            for r in y_res:
                for b in r.boxes:
                    xyxy = [int(x * scale_factor) for x in b.xyxy[0]]
                    detected_boxes.append([
                        xyxy[0], xyxy[1], xyxy[2] - xyxy[0], (xyxy[3] - xyxy[1]) * 0.4
                    ])
    cap.release()

    if not detected_boxes:
        return []

    # Cluster detected face boxes by horizontal center X (faces within 180px belong to the same person)
    clusters = []
    for box in detected_boxes:
        cx = box[0] + box[2] / 2.0
        matched = False
        for cl in clusters:
            if abs(cl['cx'] - cx) < 200:
                cl['boxes'].append(box)
                cl['cx'] = sum(b[0] + b[2] / 2.0 for b in cl['boxes']) / len(cl['boxes'])
                matched = True
                break
        if not matched:
            clusters.append({'cx': cx, 'boxes': [box]})

    # Keep clusters with at least 2 detections (filter out momentary noise)
    valid_clusters = [cl for cl in clusters if len(cl['boxes']) >= 2] or clusters

    # Compute median bounding box for each cluster
    speaker_list = []
    for cl in valid_clusters:
        boxes_arr = np.array(cl['boxes'])
        med_box = np.median(boxes_arr, axis=0).tolist()
        speaker_list.append({
            'cx': cl['cx'],
            'box': med_box
        })

    # Sort left to right
    speaker_list.sort(key=lambda s: s['cx'])
    return speaker_list

def compute_active_speaker_trajectory(video_path: str, log_fn=safe_print):
    """
    Detects who is speaking in each time window and computes a smooth horizontal pan (X).
    Accurately cuts/pans between speakers when conversation switches.
    """
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 29.97
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 2560)
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1440)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 100)
    dur_s = total_frames / fps
    cap.release()

    crop_h = orig_h
    crop_w = int(orig_h * 9 / 16)
    if crop_w % 2 != 0:
        crop_w -= 1
    max_x = max(0, orig_w - crop_w)
    center_default_x = max_x // 2

    # Discover candidate speakers
    log_fn("   👤 Detecting speaker positions and face clusters...")
    speakers = detect_candidate_speakers(video_path, orig_w, orig_h, log_fn=log_fn)

    speaker_switches = [] # Frame indices where active speaker changes

    if len(speakers) == 0:
        log_fn("   ℹ️ No face clusters identified, using center 9:16 framing.")
        xs = [center_default_x] * total_frames
        return xs, fps, orig_w, orig_h, crop_w, crop_h, speaker_switches

    if len(speakers) == 1:
        log_fn(f"   👤 Solo speaker tracked at X={speakers[0]['cx']:.0f}px.")
        target_x = max(0, min(int(round(speakers[0]['cx'] - crop_w / 2.0)), max_x))
        xs = [target_x] * total_frames
        return xs, fps, orig_w, orig_h, crop_w, crop_h, speaker_switches

    # Multi-speaker setup: Run lip/mouth activity + audio envelope analysis
    log_fn(f"   🎙️ Found {len(speakers)} speakers! Analyzing active mouth movement & audio energy...")
    window_s = 0.4
    boxes = [s['box'] for s in speakers]

    try:
        activity = active_speaker.decode_activity(video_path, 0.0, dur_s, boxes, fps, window_s=window_s)
        loudness = active_speaker.audio_envelope(video_path, 0.0, dur_s, window_s=window_s)
        norm_act = active_speaker.normalise_activity(activity)

        verdicts = []
        for i, act_row in enumerate(norm_act):
            if loudness and i < len(loudness) and loudness[i] < 0.15:
                verdicts.append(None)
                continue
            row = np.array(act_row)
            tot = np.sum(row)
            if tot <= 0:
                verdicts.append(None)
                continue
            sorted_indices = np.argsort(row)[::-1]
            top = sorted_indices[0]
            second = sorted_indices[1] if len(sorted_indices) > 1 else top
            if len(sorted_indices) > 1 and (row[top] - row[second]) / tot >= 0.10:
                verdicts.append(top)
            else:
                verdicts.append(top)

        # Hold smoothing (require 2 windows in a row to switch speakers)
        held = []
        curr = None
        pending = None
        run = 0
        for v in verdicts:
            if v is None or v == curr:
                if v == curr:
                    pending, run = None, 0
                held.append(curr)
                continue
            if v == pending:
                run += 1
            else:
                pending, run = v, 1
            if curr is None or run >= 2:
                curr, pending, run = v, None, 0
            held.append(curr)

        first_valid = next((v for v in held if v is not None), 0)
        held = [first_valid if v is None else v for v in held]

    except Exception as e:
        log_fn(f"   ⚠️ Active speaker attribution fallback ({e}); using primary speaker.")
        held = [0] * int(dur_s / window_s + 2)

    # Compute per-frame target X
    per_frame_targets = []
    prev_speaker = None
    for f in range(total_frames):
        w_idx = min(int((f / fps) / window_s), len(held) - 1) if held else 0
        spk_idx = held[w_idx] if w_idx < len(held) else 0
        if spk_idx != prev_speaker:
            speaker_switches.append(f)
            prev_speaker = spk_idx
        cx = speakers[spk_idx]['cx']
        tx = max(0, min(int(round(cx - crop_w / 2.0)), max_x))
        per_frame_targets.append(tx)

    # Smooth camera pan transitions (cinematic easing when switching speakers)
    xs = []
    current_x = per_frame_targets[0]
    for i, target_x in enumerate(per_frame_targets):
        diff = target_x - current_x
        if abs(diff) > 20:
            speed_px = 16.0 if abs(diff) > 250 else 6.0
            direction = 1 if diff > 0 else -1
            current_x += direction * speed_px
            if (direction == 1 and current_x > target_x) or (direction == -1 and current_x < target_x):
                current_x = target_x
        else:
            current_x = target_x
        xs.append(max(0, min(int(round(current_x)), max_x)))

    log_fn(f"   🎯 Active speaker camera trajectory computed ({len(speaker_switches)} speaker turns).")
    return xs, fps, orig_w, orig_h, crop_w, crop_h, speaker_switches

def compute_dynamic_motion_zooms(n_frames: int, fps: float, speaker_switches: list = None, max_zoom: float = 1.13):
    """
    Adds professional, cinematic motion zoom in and zoom out animations:
    - Slowly pushes in during speaker emphasis (1.0x -> max_zoom) with smoothstep easing.
    - Holds at peak zoom during core points.
    - Gently eases back out (max_zoom -> 1.0x).
    - Resets smoothly when camera pans to a new speaker.
    """
    zooms = [1.0] * n_frames
    dur_s = n_frames / fps
    if dur_s < 4.0:
        return zooms

    def smoothstep(t):
        t = max(0.0, min(1.0, t))
        return t * t * (3.0 - 2.0 * t)

    # Generate rhythmic motion zoom cycles every 5 to 7 seconds
    cycle_s = 6.0
    rise_s = 1.2
    fall_s = 1.2

    num_cycles = max(1, int(dur_s / cycle_s))
    zoom_beats = []
    for c in range(num_cycles):
        start_s = c * cycle_s + 1.0
        end_s = min(dur_s - 0.5, start_s + 4.5)
        if end_s - start_s >= 2.5:
            zoom_beats.append((start_s, end_s))

    for start_s, end_s in zoom_beats:
        hold_s = max(0.4, end_s - start_s - rise_s - fall_s)
        total_s = rise_s + hold_s + fall_s
        for f in range(n_frames):
            t = f / fps
            if start_s <= t <= start_s + total_s:
                dt = t - start_s
                if dt < rise_s:
                    amt = smoothstep(dt / rise_s)
                elif dt < rise_s + hold_s:
                    amt = 1.0
                else:
                    amt = 1.0 - smoothstep((dt - rise_s - hold_s) / fall_s)
                zooms[f] = max(zooms[f], 1.0 + (max_zoom - 1.0) * amt)

    # Reset zoom smoothly during speaker switches
    if speaker_switches:
        reset_window = int(fps * 0.8)
        for sw in speaker_switches:
            if sw > 0:
                for f in range(max(0, sw - reset_window), min(n_frames, sw + reset_window)):
                    factor = abs(f - sw) / float(reset_window)
                    zooms[f] = 1.0 + (zooms[f] - 1.0) * factor

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
        t = (i / fps) / speed
        w, h, x, y = box
        pw, ph, px, py = prev if prev else (None, None, None, None)
        if w != pw:
            lines.append(f"{t:.4f} crop@c w {w};")
        if h != ph:
            lines.append(f"{t:.4f} crop@c h {h};")
        if x != px:
            lines.append(f"{t:.4f} crop@c x {x};")
        if y != py:
            lines.append(f"{t:.4f} crop@c y {y};")
        prev = box
    with open(cmd_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def process_single_clip(src_video: str, clip_data: dict, work_dir: str,
                        clean_out_video: str, subtitled_out_video: str,
                        speed: float = 1.20, outro_path: str = DEFAULT_OUTRO, log_fn=safe_print):
    """
    Renders one manual clip with:
    - Active speaker face detection & smooth cinematic tracking
    - Dynamic motion zoom in/out animations
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
    xs, fps, orig_w, orig_h, crop_w, crop_h, speaker_switches = compute_active_speaker_trajectory(raw_segment, log_fn=log_fn)
    duration_orig = len(xs) / fps
    duration_scaled = duration_orig / speed

    # 3. Dynamic motion zoom in and zoom out animation
    log_fn("🎥 Adding professional motion zoom in / zoom out animations...")
    zooms = compute_dynamic_motion_zooms(len(xs), fps, speaker_switches, max_zoom=1.13)
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

    first_w, first_h, first_x, first_y = boxes[0]
    filtergraph = (
        f"[0:v]setpts=PTS/{speed},"
        f"sendcmd=f={rel_cmd},"
        f"crop@c=w={first_w}:h={first_h}:x={first_x}:y={first_y},"
        f"scale=1080:1920:flags=lanczos,setsar=1[v];"
        f"[0:a]atempo={speed}[a]"
    )

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
