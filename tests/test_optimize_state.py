"""Test endpoint /api/optimize/state — đọc current setting trên máy và so sánh với preset target."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import app as app_module

client = TestClient(app_module.app)


# ============ Helpers _normalize_value + _parse_shell_step ============


def test_normalize_value_handles_null():
    from app import _normalize_value
    assert _normalize_value(None) == ""
    assert _normalize_value("null") == ""
    assert _normalize_value("NULL") == ""
    assert _normalize_value("") == ""
    assert _normalize_value("  ") == ""


def test_normalize_value_handles_real_values():
    from app import _normalize_value
    assert _normalize_value("0") == "0"
    assert _normalize_value("1") == "1"
    assert _normalize_value("  0.5 ") == "0.5"
    assert _normalize_value("True") == "true"


def test_parse_shell_step_settings_put():
    from app import _parse_shell_step
    result = _parse_shell_step("settings put global low_power_trigger_level 25")
    assert result == {
        "tool": "settings",
        "namespace": "global",
        "key": "low_power_trigger_level",
        "expected": "25",
    }


def test_parse_shell_step_device_config():
    from app import _parse_shell_step
    result = _parse_shell_step("device_config put activity_manager max_phantom_processes 3")
    assert result == {
        "tool": "device_config",
        "namespace": "activity_manager",
        "key": "max_phantom_processes",
        "expected": "3",
    }


def test_parse_shell_step_returns_none_for_other_commands():
    from app import _parse_shell_step
    assert _parse_shell_step("dumpsys deviceidle enable all") is None
    assert _parse_shell_step("settings delete global foo") is None
    assert _parse_shell_step("setprop debug.x true") is None


# ============ Endpoint /api/optimize/state ============


def test_state_endpoint_requires_adb(monkeypatch):
    """ADB chưa cài → 400."""
    monkeypatch.setattr(app_module.adb, "adb_available", lambda: False)
    r = client.get("/api/optimize/state")
    assert r.status_code == 400


def test_state_endpoint_returns_all_presets(monkeypatch):
    """Phải trả về state cho mọi preset."""
    monkeypatch.setattr(app_module.adb, "adb_available", lambda: True)
    monkeypatch.setattr(app_module.adb, "settings_get", lambda ns, k, serial=None: "1")
    monkeypatch.setattr(app_module.adb, "device_config_get", lambda ns, k, serial=None: "null")
    monkeypatch.setattr(app_module.adb, "shell", lambda *a, **k: "")

    r = client.get("/api/optimize/state")
    assert r.status_code == 200
    data = r.json()
    assert "presets" in data
    # Phải có ít nhất 14 preset (~23 hiện tại)
    assert len(data["presets"]) >= 14
    for ps in data["presets"]:
        assert "id" in ps
        assert "title" in ps
        assert "state" in ps
        assert ps["state"] in {"applied", "default", "partial", "unknown"}
        assert "steps" in ps


def test_state_detects_applied_preset(monkeypatch):
    """Nếu setting hiện tại == expected → state = applied."""
    monkeypatch.setattr(app_module.adb, "adb_available", lambda: True)
    # animations_off preset đặt 3 setting về "0"
    monkeypatch.setattr(app_module.adb, "settings_get", lambda ns, k, serial=None: "0")
    monkeypatch.setattr(app_module.adb, "device_config_get", lambda ns, k, serial=None: "0")
    monkeypatch.setattr(app_module.adb, "shell", lambda *a, **k: "")

    r = client.get("/api/optimize/state")
    data = r.json()
    animations_off = next(p for p in data["presets"] if p["id"] == "animations_off")
    assert animations_off["state"] == "applied"
    assert animations_off["matching_steps"] == animations_off["readable_steps"]


def test_state_detects_default_preset(monkeypatch):
    """Nếu setting hiện tại == default (vd '1' cho animations) → state = default."""
    monkeypatch.setattr(app_module.adb, "adb_available", lambda: True)
    # animations_off target = "0", current = "1" (default Android)
    monkeypatch.setattr(app_module.adb, "settings_get", lambda ns, k, serial=None: "1")
    monkeypatch.setattr(app_module.adb, "device_config_get", lambda ns, k, serial=None: "null")
    monkeypatch.setattr(app_module.adb, "shell", lambda *a, **k: "")

    r = client.get("/api/optimize/state")
    data = r.json()
    animations_off = next(p for p in data["presets"] if p["id"] == "animations_off")
    assert animations_off["state"] == "default"
    assert animations_off["matching_steps"] == 0


def test_state_detects_partial(monkeypatch):
    """Nếu 1 step match, 1 step không → state = partial."""
    monkeypatch.setattr(app_module.adb, "adb_available", lambda: True)
    # animations_off có 3 step: window/transition/animator_duration_scale
    # Giả lập: window match (=0), transition không (=1), animator không (=1)
    call_count = {"n": 0}

    def fake_get(ns, k, serial=None):
        call_count["n"] += 1
        if "window" in k:
            return "0"  # matches expected "0"
        return "1"  # doesn't match expected "0"

    monkeypatch.setattr(app_module.adb, "settings_get", fake_get)
    monkeypatch.setattr(app_module.adb, "device_config_get", lambda ns, k, serial=None: "null")
    monkeypatch.setattr(app_module.adb, "shell", lambda *a, **k: "")

    r = client.get("/api/optimize/state")
    data = r.json()
    animations_off = next(p for p in data["presets"] if p["id"] == "animations_off")
    assert animations_off["state"] == "partial"
    assert 0 < animations_off["matching_steps"] < animations_off["readable_steps"]


def test_state_handles_adb_error_gracefully(monkeypatch):
    """Nếu ADB raise lỗi cho 1 step, vẫn trả về kết quả với error field."""
    monkeypatch.setattr(app_module.adb, "adb_available", lambda: True)

    def failing_get(ns, k, serial=None):
        raise app_module.adb.AdbError("device offline")

    monkeypatch.setattr(app_module.adb, "settings_get", failing_get)
    monkeypatch.setattr(app_module.adb, "device_config_get", failing_get)

    r = client.get("/api/optimize/state")
    # Tổng thể vẫn 200, không crash
    assert r.status_code == 200
    data = r.json()
    # Mỗi preset state = unknown (vì không đọc được)
    for ps in data["presets"]:
        # Step nào có matches=None do error
        error_steps = [s for s in ps["steps"] if s.get("matches") is None and "error" in s]
        assert len(error_steps) > 0 or ps["state"] == "unknown"
