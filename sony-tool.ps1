#requires -Version 5.1
# sony-tool.ps1 - One-script launcher for Sony Debloat Tool (Windows).
#
# Auto-detect setup vs run:
#   - First time: full setup (Python check + ADB + venv + deps + newflasher), then start server.
#   - Subsequent runs: skip setup steps, start server immediately.
#
# Force re-setup: .\sony-tool.ps1 -Setup
# Skip browser open: .\sony-tool.ps1 -NoBrowser
#
# ASCII-only (PowerShell 5.1 default on Win 10/11 does not parse UTF-8 BOMless reliably).
# On any error: pause + show error before exit, so user thay duoc loi gi.

param(
    [switch]$Setup,      # Force re-run setup steps
    [switch]$NoBrowser   # Don't auto-open browser
)

$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot
Set-Location $scriptDir

# ----- Global error trap: never close window without user seeing the error -----
trap {
    Write-Host ""
    Write-Host "================================================" -ForegroundColor Red
    Write-Host "[FATAL] Script crashed with an unhandled error" -ForegroundColor Red
    Write-Host "================================================" -ForegroundColor Red
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "Type:  $($_.Exception.GetType().FullName)" -ForegroundColor DarkGray
    if ($_.InvocationInfo) {
        Write-Host "At:    $($_.InvocationInfo.ScriptName):$($_.InvocationInfo.ScriptLineNumber)" -ForegroundColor DarkGray
        Write-Host "Line:  $($_.InvocationInfo.Line.Trim())" -ForegroundColor DarkGray
    }
    Write-Host ""
    Write-Host "Chup man hinh hoac copy noi dung loi tren gui dev de debug." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Bam Enter de dong cua so"
    exit 1
}

function Show-Error {
    param([string]$msg, [string]$hint = "")
    Write-Host ""
    Write-Host "[ERROR] $msg" -ForegroundColor Red
    if ($hint) { Write-Host "        $hint" -ForegroundColor Yellow }
    Write-Host ""
    Read-Host "Bam Enter de dong cua so"
    exit 1
}

Write-Host "=== Sony Debloat Tool (Windows) ===" -ForegroundColor Cyan
Write-Host ""

# ===========================================================
# SETUP PHASE — chay nếu .venv chưa có, ADB chưa tải, hoặc -Setup flag.
# ===========================================================
$venvDir = Join-Path $scriptDir ".venv"
$adbExe  = Join-Path $scriptDir "platform-tools\adb.exe"
$needsSetup = $Setup -or (-not (Test-Path $venvDir)) -or (-not (Test-Path $adbExe))

