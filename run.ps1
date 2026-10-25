# Use the same supervised launcher and runtime selection as run.bat.
$RepoRoot = $PSScriptRoot
Set-Location -LiteralPath $RepoRoot
$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($PythonCommand) {
    & $PythonCommand.Source (Join-Path $RepoRoot "run.py") @args
} elseif (Test-Path -LiteralPath (Join-Path $RepoRoot ".venv\Scripts\python.exe")) {
    & (Join-Path $RepoRoot ".venv\Scripts\python.exe") (Join-Path $RepoRoot "run.py") @args
} else {
    throw "Python was not found. Install Python and the dependencies first."
}
if ($LASTEXITCODE -ne 0) {
    throw "OpenShorts stopped. See .cache/launcher/backend.log and frontend.log."
}
