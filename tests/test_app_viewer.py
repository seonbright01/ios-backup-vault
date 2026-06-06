"""P9 Task2: 관리/뷰어 엔드포인트 위임 — 가짜 ViewerData로 위임 확인 + 등록경로 검증."""
import hashlib
import json

from fastapi.testclient import TestClient

from ios_backup_vault.app import create_app


class FakeVault:
    def open(self):
        pass

    def close(self):
        pass


class FakeViewer:
    def __init__(self, vault):
        self._v = vault

    def summary(self):
        return {"messages": 7, "contacts": 2}

    def messages(self):
        return [{"name": "가족", "messages": [{"text": "안녕", "timestamp": "t", "is_from_me": False}]}]

    def contacts(self):
        return [{"name": "김<민>호", "values": ["010"]}]

    def calls(self):
        return [{"address": "010", "timestamp": "t", "duration_sec": 5, "originated": True, "name": "김민호"}]

    def whatsapp(self):
        return [{"name": "Alex", "messages": []}]

    def chatgpt(self):
        return [{"title": "T", "created": "c", "messages": []}]

    def notes(self):
        return [{"title": "메모", "modified": "m", "body": "본문"}]

    def appscan(self):
        return [{"label": "ChatGPT", "file_count": 3, "readable": True, "note": "ok"}]

    def media(self):
        return [{"file_id": "F1", "kind": "image", "relative_path": "a.jpg"}]

    def media_bytes(self, file_id):
        if file_id == "F1":
            return b"\xff\xd8jpeg", "image/jpeg"
        return None

    def files(self):
        return [{"file_id": "f1", "filename": "report.pdf", "ext": "pdf",
                 "category": "document", "app": "카카오톡", "path": "docs/report.pdf"}]

    def file_bytes(self, file_id):
        if file_id == "f1":
            return b"%PDF data", "application/pdf"
        return None

    def search(self, q):
        return {"messages": [{"text": q, "timestamp": "t"}], "contacts": []}

    def export(self, payload):
        return "export.json", b'{"x":1}', "application/json"


def _meta(path, *, with_size=True, reveal_pii=False):
    return {
        "path": path, "udid": "UDID1", "device_name": "iPhone <X>",
        "product_type": "iPhone14,2", "ios_version": "17.2", "build": "21C62",
        "imaged_at": "i", "snapshot_date": "s", "last_backup_date": "l",
        "is_encrypted": True, "is_full": True, "snapshot_state": "", "backup_state": "",
        "app_count": 2, "size_bytes": 99 if with_size else None,
        "serial": "ABCDEF1234" if reveal_pii else "••••1234",
        "imei": "", "iccid": "", "phone": "",
    }


def _id_of(path):
    return hashlib.sha1(str(path).encode()).hexdigest()[:12]


def _reg(tmp_path, path="/x/UDID1"):
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps({"backups": [{"path": path, "label": "L", "added_at": "t"}]}),
                   encoding="utf-8")
    return str(reg)


def _opened_client(tmp_path, path="/x/UDID1"):
    reg = _reg(tmp_path, path)
    app = create_app(reg, vault_factory=lambda p, pw: FakeVault(),
                     viewer_factory=lambda v: FakeViewer(v), metadata_fn=_meta)
    client = TestClient(app)
    bid = _id_of(path)
    client.post(f"/api/backups/{bid}/open", json={"passphrase": "pw"})
    return client, bid


def test_backups_list_includes_id_and_mask(tmp_path):
    reg = _reg(tmp_path)
    app = create_app(reg, metadata_fn=_meta)
    client = TestClient(app)
    data = client.get("/api/backups").json()
    assert len(data) == 1
    assert data[0]["id"] == _id_of("/x/UDID1")
    assert data[0]["serial"].startswith("•")
    assert data[0]["opened"] is False


def test_backup_meta_reveal(tmp_path):
    reg = _reg(tmp_path)
    app = create_app(reg, metadata_fn=_meta)
    client = TestClient(app)
    bid = _id_of("/x/UDID1")
    masked = client.get(f"/api/backups/{bid}").json()
    assert masked["serial"].startswith("•")
    revealed = client.get(f"/api/backups/{bid}", params={"reveal": 1}).json()
    assert revealed["serial"] == "ABCDEF1234"


