"""Task 4: 웹 관리 대시보드 TDD (TestClient + 주입 metadata_fn)."""
import json

from fastapi.testclient import TestClient

from ios_backup_vault.manage_web import create_manager_app


def _fake_meta(path, *, with_size=True, reveal_pii=False):
    return {
        "path": path,
        "udid": "UDID1",
        "device_name": "iPhone <X>",
        "product_type": "iPhone14,2",
        "ios_version": "17.2",
        "build": "21C62",
        "imaged_at": "2026-05-30T12:00:00",
        "last_backup_date": "2026-05-30T12:00:00",
        "is_encrypted": True,
        "is_full": True,
        "snapshot_state": "finished",
        "backup_state": "new",
        "app_count": 2,
        "size_bytes": 123456 if with_size else None,
        "serial": "ABCDEF123456" if reveal_pii else "••••••••3456",
        "imei": "123456789012345" if reveal_pii else "•••••••••••2345",
        "iccid": "x" if reveal_pii else "•",
        "phone": "+1010" if reveal_pii else "•1010",
    }


def _write_registry(tmp_path):
    reg = tmp_path / "registry.json"
    reg.write_text(
        json.dumps({"backups": [{"path": "/x/UDID1", "label": "L", "added_at": "t"}]}),
        encoding="utf-8",
    )
    return str(reg)


def _client(tmp_path):
    reg = _write_registry(tmp_path)
    app = create_manager_app(reg, metadata_fn=_fake_meta)
    return TestClient(app), reg


def test_api_backups(tmp_path):
    client, _ = _client(tmp_path)
    r = client.get("/api/backups")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["device_name"] == "iPhone <X>"
    assert data[0]["serial"].startswith("•")  # masked by default


def test_api_meta_mask_and_reveal(tmp_path):
    client, _ = _client(tmp_path)
    masked = client.get("/api/meta", params={"path": "/x/UDID1", "reveal": 0}).json()
    assert masked["serial"].startswith("•")
    revealed = client.get("/api/meta", params={"path": "/x/UDID1", "reveal": 1}).json()
    assert revealed["serial"] == "ABCDEF123456"


def test_api_meta_unregistered_path_forbidden(tmp_path):
    client, _ = _client(tmp_path)
    # 레지스트리에 없는 임의 경로는 거부(임의 plist 읽기/PII 노출 차단)
    r = client.get("/api/meta", params={"path": "/etc", "reveal": 1})
    assert r.status_code == 403
    assert "error" in r.json()


def test_registry_add_invalid(tmp_path):
    reg = _write_registry(tmp_path)

    def bad_meta(path, **kw):
        raise ValueError("백업 폴더가 아님")

    app = create_manager_app(reg, metadata_fn=bad_meta)
    client = TestClient(app)
    # add_fn defaults to registry.add which validates is_backup_dir on a fake path
    r = client.post("/api/registry/add", json={"path": "/nonexistent", "label": ""})
    assert r.status_code == 200
    assert "error" in r.json()


def test_index_html(tmp_path):
    client, _ = _client(tmp_path)
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    body = r.text
    assert "백업 추가" in body
    assert "새 이미징" in body
