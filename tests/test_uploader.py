from ios_backup_vault.uploader import upload_backup


class FakeStore:
    def __init__(self): self.objs = {}
    def put_from_file(self, rel, f): self.objs[rel] = f.read()
    def head(self, rel):
        d = self.objs.get(rel); return {"size": len(d), "generation": 1} if d is not None else None


def _mk(tmp):
    bk = tmp / "UDID"; (bk / "ab").mkdir(parents=True)
    (bk / "Manifest.plist").write_bytes(b"mp"); (bk / "Status.plist").write_bytes(b"sp")
    (bk / "ab" / ("ab"+"0"*38)).write_bytes(b"blob")
    return bk


def test_mirror_parallel(tmp_path):
    bk = _mk(tmp_path); s = FakeStore()
    n = upload_backup(str(bk), udid="UDID", store=s, workers=4)
    assert n == 3 and set(s.objs) == {"UDID/Manifest.plist", "UDID/Status.plist", "UDID/ab/ab"+"0"*38}


def test_skip_by_size(tmp_path):
    bk = _mk(tmp_path); s = FakeStore(); s.objs["UDID/Status.plist"] = b"sp"  # 동일 크기 존재
    logs = []
    upload_backup(str(bk), udid="UDID", store=s, on_file=lambda r, st: logs.append((r, st)))
    assert ("Status.plist", "skip") in logs and ("Manifest.plist", "put") in logs


def test_delete_local_only_after_integrity(tmp_path):
    bk = _mk(tmp_path); s = FakeStore()
    upload_backup(str(bk), udid="UDID", store=s, delete_local=True)
    assert not bk.exists()


def test_delete_local_blocked_on_mismatch(tmp_path, monkeypatch):
    bk = _mk(tmp_path); s = FakeStore()
    # head가 잘린 크기를 보고하도록 → 무결성 실패 → 삭제 안 함
    real_head = s.head
    monkeypatch.setattr(s, "head", lambda rel: {"size": 1, "generation": 1} if real_head(rel) else None)
    import pytest
    with pytest.raises(RuntimeError):
        upload_backup(str(bk), udid="UDID", store=s, delete_local=True)
    assert bk.exists()   # 보존
