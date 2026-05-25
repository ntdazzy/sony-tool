"""Sony GCS (Global Cloud Services) API client — query firmware list cho 1 (model, customization).

Endpoint hiện tại (verified 2026-05-25):
    GET https://app.swup.update.sony.net/ess-distribution/public/api/device-service/match/v2

Sony đổi endpoint nhiều lần trong 2025 (XperiFirm 5.7.1, 5.8.0 phải update).
Nếu API chết hoặc đổi format → cần repeat reverse engineering process trên
XperiFirm version mới hơn.
"""
from __future__ import annotations

import logging
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from rom_resources import Customization, Model

logger = logging.getLogger(__name__)

GCS_BASE = "https://app.swup.update.sony.net/ess-distribution/public/api/"
USER_AGENT = "XperiFirm/5.8.1"


class GcsError(RuntimeError):
    pass


@dataclass(frozen=True)
class FirmwareEntry:
    """1 phiên bản firmware có sẵn cho (model, cust)."""
    version: str           # vd "64.0.A.5.10"
    revision: str | None   # vd "R5A" (phần sau dash)
    logic_type: str        # vd "SOFTWARE_UPDATE_CONTENT_ERASE" hoặc "CR_SOFTWARE_UPDATE"
    download_url: str      # link href trong response (đã HTML-decoded)
    release_state: str     # "RELEASED" / "BETA" / ...
    android_update_type: str  # "NA" / "MAJOR" / ...

    @property
    def is_factory_reset(self) -> bool:
        """SOFTWARE_UPDATE_CONTENT_ERASE = wipe data; CR_SOFTWARE_UPDATE = giữ data."""
        return self.logic_type == "SOFTWARE_UPDATE_CONTENT_ERASE"

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "revision": self.revision,
            "logic_type": self.logic_type,
            "download_url": self.download_url,
            "release_state": self.release_state,
            "android_update_type": self.android_update_type,
            "is_factory_reset": self.is_factory_reset,
        }


@dataclass
class FirmwareList:
    """Kết quả query: cả firmware list + status."""
    model_name: str
    cust_name: str
    device_problem: str             # "NO_PROBLEM" nếu OK, else error code
    entries: list[FirmwareEntry] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.device_problem == "NO_PROBLEM"

    def to_dict(self) -> dict:
        return {
            "model_name": self.model_name,
            "cust_name": self.cust_name,
            "device_problem": self.device_problem,
            "ok": self.ok,
            "entries": [e.to_dict() for e in self.entries],
        }


def _build_url(model: Model, cust: Customization) -> str:
    params: list[tuple[str, str]] = []
    # Nếu có SPC, dùng SPC; ngược lại CDFId. XperiFirm cũng dùng heuristic này.
    if not cust.spc:
        params.append(("CDFId", cust.id))
    params.append(("HwSetupKey", "Default"))
    params.append(("HWVariantId", model.hwid))
    params.append(("ModelObjectId", model.id))
    params.append(("ProductObjectId", model.product_id))
    params.append(("SecurityStateType", cust.sst))
    if cust.spc:
        params.append(("SonyProductCode", cust.spc))

    return GCS_BASE + "device-service/match/v2?" + urllib.parse.urlencode(params)


def _parse_response(xml_str: str, model_name: str, cust_name: str) -> FirmwareList:
    root = ET.fromstring(xml_str)
    if root.tag != "match-response":
        raise GcsError(f"Response root sai: {root.tag} (expected 'match-response')")

    problem_node = root.find("device-problem")
    device_problem = problem_node.text.strip() if problem_node is not None and problem_node.text else "UNKNOWN"

    fw_list = FirmwareList(model_name=model_name, cust_name=cust_name, device_problem=device_problem)
    if device_problem != "NO_PROBLEM":
        logger.warning("Sony reported device-problem='%s' for %s / %s", device_problem, model_name, cust_name)
        return fw_list

    infos = root.findall("device-service-infos/software-device-service-info")
    seen_versions: set[tuple[str, str]] = set()  # (version, logic_type) dedup

    for info in infos:
        version_node = info.find("software-version")
        link_node = info.find("link")
        logic_node = info.find("logic-type")
        rel_node = info.find("release-state")
        avut_node = info.find("android-version-update-type")

        if version_node is None or link_node is None or logic_node is None:
            continue
        raw_version = (version_node.text or "").strip()
        if not raw_version:
            continue

        # Format thật: "58.2.A.10.163" hoặc "58.2.A.10.163-R5A"
        parts = raw_version.split("-", 1)
        version = parts[0]
        revision = parts[1] if len(parts) == 2 else None

        logic_type = (logic_node.text or "").strip()
        key = (version, logic_type)
        if key in seen_versions:
            continue
        seen_versions.add(key)

        # href bị HTML-encoded (&amp;) — ET tự decode entity
        download_url = link_node.get("href") or ""
        release_state = (rel_node.text or "RELEASED").strip() if rel_node is not None else "RELEASED"
        avut = (avut_node.text or "NA").strip() if avut_node is not None else "NA"

        fw_list.entries.append(FirmwareEntry(
            version=version,
            revision=revision,
            logic_type=logic_type,
            download_url=download_url,
            release_state=release_state,
            android_update_type=avut,
        ))

    # Sort: version desc (newest first), giữ data > wipe data cho cùng version
    fw_list.entries.sort(key=lambda e: (_version_key(e.version), 0 if e.is_factory_reset else 1), reverse=True)
    return fw_list


def _version_key(v: str) -> tuple[int, ...]:
    """Convert '58.2.A.10.163' → (58, 2, 0, 10, 163) cho sort. Letter 'A' → 0."""
    out: list[int] = []
    for part in v.split("."):
        if part.isdigit():
            out.append(int(part))
        else:
            # 'A', 'B', ... → 0, 1, ...
            if len(part) == 1 and part.isalpha():
                out.append(ord(part.upper()) - ord("A"))
            else:
                out.append(0)
    return tuple(out)


def query_firmware(model: Model, cust: Customization, timeout: int = 30) -> FirmwareList:
    """Gọi Sony API match/v2 → trả danh sách firmware version cho (model, cust)."""
    url = _build_url(model, cust)
    logger.info("Query Sony GCS: %s", url)

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise GcsError(f"Sony API HTTP {e.code}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise GcsError(f"Sony API không gọi được: {e.reason}") from e

    return _parse_response(body, model.name, cust.name)


def query_all_customizations(model: Model, timeout: int = 30) -> list[FirmwareList]:
    """Query firmware cho TẤT CẢ customization của 1 model. UI cần list này
    để show toàn bộ ROM available."""
    out = []
    for cust in model.customizations:
        try:
            out.append(query_firmware(model, cust, timeout=timeout))
        except GcsError as e:
            logger.warning("Bỏ qua cust %s do lỗi: %s", cust.name, e)
            out.append(FirmwareList(
                model_name=model.name, cust_name=cust.name,
                device_problem=f"ERROR: {e}",
            ))
    return out
