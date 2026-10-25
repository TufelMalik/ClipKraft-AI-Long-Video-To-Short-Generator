# OpenShorts PowerShell Launcher
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "       Starting OpenShorts Application    " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$RepoRoot = $PSScriptRoot
if (-not $RepoRoot) { $RepoRoot = (Get-Location).Path }
Set-Location $RepoRoot

# 1. Start Backend on port 8000
Write-Host "[1/2] Starting OpenShorts Backend on http://127.0.0.1:8000..." -ForegroundColor Yellow
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "cd '$RepoRoot'; & '$RepoRoot\.venv\Scripts\python.exe' -m uvicorn app:app --host 127.0.0.1 --port 8000"

# 2. Start Frontend on port 5173
Write-Host "[2/2] Starting OpenShorts Frontend on http://localhost:5173..." -ForegroundColor Yellow
$FrontendDir = Join-Path $RepoRoot "dashboard"
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "cd '$FrontendDir'; `$env:VITE_PROXY_TARGET='http://127.0.0.1:8000'; npm run dev"

Start-Sleep -Seconds 3
Start-Process "http://localhost:5173/index.html"
Write-Host "`nOpenShorts is running! Keep both backend and frontend windows open." -ForegroundColor Green
