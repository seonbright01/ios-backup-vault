"""Task 2: 백업 레지스트리 TDD."""
import plistlib

import pytest

from ios_backup_vault import registry


def _make_backup(tmp_path, name="UDID1"):
    bk = tmp_path / name
    bk.mkdir()
    (bk / "Info.plist").write_bytes(plistlib.dumps({"Target Identifier": name}))
    (bk / "Manifest.plist").write_bytes(plistlib.dumps({"IsEncrypted": True}))
    return bk


def test_load_missing(tmp_path):
    assert registry.load(str(tmp_path / "registry.json")) == []


def test_add_and_load(tmp_path):
    reg = str(tmp_path / "reg" / "registry.json")
    bk = _make_backup(tmp_path)
    entry = registry.add(reg, str(bk), label="라벨", now_iso="2026-05-31T00:00:00")
    assert entry["label"] == "라벨"
    assert entry["added_at"] == "2026-05-31T00:00:00"
    items = registry.load(reg)
    assert len(items) == 1
    assert items[0]["path"] == str(bk.resolve())
    assert items[0]["label"] == "라벨"
    assert items[0]["added_at"] == "2026-05-31T00:00:00"


def test_add_duplicate_updates(tmp_path):
    reg = str(tmp_path / "registry.json")
    bk = _make_backup(tmp_path)
    registry.add(reg, str(bk), label="A")
    registry.add(reg, str(bk), label="B")
    items = registry.load(reg)
    assert len(items) == 1
    assert items[0]["label"] == "B"


def test_add_non_backup_raises(tmp_path):
    reg = str(tmp_path / "registry.json")
    bad = tmp_path / "bad"
    bad.mkdir()
    with pytest.raises(ValueError):
        registry.add(reg, str(bad))


def test_remove(tmp_path):
    reg = str(tmp_path / "registry.json")
    bk = _make_backup(tmp_path)
    registry.add(reg, str(bk))
    assert registry.remove(reg, str(bk)) is True
    assert registry.load(reg) == []
    assert registry.remove(reg, str(bk)) is False


def test_registry_path_env(tmp_path, monkeypatch):
    monkeypatch.setenv("IOS_BACKUP_VAULT_HOME", str(tmp_path))
    assert registry.registry_path() == str(tmp_path / "registry.json")
