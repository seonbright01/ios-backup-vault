"""GCS 백업을 EncryptedBackup 호환 backend로. 메타 우선 + fetch-on-miss(이중 SQL 제거)."""
import os

_REQUIRED_META = ("Manifest.plist", "Manifest.db")   # 라이브러리 필수
_LAZY_META = ("Info.plist", "Status.plist")           # 표시용
# 출처: iphone_backup_decrypt _file_metadata_from_manifest — 라이브러리와 동일하게 유지할 것
_RESOLVE_SQL = ("SELECT fileID FROM Files WHERE relativePath = ? "
                "AND domain LIKE ? AND flags=1 ORDER BY domain, relativePath LIMIT 1")


def _is_file_id(fid):
    return isinstance(fid, str) and len(fid) == 40 and all(c in "0123456789abcdef" for c in fid)


class CloudBackend:
    def __init__(self, *, store, udid, cache_dir, inner_factory, blob_cache=None):
        self._store = store; self._udid = udid; self._dir = cache_dir
        self._inner_factory = inner_factory; self._cache = blob_cache
        self._inner = None
        if blob_cache is not None and \
                os.path.realpath(blob_cache._dir) != os.path.realpath(cache_dir):
            raise ValueError("blob_cache 루트가 cache_dir과 달라 라이브러리가 블롭을 찾지 못합니다")
        os.makedirs(cache_dir, mode=0o700, exist_ok=True)

    def _obj(self, rel): return f"{self._udid}/{rel}"

    def _ensure_meta(self, names):
        for name in names:
            local = os.path.join(self._dir, name)
            gen_file = local + ".gen"
            head = self._store.head(self._obj(name))
            if head is None:
                raise FileNotFoundError(f"GCS에 {name} 없음")
            cur_gen = str(head["generation"])
            if os.path.exists(local):
                old = open(gen_file).read() if os.path.exists(gen_file) else None
                if old == cur_gen:
                    continue                  # 최신 → 재사용
            data = self._store.get(self._obj(name))
            if data is None:
                raise FileNotFoundError(f"GCS에 {name} 없음")
            fd = os.open(local, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            gfd = os.open(gen_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(gfd, "w") as f:
                f.write(cur_gen)

    def _ensure_inner(self):
        if self._inner is None:
            self._ensure_meta(_REQUIRED_META)
            self._inner = self._inner_factory(self._dir)
        return self._inner

    def _resolve(self, rel, domain_like):
        with self._ensure_inner().manifest_db_cursor() as cur:
            row = cur.execute(_RESOLVE_SQL, (rel, domain_like or "%")).fetchone()
        return row[0] if row else None

    def fetch_blob(self, fid):
        """executor 밖에서 호출(네트워크). 캐시/디스크에 블롭 확보."""
        if not _is_file_id(fid):
            raise ValueError(f"비정상 file_id: {fid!r}")
        local = os.path.join(self._dir, fid[:2], fid)
        if not os.path.realpath(local).startswith(os.path.realpath(self._dir)):
            raise ValueError("캐시 경계 위반")
        obj = self._obj(f"{fid[:2]}/{fid}")
        if self._cache is not None:
            # 디스크 존재와 무관하게 ensure로 위임(존재 시 LRU touch+손상검증, 부재 시 fetch)
            head = self._store.head(obj)
            exp = head["size"] if head else None
            return self._cache.ensure(f"{fid[:2]}/{fid}",
                                      lambda: self._store.get(obj), expected_size=exp)
        if os.path.exists(local):
            return local
        data = self._store.get(obj)
        if data is None:
            raise FileNotFoundError(obj)
        os.makedirs(os.path.dirname(local), mode=0o700, exist_ok=True)
        fd = os.open(local, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        return local

    # --- EncryptedBackup 호환 ---
    def test_decryption(self):
        return self._ensure_inner().test_decryption()

    def manifest_db_cursor(self):
        return self._ensure_inner().manifest_db_cursor()

    def extract_file(self, *, relative_path, domain_like=None, output_filename):
        inner = self._ensure_inner()
        try:
            return inner.extract_file(relative_path=relative_path,
                                      domain_like=domain_like, output_filename=output_filename)
        except FileNotFoundError:
            fid = self._resolve(relative_path, domain_like)   # 라이브러리 동일 SQL
            if not fid:
                raise
            self.fetch_blob(fid)                              # 누락 블롭 확보
            return inner.extract_file(relative_path=relative_path,
                                      domain_like=domain_like, output_filename=output_filename)

    def ensure_lazy_meta(self):
        self._ensure_meta(_LAZY_META)

    def close(self, purge_meta=True):
        if purge_meta:
            for name in _REQUIRED_META + _LAZY_META:
                for p in (os.path.join(self._dir, name), os.path.join(self._dir, name + ".gen")):
                    try: os.unlink(p)
                    except OSError: pass
