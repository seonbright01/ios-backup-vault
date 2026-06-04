import os
from ios_backup_vault.paths import vault_home, cloud_config_path, cache_root


def test_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("IOS_BACKUP_VAULT_HOME", str(tmp_path))
    assert vault_home() == str(tmp_path)
    assert cloud_config_path() == os.path.join(str(tmp_path), "cloud.json")
    assert cache_root().startswith(str(tmp_path))
