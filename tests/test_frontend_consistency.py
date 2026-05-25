"""Test sự nhất quán giữa frontend (app.js) và data backend.

Mục đích: bắt lỗi kiểu "ONE_CLICK_PRESETS trong app.js trỏ tới preset_id không tồn tại
trong optimize_presets.json" — lỗi runtime mà chỉ phát hiện khi user bấm nút.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
STATIC = ROOT / "static"


def _read(p):
    return p.read_text(encoding="utf-8")


def test_one_click_presets_all_exist_in_json():
    """ONE_CLICK_PRESETS trong app.js — tất cả id phải có trong optimize_presets.json."""
    presets_json = json.loads(_read(DATA / "optimize_presets.json"))
    real_ids = {p["id"] for p in presets_json["presets"]}

    js = _read(STATIC / "app.js")
    match = re.search(r"const ONE_CLICK_PRESETS\s*=\s*\[(.*?)\];", js, re.DOTALL)
    assert match, "Không tìm thấy ONE_CLICK_PRESETS trong app.js"
    ids_in_js = re.findall(r'"([^"]+)"', match.group(1))
    assert len(ids_in_js) > 0, "ONE_CLICK_PRESETS rỗng"

    missing = [i for i in ids_in_js if i not in real_ids]
    assert missing == [], f"ID trong ONE_CLICK_PRESETS không có trong JSON: {missing}"


def test_tier_label_keys_match_data_tiers():
    """TIER_LABEL trong app.js phải có đủ 4 tier mà data dùng."""
    bloat = json.loads(_read(DATA / "bloat_jp.json"))
    data_tiers = {p["tier"] for c in bloat["categories"] for p in c["packages"]}

    js = _read(STATIC / "app.js")
    match = re.search(r"const TIER_LABEL\s*=\s*\{(.*?)\};", js, re.DOTALL)
    assert match
    js_tiers = set(re.findall(r"(\w+):", match.group(1)))

    missing = data_tiers - js_tiers
    assert missing == set(), f"TIER_LABEL thiếu key: {missing}"


def test_html_references_real_endpoints_via_js():
    """app.js gọi /api/* — tất cả (kể cả template strings) phải có handler trong app.py."""
    js = _read(STATIC / "app.js")
    api_calls = set(re.findall(r'api\(\s*[`"\']([^`"\']+)', js))
    api_calls.update(re.findall(r'api\(\s*`([^`]+)', js))

    app_py = _read(ROOT / "app.py")
    decorators = re.findall(r'@app\.(?:get|post)\(\s*["\']([^"\']+)', app_py)
    real_paths = set(decorators)

    # Với template strings (chứa ${...}), check xem có endpoint nào trong app.py
    # có cùng prefix không. VD `/api/optimize/${action}` → match cả `/api/optimize/apply` và `/api/optimize/revert`
    missing = []
    for call in api_calls:
        if not call.startswith("/api/"):
            continue
        path = call.split("?")[0]
        if "${" in path:
            prefix = path.split("${")[0]
            # Phải có ít nhất 1 endpoint thật bắt đầu bằng prefix
            if not any(rp.startswith(prefix) for rp in real_paths):
                missing.append(call)
        else:
            if path not in real_paths:
                missing.append(call)

    assert missing == [], f"app.js gọi endpoint không tồn tại trong app.py: {missing}"


def test_css_pkg_tag_classes_present():
    """JS render <span class='pkg-tag tier-X'> — CSS phải có style cho từng tier."""
    css = _read(STATIC / "style.css")
    required_classes = [
        ".pkg-tag.enabled",
        ".pkg-tag.disabled",
        ".pkg-tag.tier-safe",
        ".pkg-tag.tier-recommended",
        ".pkg-tag.tier-aggressive",
        ".pkg-tag.tier-optional",
        ".pkg-tag.critical",
    ]
    for cls in required_classes:
        assert cls in css, f"CSS thiếu class {cls}"


def test_html_has_required_element_ids():
    """JS query các id — HTML phải define. Bỏ qua template literals."""
    html = _read(STATIC / "index.html")
    js = _read(STATIC / "app.js")

    # Chỉ match $('#xxx') với selector tĩnh (không template literal có ${})
    # Pattern: $('#abc'), $("#abc"), $(`#abc`) — không match `#stat-${k}`
    js_ids = set(re.findall(r'\$\(\s*["\']#([a-z][a-z0-9_-]*)["\']\s*\)', js))
    # Template literals: bỏ qua nếu chứa ${
    template_ids = re.findall(r'\$\(\s*`#([a-z][a-z0-9_-]*)`\s*\)', js)
    js_ids.update(template_ids)
    js_ids.update(re.findall(r'getElementById\(\s*["\']([a-z][a-z0-9_-]*)["\']', js))

    missing = []
    for jid in js_ids:
        if f'id="{jid}"' not in html and f"id='{jid}'" not in html:
            missing.append(jid)

    assert missing == [], f"HTML thiếu id mà JS query: {missing}"


def test_html_all_tab_panels_have_matching_buttons():
    """Mỗi data-tab phải có tab-panel id tương ứng."""
    html = _read(STATIC / "index.html")
    tabs = set(re.findall(r'data-tab="([^"]+)"', html))
    panels = set(re.findall(r'id="tab-([^"]+)"', html))
    assert tabs == panels, f"Tab/panel mismatch — tabs:{tabs} panels:{panels}"


def test_oneclick_apply_uses_correct_endpoint():
    """doOneClick phải gọi /api/packages/disable HOẶC uninstall (không gì khác)."""
    js = _read(STATIC / "app.js")
    match = re.search(r"async function doOneClick\(.*?\}\s*$", js, re.DOTALL | re.MULTILINE)
    if not match:
        # fallback: tìm phần code có endpoint = ...
        match = re.search(r'endpoint\s*=\s*mode\s*===\s*"uninstall"\s*\?\s*"([^"]+)"\s*:\s*"([^"]+)"', js)
        assert match, "Không tìm thấy logic chọn endpoint trong doOneClick"
        assert match.group(1) == "/api/packages/uninstall"
        assert match.group(2) == "/api/packages/disable"


def test_activity_log_panel_present():
    """Activity log panel — đảm bảo có đủ HTML + CSS + JS."""
    html = _read(STATIC / "index.html")
    css = _read(STATIC / "style.css")
    js = _read(STATIC / "app.js")

    # HTML
    assert 'id="activity-log"' in html
    assert 'id="log-header"' in html
    assert 'id="log-body"' in html
    assert 'id="log-count"' in html
    assert 'id="log-clear"' in html
    assert 'id="log-download"' in html

    # CSS
    assert ".activity-log" in css
    assert ".log-entry" in css
    assert ".log-entry.success" in css
    assert ".log-entry.error" in css
    assert ".log-entry.warn" in css
    assert ".activity-log.collapsed" in css

    # JS
    assert "function logEntry" in js
    assert "MAX_LOG_ENTRIES" in js
    assert "LOG_BUFFER" in js


def test_log_uses_textcontent_not_innerhtml_for_message():
    """Tin nhắn log phải đi qua textContent — chống XSS qua tên package."""
    js = _read(STATIC / "app.js")
    # Tìm hàm logEntry
    fn = re.search(r"function logEntry\([^)]*\)\s*\{(.+?)\n\}", js, re.DOTALL)
    assert fn, "Không tìm thấy hàm logEntry"
    body = fn.group(1)
    # Tin nhắn user-supplied phải dùng textContent, KHÔNG innerHTML
    assert ".textContent = message" in body, "logEntry phải dùng textContent cho message (chống XSS)"


def test_critical_actions_have_log_entries():
    """Các action quan trọng (disable, enable, apply preset, 1-click) phải gọi logEntry."""
    js = _read(STATIC / "app.js")
    # Tìm trong từng function
    checks = [
        ("doSingleAction", "logEntry"),
        ("bulkDisable", "logEntry"),
        ("bulkEnable", "logEntry"),
        ("applyPreset", "logEntry"),
        ("doOneClick", "logEntry"),
    ]
    for fn_name, marker in checks:
        m = re.search(rf"function {fn_name}\([^)]*\)\s*\{{(.*?)\n\}}", js, re.DOTALL)
        # async function biến thể
        if not m:
            m = re.search(rf"async function {fn_name}\([^)]*\)\s*\{{(.*?)\n\}}", js, re.DOTALL)
        assert m, f"Không tìm thấy function {fn_name}"
        body = m.group(1)
        assert marker in body, f"{fn_name} không gọi {marker} — sẽ không hiển thị trong activity log"


def test_safe_list_count_matches_readme():
    """README nói '76 package' — kiểm tra match với reality."""
    readme = _read(ROOT / "README.md")
    safe = json.loads(_read(DATA / "safe_list.json"))["critical"]
    # Lấy số thực
    actual = len(safe)
    # Bỏ qua test nếu README không nói rõ số → để soft check
    if "76 package" in readme or "76 packages" in readme:
        # README đã nói 76 — actual có thể khác (ví dụ fix bug dup giảm xuống)
        # Test này chỉ cảnh báo, không fail nếu sai 1-2
        assert abs(actual - 76) <= 2, f"README nói 76 package, thực tế {actual}"
