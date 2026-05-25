"""Sony Xperia ROM metadata — download + decrypt + parse Igor's XperiFirm resources.

Tải file resources từ server XperiFirm community (igoreisberg.com), giải mã
AES-128-CBC + giải nén GZip để lấy XML chứa toàn bộ mapping:

    products → product → model → cust

Mapping này cần thiết để gọi Sony GCS API (cần các UUID HwVariantId,
ModelObjectId, ProductObjectId). XperiFirm 5.8.0+ chuyển sang dùng manual
list vì Sony's customization search API đã chết.

Cache local 7 ngày để tránh hit server Igor mỗi lần — chỉ refresh khi user
explicit hoặc cache hết hạn.

Logic AES + key derivation port nguyên từ XperiFirm 5.8.1 (sau de4dot).
"""
from __future__ import annotations

import gzip
import json
import logging
import time
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

logger = logging.getLogger(__name__)

RESOURCES_URL = "https://igoreisberg.com/xperifirm/resources"
USER_AGENT = "XperiFirm/5.8.1"
CACHE_TTL_SECONDS = 7 * 24 * 3600  # 7 ngày

ROOT = Path(__file__).parent
CACHE_DIR = ROOT / "vendor" / "rom_cache"
RESOURCES_XML = CACHE_DIR / "resources.xml"
RESOURCES_META = CACHE_DIR / "resources.meta.json"

# Lock cho fetch_resources — chống race khi nhiều request /api/rom/device đồng thời.
import threading as _threading
_RESOURCES_LOCK = _threading.Lock()


# ============ Decryption (port XperiFirm 5.8.1) ============


def _derive_key() -> bytes:
    """Reproduce XperiFirm key derivation. Hardcoded byte arrays + XOR + bit rotation.
    Output: 16-byte AES-128 key."""
    arr3 = [244, 45, 87, 45, 147, 31, 79, 89]
    arr4 = [2, 103, 211, 110, 12, 131, 88, 155]
    key = bytearray(16)
    for i in range(8):
        b = arr3[i] ^ 0xAA
        shift = (i + 3) & 7
        # ROL by `shift`
        key[i] = ((b << shift) | (b >> (8 - shift))) & 0xFF
    for j in range(8):
        b = arr4[j] ^ 0x5F
        shift = (j + 3 + 1) & 7
        # ROR by `shift`
        key[j + 8] = ((b >> shift) | (b << (8 - shift))) & 0xFF
    return bytes(key)


def _decrypt(raw: bytes) -> bytes:
    """Decrypt raw response: [16-byte IV][AES-128-CBC + PKCS7][GZip(XML)]."""
    if len(raw) < 32:
        raise ValueError(f"Resources data quá nhỏ: {len(raw)} bytes")
    iv = raw[:16]
    body = raw[16:]
    key = _derive_key()

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    d = cipher.decryptor()
    plain = d.update(body) + d.finalize()

    # Strip PKCS7 padding
    pad = plain[-1]
    if 1 <= pad <= 16 and plain[-pad:] == bytes([pad]) * pad:
        plain = plain[:-pad]

    return gzip.decompress(plain)


# ============ Data model ============


@dataclass(frozen=True)
class Customization:
    id: str           # CDFId
    name: str         # vd "Customized JP"
    spc: str | None   # SonyProductCode (43040127, ...)
    sst: str          # SecurityStateType, default "COMMERCIAL"
    market: str | None

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "spc": self.spc, "sst": self.sst, "market": self.market}


@dataclass(frozen=True)
class Model:
    id: str           # ModelObjectId (UUID)
    name: str         # vd "XQ-AS42"
    hwid: str         # HwVariantId (UUID)
    product_id: str   # ProductObjectId của parent
    product_name: str # vd "PDX-206"
    group_name: str   # vd "Smartphone (2020)"
    customizations: tuple[Customization, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "hwid": self.hwid,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "group_name": self.group_name,
            "customizations": [c.to_dict() for c in self.customizations],
        }


# ============ Network ============


