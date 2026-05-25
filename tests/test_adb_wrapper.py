"""Test ADB wrapper — chủ yếu logic parse, không gọi adb thật."""

import subprocess
from unittest.mock import MagicMock

import pytest

import adb_wrapper as adb


# ============ Parse helpers ============


def test_parse_pkg_line_simple():
    assert adb._parse_pkg_line("package:com.example.app") == "com.example.app"


def test_parse_pkg_line_with_path():
    line = "package:/system/app/Foo/Foo.apk=com.example.foo"
    assert adb._parse_pkg_line(line) == "com.example.foo"


def test_parse_pkg_line_empty():
    assert adb._parse_pkg_line("") is None
    assert adb._parse_pkg_line("   ") is None


def test_parse_pkg_line_non_package():
    assert adb._parse_pkg_line("some random text") is None


def test_parse_pkg_line_strips_whitespace():
    assert adb._parse_pkg_line("  package:com.test  ") == "com.test"


# ============ Bundled ADB detection ============


def test_bundled_adb_returns_none_in_test_env():
    # Trong dev env không có platform-tools/ trong sony-tool
    # Nếu test chạy sau khi user đã setup Windows thì có thể có — chấp nhận cả 2
    result = adb._bundled_adb()
    assert result is None or result.exists()


def test_adb_executable_raises_when_missing(monkeypatch):
    monkeypatch.setattr(adb.shutil, "which", lambda x: None)
    monkeypatch.setattr(adb, "_bundled_adb", lambda: None)
    with pytest.raises(adb.AdbError, match="Chưa cài ADB"):
        adb._adb_executable()


def test_adb_executable_prefers_path(monkeypatch):
    monkeypatch.setattr(adb.shutil, "which", lambda x: "/usr/local/bin/adb")
    monkeypatch.setattr(adb, "_bundled_adb", lambda: None)
    assert adb._adb_executable() == "/usr/local/bin/adb"


# ============ _run with mocked subprocess ============


def test_run_success(monkeypatch):
    monkeypatch.setattr(adb, "_adb_executable", lambda: "adb")
    mock_result = MagicMock(returncode=0, stdout="OK\n", stderr="")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: mock_result)
    assert adb._run(["devices"]) == "OK\n"


def test_run_failure_raises(monkeypatch):
    monkeypatch.setattr(adb, "_adb_executable", lambda: "adb")
    mock_result = MagicMock(returncode=1, stdout="", stderr="device offline\n")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: mock_result)
    with pytest.raises(adb.AdbError, match="device offline"):
        adb._run(["devices"])


def test_run_timeout_raises(monkeypatch):
    monkeypatch.setattr(adb, "_adb_executable", lambda: "adb")

    def raising_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="adb", timeout=30)

    monkeypatch.setattr(subprocess, "run", raising_run)
    with pytest.raises(adb.AdbError, match="quá lâu"):
        adb._run(["shell", "ls"])


# ============ list_devices parsing ============


def test_list_devices_empty(monkeypatch):
    monkeypatch.setattr(adb, "_run", lambda *a, **k: "List of devices attached\n\n")
    assert adb.list_devices() == []


def test_list_devices_one(monkeypatch):
    monkeypatch.setattr(
        adb, "_run", lambda *a, **k: "List of devices attached\nABC123\tdevice\n\n"
    )
    devs = adb.list_devices()
    assert len(devs) == 1
    assert devs[0].serial == "ABC123"
    assert devs[0].state == "device"


def test_list_devices_unauthorized(monkeypatch):
    monkeypatch.setattr(
        adb,
        "_run",
        lambda *a, **k: "List of devices attached\nABC123\tunauthorized\n\n",
    )
    devs = adb.list_devices()
    assert devs[0].state == "unauthorized"


def test_list_devices_multiple(monkeypatch):
    output = "List of devices attached\nABC\tdevice\nDEF\tdevice\nGHI\toffline\n\n"
    monkeypatch.setattr(adb, "_run", lambda *a, **k: output)
    devs = adb.list_devices()
    assert len(devs) == 3
    assert {d.serial for d in devs} == {"ABC", "DEF", "GHI"}


# ============ list_packages parsing ============


def test_list_packages_basic(monkeypatch):
    """Mô phỏng output của 3 lệnh pm list packages."""
    outputs = {
        ("shell", "pm", "list", "packages", "-f", "-u"): (
            "package:/system/app/A/A.apk=com.android.system_app\n"
            "package:/data/app/B/B.apk=com.example.userapp\n"
        ),
        ("shell", "pm", "list", "packages", "-s"): "package:com.android.system_app\n",
        ("shell", "pm", "list", "packages", "-d"): "",
    }

    def fake_run(args, timeout=30):
        key = tuple(args)
        return outputs.get(key, "")

    monkeypatch.setattr(adb, "_run", fake_run)
    pkgs = adb.list_packages()
    assert len(pkgs) == 2

    sys_pkg = next(p for p in pkgs if p.name == "com.android.system_app")
    assert sys_pkg.is_system is True
    assert sys_pkg.enabled is True
    assert sys_pkg.path == "/system/app/A/A.apk"

    user_pkg = next(p for p in pkgs if p.name == "com.example.userapp")
    assert user_pkg.is_system is False


def test_list_packages_with_disabled(monkeypatch):
    outputs = {
        ("shell", "pm", "list", "packages", "-f", "-u"): "package:/system/app/X=com.test.x\n",
        ("shell", "pm", "list", "packages", "-s"): "package:com.test.x\n",
        ("shell", "pm", "list", "packages", "-d"): "package:com.test.x\n",
    }

    def fake_run(args, timeout=30):
        return outputs.get(tuple(args), "")

    monkeypatch.setattr(adb, "_run", fake_run)
    pkgs = adb.list_packages()
    assert len(pkgs) == 1
    assert pkgs[0].enabled is False


def test_list_packages_sorted(monkeypatch):
    outputs = {
        ("shell", "pm", "list", "packages", "-f", "-u"): (
            "package:/x=com.zzz\npackage:/y=com.aaa\npackage:/z=com.mmm\n"
        ),
        ("shell", "pm", "list", "packages", "-s"): "",
        ("shell", "pm", "list", "packages", "-d"): "",
    }
    monkeypatch.setattr(adb, "_run", lambda args, timeout=30: outputs.get(tuple(args), ""))
    pkgs = adb.list_packages()
    names = [p.name for p in pkgs]
    assert names == sorted(names)
