import pytest
from ios_backup_vault.precheck import estimate_backup_size, assess_fit, SizeEstimate


def test_estimate_is_used_data():
    # 총 128GB 중 28GB 가용 => 사용량 100GB
    assert estimate_backup_size(
        total_data_bytes=128_000_000_000,
        available_data_bytes=28_000_000_000,
    ) == 100_000_000_000


def test_estimate_raises_on_inconsistent_data():
    # avail > total 은 불가능한 상태 → 조용히 0 반환하지 말고 오류로 표면화
    with pytest.raises(ValueError):
        estimate_backup_size(total_data_bytes=10, available_data_bytes=20)


def test_assess_fit_true_with_margin():
    est = assess_fit(estimated_backup_bytes=100, free_bytes=200)
    assert isinstance(est, SizeEstimate)
    assert est.fits is True
    assert est.estimated_backup_bytes == 100
    assert est.required_bytes == 110  # 10% 여유


def test_assess_fit_false_when_free_below_required():
    est = assess_fit(estimated_backup_bytes=100, free_bytes=105)  # 필요 110
    assert est.fits is False
    assert est.margin_bytes == 105 - 110
