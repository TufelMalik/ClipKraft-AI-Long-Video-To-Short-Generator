import os
import sys
import json
import re
import math
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

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_TFLITE = os.path.join(REPO_ROOT, "blaze_face_short_range.tflite")
DEFAULT_YOLO = os.path.join(REPO_ROOT, "yolov8n.pt")
DEFAULT_OUTRO = r"C:\Youtube Channels\Videos\Temp Videos\OUTRO_D_3.5s.mp4"

def parse_time_str(val) -> float:
    """
    Parses timestamps like '03:26', '01:10:21', '206.5', '3m26s' into seconds.
    """
    if isinstance(val, (int, float)):
        return max(0.0, float(val))
    val_str = str(val).strip()
    if not val_str:
        return 0.0

    # Format: HH:MM:SS or MM:SS
    if ":" in val_str:
        parts = [float(p) for p in val_str.split(":")]
        if len(parts) == 3:
            return parts[0] * 3600.0 + parts[1] * 60.0 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60.0 + parts[1]
        elif len(parts) == 1:
            return parts[0]

    # Format: 3m26s
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
    """
    Cuts video losslessly or with fast re-encode for frame-accurate timing.
    """
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

def transcribe_audio_words(video_path: str, log_fn=print):
    """
    Extracts audio to WAV and transcribes using faster-whisper to get word-level timestamps.
    """
    wav_path = video_path + ".wav"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        wav_path
    ], check=True)

    words = []
    if HAS_WHISPER:
        log_fn("   🎙️ Transcribing speech with Faster-Whisper...")
        try:
            model = WhisperModel("base", device="cpu", compute_type="int8")
            segments, _ = model.transcribe(wav_path, word_timestamps=True)
            for seg in segments:
                if seg.words:
                    for w in seg.words:
                        cleaned = w.word.strip()
                        if cleaned:
                            words.append({
                                "word": cleaned,
                                "start": round(w.start, 3),
                                "end": round(w.end, 3)
                            })
        except Exception as e:
            log_fn(f"   ⚠️ Faster-Whisper failed: {e}. Continuing without full word timestamps.")
    
    if os.path.exists(wav_path):
        try:
            os.remove(wav_path)
        except Exception:
            pass

    return words

