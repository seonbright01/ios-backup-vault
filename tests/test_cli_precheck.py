import pytest
from ios_backup_vault import device
from ios_backup_vault.cli import run_precheck, PrecheckReport
from ios_backup_vault.device import DeviceNotConnected, DeviceNotTrusted


def _info_fn(version="17.4", will_encrypt=False, total=128_000_000_000, avail=28_000_000_000):
    def fn(domain=None, udid=None):
        if domain == device.BACKUP_DOMAIN:
            return {device.KEY_WILL_ENCRYPT: will_encrypt}
        if domain == device.DISK_USAGE_DOMAIN:
            return {device.KEY_TOTAL_DATA: total, device.KEY_AVAIL_DATA: avail}
        return {device.KEY_PRODUCT_VERSION: version}
    return fn


def test_run_precheck_happy_path():
    report = run_precheck(
        "/tmp/target",
        list_udids=lambda: ["u1"],
        is_paired=lambda udid: True,
        device_info=_info_fn(will_encrypt=True),
        disk_free=lambda path: 500_000_000_000,
    )
    assert isinstance(report, PrecheckReport)
    assert report.udid == "u1"
    assert report.state.backup_encryption_enabled is True
    assert report.estimate.estimated_backup_bytes == 100_000_000_000
    assert report.estimate.fits is True


def test_run_precheck_no_device():
    with pytest.raises(DeviceNotConnected):
        run_precheck(
            "/tmp/target",
            list_udids=lambda: [],
            is_paired=lambda udid: True,
            device_info=_info_fn(),
            disk_free=lambda path: 1,
        )


def test_run_precheck_not_trusted():
    with pytest.raises(DeviceNotTrusted):
        run_precheck(
            "/tmp/target",
            list_udids=lambda: ["u1"],
            is_paired=lambda udid: False,
            device_info=_info_fn(),
            disk_free=lambda path: 1,
        )


def test_run_precheck_reports_does_not_fit():
    report = run_precheck(
        "/tmp/target",
        list_udids=lambda: ["u1"],
        is_paired=lambda udid: True,
        device_info=_info_fn(total=600_000_000_000, avail=0),
        disk_free=lambda path: 100_000_000_000,
    )
    assert report.estimate.fits is False


def test_run_precheck_raises_deviceerror_on_missing_disk_keys():
    from ios_backup_vault.device import DeviceError

    def info_fn(domain=None, udid=None):
        if domain == device.BACKUP_DOMAIN:
            return {device.KEY_WILL_ENCRYPT: False}
        if domain == device.DISK_USAGE_DOMAIN:
            return {}  # 예상 키 누락
        return {device.KEY_PRODUCT_VERSION: "17.4"}

    with pytest.raises(DeviceError):
        run_precheck(
            "/tmp/t",
            list_udids=lambda: ["u1"],
            is_paired=lambda u: True,
            device_info=info_fn,
            disk_free=lambda p: 1,
        )
