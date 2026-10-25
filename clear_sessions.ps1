# OpenShorts Safe Session & Clips Cleaner
param (
    [switch]$Force,
    [switch]$KillProcesses
)

$RepoRoot = $PSScriptRoot
if (-not $RepoRoot) { $RepoRoot = (Get-Location).Path }
Set-Location $RepoRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "         OpenShorts Session & Clips Safe Cleaner            " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Workspace: $RepoRoot`n" -ForegroundColor DarkGray

# Check for running processes that might lock files
$lingering = Get-Process -Name ffmpeg, uvicorn -ErrorAction SilentlyContinue
if ($lingering) {
    Write-Host "[!] Detected running OpenShorts / FFmpeg processes:" -ForegroundColor Yellow
    foreach ($p in $lingering) {
        Write-Host "    - $($p.ProcessName) (PID: $($p.Id))" -ForegroundColor DarkYellow
    }
    if ($KillProcesses -or $Force) {
        Write-Host "Terminating lingering processes..." -ForegroundColor Yellow
        $lingering | Stop-Process -Force -ErrorAction SilentlyContinue
    } else {
        $ans = Read-Host "Would you like to stop these processes before cleaning? (Y/N)"
        if ($ans -match '^(y|yes)$') {
            $lingering | Stop-Process -Force -ErrorAction SilentlyContinue
            Write-Host "Processes stopped.`n" -ForegroundColor Green
        }
    }
}

if (-not $Force) {
    $confirm = Read-Host "Are you sure you want to clean all editing sessions, clips, and uploads? (Y/N)"
    if ($confirm -notmatch '^(y|yes)$') {
        Write-Host "Cleanup cancelled by user." -ForegroundColor Yellow
        exit 0
    }
}

$uploadsDir = Join-Path $RepoRoot "uploads"
$outputDir = Join-Path $RepoRoot "output"
$cacheDir = Join-Path $RepoRoot ".cache"

# Collect items to delete & measure size
$filesToDelete = @()

if (Test-Path $uploadsDir) {
    $filesToDelete += Get-ChildItem -Path $uploadsDir -Recurse -File -Force -ErrorAction SilentlyContinue
}

if (Test-Path $outputDir) {
    # Job subdirectories (preserve thumbnails folder and .instance file)
    $jobDirs = Get-ChildItem -Path $outputDir -Directory -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne "thumbnails" }
    foreach ($d in $jobDirs) {
        $filesToDelete += Get-ChildItem -Path $d.FullName -Recurse -File -Force -ErrorAction SilentlyContinue
    }
    $thumbDir = Join-Path $outputDir "thumbnails"
    if (Test-Path $thumbDir) {
        $filesToDelete += Get-ChildItem -Path $thumbDir -Recurse -File -Force -ErrorAction SilentlyContinue
    }
}

# Root temp/work folders
$tempDirs = Get-ChildItem -Path $RepoRoot -Directory -Force -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -like "temp_*" -or $_.Name -like "work_*" -or $_.Name -eq "inspection_frames"
}
foreach ($d in $tempDirs) {
    $filesToDelete += Get-ChildItem -Path $d.FullName -Recurse -File -Force -ErrorAction SilentlyContinue
}

# Camera caches in .cache/
if (Test-Path $cacheDir) {
    $cameraCaches = Get-ChildItem -Path $cacheDir -Directory -Filter "camera*" -Force -ErrorAction SilentlyContinue
    foreach ($d in $cameraCaches) {
        $filesToDelete += Get-ChildItem -Path $d.FullName -Recurse -File -Force -ErrorAction SilentlyContinue
    }
}

$totalBytes = ($filesToDelete | Measure-Object -Property Length -Sum).Sum
if (-not $totalBytes) { $totalBytes = 0 }
$totalMB = [math]::Round($totalBytes / 1MB, 2)

Write-Host "`nCleaning session files and media..." -ForegroundColor Yellow

$deletedCount = 0

# 1. Clean uploads
if (Test-Path $uploadsDir) {
    Get-ChildItem -Path $uploadsDir -Force -ErrorAction SilentlyContinue | ForEach-Object {
        Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
        $deletedCount++
    }
} else {
    New-Item -ItemType Directory -Path $uploadsDir -Force | Out-Null
}

# 2. Clean output job directories
if (Test-Path $outputDir) {
    # Remove job folders
    Get-ChildItem -Path $outputDir -Directory -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne "thumbnails" } | ForEach-Object {
        Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
        $deletedCount++
    }
    # Clean inside thumbnails folder, but preserve the directory itself
    $thumbDir = Join-Path $outputDir "thumbnails"
    if (Test-Path $thumbDir) {
        Get-ChildItem -Path $thumbDir -Force -ErrorAction SilentlyContinue | ForEach-Object {
            Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
            $deletedCount++
        }
    } else {
        New-Item -ItemType Directory -Path $thumbDir -Force | Out-Null
    }
} else {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $outputDir "thumbnails") -Force | Out-Null
}

# 3. Clean temp/work directories
foreach ($d in $tempDirs) {
    Remove-Item -Path $d.FullName -Recurse -Force -ErrorAction SilentlyContinue
    $deletedCount++
}

# 4. Clean camera caches
if (Test-Path $cacheDir) {
    Get-ChildItem -Path $cacheDir -Directory -Filter "camera*" -Force -ErrorAction SilentlyContinue | ForEach-Object {
        Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
        $deletedCount++
    }
}

# 5. Clean stray sample images
Get-ChildItem -Path $RepoRoot -File -Filter "sample_*.jpg" -Force -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -Path $_.FullName -Force -ErrorAction SilentlyContinue
    $deletedCount++
}

Write-Host "============================================================" -ForegroundColor Green
Write-Host "               Cleanup Completed Successfully               " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "   - Items deleted     : $deletedCount" -ForegroundColor Green
Write-Host "   - Disk space freed  : $totalMB MB" -ForegroundColor Green
Write-Host "   - Uploads folder    : Ready & Clean ($uploadsDir)" -ForegroundColor Green
Write-Host "   - Output folder     : Ready & Clean ($outputDir)`n" -ForegroundColor Green

Write-Host "Tip: To clear cached session tabs from the browser dashboard, open DevTools (F12) and run:" -ForegroundColor Cyan
Write-Host "   localStorage.removeItem('openshorts_multi_sessions_v2'); localStorage.removeItem('openshorts_session'); location.reload();`n" -ForegroundColor DarkCyan
