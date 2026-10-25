@echo off
title OpenShorts Launcher
set "REPO_ROOT=%~dp0"
cd /d "%REPO_ROOT%"

echo Starting OpenShorts Backend...
start "OpenShorts Backend" cmd /k "cd /d "%REPO_ROOT%" && .venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000"

echo Starting OpenShorts Frontend...
start "OpenShorts Frontend" cmd /k "cd /d "%REPO_ROOT%dashboard" && set VITE_PROXY_TARGET=http://localhost:8000 && npm run dev"

ping 127.0.0.1 -n 4 >nul
start http://localhost:5173/index.html

echo OpenShorts is running!