def _download_raw(timeout: int = 30) -> bytes:
    logger.info("Downloading XperiFirm resources from %s", RESOURCES_URL)
    req = urllib.request.Request(RESOURCES_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_resources(force_refresh: bool = False) -> bytes:
    """Lấy resources XML — đọc từ cache nếu còn hợp lệ, ngược lại tải mới.
    Trả về XML bytes (đã decrypt + decompress).

    Thread-safe: dùng _RESOURCES_LOCK để chống concurrent write race
    (vd: 2 request /api/rom/device gọi cùng lúc khi cache hết hạn)."""
    with _RESOURCES_LOCK:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        if not force_refresh and RESOURCES_XML.exists() and RESOURCES_META.exists():
            try:
                meta = json.loads(RESOURCES_META.read_text(encoding="utf-8"))
                age = time.time() - meta.get("fetched_at", 0)
                if age < CACHE_TTL_SECONDS:
                    logger.info("Using cached resources (%.0f hours old)", age / 3600)
                    return RESOURCES_XML.read_bytes()
            except (json.JSONDecodeError, OSError):
                logger.warning("Cache meta corrupt, refetching")

        raw = _download_raw()
        xml_bytes = _decrypt(raw)
        # Write atomic: write to .tmp rồi rename, tránh partial file nếu crash giữa chừng
        tmp_xml = RESOURCES_XML.with_suffix(".xml.tmp")
        tmp_meta = RESOURCES_META.with_suffix(".json.tmp")
        tmp_xml.write_bytes(xml_bytes)
        tmp_meta.write_text(
            json.dumps({"fetched_at": time.time(), "raw_size": len(raw), "xml_size": len(xml_bytes)}),
            encoding="utf-8",
        )
        tmp_xml.replace(RESOURCES_XML)
        tmp_meta.replace(RESOURCES_META)
        logger.info("Resources cached: %d bytes XML", len(xml_bytes))
        return xml_bytes


# ============ Parse ============


def _iter_models(xml_bytes: bytes) -> Iterator[Model]:
    root = ET.fromstring(xml_bytes)
    products_node = root.find("products")
    if products_node is None:
        return
    for group in products_node.findall("group"):
        gname = group.get("name", "")
        for product in group.findall("product"):
            pid = product.get("id")
            pname = product.get("name", "")
            if not pid:
                continue
            for model in product.findall("model"):
                mid = model.get("id")
                mname = model.get("name") or ""
                hwid = model.get("hwid")
                if not mid or not hwid:
                    continue
                custs = []
                for c in model.findall("cust"):
                    cid = c.get("id")
                    if not cid:
                        continue
                    custs.append(Customization(
                        id=cid,
                        name=c.get("name") or "",
                        spc=c.get("spc"),
                        sst=c.get("sst") or "COMMERCIAL",
                        market=c.get("market"),
                    ))
                yield Model(
                    id=mid,
                    name=mname,
                    hwid=hwid,
                    product_id=pid,
                    product_name=pname,
                    group_name=gname,
                    customizations=tuple(custs),
                )


def find_model(model_name: str, xml_bytes: bytes | None = None) -> Model | None:
    """Tìm model theo tên (vd "XQ-AS42"). Trả None nếu không có."""
    if xml_bytes is None:
        xml_bytes = fetch_resources()
    target = model_name.strip().upper()
    for m in _iter_models(xml_bytes):
        if m.name.upper() == target:
            return m
    return None


def search_models(query: str, xml_bytes: bytes | None = None, limit: int = 20) -> list[Model]:
    """Tìm models có tên match substring (case-insensitive). Dùng cho UI search."""
    if xml_bytes is None:
        xml_bytes = fetch_resources()
    q = query.strip().lower()
    hits = []
    for m in _iter_models(xml_bytes):
        if q in m.name.lower():
            hits.append(m)
            if len(hits) >= limit:
                break
    return hits


def all_model_names(xml_bytes: bytes | None = None) -> list[str]:
    """List toàn bộ model names. Dùng cho dropdown / stats."""
    if xml_bytes is None:
        xml_bytes = fetch_resources()
    return [m.name for m in _iter_models(xml_bytes) if m.name]
