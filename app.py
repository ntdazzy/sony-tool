"""FastAPI server cho Sony Debloat Tool — chạy local, mở browser tại http://localhost:8765"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
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
    except adb.AdbError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    data = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "device": adb.device_info(serial) if serial else adb.device_info(),
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
    """Xuất dump đầy đủ máy (packages + services + getprop) để gửi cho dev phân tích."""
    try:
        pkgs = adb.list_packages(serial)
        info = adb.device_info(serial)
        services = ""
        props = ""
        try:
            services = adb.shell("service list", serial=serial, timeout=20)
        except adb.AdbError:
            pass
        try:
            props = adb.shell("getprop", serial=serial, timeout=20)
        except adb.AdbError:
            pass
    except adb.AdbError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    data = {
        "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tool_version": "1.0",
        "device": info,
        "stats": {
            "total_packages": len(pkgs),
            "system": sum(1 for p in pkgs if p.is_system),
            "user_installed": sum(1 for p in pkgs if not p.is_system),
            "enabled": sum(1 for p in pkgs if p.enabled),
            "disabled": sum(1 for p in pkgs if not p.enabled),
        },
        "packages": [asdict(p) for p in pkgs],
        "services_raw": services,
        "getprop_raw": props,
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


@app.post("/api/reboot")
def reboot(serial: str | None = None):
    try:
        adb.shell("reboot", serial=serial, timeout=10)
    except adb.AdbError as e:
        # reboot có thể đứt kết nối ngay → coi như ok
        if "closed" not in str(e).lower():
            raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


@app.exception_handler(adb.AdbError)
def adb_error_handler(_, exc):
    return JSONResponse(status_code=400, content={"detail": str(exc)})
