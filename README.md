# Sony Debloat Tool

Tool web local giúp dọn app rác và tối ưu máy **Sony Xperia 5 II (XQ-AS42)** bản nội địa Nhật.

Không cần root, không cần unlock bootloader. Mọi thao tác đảo ngược được.

## Tóm tắt — XQ-AS42 làm được gì?

| Việc | Khả thi? | Cách |
|---|---|---|
| Liệt kê toàn bộ app | ✅ | ADB `pm list packages` |
| Tắt app rác (vẫn khôi phục) | ✅ | `pm disable-user --user 0` |
| Gỡ app rác cho user 0 | ✅ | `pm uninstall --user 0` (factory reset thì quay lại) |
| Tinh chỉnh hiệu năng | ✅ | `settings put` (animation, background, pin...) |
| Đổi font hệ thống toàn máy | ❌ | Cần root |
| Đổi font trong launcher | ✅ | Cài Nova/Niagara Launcher |
| Cài ROM custom | ❌ | Bootloader Sony khoá thị trường Nhật, không unlock được |
| Bẻ khoá bootloader bằng exploit | ❌ | Chưa có exploit công khai cho Snapdragon 865 Xperia |

## Cài đặt (chỉ 1 lần)

```bash
cd ~/Desktop/sony-tool
./setup_adb.sh
```

Script sẽ:
1. Kiểm tra Homebrew
2. Cài `android-platform-tools` (chứa `adb`)
3. Tạo Python venv + cài FastAPI

## Bật USB Debugging trên máy Sony

1. **Cài đặt → Giới thiệu điện thoại** → chạm liên tục 7 lần vào **Số hiệu bản dựng**
2. **Cài đặt → Hệ thống → Tuỳ chọn nhà phát triển** → bật **Gỡ lỗi USB**
3. Cắm cáp USB vào Mac (cáp **data**, không phải cáp chỉ sạc)
4. Trên máy hiện popup "Cho phép gỡ lỗi USB?" → tick "luôn cho phép" → **Cho phép**

## Chạy tool

```bash
./run.sh
```

Trình duyệt tự mở [http://localhost:8765](http://localhost:8765).

## Quy trình đề xuất

1. **Tab Tổng quan** → bấm "Làm mới" → xác nhận máy đã kết nối
2. **Tab Backup** → bấm "Tạo backup mới" → lưu trạng thái hiện tại
3. **Tab App rác (đề xuất)** → tick "Tick toàn bộ Safe" → "Tắt các app đã chọn"
4. **Tab Tối ưu** → áp dụng "Tắt animation" (cảm giác máy nhanh hơn rõ)
5. **Khởi động lại máy**, dùng 1–2 ngày
6. Nếu thiếu chức năng → **Tab Tất cả app** → lọc "Đã tắt" → bật lại

## Cấu trúc thư mục

```
sony-tool/
├── app.py                # FastAPI server
├── adb_wrapper.py        # Wrapper subprocess gọi adb
├── data/
│   ├── safe_list.json        # Package CẤM tắt
│   ├── bloat_jp.json         # Bloat list cho XQ-AS42 JP
│   └── optimize_presets.json # Tinh chỉnh hệ thống
├── static/               # Web UI (HTML/CSS/JS)
├── backups/              # File backup tự động lưu
├── setup_adb.sh          # Cài deps
└── run.sh                # Khởi động tool
```

## Thêm app vào danh sách bloat

Sửa `data/bloat_jp.json`, thêm vào category phù hợp:

```json
{
  "id": "com.ten.goi.app",
  "label": "Tên app dễ hiểu"
}
```

Reload tool (Cmd+R trong browser).

## Khôi phục khẩn cấp

Nếu lỡ tắt app khiến máy lạ:

**Cách 1 — qua tool**: Tab Tất cả app → lọc "Đã tắt" → tick → "Bật đã chọn".

**Cách 2 — qua terminal**:
```bash
adb shell pm enable com.ten.goi.app
# hoặc bật lại toàn bộ:
adb shell pm list packages -d | sed 's/package://' | xargs -n1 -I{} adb shell pm enable {}
```

**Cách 3 — cuối cùng**: Factory reset trong **Cài đặt → Hệ thống → Đặt lại**.

## Cảnh báo

- KHÔNG tắt package trong `data/safe_list.json` — tool đã chặn nhưng đừng cố bypass.
- Sau khi tắt một loạt app, **khởi động lại máy** trước khi đánh giá.
- Một số app Sony có liên kết với nhau — tắt 1 cái có thể làm cái khác lỗi. Nếu thấy lạ → bật lại cái vừa tắt.
