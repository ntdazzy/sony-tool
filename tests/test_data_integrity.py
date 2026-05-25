"""Test tính nguyên vẹn của data files — safe_list, bloat_jp, optimize_presets."""

import json
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"


def _load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


# ============ safe_list.json ============


def test_safe_list_is_valid_json():
    data = _load("safe_list.json")
    assert "critical" in data
    assert isinstance(data["critical"], list)


def test_safe_list_contains_play_store():
    safe = set(_load("safe_list.json")["critical"])
    assert "com.android.vending" in safe, "Play Store phải được bảo vệ"


def test_safe_list_contains_google_services():
    safe = set(_load("safe_list.json")["critical"])
    assert "com.google.android.gms" in safe
    assert "com.google.android.gsf" in safe


def test_safe_list_contains_camera_phone_sysui():
    safe = set(_load("safe_list.json")["critical"])
    assert "com.android.systemui" in safe
    assert "com.android.phone" in safe
    assert "com.android.settings" in safe


def test_safe_list_no_duplicates():
    pkgs = _load("safe_list.json")["critical"]
    assert len(pkgs) == len(set(pkgs)), "Có package trùng trong safe_list"


def test_safe_list_size_reasonable():
    safe = _load("safe_list.json")["critical"]
    assert 50 <= len(safe) <= 200, f"Safe list size bất thường: {len(safe)}"


# ============ bloat_jp.json ============


def test_bloat_list_valid_structure():
    data = _load("bloat_jp.json")
    assert "categories" in data
    assert len(data["categories"]) > 5

    valid_tiers = {"safe", "recommended", "aggressive", "optional"}
    for cat in data["categories"]:
        assert "id" in cat, f"Category thiếu id: {cat}"
        assert "title" in cat
        assert "packages" in cat
        for pkg in cat["packages"]:
            assert "id" in pkg, f"Package thiếu id trong {cat['title']}: {pkg}"
            assert "label" in pkg
            assert "tier" in pkg
            assert pkg["tier"] in valid_tiers, f"Tier không hợp lệ: {pkg}"


def test_bloat_list_no_duplicate_packages():
    data = _load("bloat_jp.json")
    seen = {}
    for cat in data["categories"]:
        for pkg in cat["packages"]:
            if pkg["id"] in seen:
                raise AssertionError(
                    f"Package {pkg['id']} xuất hiện trong cả '{seen[pkg['id']]}' và '{cat['title']}'"
                )
            seen[pkg["id"]] = cat["title"]


def test_bloat_list_contains_facebook_bloat():
    data = _load("bloat_jp.json")
    all_ids = {p["id"] for c in data["categories"] for p in c["packages"]}
    assert "com.facebook.appmanager" in all_ids
    assert "com.facebook.services" in all_ids
    assert "com.facebook.system" in all_ids


def test_bloat_list_contains_sony_specific():
    data = _load("bloat_jp.json")
    all_ids = {p["id"] for c in data["categories"] for p in c["packages"]}
    # News Suite là bloat điển hình của Xperia JP
    assert "com.sony.nfx.app.sfrc" in all_ids


# ============ safe_list ↔ bloat_list không conflict ============


def test_safe_list_and_bloat_list_disjoint():
    """Một package không thể vừa critical (bảo vệ) vừa bloat (đề xuất tắt)."""
    safe = set(_load("safe_list.json")["critical"])
    bloat = _load("bloat_jp.json")
    bloat_ids = {p["id"] for c in bloat["categories"] for p in c["packages"]}
    conflicts = safe & bloat_ids
    assert conflicts == set(), f"Conflicts giữa safe_list và bloat: {conflicts}"


# ============ optimize_presets.json ============


def test_optimize_presets_valid():
    data = _load("optimize_presets.json")
    assert "presets" in data
    assert len(data["presets"]) > 10


def test_optimize_presets_structure():
    data = _load("optimize_presets.json")
    seen_ids = set()
    for p in data["presets"]:
        assert "id" in p
        assert p["id"] not in seen_ids, f"Trùng preset id: {p['id']}"
        seen_ids.add(p["id"])
        assert "title" in p
        assert "description" in p
        assert "category" in p
        assert "apply" in p
        assert "revert" in p
        assert isinstance(p["apply"], list) and len(p["apply"]) > 0
        assert isinstance(p["revert"], list) and len(p["revert"]) > 0


def test_optimize_presets_steps_well_formed():
    data = _load("optimize_presets.json")
    for p in data["presets"]:
        for step in p["apply"] + p["revert"]:
            assert isinstance(step, dict)
            # Mỗi step phải có hoặc shell hoặc (namespace+key+value)
            if "shell" in step:
                assert isinstance(step["shell"], str) and step["shell"]
            else:
                assert "namespace" in step
                assert "key" in step
                assert "value" in step
                assert step["namespace"] in {"global", "system", "secure"}


def test_optimize_presets_has_animation_off():
    data = _load("optimize_presets.json")
    ids = {p["id"] for p in data["presets"]}
    assert "animations_off" in ids, "Preset animations_off bắt buộc phải có"


def test_optimize_presets_categories_in_vietnamese():
    data = _load("optimize_presets.json")
    valid_cats = {"Tốc độ", "Hiệu năng", "Pin", "Hiển thị", "Riêng tư", "Âm thanh", "Khác"}
    for p in data["presets"]:
        assert p["category"] in valid_cats, f"Category lạ: {p['category']}"
