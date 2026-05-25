# setup_adb.ps1 - Install ADB + Python deps for Windows.
# ASCII-only. Compatible with PowerShell 5.1 (Win 10/11 default) and 7+.
# Requires Python 3.10+ already installed (https://www.python.org/downloads/).

$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot
Set-Location $scriptDir

Write-Host "=== Sony Debloat Tool - Setup (Windows) ===" -ForegroundColor Cyan
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
    Write-Host "[ERROR] Python not installed." -ForegroundColor Red
    Write-Host "        Download: https://www.python.org/downloads/"
    Write-Host "        IMPORTANT: tick 'Add Python to PATH' when installing."
    exit 1
}
$pyVersion = & $pythonCmd --version 2>&1
Write-Host "[OK] Python: $pyVersion" -ForegroundColor Green

# 2. Download platform-tools if missing
$adbDir = Join-Path $scriptDir "platform-tools"
$adb = Join-Path $adbDir "adb.exe"

if (-not (Test-Path $adb)) {
    Write-Host "[..] Downloading platform-tools from Google..."
    $url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
    $zipPath = Join-Path $env:TEMP "platform-tools.zip"

    try {
        Invoke-WebRequest -Uri $url -OutFile $zipPath -UseBasicParsing
    } catch {
        Write-Host "[ERROR] Download failed: $_" -ForegroundColor Red
        Write-Host "        Manual download: $url"
        Write-Host "        Extract to: $scriptDir"
        exit 1
    }

    Write-Host "[..] Extracting..."
    Expand-Archive -Path $zipPath -DestinationPath $scriptDir -Force
    Remove-Item $zipPath
}
Write-Host "[OK] ADB ready: $adb" -ForegroundColor Green

# 3. Create Python venv
$venv = Join-Path $scriptDir ".venv"
if (-not (Test-Path $venv)) {
    Write-Host "[..] Creating Python virtual env..."
    & $pythonCmd -m venv $venv
}

# 4. Install Python deps
$pip = Join-Path $venv "Scripts\pip.exe"
Write-Host "[..] Installing Python dependencies..."
& $pip install -q --upgrade pip
& $pip install -q -r (Join-Path $scriptDir "requirements.txt")
Write-Host "[OK] Python deps installed" -ForegroundColor Green

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "[OK] Setup done. Next steps:" -ForegroundColor Green
Write-Host ""
Write-Host "1. On Sony phone: enable USB Debugging"
Write-Host "   Settings -> About phone -> tap 'Build number' 7 times"
Write-Host "   -> Settings -> System -> Developer options -> enable 'USB debugging'"
Write-Host ""
Write-Host "2. Connect USB cable to PC. Tap 'Allow' on phone popup."
Write-Host ""
Write-Host "3. Start the tool:"
Write-Host "   .\run.ps1"
Write-Host "================================================" -ForegroundColor Cyan
