"""libimobiledevice CLI 얇은 래퍼. 모든 함수는 runner 주입 가능(테스트용)."""
import plistlib
import subprocess
from collections.abc import Callable
from dataclasses import dataclass


# --- libimobiledevice 도메인/키 상수 (실기기 검증 전까지 best-known; Task 6에서 확정) ---
BACKUP_DOMAIN = "com.apple.mobile.backup"
KEY_WILL_ENCRYPT = "WillEncrypt"
DISK_USAGE_DOMAIN = "com.apple.disk_usage"
KEY_TOTAL_DATA = "TotalDataCapacity"
KEY_AVAIL_DATA = "TotalDataAvailable"
KEY_PRODUCT_VERSION = "ProductVersion"


class DeviceError(Exception):
    """libimobiledevice 호출 실패."""


class DeviceNotConnected(DeviceError):
    """USB에 기기 없음."""


class DeviceNotTrusted(DeviceError):
    """기기가 이 맥을 신뢰하지 않음(페어링 안 됨)."""


@dataclass
class CommandResult:
    returncode: int
    stdout: bytes
    stderr: str


def _default_runner(args, *, timeout: int = 120) -> CommandResult:
    try:
        proc = subprocess.run(args, capture_output=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise DeviceError(f"명령을 찾을 수 없음: {args[0]} (libimobiledevice 설치 필요)") from exc
    except subprocess.TimeoutExpired as exc:
        raise DeviceError(f"명령 시간 초과({timeout}s): {args[0]}") from exc
    return CommandResult(proc.returncode, proc.stdout, proc.stderr.decode(errors="replace"))


def list_udids(runner: Callable[..., CommandResult] = _default_runner) -> list[str]:
    res = runner(["idevice_id", "-l"])
    if res.returncode != 0:
        raise DeviceError(res.stderr or "idevice_id 실패")
    return [line.strip() for line in res.stdout.decode(errors="replace").splitlines() if line.strip()]


def is_paired(udid: str | None = None, runner: Callable[..., CommandResult] = _default_runner) -> bool:
    args = ["idevicepair"]
    if udid:
        args += ["-u", udid]
    args += ["validate"]
    # rc==0=페어링됨, 그 외=미페어링으로 처리. 데몬/도구 오류 vs 미신뢰 구분은
    # 실제 idevicepair stderr/exit code 확인이 필요 → Task 6에서 검증·세분화.
    return runner(args).returncode == 0


def device_info(domain: str | None = None, udid: str | None = None, runner: Callable[..., CommandResult] = _default_runner) -> dict:
    args = ["ideviceinfo", "-x"]
    if udid:
        args += ["-u", udid]
    if domain:
        args += ["-q", domain]
    res = runner(args)
    if res.returncode != 0:
        raise DeviceError(res.stderr or "ideviceinfo 실패")
    try:
        return plistlib.loads(res.stdout)
    except Exception as exc:
        raise DeviceError(f"plist 파싱 실패: {exc}") from exc


def _streaming_runner(args, *, timeout=None) -> CommandResult:
    """장시간 작업용 runner: 출력을 터미널로 스트리밍, 타임아웃 없음."""
    try:
        proc = subprocess.run(args, timeout=timeout)
    except FileNotFoundError as exc:
        raise DeviceError(f"명령을 찾을 수 없음: {args[0]} (libimobiledevice 설치 필요)") from exc
    return CommandResult(proc.returncode, b"", "")


def run_backup(udid: str | None, target_dir: str, runner=_streaming_runner, full: bool = True) -> CommandResult:
    """idevicebackup2 backup 실행. 기본 runner는 스트리밍(장시간). 기기 데이터는 읽기."""
    args = ["idevicebackup2"]
    if udid:
        args += ["-u", udid]
    args += ["backup"]
    if full:
        args += ["--full"]
    args += [target_dir]
    res = runner(args)
    if res.returncode != 0:
        raise DeviceError(res.stderr or "idevicebackup2 backup 실패")
    return res
