@echo off
title OpenShorts Launcher
cd /d "D:\Open Short"

echo Starting OpenShorts Backend...
start "OpenShorts Backend" cmd /k "cd /d D:\Open Short && .venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000"

echo Starting OpenShorts Frontend...
start "OpenShorts Frontend" cmd /k "cd /d D:\Open Short\dashboard && set VITE_PROXY_TARGET=http://localhost:8000 && npm run dev"

timeout /t 3 /nobreak >nul
start http://localhost:5173/index.html

echo OpenShorts is running!
