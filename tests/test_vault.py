import pytest
from ios_backup_vault.vault import Vault, VaultError


class FakeBackend:
    def __init__(self, *, ok=True, blobs=None):
        self._ok = ok
        self._blobs = blobs or {}
        self.tested = False

    def test_decryption(self):
        self.tested = True
        if not self._ok:
            raise ValueError("bad password")

    def extract_file(self, *, relative_path, domain_like=None, output_filename):
        if relative_path in self._blobs:
            with open(output_filename, "wb") as f:
                f.write(self._blobs[relative_path])
            return
        raise FileNotFoundError(relative_path)


def test_open_validates_password_ok():
    be = FakeBackend(ok=True)
    Vault(backend=be).open()
    assert be.tested is True


def test_open_wrong_password_raises_vaulterror():
    with pytest.raises(VaultError):
        Vault(backend=FakeBackend(ok=False)).open()


def test_read_bytes_delegates():
    v = Vault(backend=FakeBackend(blobs={"Library/SMS/sms.db": b"DATA"}))
    assert v.read_bytes("Library/SMS/sms.db") == b"DATA"


def test_read_bytes_missing_returns_none():
    assert Vault(backend=FakeBackend(blobs={})).read_bytes("nope") is None


def test_read_bytes_decrypt_error_raises_vaulterror():
    class BoomBackend:
        def test_decryption(self): pass
        def extract_file(self, *, relative_path, domain_like=None, output_filename):
            raise ValueError("decrypt boom")
    with pytest.raises(VaultError):
        Vault(backend=BoomBackend()).read_bytes("X")
