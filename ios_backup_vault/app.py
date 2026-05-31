"""P9 통합 앱(대시보드 + 뷰어 + 라이브 이미징) — 로컬 전용 FastAPI.

create_app(registry_path, *, vault_factory, folder_picker, imaging, ...) → FastAPI.
모든 외부 I/O는 주입 가능(테스트 용이). 127.0.0.1 바인드는 호출자(cli)가 담당.
패스프레이즈·PII는 메모리에서만, 로그/에러로 유출하지 않는다.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from ios_backup_vault import registry
from ios_backup_vault.metadata import read_backup_metadata
from ios_backup_vault.vault import Vault, VaultError

logger = logging.getLogger(__name__)

# 통합 SPA(시각 셸) — Task4에서 _INDEX_HTML로 채워진다.
from ios_backup_vault._index_html import INDEX_HTML as _INDEX_HTML


def _backup_id(path) -> str:
    """등록 경로에서 결정적 id 파생(sha1 앞 12자)."""
    return hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:12]


def _default_vault_factory(path, passphrase):
    return Vault(backup_directory=path, passphrase=passphrase)


def _default_viewer_factory(vault):
    from ios_backup_vault.viewer_data import ViewerData
    return ViewerData(vault)


def _osascript_pick():
    """macOS 네이티브 폴더 선택(choose folder). 취소→None, 비-macOS→{error}."""
    import subprocess
    import sys
    if sys.platform != "darwin":
        return {"error": "지원되지 않는 환경(폴더 선택은 macOS 전용)"}
    try:
        proc = subprocess.run(
            ["osascript", "-e", 'POSIX path of (choose folder)'],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        return {"error": "osascript를 찾을 수 없습니다."}
    if proc.returncode != 0:
        # 사용자가 취소하면 osascript는 비-0으로 종료한다.
        return None
    path = proc.stdout.strip()
    return path or None


def create_app(
    registry_path,
    *,
    vault_factory=_default_vault_factory,
    viewer_factory=_default_viewer_factory,
    folder_picker=_osascript_pick,
    imaging=None,
    metadata_fn=read_backup_metadata,
    add_fn=registry.add,
    remove_fn=registry.remove,
    preselect_id=None,
) -> FastAPI:
    app = FastAPI(title="ios-backup-vault")

    # 열린 백업: id -> ViewerData (단일/다중 모두 허용; 단일 활성 흐름은 프론트가 관리)
    opened: dict[str, object] = {}
    vaults: dict[str, object] = {}

    if imaging is None:
        from ios_backup_vault.imaging import ImagingManager
        imaging = ImagingManager()

    def _registered_paths() -> dict[str, dict]:
        """id -> 레지스트리 엔트리."""
        out = {}
        for b in registry.load(registry_path):
            out[_backup_id(b["path"])] = b
        return out

    def _meta(path, *, reveal=False):
        return metadata_fn(path, with_size=True, reveal_pii=reveal)

    def _viewer_or_409(backup_id: str):
        v = opened.get(backup_id)
        if v is None:
            return None, JSONResponse({"error": "열린 백업이 없습니다"}, status_code=409)
        return v, None

    # ---- 도메인 예외 핸들러 ----
    @app.exception_handler(VaultError)
    async def _vault_error(request: Request, exc: VaultError):
        return JSONResponse({"error": str(exc)}, status_code=503)

    # ---- SPA ----
    @app.get("/", response_class=HTMLResponse)
    async def index():
        if preselect_id:
            # 사전선택 id 주입(cli view --backup). esc 불필요: 영숫자 sha1 id.
            safe = "".join(ch for ch in str(preselect_id) if ch.isalnum())
            inject = f'<script>window.__PRESELECT_ID="{safe}";</script>'
            return _INDEX_HTML.replace("</body>", inject + "</body>", 1)
        return _INDEX_HTML

    # ---- 관리: 목록/메타/스캔/제거 ----
    @app.get("/api/backups")
    async def api_backups():
        out = []
        for b in registry.load(registry_path):
            bid = _backup_id(b["path"])
            try:
                m = _meta(b["path"])
            except (ValueError, OSError) as exc:
                m = {
                    "path": b["path"], "udid": "", "device_name": "(없음)",
                    "product_type": "", "ios_version": "", "build": "",
                    "imaged_at": "", "snapshot_date": "", "last_backup_date": "",
                    "is_encrypted": False, "is_full": False, "snapshot_state": "",
                    "backup_state": "", "app_count": 0, "size_bytes": None,
                    "serial": "", "imei": "", "iccid": "", "phone": "",
                    "error": str(exc),
                }
            m["id"] = bid
            m["label"] = b.get("label", "")
            m["opened"] = bid in opened
            out.append(m)
        return out

    @app.get("/api/backups/{backup_id}")
    async def api_backup_meta(backup_id: str, reveal: int = 0):
        entry = _registered_paths().get(backup_id)
        if entry is None:
            return JSONResponse({"error": "등록되지 않은 백업입니다."}, status_code=404)
        try:
            m = _meta(entry["path"], reveal=bool(reveal))
        except (ValueError, OSError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=200)
        m["id"] = backup_id
        m["label"] = entry.get("label", "")
        m["opened"] = backup_id in opened
        return m

    @app.post("/api/backups/scan-path")
    async def api_scan_path(payload: dict):
        path = (payload or {}).get("path", "")
        label = (payload or {}).get("label", "")
        try:
            entry = add_fn(registry_path, path, label=label)
        except (ValueError, OSError) as exc:
            return {"error": str(exc)}
        entry = dict(entry)
        entry["id"] = _backup_id(entry["path"])
        return entry

    @app.post("/api/backups/scan-folder")
    async def api_scan_folder():
        picked = folder_picker()
        if isinstance(picked, dict):  # {"error": ...}
            return picked
        if not picked:
            return {"error": "폴더 선택이 취소되었습니다."}
        try:
            entry = add_fn(registry_path, picked, label="")
        except (ValueError, OSError) as exc:
            return {"error": str(exc)}
        entry = dict(entry)
        entry["id"] = _backup_id(entry["path"])
        return entry

    @app.post("/api/backups/{backup_id}/remove")
    async def api_remove(backup_id: str):
        entry = _registered_paths().get(backup_id)
        if entry is None:
            return {"removed": False}
        # 열려 있으면 먼저 닫는다.
        _do_close(backup_id)
        return {"removed": remove_fn(registry_path, entry["path"])}

    # ---- 열기/닫기 ----
    @app.post("/api/backups/{backup_id}/open")
    async def api_open(backup_id: str, payload: dict):
        entry = _registered_paths().get(backup_id)
        if entry is None:
            return JSONResponse({"error": "등록되지 않은 백업입니다."}, status_code=404)
        passphrase = (payload or {}).get("passphrase", "") or ""
        try:
            vault = vault_factory(entry["path"], passphrase)
            vault.open()
        except VaultError as exc:
            return {"error": str(exc)}
        opened[backup_id] = viewer_factory(vault)
        vaults[backup_id] = vault
        try:
            meta = _meta(entry["path"])
        except (ValueError, OSError):
            meta = {"path": entry["path"], "id": backup_id}
        meta["id"] = backup_id
        return {"ok": True, "meta": meta}

    def _do_close(backup_id: str) -> bool:
        opened.pop(backup_id, None)
        vault = vaults.pop(backup_id, None)
        if vault is not None:
            try:
                vault.close()
            except Exception:  # noqa: BLE001 — 닫기 실패는 무시(이미 해제)
                pass
            return True
        return False

    @app.post("/api/backups/{backup_id}/close")
    async def api_close(backup_id: str):
        _do_close(backup_id)
        return {"ok": True}

    # ---- 뷰어(열림 필요) ----
    @app.get("/api/backups/{backup_id}/summary")
    async def api_summary(backup_id: str):
        v, err = _viewer_or_409(backup_id)
        return err or v.summary()

    @app.get("/api/backups/{backup_id}/messages")
    async def api_messages(backup_id: str):
        v, err = _viewer_or_409(backup_id)
        return err or v.messages()

    @app.get("/api/backups/{backup_id}/contacts")
    async def api_contacts(backup_id: str):
        v, err = _viewer_or_409(backup_id)
        return err or v.contacts()

    @app.get("/api/backups/{backup_id}/calls")
    async def api_calls(backup_id: str):
        v, err = _viewer_or_409(backup_id)
        return err or v.calls()

    @app.get("/api/backups/{backup_id}/media")
    async def api_media(backup_id: str, limit: int = 200, offset: int = 0):
        v, err = _viewer_or_409(backup_id)
        if err:
            return err
        items = v.media()
        return {"total": len(items), "offset": offset, "items": items[offset:offset + limit]}

    @app.get("/api/backups/{backup_id}/whatsapp")
    async def api_whatsapp(backup_id: str):
        v, err = _viewer_or_409(backup_id)
        return err or v.whatsapp()

    @app.get("/api/backups/{backup_id}/chatgpt")
    async def api_chatgpt(backup_id: str):
        v, err = _viewer_or_409(backup_id)
        return err or v.chatgpt()

    @app.get("/api/backups/{backup_id}/notes")
    async def api_notes(backup_id: str):
        v, err = _viewer_or_409(backup_id)
        return err or v.notes()

    @app.get("/api/backups/{backup_id}/appscan")
    async def api_appscan(backup_id: str):
        v, err = _viewer_or_409(backup_id)
        return err or v.appscan()

    @app.get("/api/backups/{backup_id}/search")
    async def api_search(backup_id: str, q: str = ""):
        v, err = _viewer_or_409(backup_id)
        return err or v.search(q)

    @app.get("/api/backups/{backup_id}/media/{file_id}")
    async def api_media_bytes(backup_id: str, file_id: str):
        v, err = _viewer_or_409(backup_id)
        if err:
            return err
        got = v.media_bytes(file_id)
        if got is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        content, mime = got
        return Response(content=content, media_type=mime)

    @app.post("/api/backups/{backup_id}/export")
    async def api_export(backup_id: str, payload: dict):
        v, err = _viewer_or_409(backup_id)
        if err:
            return err
        name, content, mime = v.export(payload)
        return Response(content=content, media_type=mime,
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})

    # ---- 이미징 ----
    @app.post("/api/imaging/pick-folder")
    async def api_pick_folder():
        picked = folder_picker()
        if isinstance(picked, dict):
            return picked
        if not picked:
            return {"error": "폴더 선택이 취소되었습니다."}
        return {"path": picked}

    @app.get("/api/imaging/precheck")
    async def api_precheck(target: str = ""):
        return imaging.precheck(target)

    @app.post("/api/imaging/start")
    async def api_imaging_start(payload: dict):
        target = (payload or {}).get("target", "") or ""
        if not target:
            return JSONResponse({"error": "저장 폴더(target)가 필요합니다."}, status_code=400)
        try:
            job_id = imaging.start(target)
        except RuntimeError as exc:  # 동시 1개 제한
            return JSONResponse({"error": str(exc)}, status_code=409)
        return {"job_id": job_id}

    @app.get("/api/imaging/status")
    async def api_imaging_status(job_id: str):
        st = imaging.status(job_id)
        if st is None:
            return JSONResponse({"error": "알 수 없는 작업입니다."}, status_code=404)
        _maybe_register_result(st)
        return st

    @app.get("/api/imaging/stream")
    async def api_imaging_stream(job_id: str):
        st = imaging.status(job_id)
        if st is None:
            return JSONResponse({"error": "알 수 없는 작업입니다."}, status_code=404)

        def _gen():
            import json as _json
            for event in imaging.stream(job_id):
                if event.get("state") in ("done", "error"):
                    _maybe_register_result(event)
                yield f"data: {_json.dumps(event, ensure_ascii=False)}\n\n"

        return StreamingResponse(_gen(), media_type="text/event-stream")

    _registered_results: set[str] = set()

    def _maybe_register_result(st: dict) -> None:
        if st.get("state") != "done":
            return
        bp = st.get("backup_path")
        if not bp or bp in _registered_results:
            return
        _registered_results.add(bp)
        try:
            label = ""
            try:
                label = metadata_fn(bp, with_size=False)["device_name"]
            except Exception:  # noqa: BLE001 — 라벨 추출 실패는 등록을 막지 않음
                pass
            add_fn(registry_path, bp, label=label)
        except Exception as exc:  # noqa: BLE001
            logger.warning("이미징 결과 자동 등록 실패: %s", exc)

    return app
