@echo off
title OpenShorts - Clear Sessions and Clips
setlocal enabledelayedexpansion

set "REPO_ROOT=%~dp0"
cd /d "%REPO_ROOT%"

set "FORCE_FLAG="
set "NO_PAUSE="
for %%A in (%*) do (
    if /i "%%A"=="/y" (set "FORCE_FLAG=-Force" & set "NO_PAUSE=1")
    if /i "%%A"=="-y" (set "FORCE_FLAG=-Force" & set "NO_PAUSE=1")
    if /i "%%A"=="--force" (set "FORCE_FLAG=-Force" & set "NO_PAUSE=1")
    if /i "%%A"=="/f" (set "FORCE_FLAG=-Force" & set "NO_PAUSE=1")
    if /i "%%A"=="/nopause" set "NO_PAUSE=1"
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%clear_sessions.ps1" %FORCE_FLAG%

if errorlevel 1 (
    echo.
    echo [ERROR] An error occurred during session cleanup.
)

if not defined NO_PAUSE (
    echo.
    echo Press any key to exit...
    pause >nul
)
