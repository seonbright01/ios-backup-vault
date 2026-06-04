"""provider-중립 객체 저장소. 네트워크는 주입 client로 위임(테스트=fake, 실사용=GcsClient)."""
from __future__ import annotations


def _safe(rel: str) -> str:
    rel = rel.lstrip("/")
    parts = rel.split("/")
    if any(p in ("", "..", ".") for p in parts):
        raise ValueError(f"잘못된/순회 키: {rel!r}")
    return rel


class ObjectStore:
    def __init__(self, *, bucket: str, prefix: str = "", client=None):
        if client is None:
            raise ValueError("client 필요")
        self._bucket = bucket
        self._prefix = prefix.strip("/")
        self._c = client

    def _key(self, rel: str) -> str:
        rel = _safe(rel)
        return f"{self._prefix}/{rel}" if self._prefix else rel

    def get(self, rel, *, start=None, length=None):
        key = self._key(rel)
        try:
            if start is not None:
                return self._c.download_range(key, start, start + (length or 0))
            return self._c.download(key)
        except KeyError:
            return None

    def get_to_file(self, rel, fobj):
        self._c.download_to_file(self._key(rel), fobj)

    def download_to_file(self, rel, fobj):
        self._c.download_to_file(self._key(rel), fobj)

    def put(self, rel, data):
        self._c.upload(self._key(rel), data)

    def put_from_file(self, rel, fobj):
        self._c.upload_from_file(self._key(rel), fobj)

    def exists(self, rel):
        return self._c.exists(self._key(rel))

    def head(self, rel):
        return self._c.head(self._key(rel))

    def delete(self, rel):
        self._c.delete(self._key(rel))

    def _strip(self, keys):
        n = len(self._prefix) + 1 if self._prefix else 0
        return sorted(k[n:] for k in keys)

    def list(self, rel_prefix=""):
        full = self._key(rel_prefix) if rel_prefix else (self._prefix or "")
        return self._strip(self._c.list(full))

    def list_udids(self):
        base = (self._prefix + "/") if self._prefix else ""
        dirs = self._c.list_dirs(base)
        n = len(self._prefix) + 1 if self._prefix else 0
        return sorted(d[n:].rstrip("/") for d in dirs)


class GcsClient:
    """google-cloud-storage 어댑터(지연 import). 자격증명은 secrets.resolve_credentials()."""
    def __init__(self, bucket, *, credentials=None):
        try:
            from google.cloud import storage
        except ImportError as e:
            raise RuntimeError("GCS 기능은 'pip install ios-backup-vault[gcs]' 필요") from e
        self._client = (storage.Client(credentials=credentials) if credentials
                        else storage.Client())  # credentials=None → ADC
        self._bucket = self._client.bucket(bucket)

    def _b(self, key): return self._bucket.blob(key)

    def download(self, key):
        from google.cloud.exceptions import NotFound
        try: return self._b(key).download_as_bytes()
        except NotFound as e: raise KeyError(key) from e

    def download_range(self, key, start, end):
        return self._b(key).download_as_bytes(start=start, end=end - 1)

    def download_to_file(self, key, fobj):
        self._b(key).download_to_file(fobj)

    def upload(self, key, data):
        self._b(key).upload_from_string(bytes(data))

    def upload_from_file(self, key, fobj):
        self._b(key).upload_from_file(fobj)

    def exists(self, key):
        return self._b(key).exists()

    def head(self, key):
        b = self._b(key)
        if not b.exists(): return None
        b.reload()
        return {"size": b.size, "generation": b.generation}

    def list(self, prefix):
        return [b.name for b in self._client.list_blobs(self._bucket, prefix=prefix)]

    def list_dirs(self, prefix):
        it = self._client.list_blobs(self._bucket, prefix=prefix, delimiter="/")
        list(it)  # prefixes 채우려면 소비 필요
        return sorted(it.prefixes)

    def delete(self, key):
        from google.cloud.exceptions import NotFound
        try: self._b(key).delete()
        except NotFound: pass
