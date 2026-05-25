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

# 5. Create vendor folder + check newflasher.exe (for ROM flashing)
$vendorDir = Join-Path $scriptDir "vendor"
if (-not (Test-Path $vendorDir)) {
    New-Item -ItemType Directory -Path $vendorDir | Out-Null
}
$newflasher = Join-Path $vendorDir "newflasher.exe"
if (-not (Test-Path $newflasher)) {
    Write-Host ""
    Write-Host "[INFO] Optional: newflasher.exe missing (only needed for ROM flashing)" -ForegroundColor Yellow
    Write-Host "        Tool van chay duoc cho debloat/optimize. Khi muon dung tinh nang"
    Write-Host "        cai ROM, tai newflasher.exe va dat vao:"
    Write-Host "          $newflasher"
    Write-Host ""
    Write-Host "        Source code (MIT license):"
    Write-Host "          https://github.com/munjeni/newflasher"
    Write-Host "        Prebuilt binary (XDA community):"
    Write-Host "          https://xdaforums.com/t/tool-newflasher-xperia-command-line-flasher.3619426/"
    Write-Host ""
} else {
    Write-Host "[OK] newflasher.exe ready: $newflasher" -ForegroundColor Green
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
