"""Test FastAPI endpoints — chủ yếu kiểm tra safe-list enforcement & happy paths."""

import pytest
from fastapi.testclient import TestClient

import app as app_module
from adb_wrapper import Device, PackageInfo

client = TestClient(app_module.app)


# ============ Static & meta endpoints ============


def test_index_serves_html():
    r = client.get("/")
    assert r.status_code == 200
    assert "Sony Debloat" in r.text


def test_bloat_list_endpoint():
    r = client.get("/api/bloat-list")
    assert r.status_code == 200
    data = r.json()
    assert "categories" in data
    assert len(data["categories"]) > 5


def test_optimize_presets_endpoint():
    r = client.get("/api/optimize/presets")
    assert r.status_code == 200
    data = r.json()
    assert len(data["presets"]) >= 20


# ============ Status endpoint ============


def test_status_when_adb_missing(monkeypatch):
    monkeypatch.setattr(app_module.adb, "adb_available", lambda: False)
    r = client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert data["adb_installed"] is False
    assert "message" in data


def test_status_with_no_devices(monkeypatch):
    monkeypatch.setattr(app_module.adb, "adb_available", lambda: True)
    monkeypatch.setattr(app_module.adb, "list_devices", lambda: [])
    r = client.get("/api/status")
    data = r.json()
    assert data["adb_installed"] is True
    assert data["devices"] == []
    assert data["active_serial"] is None
    assert data.get("multiple_devices") is False


def test_status_with_one_device(monkeypatch):
    monkeypatch.setattr(app_module.adb, "adb_available", lambda: True)
    monkeypatch.setattr(
        app_module.adb, "list_devices", lambda: [Device("ABC123", "device")]
    )
    monkeypatch.setattr(
        app_module.adb,
        "device_info",
        lambda s=None: {
            "model": "SO-52A",
            "manufacturer": "Sony",
            "android_version": "12",
            "sdk": "31",
            "build": "test",
            "device": "xperia",
        },
    )
    r = client.get("/api/status")
    data = r.json()
    assert data["active_serial"] == "ABC123"
    assert data["device_info"]["model"] == "SO-52A"


def test_status_with_unauthorized_device(monkeypatch):
    monkeypatch.setattr(app_module.adb, "adb_available", lambda: True)
    monkeypatch.setattr(
        app_module.adb, "list_devices", lambda: [Device("ABC", "unauthorized")]
    )
    r = client.get("/api/status")
    data = r.json()
    assert data["active_serial"] is None  # unauthorized không phải device active
    assert data["devices"][0]["state"] == "unauthorized"


def test_status_with_multiple_devices(monkeypatch):
    monkeypatch.setattr(app_module.adb, "adb_available", lambda: True)
    monkeypatch.setattr(
        app_module.adb,
        "list_devices",
        lambda: [Device("ABC", "device"), Device("DEF", "device")],
    )
    r = client.get("/api/status")
    data = r.json()
    assert data["multiple_devices"] is True
    assert data["active_serial"] is None


# ============ Packages endpoint ============


def test_packages_endpoint_returns_stats(monkeypatch):
    monkeypatch.setattr(
        app_module.adb,
        "list_packages",
        lambda s=None: [
            PackageInfo(name="com.android.systemui", path="/x", is_system=True, enabled=True),
            PackageInfo(name="com.facebook.katana", path="/y", is_system=False, enabled=True),
            PackageInfo(name="com.disabled.app", path="/z", is_system=False, enabled=False),
        ],
    )
    r = client.get("/api/packages")
    assert r.status_code == 200
    data = r.json()
    assert "packages" in data
    assert "stats" in data
    assert data["stats"]["total"] == 3
    assert data["stats"]["enabled"] == 2
    assert data["stats"]["disabled"] == 1
    assert data["stats"]["system"] == 1
    assert data["stats"]["user_installed"] == 2
    assert data["stats"]["critical"] >= 1  # systemui là critical


def test_packages_marks_critical_and_bloat(monkeypatch):
    monkeypatch.setattr(
        app_module.adb,
        "list_packages",
        lambda s=None: [
            PackageInfo(name="com.android.vending", path="/x", is_system=True, enabled=True),
            PackageInfo(name="com.facebook.katana", path="/y", is_system=True, enabled=True),
            PackageInfo(name="com.random.app", path="/z", is_system=False, enabled=True),
        ],
    )
    r = client.get("/api/packages")
    data = r.json()
    by_name = {p["name"]: p for p in data["packages"]}

    assert by_name["com.android.vending"]["is_critical"] is True
    assert by_name["com.android.vending"]["bloat_tier"] is None

    assert by_name["com.facebook.katana"]["is_critical"] is False
    assert by_name["com.facebook.katana"]["bloat_tier"] == "safe"
    assert by_name["com.facebook.katana"]["bloat_category"] is not None

    assert by_name["com.random.app"]["is_critical"] is False
    assert by_name["com.random.app"]["bloat_tier"] is None


# ============ Safety: disable critical packages refused ============


