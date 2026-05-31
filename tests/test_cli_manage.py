"""Task 3: CLI list/add/info + 자동등록 TDD."""
import plistlib
from datetime import datetime

from ios_backup_vault.cli import main


def _make_backup(tmp_path, name="UDID1"):
    bk = tmp_path / name
    bk.mkdir()
    info = {
        "Target Identifier": name,
        "Device Name": "iPhone",
        "Product Type": "iPhone14,2",
        "Product Version": "17.2",
        "Serial Number": "ABCDEF123456",
        "Last Backup Date": datetime(2026, 5, 30, 12, 0, 0),
        "Installed Applications": ["a"],
    }
    manifest = {"IsEncrypted": True, "Date": datetime(2026, 5, 30, 12, 0, 0)}
    status = {"IsFullBackup": True, "SnapshotState": "finished"}
    (bk / "Info.plist").write_bytes(plistlib.dumps(info))
    (bk / "Manifest.plist").write_bytes(plistlib.dumps(manifest))
    (bk / "Status.plist").write_bytes(plistlib.dumps(status))
    return bk


def test_info(tmp_path, capsys):
    bk = _make_backup(tmp_path)
    rc = main(["info", "--backup", str(bk)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "iPhone" in out
    # PII는 기본 마스킹
    assert "ABCDEF123456" not in out


def test_add_and_list(tmp_path, capsys, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("IOS_BACKUP_VAULT_HOME", str(home))
    bk = _make_backup(tmp_path)
    from ios_backup_vault import registry

    rc = main(["add", "--path", str(bk)])
    assert rc == 0
    assert len(registry.load(registry.registry_path())) == 1

    rc = main(["list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "iPhone" in out or str(bk) in out


def test_add_non_backup(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("IOS_BACKUP_VAULT_HOME", str(tmp_path / "home"))
    bad = tmp_path / "bad"
    bad.mkdir()
    rc = main(["add", "--path", str(bad)])
    assert rc != 0
    err = capsys.readouterr().err
    assert err
