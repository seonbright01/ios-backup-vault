"""설정·캐시 경로 단일 출처."""
import os


def vault_home():
    return os.environ.get("IOS_BACKUP_VAULT_HOME") or os.path.expanduser("~/.ios_backup_vault")


def cloud_config_path():
    return os.path.join(vault_home(), "cloud.json")


def cache_root():
    return os.path.join(vault_home(), "cache")
