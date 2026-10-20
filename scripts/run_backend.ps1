# TidyAI Backend Launch Script (Windows PowerShell)
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "   Starting TidyAI Backend (FastAPI)     " -ForegroundColor Cyan
Write-Host "   Binding strictly to 127.0.0.1:8765   " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$VenvPython = Join-Path $PSScriptRoot "..\backend\.venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "[!] Virtual environment not found at $VenvPython" -ForegroundColor Red
    Write-Host "[*] Creating virtual environment and installing dependencies..." -ForegroundColor Yellow
    python -m venv (Join-Path $PSScriptRoot "..\backend\.venv")
    & (Join-Path $PSScriptRoot "..\backend\.venv\Scripts\pip.exe") install -r (Join-Path $PSScriptRoot "..\backend\requirements.txt")
}

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$env:PYTHONPATH = $ProjectRoot

Write-Host "[+] Launching Uvicorn on 127.0.0.1:8765..." -ForegroundColor Green
& $VenvPython -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8765 --reload
