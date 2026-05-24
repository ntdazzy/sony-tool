@echo off
REM Xuat danh sach package + services + getprop tu may Sony qua ADB (Windows)
REM Usage: export_packages.bat [serial]

setlocal enabledelayedexpansion

set "DEVICE=%~1"
set "ADB_ARG="
if not "%DEVICE%"=="" set "ADB_ARG=-s %DEVICE%"

set "SCRIPT_DIR=%~dp0.."
set "ADB=%SCRIPT_DIR%\platform-tools\adb.exe"

if not exist "%ADB%" (
    where adb >nul 2>&1
    if errorlevel 1 (
        echo Chua co ADB. Chay setup_adb.ps1 truoc.
        exit /b 1
    )
    set "ADB=adb"
)

"%ADB%" %ADB_ARG% get-state >nul 2>&1
if errorlevel 1 (
    echo Khong thay may. Dam bao:
    echo   1. Cap USB la cap data
    echo   2. May bat USB Debugging
    echo   3. Da bam 'Cho phep' tren popup may
    exit /b 1
)

for /f "tokens=2-4 delims=/ " %%a in ('date /t') do set "DATE=%%c%%a%%b"
for /f "tokens=1-2 delims=:" %%a in ("%TIME: =0%") do set "TIME_=%%a%%b"
set "TS=%DATE%-%TIME_%"
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
    echo ===== GETPROP =====
    "%ADB%" %ADB_ARG% shell "getprop"
) > "%OUT%"

echo.
echo Xong. File: %OUT%
echo Gui file nay qua chat cho dev.
