import plistlib
import subprocess
import pytest
from ios_backup_vault import device
from ios_backup_vault.device import CommandResult, DeviceError


def make_runner(result: CommandResult, capture: dict):
    def _runner(args, **kwargs):
        capture["args"] = args
        return result
    return _runner


def test_list_udids_parses_lines():
    cap = {}
    runner = make_runner(CommandResult(0, b"abc123\ndef456\n", ""), cap)
    assert device.list_udids(runner=runner) == ["abc123", "def456"]
    assert cap["args"] == ["idevice_id", "-l"]


def test_list_udids_empty():
    runner = make_runner(CommandResult(0, b"\n", ""), {})
    assert device.list_udids(runner=runner) == []


def test_is_paired_true_on_zero_exit():
    cap = {}
    runner = make_runner(CommandResult(0, b"SUCCESS", ""), cap)
    assert device.is_paired(udid="u1", runner=runner) is True
    assert cap["args"] == ["idevicepair", "-u", "u1", "validate"]


def test_is_paired_false_on_nonzero_exit():
    runner = make_runner(CommandResult(255, b"", "ERROR: No device"), {})
    assert device.is_paired(udid="u1", runner=runner) is False


def test_device_info_parses_plist_and_builds_args():
    cap = {}
    payload = plistlib.dumps({"ProductVersion": "17.4"})
    runner = make_runner(CommandResult(0, payload, ""), cap)
    info = device.device_info(domain="com.apple.mobile.backup", udid="u1", runner=runner)
    assert info["ProductVersion"] == "17.4"
    assert cap["args"] == ["ideviceinfo", "-x", "-u", "u1", "-q", "com.apple.mobile.backup"]


def test_device_info_raises_on_error():
    runner = make_runner(CommandResult(255, b"", "ERROR: Could not connect"), {})
    with pytest.raises(DeviceError):
        device.device_info(runner=runner)


def test_device_info_raises_on_malformed_plist():
    runner = make_runner(CommandResult(0, b"not a plist", ""), {})
    with pytest.raises(DeviceError):
        device.device_info(runner=runner)


def test_default_runner_maps_filenotfound(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError()
    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(DeviceError):
        device._default_runner(["idevice_id", "-l"])


def test_default_runner_maps_timeout(monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="idevice_id", timeout=1)
    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(DeviceError):
        device._default_runner(["idevice_id", "-l"])
