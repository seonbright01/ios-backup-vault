from fastapi.testclient import TestClient
from ios_backup_vault.web import create_app


class FakeData:
    def summary(self): return {}
    def messages(self): return []
    def contacts(self): return []
    def calls(self): return []
    def media(self): return []
    def media_bytes(self, fid): return None
    def search(self, q): return {"messages": [], "contacts": []}
    def whatsapp(self): return []
    def appscan(self): return []
    def chatgpt(self): return []
    def notes(self): return [{"title": "T", "body": "본문", "created": "2023-11-14", "modified": "2023-11-15"}]


def test_notes_endpoint():
    r = TestClient(create_app(FakeData())).get("/api/notes")
    assert r.json()[0]["title"] == "T"
