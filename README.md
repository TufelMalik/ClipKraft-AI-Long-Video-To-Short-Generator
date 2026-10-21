# ClipKraft — AI Long Video To Short Generator

ClipKraft converts long-form videos into high-retention 9:16 vertical shorts with AI moment detection, manual timestamp clipping, active speaker tracking, cinematic motion zooms, animated karaoke subtitles, hook banners, and seamless social publishing.

> **Security Notice**: This repository is public. Never commit API keys, `.env`, keystores, credentials, uploaded videos, or generated outputs.

---

## 🌟 Key Features

### 1. Dual-Mode Workflow
- **Open-Shorts (AI Mode)**: Upload a video or paste a YouTube URL. AI identifies viral moments, selects layouts, transcribes speech, and extracts clips automatically.
- **Edit Video (Manual Mode)**: Full creator control over exact viral timestamps:
  - Add multiple start and end timestamps (`00:15` to `01:30`, `90.5s`, `02:15.5`, etc.).
  - Custom viral hook text per clip.
  - Automatic **1.20x speedup** with pitch-preserved audio.
  - Automatic **Outro bumper video** appended seamlessly to every clip.

### 2. Smart AI Framing & Active Speaker Tracking
- Uses **MediaPipe Tasks Vision** (`blaze_face_short_range.tflite`) and **YOLO** fallback.
- Decodes audio energy and visual lip activity to track active speakers dynamically in 9:16 vertical framing without jerky jumps.

### 3. Professional Motion Zooms
- Procedural **Cinematic Zoom In & Zoom Out Animations** (punch-zooms at cuts and smooth camera drift) to boost audience retention.

### 4. Viral Hooks & Karaoke Subtitles
- **Eye-Catching Hook Banner**: Top center banner for the first 3.0s styled with **bold yellow text on a solid black background box**.
- **Word-by-Word Karaoke Subtitles**: Powered by **Faster-Whisper** with zero-gap flicker elimination and dynamic pop scaling on the active spoken word.
- **Full Non-Destructive Restyling**: Clean baseline videos are preserved alongside subtitled cuts, enabling instant restyling, font/color adjustments, or custom caption text editing in the Subtitle Modal without double-burning.

### 5. Extended Retention & Optional Social Keys
- **1-Week Retention**: Jobs and generated shorts are kept for **7 days (604,800 seconds)** before cleanup.
- **Decoupled Social Publishing**: An Upload-Post API key is **never required** to generate clips or use the editor. It is only prompted when you choose to post/schedule clips to TikTok, Instagram Reels, or YouTube Shorts.

---

## 💻 System Requirements

- **Operating System**: Windows 10 / 11, Linux, or macOS
- **Memory**: 8 GB RAM minimum (16 GB recommended)
- **Disk Space**: 15–20 GB free space for models, virtual environment, and FFmpeg caches
- **Software**: Python 3.10–3.12, Node.js 18+, FFmpeg with `libass` support, Git
- **AI Keys**: Google Gemini API key (free tier available at [Google AI Studio](https://aistudio.google.com/app/apikey))

---

## 🚀 Quick Start (Native Windows — 1-Click)

The fastest way to run ClipKraft on Windows without Docker:

### 1. Clone & Setup

```powershell
git clone https://github.com/TufelMalik/ClipKraft-AI-Long-Video-To-Short-Generator.git "D:\Open Short"
cd "D:\Open Short"
```

### 2. Configure Environment (`.env`)

Create your `.env` file from `.env.example`:

```powershell
Copy-Item .env.example .env
```

Open `.env` and set your Gemini API key:

```dotenv
GEMINI_API_KEY=your_gemini_api_key_here
JOB_RETENTION_SECONDS=604800
```

### 3. Run with 1-Click Launcher

Double-click or run:

```powershell
.\run.bat
```

This automatically:
1. Detects or creates the Python virtual environment (`.venv`).
2. Installs backend dependencies (`faster-whisper`, `mediapipe`, `ultralytics`, `fastapi`, `uvicorn`, etc.).
3. Installs frontend dependencies (`npm install` in `dashboard/`).
4. Launches the FastAPI backend on **`http://localhost:8000`**.
5. Launches the Vite dashboard on **`http://localhost:5173`**.

---

## 🐳 Docker Deployment (Alternative)

If you prefer running via Docker Desktop with WSL 2:

```powershell
# 1. Build and start containers
docker compose up -d --build

# 2. Open dashboard
http://localhost:5175

# 3. View logs
docker compose logs -f
```

---

## 🛠️ Configuration Reference (`.env`)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | *Required* | API key for Gemini models (moment picking, titles, descriptions). |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Model for transcript analysis and scoring. |
| `JOB_RETENTION_SECONDS` | `604800` | Duration to keep generated clips and jobs before cleanup (7 days / 1 week). |
| `WHISPER_MODEL` | `base` | Faster-Whisper model size (`base`, `small`, `medium`). |
| `WHISPER_DEVICE` | `cpu` | Device for whisper (`cpu` or `cuda`). |
| `WHISPER_COMPUTE` | `int8` | Compute type for whisper (`int8` or `float16`). |
| `UPLOAD_POST_API_KEY` | *Optional* | Key for Upload-Post social publishing (prompted only on post). |

---

## 📁 Repository Structure

```
D:\Open Short\
├── app.py                      # FastAPI application & REST endpoints
├── run.bat                     # 1-click Windows native launcher
├── .env                        # Local environment variables & API keys
├── backend\
│   ├── pipeline\
│   │   ├── manual_clip_pipeline.py # Manual clipping, face tracking, zoom & ASS subtitles
│   │   ├── subtitles.py            # OpenShorts ASS/SRT caption rendering engine
│   │   ├── active_speaker.py       # Audio-visual active face tracking
│   │   └── recut.py                # EDL recut & virtual transcript engine
│   └── services\
│       └── manual_clip_worker.py   # Background job executor for manual clips
├── dashboard\                  # React + Vite frontend dashboard
│   ├── src\
│   │   ├── App.jsx             # Main dashboard shell & tab controller
│   │   └── components\
│   │       ├── ManualClipTab.jsx   # Dedicated Edit Video tab UI
│   │       ├── ResultCard.jsx      # Video card with player, subtitle modal & post modal
│   │       └── SubtitleModal.jsx   # Interactive word caption editor & style preview
└── tests\                      # Pipeline test suites
```

---

## 🔒 Security Best Practices

Before pushing code:
```powershell
git status --short
git diff --check
git check-ignore -v .env
```
- Never commit `.env`, `*.jks`, `*.keystore`, or secret keys.
- Upload keys and keystore files are write-protected and strictly excluded by `.gitignore`.

---

## 📄 License & Credits

Based on the open-source [OpenShorts](https://github.com/mutonby/openshorts) project. Enhanced with custom manual viral clipping, motion zoom animations, active speaker framing, and non-destructive subtitle synchronization.
