param([string]$Python = "python")
$ErrorActionPreference = "Stop"
& $Python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw "Python 3.12+ is required" }
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) { throw "Callisto installation failed" }
Write-Host "Install ADB and log in to your AI CLI separately on this machine."
Write-Host "Then run .\.venv\Scripts\callisto.exe doctor --json"
