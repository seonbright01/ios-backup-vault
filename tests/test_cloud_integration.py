import os, pytest
from ios_backup_vault.cloud_backend import CloudBackend
from ios_backup_vault.vault import Vault

REAL = os.environ.get("VAULT_TEST_BACKUP", "")   # 실백업 경로(환경변수, 미설정 시 skip)


class DirStore:
    """로컬 백업 디렉터리를 객체 저장소처럼 노출(udid/rel)."""
    def __init__(self, root, udid): self.root = root; self.udid = udid
    def _p(self, rel):
        assert rel.startswith(self.udid + "/")
        return os.path.join(self.root, rel[len(self.udid) + 1:])
    def get(self, rel, **k):
        p = self._p(rel)
        return open(p, "rb").read() if os.path.exists(p) else None
    def head(self, rel):
        p = self._p(rel)
        return {"size": os.path.getsize(p), "generation": 1} if os.path.exists(p) else None


@pytest.mark.skipif(not REAL or not os.path.isdir(REAL), reason="VAULT_TEST_BACKUP 미설정/없음")
def test_real_crypto_via_cloud_backend(tmp_path):
    pw = os.environ.get("VAULT_TEST_PASSPHRASE")
    if not pw: pytest.skip("VAULT_TEST_PASSPHRASE 미설정")

    def inner_factory(cdir):
        from iphone_backup_decrypt import EncryptedBackup
        return EncryptedBackup(backup_directory=cdir, passphrase=pw)

    udid = os.path.basename(REAL.rstrip("/"))
    be = CloudBackend(store=DirStore(REAL, udid), udid=udid,
                      cache_dir=str(tmp_path), inner_factory=inner_factory)
    v = Vault(backend=be)
    try:
        v.open()                                  # 실제 복호화 성공해야
        rows = v.find_files(path_like="%sms.db")  # Manifest.db 쿼리(실데이터)
        assert rows
        data = v.read_bytes(rows[0][2])           # 온디맨드 fetch+복호화
        assert data and data[:15] == b"SQLite format 3"   # 실제 평문 SQLite 헤더
    finally:
        v.close()                                 # 소유 스레드에서 SQLite 연결 정리
