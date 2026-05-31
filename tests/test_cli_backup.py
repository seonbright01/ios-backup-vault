import plistlib
from pathlib import Path
import pytest
from ios_backup_vault import device
from ios_backup_vault.cli import run_backup_command
from ios_backup_vault.device import DeviceNotConnected


def _info_fn(will_encrypt=True):
    def fn(domain=None, udid=None):
        if domain == device.BACKUP_DOMAIN:
            return {device.KEY_WILL_ENCRYPT: will_encrypt}
        return {device.KEY_PRODUCT_VERSION: "26.2"}
    return fn


def test_run_backup_command_happy(tmp_path):
    udid = "u1"
    def do_backup(root):
        bp = Path(root) / udid
        bp.mkdir(parents=True, exist_ok=True)
        for f in ["Manifest.plist", "Manifest.db", "Info.plist"]:
            (bp / f).write_bytes(b"x")
        (bp / "Status.plist").write_bytes(plistlib.dumps({"SnapshotState": "finished", "IsFullBackup": True}))
    bp, integ, meta = run_backup_command(
        str(tmp_path),
        want_encryption=True,
        list_udids=lambda: [udid],
        is_paired=lambda u: True,
        device_info=_info_fn(),
        do_backup=do_backup,
        consent_fn=lambda plan: True,
        enable_encryption_fn=lambda: None,
        now_iso="2026-05-30T00:00:00",
    )
    assert integ.ok is True
    assert meta.encryption_enabled is True


def test_run_backup_command_no_device(tmp_path):
    with pytest.raises(DeviceNotConnected):
        run_backup_command(
            str(tmp_path), want_encryption=True,
            list_udids=lambda: [], is_paired=lambda u: True,
            device_info=_info_fn(), do_backup=lambda r: None,
            consent_fn=lambda p: True, enable_encryption_fn=lambda: None, now_iso="t",
        )
