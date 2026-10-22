import os
import sys
import json
import wave
import subprocess
import numpy as np

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from faster_whisper import WhisperModel

CLIPS_TO_TRANSCRIBE = [
    {
        "id": "03",
        "video": r"C:\Youtube Channels\Videos\Temp Videos\03 - Earning More Isn't the Whole Answer - Mike Rowe.mp4",
        "output_json": r"d:\Open Short\clip3_words.json"
    },
    {
        "id": "04",
        "video": r"C:\Youtube Channels\Videos\Temp Videos\04 - What QVC Taught Mike Rowe About Trust.mp4",
        "output_json": r"d:\Open Short\clip4_words.json"
    },
    {
        "id": "05",
        "video": r"C:\Youtube Channels\Videos\Temp Videos\05 - Passion vs Skill - Mike Rowe's Career Lesson.mp4",
        "output_json": r"d:\Open Short\clip5_words.json"
    },
    {
        "id": "06",
        "video": r"C:\Youtube Channels\Videos\Temp Videos\06 - Mike Rowe on Choosing Difficult Work.mp4",
        "output_json": r"d:\Open Short\clip6_words.json"
    }
]

def main():
    print("Loading Faster-Whisper model ('small', cpu, int8)...")
    model = WhisperModel("small", device="cpu", compute_type="int8")
    print("Model loaded successfully!")

    for item in CLIPS_TO_TRANSCRIBE:
        cid = item["id"]
        vpath = item["video"]
        jpath = item["output_json"]

        if os.path.exists(jpath):
            print(f"[Clip {cid}] {jpath} already exists, skipping transcription.")
            continue

        wav_path = os.path.join(r"d:\Open Short", f"temp_audio_{cid}.wav")
        print(f"\n[Clip {cid}] Extracting audio from {os.path.basename(vpath)}...")
        extract_cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", vpath,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            wav_path
        ]
        subprocess.run(extract_cmd, check=True)

        with wave.open(wav_path, "rb") as wf:
            n_frames = wf.getnframes()
            frames = wf.readframes(n_frames)
            audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

        dur_sec = len(audio) / 16000.0
        print(f"   Transcribing audio ({dur_sec:.1f}s) with word timestamps...")
        segments, info = model.transcribe(audio, beam_size=5, word_timestamps=True, vad_filter=True)

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

        with open(jpath, "w", encoding="utf-8") as f:
            json.dump(words, f, indent=2)

        print(f"   [Clip {cid}] Generated {len(words)} word timestamps -> {jpath}")

        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass

    print("\nALL 4 CLIPS TRANSCRIBED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
