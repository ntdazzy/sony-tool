#!/usr/bin/env bash
# run.sh — khởi động Sony Debloat Tool tại http://localhost:8765
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
  echo "❌ Chưa setup. Chạy ./setup_adb.sh trước."
  exit 1
fi

if ! command -v adb >/dev/null 2>&1; then
  echo "⚠️  ADB không có trong PATH. Mở Terminal mới hoặc chạy:"
  echo '   export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"'
fi

PORT=8765
URL="http://localhost:${PORT}"

echo "🚀 Sony Debloat Tool đang khởi động..."
echo "📱 Mở trình duyệt: ${URL}"
echo "🛑 Bấm Ctrl+C để dừng"
echo ""

# Mở browser sau 1.5s
(sleep 1.5 && open "${URL}") &

exec ./.venv/bin/uvicorn app:app --host 127.0.0.1 --port ${PORT} --log-level info
