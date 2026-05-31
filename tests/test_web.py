from fastapi.testclient import TestClient
from ios_backup_vault.web import create_app


class FakeData:
    def summary(self): return {"messages": 1, "contacts": 1, "calls": 1, "media": 1}
    def messages(self): return [{"chat_identifier": "+1", "display_name": "", "messages": [{"text": "hi", "timestamp": "2020-01-01T00:00:00+00:00", "is_from_me": False, "handle": "+1"}]}]
    def contacts(self): return [{"name": "Ada", "values": ["+100"]}]
    def calls(self): return [{"address": "+100", "timestamp": "2020-01-01T00:00:00+00:00", "duration_sec": 65, "originated": True}]
    def media(self): return [{"file_id": "fid1", "relative_path": "Media/DCIM/IMG_0001.JPG", "kind": "image"}]
    def media_bytes(self, file_id): return (b"\xff\xd8\xff", "image/jpeg") if file_id == "fid1" else None
    def search(self, q): return {"messages": [], "contacts": [{"name": "Ada", "values": ["+100"]}] if q == "ada" else []}


def _client(): return TestClient(create_app(FakeData()))


def test_root_ok():
    r = _client().get("/")
    assert r.status_code == 200


def test_api_messages():
    assert _client().get("/api/messages").json()[0]["messages"][0]["text"] == "hi"


def test_media_bytes_served():
    r = _client().get("/media/fid1")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/")
    assert r.content == b"\xff\xd8\xff"


def test_media_missing_404():
    assert _client().get("/media/nope").status_code == 404


def test_search():
    assert any(c["name"] == "Ada" for c in _client().get("/api/search", params={"q": "ada"}).json()["contacts"])


def test_vault_error_returns_503():
    from ios_backup_vault.vault import VaultError
    class BoomData(FakeData):
        def messages(self): raise VaultError("decrypt failed")
    from fastapi.testclient import TestClient
    c = TestClient(create_app(BoomData()), raise_server_exceptions=False)
    r = c.get("/api/messages")
    assert r.status_code == 503
    assert "error" in r.json()
