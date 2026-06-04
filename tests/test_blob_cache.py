import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from ios_backup_vault.blob_cache import BlobCache


def test_ensure_once_and_o1_size(tmp_path):
    c = BlobCache(tmp_path, cap_bytes=1000)
    calls = []
    p1 = c.ensure("ab/f1", lambda: (calls.append(1) or b"DATA"))
    p2 = c.ensure("ab/f1", lambda: (calls.append(1) or b"DATA"))
    assert p1 == p2 and open(p1, "rb").read() == b"DATA"
    assert len(calls) == 1
    assert c.size() == 4


def test_lru_eviction(tmp_path):
    c = BlobCache(tmp_path, cap_bytes=10)
    c.ensure("a", lambda: b"12345"); c.ensure("b", lambda: b"12345")
    c.ensure("c", lambda: b"12345")
    assert c.size() <= 10 and not (tmp_path / "a").exists() and (tmp_path / "c").exists()


def test_cold_start_loads_index(tmp_path):
    c1 = BlobCache(tmp_path, cap_bytes=10)
    c1.ensure("a", lambda: b"12345"); c1.ensure("b", lambda: b"12345")
    c2 = BlobCache(tmp_path, cap_bytes=10)   # 재시작 시뮬
    assert c2.size() == 10                    # 기존 파일 회계 복구
    c2.ensure("c", lambda: b"12345")          # 초과 → 퇴출 동작해야
    assert c2.size() <= 10


def test_corruption_size_mismatch_refetched(tmp_path):
    c = BlobCache(tmp_path, cap_bytes=1000)
    (tmp_path / "x").write_bytes(b"TRUNC")   # 잘린 캐시
    got = c.ensure("x", lambda: b"FULLDATA", expected_size=8)
    assert open(got, "rb").read() == b"FULLDATA"  # 손상분 폐기 후 재 fetch


def test_perms_restrictive(tmp_path):
    c = BlobCache(tmp_path, cap_bytes=1000)
    p = c.ensure("a", lambda: b"x")
    assert (os.stat(p).st_mode & 0o077) == 0   # group/other 권한 없음


def test_clear(tmp_path):
    c = BlobCache(tmp_path, cap_bytes=1000)
    c.ensure("a", lambda: b"x")
    c.clear(); assert c.size() == 0


def test_clear_preserves_protected(tmp_path):
    c = BlobCache(tmp_path, cap_bytes=1000, protected={"meta"})
    c.ensure("meta", lambda: b"METADATA")   # protected, 8바이트
    c.ensure("blob", lambda: b"x")          # 일반
    c.clear()
    assert (tmp_path / "meta").exists()     # protected 보존
    assert not (tmp_path / "blob").exists() # 일반 제거
    assert c.size() == 8                     # 보존된 protected 크기와 일치


def test_temp_cleanup_on_fetch_error(tmp_path):
    c = BlobCache(tmp_path, cap_bytes=1000)

    def boom():
        raise RuntimeError("network down")

    before = c.size()
    with pytest.raises(RuntimeError):
        c.ensure("a", boom)
    tmps = [n for _r, _d, fs in os.walk(str(tmp_path)) for n in fs if n.endswith(".tmp")]
    assert tmps == []          # .tmp 잔재 없음
    assert c.size() == before  # 회계 불변


def test_concurrent_ensure_size_consistent(tmp_path):
    c = BlobCache(tmp_path, cap_bytes=1_000_000)
    data = b"PAYLOAD-1234567890"

    def work(_):
        return c.ensure("k", lambda: data)

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(work, range(8)))
    assert c.size() == len(data)  # 이중가산 없음
