"""Test endpoints /api/insights/* — storage, battery, notifications."""

import pytest
from fastapi.testclient import TestClient

import app as app_module
from app import _parse_diskstats, _parse_batterystats_checkin

client = TestClient(app_module.app)


# ============ _parse_diskstats ============


def test_parse_diskstats_well_formed():
    sample = """
Package Names: ["com.app.a","com.app.b","com.app.c"]
App Sizes: [1000,2000,3000]
App Data Sizes: [100,200,300]
App Cache Sizes: [10,20,30]
"""
    apps = _parse_diskstats(sample)
    assert len(apps) == 3
    # Sorted by total desc
    assert apps[0]["name"] == "com.app.c"
    assert apps[0]["total_bytes"] == 3330
    assert apps[0]["apk_bytes"] == 3000


def test_parse_diskstats_empty_or_malformed():
    assert _parse_diskstats("no data here") == []
    assert _parse_diskstats("Package Names: []") == []


def test_parse_diskstats_handles_zeros():
    sample = """
Package Names: ["com.x","com.y"]
App Sizes: [0,500]
App Data Sizes: [0,100]
App Cache Sizes: [0,10]
"""
    apps = _parse_diskstats(sample)
    # com.x has 0 total — still included nhưng cuối list
    assert len(apps) == 2
    assert apps[0]["name"] == "com.y"


# ============ _parse_batterystats_checkin ============


def test_parse_batterystats_extracts_cpu():
    sample = """9,1000,l,apk,5,com.example.app,com.example.Service,123
9,1000,l,cpu,5000,3000
9,2000,l,apk,2,com.other.app,com.other.Service,45
9,2000,l,cpu,10000,2000
"""
    apps = _parse_batterystats_checkin(sample)
    # com.other.app has more CPU (12000) than com.example.app (8000)
    assert apps[0]["package"] == "com.other.app"
    assert apps[0]["cpu_ms"] == 12000
    assert apps[1]["package"] == "com.example.app"
    assert apps[1]["cpu_ms"] == 8000


def test_parse_batterystats_skips_invalid():
    sample = "garbage\n9,1,l,cpu,not_a_number,still_invalid\n"
    apps = _parse_batterystats_checkin(sample)
    assert apps == []


# ============ Endpoints ============


def test_storage_endpoint(monkeypatch):
    sample = """
Package Names: ["com.test.app"]
App Sizes: [12345]
App Data Sizes: [100]
App Cache Sizes: [10]
"""
    monkeypatch.setattr(app_module.adb, "shell", lambda *a, **k: sample)
    r = client.get("/api/insights/storage")
    assert r.status_code == 200
    data = r.json()
    assert len(data["apps"]) == 1
    assert data["apps"][0]["name"] == "com.test.app"


def test_storage_endpoint_handles_adb_error(monkeypatch):
    def fail(*a, **k):
        raise app_module.adb.AdbError("device offline")
    monkeypatch.setattr(app_module.adb, "shell", fail)
    r = client.get("/api/insights/storage")
    assert r.status_code == 400


def test_storage_endpoint_unparseable_output(monkeypatch):
    monkeypatch.setattr(app_module.adb, "shell", lambda *a, **k: "no useful data")
    r = client.get("/api/insights/storage")
    assert r.status_code == 200  # vẫn 200 nhưng có warning
    data = r.json()
    assert "warning" in data
    assert data["apps"] == []


def test_battery_endpoint(monkeypatch):
    sample = "9,1,l,apk,5,com.test,com.test.S,1\n9,1,l,cpu,5000,3000\n"
    monkeypatch.setattr(app_module.adb, "shell", lambda *a, **k: sample)
    r = client.get("/api/insights/battery")
    assert r.status_code == 200
    data = r.json()
    assert len(data["top"]) == 1
    assert data["top"][0]["package"] == "com.test"


def test_battery_reset_endpoint(monkeypatch):
    called = {"cmd": None}
    def fake_shell(cmd, serial=None, timeout=20):
        called["cmd"] = cmd
        return ""
    monkeypatch.setattr(app_module.adb, "shell", fake_shell)
    r = client.post("/api/insights/battery-reset")
    assert r.status_code == 200
    assert "--reset" in called["cmd"]


def test_notifications_endpoint(monkeypatch):
    sample = "  pkg=com.facebook.katana\n  pkg=com.facebook.katana\n  pkg=com.example\n"
    monkeypatch.setattr(app_module.adb, "shell", lambda *a, **k: sample)
    r = client.get("/api/insights/notifications")
    assert r.status_code == 200
    data = r.json()
    # com.facebook.katana xuất hiện 2 lần
    facebook = next((a for a in data["top"] if a["package"] == "com.facebook.katana"), None)
    assert facebook is not None
    assert facebook["count"] == 2


def test_notifications_falls_back_when_stats_unavailable(monkeypatch):
    """Một số Android không có `--stats` flag → fallback `dumpsys notification` thường."""
    call_count = {"n": 0}

    def fake_shell(cmd, serial=None, timeout=20):
        call_count["n"] += 1
        if "--stats" in cmd:
            raise app_module.adb.AdbError("unknown flag")
        return "  pkg=com.test\n"

    monkeypatch.setattr(app_module.adb, "shell", fake_shell)
    r = client.get("/api/insights/notifications")
    assert r.status_code == 200
    assert call_count["n"] == 2  # 1 fail + 1 fallback


# ============ New presets ============


def test_private_dns_presets_exist():
    import json
    from pathlib import Path
    presets = json.loads((Path(__file__).parent.parent / "data" / "optimize_presets.json").read_text())["presets"]
    ids = {p["id"] for p in presets}
    assert "private_dns_adguard" in ids
    assert "private_dns_cloudflare" in ids


def test_haptic_intensity_preset_exists():
    import json
    from pathlib import Path
    presets = json.loads((Path(__file__).parent.parent / "data" / "optimize_presets.json").read_text())["presets"]
    ids = {p["id"] for p in presets}
    assert "haptic_intensity_low" in ids


def test_total_preset_count_after_v4():
    import json
    from pathlib import Path
    presets = json.loads((Path(__file__).parent.parent / "data" / "optimize_presets.json").read_text())["presets"]
    # Was 27, +3 new (2 DNS + 1 haptic) = 30
    assert len(presets) >= 30
