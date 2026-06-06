"""P9 통합 앱(대시보드 + 뷰어 + 라이브 이미징) — 로컬 전용 FastAPI.

create_app(registry_path, *, vault_factory, folder_picker, imaging, ...) → FastAPI.
모든 외부 I/O는 주입 가능(테스트 용이). 127.0.0.1 바인드는 호출자(cli)가 담당.
패스프레이즈·PII는 메모리에서만, 로그/에러로 유출하지 않는다.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import os
import tempfile

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


def _default_cloud_store_factory():
    """클라우드 store는 cloud.json 설정으로 cli._make_store가 만든다(ADC)."""
    from ios_backup_vault.cli import _make_store
    return _make_store()


# 메타 파일 캐시 보호키(퇴출 제외) — 라이브러리 필수 + 표시용.
_CLOUD_PROTECTED = {"Manifest.plist", "Manifest.db", "Info.plist", "Status.plist"}
_CACHE_CAP_BYTES = 8 * 1024 * 1024 * 1024  # 기본 캐시 상한(8GB)


def _default_cloud_vault_factory(*, store, udid, passphrase):
    """클라우드 udid용 Vault(CloudBackend + BlobCache). BlobCache 루트 == cache_dir."""
    from iphone_backup_decrypt import EncryptedBackup

    from ios_backup_vault.blob_cache import BlobCache
    from ios_backup_vault.cloud_backend import CloudBackend
    from ios_backup_vault.paths import cache_root

    cache_dir = os.path.join(cache_root(), udid)
    cache = BlobCache(cache_dir, _CACHE_CAP_BYTES, protected=_CLOUD_PROTECTED)
    backend = CloudBackend(
        store=store, udid=udid, cache_dir=cache_dir,
        inner_factory=lambda d: EncryptedBackup(backup_directory=d, passphrase=passphrase),
        blob_cache=cache,
    )
    return Vault(backend=backend)


def _dir_size_bytes(path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def _parse_range(header, total):
    """`bytes=start-end` → (start, end_inclusive) 또는 잘못/미지정이면 None."""
    if not header or not header.startswith("bytes="):
        return None
    spec = header[len("bytes="):].split(",")[0].strip()
    if "-" not in spec:
        return None
    lo, hi = spec.split("-", 1)
    try:
        if lo == "":  # 마지막 N바이트(suffix)
            n = int(hi)
            if n <= 0:
                return None
            start = max(0, total - n)
            return start, total - 1
        start = int(lo)
        end = int(hi) if hi else total - 1
    except ValueError:
        return None
    end = min(end, total - 1)
    if start > end or start < 0:
        return None
    return start, end


def _media_response(content: bytes, mime: str, request):
    """미디어 바이트를 StreamingResponse로. Range 헤더 있으면 206 부분 응답(비디오 seek)."""
    total = len(content)
    rng = _parse_range(request.headers.get("range"), total)
    if rng is None:
        return StreamingResponse(
            iter((content,)), media_type=mime,
            headers={"Accept-Ranges": "bytes", "Content-Length": str(total)},
        )
    start, end = rng
    chunk = content[start:end + 1]
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Range": f"bytes {start}-{end}/{total}",
        "Content-Length": str(len(chunk)),
    }
    return StreamingResponse(iter((chunk,)), status_code=206, media_type=mime, headers=headers)


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
    cloud_store_factory=_default_cloud_store_factory,
    cloud_vault_factory=_default_cloud_vault_factory,
    cloud_config_exists=None,
) -> FastAPI:
    if cloud_config_exists is None:
        from ios_backup_vault.paths import cloud_config_path
        cloud_config_exists = lambda: os.path.exists(cloud_config_path())

    app = FastAPI(title="ios-backup-vault")

    # 열린 백업: id -> ViewerData (단일/다중 모두 허용; 단일 활성 흐름은 프론트가 관리)
    opened: dict[str, object] = {}
    vaults: dict[str, object] = {}

    if imaging is None:
        from ios_backup_vault.imaging import ImagingManager
        from ios_backup_vault import uploader

        def _default_upload_fn(backup_path, emit):
            udid = os.path.basename(backup_path.rstrip("/"))
            store = cloud_store_factory()
            emit(f"클라우드 업로드 시작 (udid={udid})…", "info")
            count = uploader.upload_backup(
                backup_path, udid=udid, store=store, delete_local=True,
                on_file=lambda rel, act: emit(f"[{act}] {rel}", ""),
            )
            emit("클라우드 업로드 완료 — 로컬 스테이징 삭제됨", "ok")
            return {"cloud_udid": udid, "uploaded": int(count or 0)}

        imaging = ImagingManager(upload_fn=_default_upload_fn)

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
        except (ValueError, OSError):
            return JSONResponse({"error": "메타데이터를 읽지 못했습니다(백업 폴더 확인)."}, status_code=200)
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
    async def api_media_bytes(backup_id: str, file_id: str, request: Request):
        v, err = _viewer_or_409(backup_id)
        if err:
            return err
        got = v.media_bytes(file_id)
        if got is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        content, mime = got
        return _media_response(content, mime, request)

    @app.get("/api/backups/{backup_id}/files")
    async def api_files(backup_id: str):
        v, err = _viewer_or_409(backup_id)
        if err:
            return err
        return v.files()

    @app.get("/api/backups/{backup_id}/files/{file_id}")
    async def api_file_bytes(backup_id: str, file_id: str, request: Request):
        v, err = _viewer_or_409(backup_id)
        if err:
            return err
        got = v.file_bytes(file_id)
        if got is None:
            return JSONResponse({"error": "파일을 찾을 수 없습니다."}, status_code=404)
        content, mime = got
        return _media_response(content, mime, request)

    @app.post("/api/backups/{backup_id}/export")
    async def api_export(backup_id: str, payload: dict):
        v, err = _viewer_or_409(backup_id)
        if err:
            return err
        name, content, mime = v.export(payload)
        return Response(content=content, media_type=mime,
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})

    # ---- 클라우드(GCS) ----
    def _cloud_meta(store, udid, reveal=False):
        """udid의 Status/Info.plist를 임시 파일로 받아 metadata 파싱. 실패는 부분 표기."""
        out = {"udid": udid}
        tmp_dir = tempfile.mkdtemp(prefix="cloudmeta-")
        try:
            for name in ("Info.plist", "Manifest.plist", "Status.plist"):
                data = store.get(f"{udid}/{name}")
                if data is not None:
                    with open(os.path.join(tmp_dir, name), "wb") as f:
                        f.write(data)
            try:
                m = metadata_fn(tmp_dir, with_size=False, reveal_pii=reveal)
                m["udid"] = udid
                out = m
            except (ValueError, OSError, KeyError) as exc:
                out["error"] = str(exc)
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return out

    @app.get("/api/cloud/backups")
    async def api_cloud_backups():
        try:
            store = cloud_store_factory()
            udids = store.list_udids()
        except Exception:  # noqa: BLE001 — 미설정/오프라인은 UI 오류로 표기(원본 예외 비노출)
            return JSONResponse({"error": "클라우드 설정/인증 오류 — cloud-config 및 ADC 인증을 확인하세요."},
                                status_code=200)
        return [_cloud_meta(store, u) for u in udids]

    @app.get("/api/cloud/backups/{udid}")
    async def api_cloud_backup_meta(udid: str, reveal: int = 0):
        if not udid or not all(ch.isalnum() or ch == "-" for ch in udid):
            return JSONResponse({"error": "잘못된 udid"}, status_code=400)
        try:
            store = cloud_store_factory()
        except Exception:  # noqa: BLE001 — 원본 예외 비노출
            return JSONResponse({"error": "클라우드 설정/인증 오류 — cloud-config 및 ADC 인증을 확인하세요."},
                                status_code=200)
        return _cloud_meta(store, udid, reveal=bool(reveal))

    @app.post("/api/cloud/open")
    async def api_cloud_open(payload: dict):
        udid = (payload or {}).get("udid", "") or ""
        passphrase = (payload or {}).get("passphrase", "") or ""
        if not udid or not all(ch.isalnum() or ch == "-" for ch in udid):
            return JSONResponse({"error": "udid가 필요합니다."}, status_code=400)
        try:
            store = cloud_store_factory()
        except Exception:  # noqa: BLE001 — 원본 예외 비노출
            return JSONResponse({"error": "클라우드 설정/인증 오류 — cloud-config 및 ADC 인증을 확인하세요."},
                                status_code=200)
        cloud_id = "cloud-" + udid
        try:
            vault = cloud_vault_factory(store=store, udid=udid, passphrase=passphrase)
            vault.open()
        except VaultError as exc:
            return {"error": str(exc)}
        except Exception:  # noqa: BLE001 — 네트워크/메타 누락 등(원본 예외 비노출)
            return JSONResponse({"error": "클라우드 연결 또는 메타데이터 오류 — 네트워크/버킷 상태를 확인하세요."},
                                status_code=200)
        opened[cloud_id] = viewer_factory(vault)
        vaults[cloud_id] = vault
        return {"ok": True, "id": cloud_id, "udid": udid}

    @app.get("/api/cache/size")
    async def api_cache_size():
        from ios_backup_vault.paths import cache_root
        root = cache_root()
        return {"bytes": _dir_size_bytes(root) if os.path.isdir(root) else 0}

    @app.post("/api/cache/clear")
    async def api_cache_clear():
        import shutil
        from ios_backup_vault.paths import cache_root
        # 열린 클라우드 백업은 먼저 닫는다(캐시 사용 중 파일 정리).
        for bid in [k for k in list(vaults) if k.startswith("cloud-")]:
            _do_close(bid)
        root = cache_root()
        if os.path.isdir(root):
            shutil.rmtree(root, ignore_errors=True)
        return {"ok": True}

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
        payload = payload or {}
        target = payload.get("target", "") or ""
        destination = payload.get("destination", "local") or "local"
        if not target:
            return JSONResponse({"error": "저장 폴더(target)가 필요합니다."}, status_code=400)
        if destination not in ("local", "cloud"):
            return JSONResponse({"error": "알 수 없는 목적지입니다."}, status_code=400)
        if destination == "cloud" and not cloud_config_exists():
            return JSONResponse({"error": "클라우드 설정이 없습니다 — 먼저 클라우드(cloud-config)를 설정하세요."}, status_code=400)
        try:
            job_id = imaging.start(target, destination=destination)
        except RuntimeError:  # 동시 1개 제한
            return JSONResponse({"error": "이미 이미징이 진행 중입니다."}, status_code=409)
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
        # 클라우드 완료 이벤트는 로컬 경로가 없으므로 등록하지 않는다(벨트+멜빵).
        if st.get("destination") == "cloud":
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
