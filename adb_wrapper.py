"""ADB wrapper — gọi adb qua subprocess, parse output."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class AdbError(Exception):
    pass


def _bundled_adb() -> Path | None:
    """Trả về path đến adb bundled (Windows setup script tải về platform-tools/)."""
    name = "adb.exe" if os.name == "nt" else "adb"
    p = Path(__file__).parent / "platform-tools" / name
    return p if p.exists() else None


def _adb_executable() -> str:
    """Tìm adb: PATH trước, sau đó folder platform-tools bundled."""
    found = shutil.which("adb")
    if found:
        return found
    bundled = _bundled_adb()
    if bundled:
        return str(bundled)
    raise AdbError(
        "Chưa cài ADB. Chạy setup_adb.sh (Mac/Linux) hoặc setup_adb.ps1 (Windows) trước."
    )


@dataclass
class Device:
    serial: str
    state: str  # "device" | "unauthorized" | "offline"


@dataclass
class PackageInfo:
    name: str
    path: str | None
    is_system: bool
    enabled: bool


def adb_available() -> bool:
    return shutil.which("adb") is not None or _bundled_adb() is not None


_CREATE_NO_WINDOW = 0x08000000  # Windows: ẩn cmd console khi gọi adb


def _run(args: list[str], timeout: int = 30) -> str:
    exe = _adb_executable()  # raise AdbError nếu không có
    kwargs: dict = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout,
    }
    if os.name == "nt":
        kwargs["creationflags"] = _CREATE_NO_WINDOW
    try:
        result = subprocess.run([exe, *args], **kwargs)
    except subprocess.TimeoutExpired as e:
        raise AdbError(f"Lệnh ADB chạy quá lâu: {' '.join(args)}") from e
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise AdbError(err or f"adb {' '.join(args)} thất bại")
    return result.stdout or ""


def list_devices() -> list[Device]:
    out = _run(["devices"])
    devices: list[Device] = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            devices.append(Device(serial=parts[0], state=parts[1]))
    return devices


def device_info(serial: str | None = None) -> dict:
    def getprop(key: str) -> str:
        args = []
        if serial:
            args += ["-s", serial]
        args += ["shell", "getprop", key]
        try:
            return _run(args, timeout=10).strip()
        except AdbError:
            return ""

    return {
        "model": getprop("ro.product.model"),
        "manufacturer": getprop("ro.product.manufacturer"),
        "android_version": getprop("ro.build.version.release"),
        "sdk": getprop("ro.build.version.sdk"),
        "build": getprop("ro.build.display.id"),
        "device": getprop("ro.product.device"),
    }


def list_packages(serial: str | None = None) -> list[PackageInfo]:
    """Trả danh sách toàn bộ package, kèm path và trạng thái enabled."""
    base = ["-s", serial] if serial else []

    # -f để lấy path APK, -u để bao gồm cả package đã uninstall cho user 0
    out_all = _run(base + ["shell", "pm", "list", "packages", "-f", "-u"])
    out_system = _run(base + ["shell", "pm", "list", "packages", "-s"])
    out_disabled = _run(base + ["shell", "pm", "list", "packages", "-d"])

    system_set = {_parse_pkg_line(line) for line in out_system.splitlines()}
    disabled_set = {_parse_pkg_line(line) for line in out_disabled.splitlines()}
    system_set.discard(None)
    disabled_set.discard(None)

    packages: list[PackageInfo] = []
    seen: set[str] = set()
    for line in out_all.splitlines():
        line = line.strip()
        if not line.startswith("package:"):
            continue
        rest = line[len("package:") :]
        # format: <path>=<package_name>
        if "=" in rest:
            path, name = rest.rsplit("=", 1)
        else:
            path, name = "", rest
        name = name.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        packages.append(
            PackageInfo(
                name=name,
                path=path or None,
                is_system=name in system_set,
                enabled=name not in disabled_set,
            )
        )
    packages.sort(key=lambda p: p.name)
    return packages


def _parse_pkg_line(line: str) -> str | None:
    line = line.strip()
    if not line.startswith("package:"):
        return None
    rest = line[len("package:") :]
    if "=" in rest:
        return rest.rsplit("=", 1)[-1].strip()
    return rest.strip()


def _pm_cmd(action: str, package: str, serial: str | None = None) -> str:
    base = ["-s", serial] if serial else []
    args = base + ["shell", "pm", action, "--user", "0", package]
    return _run(args, timeout=20).strip()


def disable_package(package: str, serial: str | None = None) -> str:
    return _pm_cmd("disable-user", package, serial)


def enable_package(package: str, serial: str | None = None) -> str:
    return _pm_cmd("enable", package, serial)


def uninstall_user(package: str, serial: str | None = None) -> str:
    """Gỡ cho user 0 — vẫn có thể khôi phục bằng `pm install-existing`."""
    return _pm_cmd("uninstall", package, serial)


def reinstall_existing(package: str, serial: str | None = None) -> str:
    base = ["-s", serial] if serial else []
    args = base + ["shell", "cmd", "package", "install-existing", package]
    return _run(args, timeout=20).strip()


def shell(command: str, serial: str | None = None, timeout: int = 20) -> str:
    base = ["-s", serial] if serial else []
    return _run(base + ["shell", command], timeout=timeout)


def settings_get(namespace: str, key: str, serial: str | None = None) -> str:
    return shell(f"settings get {namespace} {key}", serial=serial).strip()


def settings_put(namespace: str, key: str, value: str, serial: str | None = None) -> str:
    return shell(f"settings put {namespace} {key} {value}", serial=serial).strip()
