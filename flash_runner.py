"""Wrap newflasher.exe subprocess + stream output → SSE progress.

Newflasher CLI:
- Đặt newflasher.exe vào folder chứa .sin files
- Chạy không args → tool scan folder + flash tất cả .sin theo thứ tự
- Stdout: progress text + "Flashing X..." per partition

Module này:
- Spawn subprocess, capture stdout line-by-line
- Parse output để tìm partition đang flash + estimate progress
- Push events vào queue cho SSE
- Hỗ trợ cancel (terminate process)
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent
VENDOR_DIR = ROOT / "vendor"
# Windows dùng newflasher.exe, Mac/Linux dùng newflasher (không extension).
NEWFLASHER_EXE = VENDOR_DIR / ("newflasher.exe" if os.name == "nt" else "newflasher")

# Pattern detect output từ newflasher (đoán theo XDA discussion + source code)
_RE_FLASHING = re.compile(r"(?:flashing|writing|sending)\s+(.+?)(?:\.\.\.|\s*$)", re.IGNORECASE)
_RE_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_RE_ERROR = re.compile(r"(error|failed|fatal|cannot|abort)", re.IGNORECASE)
_RE_DONE = re.compile(r"(done|finished|complete|success|all done)", re.IGNORECASE)

# Bytes per partition để estimate (rough)
_PARTITION_WEIGHTS = {
    "boot": 1, "vendor_boot": 1, "dtbo": 1, "vbmeta": 1,
    "system": 5, "vendor": 3, "product": 3,
    "userdata": 2, "cache": 1, "persist": 1,
    "modem": 2, "recovery": 1, "oem": 1, "elabel": 1,
}


@dataclass
class FlashProgress:
    job_id: str
    state: str                  # "starting" | "flashing" | "done" | "error" | "cancelled"
    current_partition: str = ""
    log_lines: list[str] = field(default_factory=list)
    partitions_done: int = 0
    partitions_total: int = 0
    elapsed_seconds: float = 0
    error: str | None = None
    exit_code: int | None = None

    def snapshot(self) -> dict:
        # Truncate log buffer to last 50 lines for SSE (frontend keep full history)
        return {
            "job_id": self.job_id,
            "state": self.state,
            "current_partition": self.current_partition,
            "log_tail": self.log_lines[-3:],   # last 3 mới nhất, frontend append
            "partitions_done": self.partitions_done,
            "partitions_total": self.partitions_total,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "error": self.error,
            "exit_code": self.exit_code,
        }


class FlashError(RuntimeError):
    pass


def newflasher_available() -> bool:
    """Check xem newflasher.exe có trong vendor/ không."""
    return NEWFLASHER_EXE.exists()


def newflasher_path() -> Path | None:
    if NEWFLASHER_EXE.exists():
        return NEWFLASHER_EXE
    # Fallback: PATH
    found = shutil.which("newflasher" if os.name != "nt" else "newflasher.exe")
    return Path(found) if found else None


def _count_partitions(rom_dir: Path) -> int:
    """Đếm số .sin / .ext4 / .img files để estimate total."""
    if not rom_dir.exists():
        return 0
    extensions = {".sin", ".ext4", ".img", ".zip"}
    return sum(1 for p in rom_dir.iterdir() if p.is_file() and p.suffix.lower() in extensions)


def _parse_output_line(line: str, progress: FlashProgress) -> bool:
    """Parse 1 dòng stdout của newflasher, update progress. Trả True nếu match pattern."""
    line_stripped = line.strip()
    if not line_stripped:
        return False
    progress.log_lines.append(line_stripped)

    if _RE_ERROR.search(line_stripped):
        # Đôi khi "error" xuất hiện trong context không lỗi (vd "0 errors"). Heuristic:
        # chỉ flag nếu line có pattern lỗi cụ thể.
        if re.search(r"error\s*:\s*[a-z]", line_stripped, re.IGNORECASE) or \
           re.search(r"(failed|fatal|abort)", line_stripped, re.IGNORECASE):
            progress.error = line_stripped
            return True

    m = _RE_FLASHING.search(line_stripped)
    if m:
        partition = m.group(1).strip().split()[0]
        if partition and partition != progress.current_partition:
            progress.current_partition = partition
            progress.partitions_done += 1
            logger.info("Flashing: %s (%d/%d)", partition, progress.partitions_done, progress.partitions_total)
        return True

    if _RE_DONE.search(line_stripped) and "ll done" in line_stripped.lower() or line_stripped.lower().strip() in ("done.", "done", "finished"):
        # "All done" thường là final
        return True

    return False


@dataclass
class FlashJob:
    job_id: str
    rom_dir: Path
    progress_queue: Queue
    cancel_event: threading.Event
    thread: threading.Thread
    started_at: float
    process: subprocess.Popen | None = None


_JOBS: dict[str, FlashJob] = {}
_JOBS_LOCK = threading.Lock()


_CREATE_NO_WINDOW = 0x08000000


def _run_newflasher(job: FlashJob) -> None:
    """Worker thread: spawn newflasher, read stdout, push progress."""
    exe = newflasher_path()
    progress = FlashProgress(
        job_id=job.job_id,
        state="starting",
        partitions_total=_count_partitions(job.rom_dir),
    )
    job.progress_queue.put(progress.snapshot())

    if exe is None:
        progress.state = "error"
        progress.error = f"newflasher.exe không tồn tại tại {NEWFLASHER_EXE}. Tải từ https://github.com/munjeni/newflasher rồi đặt vào vendor/"
        job.progress_queue.put(progress.snapshot())
        return

    if not job.rom_dir.exists() or not job.rom_dir.is_dir():
        progress.state = "error"
        progress.error = f"ROM folder không tồn tại: {job.rom_dir}"
        job.progress_queue.put(progress.snapshot())
        return

    # Newflasher đọc current working dir → cwd=rom_dir
    kwargs: dict = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "cwd": str(job.rom_dir),
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "bufsize": 1,  # line-buffered
    }
    if os.name == "nt":
        kwargs["creationflags"] = _CREATE_NO_WINDOW

    progress.state = "flashing"
    job.progress_queue.put(progress.snapshot())
    start_time = time.time()

    try:
        proc = subprocess.Popen([str(exe)], **kwargs)
    except OSError as e:
        progress.state = "error"
        progress.error = f"Spawn newflasher lỗi: {e}"
        job.progress_queue.put(progress.snapshot())
        return

    job.process = proc

    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            if job.cancel_event.is_set():
                proc.terminate()
                break
            progress.elapsed_seconds = time.time() - start_time
            _parse_output_line(line, progress)
            # Throttle SSE emit — chỉ push khi state change hoặc mỗi 0.5s
            job.progress_queue.put(progress.snapshot())
    except Exception as e:
        logger.exception("flash_runner stdout read error")
        progress.error = f"Đọc stdout lỗi: {e}"

    proc.wait(timeout=10)
    progress.exit_code = proc.returncode
    progress.elapsed_seconds = time.time() - start_time

    if job.cancel_event.is_set():
        progress.state = "cancelled"
    elif proc.returncode == 0 and not progress.error:
        progress.state = "done"
    else:
        progress.state = "error"
        if not progress.error:
            progress.error = f"Newflasher exit code {proc.returncode}"

    job.progress_queue.put(progress.snapshot())


def start_flash_job(rom_dir: Path) -> FlashJob:
    """Spawn worker thread chạy newflasher trên rom_dir. Trả job_id để client subscribe SSE."""
    import secrets
    job_id = secrets.token_urlsafe(12)
    queue: Queue = Queue(maxsize=500)
    cancel = threading.Event()

    job = FlashJob(
        job_id=job_id, rom_dir=rom_dir,
        progress_queue=queue, cancel_event=cancel,
        thread=None,  # type: ignore[arg-type]
        started_at=time.time(),
    )

    thread = threading.Thread(target=_run_newflasher, args=(job,), name=f"flash-{job_id}", daemon=True)
    job.thread = thread

    with _JOBS_LOCK:
        _JOBS[job_id] = job
    thread.start()
    return job


def get_job(job_id: str) -> FlashJob | None:
    with _JOBS_LOCK:
        return _JOBS.get(job_id)


def cancel_job(job_id: str) -> bool:
    job = get_job(job_id)
    if not job:
        return False
    job.cancel_event.set()
    if job.process and job.process.poll() is None:
        try:
            job.process.terminate()
        except Exception:
            pass
    return True
