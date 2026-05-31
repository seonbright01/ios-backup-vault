import json
from ios_backup_vault import device
from ios_backup_vault.safety import (
    DeviceState, detect_state, plan_changes, ChangePlan, record_original_state,
)


def test_detect_state_reads_version_and_encryption():
    state = detect_state(
        udid="u1",
        paired=True,
        info_root={device.KEY_PRODUCT_VERSION: "17.4"},
        info_backup={device.KEY_WILL_ENCRYPT: True},
    )
    assert state == DeviceState(
        udid="u1", paired=True, backup_encryption_enabled=True, ios_version="17.4",
    )


def test_detect_state_defaults_when_keys_missing():
    state = detect_state(udid="u1", paired=False, info_root={}, info_backup={})
    assert state.backup_encryption_enabled is False
    assert state.ios_version == "unknown"


def test_plan_changes_requires_consent_to_enable():
    state = DeviceState("u1", True, backup_encryption_enabled=False, ios_version="17.4")
    plan = plan_changes(state, want_encryption=True)
    assert isinstance(plan, ChangePlan)
    assert plan.will_enable_encryption is True
    assert plan.requires_consent is True
    assert any("설정" in w for w in plan.warnings)


def test_plan_changes_no_change_when_already_encrypted():
    state = DeviceState("u1", True, backup_encryption_enabled=True, ios_version="17.4")
    plan = plan_changes(state, want_encryption=True)
    assert plan.will_enable_encryption is False
    assert plan.requires_consent is False


def test_plan_changes_no_change_when_not_wanting_encryption():
    state = DeviceState("u1", True, backup_encryption_enabled=False, ios_version="17.4")
    plan = plan_changes(state, want_encryption=False)
    assert plan.will_enable_encryption is False
    assert plan.requires_consent is False


def test_record_original_state_writes_json(tmp_path):
    state = DeviceState("u1", True, backup_encryption_enabled=False, ios_version="17.4")
    path = tmp_path / "original_state.json"
    record_original_state(state, path)
    data = json.loads(path.read_text())
    assert data["udid"] == "u1"
    assert data["backup_encryption_enabled"] is False
    assert data["ios_version"] == "17.4"
