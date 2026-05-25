"""Test cross-platform compatibility — chạy được trên cả Mac/Linux và Windows.

Mục đích: phát hiện sớm các giả định Unix-only (path separator, encoding, subprocess flags).
"""

import os
import re
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parent.parent


def _read(p):
    return p.read_text(encoding="utf-8")


# ============ Path handling ============


def test_app_uses_pathlib_not_string_paths():
    """app.py không hardcode separator như '/static' hay '\\\\backups'."""
    src = _read(ROOT / "app.py")
    # Không có pattern như "data/safe_list.json" trực tiếp (phải qua Path)
    bad_patterns = [
        r'open\([\'"][./\\]',  # open("/x") hoặc open("./x")
        r"Path\([\'\"]\\\\",  # Path("C:\...") absolute Windows hardcoded
    ]
    for pat in bad_patterns:
        matches = re.findall(pat, src)
        assert not matches, f"Path không an toàn: {matches}"


def test_adb_wrapper_uses_path_for_bundled():
    """_bundled_adb dùng Path() chứ không nối string."""
    src = _read(ROOT / "adb_wrapper.py")
    assert "Path(__file__).parent" in src
    assert 'os.name == "nt"' in src, "Phải có check Windows để dùng adb.exe"


# ============ Encoding ============


def test_subprocess_uses_utf8_encoding():
    """_run trong adb_wrapper.py specify encoding=utf-8 (tránh cp1252 trên Windows)."""
    src = _read(ROOT / "adb_wrapper.py")
    assert 'encoding": "utf-8"' in src or "encoding='utf-8'" in src, (
        "subprocess.run phải set encoding utf-8 để Windows không bị mojibake"
    )


def test_subprocess_hides_window_on_windows():
    """Windows: phải set CREATE_NO_WINDOW để không pop cmd console."""
    src = _read(ROOT / "adb_wrapper.py")
    assert "CREATE_NO_WINDOW" in src or "0x08000000" in src, (
        "Cần CREATE_NO_WINDOW flag để Windows không hiện console mỗi adb call"
    )


def test_json_files_read_with_utf8():
    """Tất cả load JSON phải specify encoding=utf-8 (Windows mặc định cp1252)."""
    for src_file in [ROOT / "app.py", ROOT / "adb_wrapper.py"]:
        src = _read(src_file)
        # Tìm pattern .read_text() không có encoding
        bad = re.findall(r"\.read_text\(\s*\)", src)
        assert not bad, f"{src_file.name}: .read_text() phải có encoding='utf-8'"


# ============ Windows scripts exist ============


def test_windows_scripts_exist():
    assert (ROOT / "setup_adb.ps1").exists(), "setup_adb.ps1 thiếu"
    assert (ROOT / "run.ps1").exists(), "run.ps1 thiếu"


def test_setup_adb_ps1_downloads_platform_tools():
    """Verify setup_adb.ps1 đúng URL Google + giải nén ra platform-tools/."""
    src = _read(ROOT / "setup_adb.ps1")
    assert "platform-tools-latest-windows.zip" in src
    assert "dl.google.com" in src
    assert "Expand-Archive" in src


def test_run_ps1_adds_platform_tools_to_path():
    src = _read(ROOT / "run.ps1")
    assert "platform-tools" in src
    assert "$env:PATH" in src or '$env:Path' in src


def test_run_ps1_uses_windows_venv_path():
    """Venv path Windows là .venv\\Scripts\\... (không phải bin/)."""
    src = _read(ROOT / "run.ps1")
    assert r".venv\Scripts" in src or '.venv/Scripts' in src


def test_setup_uses_python_m_pip_not_pip_exe():
    """Trên Windows, pip.exe bị lock khi tự chạy → self-upgrade fail.
    Phải dùng `python.exe -m pip` để tránh ERROR misleading khi setup."""
    src = _read(ROOT / "setup_adb.ps1")
    assert "python.exe" in src and "-m pip" in src, (
        "setup_adb.ps1 phải gọi pip qua `python.exe -m pip` (không phải pip.exe trực tiếp)"
    )
    # Đảm bảo có --disable-pip-version-check để bớt noise
    assert "--disable-pip-version-check" in src


