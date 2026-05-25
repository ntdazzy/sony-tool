# setup_adb.ps1 - Install ADB + Python deps for Windows.
# ASCII-only. Compatible with PowerShell 5.1 (Win 10/11 default) and 7+.
# Requires Python 3.10+ already installed (https://www.python.org/downloads/).

$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot
Set-Location $scriptDir

Write-Host "=== Sony Debloat Tool - Setup (Windows) ===" -ForegroundColor Cyan
Write-Host ""

# 1. Check Python - skip Microsoft Store alias
# Win 10/11 default has python.exe as a Store stub at WindowsApps. Get-Command
# returns success even though running it prints "Python was not found".
# Try py.exe (Python Launcher) FIRST since it is never aliased.
$pythonCmd = $null
foreach ($cmd in @("py", "python", "python3")) {
    $found = Get-Command $cmd -ErrorAction SilentlyContinue
    if (-not $found) { continue }
    # Skip Microsoft Store alias (path under WindowsApps)
    if ($found.Source -match "\\WindowsApps\\") { continue }
    # Verify it actually runs and prints a real version
    try {
        $verOut = & $cmd --version 2>&1 | Out-String
        if ($verOut -match "Python \d+\.\d+") {
            $pythonCmd = $cmd
            $pyVersion = ($verOut.Trim() -split "`n")[0]
            break
        }
    } catch {}
}
if (-not $pythonCmd) {
    Write-Host "[ERROR] Python not installed (or only Microsoft Store alias detected)." -ForegroundColor Red
    Write-Host ""
    Write-Host "  Cach fix:"
    Write-Host "  1. Tai Python 3.10+ tu: https://www.python.org/downloads/"
    Write-Host "  2. Khi cai - TICK 'Add Python to PATH'"
    Write-Host "  3. (Neu van loi) Tat Microsoft Store alias:"
    Write-Host "     Settings -> Apps -> Advanced app settings -> App execution aliases"
    Write-Host "     -> tat python.exe va python3.exe"
    Write-Host "  4. Mo PowerShell moi roi chay lai .\setup_adb.ps1"
    exit 1
}
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
# Use `python.exe -m pip` so pip self-upgrade works on Windows
# (pip.exe is locked while running -> "ERROR: To modify pip, please run..." otherwise).
$venvPython = Join-Path $venv "Scripts\python.exe"
Write-Host "[..] Installing Python dependencies..."
& $venvPython -m pip install --quiet --disable-pip-version-check --upgrade pip
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] pip self-upgrade failed (non-fatal, continuing)" -ForegroundColor Yellow
}
& $venvPython -m pip install --quiet --disable-pip-version-check -r (Join-Path $scriptDir "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to install dependencies" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Python deps installed" -ForegroundColor Green

# 5. Auto-download newflasher.exe (MIT license, for ROM flashing feature)
# Source: github.com/puksh/newflasher - community fork rebuilds Munjeni's upstream
# with prebuilt assets. v59 matches Munjeni source tag v59.
$vendorDir = Join-Path $scriptDir "vendor"
if (-not (Test-Path $vendorDir)) {
    New-Item -ItemType Directory -Path $vendorDir | Out-Null
}
$newflasher = Join-Path $vendorDir "newflasher.exe"
$nfUrl = "https://github.com/puksh/newflasher/releases/download/v59/newflasher.exe"
$nfSha256 = "D859F3D9F9D6CAB5579C3F1AE516727F6EC94C008DC083140F3BA990F3A2F37D"

function Test-NewflasherHash {
    param([string]$path, [string]$expected)
    if (-not (Test-Path $path)) { return $false }
    $actual = (Get-FileHash -Path $path -Algorithm SHA256).Hash
    return ($actual -eq $expected)
}

if (Test-NewflasherHash -path $newflasher -expected $nfSha256) {
    Write-Host "[OK] newflasher.exe ready (SHA256 verified): $newflasher" -ForegroundColor Green
} else {
    if (Test-Path $newflasher) {
        Write-Host "[WARN] newflasher.exe SHA256 mismatch, redownloading..." -ForegroundColor Yellow
        Remove-Item $newflasher -Force
    }
    Write-Host "[..] Downloading newflasher.exe (3.2 MB) from puksh/newflasher v59..."
    try {
        Invoke-WebRequest -Uri $nfUrl -OutFile $newflasher -UseBasicParsing -TimeoutSec 60
        if (Test-NewflasherHash -path $newflasher -expected $nfSha256) {
            Write-Host "[OK] newflasher.exe downloaded + SHA256 verified" -ForegroundColor Green
        } else {
            Write-Host "[ERROR] SHA256 mismatch after download. Expected $nfSha256" -ForegroundColor Red
            Write-Host "        Got      $((Get-FileHash -Path $newflasher -Algorithm SHA256).Hash)"
            Write-Host "        Possible: upstream binary changed, or download corrupted."
            Remove-Item $newflasher -Force -ErrorAction SilentlyContinue
            Write-Host "[WARN] ROM flash feature will not work without newflasher.exe" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[WARN] Download failed: $_" -ForegroundColor Yellow
        Write-Host "        ROM flash feature van chua su dung duoc."
        Write-Host "        Manual: tai newflasher.exe roi dat vao $newflasher"
        Write-Host "        Source code (MIT): https://github.com/munjeni/newflasher"
    }
}

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
