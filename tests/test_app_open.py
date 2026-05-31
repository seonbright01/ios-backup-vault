"""P9 Task1: app 골격 — pick-folder + scan-path/scan-folder + open/close + 활성 게이팅.

folder_picker / vault_factory 모킹. 열린 백업 없을 때 뷰어 엔드포인트 409.
"""
import json

from fastapi.testclient import TestClient

from ios_backup_vault.app import create_app


class FakeVault:
    def __init__(self, *, ok=True):
        self._ok = ok
        self.closed = False

    def open(self):
        if not self._ok:
            from ios_backup_vault.vault import VaultError
            raise VaultError("백업 복호화 실패 — 비밀번호가 틀렸거나 백업이 손상되었을 수 있습니다.")

    def close(self):
        self.closed = True


def _meta(path, *, with_size=True, reveal_pii=False):
    return {
        "path": path, "udid": "UDID1", "device_name": "iPhone <X>",
        "product_type": "iPhone14,2", "ios_version": "17.2", "build": "21C62",
        "imaged_at": "2026-05-30T12:00:00", "snapshot_date": "2026-05-30T11:00:00",
        "last_backup_date": "2026-05-30T12:00:00", "is_encrypted": True, "is_full": True,
        "snapshot_state": "finished", "backup_state": "new", "app_count": 2,
        "size_bytes": 123 if with_size else None,
        "serial": "ABCD" if reveal_pii else "••••", "imei": "", "iccid": "", "phone": "",
    }


def _reg(tmp_path, path="/x/UDID1"):
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps({"backups": [{"path": path, "label": "L", "added_at": "t"}]}),
                   encoding="utf-8")
    return str(reg)


def _id_of(path):
    import hashlib
    return hashlib.sha1(str(path).encode()).hexdigest()[:12]


def test_pick_folder_returns_path(tmp_path):
    reg = _reg(tmp_path)
    app = create_app(reg, folder_picker=lambda: "/picked/folder", metadata_fn=_meta)
    client = TestClient(app)
    r = client.post("/api/imaging/pick-folder")
    assert r.status_code == 200
    assert r.json()["path"] == "/picked/folder"


def test_pick_folder_cancel(tmp_path):
    reg = _reg(tmp_path)
    app = create_app(reg, folder_picker=lambda: None, metadata_fn=_meta)
    client = TestClient(app)
    r = client.post("/api/imaging/pick-folder")
    assert "error" in r.json()


def test_viewer_endpoint_409_when_no_open(tmp_path):
    reg = _reg(tmp_path)
    app = create_app(reg, metadata_fn=_meta)
    client = TestClient(app)
    bid = _id_of("/x/UDID1")
    r = client.get(f"/api/backups/{bid}/summary")
    assert r.status_code == 409
    assert r.json()["error"] == "열린 백업이 없습니다"


def test_open_success_then_summary(tmp_path):
    reg = _reg(tmp_path)
    fake = FakeVault(ok=True)

    class FakeViewer:
        def __init__(self, v):
            self._v = v

        def summary(self):
            return {"messages": 3}

    app = create_app(
        reg,
        vault_factory=lambda path, passphrase: fake,
        viewer_factory=lambda v: FakeViewer(v),
        metadata_fn=_meta,
    )
    client = TestClient(app)
    bid = _id_of("/x/UDID1")
    r = client.post(f"/api/backups/{bid}/open", json={"passphrase": "pw"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    s = client.get(f"/api/backups/{bid}/summary")
    assert s.status_code == 200
    assert s.json()["messages"] == 3


def test_open_failure_returns_error(tmp_path):
    reg = _reg(tmp_path)
    fake = FakeVault(ok=False)
    app = create_app(reg, vault_factory=lambda path, passphrase: fake, metadata_fn=_meta)
    client = TestClient(app)
    bid = _id_of("/x/UDID1")
    r = client.post(f"/api/backups/{bid}/open", json={"passphrase": "bad"})
    assert "error" in r.json()
    assert "ok" not in r.json() or r.json().get("ok") is not True


def test_open_unregistered_id_404(tmp_path):
    reg = _reg(tmp_path)
    app = create_app(reg, vault_factory=lambda path, passphrase: FakeVault(), metadata_fn=_meta)
    client = TestClient(app)
    r = client.post("/api/backups/deadbeef0000/open", json={"passphrase": "pw"})
    assert r.status_code == 404


def test_close_releases_active(tmp_path):
    reg = _reg(tmp_path)
    fake = FakeVault(ok=True)

    class FakeViewer:
        def __init__(self, v):
            self._v = v

        def summary(self):
            return {"messages": 1}

    app = create_app(reg, vault_factory=lambda path, passphrase: fake,
                     viewer_factory=lambda v: FakeViewer(v), metadata_fn=_meta)
    client = TestClient(app)
    bid = _id_of("/x/UDID1")
    client.post(f"/api/backups/{bid}/open", json={"passphrase": "pw"})
    assert client.get(f"/api/backups/{bid}/summary").status_code == 200
    r = client.post(f"/api/backups/{bid}/close")
    assert r.status_code == 200
    assert client.get(f"/api/backups/{bid}/summary").status_code == 409
    assert fake.closed is True


def test_scan_path_registers(tmp_path):
    reg = _reg(tmp_path, path="/x/UDID1")
    added = {}

    def fake_add(reg_path, path, label="", now_iso=""):
        added["path"] = path
        return {"path": path, "label": label}

    app = create_app(reg, add_fn=fake_add, metadata_fn=_meta)
    client = TestClient(app)
    r = client.post("/api/backups/scan-path", json={"path": "/new/UDID2"})
    assert r.status_code == 200
    assert added["path"] == "/new/UDID2"


def test_scan_folder_uses_picker(tmp_path):
    reg = _reg(tmp_path)
    added = {}

    def fake_add(reg_path, path, label="", now_iso=""):
        added["path"] = path
        return {"path": path, "label": label}

    app = create_app(reg, folder_picker=lambda: "/picked/UDID3",
                     add_fn=fake_add, metadata_fn=_meta)
    client = TestClient(app)
    r = client.post("/api/backups/scan-folder")
    assert r.status_code == 200
    assert added["path"] == "/picked/UDID3"