def test_ps1_files_are_ascii_only():
    """PowerShell 5.1 (Win10/11 default) đọc .ps1 không-BOM sai khi có Unicode →
    'string is missing the terminator' error. Bắt buộc ASCII thuần."""
    for fname in ["setup_adb.ps1", "run.ps1"]:
        path = ROOT / fname
        raw = path.read_bytes()
        non_ascii_bytes = [(i, b) for i, b in enumerate(raw) if b > 0x7F]
        if non_ascii_bytes:
            preview = non_ascii_bytes[:5]
            raise AssertionError(
                f"{fname} chứa byte non-ASCII tại offset {preview} — "
                f"PowerShell 5.1 sẽ parse sai. Đổi sang ASCII (vd. ✅ → [OK], 'Cài đặt' → 'Settings')."
            )


# ============ BAT script ============


def test_export_bat_uses_utf8_codepage():
    """export_packages.bat phải set chcp 65001 để xuất Vietnamese đúng."""
    src = _read(ROOT / "scripts" / "export_packages.bat")
    assert "chcp 65001" in src


def test_export_bat_locale_safe_date():
    """Không dùng `date /t` (locale-dependent) — phải dùng PowerShell."""
    src = _read(ROOT / "scripts" / "export_packages.bat")
    # date /t output format thay đổi theo locale: 05/25/2026 vs 25/05/2026 vs 2026/05/25
    # PowerShell Get-Date là deterministic
    assert "powershell" in src.lower() and "Get-Date" in src
    assert "for /f" in src and "date /t" not in src.lower()


# ============ Functional ============


def test_pathlib_works_with_data_files():
    """Data files đọc được qua Path API."""
    import json
    for fname in ["safe_list.json", "bloat_jp.json", "optimize_presets.json"]:
        f = ROOT / "data" / fname
        assert f.exists()
        # Phải parse được với encoding utf-8 explicit
        data = json.loads(f.read_text(encoding="utf-8"))
        assert isinstance(data, dict)


def test_os_name_check_is_correct():
    """os.name == 'nt' đúng trên Windows, 'posix' trên Mac/Linux."""
    assert os.name in {"nt", "posix"}


# ============ subprocess mock for Windows path ============


def test_run_passes_creationflags_only_on_windows(monkeypatch):
    """Khi os.name='nt', _run phải pass creationflags. Khi posix thì không."""
    import adb_wrapper as adb

    captured_kwargs = {}

    def fake_run(*args, **kwargs):
        captured_kwargs.update(kwargs)
        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""
        return Result()

    monkeypatch.setattr(adb, "_adb_executable", lambda: "adb")
    monkeypatch.setattr(adb.subprocess, "run", fake_run)

    # Simulate Windows
    monkeypatch.setattr(adb.os, "name", "nt")
    adb._run(["devices"])
    assert "creationflags" in captured_kwargs, "Windows phải pass creationflags"

    # Simulate POSIX
    captured_kwargs.clear()
    monkeypatch.setattr(adb.os, "name", "posix")
    adb._run(["devices"])
    assert "creationflags" not in captured_kwargs, "POSIX không pass creationflags"


def test_run_always_passes_utf8_encoding(monkeypatch):
    """encoding='utf-8' phải có trên mọi platform."""
    import adb_wrapper as adb
    captured_kwargs = {}
    def fake_run(*args, **kwargs):
        captured_kwargs.update(kwargs)
        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""
        return Result()
    monkeypatch.setattr(adb, "_adb_executable", lambda: "adb")
    monkeypatch.setattr(adb.subprocess, "run", fake_run)
    adb._run(["devices"])
    assert captured_kwargs.get("encoding") == "utf-8"
