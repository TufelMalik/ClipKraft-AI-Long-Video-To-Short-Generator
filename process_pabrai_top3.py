import os
import sys
import json
import wave
import subprocess
import cv2
import numpy as np

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from faster_whisper import WhisperModel
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from ultralytics import YOLO

SOURCE_VIDEO = r"C:\Youtube Channels\Videos\QHD 1440p\Mohnish Pabrai_ FASTEST Way To Financial Freedom! Proven Playbook For Quitting Your 9-5 In 9 Months! [qgeQ5kMVwRA].webm"
OUTPUT_DIR = r"C:\Youtube Channels\Videos\Temp Videos"
BASE_DIR = r"d:\Open Short"

MODEL_TFLITE = os.path.join(BASE_DIR, "blaze_face_short_range.tflite")
YOLO_MODEL_PATH = os.path.join(BASE_DIR, "yolov8n.pt")
OUTRO_PATH = os.path.join(OUTPUT_DIR, "OUTRO_D_3.5s.mp4")

SPEED = 1.20

CLIPS_CONFIG = [
    {
        "id": "01",
        "title": "01 - He Exposed the #1 Secret Banks Don't Want You to Know [SHORTS_FINAL].mp4",
        "ss": 3916.80,
        "dur": 62.20,
        "hook": "THE MATH NOBODY TAUGHT YOU",
        "topic": "The Magic of Compounding & The Rule of 72",
        "zoom_beats": [
            (8.0, 16.0),
            (28.0, 38.0),
            (48.0, 58.0)
        ]
    },
    {
        "id": "02",
        "title": "02 - A Billionaire Just Destroyed Everything You Believe About Risk [SHORTS_FINAL].mp4",
        "ss": 448.80,
        "dur": 67.60,
        "hook": "THE BIGGEST LIE IN BUSINESS",
        "topic": "Entrepreneurs Do NOT Take Risks",
        "zoom_beats": [
            (7.0, 15.0),
            (26.0, 37.0),
            (48.0, 62.0)
        ]
    },
    {
        "id": "03",
        "title": "03 - Billionaire Investor - Stop Trying to Be Original [SHORTS_FINAL].mp4",
        "ss": 0.00,
        "dur": 60.50,
        "hook": "COPYING = GENIUS?",
        "topic": "Cloning: Why Copying Beats Inventing",
        "zoom_beats": [
            (5.0, 14.0),
            (24.0, 35.0),
            (45.0, 56.0)
        ]
    }
]

def step1_cut_raw_clips():
    print("\n--- STEP 1: CUTTING RAW CLIPS IN 1440p ---")
    for c in CLIPS_CONFIG:
        raw_path = os.path.join(BASE_DIR, f"pabrai_raw_{c['id']}.mp4")
        if os.path.exists(raw_path) and os.path.getsize(raw_path) > 1000000:
            print(f"[{c['id']}] {raw_path} already exists, skipping cut.")
            continue
        print(f"[{c['id']}] Cutting {c['dur']}s from {c['ss']}s...")
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", str(c["ss"]),
            "-i", SOURCE_VIDEO,
            "-t", str(c["dur"]),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            raw_path
        ]
        subprocess.run(cmd, check=True)
        print(f"[{c['id']}] Cut complete: {raw_path}")

