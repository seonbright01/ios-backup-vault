import contextlib, os
import pytest
from ios_backup_vault.blob_cache import BlobCache
from ios_backup_vault.cloud_backend import CloudBackend


class FakeStore:
    def __init__(self, objs): self.objs = objs; self.gets = []
    def get(self, rel, **k): self.gets.append(rel); return self.objs.get(rel)
    def head(self, rel):
        d = self.objs.get(rel); return {"size": len(d), "generation": 1} if d else None


class FakeInner:
    """캐시에 블롭 있으면 복호화 성공, 없으면 라이브러리처럼 FileNotFoundError."""
    def __init__(self, cdir): self.cdir = cdir
    def test_decryption(self): pass
    @contextlib.contextmanager
    def manifest_db_cursor(self):
        class C:
            def execute(self, sql, p=()):
                assert "flags=1" in sql        # 라이브러리 동일 쿼리 보장
                self._r = ("a1b2"+"0"*36,); return self
            def fetchone(self): return self._r
            def fetchall(self): return [(self._r[0], "Dom", "Library/SMS/sms.db")]
        yield C()
    def extract_file(self, *, relative_path, domain_like=None, output_filename):
        fid = "a1b2"+"0"*36
        blob = os.path.join(self.cdir, fid[:2], fid)
        if not os.path.exists(blob):
            raise FileNotFoundError(blob)
        with open(output_filename, "wb") as f: f.write(b"PLAIN")


def _be(tmp_path):
    fid = "a1b2"+"0"*36
    objs = {"UDID/Manifest.plist": b"mp", "UDID/Manifest.db": b"mdb",
            f"UDID/{fid[:2]}/{fid}": b"<cipher>"}
    store = FakeStore(objs)
    return CloudBackend(store=store, udid="UDID", cache_dir=str(tmp_path),
                        inner_factory=FakeInner), store


def test_open_fetches_only_required_meta(tmp_path):
    be, store = _be(tmp_path); be.test_decryption()
    assert set(store.gets) == {"UDID/Manifest.plist", "UDID/Manifest.db"}  # 블롭·Info·Status 미포함


def test_fetch_on_miss(tmp_path):
    be, store = _be(tmp_path); be.test_decryption()
    out = str(tmp_path / "o")
    be.extract_file(relative_path="Library/SMS/sms.db", output_filename=out)
    fid = "a1b2"+"0"*36
    assert f"UDID/{fid[:2]}/{fid}" in store.gets and open(out, "rb").read() == b"PLAIN"


def test_bad_file_id_rejected(tmp_path):
    be, _ = _be(tmp_path); be.test_decryption()
    import pytest
    with pytest.raises(ValueError):
        be.fetch_blob("../evil")


def test_blob_cache_root_must_match_cache_dir(tmp_path):
    cache_dir = str(tmp_path / "cache")
    os.makedirs(cache_dir, exist_ok=True)
    store = FakeStore({})
    other = BlobCache(str(tmp_path / "other"), 1 << 20)
    with pytest.raises(ValueError):
        CloudBackend(store=store, udid="UDID", cache_dir=cache_dir,
                     inner_factory=FakeInner, blob_cache=other)
    same = BlobCache(cache_dir, 1 << 20)
    be = CloudBackend(store=store, udid="UDID", cache_dir=cache_dir,
                      inner_factory=FakeInner, blob_cache=same)
    assert be is not None


def test_missing_required_meta_raises(tmp_path):
    # Manifest.db가 GCS에 없음(head=None) → 캐시 최신 오판 금지, FileNotFoundError
    objs = {"UDID/Manifest.plist": b"mp"}   # Manifest.db 누락
    store = FakeStore(objs)
    be = CloudBackend(store=store, udid="UDID", cache_dir=str(tmp_path),
                      inner_factory=FakeInner)
    with pytest.raises(FileNotFoundError):
        be.test_decryption()


def test_stale_cache_with_missing_head_raises(tmp_path):
    # 캐시 파일은 있으나 GCS에 메타가 없음(head=None): old==cur_gen==None 오판 금지
    cache_dir = str(tmp_path)
    for name in ("Manifest.plist", "Manifest.db"):
        with open(os.path.join(cache_dir, name), "wb") as f:
            f.write(b"stale")   # .gen 사이드카는 없음 → old=None
    store = FakeStore({})       # 모든 head=None
    be = CloudBackend(store=store, udid="UDID", cache_dir=cache_dir,
                      inner_factory=FakeInner)
    with pytest.raises(FileNotFoundError):
        be.test_decryption()


def test_fetch_blob_disk_hit_touches_lru(tmp_path):
    # blob_cache 주입 시 디스크 히트도 cache.ensure로 위임 → LRU touch.
    # 자주 쓴 fid가 cap 근처 적재로 퇴출되지 않아야 함(디스크 히트 조기반환 버그 회귀).
    cache_dir = str(tmp_path)
    hot = "a1b2" + "0" * 36                     # 자주 쓰는 블롭
    cold = "c3d4" + "0" * 36                     # 채움용 블롭
    objs = {f"UDID/{hot[:2]}/{hot}": b"12345",   # 5바이트
            f"UDID/{cold[:2]}/{cold}": b"12345"}
    store = FakeStore(objs)
    cache = BlobCache(cache_dir, cap_bytes=10)   # 2개 블롭만 수용
    be = CloudBackend(store=store, udid="UDID", cache_dir=cache_dir,
                      inner_factory=FakeInner, blob_cache=cache)
    be.fetch_blob(hot)                            # hot 적재(디스크+캐시)
    be.fetch_blob(cold)                           # cold 적재(cap 도달)
    be.fetch_blob(hot)                            # 디스크 히트 → ensure 위임 시 hot이 말단으로 touch
    # 새 키 적재로 퇴출 유발: hot이 touch됐으면 cold가 퇴출돼야(hot 생존)
    objs[f"UDID/aa/{'aa' + '0' * 38}"] = b"12345"
    be.fetch_blob("aa" + "0" * 38)
    hot_path = os.path.join(cache_dir, hot[:2], hot)
    cold_path = os.path.join(cache_dir, cold[:2], cold)
    assert os.path.exists(hot_path)               # 자주 쓴 hot 생존
    assert not os.path.exists(cold_path)          # 가장 오래된 cold 퇴출


def test_gen_sidecar_written_when_head_present(tmp_path):
    # head 정상이면 .gen 항상 기록(매번 재다운로드되는 문제 방지) + 0600
    be, store = _be(tmp_path); be.test_decryption()
    gen_file = os.path.join(str(tmp_path), "Manifest.db.gen")
    assert os.path.exists(gen_file)
    assert open(gen_file).read() == "1"
    assert (os.stat(gen_file).st_mode & 0o777) == 0o600
    # 두 번째 inner 생성 경로(캐시 재사용)에서는 재다운로드 없어야 함
    before = list(store.gets)
    be2 = CloudBackend(store=store, udid="UDID", cache_dir=str(tmp_path),
                       inner_factory=FakeInner)
    be2.test_decryption()
    assert store.gets == before   # .gen 매칭으로 재사용 → 추가 get 없음
