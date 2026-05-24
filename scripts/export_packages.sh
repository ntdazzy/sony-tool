#!/usr/bin/env bash
# Xuất danh sách package + services + getprop từ máy Sony qua ADB.
# Dùng độc lập, không cần chạy tool web.
# Usage: ./scripts/export_packages.sh  (tự dò máy đầu tiên)
#        ./scripts/export_packages.sh ABC123XYZ  (chỉ định serial)
set -e

DEVICE="${1:-}"
ADB_ARG=""
[ -n "$DEVICE" ] && ADB_ARG="-s $DEVICE"

if ! command -v adb >/dev/null 2>&1; then
  echo "❌ Chưa có ADB. Chạy ./setup_adb.sh trước."
  exit 1
fi

if ! adb $ADB_ARG get-state >/dev/null 2>&1; then
  echo "❌ Không thấy máy. Đảm bảo:"
  echo "   1. Cáp USB là cáp data"
  echo "   2. Máy bật USB Debugging"
  echo "   3. Đã bấm 'Cho phép' trên popup máy"
  exit 1
fi

TS=$(date +%Y%m%d-%H%M%S)
OUT="$HOME/Desktop/sony-export-$TS.txt"

echo "🔎 Đang đọc dữ liệu từ máy..."

{
  echo "============================================"
  echo "  Sony Xperia Export — $TS"
  echo "============================================"
  echo ""
  echo "===== DEVICE INFO ====="
  echo "Model:        $(adb $ADB_ARG shell getprop ro.product.model | tr -d '\r')"
  echo "Manufacturer: $(adb $ADB_ARG shell getprop ro.product.manufacturer | tr -d '\r')"
  echo "Device:       $(adb $ADB_ARG shell getprop ro.product.device | tr -d '\r')"
  echo "Android:      $(adb $ADB_ARG shell getprop ro.build.version.release | tr -d '\r')"
  echo "SDK:          $(adb $ADB_ARG shell getprop ro.build.version.sdk | tr -d '\r')"
  echo "Build:        $(adb $ADB_ARG shell getprop ro.build.display.id | tr -d '\r')"
  echo "Serial:       $(adb $ADB_ARG shell getprop ro.serialno | tr -d '\r')"
  echo ""

  echo "===== ALL PACKAGES (with paths) ====="
  adb $ADB_ARG shell "pm list packages -f -U"
  echo ""

  echo "===== USER-INSTALLED (3rd party) ====="
  adb $ADB_ARG shell "pm list packages -3"
  echo ""

  echo "===== SYSTEM PACKAGES ====="
  adb $ADB_ARG shell "pm list packages -s"
  echo ""

  echo "===== DISABLED PACKAGES ====="
  adb $ADB_ARG shell "pm list packages -d"
  echo ""

  echo "===== SERVICES (running) ====="
  adb $ADB_ARG shell "service list"
  echo ""

  echo "===== GETPROP (system properties) ====="
  adb $ADB_ARG shell "getprop"
} > "$OUT" 2>&1

LINES=$(wc -l < "$OUT")
SIZE=$(du -h "$OUT" | cut -f1)

echo ""
echo "============================================"
echo "✅ Xong"
echo "📄 File: $OUT"
echo "📊 $LINES dòng, $SIZE"
echo "📤 Gửi file này qua chat cho dev phân tích"
echo "============================================"
