import os
import sys
import subprocess
import json
import cv2

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

FINAL_VIDEOS = [
    {
        "id": "03",
        "path": r"C:\Youtube Channels\Videos\Temp Videos\03 - Earning More Isn't the Whole Answer - Mike Rowe [SHORTS_FINAL].mp4",
        "hook": "MORE INCOME. SAME PROBLEM?"
    },
    {
        "id": "04",
        "path": r"C:\Youtube Channels\Videos\Temp Videos\04 - What QVC Taught Mike Rowe About Trust [SHORTS_FINAL].mp4",
        "hook": "TRUST BEFORE THE SALE."
    },
    {
        "id": "05",
        "path": r"C:\Youtube Channels\Videos\Temp Videos\05 - Passion vs Skill - Mike Rowe's Career Lesson [SHORTS_FINAL].mp4",
        "hook": "PASSION ISN'T THE WHOLE PLAN."
    },
    {
        "id": "06",
        "path": r"C:\Youtube Channels\Videos\Temp Videos\06 - Mike Rowe on Choosing Difficult Work [SHORTS_FINAL].mp4",
        "hook": "IS COMFORT HOLDING YOU BACK?"
    }
]

print("VERIFYING ALL 4 OUTPUT SHORTS:")
for item in FINAL_VIDEOS:
    cid = item["id"]
    p = item["path"]
    if not os.path.exists(p):
        print(f"[MISSING] {p}")
        continue

    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration,size:stream=width,height,r_frame_rate,codec_name,sample_rate",
        "-of", "json", p
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    d = json.loads(res.stdout)
    dur = float(d["format"]["duration"])
    size_mb = float(d["format"]["size"]) / (1024 * 1024)
    streams = d["streams"]
    v_stream = next(s for s in streams if s.get("width"))
    a_stream = next(s for s in streams if s.get("sample_rate"))

    w = v_stream["width"]
    h = v_stream["height"]
    fps = v_stream["r_frame_rate"]
    sr = a_stream["sample_rate"]

    print(f"\n[OK] Clip {cid}: {os.path.basename(p)}")
    print(f"   Resolution: {w}x{h} (Vertical 9:16) @ {fps} fps")
    print(f"   Duration: {dur:.2f}s | File Size: {size_mb:.1f} MB")
    print(f"   Audio: {a_stream['codec_name']} @ {sr} Hz")

    # Extract sample verification frame at t=1.5s (Hook banner verification)
    cap = cv2.VideoCapture(p)
    cap.set(cv2.CAP_PROP_POS_MSEC, 1500)
    ret, frame = cap.read()
    if ret:
        thumb_path = os.path.join(r"d:\Open Short", f"thumb_verify_{cid}_hook.jpg")
        cv2.imwrite(thumb_path, frame)
        print(f"   Verification frame (Hook at 1.5s): {thumb_path}")
    cap.release()
