"""백업(이미지) 메타데이터 읽기. 패스프레이즈 불필요 — 공개 plist만 파싱.

PII(Serial/IMEI/ICCID/Phone)는 기본 마스킹, reveal_pii=True에서만 원본 노출.
"""
import os
import plistlib
from datetime import datetime
from pathlib import Path

_INFO = "Info.plist"
_MANIFEST = "Manifest.plist"
_STATUS = "Status.plist"


def is_backup_dir(path) -> bool:
    """Info.plist & Manifest.plist 존재 시 백업 폴더로 판정."""
    p = Path(path)
    return (p / _INFO).is_file() and (p / _MANIFEST).is_file()


def mask_pii(s) -> str:
    """None/빈값→""; 길이≤4면 전부 마스킹; 아니면 마지막 4자만 남기고 앞을 마스킹."""
    if not s:
        return ""
    s = str(s)
    if len(s) <= 4:
        return "•" * len(s)
    return "•" * (len(s) - 4) + s[-4:]


def dir_size_bytes(path) -> int:
    """os.walk로 파일 stat 합(심볼릭 링크는 따라가지 않음)."""
    total = 0
    for root, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            fp = os.path.join(root, name)
            try:
                st = os.lstat(fp)
            except OSError:
                continue
            if os.path.islink(fp):
                continue
            total += st.st_size
    return total


def _iso(value) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return ""


def read_backup_metadata(path, *, with_size=True, reveal_pii=False) -> dict:
    """공개 plist에서 백업 메타데이터를 읽어 dict로 반환."""
    p = Path(path)
    if not is_backup_dir(p):
        raise ValueError(f"백업 폴더가 아님: {p}")

    info = plistlib.loads((p / _INFO).read_bytes())
    manifest = plistlib.loads((p / _MANIFEST).read_bytes())
    status = {}
    status_file = p / _STATUS
    if status_file.is_file():
        status = plistlib.loads(status_file.read_bytes())

    imaged_at = _iso(status.get("Date")) or _iso(manifest.get("Date"))

    def _pii(value):
        raw = "" if value is None else str(value)
        return raw if reveal_pii else mask_pii(raw)

    return {
        "path": str(p),
        "udid": info.get("Target Identifier") or p.name,
        "device_name": info.get("Device Name", ""),
        "product_type": info.get("Product Type", ""),
        "ios_version": info.get("Product Version", ""),
        "build": info.get("Build Version", ""),
        "imaged_at": imaged_at,
        "last_backup_date": _iso(info.get("Last Backup Date")),
        "is_encrypted": bool(manifest.get("IsEncrypted", False)),
        "is_full": bool(status.get("IsFullBackup", False)),
        "snapshot_state": status.get("SnapshotState", ""),
        "backup_state": status.get("BackupState", ""),
        "app_count": len(info.get("Installed Applications", []) or []),
        "size_bytes": dir_size_bytes(p) if with_size else None,
        "serial": _pii(info.get("Serial Number")),
        "imei": _pii(info.get("IMEI")),
        "iccid": _pii(info.get("ICCID")),
        "phone": _pii(info.get("Phone Number")),
    }
