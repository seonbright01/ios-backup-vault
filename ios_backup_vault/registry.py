"""백업 레지스트리 — 이 툴이 만든 백업 + 임의 경로(타툴/외부) 등록·열람.

레지스트리 파일경로를 인자로 받는 순수 함수 + 기본 경로 결정 헬퍼.
"""
import json
import os
from pathlib import Path

from ios_backup_vault.metadata import is_backup_dir
from ios_backup_vault.paths import vault_home


def registry_path() -> str:
    """env IOS_BACKUP_VAULT_HOME 있으면 그 아래, 없으면 ~/.ios_backup_vault."""
    return os.path.join(vault_home(), "registry.json")


def load(reg_path) -> list[dict]:
    """레지스트리 파일에서 backups 목록을 읽음(없으면 빈 리스트)."""
    p = Path(reg_path)
    if not p.is_file():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("backups", [])


def _save(reg_path, backups: list[dict]) -> None:
    p = Path(reg_path)
    os.makedirs(p.parent, exist_ok=True)
    p.write_text(
        json.dumps({"backups": backups}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add(reg_path, backup_path, label="", now_iso="") -> dict:
    """is_backup_dir 검증 후 등록(중복 path는 갱신). 저장 후 엔트리 반환."""
    if not is_backup_dir(backup_path):
        raise ValueError(f"백업 폴더가 아님: {backup_path}")
    abs_path = str(Path(backup_path).resolve())
    entry = {"path": abs_path, "label": label, "added_at": now_iso}
    backups = [b for b in load(reg_path) if b.get("path") != abs_path]
    backups.append(entry)
    _save(reg_path, backups)
    return entry


def remove(reg_path, backup_path) -> bool:
    """등록된 path 제거. 제거했으면 True, 없었으면 False."""
    abs_path = str(Path(backup_path).resolve())
    backups = load(reg_path)
    remaining = [b for b in backups if b.get("path") != abs_path]
    if len(remaining) == len(backups):
        return False
    _save(reg_path, remaining)
    return True
