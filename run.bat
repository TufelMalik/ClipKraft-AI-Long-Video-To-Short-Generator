@echo off
title OpenShorts Launcher
set "REPO_ROOT=%~dp0"
cd /d "%REPO_ROOT%"

rem Reuse a healthy instance instead of failing on its occupied ports.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$backend = $false; $frontend = $false; try { $backend = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:8000/health').StatusCode -eq 200 } catch {}; try { $frontend = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:5173/').StatusCode -eq 200 } catch {}; if ($backend -and $frontend) { exit 10 }; exit 0"
if errorlevel 10 goto already_running

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
goto :eof

:already_running
echo OpenShorts is already running at http://localhost:5173/
if /i not "%~1"=="--no-browser" start "" "http://localhost:5173/"
exit /b 0
