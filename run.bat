@echo off
title OpenShorts Launcher
set "REPO_ROOT=%~dp0"
cd /d "%REPO_ROOT%"

where python >nul 2>&1
if not errorlevel 1 (
    python "%REPO_ROOT%run.py" %*
) else (
    if exist "%REPO_ROOT%.venv\Scripts\python.exe" (
        "%REPO_ROOT%.venv\Scripts\python.exe" "%REPO_ROOT%run.py" %*
    ) else (
        echo Python was not found. Install Python and the dependencies first.
        pause
        exit /b 1
    )
)
if errorlevel 1 (
    echo See .cache\launcher\backend.log and frontend.log for details.
    pause
    exit /b 1
)
