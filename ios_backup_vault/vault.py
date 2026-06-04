"""암호화 백업 복호화 래퍼. 모든 동작 로컬. 비밀번호는 메모리에서만.

iphone_backup_decrypt의 sqlite 연결은 생성된 스레드에서만 사용 가능하다.
FastAPI는 요청을 여러 스레드에서 처리하므로, 백엔드 생성과 모든 접근을
단일 전용 워커 스레드(_executor)로 직렬화해 교차 스레드 오류를 차단한다.
"""
from __future__ import annotations

import concurrent.futures
import os
import tempfile


class VaultError(Exception):
    """복호화/열람 실패(잘못된 비밀번호 등)."""


def _make_default_backend(backup_directory: str, passphrase: str):
    from iphone_backup_decrypt import EncryptedBackup
    return EncryptedBackup(backup_directory=backup_directory, passphrase=passphrase)


def _ensure_tmp_dir():
    """임시 평문 파일을 보호 위치(캐시루트)에 생성하기 위한 디렉터리.

    캐시루트 생성에 실패하면 None을 반환해 시스템 기본 temp로 폴백한다.
    """
    try:
        from ios_backup_vault.paths import cache_root
        d = cache_root()
        os.makedirs(d, mode=0o700, exist_ok=True)
        return d
    except OSError:
        return None


class Vault:
    def __init__(self, *, backup_directory: str | None = None, passphrase: str | None = None, backend=None):
        # 단일 워커 스레드: 백엔드(및 그 sqlite 연결)를 한 스레드에 고정.
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="vault")
        if backend is None:
            if backup_directory is None or passphrase is None:
                self._executor.shutdown(wait=False)
                raise VaultError("backup_directory와 passphrase 또는 backend가 필요합니다.")
            # 백엔드 생성도 워커 스레드에서 수행해 연결이 그 스레드에 생기도록.
            backend = self._call(_make_default_backend, backup_directory, passphrase)
        self._backend = backend

    def _call(self, fn, *args, **kwargs):
        """모든 백엔드 접근을 단일 워커 스레드에서 실행."""
        return self._executor.submit(fn, *args, **kwargs).result()

    def open(self) -> None:
        try:
            self._call(self._backend.test_decryption)
        except Exception as exc:
            raise VaultError("백업 복호화 실패 — 비밀번호가 틀렸거나 백업이 손상되었을 수 있습니다.") from exc

    def read_bytes_and_mtime(self, relative_path: str, *, domain_like: str | None = None):
        """(bytes, mtime) 반환. mtime은 백업 Manifest의 원본 LastModified(라이브러리가
        추출 시 os.utime로 파일에 복원). 없으면 mtime=None. 파일 없으면 None 반환."""
        # 클라우드 backend(fetch_blob+_resolve 보유)는 SQLite 단일스레드(_executor)에
        # 네트워크 fetch가 묶이지 않도록, fileID는 executor에서 resolve(SQLite)하고
        # 블롭 fetch는 executor 밖(호출 스레드)에서 먼저 수행한다.
        # 로컬 backend는 두 속성이 없어 기존 경로 그대로(무회귀).
        fetch_blob = getattr(self._backend, "fetch_blob", None)
        resolve = getattr(self._backend, "_resolve", None)
        if fetch_blob and resolve:
            fid = self._call(resolve, relative_path, domain_like)  # executor 내 SQLite
            if fid:
                fetch_blob(fid)               # 네트워크: 호출 스레드(executor 밖)
        # 인메모리 복호화(extract_file_as_bytes)는 대용량 파일에서 크기가 어긋나므로,
        # 청크 방식 extract_file(디스크)로 복호화한 뒤 읽는다.
        # 임시 평문은 가능하면 캐시루트(보호 위치)에 생성한다.
        tmp_dir = _ensure_tmp_dir()
        fd, tmp = tempfile.mkstemp(prefix="vault-", dir=tmp_dir)
        os.close(fd)

        def _extract():
            self._backend.extract_file(
                relative_path=relative_path, domain_like=domain_like, output_filename=tmp
            )

        try:
            try:
                self._call(_extract)
            except FileNotFoundError:
                return None
            except Exception as exc:
                raise VaultError(f"'{relative_path}' 추출 실패({type(exc).__name__})") from exc
            try:
                mtime = os.path.getmtime(tmp)
            except OSError:
                mtime = None
            with open(tmp, "rb") as f:
                return f.read(), mtime
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def read_bytes(self, relative_path: str, *, domain_like: str | None = None) -> bytes | None:
        got = self.read_bytes_and_mtime(relative_path, domain_like=domain_like)
        return None if got is None else got[0]

    def manifest_files(self, domain: str | None = None) -> list:
        """매니페스트 Files 조회(단일 워커 스레드에서)."""
        sql = "SELECT fileID, domain, relativePath FROM Files"
        params: tuple = ()
        if domain is not None:
            sql += " WHERE domain = ?"
            params = (domain,)

        def _query():
            with self._backend.manifest_db_cursor() as cur:
                return cur.execute(sql, params).fetchall()

        try:
            return self._call(_query)
        except Exception as exc:
            raise VaultError(f"매니페스트 조회 실패: {exc}") from exc

    def find_files(self, *, domain_like: str | None = None, path_like: str | None = None) -> list:
        """flags=1(파일) 중 domain/relativePath LIKE 검색."""
        sql = "SELECT fileID, domain, relativePath FROM Files WHERE flags=1"
        params: list = []
        if domain_like is not None:
            sql += " AND domain LIKE ?"
            params.append(domain_like)
        if path_like is not None:
            sql += " AND relativePath LIKE ?"
            params.append(path_like)

        def _query():
            with self._backend.manifest_db_cursor() as cur:
                return cur.execute(sql, params).fetchall()

        try:
            return self._call(_query)
        except Exception as exc:
            raise VaultError(f"파일 검색 실패: {exc}") from exc

    def close(self) -> None:
        # 백엔드의 SQLite 연결을 소유 스레드(executor)에서 정리한다. 그렇지 않으면
        # 객체 GC 시점에 다른 스레드에서 close되며 sqlite3 ProgrammingError(스레드 위반)
        # 경고와 임시 연결 누수가 발생한다. CloudBackend는 실제 백엔드를 _inner로 감싼다.
        backend = self._backend

        def _cleanup_on_owner():
            # 스레드 종속 자원(SQLite 연결)만 소유 스레드에서 닫고 참조를 제거한다.
            # 임시폴더 삭제(rmtree)는 스레드 안전하므로 라이브러리 __del__에 맡긴다.
            # (라이브러리 _cleanup() 전체를 부르면 rmtree가 중복돼 GC 시 FileNotFound 경고)
            for obj in (backend, getattr(backend, "_inner", None)):
                if obj is None:
                    continue
                conn = getattr(obj, "_temp_manifest_db_conn", None)
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    obj._temp_manifest_db_conn = None

        try:
            self._call(_cleanup_on_owner)
        except Exception:
            pass
        self._executor.shutdown(wait=False)
