"""FastAPI server cho Sony Debloat Tool — chạy local, mở browser tại http://localhost:8765"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import adb_wrapper as adb

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
STATIC_DIR = ROOT / "static"
BACKUP_DIR = ROOT / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Sony Debloat Tool", version="1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _load_json(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def _safe_set() -> set[str]:
    return set(_load_json("safe_list.json")["critical"])


class PackageAction(BaseModel):
    packages: list[str]
    serial: str | None = None


class PresetAction(BaseModel):
    preset_id: str
    serial: str | None = None


class SettingsWrite(BaseModel):
    namespace: str  # global | system | secure
    key: str
    value: str
    serial: str | None = None


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
def status():
    if not adb.adb_available():
        return {
            "adb_installed": False,
            "message": "ADB chưa được cài. Mở Terminal, vào thư mục sony-tool và chạy: ./setup_adb.sh",
        }
    try:
        devices = adb.list_devices()
    except adb.AdbError as e:
        return {"adb_installed": True, "error": str(e), "devices": []}

    connected = [d for d in devices if d.state == "device"]
    info = None
    if len(connected) == 1:
        try:
            info = adb.device_info(connected[0].serial)
        except adb.AdbError as e:
            info = {"error": str(e)}

    return {
        "adb_installed": True,
        "devices": [asdict(d) for d in devices],
        "active_serial": connected[0].serial if len(connected) == 1 else None,
        "device_info": info,
        "multiple_devices": len(connected) > 1,
    }


@app.get("/api/packages")
def get_packages(serial: str | None = None):
    try:
        pkgs = adb.list_packages(serial)
    except adb.AdbError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    bloat = _load_json("bloat_jp.json")
    bloat_index: dict[str, dict] = {}
    for cat in bloat["categories"]:
        for pkg in cat["packages"]:
            bloat_index[pkg["id"]] = {
                "category": cat["title"],
                "category_icon": cat.get("icon", ""),
                "tier": pkg.get("tier", "optional"),
                "label": pkg["label"],
            }

    safe = _safe_set()
    out = []
    bloat_present = 0
    for p in pkgs:
        meta = bloat_index.get(p.name)
        if meta and p.enabled:
            bloat_present += 1
        out.append(
            {
                "name": p.name,
                "path": p.path,
                "is_system": p.is_system,
                "enabled": p.enabled,
                "is_critical": p.name in safe,
                "bloat_category": meta["category"] if meta else None,
                "bloat_tier": meta["tier"] if meta else None,
                "label": meta["label"] if meta else None,
            }
        )
    stats = {
        "total": len(out),
        "enabled": sum(1 for p in out if p["enabled"]),
        "disabled": sum(1 for p in out if not p["enabled"]),
        "user_installed": sum(1 for p in out if not p["is_system"]),
        "system": sum(1 for p in out if p["is_system"]),
        "critical": sum(1 for p in out if p["is_critical"]),
        "bloat_active": bloat_present,
    }
    return {"packages": out, "total": len(out), "stats": stats}


@app.get("/api/bloat-list")
def bloat_list():
    return _load_json("bloat_jp.json")


@app.get("/api/optimize/presets")
def optimize_presets():
    return _load_json("optimize_presets.json")


def _normalize_value(v: str | None) -> str:
    """Chuẩn hoá value để so sánh ('null', '', None đều == default)."""
    if v is None:
        return ""
    s = v.strip().lower()
    if s in ("null", "none", ""):
        return ""
    return s


def _parse_shell_step(shell_cmd: str) -> dict | None:
    """Parse `device_config put <ns> <key> <val>` hoặc `settings put <ns> <key> <val>`."""
    parts = shell_cmd.strip().split(maxsplit=4)
    if len(parts) >= 5 and parts[0] in ("device_config", "settings") and parts[1] == "put":
        return {"tool": parts[0], "namespace": parts[2], "key": parts[3], "expected": parts[4]}
    return None


@app.get("/api/optimize/state")
def optimize_state(serial: str | None = None):
    """Đọc current value của các setting trong mỗi preset → so sánh với apply target.
    Trả về state cho mỗi preset: applied / partial / default / unknown."""
    presets = _load_json("optimize_presets.json")["presets"]
    if not adb.adb_available():
        raise HTTPException(status_code=400, detail="ADB chưa cài.")

    out = []
    for preset in presets:
        steps_status: list[dict] = []
        readable_count = 0
        match_count = 0

        for step in preset["apply"]:
            if "namespace" in step:
                # `settings put <ns> <key> <val>` style
                try:
                    current = adb.settings_get(step["namespace"], step["key"], serial=serial)
                except adb.AdbError as e:
                    steps_status.append({
                        "type": "settings",
                        "namespace": step["namespace"],
                        "key": step["key"],
                        "expected": step["value"],
                        "current": None,
                        "matches": None,
                        "error": str(e),
                    })
                    continue
                norm_current = _normalize_value(current)
                norm_expected = _normalize_value(step["value"])
                matches = norm_current == norm_expected
                readable_count += 1
                if matches:
                    match_count += 1
                steps_status.append({
                    "type": "settings",
                    "namespace": step["namespace"],
                    "key": step["key"],
                    "expected": step["value"],
                    "current": current,
                    "matches": matches,
                })
            elif "shell" in step:
                parsed = _parse_shell_step(step["shell"])
                if parsed:
                    try:
                        if parsed["tool"] == "device_config":
                            current = adb.device_config_get(parsed["namespace"], parsed["key"], serial=serial)
                        else:
                            current = adb.settings_get(parsed["namespace"], parsed["key"], serial=serial)
                    except adb.AdbError as e:
                        steps_status.append({
                            "type": parsed["tool"],
                            "namespace": parsed["namespace"],
                            "key": parsed["key"],
                            "expected": parsed["expected"],
                            "current": None,
                            "matches": None,
                            "error": str(e),
                        })
                        continue
                    norm_current = _normalize_value(current)
                    norm_expected = _normalize_value(parsed["expected"])
                    matches = norm_current == norm_expected
                    readable_count += 1
                    if matches:
                        match_count += 1
                    steps_status.append({
                        "type": parsed["tool"],
                        "namespace": parsed["namespace"],
                        "key": parsed["key"],
                        "expected": parsed["expected"],
                        "current": current,
                        "matches": matches,
                    })
                else:
                    # Shell command không parse được (dumpsys, setprop...) — coi như unknown
                    steps_status.append({
                        "type": "shell",
                        "command": step["shell"],
                        "matches": None,
                    })

        # Xác định state của preset
        if readable_count == 0:
            preset_state = "unknown"
        elif match_count == readable_count:
            preset_state = "applied"
        elif match_count == 0:
            preset_state = "default"
        else:
            preset_state = "partial"

        out.append({
            "id": preset["id"],
            "title": preset["title"],
            "state": preset_state,
            "readable_steps": readable_count,
            "matching_steps": match_count,
            "steps": steps_status,
        })

    return {"presets": out}


def _check_safe(packages: list[str]) -> list[str]:
    safe = _safe_set()
    return [p for p in packages if p in safe]


@app.post("/api/packages/disable")
def disable(req: PackageAction):
    bad = _check_safe(req.packages)
    if bad:
        raise HTTPException(
            status_code=400,
            detail=f"Từ chối tắt package thiết yếu: {', '.join(bad)}. Máy có thể không khởi động.",
        )
    results = []
    for pkg in req.packages:
        try:
            out = adb.disable_package(pkg, req.serial)
            results.append({"package": pkg, "ok": True, "message": out})
        except adb.AdbError as e:
            results.append({"package": pkg, "ok": False, "message": str(e)})
    return {"results": results}


@app.post("/api/packages/enable")
def enable(req: PackageAction):
    results = []
    for pkg in req.packages:
        try:
            out = adb.enable_package(pkg, req.serial)
            results.append({"package": pkg, "ok": True, "message": out})
        except adb.AdbError as e:
            results.append({"package": pkg, "ok": False, "message": str(e)})
    return {"results": results}


@app.post("/api/packages/uninstall")
def uninstall(req: PackageAction):
    bad = _check_safe(req.packages)
    if bad:
        raise HTTPException(
            status_code=400,
            detail=f"Từ chối gỡ package thiết yếu: {', '.join(bad)}.",
        )
    results = []
    for pkg in req.packages:
        try:
            out = adb.uninstall_user(pkg, req.serial)
            results.append({"package": pkg, "ok": True, "message": out})
        except adb.AdbError as e:
            results.append({"package": pkg, "ok": False, "message": str(e)})
    return {"results": results}


@app.post("/api/packages/restore")
def restore(req: PackageAction):
    """Khôi phục package đã `pm uninstall --user 0` bằng install-existing."""
    results = []
    for pkg in req.packages:
        try:
            out = adb.reinstall_existing(pkg, req.serial)
            results.append({"package": pkg, "ok": True, "message": out})
        except adb.AdbError as e:
            results.append({"package": pkg, "ok": False, "message": str(e)})
    return {"results": results}


def _apply_steps(steps: list[dict], serial: str | None) -> list[dict]:
    results = []
    for step in steps:
        try:
            if "shell" in step:
                out = adb.shell(step["shell"], serial=serial)
                results.append({"step": step["shell"], "ok": True, "message": out.strip()})
            else:
                out = adb.settings_put(step["namespace"], step["key"], step["value"], serial=serial)
                desc = f"settings put {step['namespace']} {step['key']} {step['value']}"
                results.append({"step": desc, "ok": True, "message": out})
        except adb.AdbError as e:
            results.append({"step": str(step), "ok": False, "message": str(e)})
    return results


@app.post("/api/optimize/apply")
def optimize_apply(req: PresetAction):
    presets = _load_json("optimize_presets.json")["presets"]
    preset = next((p for p in presets if p["id"] == req.preset_id), None)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy preset: {req.preset_id}")
    return {"results": _apply_steps(preset["apply"], req.serial), "preset": preset["title"]}


@app.post("/api/optimize/revert")
def optimize_revert(req: PresetAction):
    presets = _load_json("optimize_presets.json")["presets"]
    preset = next((p for p in presets if p["id"] == req.preset_id), None)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy preset: {req.preset_id}")
    return {"results": _apply_steps(preset["revert"], req.serial), "preset": preset["title"]}


@app.post("/api/settings/write")
def settings_write(req: SettingsWrite):
    if req.namespace not in {"global", "system", "secure"}:
        raise HTTPException(status_code=400, detail="namespace phải là global/system/secure")
    try:
        out = adb.settings_put(req.namespace, req.key, req.value, serial=req.serial)
    except adb.AdbError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "message": out}


@app.get("/api/backup")
def backup(serial: str | None = None):
    """Xuất danh sách package + trạng thái enabled. Lưu file JSON local."""
    try:
        pkgs = adb.list_packages(serial)
        info = adb.device_info(serial)
    except adb.AdbError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    data = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "device": info,
        "packages": [asdict(p) for p in pkgs],
    }
    fname = f"backup-{time.strftime('%Y%m%d-%H%M%S')}.json"
    (BACKUP_DIR / fname).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"file": fname, "count": len(pkgs), "path": str(BACKUP_DIR / fname)}


@app.get("/api/backups")
def list_backups():
    files = sorted(list(BACKUP_DIR.glob("backup-*.json")) + list(BACKUP_DIR.glob("export-*.json")), reverse=True)
    return {
        "backups": [
            {"name": f.name, "size_kb": round(f.stat().st_size / 1024, 1)} for f in files
        ]
    }


@app.get("/api/export-full")
def export_full(serial: str | None = None):
    """Xuất dump đầy đủ máy (packages + services + getprop + settings) để gửi dev phân tích."""
    try:
        pkgs = adb.list_packages(serial)
        info = adb.device_info(serial)
    except adb.AdbError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    def safe_shell(cmd: str, timeout: int = 20) -> str:
        try:
            return adb.shell(cmd, serial=serial, timeout=timeout)
        except adb.AdbError:
            return ""

    data = {
        "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tool_version": "1.1",
        "device": info,
        "stats": {
            "total_packages": len(pkgs),
            "system": sum(1 for p in pkgs if p.is_system),
            "user_installed": sum(1 for p in pkgs if not p.is_system),
            "enabled": sum(1 for p in pkgs if p.enabled),
            "disabled": sum(1 for p in pkgs if not p.enabled),
        },
        "packages": [asdict(p) for p in pkgs],
        "services_raw": safe_shell("service list", 25),
        "getprop_raw": safe_shell("getprop", 20),
        "settings_global_raw": safe_shell("settings list global", 15),
        "settings_system_raw": safe_shell("settings list system", 15),
        "settings_secure_raw": safe_shell("settings list secure", 15),
    }
    fname = f"export-{time.strftime('%Y%m%d-%H%M%S')}.json"
    fpath = BACKUP_DIR / fname
    fpath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "file": fname,
        "path": str(fpath),
        "count": len(pkgs),
        "size_kb": round(fpath.stat().st_size / 1024, 1),
    }


# ============ Insights endpoints (storage/battery/notifications) ============


def _parse_diskstats(out: str) -> list[dict]:
    """Parse `dumpsys diskstats` để lấy app sizes."""
    import re as _re

    pkg_match = _re.search(r"Package Names: \[([^\]]+)\]", out)
    size_match = _re.search(r"App Sizes: \[([^\]]+)\]", out)
    data_match = _re.search(r"App Data Sizes: \[([^\]]+)\]", out)
    cache_match = _re.search(r"App Cache Sizes: \[([^\]]+)\]", out)

    if not all([pkg_match, size_match, data_match, cache_match]):
        return []

    names = [n.strip().strip('"') for n in pkg_match.group(1).split(",")]

    def _parse_nums(s: str) -> list[int]:
        out_list = []
        for x in s.split(","):
            x = x.strip()
            try:
                out_list.append(int(x))
            except (ValueError, TypeError):
                out_list.append(0)
        return out_list

    sizes = _parse_nums(size_match.group(1))
    data_sizes = _parse_nums(data_match.group(1))
    cache_sizes = _parse_nums(cache_match.group(1))

    apps = []
    for i, name in enumerate(names):
        if not name:
            continue
        apk = sizes[i] if i < len(sizes) else 0
        data = data_sizes[i] if i < len(data_sizes) else 0
        cache = cache_sizes[i] if i < len(cache_sizes) else 0
        apps.append({
            "name": name,
            "apk_bytes": apk,
            "data_bytes": data,
            "cache_bytes": cache,
            "total_bytes": apk + data + cache,
        })
    apps.sort(key=lambda a: a["total_bytes"], reverse=True)
    return apps


@app.get("/api/insights/storage")
def insights_storage(serial: str | None = None):
    """Top app theo dung lượng (APK + data + cache)."""
    try:
        out = adb.shell("dumpsys diskstats", serial=serial, timeout=30)
    except adb.AdbError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    apps = _parse_diskstats(out)
    if not apps:
        return {"apps": [], "total_count": 0, "warning": "Không parse được dumpsys diskstats output."}
    return {"apps": apps[:50], "total_count": len(apps)}


def _parse_batterystats_checkin(out: str) -> list[dict]:
    """Parse `dumpsys batterystats --checkin` lấy top apps theo CPU time."""
    cpu_by_uid: dict[str, int] = {}
    uid_to_pkg: dict[str, str] = {}

    for line in out.splitlines():
        parts = line.split(",")
        if len(parts) < 5:
            continue
        # Format: <version>,<uid>,<aggregation>,<tag>,...
        try:
            tag = parts[3]
        except IndexError:
            continue
        uid = parts[1]
        if tag == "cpu" and len(parts) >= 6:
            try:
                user_ms = int(parts[4])
                sys_ms = int(parts[5])
                cpu_by_uid[uid] = cpu_by_uid.get(uid, 0) + user_ms + sys_ms
            except ValueError:
                continue
        elif tag == "apk" and len(parts) >= 8:
            # apk line: <ver>,<uid>,<agg>,apk,<wakeups>,<package>,<service_name>,<service_time>
            pkg = parts[5] if len(parts) > 5 else ""
            if pkg and uid not in uid_to_pkg:
                uid_to_pkg[uid] = pkg

    apps = []
    for uid, cpu_ms in cpu_by_uid.items():
        if cpu_ms <= 0:
            continue
        apps.append({
            "uid": uid,
            "package": uid_to_pkg.get(uid, f"(uid={uid})"),
            "cpu_ms": cpu_ms,
        })
    apps.sort(key=lambda a: a["cpu_ms"], reverse=True)
    return apps


@app.get("/api/insights/battery")
def insights_battery(serial: str | None = None):
    """Top app theo CPU time tích luỹ (proxy cho pin)."""
    try:
        out = adb.shell("dumpsys batterystats --checkin", serial=serial, timeout=60)
    except adb.AdbError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    apps = _parse_batterystats_checkin(out)
    return {"top": apps[:20], "raw_lines": len(out.splitlines())}


@app.post("/api/insights/battery-reset")
def insights_battery_reset(serial: str | None = None):
    """Reset batterystats để bắt đầu đo từ đầu."""
    try:
        adb.shell("dumpsys batterystats --reset", serial=serial, timeout=20)
        return {"ok": True, "message": "Battery stats đã reset. Dùng máy bình thường, quay lại sau 24h xem top."}
    except adb.AdbError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/insights/notifications")
def insights_notifications(serial: str | None = None):
    """Đếm số notification post bởi mỗi package."""
    import re as _re
    from collections import Counter

    try:
        out = adb.shell("dumpsys notification --stats", serial=serial, timeout=20)
    except adb.AdbError:
        # Fallback: regular dumpsys notification
        try:
            out = adb.shell("dumpsys notification", serial=serial, timeout=20)
        except adb.AdbError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    counts: Counter = Counter()
    for line in out.splitlines():
        m = _re.search(r"pkg=([a-zA-Z][\w.]+)", line)
        if m:
            counts[m.group(1)] += 1

    top = [{"package": pkg, "count": n} for pkg, n in counts.most_common(20)]
    return {"top": top, "unique_apps": len(counts)}


# Sony JP market device codes — bootloader locked by Sony policy
_SONY_JP_MARKET_PREFIXES = (
    "SO-52", "SO-51", "SO-41", "SO-04", "SO-05",  # docomo
    "SOG02", "SOG01", "SOG03", "SOG04",  # au
    "A002SO", "A001SO", "A101SO", "A102SO",  # SoftBank
    "XQ-AS42", "XQ-AS72",  # SIM-free Japan
)


@app.get("/api/bootloader-status")
def bootloader_status(serial: str | None = None):
    """Đọc trạng thái bootloader + estimate unlock eligibility."""
    def getprop(key: str) -> str:
        try:
            return adb.shell(f"getprop {key}", serial=serial, timeout=10).strip()
        except adb.AdbError:
            return ""

    locked_raw = getprop("ro.boot.flash.locked")  # "0"=unlocked, "1"=locked, ""=unknown
    verified = getprop("ro.boot.verifiedbootstate")  # green/yellow/orange/red
    model = getprop("ro.product.model")
    device = getprop("ro.product.device")
    manufacturer = getprop("ro.product.manufacturer")
    build_type = getprop("ro.build.type")  # user/userdebug

    try:
        oem_disallowed = adb.settings_get("global", "oem_unlock_disallowed", serial=serial)
    except adb.AdbError:
        oem_disallowed = ""

    is_jp_market = any(model.upper().startswith(p) for p in _SONY_JP_MARKET_PREFIXES) or any(
        device.upper().startswith(p) for p in _SONY_JP_MARKET_PREFIXES
    )

    # Eligibility estimate
    if is_jp_market:
        eligibility = "no_jp_market"
    elif locked_raw == "0":
        eligibility = "already_unlocked"
    elif manufacturer.lower() not in ("sony", "sonyericsson"):
        eligibility = "not_sony"
    else:
        eligibility = "check_sony_site"

    return {
        "model": model,
        "device": device,
        "manufacturer": manufacturer,
        "build_type": build_type,
        "locked": locked_raw == "1",
        "locked_raw": locked_raw or "unknown",
        "verified_boot_state": verified or "unknown",
        "oem_unlock_disallowed": oem_disallowed,
        "is_jp_market": is_jp_market,
        "eligibility": eligibility,
        "sony_unlock_url": "https://developer.sony.com/develop/open-devices/get-started/unlock-bootloader/",
        "imei_dial_code": "*#06#",
    }


@app.get("/api/apn-list")
def apn_list():
    return _load_json("vn_apn.json")


@app.post("/api/apn-open-settings")
def apn_open_settings(serial: str | None = None):
    """Mở APN settings activity trên máy để user nhập tay."""
    try:
        adb.shell("am start -a android.settings.APN_SETTINGS", serial=serial, timeout=15)
        return {"ok": True, "message": "Đã mở APN settings trên máy. Bấm + để thêm APN mới."}
    except adb.AdbError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/reboot")
def reboot(serial: str | None = None):
    try:
        adb.shell("reboot", serial=serial, timeout=10)
    except adb.AdbError as e:
        # reboot có thể đứt kết nối ngay → coi như ok
        if "closed" not in str(e).lower():
            raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


# ============ ROM (Sony stock firmware) endpoints ============


@app.get("/api/rom/device")
def rom_detect_device(serial: str | None = None):
    """Đọc model + customization code từ máy đang cắm qua ADB → match vào
    resources XperiFirm để biết Product/Model/HwId/Cust UUIDs cần cho Sony API."""
    import rom_resources  # lazy import — cryptography import nặng

    def getprop(key: str) -> str:
        try:
            return adb.shell(f"getprop {key}", serial=serial, timeout=10).strip()
        except adb.AdbError:
            return ""

    model_name = getprop("ro.product.model")
    if not model_name:
        raise HTTPException(status_code=400, detail="Không đọc được ro.product.model — máy chưa cắm hoặc ADB chưa authorize")

    # Customization code: Sony Mobile Communications properties (khác nhau theo model)
    spcode = getprop("ro.semc.product.spcode") or getprop("ro.semc.spc.no")
    cust_number = getprop("ro.semc.product.number") or getprop("ro.semc.version")  # vd "1325-0114"
    build_id = getprop("ro.build.display.id")  # vd "61.0.A.0.420"

    try:
        model = rom_resources.find_model(model_name)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Không tải được resources XperiFirm: {e}") from e

    if model is None:
        return {
            "model_name": model_name,
            "supported": False,
            "current_build": build_id,
            "device_spcode": spcode,
            "device_cust_number": cust_number,
            "message": f"Model '{model_name}' không có trong database XperiFirm — có thể chưa support hoặc model mới chưa update.",
        }

    # Auto-pick customization theo SPC match
    auto_cust = None
    if spcode:
        for c in model.customizations:
            if c.spc == spcode:
                auto_cust = c
                break

    return {
        "supported": True,
        "current_build": build_id,
        "device_spcode": spcode,
        "device_cust_number": cust_number,
        "model": model.to_dict(),
        "auto_cust_id": auto_cust.id if auto_cust else (model.customizations[0].id if model.customizations else None),
    }


@app.get("/api/rom/firmware-list")
def rom_firmware_list(model_name: str, cust_id: str | None = None):
    """List firmware có sẵn cho 1 model + customization từ Sony GCS API."""
    import rom_resources
    import sony_gcs

    model = rom_resources.find_model(model_name)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' không có trong database XperiFirm")

    if cust_id:
        cust = next((c for c in model.customizations if c.id == cust_id), None)
        if cust is None:
            raise HTTPException(status_code=404, detail=f"Customization id={cust_id} không thuộc model {model_name}")
        custs_to_query = [cust]
    else:
        custs_to_query = list(model.customizations)

    results = []
    for c in custs_to_query:
        try:
            fw_list = sony_gcs.query_firmware(model, c)
            results.append(fw_list.to_dict())
        except sony_gcs.GcsError as e:
            results.append({
                "model_name": model.name,
                "cust_name": c.name,
                "device_problem": f"ERROR: {e}",
                "ok": False,
                "entries": [],
            })
    return {"model": model.to_dict(), "results": results}


class RomDownloadStart(BaseModel):
    firmware_url: str
    label: str  # tên hiển thị (vd "XQ-AS42_64.0.A.5.10_keep")


@app.post("/api/rom/download/start")
def rom_download_start(req: RomDownloadStart):
    """Spawn background thread tải firmware. Client subscribe SSE qua
    /api/rom/download/stream?job_id=… để xem progress."""
    import ftf_builder

    if not req.firmware_url.startswith("https://app.swup.update.sony.net/"):
        raise HTTPException(status_code=400, detail="firmware_url phải là URL Sony chính thức")

    job = ftf_builder.start_download_job(req.firmware_url, req.label)
    return {"job_id": job.job_id, "output_dir": str(job.output_dir)}


@app.get("/api/rom/download/stream")
def rom_download_stream(job_id: str):
    """SSE stream — push progress updates về client trong khi download."""
    import json as _json
    import ftf_builder

    job = ftf_builder.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} không tồn tại")

    def event_gen():
        # Drain mọi progress đã queue trước khi client connect
        while True:
            try:
                # block 1s, then heartbeat (chống proxy timeout) nếu queue rỗng và thread vẫn chạy
                item = job.progress_queue.get(timeout=1.0)
            except Exception:
                if not job.thread.is_alive():
                    # Thread chết, no more events
                    break
                yield ": heartbeat\n\n"
                continue
            yield f"data: {_json.dumps(item)}\n\n"
            if item.get("state") in ("done", "error", "cancelled"):
                break

    return StreamingResponse(event_gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # tắt nginx buffering nếu proxy
    })


@app.post("/api/rom/download/cancel/{job_id}")
def rom_download_cancel(job_id: str):
    import ftf_builder
    if not ftf_builder.cancel_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job {job_id} không tồn tại")
    return {"ok": True}


# ============ Flash Mode detection + Flash runner ============


@app.get("/api/rom/flash-mode/scan")
def rom_flash_mode_scan():
    """1-shot scan USB tìm Sony device + xác định có ở Flash Mode không.
    Frontend poll endpoint này hoặc gọi 1 lần để check trước khi enable nút Flash."""
    import flash_mode_detect
    return flash_mode_detect.scan().to_dict()


@app.get("/api/rom/flash/check-newflasher")
def rom_check_newflasher():
    """Check newflasher.exe có sẵn không + path nếu có."""
    import flash_runner
    path = flash_runner.newflasher_path()
    return {
        "available": path is not None,
        "path": str(path) if path else None,
        "expected_path": str(flash_runner.NEWFLASHER_EXE),
        "github_url": "https://github.com/munjeni/newflasher",
        "xda_url": "https://xdaforums.com/t/tool-newflasher-xperia-command-line-flasher.3619426/",
    }


class FlashStart(BaseModel):
    rom_dir: str        # absolute path đến folder chứa .sin files
    flash_ta: bool = False  # Default False = an toàn (skip TA). True = expert risk DRM/camera.


@app.post("/api/rom/flash/start")
def rom_flash_start(req: FlashStart):
    """Spawn newflasher subprocess trên rom_dir. Trả job_id."""
    import flash_runner

    rom_path = Path(req.rom_dir).resolve()
    # Safety: chỉ cho phép path nằm trong vendor/rom_downloads/
    allowed_base = (ROOT / "vendor" / "rom_downloads").resolve()
    try:
        rom_path.relative_to(allowed_base)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"rom_dir phải trong {allowed_base}")

    if not rom_path.exists() or not rom_path.is_dir():
        raise HTTPException(status_code=404, detail=f"rom_dir không tồn tại: {rom_path}")

    if not flash_runner.newflasher_available():
        raise HTTPException(
            status_code=400,
            detail=f"newflasher.exe chưa có. Đặt vào {flash_runner.NEWFLASHER_EXE} (tải từ Github Munjeni)"
        )

    # Verify máy đang ở Flash Mode
    import flash_mode_detect
    result = flash_mode_detect.scan()
    if result.available and not result.flash_mode_device:
        raise HTTPException(
            status_code=400,
            detail="Máy chưa ở Flash Mode. Tắt máy → giữ Vol Down → cắm USB → đợi LED xanh sáng."
        )
    # Nếu pyusb không available, vẫn cho phép start (user xác nhận manual)

    job = flash_runner.start_flash_job(rom_path, flash_ta=req.flash_ta)
    return {"job_id": job.job_id}


@app.get("/api/rom/flash/stream")
def rom_flash_stream(job_id: str):
    """SSE stream progress flash."""
    import json as _json
    import flash_runner

    job = flash_runner.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Flash job {job_id} không tồn tại")

    def event_gen():
        while True:
            try:
                item = job.progress_queue.get(timeout=1.0)
            except Exception:
                if not job.thread.is_alive():
                    break
                yield ": heartbeat\n\n"
                continue
            yield f"data: {_json.dumps(item)}\n\n"
            if item.get("state") in ("done", "error", "cancelled"):
                break

    return StreamingResponse(event_gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@app.post("/api/rom/flash/cancel/{job_id}")
def rom_flash_cancel(job_id: str):
    import flash_runner
    if not flash_runner.cancel_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job {job_id} không tồn tại")
    return {"ok": True}


# ============ ROM downloads management ============


@app.get("/api/rom/downloads/list")
def rom_downloads_list():
    """List các folder ROM đã tải về."""
    dl_dir = ROOT / "vendor" / "rom_downloads"
    if not dl_dir.exists():
        return {"downloads": []}
    out = []
    for d in sorted(dl_dir.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        files = list(d.iterdir())
        total_bytes = sum(f.stat().st_size for f in files if f.is_file())
        out.append({
            "name": d.name,
            "path": str(d),
            "file_count": sum(1 for f in files if f.is_file()),
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / 1024 / 1024, 1),
        })
    return {"downloads": out}


class RomDeletePath(BaseModel):
    path: str


@app.post("/api/rom/downloads/delete")
def rom_downloads_delete(req: RomDeletePath):
    """Xoá 1 folder ROM (must nằm trong vendor/rom_downloads/)."""
    import shutil as _shutil
    target = Path(req.path).resolve()
    allowed_base = (ROOT / "vendor" / "rom_downloads").resolve()
    try:
        target.relative_to(allowed_base)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"path phải trong {allowed_base}")
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Folder không tồn tại: {target}")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="path phải là folder")
    try:
        _shutil.rmtree(target)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Xoá thất bại: {e}") from e
    return {"ok": True, "deleted": str(target)}


@app.post("/api/rom/refresh-resources")
def rom_refresh_resources():
    """Force refresh XperiFirm resources cache (bypass 7-day TTL).
    Dùng khi Sony/Igor update mapping và tool cache cũ."""
    import rom_resources

    try:
        xml_bytes = rom_resources.fetch_resources(force_refresh=True)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Refresh thất bại: {e}") from e
    return {
        "ok": True,
        "xml_size": len(xml_bytes),
        "model_count": len(rom_resources.all_model_names(xml_bytes)),
    }


@app.exception_handler(adb.AdbError)
def adb_error_handler(_, exc):
    return JSONResponse(status_code=400, content={"detail": str(exc)})
