"""P9 Task4: SPA 임베드 + CLI 전환 스모크."""
import json

from fastapi.testclient import TestClient

from ios_backup_vault.app import create_app


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


def test_index_serves_spa(tmp_path):
    app = create_app(_reg(tmp_path), metadata_fn=_meta)
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    body = r.text
    # SPA 셸 핵심 마커
    assert "iOS 백업 도구" in body
    assert "새 이미징" in body
    assert "data-vtab" in body
    # 실제 API 경로로 연결됨(목업 더미 아님)
    assert "/api/backups" in body
    assert "/api/imaging/start" in body
    assert "/api/imaging/stream" in body
    assert "/api/backups/scan-folder" in body
    # 더미 데이터 흔적 없음
    assert "DUMMY_BACKUPS" not in body
    assert "[시안]" not in body


def test_index_preselect_injection(tmp_path):
    app = create_app(_reg(tmp_path), metadata_fn=_meta, preselect_id="abc123def456")
    client = TestClient(app)
    body = client.get("/").text
    assert 'window.__PRESELECT_ID="abc123def456"' in body


def test_cli_help_smoke():
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "-m", "ios_backup_vault.cli", "--help"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "manage" in r.stdout and "view" in r.stdout
