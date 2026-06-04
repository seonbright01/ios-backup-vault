from ios_backup_vault import secrets


def test_adc_returns_none():
    assert secrets.resolve_credentials({"auth": "adc"}) is None


def test_keyring_path_uses_injected_getter(monkeypatch):
    monkeypatch.setattr(secrets, "_keyring_get", lambda acct: '{"type":"service_account"}')
    made = {}
    monkeypatch.setattr(secrets, "_creds_from_info", lambda info: (made.__setitem__("info", info), "CREDS")[1])
    out = secrets.resolve_credentials({"auth": "keyring", "account": "gcs"})
    assert out == "CREDS" and made["info"]["type"] == "service_account"


def test_keyring_missing_raises(monkeypatch):
    monkeypatch.setattr(secrets, "_keyring_get", lambda acct: None)
    import pytest
    with pytest.raises(RuntimeError):
        secrets.resolve_credentials({"auth": "keyring", "account": "gcs"})
