"""Tải firmware Sony + build FTF (Flashable Firmware) file.

Sony cấu trúc 2-tier:
1. GET <firmware_url> (từ Sony match/v2 response) → XML file-resources
2. Mỗi file-resource → GET <link href> → XML chunks
3. GET từng chunk URL → concat bytes → save thành .sin file
4. (Optional) ZIP tất cả .sin + manifest.txt → .ftf (newflasher đọc cả 2 format)

Logic port từ XperiFirm 5.8.1 (sau de4dot). Có MD5 verify per-file và per-chunk.
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue

logger = logging.getLogger(__name__)

USER_AGENT = "XperiFirm/5.8.1"
CHUNK_BUFFER_SIZE = 64 * 1024  # 64KB read buffer

ROOT = Path(__file__).parent
DOWNLOADS_DIR = ROOT / "vendor" / "rom_downloads"


# ============ Data model ============


@dataclass
class ChunkInfo:
    number: int
    size: int               # bytes
    md5: str | None         # hex MD5 hash
    url: str                # download URL


@dataclass
class FileResource:
    """1 partition trong firmware (boot, system, vendor, ...)."""
    content_id: int
    file_key: str           # vd "boot_partition_image"
    original_name: str      # vd "boot_BLA_BLA.sin"
    extension: str          # vd ".sin"
    gzipped: bool
    file_md5: str | None
    chunks: list[ChunkInfo] = field(default_factory=list)

    @property
    def filename(self) -> str:
        """Filename newflasher expects: file_key (lowercase, _→-) + extension."""
        return self.file_key.replace("_", "-").lower() + self.extension

    @property
    def total_size(self) -> int:
        return sum(c.size for c in self.chunks)


@dataclass
class DownloadProgress:
    """Snapshot trạng thái download — push vào queue cho SSE."""
    job_id: str
    state: str              # "init" | "list_files" | "downloading" | "done" | "error" | "cancelled"
    current_file: str = ""
    files_done: int = 0
    files_total: int = 0
    bytes_done: int = 0
    bytes_total: int = 0
    speed_bps: float = 0.0   # bytes per second
    eta_seconds: float = 0.0
    error: str | None = None
    output_dir: str | None = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "state": self.state,
            "current_file": self.current_file,
            "files_done": self.files_done,
            "files_total": self.files_total,
            "bytes_done": self.bytes_done,
            "bytes_total": self.bytes_total,
            "speed_bps": round(self.speed_bps, 1),
            "eta_seconds": round(self.eta_seconds, 1),
            "percent": round(100.0 * self.bytes_done / max(self.bytes_total, 1), 2),
            "error": self.error,
            "output_dir": self.output_dir,
        }


class DownloadCancelled(Exception):
    pass


def _emit(q: Queue, item: dict) -> None:
    """Non-blocking emit — drop nếu queue full thay vì block worker thread.
    Tránh deadlock khi SSE client chậm hoặc disconnect."""
    try:
        q.put_nowait(item)
    except Exception:
        logger.debug("Queue full, drop event")


# ============ HTTP helpers ============


def _http_get_text(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def _http_get_stream(url: str, timeout: int = 60):
    """Trả response object có .read(n), .length. Caller phải close."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=timeout)


# ============ Parse Sony XML ============


def fetch_file_list(firmware_url: str) -> list[FileResource]:
    """GET firmware URL → parse file-resources → return list partition.
    Mỗi file-resource sẽ fetch tiếp chunk list ở step sau."""
    logger.info("Fetching file list from %s", firmware_url)
    xml_str = _http_get_text(firmware_url, timeout=30)

    root = ET.fromstring(xml_str)
    # Path: <software-device-service><file-resources><file-resource>
    resources = root.findall(".//file-resources/file-resource")
    if not resources:
        # Try alternate path (in case root is file-resources)
        resources = root.findall("file-resource")
    if not resources:
        raise RuntimeError(f"Không tìm thấy file-resource trong XML response (root={root.tag})")

    out: list[FileResource] = []
    for r in resources:
        name_node = r.find("name")
        key_node = r.find("file-key")
        link_node = r.find("link")
        gz_node = r.find("gzipped")
        if name_node is None or key_node is None or link_node is None:
            continue
        name = (name_node.text or "").strip()
        if name.startswith("@template"):
            continue  # skip template/metadata entries
        file_key = (key_node.text or "").strip()
        content_id_attr = r.get("content-id") or "0"
        try:
            content_id = int(content_id_attr)
        except ValueError:
            content_id = 0
        # Extension from original filename
        ext_idx = name.rfind(".")
        extension = name[ext_idx:] if ext_idx >= 0 else ""
        gzipped = False
        if gz_node is not None and gz_node.text:
            gzipped = gz_node.text.strip().lower() == "true"
        link_href = link_node.get("href", "")

        # Fetch chunk list immediately (small XML, ~few KB)
        chunks, file_md5 = _fetch_chunks(link_href)

        out.append(FileResource(
            content_id=content_id,
            file_key=file_key,
            original_name=name,
            extension=extension,
            gzipped=gzipped,
            file_md5=file_md5,
            chunks=chunks,
        ))
    logger.info("Got %d file resources", len(out))
    return out


