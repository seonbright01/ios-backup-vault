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
    def notes(self): return []

    def export(self, payload):
        return "export.json", b"{}", "application/json"


def test_export_endpoint():
    r = TestClient(create_app(FakeData())).post(
        "/api/export", json={"formats": ["json"], "items": {}})
    assert r.status_code == 200
    assert 'filename="export.json"' in r.headers["content-disposition"]
    assert r.content == b"{}"
