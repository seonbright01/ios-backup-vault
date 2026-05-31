"""순수 용량 추정/적재 판정. 기기·파일 I/O 없음."""
from dataclasses import dataclass


@dataclass
class SizeEstimate:
    estimated_backup_bytes: int
    free_bytes: int
    required_bytes: int
    fits: bool
    margin_bytes: int  # free - required (음수면 부족분)


def estimate_backup_size(*, total_data_bytes: int, available_data_bytes: int) -> int:
    """백업 크기 근삿값 = 기기 데이터 사용량. avail>total(비일관)이면 오류."""
    used = total_data_bytes - available_data_bytes
    if used < 0:
        raise ValueError(
            f"기기 디스크 데이터가 비일관적입니다(avail>total): "
            f"total={total_data_bytes}, avail={available_data_bytes}. 도메인/키 상수 확인 필요(Task 6)."
        )
    return used


def assess_fit(estimated_backup_bytes: int, free_bytes: int, safety_margin: float = 0.10) -> SizeEstimate:
    """여유공간이 (추정치 + 올림한 여유분) 이상인지 판정. 정수연산으로 부동소수 오차 회피."""
    margin_percent = round(safety_margin * 100)
    extra = (estimated_backup_bytes * margin_percent + 99) // 100  # ceil(bytes * margin_percent / 100)
    required = estimated_backup_bytes + extra
    margin = free_bytes - required
    return SizeEstimate(
        estimated_backup_bytes=estimated_backup_bytes,
        free_bytes=free_bytes,
        required_bytes=required,
        fits=margin >= 0,
        margin_bytes=margin,
    )
