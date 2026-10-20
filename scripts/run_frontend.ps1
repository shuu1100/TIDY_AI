# TidyAI Frontend Launch Script (Windows PowerShell)
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "   Starting TidyAI Frontend (Next.js)   " -ForegroundColor Cyan
Write-Host "   Binding strictly to 127.0.0.1:3000   " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$FrontendDir = Resolve-Path (Join-Path $PSScriptRoot "..\frontend")
Set-Location $FrontendDir

Write-Host "[+] Launching Next.js dev server on 127.0.0.1:3000..." -ForegroundColor Green
npm run dev -- -p 3000 -H 127.0.0.1
