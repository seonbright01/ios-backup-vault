"""기기 상태 감지(순수)·변경계획·원상태 기록."""
import json
from dataclasses import dataclass, asdict
from pathlib import Path

from ios_backup_vault.device import KEY_WILL_ENCRYPT, KEY_PRODUCT_VERSION


@dataclass
class DeviceState:
    udid: str
    paired: bool
    backup_encryption_enabled: bool
    ios_version: str


@dataclass
class ChangePlan:
    will_enable_encryption: bool
    requires_consent: bool
    warnings: list[str]


def detect_state(*, udid: str, paired: bool, info_root: dict, info_backup: dict) -> DeviceState:
    return DeviceState(
        udid=udid,
        paired=paired,
        backup_encryption_enabled=bool(info_backup.get(KEY_WILL_ENCRYPT, False)),
        ios_version=str(info_root.get(KEY_PRODUCT_VERSION, "unknown")),
    )


def plan_changes(state: DeviceState, want_encryption: bool) -> ChangePlan:
    will_enable = want_encryption and not state.backup_encryption_enabled
    warnings: list[str] = []
    if will_enable:
        warnings.append("기기에 '백업 암호화' 설정을 켭니다(기기 설정 1회 변경). 동의가 필요합니다.")
    return ChangePlan(
        will_enable_encryption=will_enable,
        requires_consent=will_enable,
        warnings=warnings,
    )


def record_original_state(state: DeviceState, path: str | Path) -> None:
    Path(path).write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")
