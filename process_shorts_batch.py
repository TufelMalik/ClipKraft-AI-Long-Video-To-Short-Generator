import os
import sys
import json
import wave
import subprocess
import cv2
import numpy as np

# MediaPipe Tasks Face Detection
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# YOLO Fallback
from ultralytics import YOLO

MODEL_TFLITE = r"d:\Open Short\blaze_face_short_range.tflite"
YOLO_MODEL_PATH = r"d:\Open Short\yolov8n.pt"

OUTRO_PATH = r"C:\Youtube Channels\Videos\Temp Videos\OUTRO_D_3.5s.mp4"
SPEED = 1.20  # 1.20x playback speed

CLIPS = [
    {
        "id": "01",
        "input": r"C:\Youtube Channels\Videos\Temp Videos\01 - Mike Rowe - Find Opportunity Where Others Won't Look.mp4",
        "output": r"C:\Youtube Channels\Videos\Temp Videos\01 - Mike Rowe - Find Opportunity Where Others Won't Look [SHORTS_FINAL].mp4",
        "hook": "BORING JOB. REAL OPPORTUNITY?",
        "words_json": r"d:\Open Short\clip1_words.json",
        # Required emphasis moments for slow zoom in / out (in source seconds)
        "zoom_beats": [
            (9.5, 15.5),   # Mastering a trade & reverse commute
            (26.5, 36.5)   # Going in the other direction & find opportunity
        ]
    },
    {
        "id": "02",
        "input": r"C:\Youtube Channels\Videos\Temp Videos\02 - Looking Rich vs Building Wealth - Mike Rowe.mp4",
        "output": r"C:\Youtube Channels\Videos\Temp Videos\02 - Looking Rich vs Building Wealth - Mike Rowe [SHORTS_FINAL].mp4",
        "hook": "LOOKING RICH IS EXPENSIVE.",
        "words_json": r"d:\Open Short\clip2_words.json",
        # Required emphasis moments for slow zoom in / out (in source seconds)
        "zoom_beats": [
            (21.0, 31.0),   # People feeling lesser than all the time
            (47.0, 58.0),   # Confused living life to the hilt of spending
            (70.5, 77.0),   # What's in your garage right now?
            (91.0, 107.0)   # Status life defined by stuff in garage
        ]
    }
]

