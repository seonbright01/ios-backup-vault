import plistlib
from pathlib import Path
from ios_backup_vault.backup import verify_integrity, IntegrityResult

REQUIRED = ["Status.plist", "Manifest.plist", "Manifest.db", "Info.plist"]


def _make_backup(dirpath: Path, snapshot="finished", is_full=True, files=REQUIRED):
    dirpath.mkdir(parents=True, exist_ok=True)
    for f in files:
        (dirpath / f).write_bytes(b"x")
    (dirpath / "Status.plist").write_bytes(
        plistlib.dumps({"SnapshotState": snapshot, "IsFullBackup": is_full})
    )


def test_verify_ok(tmp_path):
    bp = tmp_path / "udid1"
    _make_backup(bp)
    res = verify_integrity(bp)
    assert isinstance(res, IntegrityResult)
    assert res.ok is True
    assert res.snapshot_state == "finished"
    assert res.is_full is True
    assert res.missing == []


def test_verify_missing_files(tmp_path):
    bp = tmp_path / "udid2"
    _make_backup(bp, files=["Status.plist", "Info.plist"])  # Manifest.* 누락
    res = verify_integrity(bp)
    assert res.ok is False
    assert "Manifest.db" in res.missing


def test_verify_unfinished_snapshot(tmp_path):
    bp = tmp_path / "udid3"
    _make_backup(bp, snapshot="running")
    res = verify_integrity(bp)
    assert res.ok is False
    assert res.snapshot_state == "running"


import json as _json
from ios_backup_vault.backup import (
    BackupMetadata, write_backup_metadata, dir_size_and_count,
)


def test_dir_size_and_count(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"12345")      # 5 bytes
    sub = tmp_path / "sub"; sub.mkdir()
    (sub / "b.bin").write_bytes(b"678")             # 3 bytes
    size, count = dir_size_and_count(tmp_path)
    assert size == 8
    assert count == 2


def test_write_backup_metadata(tmp_path):
    meta = BackupMetadata(
        udid="u1", ios_version="26.2", encryption_enabled=True,
        size_bytes=8, file_count=2, created_at="2026-05-30T00:00:00",
    )
    out = tmp_path / "u1.vault_meta.json"
    write_backup_metadata(out, meta)
    data = _json.loads(out.read_text())
    assert data["udid"] == "u1"
    assert data["encryption_enabled"] is True
    assert data["size_bytes"] == 8
    assert data["created_at"] == "2026-05-30T00:00:00"


import pytest
from ios_backup_vault.backup import run_backup_flow, BackupAborted, BackupIntegrityError
from ios_backup_vault.safety import DeviceState


def _fake_do_backup_factory(udid, ok=True):
    def _do(target_root):
        bp = Path(target_root) / udid
        bp.mkdir(parents=True, exist_ok=True)
        for f in ["Manifest.plist", "Manifest.db", "Info.plist"]:
            (bp / f).write_bytes(b"x")
        snap = "finished" if ok else "running"
        (bp / "Status.plist").write_bytes(plistlib.dumps({"SnapshotState": snap, "IsFullBackup": True}))
    return _do


def test_run_backup_flow_happy_encryption_already_on(tmp_path):
    state = DeviceState("u1", True, backup_encryption_enabled=True, ios_version="26.2")
    calls = {"enabled": False}
    bp, integ, meta = run_backup_flow(
        str(tmp_path),
        state=state, want_encryption=True, now_iso="2026-05-30T00:00:00",
        consent_fn=lambda plan: True,
        enable_encryption_fn=lambda: calls.__setitem__("enabled", True),
        do_backup=_fake_do_backup_factory("u1", ok=True),
    )
    assert integ.ok is True
    assert meta.udid == "u1" and meta.file_count == 4
    assert calls["enabled"] is False  # 이미 켜져 있으니 enable 호출 안 됨
    assert (tmp_path / "u1.vault_meta.json").exists()
    assert (tmp_path / "u1.original_state.json").exists()


def test_run_backup_flow_aborts_without_consent_when_enabling(tmp_path):
    state = DeviceState("u1", True, backup_encryption_enabled=False, ios_version="26.2")
    called = {"backup": False}
    def do(_):
        called["backup"] = True
    with pytest.raises(BackupAborted):
        run_backup_flow(
            str(tmp_path),
            state=state, want_encryption=True, now_iso="t",
            consent_fn=lambda plan: False,           # 미동의
            enable_encryption_fn=lambda: None,
            do_backup=do,
        )
    assert called["backup"] is False  # 백업 시작 안 함


def test_run_backup_flow_integrity_failure(tmp_path):
    state = DeviceState("u1", True, backup_encryption_enabled=True, ios_version="26.2")
    with pytest.raises(BackupIntegrityError):
        run_backup_flow(
            str(tmp_path),
            state=state, want_encryption=True, now_iso="t",
            consent_fn=lambda plan: True,
            enable_encryption_fn=lambda: None,
            do_backup=_fake_do_backup_factory("u1", ok=False),  # snapshot=running
        )


def test_verify_integrity_malformed_status_plist(tmp_path):
    from ios_backup_vault.backup import verify_integrity, BackupIntegrityError
    bp = tmp_path / "udidX"; bp.mkdir()
    for f in ["Manifest.plist", "Manifest.db", "Info.plist"]:
        (bp / f).write_bytes(b"x")
    (bp / "Status.plist").write_bytes(b"\x00not a plist")
    with pytest.raises(BackupIntegrityError):
        verify_integrity(bp)
