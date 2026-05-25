# Sony Debloat Tool

Tool web local giúp **dọn app rác** và **tối ưu hiệu năng** cho điện thoại Sony Xperia 5 II (model nội địa Nhật **XQ-AS42**). Không cần root, không cần unlock bootloader, mọi thao tác đảo ngược được.

---

## 📋 Mục lục

1. [Mô tả tổng quan](#mô-tả-tổng-quan)
2. [Tính năng chính](#tính-năng-chính)
3. [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
4. [Cài đặt](#cài-đặt)
5. [Sử dụng](#sử-dụng)
6. [Cấu trúc thư mục](#cấu-trúc-thư-mục)
7. [Bảo mật & an toàn](#bảo-mật--an-toàn)
8. [Tuỳ biến](#tuỳ-biến)
9. [API reference](#api-reference)
10. [Troubleshooting](#troubleshooting)
11. [FAQ](#faq)

---

## Mô tả tổng quan

### Vấn đề

Sony Xperia 5 II bản nội địa Nhật (XQ-AS42, SO-52A, SOG02, A002SO) đi kèm:
- **Bloat từ Sony**: News Suite, Lifelog, 3D Creator, Theme Engine, Smart Connect, Help, Tips...
- **Bloat từ nhà mạng JP**: G-Guide TV, iWnn IME, Docomo OSV...
- **Bloat từ partner**: Facebook (4 service ngầm), Amazon, Netflix activator, LinkedIn, LINE...
- **Bloat từ Google không cần**: Drive, Maps, YouTube, Gmail (nếu không dùng).

Sony **khoá bootloader** cho thị trường Nhật → không cài được ROM custom, không root được. Cách duy nhất để dọn là dùng **ADB** (`pm disable-user` / `pm uninstall --user 0`).

### Giải pháp

Tool web local chạy trên Mac/Windows, kết nối máy Sony qua USB (ADB):
- **GUI rõ ràng** (tiếng Việt) thay vì gõ lệnh terminal
- **Bloat list 165 package** đã curate cho XQ-AS42 JP
- **Safe-list 76 package cốt lõi** chặn ở backend — không thể tắt nhầm app hệ thống
- **1-click cleanup** với backup tự động + 11 tối ưu khách quan
- **Khôi phục được** mọi thao tác (`pm enable` hoặc `pm install-existing`)

### Kiến trúc

```
┌─────────────┐         ┌──────────────┐         ┌────────┐         ┌─────────┐
│   Browser   │ ◄──────►│  FastAPI     │ ◄──────►│  ADB   │ ◄──────►│  Sony   │
│ (HTML/JS)   │  HTTP   │  (Python)    │ subproc │ binary │   USB   │  phone  │
└─────────────┘         └──────────────┘         └────────┘         └─────────┘
   localhost:8765         localhost:8765           PATH               cable
```

- **Frontend**: HTML + vanilla JS + CSS (no framework, không build step)
- **Backend**: Python FastAPI, port 8765, chạy local
- **Storage**: JSON files trong `data/`, backup trong `backups/`
- **Communication**: ADB qua `subprocess.run()`

---

## Tính năng chính

### 🚀 1-click cleanup
Card nổi bật ở tab "Dọn sạch":
1. Backup trạng thái hiện tại
2. Tắt/Gỡ toàn bộ bloat tier "Tối đa" (~140 app)
3. Áp dụng 11 tối ưu khách quan (animation, RAM, Wi-Fi scan, telemetry, ad tracking, AOD, network suggestions, Live Caption...)
4. Đề nghị khởi động lại máy

Toggle **Tắt** (an toàn) vs **🗑️ Gỡ hẳn** (sạch hơn).

### 🎚️ 4 mức cleanup thủ công

| Mức | Bloat tier | Mô tả |
|---|---|---|
| 🟢 Nhẹ | safe | Facebook, partner apps, JP-only, ad services |
| 🔵 Vừa *(đề xuất)* | safe + recommended | Thêm Sony Music/Album/Email/Calendar, Lifelog, service ngầm |
| 🟡 Mạnh | + aggressive | Thêm FOTA scheduler, call log backup, SMS push, service menu |
| 🔴 Tối đa | + optional | Thêm Google apps không dùng (Drive, Maps, YouTube...) |

### 📦 Quản lý từng app
Tab "Tất cả app" — bảng filter + search:
- Filter: User-installed / System / Disabled / Enabled / In bloat list / Critical
- Search: gõ "facebook" / "sony" để lọc nhanh
- Action: Tắt/Bật từng app hoặc bulk select

### ⚡ 23 tối ưu hiệu năng
Chia 5 nhóm:
- **Tốc độ** (2): tắt animation, animation 50%
- **Hiệu năng** (3): giới hạn 3 process, cached process limit, tắt haptic/sound chạm
- **Pin** (10): tắt Wi-Fi scan, AOD, lift-to-wake, ringtone vibrate, screen timeout 30s, cảnh báo pin 25%, auto-rotate, adaptive brightness, Wi-Fi notif, doze aggressive
- **Hiển thị** (3): force dark mode, Live Caption off, charging sound off
- **Riêng tư** (5): tắt Google Backup, telemetry, ad tracking, network suggestions, captive portal check

Mỗi preset có **Áp dụng** + **Khôi phục mặc định** riêng.

### 💾 Backup & export
- **Tạo backup mới**: lưu JSON danh sách app + trạng thái
- **Xuất chi tiết**: dump đầy đủ (packages + services + getprop) để gửi dev phân tích

### 🌓 Theme
Light mode (mặc định) / Dark mode. Toggle 🌙/☀️ ở góc trên phải. Lưu vào browser localStorage.

---

## Yêu cầu hệ thống

### Mac / Linux
- macOS 10.14+ hoặc Linux modern distro
- **Python 3.10+** (cài qua `brew install python` hoặc dùng Python sẵn)
- **Homebrew** (cho setup tự động cài ADB)
- Cáp USB **data** (không phải cáp chỉ sạc)

### Windows
- Windows 10 / 11
- **Python 3.10+** từ [python.org](https://www.python.org/downloads/) — **tick "Add Python to PATH"** khi cài
- PowerShell (sẵn có)
- Cáp USB **data**

### Điện thoại Sony
- Bản XQ-AS42 (cũng work với SO-52A, SOG02, A002SO và Xperia khác — bloat list có thể không trùng 100%)
- Đã bật **Developer Options** + **USB Debugging**
- Android 10+ (preset "giới hạn 3 process" + "cached process limit" cần Android 12+)

---

## Cài đặt

### Mac / Linux

```bash
cd ~/Desktop/sony-tool
chmod +x setup_adb.sh run.sh
./setup_adb.sh
```

Script sẽ:
1. Kiểm tra Homebrew
2. Cài `android-platform-tools` (chứa adb + fastboot)
3. Tạo Python virtual env trong `.venv/`
4. Cài FastAPI + uvicorn

### Windows

Mở PowerShell trong folder `sony-tool`:

```powershell
.\setup_adb.ps1
```

Nếu lỗi "running scripts is disabled":
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Script sẽ:
1. Kiểm tra Python
2. Tải `platform-tools-latest-windows.zip` từ Google (~10 MB)
3. Giải nén ra `platform-tools/`
4. Tạo Python venv + cài deps

### Bật USB Debugging trên máy Sony (1 lần)

1. **Cài đặt → Giới thiệu điện thoại** → cuộn xuống cuối → chạm liên tục **7 lần** vào **Số hiệu bản dựng** (Build number)
2. Quay lại **Cài đặt → Hệ thống → Tuỳ chọn nhà phát triển** → bật **Gỡ lỗi USB**
3. Cắm cáp USB vào máy tính, kéo notification shade xuống → bấm "Charging this device via USB" → chọn **File transfer**
4. Trên máy hiện popup **"Cho phép gỡ lỗi USB?"** → tick **Luôn cho phép** → **Cho phép**

---

## Sử dụng

### Khởi động tool

**Mac/Linux**:
```bash
./run.sh
```

**Windows**:
```powershell
.\run.ps1
```

Trình duyệt tự mở `http://localhost:8765`.

### Quy trình đề xuất (lần đầu)

1. **Tab Tổng quan** → bấm **↻** ở góc trên phải → xác nhận đã thấy thông tin máy
2. **Tab Backup** → bấm **💾 Tạo backup mới**
3. **Tab Backup** → bấm **📤 Xuất chi tiết** → gửi file cho dev nếu muốn bloat list khớp 100% máy bạn
4. **Tab Dọn sạch** → bấm **🚀 Bắt đầu — máy sạch trong 1 phút** (mặc định Gỡ hẳn ở mức Tối đa)
5. Đợi 30-60s, xác nhận **🔄 Khởi động lại máy**
6. Sau khi máy bật lại, dùng 1-2 ngày
7. Nếu thiếu app nào → vào CH Play cài lại
8. Nếu thiếu chức năng nào → **Tab Tất cả app** → lọc **Đã tắt** → tìm + bật lại

### Quy trình thủ công (kiểm soát hơn)

1. **Tab Dọn sạch** → cuộn xuống "Hoặc chọn thủ công theo mức"
2. Chọn tier mong muốn (Nhẹ/Vừa/Mạnh/Tối đa)
3. Bấm **Xem danh sách ▾** để review trước
4. Bấm **🧹 Tắt tất cả đã chọn**
5. Vào **Tab Tối ưu** → áp dụng từng preset bạn muốn

---

## Cấu trúc thư mục

```
sony-tool/
├── README.md                    # File này
├── requirements.txt             # Python deps (fastapi, uvicorn)
├── app.py                       # FastAPI server (300 dòng)
├── adb_wrapper.py               # Wrapper subprocess gọi adb
│
├── data/
│   ├── safe_list.json           # 76 package CẤM tắt (Play Store, GMS, Camera...)
│   ├── bloat_jp.json            # 165 package bloat XQ-AS42 JP (11 nhóm, 4 tier)
│   └── optimize_presets.json    # 23 preset tinh chỉnh
│
├── static/                      # Frontend (vanilla, no build)
│   ├── index.html               # Single page app
│   ├── style.css                # CSS variables, dark + light theme
│   └── app.js                   # Logic (tabs, API calls, 1-click, modal)
│
├── scripts/
│   ├── export_packages.sh       # Dump full package list (Mac/Linux)
│   └── export_packages.bat      # Tương tự (Windows)
│
├── backups/                     # Auto-created, lưu file backup-*.json + export-*.json
├── platform-tools/              # ADB binary (Windows tải về đây)
├── .venv/                       # Python virtual env
│
├── setup_adb.sh                 # Setup Mac/Linux (Homebrew + venv)
├── setup_adb.ps1                # Setup Windows (download platform-tools + venv)
├── run.sh                       # Khởi động uvicorn (Mac/Linux)
└── run.ps1                      # Khởi động uvicorn (Windows)
```

---

## Bảo mật & an toàn

### 3 lớp bảo vệ

**1. Safe-list backend chặn cứng**

File `data/safe_list.json` liệt kê 76 package **không thể tắt**. Backend kiểm tra mọi POST `/api/packages/disable` và `/api/packages/uninstall` — nếu request chứa bất kỳ package nào trong safe-list, server trả 400 ngay, không gửi lệnh ADB nào.

Các package được bảo vệ:
- **CH Play & Google core**: `com.android.vending`, `com.google.android.gms`, `com.google.android.gsf`, `com.google.android.webview`, `com.google.android.tts`
- **Cellular & emergency**: `com.android.phone`, `com.android.dialer`, `com.android.cellbroadcastservice`, `com.android.cellbroadcastreceiver`
- **Camera**: `com.sonymobile.PhotoPro`, `com.sonyericsson.android.camera`, `com.sonymobile.cameracommon`
- **Providers**: media, contacts, telephony, settings, calendar, downloads
- **System UI**: `com.android.systemui`, `com.android.settings`
- **Network**: NetworkStack, captiveportallogin, Bluetooth, NFC, UWB (Android 12+)
- **Permission**: permissioncontroller, role manager, intentresolver
- **Qualcomm modem**: callfeaturessetting, qms.service, telephonyservice, ims

**2. "Tắt" thay vì "Gỡ" làm mặc định**

`pm disable-user --user 0` chỉ marker app là disabled, **giữ nguyên file APK trong `/system/`**. Bật lại bằng 1 lệnh `pm enable`. Khác với `pm uninstall --user 0` (cũng giữ APK nhưng xoá data) và `rm /system/app/Foo.apk` (xoá thật, cần root).

User có thể chọn "Gỡ hẳn" (uninstall --user 0) nếu muốn sạch hơn — vẫn khôi phục được bằng `cmd package install-existing`.

**3. Backup tự động trước mỗi cleanup**

1-click flow tự backup trước khi xử lý gì. File `backup-YYYYMMDD-HHMMSS.json` lưu danh sách app + trạng thái enabled. Restore manually bằng cách so sánh + bật lại các app cần.

### Phục hồi khẩn cấp

Nếu lỡ tắt nhầm gây UI lạ:

**Cách 1 — qua tool**:
- Tab "Tất cả app" → filter "Đã tắt" → tick → "Bật đã chọn"

**Cách 2 — terminal**:
```bash
# Bật lại 1 app
adb shell pm enable com.ten.goi.app

# Bật lại TOÀN BỘ app đang disabled
adb shell "pm list packages -d" | sed 's/package://' | xargs -n1 -I{} adb shell pm enable {}
```

**Cách 3 — factory reset**:
- Cài đặt → Hệ thống → Đặt lại → Đặt lại thiết bị (mất data nhưng tất cả app quay lại)

---

## Tuỳ biến

### Thêm app vào bloat list

Sửa `data/bloat_jp.json`, thêm vào category phù hợp:

```json
{
  "id": "com.ten.goi.app",
  "label": "Tên dễ hiểu",
  "tier": "safe"
}
```

Tiers:
- `safe` — không ảnh hưởng tính năng nào
- `recommended` — bạn không dùng, nên tắt cho máy nhẹ
- `aggressive` — chỉ tắt nếu hiểu rõ, có thể mất vài chức năng phụ
- `optional` — tuỳ nhu cầu (vd Google apps)

Reload tool (Cmd+R / Ctrl+R) để áp dụng.

### Thêm preset tối ưu

Sửa `data/optimize_presets.json`:

```json
{
  "id": "my_preset_id",
  "icon": "🔧",
  "category": "Tốc độ",
  "title": "Tên hiển thị",
  "description": "Mô tả ngắn",
  "warning": "Cảnh báo (optional)",
  "apply": [
    {"namespace": "global", "key": "some_setting", "value": "0"},
    {"shell": "any adb shell command"}
  ],
  "revert": [
    {"namespace": "global", "key": "some_setting", "value": "1"}
  ]
}
```

### Bảo vệ thêm package

Thêm vào `data/safe_list.json`:

```json
{
  "critical": [
    "com.android.systemui",
    "com.example.never.disable.this"
  ]
}
```

---

## API reference

Tất cả endpoint chạy trên `http://localhost:8765`. Không có auth (chỉ chạy local).

| Method | Path | Mô tả |
|---|---|---|
| GET | `/` | Trang chủ HTML |
| GET | `/api/status` | Trạng thái ADB + device info |
| GET | `/api/packages?serial=<s>` | Liệt kê tất cả package + tier + flag critical |
| GET | `/api/bloat-list` | Curated bloat list từ `data/bloat_jp.json` |
| GET | `/api/optimize/presets` | Danh sách 23 preset |
| POST | `/api/packages/disable` | Body: `{packages: [...], serial?}` |
| POST | `/api/packages/enable` | Body: `{packages: [...], serial?}` |
| POST | `/api/packages/uninstall` | `pm uninstall --user 0`, body như disable |
| POST | `/api/packages/restore` | `cmd package install-existing`, body như disable |
| POST | `/api/optimize/apply` | Body: `{preset_id, serial?}` |
| POST | `/api/optimize/revert` | Body: `{preset_id, serial?}` |
| POST | `/api/settings/write` | Body: `{namespace, key, value, serial?}` |
| GET | `/api/backup?serial=<s>` | Tạo file backup mới, trả `{file, path, count}` |
| GET | `/api/export-full?serial=<s>` | Dump packages + services + getprop |
| GET | `/api/backups` | List file backup đã tạo |
| POST | `/api/reboot?serial=<s>` | Reboot máy qua ADB |

Endpoint disable/uninstall **luôn check safe-list** và refuse với HTTP 400 nếu chạm package critical.

---

## Troubleshooting

### `adb devices` không thấy máy

Theo thứ tự khả năng:

**1. Cáp chỉ sạc**
- Cáp rẻ tiền / kèm cục sạc 5W / kèm tai nghe thường chỉ truyền điện
- Đổi cáp khác (loại data, có chữ "data" hoặc tested với máy tính)

**2. USB mode sai**
- Vuốt notification shade trên máy → có thông báo "Charging via USB" → bấm → chọn **File transfer** (không phải Charging only)

**3. USB Debugging chưa bật**
- Cài đặt → Hệ thống → Tuỳ chọn nhà phát triển → "Gỡ lỗi USB" phải ON

**4. Authorization cũ còn lưu**
- Trên máy: Tuỳ chọn nhà phát triển → bấm "Thu hồi quyền gỡ lỗi USB"
- Rút cáp, cắm lại
- Trên Mac: `adb kill-server && adb start-server`
- Popup sẽ hiện lại trên máy

**5. Hackintosh USB issue**
- Hackintosh hay có vấn đề với USB injection / kext mapping
- Thử port USB 2.0 thay vì USB 3.0 (USB 2.0 ổn hơn cho ADB trên Hackintosh)
- Hoặc chạy tool trên máy Windows / Mac thật

**6. WSL2 / Docker**
- Tool chạy native, không cần WSL hay Docker
- Nếu Python trong WSL → adb từ Windows không kết nối được tới WSL — chạy native Windows

### Tool chạy nhưng không kết nối server

- Check port 8765: `lsof -i:8765` (Mac) hoặc `netstat -an | findstr 8765` (Windows)
- Nếu bị chiếm: kill process khác hoặc đổi port trong `run.sh` / `run.ps1`

### Preset không có hiệu ứng

- Một số preset (AOD off, Lift-to-Wake off) dùng key AOSP gốc. Sony Xperia có thể override → vào Cài đặt tắt thủ công
- Preset `background_limit_3` và `cached_processes_limit` cần **Android 12+**
- Sony STAMINA mode có thể conflict với "Doze aggressive"

### App tắt rồi mà vẫn thấy chạy

- Reboot máy. Vài app cache phải reboot mới biến mất
- Check lại bằng `adb shell pm list packages -d` — app phải nằm trong list disabled

---

## FAQ

**Q: Tool có gửi data của tôi đi đâu không?**  
A: Không. Server chạy 100% local trên máy bạn (`127.0.0.1:8765`), không có gọi internet nào. Source code mở, đọc được.

**Q: Bootloader có unlock được không?**  
A: KHÔNG. Sony chính sách không cấp mã unlock cho thị trường Nhật (XQ-AS42, SO-52A, SOG02, A002SO). Snapdragon 865 secure boot — không có exploit công khai cho Android 10+.

**Q: Đổi font hệ thống được không?**  
A: KHÔNG, không có root. Workaround: cài Nova/Niagara Launcher (đổi font tên app), đổi cỡ chữ trong Cài đặt → Hiển thị.

**Q: "Tắt" và "Gỡ" khác nhau thế nào?**  
A: 
- **Tắt** (`pm disable-user`): app ẩn icon, không chạy, dữ liệu vẫn còn. Bật lại 1 lệnh.
- **Gỡ hẳn** (`pm uninstall --user 0`): app gỡ cho user 0, dữ liệu xoá, APK vẫn trong `/system`. Khôi phục bằng `cmd package install-existing`.

**Q: Sau factory reset, app đã gỡ có quay lại không?**  
A: Có. Cả "Tắt" và "Gỡ --user 0" đều không xoá APK trong system. Factory reset = reset user data → app quay lại.

**Q: Có khác gì với mấy app debloat trên Play Store?**  
A: App trên Play Store **không thể** disable system app (Android security). Cần ADB từ PC. Tool này là wrapper GUI cho ADB.

**Q: Chạy được trên Android không phải Sony không?**  
A: Backend chạy được (vẫn liệt kê + disable package). Bloat list trong `data/bloat_jp.json` là Sony-specific — sẽ không khớp với Samsung/Xiaomi. Cần sửa list cho hãng khác.

---

## License

Cá nhân sử dụng. Code mở, không bảo hành.

## Acknowledgements

Cảm ơn Sony vì khoá bootloader 😉
