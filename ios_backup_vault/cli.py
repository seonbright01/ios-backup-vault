"""CLI 진입점 + precheck 오케스트레이션."""
import argparse
import getpass
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ios_backup_vault import device
from ios_backup_vault import backup as backup_mod
from ios_backup_vault import registry
from ios_backup_vault.backup import run_backup_flow
from ios_backup_vault.metadata import read_backup_metadata
from ios_backup_vault.device import DeviceNotConnected, DeviceNotTrusted
from ios_backup_vault.precheck import SizeEstimate, estimate_backup_size, assess_fit
from ios_backup_vault.safety import DeviceState, detect_state


@dataclass
class PrecheckReport:
    udid: str
    state: DeviceState
    estimate: SizeEstimate


def run_precheck(target_path: str | Path, *, list_udids, is_paired, device_info, disk_free) -> PrecheckReport:
    udids = list_udids()
    if not udids:
        raise DeviceNotConnected("USB에 연결된 iOS 기기가 없습니다. 케이블 연결 후 다시 시도하세요.")
    udid = udids[0]
    if not is_paired(udid):
        raise DeviceNotTrusted(
            "페어링/신뢰 검증에 실패했습니다. 폰 잠금을 풀고 '이 컴퓨터를 신뢰'를 누르세요"
            "(이미 했다면 케이블을 다시 연결). 문제가 계속되면 idevicepair 오류일 수 있습니다."
        )

    info_root = device_info(None, udid)
    info_backup = device_info(device.BACKUP_DOMAIN, udid)
    info_disk = device_info(device.DISK_USAGE_DOMAIN, udid)

    state = detect_state(udid=udid, paired=True, info_root=info_root, info_backup=info_backup)
    try:
        est_bytes = estimate_backup_size(
            total_data_bytes=int(info_disk[device.KEY_TOTAL_DATA]),
            available_data_bytes=int(info_disk[device.KEY_AVAIL_DATA]),
        )
    except KeyError as exc:
        raise device.DeviceError(
            f"기기 디스크 정보에서 예상 키를 찾지 못했습니다: {exc}. "
            f"libimobiledevice 버전/도메인 키 확인 필요(설계 Task 6)."
        ) from exc
    except (ValueError, TypeError) as exc:
        raise device.DeviceError(f"기기 디스크 정보 파싱 실패: {exc}") from exc
    estimate = assess_fit(est_bytes, disk_free(target_path))
    return PrecheckReport(udid=udid, state=state, estimate=estimate)


def run_backup_command(
    target_root,
    *,
    want_encryption,
    list_udids,
    is_paired,
    device_info,
    do_backup=None,
    consent_fn,
    enable_encryption_fn,
    now_iso,
):
    udids = list_udids()
    if not udids:
        raise DeviceNotConnected("USB에 연결된 iOS 기기가 없습니다.")
    udid = udids[0]
    if not is_paired(udid):
        raise DeviceNotTrusted("기기가 이 맥을 신뢰하지 않습니다. 폰에서 '신뢰'를 누르세요.")
    info_root = device_info(None, udid)
    info_backup = device_info(device.BACKUP_DOMAIN, udid)
    state = detect_state(udid=udid, paired=True, info_root=info_root, info_backup=info_backup)
    if do_backup is None:
        do_backup = lambda root: device.run_backup(udid, root)
    return run_backup_flow(
        target_root,
        state=state,
        want_encryption=want_encryption,
        now_iso=now_iso,
        consent_fn=consent_fn,
        enable_encryption_fn=enable_encryption_fn,
        do_backup=do_backup,
    )


def _gb(n: int) -> str:
    return f"{n / 1_000_000_000:.1f}GB"


