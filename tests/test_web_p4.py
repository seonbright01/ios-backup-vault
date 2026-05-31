from fastapi.testclient import TestClient
from ios_backup_vault.web import create_app


class FakeData:
    def summary(self): return {"messages": 0, "contacts": 0, "calls": 0, "media": 0, "whatsapp": 0}
    def messages(self): return []
    def contacts(self): return []
    def calls(self): return [{"address": "+100", "name": "Ada", "timestamp": "t", "duration_sec": 1, "originated": True}]
    def media(self): return []
    def media_bytes(self, fid): return None
    def search(self, q): return {"messages": [], "contacts": []}
    def whatsapp(self): return [{"name": "Bob", "jid": "11@x", "messages": [{"text": "hi", "timestamp": "t", "is_from_me": False}]}]
    def appscan(self): return [{"label": "KakaoTalk", "file_count": 3, "domains": ["AppDomain-com.kakao.talk"], "readable": False, "note": "앱 자체 암호화 — 내용 불가"}]


def _c(): return TestClient(create_app(FakeData()))


def test_whatsapp_endpoint():
    assert _c().get("/api/whatsapp").json()[0]["name"] == "Bob"


def test_appscan_endpoint():
    a = _c().get("/api/appscan").json()
    assert a[0]["label"] == "KakaoTalk" and a[0]["readable"] is False


def test_calls_include_name():
    assert _c().get("/api/calls").json()[0]["name"] == "Ada"
