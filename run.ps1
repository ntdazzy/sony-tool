# run.ps1 — Khởi động Sony Debloat Tool tại http://localhost:8765

$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot
Set-Location $scriptDir

if (-not (Test-Path "$scriptDir\.venv")) {
    Write-Host "❌ Chưa setup. Chạy: .\setup_adb.ps1 trước." -ForegroundColor Red
    exit 1
}

# Thêm bundled ADB vào PATH
$env:PATH = "$scriptDir\platform-tools;$env:PATH"

$port = 8765
$url = "http://localhost:$port"

Write-Host "🚀 Sony Debloat Tool đang khởi động..." -ForegroundColor Cyan
Write-Host "📱 Mở trình duyệt: $url" -ForegroundColor Cyan
Write-Host "🛑 Bấm Ctrl+C để dừng" -ForegroundColor Yellow
Write-Host ""

# Mở browser sau 2s
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:8765"
} | Out-Null

& "$scriptDir\.venv\Scripts\uvicorn.exe" app:app --host 127.0.0.1 --port $port --log-level info
