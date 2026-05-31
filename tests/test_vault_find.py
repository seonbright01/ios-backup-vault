import contextlib
from ios_backup_vault.vault import Vault


def test_find_files_builds_like_query():
    captured = {}

    class FakeCur:
        def execute(self, sql, params):
            captured["sql"] = sql; captured["params"] = params; return self
        def fetchall(self):
            return [("fid", "AppDomain-com.openai.chat", "Library/Application Support/conversations-v3-x/a.json")]

    class CMBackend:
        def test_decryption(self): pass
        @contextlib.contextmanager
        def manifest_db_cursor(self):
            yield FakeCur()

    rows = Vault(backend=CMBackend()).find_files(
        domain_like="AppDomain-com.openai.chat", path_like="%conversations-v3-%/%.json")
    assert rows[0][1] == "AppDomain-com.openai.chat"
    assert "domain LIKE ?" in captured["sql"] and "relativePath LIKE ?" in captured["sql"]
    assert captured["params"] == ["AppDomain-com.openai.chat", "%conversations-v3-%/%.json"]
