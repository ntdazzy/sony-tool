@echo off
REM Xuat danh sach package + settings + getprop tu may Sony qua ADB (Windows).
REM Locale-safe: dung PowerShell de tao timestamp, dung UTF-8 codepage.
REM Usage: export_packages.bat [serial]

chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

set "DEVICE=%~1"
set "ADB_ARG="
if not "%DEVICE%"=="" set "ADB_ARG=-s %DEVICE%"

set "SCRIPT_DIR=%~dp0.."
set "ADB=%SCRIPT_DIR%\platform-tools\adb.exe"

if not exist "%ADB%" (
    where adb >nul 2>&1
    if errorlevel 1 (
        echo [LOI] Chua co ADB. Chay setup_adb.ps1 truoc.
        exit /b 1
    )
    set "ADB=adb"
)

"%ADB%" %ADB_ARG% get-state >nul 2>&1
if errorlevel 1 (
    echo [LOI] Khong thay may. Dam bao:
    echo   1. Cap USB la cap data
    echo   2. May bat USB Debugging
    echo   3. Da bam 'Cho phep' tren popup may
    exit /b 1
)

REM Timestamp locale-safe qua PowerShell
for /f "delims=" %%a in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "TS=%%a"
set "OUT=%USERPROFILE%\Desktop\sony-export-%TS%.txt"

echo Dang doc du lieu tu may...

(
    echo ============================================
    echo   Sony Xperia Export - %TS%
    echo ============================================
    echo.
    echo ===== DEVICE INFO =====
    "%ADB%" %ADB_ARG% shell getprop ro.product.model
    "%ADB%" %ADB_ARG% shell getprop ro.product.manufacturer
    "%ADB%" %ADB_ARG% shell getprop ro.build.version.release
    "%ADB%" %ADB_ARG% shell getprop ro.build.display.id
    echo.
    echo ===== ALL PACKAGES =====
    "%ADB%" %ADB_ARG% shell "pm list packages -f -U"
    echo.
    echo ===== USER-INSTALLED =====
    "%ADB%" %ADB_ARG% shell "pm list packages -3"
    echo.
    echo ===== SYSTEM =====
    "%ADB%" %ADB_ARG% shell "pm list packages -s"
    echo.
    echo ===== DISABLED =====
    "%ADB%" %ADB_ARG% shell "pm list packages -d"
    echo.
    echo ===== SERVICES =====
    "%ADB%" %ADB_ARG% shell "service list"
    echo.
    echo ===== SETTINGS GLOBAL =====
    "%ADB%" %ADB_ARG% shell "settings list global"
    echo.
    echo ===== SETTINGS SYSTEM =====
    "%ADB%" %ADB_ARG% shell "settings list system"
    echo.
    echo ===== SETTINGS SECURE =====
    "%ADB%" %ADB_ARG% shell "settings list secure"
    echo.
    echo ===== GETPROP =====
    "%ADB%" %ADB_ARG% shell "getprop"
) > "%OUT%"

echo.
echo Xong. File: %OUT%
echo Gui file nay qua chat cho dev.
