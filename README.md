# Sony Debloat

Tool web local **dọn app rác** và **tối ưu Sony Xperia** qua ADB. Không root, không unlock bootloader, mọi thao tác đảo ngược được.

## Tool này làm gì

- Tắt/gỡ **165+ app rác Sony** (Facebook ngầm, Lifelog, News Suite, JP carrier apps...)
- Áp dụng **30 preset tối ưu** RAM / pin / privacy / animation / audio
- Phân tích **dung lượng, CPU, notification** từng app
- Cấu hình **APN nhanh** cho SIM Việt (Sony Nhật không preload)
- Kiểm tra **bootloader status** + Sony unlock eligibility
- **76 package cốt lõi** (Play Store, GMS, Camera) bảo vệ ở backend — không tắt nhầm được

## Cài đặt

**Yêu cầu**: Python 3.10+

### Mac/Linux
```bash
git clone https://github.com/ntdazzy/sony-tool.git
cd sony-tool
chmod +x setup_adb.sh run.sh
./setup_adb.sh
```

### Windows
```powershell
git clone https://github.com/ntdazzy/sony-tool.git
cd sony-tool
.\sony-tool.ps1
```

Lần đầu tự setup (ADB + Python venv + newflasher, ~1-2 phút) rồi mở browser.
Lần sau chỉ chạy `.\sony-tool.ps1` → start ngay.

## Chạy

```bash
./run.sh             # Mac/Linux
.\sony-tool.ps1      # Windows (cùng script, auto-detect setup/run)
```

Browser tự mở `http://localhost:8765`.

**Trước khi dùng**: trên máy Sony bật USB Debugging  
*(Cài đặt → Giới thiệu điện thoại → bấm "Số hiệu bản dựng" 7 lần → Cài đặt → Hệ thống → Tuỳ chọn nhà phát triển → Gỡ lỗi USB)*

## Tính năng chính

| Tab | Mô tả |
|---|---|
| **Tổng quan** | Stats + thông tin máy + hướng dẫn |
| **Dọn sạch** | 1-click cleanup, 4 mức (Nhẹ/Vừa/Mạnh/Tối đa), toggle Tắt vs Gỡ hẳn |
| **Tất cả app** | Bảng 200+ package, search + filter, tắt/bật từng cái |
| **Tối ưu** | 30 preset settings tweaks, hiển thị state hiện tại (Đã áp dụng / Mặc định / 1 phần) |
| **Phân tích** | Top app theo dung lượng + CPU/pin + notification — biết ai ăn tài nguyên |
| **APN** | Config 4 nhà mạng VN (Viettel/Vinaphone/Mobifone/Vietnamobile), nút mở thẳng APN settings |
| **Bootloader** | Trạng thái lock + estimate Sony unlock eligibility |
| **Backup** | Tạo backup JSON, export đầy đủ packages + settings + getprop để gửi dev phân tích |

## Multi-model

Curated trên XQ-AS42 (Sony Xperia 5 II JP) nhưng hoạt động với mọi Sony Xperia:
- 80% bloat list là universal Sony — chạy được Xperia 1/5/10 series
- Tool tự ẩn package không tồn tại trên máy cụ thể
- Settings tweaks dùng AOSP keys — không Sony-specific

## Tech

Python 3.10+ · FastAPI · vanilla JS · ADB. Tổng ~50MB sau cài.

Tests: 144 pytest tests, ~0.6s.

## License

Cá nhân sử dụng. Code mở, không bảo hành.
