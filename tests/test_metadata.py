"""Task 1: 백업 메타데이터 파서(패스프레이즈 불필요) TDD."""
import plistlib
from datetime import datetime

import pytest

from ios_backup_vault.metadata import (
    dir_size_bytes,
    is_backup_dir,
    mask_pii,
    read_backup_metadata,
)


def _make_backup(tmp_path):
    bk = tmp_path / "UDID1"
    bk.mkdir()
    info = {
        "Device Name": "iPhone",
        "Product Type": "iPhone14,2",
        "Product Version": "17.2",
        "Build Version": "21C62",
        "Serial Number": "ABCDEF123456",
        "IMEI": "123456789012345",
        "ICCID": "8901410321111851234",
        "Phone Number": "+1010",
        "Target Identifier": "UDID1",
        "Last Backup Date": datetime(2026, 5, 30, 12, 0, 0),
        "Installed Applications": ["a", "b"],
    }
    manifest = {
        "IsEncrypted": True,
        "Date": datetime(2026, 5, 30, 12, 0, 0),
        "Version": "10.0",
        "WasPasscodeSet": True,
    }
    status = {
        "IsFullBackup": True,
        "UUID": "X",
        "Date": datetime(2026, 5, 30, 12, 0, 0),
        "BackupState": "new",
        "SnapshotState": "finished",
    }
    (bk / "Info.plist").write_bytes(plistlib.dumps(info))
    (bk / "Manifest.plist").write_bytes(plistlib.dumps(manifest))
    (bk / "Status.plist").write_bytes(plistlib.dumps(status))
    return bk


def test_is_backup_dir(tmp_path):
    bk = _make_backup(tmp_path)
    assert is_backup_dir(bk) is True
    empty = tmp_path / "empty"
    empty.mkdir()
    assert is_backup_dir(empty) is False


def test_mask_pii():
    assert mask_pii("123") == "•••"
    assert mask_pii("") == ""
    assert mask_pii(None) == ""
    assert mask_pii("ABCD") == "••••"
    assert mask_pii("ABCDEF123456") == "•" * 8 + "3456"


def test_dir_size_bytes(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"x" * 10)
    (tmp_path / "b.bin").write_bytes(b"y" * 5)
    assert dir_size_bytes(tmp_path) == 15


def test_read_backup_metadata_masked(tmp_path):
    bk = _make_backup(tmp_path)
    m = read_backup_metadata(bk, with_size=False)
    assert m["device_name"] == "iPhone"
    assert m["product_type"] == "iPhone14,2"
    assert m["ios_version"] == "17.2"
    assert m["build"] == "21C62"
    assert m["is_encrypted"] is True
    assert m["is_full"] is True
    assert m["app_count"] == 2
    assert m["udid"] == "UDID1"
    assert m["snapshot_state"] == "finished"
    assert m["backup_state"] == "new"
    assert m["size_bytes"] is None
    assert m["imaged_at"] == "2026-05-30T12:00:00"
    assert m["last_backup_date"] == "2026-05-30T12:00:00"
    assert m["serial"] == "•" * 8 + "3456"
    assert m["phone"] == "•" * 1 + "1010"  # "+1010" -> keep last 4
    assert m["imei"].endswith("2345")
    assert "•" in m["imei"]


def test_read_backup_metadata_reveal(tmp_path):
    bk = _make_backup(tmp_path)
    m = read_backup_metadata(bk, with_size=False, reveal_pii=True)
    assert m["serial"] == "ABCDEF123456"
    assert m["imei"] == "123456789012345"
    assert m["phone"] == "+1010"


def test_read_backup_metadata_with_size(tmp_path):
    bk = _make_backup(tmp_path)
    m = read_backup_metadata(bk, with_size=True)
    assert isinstance(m["size_bytes"], int)
    assert m["size_bytes"] > 0


def test_read_backup_metadata_not_backup(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError):
        read_backup_metadata(empty)
