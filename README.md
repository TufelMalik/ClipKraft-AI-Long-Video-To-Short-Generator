# ClipKraft — AI Long Video To Short Generator

ClipKraft converts long-form videos into vertical clips with AI moment detection, smart reframing, subtitles, hook text, and optional dubbing. This repository is configured for a simple Docker-based Windows setup.

> This is a public repository. Never commit API keys, `.env`, credential files, uploaded videos, or generated output.

## What you need

- Windows 10 or Windows 11
- 8 GB RAM minimum; 16 GB recommended
- At least 15–20 GB free disk space for Docker images and AI models
- Git
- Docker Desktop with the WSL 2 backend
- Hardware virtualization enabled in BIOS/UEFI (`Intel VT-x` or `AMD SVM`)
- A Google Gemini API key for AI features

Optional services:

- `fal.ai` for AI actors and generated video
- ElevenLabs for voiceover and dubbing
- Upload-Post for direct social publishing

## 1. Clone the repository

Open PowerShell and run:

```powershell
git clone https://github.com/TufelMalik/ClipKraft-AI-Long-Video-To-Short-Generator.git "D:\Open Short"
cd "D:\Open Short"
```

If the folder already exists and contains this repository:

```powershell
cd "D:\Open Short"
git pull
```

## 2. Install Docker and WSL 2

Install Docker Desktop. If WSL 2 is not installed, open PowerShell as Administrator and run:

```powershell
wsl --install
```

Restart Windows. Open Docker Desktop, complete its first-run setup, and wait until **Docker Engine is running**.

If Docker reports that virtualization is disabled, enable `Intel VT-x`, `Intel Virtualization Technology`, or `AMD SVM` in BIOS/UEFI.

## 3. Create the local configuration

Create your private `.env` file:

```powershell
Copy-Item .env.example .env
```

Open `.env` in a text editor and add:

```dotenv
GEMINI_API_KEY=your_gemini_api_key_here
```

Do not add quotes unless they are part of the actual value. Do not paste the key into `README.md`, source code, screenshots, issues, or commits.

The included Docker Compose configuration loads `.env` into the backend container. `.env` and common local key files are excluded by `.gitignore`.

## 4. Start OpenShorts

From `D:\Open Short`, run:

```powershell
docker compose up -d --build
```

The first build can take several minutes because Docker downloads images, packages, and AI dependencies.

Open the dashboard:

```text
http://localhost:5175
```

Backend API:

```text
http://localhost:8000
```

## 5. Verify the installation

Check running containers:

```powershell
docker compose ps
```

Follow logs without displaying the contents of `.env`:

```powershell
docker compose logs -f
```

Expected services:

- `openshorts-backend`
- `openshorts-frontend`
- `openshorts-renderer`

## Everyday commands

Start:

```powershell
docker compose up -d
```

Stop:

```powershell
docker compose down
```

Restart after changing `.env`:

```powershell
docker compose up -d --force-recreate
```

Rebuild after updating the code:

```powershell
git pull
docker compose up -d --build
```

## Troubleshooting

### Docker daemon is not running

Open Docker Desktop and wait until it reports that the engine is running, then retry:

```powershell
docker compose up -d --build
```

### WSL or virtualization error

Restart Windows after installing WSL. If the error remains, enable virtualization in BIOS/UEFI and confirm Docker Desktop is using the WSL 2 backend.

### Port already in use

Open `docker-compose.yml` and change the host side of the conflicting mapping. For example, change `5175:5173` to `5176:5173`, then open `http://localhost:5176`.

### Gemini key is not detected

Confirm `.env` contains a non-empty `GEMINI_API_KEY` entry, then recreate the backend:

```powershell
docker compose up -d --force-recreate backend
```

Never paste the key into terminal output or public support messages.

## Security checklist before every push

```powershell
git status --short
git diff --check
git check-ignore -v .env Gemini_API_KEY.txt
```

Before committing, confirm that no secret file is staged:

```powershell
git diff --cached --name-only
```

If a secret was ever committed, removing the file is not enough: revoke/rotate the credential immediately and clean the Git history before publishing.

## Credits

This project is based on the open-source [OpenShorts](https://github.com/mutonby/openshorts) project. Refer to the upstream repository for full feature documentation, licensing, and advanced deployment options.