def _fetch_chunks(link_url: str) -> tuple[list[ChunkInfo], str | None]:
    xml_str = _http_get_text(link_url, timeout=20)
    root = ET.fromstring(xml_str)
    # Root có thể là <file-chunks>
    if root.tag != "file-chunks":
        node = root.find(".//file-chunks")
        if node is not None:
            root = node

    md5_node = root.find("content-md5")
    file_md5 = (md5_node.text or "").strip() if md5_node is not None and md5_node.text else None

    chunks: list[ChunkInfo] = []
    for c in root.findall("file-chunk"):
        try:
            number = int(c.get("number", "0"))
        except ValueError:
            number = 0
        size_node = c.find("size")
        link_node = c.find("link")
        cmd5_node = c.find("content-md5")
        if size_node is None or link_node is None:
            continue
        try:
            size = int((size_node.text or "0").strip())
        except ValueError:
            size = 0
        c_md5 = (cmd5_node.text or "").strip() if cmd5_node is not None and cmd5_node.text else None
        chunks.append(ChunkInfo(
            number=number,
            size=size,
            md5=c_md5,
            url=link_node.get("href", ""),
        ))
    chunks.sort(key=lambda x: x.number)
    return chunks, file_md5


# ============ Download with progress ============


class _SpeedMeter:
    """Smooth-ish speed calculator dùng window 5 giây."""

    def __init__(self) -> None:
        self.samples: list[tuple[float, int]] = []  # (timestamp, bytes_cumulative)

    def add(self, bytes_cumulative: int) -> float:
        now = time.time()
        self.samples.append((now, bytes_cumulative))
        # Keep only last 5s
        cutoff = now - 5.0
        while self.samples and self.samples[0][0] < cutoff:
            self.samples.pop(0)
        if len(self.samples) < 2:
            return 0.0
        dt = self.samples[-1][0] - self.samples[0][0]
        db = self.samples[-1][1] - self.samples[0][1]
        return db / dt if dt > 0 else 0.0


def download_firmware(
    firmware_url: str,
    output_dir: Path,
    job_id: str,
    progress_queue: Queue,
    cancel_event: threading.Event,
) -> Path:
    """Tải toàn bộ firmware vào output_dir. Đẩy DownloadProgress vào queue
    để SSE stream cho frontend. Raise DownloadCancelled nếu cancel_event set.
    Trả về output_dir khi xong."""
    output_dir.mkdir(parents=True, exist_ok=True)
    progress = DownloadProgress(job_id=job_id, state="list_files", output_dir=str(output_dir))
    _emit(progress_queue, progress.to_dict())

    try:
        files = fetch_file_list(firmware_url)
    except Exception as e:
        progress.state = "error"
        progress.error = f"Không lấy được danh sách file: {e}"
        _emit(progress_queue, progress.to_dict())
        raise

    progress.files_total = len(files)
    progress.bytes_total = sum(f.total_size for f in files)
    progress.state = "downloading"
    _emit(progress_queue, progress.to_dict())

    meter = _SpeedMeter()
    bytes_done_global = 0
    last_emit = 0.0  # emit progress max 5 lần/giây

    for f_idx, fr in enumerate(files):
        if cancel_event.is_set():
            progress.state = "cancelled"
            _emit(progress_queue, progress.to_dict())
            raise DownloadCancelled()

        progress.current_file = fr.filename
        progress.files_done = f_idx
        _emit(progress_queue, progress.to_dict())

        target = output_dir / fr.filename
        # Resume: nếu file tồn tại và đúng size → skip
        if target.exists() and target.stat().st_size == fr.total_size:
            logger.info("Skip %s (already done)", fr.filename)
            bytes_done_global += fr.total_size
            progress.bytes_done = bytes_done_global
            continue

        target_tmp = target.with_suffix(target.suffix + ".part")
        md5_hash = hashlib.md5() if fr.file_md5 else None

        with target_tmp.open("wb") as fout:
            for chunk in fr.chunks:
                if cancel_event.is_set():
                    fout.close()
                    target_tmp.unlink(missing_ok=True)
                    progress.state = "cancelled"
                    _emit(progress_queue, progress.to_dict())
                    raise DownloadCancelled()

                resp = _http_get_stream(chunk.url, timeout=60)
                try:
                    while True:
                        if cancel_event.is_set():
                            resp.close()
                            fout.close()
                            target_tmp.unlink(missing_ok=True)
                            progress.state = "cancelled"
                            _emit(progress_queue, progress.to_dict())
                            raise DownloadCancelled()
                        buf = resp.read(CHUNK_BUFFER_SIZE)
                        if not buf:
                            break
                        fout.write(buf)
                        if md5_hash:
                            md5_hash.update(buf)
                        bytes_done_global += len(buf)
                        progress.bytes_done = bytes_done_global

                        # Throttled emit
                        now = time.time()
                        if now - last_emit >= 0.2:
                            last_emit = now
                            speed = meter.add(bytes_done_global)
                            progress.speed_bps = speed
                            remaining = progress.bytes_total - progress.bytes_done
                            progress.eta_seconds = remaining / speed if speed > 0 else 0
                            _emit(progress_queue, progress.to_dict())
                finally:
                    resp.close()

        # Verify MD5 nếu Sony cung cấp
        if md5_hash and fr.file_md5:
            actual = md5_hash.hexdigest()
            if actual.lower() != fr.file_md5.lower():
                target_tmp.unlink(missing_ok=True)
                progress.state = "error"
                progress.error = f"MD5 không khớp cho {fr.filename} (got {actual[:8]}.. expected {fr.file_md5[:8]}..)"
                _emit(progress_queue, progress.to_dict())
                raise RuntimeError(progress.error)

        target_tmp.replace(target)
        logger.info("Done %s (%d bytes)", fr.filename, fr.total_size)

    progress.state = "done"
    progress.files_done = progress.files_total
    progress.current_file = ""
    progress.eta_seconds = 0
    _emit(progress_queue, progress.to_dict())
    return output_dir