def build_ass_subtitles(words, hook_text: str, duration_scaled: float, ass_path: str, speed: float = 1.20):
    """
    Generates ASS subtitles with:
    - 3.0s Top Hook banner with solid black background box and yellow text
    - Word-by-word animated karaoke captions
    """
    scaled_words = []
    for w in words:
        scaled_words.append({
            'word': w['word'].upper(),
            'start': w['start'] / speed,
            'end': w['end'] / speed
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

    # 3.0s Hook Banner with solid black background box
    if hook_text and hook_text.strip():
        hook_end = min(3.0, duration_scaled)
        clean_hook = hook_text.strip().upper()
        events.append(f"Dialogue: 1,0:00:00.00,{format_ts(hook_end)},Hook,,0,0,0,,{clean_hook}")

    # Karaoke blocks
    for block in blocks:
        for active_idx, active_word in enumerate(block):
            w_start = active_word['start']
            w_end = active_word['end']
            if w_end <= w_start:
                w_end = w_start + 0.12

            line_parts = []
            for i, w in enumerate(block):
                txt = w['word']
                if i == active_idx:
                    line_parts.append(f"{{\\c&H0000E5FF&\\fscx106\\fscy106\\bord3.0}}{txt}{{\\rDefault}}")
                else:
                    line_parts.append(txt)
            line_text = " ".join(line_parts)
            events.append(f"Dialogue: 0,{format_ts(w_start)},{format_ts(w_end)},Default,,0,0,0,,{line_text}")

    with open(ass_path, "w", encoding="utf-8-sig") as f:
        f.write(header + "\n".join(events) + "\n")

def compute_speaker_trajectory(video_path: str, log_fn=print):
    """
    Computes smooth horizontal crop center X for 9:16 vertical framing using MediaPipe/YOLO.
    """
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 29.97
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 2560)
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1440)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 100)
    cap.release()

    # Calculate 9:16 crop width based on source height
    crop_h = orig_h
    crop_w = int(orig_h * 9 / 16)
    if crop_w % 2 != 0:
        crop_w -= 1
    max_x = max(0, orig_w - crop_w)
    center_default_x = max_x // 2

    # Check for MediaPipe detector
    detector = None
    if HAS_MEDIAPIPE and os.path.exists(DEFAULT_TFLITE):
        try:
            base_options = mp_python.BaseOptions(model_asset_path=DEFAULT_TFLITE)
            options = mp_vision.FaceDetectorOptions(base_options=base_options, min_detection_confidence=0.35)
            detector = mp_vision.FaceDetector.create_from_options(options)
        except Exception as e:
            log_fn(f"   ⚠️ MediaPipe init error: {e}")

    # Fallback YOLO
    yolo_model = None
    if HAS_YOLO and os.path.exists(DEFAULT_YOLO):
        try:
            yolo_model = YOLO(DEFAULT_YOLO)
        except Exception:
            pass

    stride = 3
    small_w = 640
    small_h = int(640 * (orig_h / orig_w))
    scale_factor = orig_w / small_w
    frame_bytes = small_w * small_h * 3

    proc = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-i", video_path,
         "-vf", f"scale={small_w}:{small_h}",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=frame_bytes * 4
    )

    detected_targets = {}
    f_idx = 0

    while True:
        buf = proc.stdout.read(frame_bytes)
        if len(buf) < frame_bytes:
            break

        if f_idx % stride == 0:
            frame_small = np.frombuffer(buf, dtype=np.uint8).reshape((small_h, small_w, 3))
            best_target_x = None

            if detector is not None:
                rgb = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = detector.detect(mp_image)
                if result.detections:
                    faces = []
                    for d in result.detections:
                        b = d.bounding_box
                        cx = (b.origin_x + b.width / 2) * scale_factor
                        area = b.width * b.height * (scale_factor ** 2)
                        faces.append((cx, area))
                    best_face = max(faces, key=lambda f: f[1])
                    best_target_x = best_face[0] - crop_w / 2

            if best_target_x is None and yolo_model is not None:
                y_res = yolo_model(frame_small, classes=[0], verbose=False)
                persons = []
                for r in y_res:
                    for b in r.boxes:
                        xyxy = [int(x * scale_factor) for x in b.xyxy[0]]
                        cx = (xyxy[0] + xyxy[2]) / 2
                        persons.append(cx)
                if persons:
                    best_target_x = persons[0] - crop_w / 2

            if best_target_x is not None:
                detected_targets[f_idx] = max(0, min(int(best_target_x), max_x))

        f_idx += 1

    proc.stdout.close()
    proc.wait()

    # Smooth trajectory
    xs = []
    current_x = center_default_x
    target_x = center_default_x

    for i in range(total_frames):
        if i in detected_targets:
            new_target = detected_targets[i]
            if abs(new_target - current_x) > 350:
                current_x = new_target
                target_x = new_target
            else:
                target_x = new_target

        diff = target_x - current_x
        if abs(diff) > 30:
            speed_px = 12.0 if abs(diff) > 200 else 4.0
            direction = 1 if diff > 0 else -1
            current_x += direction * speed_px
            if (direction == 1 and current_x > target_x) or (direction == -1 and current_x < target_x):
                current_x = target_x

        xs.append(max(0, min(int(round(current_x)), max_x)))

    return xs, fps, orig_w, orig_h, crop_w, crop_h

def compute_slow_zoom_curve(n_frames: int, fps: float, zoom_beats: list = None, max_zoom: float = 1.12):
    zooms = [1.0] * n_frames
    if not zoom_beats:
        dur_s = n_frames / fps
        if dur_s > 10.0:
            zoom_beats = [
                (dur_s * 0.25, dur_s * 0.45),
                (dur_s * 0.65, dur_s * 0.85)
            ]
        else:
            zoom_beats = [(dur_s * 0.2, dur_s * 0.7)]

    rise_s = 1.3
    fall_s = 1.3

    def smoothstep(t):
        t = max(0.0, min(1.0, t))
        return t * t * (3.0 - 2.0 * t)

    for start_s, end_s in zoom_beats:
        hold_s = max(0.5, end_s - start_s - rise_s - fall_s)
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

    return zooms

