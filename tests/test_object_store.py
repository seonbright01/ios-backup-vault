import io, pytest
from ios_backup_vault.object_store import ObjectStore


class FakeClient:
    def __init__(self): self.objs = {}
    def upload(self, k, d): self.objs[k] = bytes(d)
    def upload_from_file(self, k, f): self.objs[k] = f.read()
    def download(self, k):
        if k not in self.objs: raise KeyError(k)
        return self.objs[k]
    def download_range(self, k, s, e): return self.objs[k][s:e]
    def download_to_file(self, k, f): f.write(self.objs[k])
    def exists(self, k): return k in self.objs
    def head(self, k): return {"size": len(self.objs[k]), "generation": 1} if k in self.objs else None
    def list(self, p): return sorted(x for x in self.objs if x.startswith(p))
    def list_dirs(self, p):
        out = set()
        for x in self.objs:
            if x.startswith(p):
                rest = x[len(p):].split("/")[0]
                out.add(p + rest + "/")
        return sorted(out)
    def delete(self, k): self.objs.pop(k, None)


def _s(): return ObjectStore(bucket="b", prefix="vault", client=FakeClient())


def test_roundtrip_and_head():
    s = _s(); s.put("UDID/Status.plist", b"hi")
    assert s.get("UDID/Status.plist") == b"hi"
    assert s.head("UDID/Status.plist")["size"] == 2


def test_get_missing_none():
    assert _s().get("nope") is None


def test_range():
    s = _s(); s.put("k", b"0123456789")
    assert s.get("k", start=2, length=3) == b"234"


def test_path_traversal_blocked():
    s = _s()
    with pytest.raises(ValueError):
        s.put("../escape", b"x")
    with pytest.raises(ValueError):
        s.get("a/../../b")


def test_list_udids_uses_delimiter():
    s = _s()
    for k in ["A/Status.plist", "A/00/f", "B/Status.plist"]:
        s.put(k, b"x")
    assert s.list_udids() == ["A", "B"]


def test_download_to_file(tmp_path):
    s = _s(); s.put("k", b"DATA")
    p = tmp_path / "o"
    with open(p, "wb") as f: s.download_to_file("k", f)
    assert p.read_bytes() == b"DATA"


def test_gcs_client_interface():
    from ios_backup_vault.object_store import GcsClient
    for m in ("download","download_range","download_to_file","upload",
              "upload_from_file","exists","head","list","list_dirs","delete"):
        assert hasattr(GcsClient, m)