if ($needsSetup) {
    Write-Host "[..] Chay setup lan dau..." -ForegroundColor Cyan
    Write-Host ""

    # ----- 1. Tim Python that, bo qua Microsoft Store alias -----
    # Win 10/11 default: python.exe la stub trong WindowsApps tro toi Store.
    # Get-Command tra ve OK nhung chay --version se in "Python was not found".
    # Thu py.exe (Python Launcher) TRUOC vi no khong bi aliased.
    $pythonCmd = $null
    $pyVersion = ""
    foreach ($cmd in @("py", "python", "python3")) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if (-not $found) { continue }
        if ($found.Source -match "\\WindowsApps\\") { continue }
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
        Write-Host ""
        Write-Host "[ERROR] Python khong cai (hoac chi co Microsoft Store alias)." -ForegroundColor Red
        Write-Host ""
        Write-Host "Cach fix:" -ForegroundColor Yellow
        Write-Host "  1. Tai Python 3.10+ tu: https://www.python.org/downloads/"
        Write-Host "  2. Khi cai: tick 'Add Python to PATH'"
        Write-Host "  3. (Neu van loi) Tat Microsoft Store alias:"
        Write-Host "     Settings -> Apps -> Advanced app settings -> App execution aliases"
        Write-Host "     -> tat python.exe va python3.exe"
        Write-Host "  4. Mo PowerShell moi roi chay lai script nay"
        Show-Error "Python missing"
    }
    Write-Host "[OK] Python: $pyVersion" -ForegroundColor Green

    # ----- 2. Download platform-tools (ADB) -----
    if (-not (Test-Path $adbExe)) {
        Write-Host "[..] Downloading platform-tools tu Google..."
        $url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
        $zipPath = Join-Path $env:TEMP "platform-tools.zip"
        try {
            Invoke-WebRequest -Uri $url -OutFile $zipPath -UseBasicParsing -TimeoutSec 120
        } catch {
            Show-Error "Khong tai duoc platform-tools: $_" "Kiem tra Internet, hoac tai tay: $url va giai nen vao $scriptDir"
        }
        Write-Host "[..] Extracting..."
        Expand-Archive -Path $zipPath -DestinationPath $scriptDir -Force
        Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
    }
    Write-Host "[OK] ADB ready: $adbExe" -ForegroundColor Green

    # ----- 3. Create Python venv -----
    if (-not (Test-Path $venvDir)) {
        Write-Host "[..] Creating Python virtual env..."
        & $pythonCmd -m venv $venvDir
        if ($LASTEXITCODE -ne 0) {
            Show-Error "Tao venv that bai (exit $LASTEXITCODE)"
        }
    }

    # ----- 4. Install Python deps -----
    # Goi pip qua python.exe -m pip de tranh pip.exe bi lock khi self-upgrade.
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Show-Error "venv broken: $venvPython missing" "Xoa folder .venv roi chay lai"
    }
    Write-Host "[..] Installing Python dependencies (1-2 phut lan dau)..."
    & $venvPython -m pip install --quiet --disable-pip-version-check --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARN] pip self-upgrade failed (non-fatal, continuing)" -ForegroundColor Yellow
    }
    & $venvPython -m pip install --quiet --disable-pip-version-check -r (Join-Path $scriptDir "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        Show-Error "Cai dependencies that bai (exit $LASTEXITCODE)" "Kiem tra requirements.txt + Internet"
    }
    Write-Host "[OK] Python deps installed" -ForegroundColor Green

    # ----- 5. Auto-download newflasher.exe (MIT license, optional cho ROM flashing) -----
    $vendorDir = Join-Path $scriptDir "vendor"
    if (-not (Test-Path $vendorDir)) {
        New-Item -ItemType Directory -Path $vendorDir | Out-Null
    }
    $newflasher = Join-Path $vendorDir "newflasher.exe"
    $nfUrl = "https://github.com/puksh/newflasher/releases/download/v59/newflasher.exe"
    $nfSha256 = "D859F3D9F9D6CAB5579C3F1AE516727F6EC94C008DC083140F3BA990F3A2F37D"

    function Test-FileHash {
        param([string]$path, [string]$expected)
        if (-not (Test-Path $path)) { return $false }
        $actual = (Get-FileHash -Path $path -Algorithm SHA256).Hash
        return ($actual -eq $expected)
    }

    if (Test-FileHash -path $newflasher -expected $nfSha256) {
        Write-Host "[OK] newflasher.exe ready (SHA256 verified)" -ForegroundColor Green
    } else {
        if (Test-Path $newflasher) {
            Write-Host "[WARN] newflasher.exe SHA256 mismatch, redownloading..." -ForegroundColor Yellow
            Remove-Item $newflasher -Force
        }
        Write-Host "[..] Downloading newflasher.exe (3.2 MB)..."
        try {
            Invoke-WebRequest -Uri $nfUrl -OutFile $newflasher -UseBasicParsing -TimeoutSec 60
            if (Test-FileHash -path $newflasher -expected $nfSha256) {
                Write-Host "[OK] newflasher.exe downloaded + SHA256 verified" -ForegroundColor Green
            } else {
                $actual = (Get-FileHash -Path $newflasher -Algorithm SHA256).Hash
                Write-Host "[WARN] SHA256 mismatch (expected $nfSha256, got $actual)" -ForegroundColor Yellow
                Write-Host "       Possible: upstream binary changed. ROM flash feature disabled." -ForegroundColor Yellow
                Remove-Item $newflasher -Force -ErrorAction SilentlyContinue
            }
        } catch {
            Write-Host "[WARN] Khong tai duoc newflasher: $_" -ForegroundColor Yellow
            Write-Host "       ROM flash feature van chua dung duoc. Tool van chay duoc cho debloat/optimize." -ForegroundColor Yellow
            Write-Host "       Manual: github.com/munjeni/newflasher" -ForegroundColor Yellow
        }
    }

    Write-Host ""
    Write-Host "================================================" -ForegroundColor Cyan
    Write-Host "[OK] Setup xong!" -ForegroundColor Green
    Write-Host "================================================" -ForegroundColor Cyan
    Write-Host ""
}

# ===========================================================
# RUN PHASE — start uvicorn server + open browser.
# ===========================================================
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$uvicornExe = Join-Path $venvDir "Scripts\uvicorn.exe"
if (-not (Test-Path $uvicornExe)) {
    Show-Error "uvicorn khong tim thay tai $uvicornExe" "Chay lai voi -Setup flag"
}

# Add bundled ADB to PATH for this PowerShell session.
$env:PATH = "$scriptDir\platform-tools;$env:PATH"

$port = 8765
$url = "http://localhost:$port"

Write-Host "[..] Sony Debloat Tool starting tren $url" -ForegroundColor Cyan
Write-Host "[..] Tren may Sony: bat USB Debugging va cam cap USB" -ForegroundColor DarkGray
Write-Host "[..] Bam Ctrl+C de dung server" -ForegroundColor Yellow
Write-Host ""

# ----- Auto-open browser sau 2s (trong background) -----
if (-not $NoBrowser) {
    Start-Job -ScriptBlock {
        param($url)
        Start-Sleep -Seconds 2
        Start-Process $url
    } -ArgumentList $url | Out-Null
}

# ----- Start uvicorn — sẽ block đến khi user Ctrl+C -----
try {
    & $uvicornExe app:app --host 127.0.0.1 --port $port --log-level info
    $exitCode = $LASTEXITCODE
} catch {
    Show-Error "Uvicorn crash: $_" "Xem stack trace o tren. Co the port 8765 da dung — close app khac dang chiem port"
}

# ----- Khi user Ctrl+C, uvicorn exit. Giu window de user thay ket qua. -----
Write-Host ""
if ($exitCode -ne 0 -and $exitCode -ne $null) {
    Write-Host "[WARN] Server exited voi code $exitCode" -ForegroundColor Yellow
} else {
    Write-Host "[OK] Server dung. Tam biet!" -ForegroundColor Green
}
Write-Host ""
Read-Host "Bam Enter de dong cua so"
