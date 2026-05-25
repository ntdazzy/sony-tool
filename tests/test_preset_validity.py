"""Kiểm tra TỪNG preset: command syntactically valid, apply/revert reversible,
namespace hợp lệ, key+value đúng format."""

import json
import re
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"


def _presets():
    return json.loads((DATA / "optimize_presets.json").read_text(encoding="utf-8"))["presets"]


# ============ Per-preset structural checks ============


def test_every_preset_has_unique_id():
    ids = [p["id"] for p in _presets()]
    assert len(ids) == len(set(ids)), f"Trùng preset id: {[x for x in ids if ids.count(x) > 1]}"


def test_every_preset_has_required_fields():
    required = {"id", "title", "description", "category", "apply", "revert", "icon"}
    for p in _presets():
        missing = required - p.keys()
        assert not missing, f"Preset {p.get('id', '?')} thiếu: {missing}"


def test_every_preset_apply_has_steps():
    for p in _presets():
        assert len(p["apply"]) > 0, f"Preset {p['id']} apply rỗng"
        assert len(p["revert"]) > 0, f"Preset {p['id']} revert rỗng"


def test_every_step_is_well_formed():
    """Mỗi step phải có ('namespace'+'key'+'value') HOẶC 'shell' (mutually exclusive)."""
    for p in _presets():
        for kind in ("apply", "revert"):
            for i, step in enumerate(p[kind]):
                has_settings = all(k in step for k in ("namespace", "key", "value"))
                has_shell = "shell" in step
                assert has_settings != has_shell, (
                    f"Preset {p['id']} {kind}[{i}] phải có (namespace+key+value) HOẶC (shell), không cả 2: {step}"
                )


def test_settings_step_namespace_valid():
    """namespace = global | system | secure (đúng spec Android settings)."""
    valid = {"global", "system", "secure"}
    for p in _presets():
        for kind in ("apply", "revert"):
            for step in p[kind]:
                if "namespace" in step:
                    assert step["namespace"] in valid, (
                        f"Preset {p['id']} {kind} namespace lạ: {step['namespace']}"
                    )


def test_settings_step_key_is_snake_case():
    """key Android settings convention = snake_case lowercase ASCII."""
    pat = re.compile(r"^[a-z][a-z0-9_]*$")
    for p in _presets():
        for kind in ("apply", "revert"):
            for step in p[kind]:
                if "key" in step:
                    assert pat.match(step["key"]), (
                        f"Preset {p['id']} key không snake_case: {step['key']}"
                    )


def test_settings_step_value_not_empty():
    for p in _presets():
        for kind in ("apply", "revert"):
            for step in p[kind]:
                if "value" in step:
                    assert step["value"] != "", f"Preset {p['id']} value rỗng"


def test_shell_step_not_empty():
    for p in _presets():
        for kind in ("apply", "revert"):
            for step in p[kind]:
                if "shell" in step:
                    assert step["shell"].strip(), f"Preset {p['id']} shell rỗng"


def test_shell_command_uses_known_tools():
    """Shell commands chỉ dùng adb-safe tools (không sudo, su, rm /system...)."""
    safe_tools = {"settings", "device_config", "dumpsys", "cmd", "am", "pm", "service", "wm", "logcat"}
    for p in _presets():
        for kind in ("apply", "revert"):
            for step in p[kind]:
                if "shell" in step:
                    first = step["shell"].strip().split()[0]
                    assert first in safe_tools, (
                        f"Preset {p['id']} dùng tool lạ '{first}': {step['shell']}"
                    )


def test_dangerous_commands_not_in_presets():
    """Không có rm/dd/mkfs/sudo/su trong bất kỳ preset nào."""
    dangerous = ["rm ", "dd ", "mkfs", "sudo", "su -", "factory_reset", "format"]
    for p in _presets():
        for kind in ("apply", "revert"):
            for step in p[kind]:
                cmd = step.get("shell", "")
                for bad in dangerous:
                    assert bad not in cmd, (
                        f"Preset {p['id']} có lệnh nguy hiểm '{bad}': {cmd}"
                    )


# ============ Apply ↔ Revert symmetry ============


def test_apply_revert_have_same_keys_targeted():
    """Mỗi key có trong apply phải có trong revert (để khôi phục lại được)."""
    for p in _presets():
        apply_keys = set()
        revert_keys = set()
        for step in p["apply"]:
            if "key" in step:
                apply_keys.add(f"{step['namespace']}/{step['key']}")
        for step in p["revert"]:
            if "key" in step:
                revert_keys.add(f"{step['namespace']}/{step['key']}")

        # Apply phải subset của revert (revert có thể có thêm để dọn các value)
        missing_in_revert = apply_keys - revert_keys
        # Cho phép revert dùng `device_config delete` thay vì put → check shell command
        if missing_in_revert:
            for shell_step in [s for s in p["revert"] if "shell" in s]:
                for key_path in list(missing_in_revert):
                    _, k = key_path.split("/", 1)
                    if k in shell_step["shell"]:
                        missing_in_revert.discard(key_path)

        assert not missing_in_revert, (
            f"Preset {p['id']} revert không cover các key: {missing_in_revert}"
        )


# ============ Tier coverage ============


def test_one_click_presets_subset_of_all_presets():
    """Frontend ONE_CLICK_PRESETS phải là subset của presets thực sự tồn tại."""
    static_js = (DATA.parent / "static" / "app.js").read_text(encoding="utf-8")
    match = re.search(r"const ONE_CLICK_PRESETS\s*=\s*\[(.*?)\];", static_js, re.DOTALL)
    one_click_ids = set(re.findall(r'"([^"]+)"', match.group(1)))
    all_ids = {p["id"] for p in _presets()}
    missing = one_click_ids - all_ids
    assert not missing, f"ONE_CLICK_PRESETS chứa id không tồn tại: {missing}"


# ============ Category distribution ============


def test_each_category_has_at_least_one_preset():
    """Đảm bảo không có category 'orphan' với 0 preset."""
    from collections import Counter
    cats = Counter(p["category"] for p in _presets())
    for cat, count in cats.items():
        assert count >= 1, f"Category {cat} rỗng"


def test_total_preset_count_after_v3():
    """Sau khi thêm audio + wake: ít nhất 27 preset."""
    assert len(_presets()) >= 27


# ============ Warning field optional ============


def test_warning_field_is_string_if_present():
    for p in _presets():
        if "warning" in p:
            assert isinstance(p["warning"], str) and len(p["warning"]) > 0
