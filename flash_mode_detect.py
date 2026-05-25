"""Detect khi máy Sony Xperia vào Flash Mode qua USB scan.

Sony Flash Mode dùng giao thức S1 độc quyền — ADB tắt 100% ở mode này.
Cách detect duy nhất: scan USB devices tìm Sony VID + Flash Mode PID.

VID Sony Mobile Communications: 0x0FCE
PIDs liên quan:
    0xB00B  — Flash Mode modern (2017+, gồm XQ-AS42)
    0xADDE  — Flash Mode legacy (Xperia Go era, dùng xflasher cũ)
    0x6135  — MTP (máy đang boot bình thường)
    0xA00B  — Alternate Flash Mode (1 vài model)

Module này graceful degrade nếu không có pyusb hoặc libusb backend:
trả về (available=False, message=...) để UI fallback sang manual confirm.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).parent

logger = logging.getLogger(__name__)

SONY_VID = 0x0FCE

# Sony Flash Mode product IDs cần detect (cho newflasher hoạt động)
FLASH_MODE_PIDS = {
    0xB00B: "Flash Mode (modern, 2017+)",
    0xADDE: "Flash Mode (legacy, pre-2017)",
    0xA00B: "Flash Mode (alternate)",
}

# Các PID mà máy KHÔNG ở Flash Mode (chỉ để annotate UI)
OTHER_SONY_PIDS = {
    0x6135: "MTP (normal boot)",
    0x518F: "Fastboot",
    0x51B0: "Fastboot",
    0x2138: "ADB",
}


@dataclass
class UsbDeviceInfo:
    vid: int
    pid: int
    description: str
    is_flash_mode: bool

    def to_dict(self) -> dict:
        return {
            "vid_hex": f"0x{self.vid:04X}",
            "pid_hex": f"0x{self.pid:04X}",
            "description": self.description,
            "is_flash_mode": self.is_flash_mode,
        }


@dataclass
class DetectResult:
    available: bool             # pyusb + libusb có sẵn không
    message: str                # lý do nếu không available
    sony_devices: list[UsbDeviceInfo]

    @property
    def flash_mode_device(self) -> UsbDeviceInfo | None:
        return next((d for d in self.sony_devices if d.is_flash_mode), None)

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "message": self.message,
            "sony_devices": [d.to_dict() for d in self.sony_devices],
            "in_flash_mode": self.flash_mode_device is not None,
            "flash_mode_pid_hex": (
                f"0x{self.flash_mode_device.pid:04X}" if self.flash_mode_device else None
            ),
        }


def _try_import_usb():
    try:
        import usb.core  # noqa: F401
        import usb.util  # noqa: F401
        return None  # OK
    except ImportError:
        return "pyusb chưa cài (pip install pyusb)"
    except Exception as e:
        return f"pyusb import lỗi: {e}"


def _find_libusb_dll() -> str | None:
    """Trả full path tới libusb-1.0.dll. Ưu tiên DLL từ pip package 'libusb',
    rồi tới PATH, rồi tới vendor/."""
    import os, sys
    # 1. PyPI `libusb` package có embed binary
    # Structure: libusb/_platform/{platform}/{arch}/libusb-1.0.dll
    # Platforms: windows | darwin | linux. Arch: x86_64 | x86 | arm64.
    try:
        import libusb as _libusb_pkg
        import platform as _platform
        pkg_dir = Path(_libusb_pkg.__file__).parent
        plat = sys.platform
        plat_dir = "windows" if plat.startswith("win") else "darwin" if plat == "darwin" else "linux"
        machine = _platform.machine().lower()
        if machine in ("amd64", "x86_64"):
            arch = "x86_64"
        elif machine in ("arm64", "aarch64"):
            arch = "arm64"
        elif machine in ("i386", "i686", "x86"):
            arch = "x86"
        else:
            arch = "x86_64"  # safe default
        ext = "dll" if plat.startswith("win") else "so" if plat_dir == "linux" else "dylib"
        candidate = pkg_dir / "_platform" / plat_dir / arch / f"libusb-1.0.{ext}"
        if candidate.exists():
            return str(candidate)
        # Fallback: walk + filter theo arch
        for p in pkg_dir.rglob(f"libusb-1.0.{ext}"):
            if arch in str(p).lower():
                return str(p)
        # Last-resort: any libusb-1.0.{ext}
        for p in pkg_dir.rglob(f"libusb-1.0.{ext}"):
            return str(p)
    except ImportError:
        pass

    # 2. vendor/ folder (user manual install)
    candidate = ROOT / "vendor" / "libusb-1.0.dll"
    if candidate.exists():
        return str(candidate)

    # 3. System PATH (cài system-wide)
    import shutil
    found = shutil.which("libusb-1.0.dll")
    if found:
        return found

    return None


def _try_find_backend():
    """Trên Windows, pyusb cần libusb-1.0.dll. Trả backend hoặc error message."""
    try:
        import usb.backend.libusb1 as libusb1
    except Exception as e:
        return None, f"libusb backend module lỗi: {e}"

    # Step 1: thử default discovery (Linux/Mac thường OK, Windows nếu DLL trong PATH)
    backend = libusb1.get_backend()
    if backend is not None:
        return backend, None

    # Step 2: Windows — explicit point tới DLL từ PyPI package
    dll = _find_libusb_dll()
    if not dll:
        return None, "libusb-1.0.dll không tìm thấy. Chạy `pip install libusb` hoặc copy DLL vào vendor/"

    backend = libusb1.get_backend(find_library=lambda x: dll)
    if backend is None:
        return None, f"libusb-1.0.dll tìm thấy ({dll}) nhưng pyusb load fail"
    return backend, None


def scan() -> DetectResult:
    """1-shot scan USB devices, return Sony devices + flag is_flash_mode."""
    err = _try_import_usb()
    if err:
        return DetectResult(available=False, message=err, sony_devices=[])

    backend, err = _try_find_backend()
    if err:
        return DetectResult(available=False, message=err, sony_devices=[])

    import usb.core
    try:
        devices = list(usb.core.find(find_all=True, idVendor=SONY_VID, backend=backend))
    except Exception as e:
        return DetectResult(available=False, message=f"USB enumerate lỗi: {e}", sony_devices=[])

    found = []
    for d in devices:
        pid = int(d.idProduct)
        is_fm = pid in FLASH_MODE_PIDS
        desc = FLASH_MODE_PIDS.get(pid) or OTHER_SONY_PIDS.get(pid) or "Sony device (unknown PID)"
        found.append(UsbDeviceInfo(vid=SONY_VID, pid=pid, description=desc, is_flash_mode=is_fm))

    return DetectResult(available=True, message="OK", sony_devices=found)


def wait_for_flash_mode(
    timeout_seconds: float = 120,
    poll_interval: float = 0.5,
    progress_callback: Callable[[DetectResult], None] | None = None,
) -> UsbDeviceInfo:
    """Block poll cho tới khi phát hiện máy ở Flash Mode hoặc timeout.

    Args:
        timeout_seconds: max wait
        poll_interval: thời gian giữa 2 lần scan (default 500ms)
        progress_callback: gọi mỗi lần scan với DetectResult — UI có thể cập nhật state

    Returns:
        UsbDeviceInfo của Flash Mode device

    Raises:
        TimeoutError: nếu hết timeout chưa thấy
        RuntimeError: nếu pyusb/libusb không available
    """
    deadline = time.time() + timeout_seconds
    last_state: tuple | None = None
    while time.time() < deadline:
        result = scan()
        if not result.available:
            raise RuntimeError(result.message)

        if progress_callback:
            # Chỉ callback khi state thay đổi để tránh spam
            current_state = tuple((d.pid, d.is_flash_mode) for d in result.sony_devices)
            if current_state != last_state:
                last_state = current_state
                progress_callback(result)

        fm = result.flash_mode_device
        if fm:
            logger.info("Detected Flash Mode: PID 0x%04X (%s)", fm.pid, fm.description)
            return fm

        time.sleep(poll_interval)

    raise TimeoutError(f"Không phát hiện Flash Mode sau {timeout_seconds:.0f}s")