def load_words(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def build_ass_subtitles(words, hook_text, duration_scaled, ass_path, speed=1.0):
    """
    Builds ASS subtitle file with:
    - 3.0s top hook banner with a solid black background box and larger text
    - Word-by-word animated karaoke captions scaled to playback speed
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
    
    # 3.0s Hook Banner with solid black background box
    hook_end = min(3.0, duration_scaled)
    events.append(f"Dialogue: 1,0:00:00.00,{format_ts(hook_end)},Hook,,0,0,0,,{hook_text}")

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
    print(f"   📝 Generated ASS subtitles at {speed}x with 3.0s black-box Hook: {ass_path}")

def compute_crop_trajectory(video_path, clip_info):
    """
    Computes smooth horizontal crop center X for 9:16 vertical video.
    """
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 29.97
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    orig_w, orig_h = 2560, 1440
    crop_w, crop_h = 810, 1440
    max_x = orig_w - crop_w  # 1750
    center_default_x = (orig_w - crop_w) // 2  # 875

    base_options = python.BaseOptions(model_asset_path=MODEL_TFLITE)
    options = vision.FaceDetectorOptions(base_options=base_options, min_detection_confidence=0.4)
    mp_detector = vision.FaceDetector.create_from_options(options)

    yolo_model = YOLO(YOLO_MODEL_PATH)

    print(f"   🎥 Analyzing {total_frames} frames ({total_frames/fps:.1f}s at {fps:.2f} fps)...")

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

                if clip_info["id"] == "01":
                    if t_sec < 3.8:
                        best_face = max(faces, key=lambda f: f[0])
                    else:
                        best_face = min(faces, key=lambda f: abs(f[0] - 1200))
                    best_target_x = best_face[0] - crop_w / 2
                elif clip_info["id"] == "02":
                    if 70.0 <= t_sec <= 72.0 or 74.0 <= t_sec <= 80.5:
                        best_face = max(faces, key=lambda f: f[0])
                    else:
                        if len(faces) >= 2:
                            best_face = min(faces, key=lambda f: f[0])
                        else:
                            best_face = faces[0]
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
                    if clip_info["id"] == "01":
                        if t_sec < 3.8:
                            target_cx = max(persons)
                        else:
                            target_cx = min(persons, key=lambda x: abs(x - 1200))
                    else:
                        if 70.0 <= t_sec <= 72.0 or 74.0 <= t_sec <= 80.5:
                            target_cx = max(persons)
                        else:
                            target_cx = min(persons)
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
    """
    Computes a gentle, slow zoom curve (1.0x -> max_zoom -> 1.0x) only at required emphasis beats.
    Uses smoothstep easing for slow, natural camera push and pull.
    """
    zooms = [1.0] * n_frames
    rise_s = 1.3  # Slow push in
    fall_s = 1.3  # Slow pull out
    
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
    """
    Computes (w, h, x, y) for each frame, smoothly scaling around the tracked subject.
    """
    boxes = []
    for i, x in enumerate(xs):
        z = zooms[i] if i < len(zooms) else 1.0
        w = int(crop_w / z)
        h = int(crop_h / z)
        w -= w % 2
        h -= h % 2
        w = max(2, min(w, orig_w))
        h = max(2, min(h, orig_h))

        # Center zoom on the tracked subject
        cx = x + crop_w / 2.0
        cy = crop_h / 2.0
        nx = int(round(cx - w / 2.0))
        ny = int(round(cy - h / 2.0))
        nx = max(0, min(nx, orig_w - w))
        ny = max(0, min(ny, orig_h - h))
        
        boxes.append((w, h, nx - (nx % 2), ny - (ny % 2)))
    return boxes

def generate_sendcmd_boxes(boxes, fps, cmd_path, speed=1.0):
    """
    Emits deduped sendcmd lines for w, h, x, y.
    """
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
    print(f"   🎯 Generated sendcmd instructions (slow zooms + tracking): {len(lines)} changes")

def process_clip(clip_info, speed=SPEED):
    clip_id = clip_info["id"]
    in_video = clip_info["input"]
    out_video = clip_info["output"]
    hook_text = clip_info["hook"]
    words_json = clip_info["words_json"]
    zoom_beats = clip_info.get("zoom_beats", [])

    print(f"\n=======================================================")
    print(f"🚀 PROCESSING CLIP {clip_id} (1.2x Speed + Slow Punch-In Zooms): {os.path.basename(in_video)}")
    print(f"=======================================================")

    workdir = os.path.join(r"d:\Open Short", f"work_{clip_id}")
    os.makedirs(workdir, exist_ok=True)

    words = load_words(words_json)

    # 1. Compute crop trajectory and slow zoom curves (cached for speed)
    xs_cache_path = os.path.join(workdir, f"xs_{clip_id}.json")
    if os.path.exists(xs_cache_path):
        print(f"   ⚡ Loaded cached tracking trajectory: {xs_cache_path}")
        with open(xs_cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            xs = data["xs"]
            fps = data["fps"]
    else:
        xs, fps = compute_crop_trajectory(in_video, clip_info)
        with open(xs_cache_path, "w", encoding="utf-8") as f:
            json.dump({"xs": xs, "fps": fps}, f)

    duration_orig = len(xs) / fps
    duration_scaled = duration_orig / speed

    zooms = compute_slow_zoom_curve(len(xs), fps, zoom_beats, max_zoom=1.12)
    boxes = compute_crop_boxes(xs, zooms)

    # 2. Generate ASS Subtitles (scaled to speed, 3.0s hook with black bg box)
    ass_path = os.path.join(workdir, f"subtitles_{clip_id}.ass")
    build_ass_subtitles(words, hook_text, duration_scaled, ass_path, speed=speed)

    # 3. Generate sendcmd file with dynamic w/h/x/y
    cmd_path = os.path.join(workdir, f"cmd_{clip_id}.txt")
    generate_sendcmd_boxes(boxes, fps, cmd_path, speed=speed)

    # 4. Reframe to 9:16 (1080x1920) with slow zoom in/out, speed multiplier, and burned subtitles
    reframed_path = os.path.join(workdir, f"reframed_{clip_id}.mp4")
    safe_cmd_path = os.path.relpath(cmd_path, r"d:\Open Short").replace("\\", "/")
    safe_ass_path = os.path.relpath(ass_path, r"d:\Open Short").replace("\\", "/")

    first_w, first_h, first_x, first_y = boxes[0]
    filtergraph = (
        f"[0:v]setpts=PTS/{speed},"
        f"sendcmd=f={safe_cmd_path},"
        f"crop@c=w={first_w}:h={first_h}:x={first_x}:y={first_y},"
        f"scale=1080:1920:flags=lanczos,setsar=1,"
        f"ass={safe_ass_path}[v];"
        f"[0:a]atempo={speed}[a]"
    )

    print(f"   🎬 Rendering 9:16 vertical reframe at {speed}x with slow zooms & burned subtitles...")
    reframe_cmd = [
        "ffmpeg", "-y", "-loglevel", "warning",
        "-i", in_video,
        "-filter_complex", filtergraph,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        reframed_path
    ]
    subprocess.run(reframe_cmd, check=True)
    print(f"   ✅ Reframed, zoomed & subtitled: {reframed_path}")

    # 5. Append Outro Video (outro stays at natural 3.5s speed)
    print(f"   🔗 Appending Outro: {OUTRO_PATH}...")
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
        out_video
    ]
    subprocess.run(final_cmd, check=True)
    print(f"   🎉 COMPLETED CLIP {clip_id}: {out_video}")

if __name__ == "__main__":
    for clip in CLIPS:
        process_clip(clip, speed=SPEED)
    print(f"\n🏁 ALL CLIPS PROCESSED SUCCESSFULLY AT {SPEED}x SPEED WITH SLOW DYNAMIC ZOOMS!")
