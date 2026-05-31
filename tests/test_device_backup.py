from ios_backup_vault import device
from ios_backup_vault.device import CommandResult, DeviceError
import pytest


def make_runner(result, cap):
    def _r(args, **kw):
        cap["args"] = args
        return result
    return _r


def test_run_backup_builds_full_command():
    cap = {}
    r = make_runner(CommandResult(0, b"", ""), cap)
    device.run_backup("u1", "/tmp/bk", runner=r)
    assert cap["args"] == ["idevicebackup2", "-u", "u1", "backup", "--full", "/tmp/bk"]


def test_run_backup_raises_on_failure():
    r = make_runner(CommandResult(1, b"", "boom"), {})
    with pytest.raises(DeviceError):
        device.run_backup("u1", "/tmp/bk", runner=r)