def compute_crop_boxes(xs, zooms, crop_w, crop_h, orig_w, orig_h):
    boxes = []
    for i, x in enumerate(xs):
        z = zooms[i] if i < len(zooms) else 1.0
        w = int(crop_w / z)
        h = int(crop_h / z)
        w -= w % 2
        h -= h % 2
        w = max(2, min(w, orig_w))
        h = max(2, min(h, orig_h))

        cx = x + crop_w / 2.0
        cy = crop_h / 2.0
        nx = int(round(cx - w / 2.0))
        ny = int(round(cy - h / 2.0))
        nx = max(0, min(nx, orig_w - w))
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

def process_single_clip(src_video: str, clip_data: dict, work_dir: str, out_video: str,
                        speed: float = 1.20, outro_path: str = DEFAULT_OUTRO, log_fn=print):
    """
    Renders one manual clip with:
    - 1.20x speed scaling
    - 3.0s black-box yellow hook banner
    - Animated karaoke captions
    - Active speaker reframing & smooth zoom
    - Appended outro video
    """
    hook_text = clip_data.get("hook", "")
    start_s = parse_time_str(clip_data.get("start", 0))
    end_s = parse_time_str(clip_data.get("end", 0))
    clip_id = clip_data.get("id", "1")

    log_fn(f"✂️ Cutting segment {format_ts(start_s)} -> {format_ts(end_s)} ({end_s - start_s:.1f}s)...")
    raw_segment = os.path.join(work_dir, f"segment_{clip_id}.mp4")
    extract_segment(src_video, start_s, end_s, raw_segment)

    # 1. Word-level transcription
    words = transcribe_audio_words(raw_segment, log_fn=log_fn)

    # 2. Speaker tracking and dynamic framing
    log_fn("🎥 Analyzing speaker framing and dynamic zooms...")
    xs, fps, orig_w, orig_h, crop_w, crop_h = compute_speaker_trajectory(raw_segment, log_fn=log_fn)
    duration_orig = len(xs) / fps
    duration_scaled = duration_orig / speed

    zooms = compute_slow_zoom_curve(len(xs), fps, max_zoom=1.12)
    boxes = compute_crop_boxes(xs, zooms, crop_w, crop_h, orig_w, orig_h)

    # 3. ASS Subtitles
    ass_path = os.path.join(work_dir, f"subtitles_{clip_id}.ass")
    build_ass_subtitles(words, hook_text, duration_scaled, ass_path, speed=speed)

    # 4. sendcmd commands
    cmd_path = os.path.join(work_dir, f"cmd_{clip_id}.txt")
    generate_sendcmd_boxes(boxes, fps, cmd_path, speed=speed)

    # 5. Reframe & Speedup
    reframed_path = os.path.join(work_dir, f"reframed_{clip_id}.mp4")
    rel_cmd = os.path.relpath(cmd_path, REPO_ROOT).replace("\\", "/")
    rel_ass = os.path.relpath(ass_path, REPO_ROOT).replace("\\", "/")

    first_w, first_h, first_x, first_y = boxes[0]
    filtergraph = (
        f"[0:v]setpts=PTS/{speed},"
        f"sendcmd=f={rel_cmd},"
        f"crop@c=w={first_w}:h={first_h}:x={first_x}:y={first_y},"
        f"scale=1080:1920:flags=lanczos,setsar=1,"
        f"ass={rel_ass}[v];"
        f"[0:a]atempo={speed}[a]"
    )

    log_fn(f"🎬 Rendering vertical 9:16 short at {speed}x speed...")
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

    # 6. Append Outro if available
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
            out_video
        ]
        subprocess.run(final_cmd, check=True)
    else:
        # Move reframed directly to final output
        if os.path.exists(out_video):
            os.remove(out_video)
        os.rename(reframed_path, out_video)

    log_fn(f"✅ Finished Clip {clip_id}: {os.path.basename(out_video)}")