def _print_meta(m: dict) -> None:
    size = "-" if m["size_bytes"] is None else _gb(m["size_bytes"])
    rows = [
        ("기기명", m["device_name"]),
        ("기종", m["product_type"]),
        ("iOS", m["ios_version"]),
        ("빌드", m["build"]),
        ("UDID", m["udid"]),
        ("이미징 시점", m["imaged_at"]),
        ("마지막 백업", m["last_backup_date"]),
        ("암호화", "켜짐" if m["is_encrypted"] else "꺼짐"),
        ("전체 백업", "예" if m["is_full"] else "아니오"),
        ("스냅샷 상태", m["snapshot_state"]),
        ("앱 수", str(m["app_count"])),
        ("용량", size),
        ("시리얼", m["serial"]),
        ("IMEI", m["imei"]),
        ("ICCID", m["iccid"]),
        ("전화번호", m["phone"]),
        ("경로", m["path"]),
    ]
    for label, value in rows:
        print(f"{label:>12}: {value}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ios-backup-vault")
    sub = parser.add_subparsers(dest="command", required=True)
    pc = sub.add_parser("precheck", help="연결·상태·용량 사전 점검")
    pc.add_argument("--target", required=True, help="백업을 저장할 폴더 경로(여유공간 판정용)")
    bk = sub.add_parser("backup", help="암호화 전체 백업 생성")
    bk.add_argument("--target", required=True, help="백업 저장 루트 폴더")
    bk.add_argument("--no-encrypt", action="store_true", help="암호화 강제 끄기(비권장)")
    vw = sub.add_parser("view", help="백업 열람(로컬 웹)")
    vw.add_argument("--backup", required=True, help="백업 폴더(<udid>) 경로")
    vw.add_argument("--port", type=int, default=8765)
    inf = sub.add_parser("info", help="백업 메타데이터 표시(패스프레이즈 불필요)")
    inf.add_argument("--backup", required=True, help="백업 폴더 경로")
    inf.add_argument("--reveal", action="store_true", help="PII(시리얼/IMEI 등) 원본 노출")
    ad = sub.add_parser("add", help="백업(임의 경로 포함)을 레지스트리에 등록")
    ad.add_argument("--path", required=True, help="등록할 백업 폴더 경로")
    ad.add_argument("--label", default="", help="라벨(선택)")
    sub.add_parser("list", help="등록된 백업 목록 표시")
    mg = sub.add_parser("manage", help="백업 관리 웹 대시보드(로컬)")
    mg.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    if args.command == "precheck":
        try:
            report = run_precheck(
                args.target,
                list_udids=device.list_udids,
                is_paired=device.is_paired,
                device_info=device.device_info,
                disk_free=lambda path: shutil.disk_usage(path).free,
            )
        except (DeviceNotConnected, DeviceNotTrusted) as exc:
            print(f"[중단] {exc}", file=sys.stderr)
            return 2
        except device.DeviceError as exc:
            print(f"[오류] 기기 통신 실패: {exc}", file=sys.stderr)
            return 1
        except OSError as exc:
            print(f"[오류] 대상 경로 접근 실패: {exc}", file=sys.stderr)
            return 1

        s, e = report.state, report.estimate
        print(f"UDID: {s.udid}")
        print(f"iOS: {s.ios_version}")
        print(f"백업 암호화 현재상태: {'켜짐' if s.backup_encryption_enabled else '꺼짐'}")
        print(f"예상 백업 크기(근삿값): {_gb(e.estimated_backup_bytes)}")
        print(f"대상 여유공간: {_gb(e.free_bytes)} / 필요(여유 10% 포함): {_gb(e.required_bytes)}")
        print("적재 판정: " + ("가능 ✅" if e.fits else f"부족 ❌ (부족분 {_gb(abs(e.margin_bytes))})"))
        if not s.backup_encryption_enabled:
            print("주의: 완전 백업(Health·키체인 포함)을 원하면 백업 단계에서 동의 후 암호화를 켜야 합니다.")
        return 0
    if args.command == "backup":
        def _consent(plan):
            print("[주의] 다음 기기 설정 변경이 필요합니다:")
            for w in plan.warnings:
                print("  - " + w)
            return input("진행하려면 'yes' 입력: ").strip().lower() == "yes"

        def _enable():
            raise NotImplementedError(
                "이 기기는 이미 암호화 ON이라 호출되지 않아야 합니다. 암호화 켜기는 향후 단계."
            )

        try:
            bp, integ, meta = run_backup_command(
                args.target,
                want_encryption=not args.no_encrypt,
                list_udids=device.list_udids,
                is_paired=device.is_paired,
                device_info=device.device_info,
                consent_fn=_consent,
                enable_encryption_fn=_enable,
                now_iso=datetime.now().isoformat(timespec="seconds"),
            )
        except (DeviceNotConnected, DeviceNotTrusted) as exc:
            print(f"[중단] {exc}", file=sys.stderr); return 2
        except backup_mod.BackupError as exc:
            print(f"[중단] {exc}", file=sys.stderr); return 2
        except device.DeviceError as exc:
            print(f"[오류] {exc}", file=sys.stderr); return 1
        except OSError as exc:
            print(f"[오류] 경로 접근 실패: {exc}", file=sys.stderr); return 1
        print(f"백업 완료: {bp}")
        print(f"무결성: {'OK' if integ.ok else '실패'} (snapshot={integ.snapshot_state}, full={integ.is_full})")
        print(f"크기: {meta.size_bytes/1_000_000_000:.1f}GB, 파일수: {meta.file_count}")
        try:
            label = ""
            try:
                label = read_backup_metadata(bp, with_size=False)["device_name"]
            except Exception:
                pass
            registry.add(
                registry.registry_path(), str(bp), label=label,
                now_iso=datetime.now().isoformat(timespec="seconds"),
            )
        except Exception as exc:
            print(f"[경고] 레지스트리 자동 등록 실패: {exc}", file=sys.stderr)
        return 0
    if args.command == "view":
        from ios_backup_vault.vault import Vault, VaultError
        from ios_backup_vault.viewer_data import ViewerData
        from ios_backup_vault.web import create_app
        import uvicorn
        pw = getpass.getpass("백업 암호: ")
        vault = Vault(backup_directory=args.backup, passphrase=pw)
        try:
            vault.open()
        except VaultError as exc:
            print(f"[오류] {exc}", file=sys.stderr); return 1
        print(f"복호화 OK — http://127.0.0.1:{args.port} (Ctrl+C 종료). 외부 전송 없음.")
        uvicorn.run(create_app(ViewerData(vault)), host="127.0.0.1", port=args.port, log_level="warning")
        return 0
    if args.command == "info":
        try:
            m = read_backup_metadata(args.backup, with_size=True, reveal_pii=args.reveal)
        except ValueError as exc:
            print(f"[오류] {exc}", file=sys.stderr); return 1
        except OSError as exc:
            print(f"[오류] 경로 접근 실패: {exc}", file=sys.stderr); return 1
        _print_meta(m)
        return 0
    if args.command == "add":
        try:
            entry = registry.add(
                registry.registry_path(), args.path, label=args.label,
                now_iso=datetime.now().isoformat(timespec="seconds"),
            )
        except ValueError as exc:
            print(f"[오류] {exc}", file=sys.stderr); return 1
        except OSError as exc:
            print(f"[오류] 경로 접근 실패: {exc}", file=sys.stderr); return 1
        print(f"등록 완료: {entry['path']}")
        return 0
    if args.command == "list":
        items = registry.load(registry.registry_path())
        if not items:
            print("등록된 백업이 없습니다. 'add --path <폴더>'로 등록하세요.")
            return 0
        print(f"{'기기':<12} {'iOS':<7} {'이미징':<20} {'용량':>8} {'암호':<4} {'전체':<4} 경로")
        for b in items:
            try:
                m = read_backup_metadata(b["path"], with_size=True)
            except (ValueError, OSError):
                print(f"{'(없음)':<12} {'-':<7} {'-':<20} {'-':>8} {'-':<4} {'-':<4} {b['path']}")
                continue
            size = "-" if m["size_bytes"] is None else _gb(m["size_bytes"])
            enc = "ON" if m["is_encrypted"] else "off"
            full = "예" if m["is_full"] else "아니오"
            print(
                f"{m['device_name']:<12} {m['ios_version']:<7} {m['imaged_at']:<20} "
                f"{size:>8} {enc:<4} {full:<4} {m['path']}"
            )
        return 0
    if args.command == "manage":
        from ios_backup_vault.manage_web import create_manager_app
        import uvicorn
        reg = registry.registry_path()
        print(f"관리 대시보드 — http://127.0.0.1:{args.port} (Ctrl+C 종료). 외부 전송 없음.")
        uvicorn.run(create_manager_app(reg), host="127.0.0.1", port=args.port, log_level="warning")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
