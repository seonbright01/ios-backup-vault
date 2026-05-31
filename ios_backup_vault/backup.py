"""백업 무결성 검증·메타데이터·오케스트레이션."""
import json
import plistlib
from dataclasses import dataclass, asdict
from pathlib import Path

from ios_backup_vault.safety import DeviceState, plan_changes, record_original_state

# Status.plist 키 (best-known; 실제 백업으로 Task 6에서 검증)
REQUIRED_FILES = ["Status.plist", "Manifest.plist", "Manifest.db", "Info.plist"]
KEY_SNAPSHOT_STATE = "SnapshotState"
VALUE_FINISHED = "finished"
KEY_IS_FULL = "IsFullBackup"


class BackupError(Exception):
    """백업 단계 실패."""


class BackupAborted(BackupError):
    """사용자 미동의 등으로 중단."""


class BackupIntegrityError(BackupError):
    """완료 후 무결성 검증 실패."""


@dataclass
class IntegrityResult:
    ok: bool
    snapshot_state: str | None
    is_full: bool
    missing: list[str]


def verify_integrity(backup_path) -> IntegrityResult:
    p = Path(backup_path)
    missing = [f for f in REQUIRED_FILES if not (p / f).exists()]
    snapshot_state = None
    is_full = False
    status_file = p / "Status.plist"
    if status_file.exists():
        try:
            status = plistlib.loads(status_file.read_bytes())
        except Exception as exc:
            raise BackupIntegrityError(f"Status.plist 파싱 실패: {exc}") from exc
        snapshot_state = status.get(KEY_SNAPSHOT_STATE)
        is_full = bool(status.get(KEY_IS_FULL, False))
    ok = not missing and snapshot_state == VALUE_FINISHED
    return IntegrityResult(ok=ok, snapshot_state=snapshot_state, is_full=is_full, missing=missing)


@dataclass
class BackupMetadata:
    udid: str
    ios_version: str
    encryption_enabled: bool
    size_bytes: int
    file_count: int
    created_at: str  # ISO8601, 호출자가 주입(순수성 유지)


def dir_size_and_count(path) -> tuple[int, int]:
    total = 0
    count = 0
    for f in Path(path).rglob("*"):
        if f.is_file():
            total += f.stat().st_size
            count += 1
    return total, count


def write_backup_metadata(out_path, meta: BackupMetadata) -> None:
    Path(out_path).write_text(
        json.dumps(asdict(meta), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def run_backup_flow(
    target_root,
    *,
    state: DeviceState,
    want_encryption: bool,
    now_iso: str,
    consent_fn,
    enable_encryption_fn,
    do_backup,
):
    """백업 오케스트레이션. 순수 조율 + 주입된 부수효과."""
    plan = plan_changes(state, want_encryption)
    if plan.requires_consent:
        if not consent_fn(plan):
            raise BackupAborted("기기 설정 변경(암호화)에 동의하지 않아 중단했습니다.")
        enable_encryption_fn()

    record_original_state(state, Path(target_root) / f"{state.udid}.original_state.json")

    do_backup(target_root)

    backup_path = Path(target_root) / state.udid
    integrity = verify_integrity(backup_path)
    if not integrity.ok:
        raise BackupIntegrityError(
            f"무결성 검증 실패: missing={integrity.missing}, snapshot={integrity.snapshot_state}"
        )

    size, count = dir_size_and_count(backup_path)
    meta = BackupMetadata(
        udid=state.udid,
        ios_version=state.ios_version,
        encryption_enabled=(state.backup_encryption_enabled or want_encryption),
        size_bytes=size,
        file_count=count,
        created_at=now_iso,
    )
    write_backup_metadata(Path(target_root) / f"{state.udid}.vault_meta.json", meta)
    return backup_path, integrity, meta