def test_disable_critical_package_rejected(monkeypatch):
    """Disable Play Store → backend phải trả 400."""
    monkeypatch.setattr(app_module.adb, "disable_package", lambda *a, **k: "OK")
    r = client.post(
        "/api/packages/disable", json={"packages": ["com.android.vending"]}
    )
    assert r.status_code == 400
    assert "thiết yếu" in r.json()["detail"]


def test_disable_multiple_with_one_critical_all_rejected(monkeypatch):
    """Nếu có 1 critical trong batch → reject toàn bộ, không gửi lệnh ADB."""
    called = []
    monkeypatch.setattr(
        app_module.adb,
        "disable_package",
        lambda pkg, s=None: called.append(pkg) or "OK",
    )
    r = client.post(
        "/api/packages/disable",
        json={"packages": ["com.facebook.katana", "com.android.systemui"]},
    )
    assert r.status_code == 400
    assert called == [], "Không gửi lệnh ADB nào khi có critical trong batch"


def test_uninstall_critical_rejected(monkeypatch):
    monkeypatch.setattr(app_module.adb, "uninstall_user", lambda *a, **k: "OK")
    r = client.post(
        "/api/packages/uninstall", json={"packages": ["com.google.android.gms"]}
    )
    assert r.status_code == 400


def test_disable_non_critical_succeeds(monkeypatch):
    monkeypatch.setattr(app_module.adb, "disable_package", lambda *a, **k: "Package disabled")
    r = client.post(
        "/api/packages/disable",
        json={"packages": ["com.facebook.katana", "com.sony.nfx.app.sfrc"]},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["results"]) == 2
    assert all(r["ok"] for r in data["results"])


def test_enable_critical_allowed(monkeypatch):
    """Enable không check safe-list — luôn có thể khôi phục."""
    monkeypatch.setattr(app_module.adb, "enable_package", lambda *a, **k: "Enabled")
    r = client.post(
        "/api/packages/enable", json={"packages": ["com.android.vending"]}
    )
    assert r.status_code == 200


def test_disable_handles_adb_error(monkeypatch):
    """Nếu ADB raise lỗi cho 1 package, các package khác vẫn được xử lý."""
    def fake_disable(pkg, serial=None):
        if pkg == "com.fail.app":
            raise app_module.adb.AdbError("device offline")
        return "OK"

    monkeypatch.setattr(app_module.adb, "disable_package", fake_disable)
    r = client.post(
        "/api/packages/disable",
        json={"packages": ["com.facebook.katana", "com.fail.app", "com.sony.nfx.app.sfrc"]},
    )
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) == 3
    assert results[0]["ok"] is True
    assert results[1]["ok"] is False
    assert "device offline" in results[1]["message"]
    assert results[2]["ok"] is True


# ============ Optimize presets ============


def test_optimize_apply_unknown_preset():
    r = client.post("/api/optimize/apply", json={"preset_id": "does_not_exist"})
    assert r.status_code == 404


def test_optimize_apply_known_preset(monkeypatch):
    monkeypatch.setattr(app_module.adb, "settings_put", lambda *a, **k: "OK")
    monkeypatch.setattr(app_module.adb, "shell", lambda *a, **k: "OK")
    r = client.post("/api/optimize/apply", json={"preset_id": "animations_off"})
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert "preset" in data
    assert all(r["ok"] for r in data["results"])


def test_optimize_revert_known_preset(monkeypatch):
    monkeypatch.setattr(app_module.adb, "settings_put", lambda *a, **k: "OK")
    monkeypatch.setattr(app_module.adb, "shell", lambda *a, **k: "OK")
    r = client.post("/api/optimize/revert", json={"preset_id": "animations_off"})
    assert r.status_code == 200


def test_optimize_revert_unknown_preset():
    r = client.post("/api/optimize/revert", json={"preset_id": "nope"})
    assert r.status_code == 404


# ============ Settings write ============


def test_settings_write_validates_namespace():
    r = client.post(
        "/api/settings/write",
        json={"namespace": "bad", "key": "x", "value": "1"},
    )
    assert r.status_code == 400


def test_settings_write_accepts_valid_namespace(monkeypatch):
    monkeypatch.setattr(app_module.adb, "settings_put", lambda *a, **k: "OK")
    r = client.post(
        "/api/settings/write",
        json={"namespace": "global", "key": "x", "value": "1"},
    )
    assert r.status_code == 200


# ============ Backup endpoint ============


def test_backup_creates_file(monkeypatch, tmp_path):
    """Backup tạo file JSON với danh sách package."""
    monkeypatch.setattr(app_module, "BACKUP_DIR", tmp_path)
    monkeypatch.setattr(
        app_module.adb,
        "list_packages",
        lambda s=None: [
            PackageInfo(name="com.x", path="/p", is_system=True, enabled=True)
        ],
    )
    monkeypatch.setattr(
        app_module.adb,
        "device_info",
        lambda s=None: {"model": "test", "manufacturer": "Sony",
                        "android_version": "12", "sdk": "31",
                        "build": "test", "device": "x"},
    )

    r = client.get("/api/backup")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 1
    assert "file" in data
    assert (tmp_path / data["file"]).exists()


def test_list_backups_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "BACKUP_DIR", tmp_path)
    r = client.get("/api/backups")
    assert r.status_code == 200
    assert r.json()["backups"] == []
