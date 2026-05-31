import json
from ios_backup_vault.viewer_data import ViewerData
from ios_backup_vault.parsers.appscan import summarize_apps


class FakeVault:
    def find_files(self, *, domain_like=None, path_like=None):
        return [("f1", "AppDomain-com.openai.chat", "Library/Application Support/conversations-v3-x/a.json")]
    def read_bytes(self, rel, *, domain_like=None):
        return json.dumps({"title": "T", "creation_date": 1700000000.0,
                           "tree": {"storage": ["i", {"content": {"author": {"role": "user"},
                           "content": {"content_type": "text", "parts": ["hi"]}, "create_time": 1700000000.0}}]}}).encode()


def test_viewer_chatgpt():
    convos = ViewerData(FakeVault()).chatgpt()
    assert convos[0]["title"] == "T"
    assert convos[0]["messages"][0]["text"] == "hi"


def test_appscan_includes_chatgpt():
    rows = [("f", "AppDomain-com.openai.chat", "Library/Application Support/conversations-v3-x/a.json")]
    apps = {a["label"]: a for a in summarize_apps(rows)}
    assert apps["ChatGPT"]["readable"] is True
