"""백그라운드 이미징 잡 매니저 + 사전점검 어댑터.

- 동시 1개만 실행(running 중 start → RuntimeError).
- device.run_backup의 스트리밍 출력을 라인별로 버퍼에 append, 종료 시 state/backup_path 갱신.
- 테스트에는 가짜 imaging 객체를 주입한다(이 모듈은 실제 기본 구현).
"""
from __future__ import annotations

import os
import queue
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field

from ios_backup_vault import device
from ios_backup_vault.cli import run_precheck


def _line_buffering_runner_factory(on_line):
    """subprocess 출력을 라인별 콜백으로 흘리는 runner(device.run_backup용)."""
    import subprocess

    def _runner(args, *, timeout=None):
        try:
            proc = subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
        except FileNotFoundError as exc:
            raise device.DeviceError(
                f"명령을 찾을 수 없음: {args[0]} (libimobiledevice 설치 필요)"
            ) from exc
        assert proc.stdout is not None
        for line in proc.stdout:
            on_line(line.rstrip("\n"))
        rc = proc.wait()
        return device.CommandResult(rc, b"", "")

    return _runner


@dataclass
class _Job:
    job_id: str
    target: str
    state: str = "running"          # running | done | error
    backup_path: str | None = None
    error: str | None = None
    lines: list[str] = field(default_factory=list)
    events: "queue.Queue" = field(default_factory=queue.Queue)
    lock: threading.Lock = field(default_factory=threading.Lock)


class ImagingManager:
    def __init__(self, *, run_backup=None, precheck_fn=None, max_log_lines=2000):
        # 실제 백업 실행기/사전점검(주입 가능, 기본은 device 기반).
        self._run_backup = run_backup or self._default_run_backup
        self._precheck_fn = precheck_fn or self._default_precheck
        self._max = max_log_lines
        self._job: _Job | None = None
        self._lock = threading.Lock()

    # ---- 사전점검 ----
    def precheck(self, target: str) -> dict:
        return self._precheck_fn(target)

    def _default_precheck(self, target: str) -> dict:
        try:
            report = run_precheck(
                target or ".",
                list_udids=device.list_udids,
                is_paired=device.is_paired,
                device_info=device.device_info,
                disk_free=lambda path: shutil.disk_usage(path).free,
            )
        except device.DeviceNotConnected as exc:
            return {"error": str(exc), "hint": "케이블을 연결하고 폰 잠금을 해제하세요."}
        except device.DeviceNotTrusted as exc:
            return {"error": str(exc), "hint": "폰에서 '이 컴퓨터를 신뢰'를 누르세요."}
        except device.DeviceError as exc:
            return {"error": f"기기 통신 실패: {exc}"}
        except OSError as exc:
            return {"error": f"대상 경로 접근 실패: {exc}"}
        s, e = report.state, report.estimate
        return {
            "udid": s.udid,
            "ios_version": s.ios_version,
            "backup_encryption_enabled": s.backup_encryption_enabled,
            "estimated_backup_bytes": e.estimated_backup_bytes,
            "free_bytes": e.free_bytes,
            "required_bytes": e.required_bytes,
            "fits": e.fits,
            "margin_bytes": e.margin_bytes,
        }

    # ---- 잡 실행 ----
    def start(self, target: str) -> str:
        with self._lock:
            if self._job is not None and self._job.state == "running":
                raise RuntimeError("이미 진행 중인 이미징 작업이 있습니다(동시 1개만 가능).")
            job = _Job(job_id=uuid.uuid4().hex[:12], target=target)
            self._job = job
        t = threading.Thread(target=self._run, args=(job,), daemon=True)
        t.start()
        return job.job_id

    def _run(self, job: _Job) -> None:
        def _emit(text: str, kind: str = "") -> None:
            with job.lock:
                job.lines.append(text)
                if len(job.lines) > self._max:
                    del job.lines[: len(job.lines) - self._max]
            job.events.put({"text": text, "kind": kind})

        try:
            backup_path = self._run_backup(job.target, _emit)
            with job.lock:
                job.state = "done"
                job.backup_path = backup_path
            job.events.put({"state": "done", "backup_path": backup_path})
        except Exception as exc:  # noqa: BLE001 — 모든 실패를 잡 상태로 수렴
            with job.lock:
                job.state = "error"
                job.error = str(exc)
            job.events.put({"state": "error", "error": str(exc)})

    def _default_run_backup(self, target: str, emit) -> str:
        """device.run_backup을 라인 콜백 runner로 실행. backup 폴더 경로 반환."""
        udids = device.list_udids()
        if not udids:
            raise device.DeviceNotConnected("USB에 연결된 iOS 기기가 없습니다.")
        udid = udids[0]
        emit(f"기기 {udid} 백업 시작…", "info")
        runner = _line_buffering_runner_factory(lambda ln: emit(ln, ""))
        device.run_backup(udid, target, runner=runner)
        # idevicebackup2는 target/<udid>/ 아래에 백업을 저장한다.
        candidate = os.path.join(target, udid)
        backup_path = candidate if os.path.isdir(candidate) else target
        emit("백업 완료", "ok")
        return backup_path

    # ---- 상태/스트림 ----
    def status(self, job_id: str) -> dict | None:
        job = self._job
        if job is None or job.job_id != job_id:
            return None
        with job.lock:
            out = {
                "job_id": job.job_id,
                "state": job.state,
                "log": "\n".join(job.lines[-200:]),
            }
            if job.backup_path:
                out["backup_path"] = job.backup_path
            if job.error:
                out["error"] = job.error
        return out

    def stream(self, job_id: str):
        """SSE용 제너레이터: 누적 라인 먼저 흘린 뒤 큐를 폴링한다."""
        job = self._job
        if job is None or job.job_id != job_id:
            return
        with job.lock:
            backlog = list(job.lines)
            done = job.state != "running"
        for ln in backlog:
            yield {"text": ln, "kind": ""}
        while True:
            try:
                event = job.events.get(timeout=0.5)
                yield event
                if event.get("state") in ("done", "error"):
                    return
            except queue.Empty:
                with job.lock:
                    if job.state != "running":
                        # 종료 후 남은 이벤트 비우고 종료 신호.
                        yield {"state": job.state,
                               **({"backup_path": job.backup_path} if job.backup_path else {}),
                               **({"error": job.error} if job.error else {})}
                        return
                time.sleep(0)
            if done:
                # running이 아니었다면 backlog만 보내고 한 번 더 종료 이벤트 확인.
                pass
