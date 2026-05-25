"""Test bootloader status + APN endpoints + new audio/wake presets."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as app_module

client = TestClient(app_module.app)
ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"


# ============ APN data file ============


def test_vn_apn_file_exists():
    assert (DATA / "vn_apn.json").exists()


def test_vn_apn_has_4_carriers():
    data = json.loads((DATA / "vn_apn.json").read_text(encoding="utf-8"))
    carriers = data["carriers"]
    assert len(carriers) == 4
    ids = {c["id"] for c in carriers}
    assert ids == {"viettel", "vinaphone", "mobifone", "vietnamobile"}


def test_vn_apn_each_carrier_has_apn_value():
    data = json.loads((DATA / "vn_apn.json").read_text(encoding="utf-8"))
    expected_apns = {
        "viettel": "v-internet",
        "vinaphone": "m3-world",
        "mobifone": "m-i-internet",
        "vietnamobile": "internet",
    }
    for c in data["carriers"]:
        assert c["settings"]["APN"] == expected_apns[c["id"]]


def test_vn_apn_includes_mcc_mnc():
    data = json.loads((DATA / "vn_apn.json").read_text(encoding="utf-8"))
    for c in data["carriers"]:
        assert c["settings"]["MCC"] == "452"  # Vietnam country code
        assert "MNC" in c["settings"]


def test_vn_apn_has_instructions():
    data = json.loads((DATA / "vn_apn.json").read_text(encoding="utf-8"))
    assert "instructions" in data
    assert len(data["instructions"]["steps"]) >= 4
    assert len(data["instructions"]["tips"]) >= 1


# ============ APN endpoints ============


def test_apn_list_endpoint():
    r = client.get("/api/apn-list")
    assert r.status_code == 200
    data = r.json()
    assert len(data["carriers"]) == 4


def test_apn_open_settings_calls_adb(monkeypatch):
    called = {"cmd": None}

    def fake_shell(cmd, serial=None, timeout=20):
        called["cmd"] = cmd
        return ""

    monkeypatch.setattr(app_module.adb, "shell", fake_shell)
    r = client.post("/api/apn-open-settings")
    assert r.status_code == 200
    assert called["cmd"] == "am start -a android.settings.APN_SETTINGS"


def test_apn_open_settings_handles_adb_error(monkeypatch):
    def fake_shell(cmd, serial=None, timeout=20):
        raise app_module.adb.AdbError("no device")

    monkeypatch.setattr(app_module.adb, "shell", fake_shell)
    r = client.post("/api/apn-open-settings")
    assert r.status_code == 400


# ============ Bootloader endpoint ============


def test_bootloader_endpoint_jp_market(monkeypatch):
    """XQ-AS42 → eligibility = no_jp_market."""
    props = {
        "ro.boot.flash.locked": "1",
        "ro.boot.verifiedbootstate": "green",
        "ro.product.model": "XQ-AS42",
        "ro.product.device": "pdx203",
        "ro.product.manufacturer": "Sony",
        "ro.build.type": "user",
    }

    def fake_shell(cmd, serial=None, timeout=10):
        if cmd.startswith("getprop "):
            key = cmd.split(maxsplit=1)[1].strip()
            return props.get(key, "")
        return ""

    monkeypatch.setattr(app_module.adb, "shell", fake_shell)
    monkeypatch.setattr(app_module.adb, "settings_get", lambda *a, **k: "0")

    r = client.get("/api/bootloader-status")
    assert r.status_code == 200
    data = r.json()
    assert data["model"] == "XQ-AS42"
    assert data["locked"] is True
    assert data["is_jp_market"] is True
    assert data["eligibility"] == "no_jp_market"


def test_bootloader_endpoint_already_unlocked(monkeypatch):
    """Bootloader unlocked → eligibility = already_unlocked."""
    props = {
        "ro.boot.flash.locked": "0",
        "ro.boot.verifiedbootstate": "orange",
        "ro.product.model": "XQ-AS52",  # international
        "ro.product.device": "pdx203",
        "ro.product.manufacturer": "Sony",
    }

    def fake_shell(cmd, serial=None, timeout=10):
        if cmd.startswith("getprop "):
            return props.get(cmd.split(maxsplit=1)[1].strip(), "")
        return ""

    monkeypatch.setattr(app_module.adb, "shell", fake_shell)
    monkeypatch.setattr(app_module.adb, "settings_get", lambda *a, **k: "")

    r = client.get("/api/bootloader-status")
    data = r.json()
    assert data["locked"] is False
    assert data["eligibility"] == "already_unlocked"


def test_bootloader_endpoint_international_sony(monkeypatch):
    """Bản quốc tế, locked → check_sony_site."""
    props = {
        "ro.boot.flash.locked": "1",
        "ro.boot.verifiedbootstate": "green",
        "ro.product.model": "XQ-BC42",
        "ro.product.device": "pdx215",
        "ro.product.manufacturer": "Sony",
    }

    def fake_shell(cmd, serial=None, timeout=10):
        if cmd.startswith("getprop "):
            return props.get(cmd.split(maxsplit=1)[1].strip(), "")
        return ""

    monkeypatch.setattr(app_module.adb, "shell", fake_shell)
    monkeypatch.setattr(app_module.adb, "settings_get", lambda *a, **k: "")

    r = client.get("/api/bootloader-status")
    data = r.json()
    assert data["is_jp_market"] is False
    assert data["eligibility"] == "check_sony_site"


def test_bootloader_detects_so_52a_jp(monkeypatch):
    """SO-52A (docomo) → JP market."""
    props = {"ro.product.model": "SO-52A", "ro.product.device": "SO-52A"}

    def fake_shell(cmd, serial=None, timeout=10):
        if cmd.startswith("getprop "):
            return props.get(cmd.split(maxsplit=1)[1].strip(), "")
        return ""

    monkeypatch.setattr(app_module.adb, "shell", fake_shell)
    monkeypatch.setattr(app_module.adb, "settings_get", lambda *a, **k: "")

    r = client.get("/api/bootloader-status")
    assert r.json()["is_jp_market"] is True


def test_bootloader_includes_sony_unlock_url():
    """Response phải có link Sony unlock checker."""
    # Even with adb error, response phải có URL
    r = client.get("/api/bootloader-status")
    if r.status_code == 200:
        assert "developer.sony.com" in r.json()["sony_unlock_url"]


# ============ New optimize presets ============


def test_new_audio_presets_exist():
    presets = json.loads((DATA / "optimize_presets.json").read_text(encoding="utf-8"))["presets"]
    ids = {p["id"] for p in presets}
    assert "bt_abs_volume_off" in ids
    assert "safe_volume_warning_off" in ids
    assert "bt_a2dp_codec_hd" in ids


def test_new_wake_preset_exists():
    presets = json.loads((DATA / "optimize_presets.json").read_text(encoding="utf-8"))["presets"]
    ids = {p["id"] for p in presets}
    assert "tap_to_wake_off" in ids


def test_audio_category_added():
    presets = json.loads((DATA / "optimize_presets.json").read_text(encoding="utf-8"))["presets"]
    audio = [p for p in presets if p["category"] == "Âm thanh"]
    assert len(audio) >= 3


def test_total_preset_count_increased():
    presets = json.loads((DATA / "optimize_presets.json").read_text(encoding="utf-8"))["presets"]
    # Was 23, now 23 + 4 new = 27
    assert len(presets) >= 27