def test_backup_meta_unregistered_404(tmp_path):
    reg = _reg(tmp_path)
    app = create_app(reg, metadata_fn=_meta)
    client = TestClient(app)
    r = client.get("/api/backups/deadbeefdead")
    assert r.status_code == 404


def test_remove_delegates(tmp_path):
    reg = _reg(tmp_path)
    removed = {}

    def fake_remove(reg_path, path):
        removed["path"] = path
        return True

    app = create_app(reg, remove_fn=fake_remove, metadata_fn=_meta)
    client = TestClient(app)
    bid = _id_of("/x/UDID1")
    r = client.post(f"/api/backups/{bid}/remove")
    assert r.json()["removed"] is True
    assert removed["path"] == "/x/UDID1"


def test_viewer_summary_delegates(tmp_path):
    client, bid = _opened_client(tmp_path)
    assert client.get(f"/api/backups/{bid}/summary").json()["messages"] == 7


def test_viewer_all_tabs_delegate(tmp_path):
    client, bid = _opened_client(tmp_path)
    assert client.get(f"/api/backups/{bid}/messages").json()[0]["name"] == "가족"
    assert client.get(f"/api/backups/{bid}/contacts").json()[0]["values"] == ["010"]
    assert client.get(f"/api/backups/{bid}/calls").json()[0]["name"] == "김민호"
    assert client.get(f"/api/backups/{bid}/whatsapp").json()[0]["name"] == "Alex"
    assert client.get(f"/api/backups/{bid}/chatgpt").json()[0]["title"] == "T"
    assert client.get(f"/api/backups/{bid}/notes").json()[0]["title"] == "메모"
    assert client.get(f"/api/backups/{bid}/appscan").json()[0]["label"] == "ChatGPT"


def test_viewer_media_and_bytes(tmp_path):
    client, bid = _opened_client(tmp_path)
    d = client.get(f"/api/backups/{bid}/media").json()
    assert d["total"] == 1 and d["items"][0]["file_id"] == "F1"
    r = client.get(f"/api/backups/{bid}/media/F1")
    assert r.status_code == 200 and r.content == b"\xff\xd8jpeg"
    assert client.get(f"/api/backups/{bid}/media/NOPE").status_code == 404


def test_viewer_search(tmp_path):
    client, bid = _opened_client(tmp_path)
    r = client.get(f"/api/backups/{bid}/search", params={"q": "hi"})
    assert r.json()["messages"][0]["text"] == "hi"


def test_viewer_export(tmp_path):
    client, bid = _opened_client(tmp_path)
    r = client.post(f"/api/backups/{bid}/export", json={"formats": ["json"], "items": {}})
    assert r.status_code == 200
    assert 'filename="export.json"' in r.headers["content-disposition"]


def test_viewer_files_list_and_bytes(tmp_path):
    client, bid = _opened_client(tmp_path)
    d = client.get(f"/api/backups/{bid}/files").json()
    assert len(d) == 1 and d[0]["file_id"] == "f1" and d[0]["filename"] == "report.pdf"
    r = client.get(f"/api/backups/{bid}/files/f1")
    assert r.status_code == 200 and r.content == b"%PDF data"
    assert client.get(f"/api/backups/{bid}/files/UNKNOWN").status_code == 404


def test_files_tab_present_in_html(tmp_path):
    reg = _reg(tmp_path)
    app = create_app(reg, metadata_fn=_meta)
    client = TestClient(app)
    html = client.get("/").text
    assert 'data-vtab="files"' in html
    assert 'id="vp-files"' in html
    assert "파일" in html


def test_viewer_409_without_open(tmp_path):
    reg = _reg(tmp_path)
    app = create_app(reg, metadata_fn=_meta)
    client = TestClient(app)
    bid = _id_of("/x/UDID1")
    for ep in ["summary", "messages", "contacts", "calls", "media",
               "whatsapp", "chatgpt", "notes", "appscan"]:
        assert client.get(f"/api/backups/{bid}/{ep}").status_code == 409