def step2_transcribe_words(whisper_model):
    print("\n--- STEP 2: TRANSCRIBING WORD TIMESTAMPS ---")
    for c in CLIPS_CONFIG:
        raw_path = os.path.join(BASE_DIR, f"pabrai_raw_{c['id']}.mp4")
        json_path = os.path.join(BASE_DIR, f"pabrai_words_{c['id']}.json")
        wav_path = os.path.join(BASE_DIR, f"temp_audio_{c['id']}.wav")

        if os.path.exists(json_path) and os.path.getsize(json_path) > 100:
            print(f"[{c['id']}] Words JSON already exists: {json_path}")
            continue

        print(f"[{c['id']}] Extracting WAV audio...")
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", raw_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            wav_path
        ], check=True)

        with wave.open(wav_path, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

        print(f"[{c['id']}] Transcribing with word timestamps...")
        segments, _ = whisper_model.transcribe(audio, beam_size=5, word_timestamps=True, vad_filter=True)
        words = []
        for s in segments:
            for w in (s.words or []):
                word_clean = w.word.strip()
                if word_clean:
                    words.append({
                        "word": word_clean,
                        "start": round(w.start, 2),
                        "end": round(w.end, 2)
                    })

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(words, f, indent=2)

        print(f"[{c['id']}] Saved {len(words)} words to {json_path}")
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass

def build_ass_subtitles(words, hook_text, duration_scaled, ass_path, speed=1.0):
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

    def format_ts(sec):
        sec = max(0.0, sec)
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        cs = int(round((sec - int(sec)) * 100))
        if cs >= 100:
            cs = 99
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

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
    hook_end = min(3.0, duration_scaled)
    events.append(f"Dialogue: 1,0:00:00.00,{format_ts(hook_end)},Hook,,0,0,0,,{hook_text}")

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
    print(f"   [Subtitles] Generated ASS subtitles at {speed}x: {ass_path}")

def compute_crop_trajectory(video_path, clip_id):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 29.97
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    orig_w, orig_h = 2560, 1440
    crop_w, crop_h = 810, 1440
    max_x = orig_w - crop_w  # 1750
    center_default_x = (orig_w - crop_w) // 2  # 875

    base_options = mp_python.BaseOptions(model_asset_path=MODEL_TFLITE)
    options = mp_vision.FaceDetectorOptions(base_options=base_options, min_detection_confidence=0.30)
    mp_detector = mp_vision.FaceDetector.create_from_options(options)
    yolo_model = YOLO(YOLO_MODEL_PATH)

    print(f"   [Tracking] Analyzing {total_frames} frames ({total_frames/fps:.1f}s at {fps:.2f} fps)...")

    stride = 3
    small_w = 640
    small_h = 360
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
            rgb = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = mp_detector.detect(mp_image)

            best_target_x = None

            if result.detections:
                t_sec = f_idx / fps
                faces = []
                for d in result.detections:
                    b = d.bounding_box
                    cx = (b.origin_x + b.width / 2) * scale_factor
                    faces.append((cx, b.width * b.height * (scale_factor**2)))

                if clip_id == "03":
                    # Clip 03: Host Steven Bartlett speaks at 0.0 - 2.0s and 16.5 - 19.0s (face on the right, cx > 1400)
                    if (t_sec < 2.0) or (16.5 <= t_sec < 19.0):
                        best_face = max(faces, key=lambda f: f[0])
                    else:
                        best_face = min(faces, key=lambda f: f[0])
                    best_target_x = best_face[0] - crop_w / 2
                else:
                    # Clip 01 & 02: Mohnish Pabrai close-up/medium shot (around cx ≈ 800 - 1100)
                    best_face = min(faces, key=lambda f: abs(f[0] - 950))
                    best_target_x = best_face[0] - crop_w / 2
            else:
                y_res = yolo_model(frame_small, classes=[0], verbose=False)
                persons = []
                for r in y_res:
                    for b in r.boxes:
                        xyxy = [int(x * scale_factor) for x in b.xyxy[0]]
                        cx = (xyxy[0] + xyxy[2]) / 2
                        persons.append(cx)
                if persons:
                    t_sec = f_idx / fps
                    if clip_id == "03" and ((t_sec < 2.0) or (16.5 <= t_sec < 19.0)):
                        target_cx = max(persons)
                    else:
                        target_cx = min(persons, key=lambda x: abs(x - 950))
                    best_target_x = target_cx - crop_w / 2

            if best_target_x is not None:
                detected_targets[f_idx] = max(0, min(int(best_target_x), max_x))

        f_idx += 1

    proc.stdout.close()
    proc.wait()

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
        if abs(diff) > 40:
            speed_px = 12.0 if abs(diff) > 200 else 4.0
            direction = 1 if diff > 0 else -1
            current_x += direction * speed_px
            if (direction == 1 and current_x > target_x) or (direction == -1 and current_x < target_x):
                current_x = target_x

        xs.append(max(0, min(int(round(current_x)), max_x)))

    return xs, fps

def compute_slow_zoom_curve(n_frames, fps, zoom_beats, max_zoom=1.12):
    zooms = [1.0] * n_frames
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

def compute_crop_boxes(xs, zooms, crop_w=810, crop_h=1440, orig_w=2560, orig_h=1440):
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
    print(f"   [Sendcmd] Generated dynamic crop instructions: {len(lines)} changes")

def render_short(c):
    cid = c["id"]
    raw_path = os.path.join(BASE_DIR, f"pabrai_raw_{cid}.mp4")
    json_path = os.path.join(BASE_DIR, f"pabrai_words_{cid}.json")
    final_output = os.path.join(OUTPUT_DIR, c["title"])

    print(f"\n=================================================================")
    print(f"🚀 RENDERING SHORT #{cid}: {c['title']}")
    print(f"=================================================================")

    workdir = os.path.join(BASE_DIR, f"work_pabrai_{cid}")
    os.makedirs(workdir, exist_ok=True)

    with open(json_path, "r", encoding="utf-8") as f:
        words = json.load(f)

    xs_cache_path = os.path.join(workdir, f"xs_{cid}.json")
    if os.path.exists(xs_cache_path):
        print(f"   [Tracking] Loaded cached tracking trajectory: {xs_cache_path}")
        with open(xs_cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            xs = data["xs"]
            fps = data["fps"]
    else:
        xs, fps = compute_crop_trajectory(raw_path, cid)
        with open(xs_cache_path, "w", encoding="utf-8") as f:
            json.dump({"xs": xs, "fps": fps}, f)

    duration_orig = len(xs) / fps
    duration_scaled = duration_orig / SPEED

    zooms = compute_slow_zoom_curve(len(xs), fps, c["zoom_beats"], max_zoom=1.12)
    boxes = compute_crop_boxes(xs, zooms)

    ass_path = os.path.join(workdir, f"subtitles_{cid}.ass")
    build_ass_subtitles(words, c["hook"], duration_scaled, ass_path, speed=SPEED)

    cmd_path = os.path.join(workdir, f"cmd_{cid}.txt")
    generate_sendcmd_boxes(boxes, fps, cmd_path, speed=SPEED)

    reframed_path = os.path.join(workdir, f"reframed_{cid}.mp4")
    safe_cmd_path = os.path.relpath(cmd_path, BASE_DIR).replace("\\", "/")
    safe_ass_path = os.path.relpath(ass_path, BASE_DIR).replace("\\", "/")

    first_w, first_h, first_x, first_y = boxes[0]
    filtergraph = (
        f"[0:v]setpts=PTS/{SPEED},"
        f"sendcmd=f={safe_cmd_path},"
        f"crop@c=w={first_w}:h={first_h}:x={first_x}:y={first_y},"
        f"scale=1080:1920:flags=lanczos,setsar=1,"
        f"ass={safe_ass_path}[v];"
        f"[0:a]atempo={SPEED}[a]"
    )

    print(f"   [Render] Rendering 9:16 vertical reframe at {SPEED}x with motion zooms & burned subtitles...")
    reframe_cmd = [
        "ffmpeg", "-y", "-loglevel", "warning",
        "-i", raw_path,
        "-filter_complex", filtergraph,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        reframed_path
    ]
    subprocess.run(reframe_cmd, cwd=BASE_DIR, check=True)
    print(f"   [Render] Reframed, zoomed & subtitled: {reframed_path}")

    print(f"   [Outro] Appending Outro bumper: {OUTRO_PATH}...")
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
        "-i", OUTRO_PATH,
        "-filter_complex", concat_filter,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        final_output
    ]
    subprocess.run(final_cmd, cwd=BASE_DIR, check=True)
    print(f"   [Complete] Saved final video -> {final_output}")

def main():
    print("=================================================================")
    print("🔥 MOHNISH PABRAI TOP 3 VIRAL SHORTS AUTOMATED PIPELINE 🔥")
    print("=================================================================")

    # Step 1: Cut raw source clips
    step1_cut_raw_clips()

    # Step 2: Transcribe words with Faster-Whisper
    print("\nLoading Faster-Whisper model ('small', cpu, int8)...")
    whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
    print("Whisper model loaded!")
    step2_transcribe_words(whisper_model)

    # Step 3 - 7: Render each clip
    for c in CLIPS_CONFIG:
        render_short(c)

    print("\n=================================================================")
    print("🏁 ALL 3 TOP VIRAL SHORTS GENERATED SUCCESSFULLY!")
    print("=================================================================")

if __name__ == "__main__":
    main()
