"""P10 Task10: 앱/대시보드 클라우드 카드·캐시 UI·스트리밍 미디어 — 엔드포인트 스모크.

프론트 JS는 단위테스트 비대상(T12 E2E). 가짜 cloud_store_factory 주입으로
신규 엔드포인트만 스모크 검증. 기존 app_* 테스트는 무회귀.
"""
import json

from fastapi.testclient import TestClient

from ios_backup_vault.app import create_app


class FakeCloudStore:
    """list_udids + get(udid/Status.plist 등) 만 제공하는 최소 가짜 store."""

    def __init__(self, udids):
        self._udids = list(udids)
        self.objs = {}

    def list_udids(self):
        return sorted(self._udids)

    def get(self, rel, **k):
        return self.objs.get(rel)

    def head(self, rel):
        d = self.objs.get(rel)
        return {"size": len(d), "generation": 1} if d is not None else None


def _meta(path, *, with_size=True, reveal_pii=False):
    return {"path": path, "device_name": "iPhone", "id": "x", "udid": "U",
            "product_type": "", "ios_version": "", "build": "", "imaged_at": "",
            "snapshot_date": "", "last_backup_date": "", "is_encrypted": False,
            "is_full": False, "snapshot_state": "", "backup_state": "", "app_count": 0,
            "size_bytes": None, "serial": "", "imei": "", "iccid": "", "phone": ""}


def _reg(tmp_path):
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps({"backups": []}), encoding="utf-8")
    return str(reg)


def test_cloud_backups_lists_udids(tmp_path, monkeypatch):
    monkeypatch.setenv("IOS_BACKUP_VAULT_HOME", str(tmp_path / "home"))
    store = FakeCloudStore(["UDID-A", "UDID-B"])
    app = create_app(_reg(tmp_path), metadata_fn=_meta,
                     cloud_store_factory=lambda: store)
    client = TestClient(app)
    r = client.get("/api/cloud/backups")
    assert r.status_code == 200
    body = r.json()
    udids = {c["udid"] for c in body}
    assert udids == {"UDID-A", "UDID-B"}


def test_cloud_backups_offline_reports_error(tmp_path, monkeypatch):
    monkeypatch.setenv("IOS_BACKUP_VAULT_HOME", str(tmp_path / "home"))

    def boom():
        raise RuntimeError("오프라인")

    app = create_app(_reg(tmp_path), metadata_fn=_meta, cloud_store_factory=boom)
    client = TestClient(app)
    r = client.get("/api/cloud/backups")
    assert r.status_code == 200
    assert "error" in r.json()


def test_cache_size_and_clear(tmp_path, monkeypatch):
    monkeypatch.setenv("IOS_BACKUP_VAULT_HOME", str(tmp_path / "home"))
    app = create_app(_reg(tmp_path), metadata_fn=_meta,
                     cloud_store_factory=lambda: FakeCloudStore([]))
    client = TestClient(app)
    r = client.get("/api/cache/size")
    assert r.status_code == 200
    assert "bytes" in r.json()
    r2 = client.post("/api/cache/clear")
    assert r2.status_code == 200
    assert r2.json().get("ok") is True


def test_cloud_open_bad_passphrase_returns_error(tmp_path, monkeypatch):
    monkeypatch.setenv("IOS_BACKUP_VAULT_HOME", str(tmp_path / "home"))
    store = FakeCloudStore(["UDID-A"])
    # 메타 fetch가 일어나도록 Manifest 류를 채워 두되, 복호화는 항상 실패하는 inner.
    store.objs["UDID-A/Manifest.plist"] = b"mp"
    store.objs["UDID-A/Manifest.db"] = b"mdb"

    class BadVault:
        def open(self):
            from ios_backup_vault.vault import VaultError
            raise VaultError("백업 복호화 실패 — 비밀번호가 틀렸거나 백업이 손상되었을 수 있습니다.")

    app = create_app(
        _reg(tmp_path), metadata_fn=_meta,
        cloud_store_factory=lambda: store,
        cloud_vault_factory=lambda **kw: BadVault(),
    )
    client = TestClient(app)
    r = client.post("/api/cloud/open", json={"udid": "UDID-A", "passphrase": "bad"})
    assert "error" in r.json()
    assert r.json().get("ok") is not True


def test_cloud_open_rejects_traversal_udid(tmp_path, monkeypatch):
    monkeypatch.setenv("IOS_BACKUP_VAULT_HOME", str(tmp_path / "home"))
    app = create_app(_reg(tmp_path), metadata_fn=_meta,
                     cloud_store_factory=lambda: FakeCloudStore([]))
    client = TestClient(app)
    r = client.post("/api/cloud/open", json={"udid": "../escape", "passphrase": "x"})
    assert r.status_code == 400
    assert "error" in r.json()


def test_index_contains_cloud_and_cache_ui(tmp_path):
    app = create_app(_reg(tmp_path), metadata_fn=_meta)
    client = TestClient(app)
    body = client.get("/").text
    assert "/api/cloud/backups" in body
    assert "/api/cloud/open" in body
    assert "/api/cache/size" in body
    assert "/api/cache/clear" in body
    assert "클라우드" in body
    assert "캐시 비우기" in body
