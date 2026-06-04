"""블롭 LRU 캐시: O(1) 회계, 콜드스타트 인덱스 로드, 원자적 쓰기, 손상검출, 0600 권한."""
import collections
import os
import tempfile
import threading


class BlobCache:
    def __init__(self, cache_dir, cap_bytes, *, protected=None):
        self._dir = str(cache_dir)
        self._cap = cap_bytes
        self._protected = set(protected or ())
        os.makedirs(self._dir, mode=0o700, exist_ok=True)
        try: os.chmod(self._dir, 0o700)
        except OSError: pass
        self._order = collections.OrderedDict()  # LRU: 앞=오래됨
        self._bytes = 0
        self._lock = threading.Lock()
        self._load_index()

    def _path(self, key): return os.path.join(self._dir, key)

    def _load_index(self):
        entries = []
        for root, _d, files in os.walk(self._dir):
            for name in files:
                fp = os.path.join(root, name)
                if name.endswith(".tmp"):
                    try: os.unlink(fp)   # 중단된 쓰기의 잔재 정리
                    except OSError: pass
                    continue
                key = os.path.relpath(fp, self._dir)
                try: entries.append((os.path.getmtime(fp), os.path.getsize(fp), key))
                except OSError: pass
        entries.sort()
        for _m, sz, key in entries:
            self._order[key] = None; self._bytes += sz

    def _touch(self, key):
        if key in self._order: self._order.move_to_end(key)
        else: self._order[key] = None

    def _drop(self, key):
        p = self._path(key)
        try: self._bytes -= os.path.getsize(p)
        except OSError: pass
        try: os.unlink(p)
        except OSError: pass
        self._order.pop(key, None)

    def _evict(self):
        while self._bytes > self._cap:
            victim = next((k for k in self._order if k not in self._protected), None)
            if victim is None: break
            self._drop(victim)

    def ensure(self, key, fetch_fn, *, expected_size=None):
        p = self._path(key)
        with self._lock:
            if os.path.exists(p):
                if expected_size is not None and os.path.getsize(p) != expected_size:
                    self._drop(key)          # 손상/잘림 → 폐기 후 재 fetch
                else:
                    self._touch(key); return p
            data = fetch_fn()
            if expected_size is not None and len(data) != expected_size:
                raise ValueError(f"fetch 크기 불일치: {key}")
            os.makedirs(os.path.dirname(p) or self._dir, mode=0o700, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self._dir, suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as f:
                    os.fchmod(f.fileno(), 0o600); f.write(data)
                os.replace(tmp, p)           # 원자적 배치
            except BaseException:
                try: os.unlink(tmp)          # 쓰기/배치 실패 시 temp 정리
                except OSError: pass
                raise
            self._bytes += len(data); self._touch(key); self._evict()
            return p

    def size(self): return self._bytes

    def clear(self):
        with self._lock:
            for key in list(self._order):
                if key not in self._protected: self._drop(key)   # protected 보존
            self._bytes = 0
            for key in self._order:                              # 남은 protected 크기 재계산
                try: self._bytes += os.path.getsize(self._path(key))
                except OSError: pass