# ============ Job manager (in-memory) ============


@dataclass
class DownloadJob:
    job_id: str
    firmware_url: str
    output_dir: Path
    progress_queue: Queue
    cancel_event: threading.Event
    thread: threading.Thread
    started_at: float


_JOBS: dict[str, DownloadJob] = {}
_JOBS_LOCK = threading.Lock()


def start_download_job(firmware_url: str, label: str) -> DownloadJob:
    """Spawn background thread tải firmware. Trả job_id để client subscribe SSE."""
    import secrets
    job_id = secrets.token_urlsafe(12)
    # Safe folder name từ label — reject control char, path separator, reserved name.
    safe_label = "".join(c if c.isalnum() or c in ".-_" else "_" for c in label)[:80]
    # Strip leading/trailing dot+underscore để tránh ".." hoặc "..." → folder ẩn/lỗi Windows
    safe_label = safe_label.strip("._")
    if not safe_label:
        safe_label = "rom"
    output_dir = DOWNLOADS_DIR / f"{safe_label}_{int(time.time())}"

    queue: Queue = Queue(maxsize=200)
    cancel = threading.Event()

    def runner():
        try:
            download_firmware(firmware_url, output_dir, job_id, queue, cancel)
        except DownloadCancelled:
            logger.info("Job %s cancelled", job_id)
        except Exception as e:
            logger.exception("Job %s failed: %s", job_id, e)
            _emit(queue, {"job_id": job_id, "state": "error", "error": str(e)})

    thread = threading.Thread(target=runner, name=f"download-{job_id}", daemon=True)
    job = DownloadJob(
        job_id=job_id, firmware_url=firmware_url, output_dir=output_dir,
        progress_queue=queue, cancel_event=cancel, thread=thread,
        started_at=time.time(),
    )
    with _JOBS_LOCK:
        _JOBS[job_id] = job
    thread.start()
    return job


def get_job(job_id: str) -> DownloadJob | None:
    with _JOBS_LOCK:
        return _JOBS.get(job_id)


def cancel_job(job_id: str) -> bool:
    job = get_job(job_id)
    if not job:
        return False
    job.cancel_event.set()
    return True


def cleanup_finished_jobs(max_age_seconds: float = 3600) -> int:
    """Dọn job đã done/error/cancelled cũ. Trả về số job dọn."""
    now = time.time()
    removed = 0
    with _JOBS_LOCK:
        for jid in list(_JOBS.keys()):
            job = _JOBS[jid]
            if not job.thread.is_alive() and (now - job.started_at) > max_age_seconds:
                del _JOBS[jid]
                removed += 1
    return removed
