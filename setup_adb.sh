#!/usr/bin/env bash
# setup_adb.sh — cài ADB qua Homebrew (chỉ chạy 1 lần).
set -e

echo "=== Sony Debloat Tool — Setup ==="
echo ""

# 1. Kiểm tra Homebrew
if ! command -v brew >/dev/null 2>&1; then
  echo "❌ Chưa có Homebrew. Cài bằng lệnh:"
  echo '   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  echo "Sau đó chạy lại ./setup_adb.sh"
  exit 1
fi
echo "✅ Homebrew đã có"

# 2. Cài android-platform-tools
if command -v adb >/dev/null 2>&1; then
  echo "✅ ADB đã cài: $(adb --version | head -1)"
else
  echo "📦 Đang cài android-platform-tools (chứa adb)..."
  brew install --cask android-platform-tools
  echo "✅ Cài xong: $(adb --version | head -1)"
fi

# 3. Python venv + deps
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
  echo "🐍 Tạo Python virtual env..."
  python3 -m venv .venv
fi

echo "📦 Cài Python dependencies..."
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements.txt
echo "✅ Python deps đã sẵn sàng"

# Auto-download newflasher binary (MIT license, github.com/puksh/newflasher)
mkdir -p "$SCRIPT_DIR/vendor"
case "$(uname -s)" in
  Darwin) NF_URL="https://github.com/puksh/newflasher/releases/download/v59/newflasher-macos"
          NF_PATH="$SCRIPT_DIR/vendor/newflasher" ;;
  Linux)  ARCH=$(uname -m)
          if [ "$ARCH" = "x86_64" ]; then
            NF_URL="https://github.com/puksh/newflasher/releases/download/v59/newflasher.x64"
          else
            NF_URL="https://github.com/puksh/newflasher/releases/download/v59/newflasher.i386"
          fi
          NF_PATH="$SCRIPT_DIR/vendor/newflasher" ;;
  *) NF_URL=""; NF_PATH="" ;;
esac

if [ -n "$NF_URL" ] && [ ! -f "$NF_PATH" ]; then
  echo "📥 Tải newflasher (ROM flash binary, MIT license)..."
  if curl -L -o "$NF_PATH" "$NF_URL" 2>/dev/null; then
    chmod +x "$NF_PATH"
    echo "✅ newflasher: $NF_PATH"
  else
    echo "⚠️  Tải newflasher fail — ROM flash sẽ chưa dùng được. Tải tay từ github.com/munjeni/newflasher"
  fi
elif [ -f "$NF_PATH" ]; then
  echo "✅ newflasher đã có: $NF_PATH"
fi

echo ""
echo "================================================"
echo "✅ Setup xong. Bước tiếp theo:"
echo ""
echo "1. Trên máy Sony: bật USB Debugging"
echo "   Cài đặt → Giới thiệu điện thoại → bấm 'Số hiệu bản dựng' 7 lần"
echo "   → Cài đặt → Hệ thống → Tuỳ chọn nhà phát triển → bật 'Gỡ lỗi USB'"
echo ""
echo "2. Cắm cáp USB vào Mac, bấm 'Cho phép' trên máy khi popup hiện."
echo ""
echo "3. Khởi động tool:"
echo "   ./run.sh"
echo "================================================"
