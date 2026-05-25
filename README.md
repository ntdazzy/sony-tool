# Sony Debloat

Tool web local **dọn app rác** + **tối ưu hiệu năng** cho Sony Xperia. Không cần root, không cần unlock bootloader, mọi thao tác đảo ngược được.

![Tests](https://img.shields.io/badge/tests-97%20passed-brightgreen) ![Python](https://img.shields.io/badge/python-3.10+-blue) ![Platform](https://img.shields.io/badge/platform-Mac%20%7C%20Windows-lightgrey)

---

## 🎯 Tool này làm gì?

**Vấn đề:** Sony Xperia (đặc biệt bản nội địa Nhật như XQ-AS42, SO-52A, SOG02, A002SO) đi kèm hàng trăm app rác/service ngầm:
- 4 service Facebook chạy ngầm dù bạn không dùng FB
- Sony News, Lifelog, Theme Engine, Smart Connect — chạy 24/7 tốn RAM/pin
- App nhà mạng Nhật (G-Guide TV, iWnn IME, Docomo OSV) — vô dụng ở VN
- Google apps preinstalled (Drive, Maps, YouTube, Gmail) — gỡ nếu không dùng
- Partner apps (Amazon, Netflix activator, LinkedIn, LINE)

**Sony khoá bootloader** cho thị trường Nhật → không cài ROM custom, không root. Cách duy nhất để dọn là dùng **ADB** với lệnh `pm disable-user` / `pm uninstall --user 0`.

**Giải pháp:** Tool web local chạy trên Mac/Windows, kết nối máy Sony qua USB:
- 🧹 **Dọn 165+ bloat package** đã curate sẵn (4 mức từ Nhẹ → Tối đa)
- ⚡ **23 preset tối ưu** (animation, RAM, pin, privacy)
- 🛡️ **76 package cốt lõi** được bảo vệ — không cho tắt nhầm Play Store/GMS/Camera
- 🚀 **1-click cleanup** với auto-backup
- 📊 **Live state detection** — biết preset nào đã/chưa áp dụng
- 📝 **Activity log** real-time hiển thị từng action

```
┌─────────────┐   HTTP   ┌──────────────┐  subprocess  ┌────────┐   USB   ┌─────────┐
│   Browser   │ ◄──────► │  FastAPI     │ ◄──────────► │  ADB   │ ◄─────► │  Sony   │
│ (HTML/JS)   │ :8765    │  (Python)    │              │ binary │  cable  │  phone  │
└─────────────┘          └──────────────┘              └────────┘         └─────────┘
```

---

## 📦 Cài đặt

### Mac/Linux

```bash
git clone https://github.com/ntdazzy/sony-tool.git
cd sony-tool
chmod +x setup_adb.sh run.sh
./setup_adb.sh    # Cài ADB via Homebrew + Python venv
./run.sh          # Mở http://localhost:8765
```

### Windows

```powershell
git clone https://github.com/ntdazzy/sony-tool.git
cd sony-tool
.\setup_adb.ps1   # Tải platform-tools + Python venv
.\run.ps1         # Mở http://localhost:8765
```

Yêu cầu Python 3.10+. ADB tự tải về thư mục `platform-tools/`.

### Bật USB Debugging trên máy Sony (1 lần)

1. **Cài đặt → Giới thiệu điện thoại** → chạm **Số hiệu bản dựng** 7 lần
2. **Cài đặt → Hệ thống → Tuỳ chọn nhà phát triển** → bật **Gỡ lỗi USB**
3. Cắm cáp **data** (không phải cáp chỉ sạc), bấm **Cho phép** trên popup
4. Trong tool, bấm **↻** để verify kết nối

---

## ✨ Tính năng

### Tab Tổng quan
- Stats dashboard: tổng app / đang chạy / đã tắt / **bloat còn chạy**
- Thông tin máy: model, manufacturer, Android version, build, serial
- Hướng dẫn bật USB Debugging

### Tab Dọn sạch
- **🚀 1-click cleanup**: backup → tắt/gỡ bloat → áp dụng tối ưu → đề nghị reboot
- Toggle **Tắt** (an toàn) / **Gỡ hẳn** (sạch hơn)
- **4 mức thủ công**:
  | Mức | Bloat tier | Mô tả |
  |---|---|---|
  | 🟢 Nhẹ | safe | Facebook, partner apps, JP-only, ad services |
  | 🔵 Vừa *(đề xuất)* | + recommended | + Sony Music/Album/Email/Calendar, Lifelog |
  | 🟡 Mạnh | + aggressive | + FOTA scheduler, call log backup, SMS push |
  | 🔴 Tối đa | + optional | + Google apps không dùng (Drive, Maps, YouTube) |
- Preview list trước khi xử lý

### Tab Tất cả app
- Bảng tất cả 200+ package trên máy
- Filter: user-installed / system / disabled / enabled / in bloat list / critical
- Search theo tên
- Action: tắt/bật từng app hoặc bulk
- Tag màu: Đang bật / Đã tắt / Cốt lõi / tier

### Tab Tối ưu
- **23 preset** chia 5 nhóm: Tốc độ / Hiệu năng / Pin / Hiển thị / Riêng tư
- **State detection**: badge "Đã áp dụng" / "Mặc định" / "1 phần" cho mỗi preset
- Áp dụng / Khôi phục cho từng preset độc lập

### Tab Backup
- **Tạo backup**: lưu trạng thái app + enabled flag → JSON
- **Xuất chi tiết**: packages + services + getprop + settings (global/system/secure) → gửi dev phân tích, cập nhật bloat list cho máy cụ thể của bạn

### Activity log (cố định bottom)
- Mỗi action ghi 1 dòng: timestamp + icon + message màu
- Auto-scroll, collapse được
- Tải log ra `.txt` để chia sẻ debug

### Theme
- Light/dark mode toggle
- Lưu preference vào localStorage

---

## 🛡️ An toàn

**3 lớp bảo vệ:**

1. **Safe-list backend (76 package)** chặn cứng: Play Store, GMS, GSF, WebView, Camera Sony, SystemUI, Settings, Phone, Dialer, providers, NetworkStack, Cellbroadcast, UWB, role manager... Request disable/uninstall package critical → HTTP 400 ngay.

2. **"Tắt" mặc định** (`pm disable-user`) thay vì gỡ thật. App vẫn còn APK trong `/system`, bật lại 1 lệnh.

3. **Auto-backup** trước mỗi đợt cleanup → file JSON ghi trạng thái cũ.

**Phục hồi khẩn cấp** nếu lỡ tắt nhầm:
```bash
# Bật lại toàn bộ app đang disabled
adb shell "pm list packages -d" | sed 's/package://' | xargs -n1 -I{} adb shell pm enable {}
```

Hoặc trong tool: tab "Tất cả app" → lọc "Đã tắt" → bật lại.

---

## 📱 Hỗ trợ multi-model

Curated trên **XQ-AS42** nhưng hoạt động với mọi Sony Xperia:

- **~80% bloat list là universal Sony** (`com.sonymobile.*`, `com.sonyericsson.*`, Facebook system apps) — chạy được trên Xperia 1/5/10 series, Pro series
- Tool có **filter "chỉ hiện app đang có trên máy"** → tự ẩn package không tồn tại
- **Settings tweaks dùng AOSP keys** → chạy được trên mọi Android (không Sony-specific)
- Verified: XQ-AS42, SO-52A

Nếu máy bạn có bloat lạ không trong list → **Backup → Xuất chi tiết → gửi file cho dev**, tôi cập nhật list, bạn `git pull`.

---

## 🔧 Cơ chế hoạt động

### Layer 1 — Tắt app rác qua Package Manager

```bash
# Disable (recommended): app vẫn còn, ẩn icon, không chạy ngầm. Bật lại 1 lệnh.
adb shell pm disable-user --user 0 com.facebook.appmanager

# Uninstall for user 0: gỡ cho user hiện tại, APK vẫn trong /system.
# Khôi phục: cmd package install-existing <pkg>
adb shell pm uninstall --user 0 com.facebook.appmanager
```

→ Bớt 30-40% RAM dùng ngay từ boot, bớt CPU/pin cho background services.

### Layer 2 — Tinh chỉnh system qua `settings` + `device_config`

```bash
# Animation off → GPU không vẽ transitions → cảm giác tap-instant
adb shell settings put global window_animation_scale 0
adb shell settings put global transition_animation_scale 0
adb shell settings put global animator_duration_scale 0

# Giới hạn background processes → ít app cached → RAM trống
adb shell device_config put activity_manager max_phantom_processes 3

# Wi-Fi không scan ngầm → pin standby trâu hơn
adb shell settings put global wifi_scan_always_enabled 0

# Tắt Always-On Display → màn hình tắt hoàn toàn lúc idle
adb shell settings put secure doze_always_on 0
```

→ ~20% pin tiết kiệm standby + snappier feel rõ rệt.

### Tool gói tất cả vào 1-click

```
1. POST /api/backup           → backups/backup-YYYYMMDD.json
2. POST /api/packages/disable  → 140 lệnh pm disable-user --user 0
3. POST /api/optimize/apply    → 11 preset (settings put + device_config put)
4. POST /api/reboot            → adb shell reboot
```

---

## 📂 Cấu trúc thư mục

```
sony-tool/
├── README.md                       # File này
├── requirements.txt                # fastapi, uvicorn, pytest, httpx
├── app.py                          # FastAPI server (~400 dòng)
├── adb_wrapper.py                  # Wrapper subprocess gọi adb
├── setup_adb.sh / setup_adb.ps1    # Setup Mac / Windows
├── run.sh / run.ps1                # Khởi động uvicorn
│
├── data/
│   ├── safe_list.json              # 76 package CẤM tắt
│   ├── bloat_jp.json               # 165 bloat package (11 nhóm, 4 tier)
│   └── optimize_presets.json       # 23 preset tinh chỉnh
│
├── static/                         # Frontend (vanilla, no build)
│   ├── index.html                  # Single page app
│   ├── style.css                   # CSS variables, light + dark theme
│   └── app.js                      # Logic: tabs, API, 1-click, modal, log
│
├── scripts/
│   ├── export_packages.sh          # Dump packages + settings (Mac/Linux)
│   └── export_packages.bat         # Tương tự (Windows)
│
├── tests/                          # pytest, 97 tests
│   ├── test_data_integrity.py      # Validate JSON, no conflicts
│   ├── test_adb_wrapper.py         # Parse helpers, subprocess mock
│   ├── test_api.py                 # Endpoints + safe-list enforcement
│   ├── test_optimize_state.py      # State detection logic
│   ├── test_frontend_consistency.py # Cross-check JS ↔ HTML ↔ data
│   └── test_windows_compat.py      # Path, encoding, ASCII-only .ps1
│
├── backups/                        # Auto-created, JSON backup files
└── platform-tools/                 # ADB binary (Windows tải về đây)
```

---

## 🚀 Roadmap — Tính năng có thể thêm

Theo độ hữu ích đề xuất:

### 1. **App size + storage analysis**
Bên cạnh tên app, hiện size APK + cache data (`dumpsys diskstats`). Sau cleanup hiển thị "Tiết kiệm 1.2 GB". Cho user thấy benefit cụ thể.

### 2. **Battery hog detector**
Đọc `dumpsys batterystats` + `dumpsys procstats` → list top 10 app tốn pin 24h qua. Suggest tắt những cái user không quan tâm.

### 3. **Restore point (full snapshot)**
Snapshot toàn bộ state (apps enabled + settings values) như macOS Time Machine. Restore 1-click nếu sau cleanup máy lạ.

### 4. **Diff view giữa các backup**
So sánh 2 backup → biết giữa 2 thời điểm, máy đã đổi gì (app mới install, settings changed). Useful sau Android update.

### 5. **Recommendation engine**
Phân tích máy: "Máy bạn có 89 bloat, RAM 6GB, ít dùng đa nhiệm → đề xuất mức Vừa + tắt animation + giới hạn 3 process". Personalized cho từng máy.

### 6. **Permission audit**
List app nào có permission nhạy cảm (LOCATION_ALWAYS, CAMERA, MICROPHONE, READ_SMS). Giúp user quyết định gỡ.

### 7. **Network usage analyzer**
Đọc `cat /proc/net/xt_qtaguid/stats` → app nào dùng nhiều data ngầm. Detect tracker / spyware.

### 8. **Multi-device support**
Nhiều máy cắm cùng lúc → dropdown chọn máy active. Manage 2-3 Xperia phụ cùng lúc.

### 9. **CLI mode**
`python cli.py cleanup --tier nuclear --serial ABC123 --auto-confirm` cho automation / scripting. Useful cho IT manage fleet.

### 10. **Custom bloat lists cho hãng khác**
`bloat_samsung.json`, `bloat_xiaomi.json`, `bloat_oppo.json`. Mở rộng tool support beyond Sony. Cộng đồng đóng góp via PR.

### 11. **Auto-update bloat list từ GitHub**
Mỗi tuần tool tự `git pull` data files → user luôn có list mới nhất.

### 12. **A/B benchmark before/after**
Đo boot time, free RAM, battery drain rate trước + sau cleanup. Show metrics rõ ràng "trước 4 phút boot, sau 2.5 phút".

### 13. **Live screen mirror (scrcpy integration)**
Hiện màn hình máy trong tool qua scrcpy. Vừa setup vừa nhìn máy không cần nhìn xuống bàn.

### 14. **Notification audit**
List app nào gửi notification nhiều (đọc `dumpsys notification`). Suggest disable.

### 15. **Shareable presets**
Export config "Setup máy phụ" / "Setup gaming" thành JSON → user khác import. Build community of bloat configs.

---

## 🧪 Tests

```bash
./.venv/bin/python -m pytest tests/ -v
```

- 97 tests across 6 files
- ~0.4s total runtime
- Cover: JSON integrity, ADB wrapper logic, API endpoints, safe-list enforcement, state detection, frontend-backend consistency, Windows compat

---

## 📡 API reference

Tất cả endpoint chạy local `http://localhost:8765`. Không auth.

| Method | Path | Mô tả |
|---|---|---|
| GET | `/` | Trang HTML chính |
| GET | `/api/status` | ADB + device info |
| GET | `/api/packages?serial=` | Danh sách app + stats + tier flags |
| GET | `/api/bloat-list` | Curated bloat catalog |
| GET | `/api/optimize/presets` | Danh sách preset tối ưu |
| GET | `/api/optimize/state?serial=` | **Current value của mỗi preset's setting** |
| POST | `/api/packages/disable` | `{packages: [...], serial?}` |
| POST | `/api/packages/enable` | tương tự, không check safe-list |
| POST | `/api/packages/uninstall` | `pm uninstall --user 0` |
| POST | `/api/packages/restore` | `cmd package install-existing` |
| POST | `/api/optimize/apply` | `{preset_id, serial?}` |
| POST | `/api/optimize/revert` | tương tự |
| POST | `/api/settings/write` | `{namespace, key, value, serial?}` |
| GET | `/api/backup?serial=` | Tạo backup JSON |
| GET | `/api/export-full?serial=` | Dump packages + services + settings + getprop |
| GET | `/api/backups` | List backup files |
| POST | `/api/reboot?serial=` | Reboot máy |

Endpoint disable/uninstall **luôn check safe-list** và refuse HTTP 400 nếu chạm package critical.

---

## ❓ FAQ rút gọn

**Q: Có an toàn không?**  
A: Có. 76 package critical chặn cứng ở backend. "Tắt" mặc định, có thể bật lại 1 click. Auto-backup trước mỗi đợt cleanup.

**Q: Tool gửi data của tôi đi đâu không?**  
A: Không. Server chạy 100% local trên máy bạn, không gọi internet. Source code mở.

**Q: Bootloader unlock được không?**  
A: KHÔNG cho XQ-AS42/SO-52A — Sony policy thị trường Nhật. Không có exploit công khai.

**Q: Đổi font hệ thống được không?**  
A: KHÔNG nếu không root. Workaround: Nova Launcher đổi font tên app, đổi cỡ chữ trong Settings.

**Q: Factory reset thì app gỡ có quay lại?**  
A: Có. Cả "Tắt" và "Gỡ --user 0" không xoá APK trong system. Factory reset = reset user data → app quay lại như mới.

---

## 🛠️ Tech stack

- **Backend**: Python 3.10+, FastAPI, uvicorn
- **Frontend**: Vanilla JS, HTML, CSS (no build step, no framework)
- **Storage**: JSON files (data/*.json), filesystem (backups/)
- **Bridge**: Android Debug Bridge (adb)
- **Test**: pytest + httpx (FastAPI TestClient)
- **Cross-platform**: Mac/Linux (bash) + Windows (PowerShell)

Không có database, không có background services, không có cloud. Toàn bộ stack ~50MB sau khi cài.

---

## 📝 License

Cá nhân sử dụng. Code mở, không bảo hành.

---

*Tool này không liên quan đến Sony Corporation. Sử dụng tự chịu trách nhiệm. Tác giả không chịu trách nhiệm nếu máy bạn lỡ tắt nhầm app quan trọng (mặc dù tool đã chặn rất nhiều).*
