# TidyAI Test Suite Runner (Windows PowerShell)
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "        Running TidyAI Test Suite       " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$VenvPython = Join-Path $PSScriptRoot "..\backend\.venv\Scripts\python.exe"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$env:PYTHONPATH = $ProjectRoot

Write-Host "`n[*] 1. Running Backend Pytest Suite..." -ForegroundColor Yellow
& $VenvPython -m pytest (Join-Path $ProjectRoot "backend\tests") -v
$backendResult = $LASTEXITCODE

Write-Host "`n[*] 2. Running Frontend Type Check (tsc)..." -ForegroundColor Yellow
$FrontendDir = Resolve-Path (Join-Path $PSScriptRoot "..\frontend")
Push-Location $FrontendDir
npx tsc --noEmit
$typeResult = $LASTEXITCODE

Write-Host "`n[*] 3. Running Frontend ESLint..." -ForegroundColor Yellow
npm run lint
$lintResult = $LASTEXITCODE
Pop-Location

Write-Host "`n=========================================" -ForegroundColor Cyan
if ($backendResult -eq 0 -and $typeResult -eq 0 -and $lintResult -eq 0) {
    Write-Host "  ALL TESTS & CHECKS PASSED SUCCESSFULLY  " -ForegroundColor Green
} else {
    Write-Host "  SOME CHECKS FAILED - REVIEW OUTPUT     " -ForegroundColor Red
}
Write-Host "=========================================" -ForegroundColor Cyan

if ($backendResult -ne 0) { exit $backendResult }
if ($typeResult -ne 0) { exit $typeResult }
if ($lintResult -ne 0) { exit $lintResult }
