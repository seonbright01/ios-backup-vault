import sqlite3
import pytest
from ios_backup_vault.vault import VaultError
from ios_backup_vault.viewer_data import ViewerData


class BadParseVault:
    def read_bytes(self, rel, *, domain_like=None): return b"not a sqlite db"
    def manifest_files(self, domain=None): return []


def test_parse_error_raises_vaulterror():
    from ios_backup_vault.viewer_data import ViewerData
    vd = ViewerData(BadParseVault())
    with pytest.raises(VaultError):
        vd.messages()


class FakeVault:
    def read_bytes(self, rel, *, domain_like=None): return None
    def manifest_files(self, domain=None): return []


def test_viewer_data_summary_handles_empty():
    vd = ViewerData(FakeVault())
    s = vd.summary()
    assert set(s.keys()) == {"messages", "contacts", "calls", "media"}
    assert s["media"] == 0
    assert vd.messages() == [] and vd.media() == []
