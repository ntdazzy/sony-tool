# run.ps1 - Start Sony Debloat Tool at http://localhost:8765
# ASCII-only. Compatible with PowerShell 5.1 and 7+.

$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot
Set-Location $scriptDir

if (-not (Test-Path "$scriptDir\.venv")) {
    Write-Host "[ERROR] Not setup yet. Run: .\setup_adb.ps1 first." -ForegroundColor Red
    exit 1
}

# Add bundled ADB to PATH for this session
$env:PATH = "$scriptDir\platform-tools;$env:PATH"

$port = 8765
$url = "http://localhost:$port"

Write-Host "[..] Sony Debloat Tool starting..." -ForegroundColor Cyan
Write-Host "[..] Open browser: $url" -ForegroundColor Cyan
Write-Host "[..] Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

# Open browser after 2s in background
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:8765"
} | Out-Null

& "$scriptDir\.venv\Scripts\uvicorn.exe" app:app --host 127.0.0.1 --port $port --log-level info
