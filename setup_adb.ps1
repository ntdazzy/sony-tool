# setup_adb.ps1 — Cài ADB + Python deps cho Windows
# Yêu cầu: Python 3.10+ đã cài (download từ python.org)

$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot
Set-Location $scriptDir

Write-Host "=== Sony Debloat Tool — Setup (Windows) ===" -ForegroundColor Cyan
Write-Host ""

# 1. Check Python
$pythonCmd = $null
foreach ($cmd in @("python", "py")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $pythonCmd = $cmd
        break
    }
}
if (-not $pythonCmd) {
    Write-Host "❌ Chưa cài Python." -ForegroundColor Red
    Write-Host "   Tải tại: https://www.python.org/downloads/"
    Write-Host "   QUAN TRỌNG: tick 'Add Python to PATH' khi cài."
    exit 1
}
$pyVersion = & $pythonCmd --version 2>&1
Write-Host "✅ Python: $pyVersion" -ForegroundColor Green

# 2. Tải ADB nếu chưa có
$adbDir = Join-Path $scriptDir "platform-tools"
$adb = Join-Path $adbDir "adb.exe"

if (-not (Test-Path $adb)) {
    Write-Host "📦 Tải platform-tools từ Google..."
    $url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
    $zipPath = Join-Path $env:TEMP "platform-tools.zip"

    try {
        Invoke-WebRequest -Uri $url -OutFile $zipPath -UseBasicParsing
    } catch {
        Write-Host "❌ Lỗi tải: $_" -ForegroundColor Red
        Write-Host "   Tải thủ công tại: $url"
        Write-Host "   Giải nén vào: $scriptDir"
        exit 1
    }

    Write-Host "📂 Giải nén..."
    Expand-Archive -Path $zipPath -DestinationPath $scriptDir -Force
    Remove-Item $zipPath
}
Write-Host "✅ ADB: $adb" -ForegroundColor Green

# 3. Tạo Python venv
$venv = Join-Path $scriptDir ".venv"
if (-not (Test-Path $venv)) {
    Write-Host "🐍 Tạo Python virtual env..."
    & $pythonCmd -m venv $venv
}

# 4. Cài deps
$pip = Join-Path $venv "Scripts\pip.exe"
Write-Host "📦 Cài Python dependencies..."
& $pip install -q --upgrade pip
& $pip install -q -r (Join-Path $scriptDir "requirements.txt")
Write-Host "✅ Python deps đã sẵn sàng" -ForegroundColor Green

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "✅ Setup xong. Bước tiếp:" -ForegroundColor Green
Write-Host ""
Write-Host "1. Trên máy Sony: bật USB Debugging"
Write-Host "   Cài đặt → Giới thiệu điện thoại → bấm 'Số hiệu bản dựng' 7 lần"
Write-Host "   → Cài đặt → Hệ thống → Tuỳ chọn nhà phát triển → bật 'Gỡ lỗi USB'"
Write-Host ""
Write-Host "2. Cắm cáp USB vào PC, bấm 'Cho phép' trên máy khi popup hiện."
Write-Host ""
Write-Host "3. Khởi động tool:"
Write-Host "   .\run.ps1"
Write-Host "================================================" -ForegroundColor Cyan
