"""Vault.read_bytes_and_mtime의 클라우드 read 분기 단위테스트(P10v2 Task7).

클라우드 backend(fetch_blob+_resolve 보유)면 fileID는 executor(단일 워커 스레드)에서
resolve(SQLite 스레드 안전)하고, 블롭 fetch는 executor 밖(호출 스레드)에서 먼저 수행한 뒤
기존 extract 경로를 실행한다. 로컬 backend(두 속성 없음)는 기존 경로 그대로(무회귀).
"""
import threading

import pytest

from ios_backup_vault.vault import Vault


@pytest.fixture(autouse=True)
def _isolate_vault_home(monkeypatch, tmp_path):
    # 임시 평문이 생성되는 캐시루트를 tmp로 격리(실제 홈 오염 방지).
    monkeypatch.setenv("IOS_BACKUP_VAULT_HOME", str(tmp_path))


class CloudFakeBackend:
    """fetch_blob+_resolve를 가진 가짜 클라우드 backend.

    각 호출이 일어난 스레드 이름을 기록해 executor 안/밖을 구분한다.
    """

    def __init__(self):
        self.resolve_threads = []
        self.fetch_threads = []
        self.extract_threads = []
        self.resolve_args = []
        self.fetch_args = []

    def _resolve(self, rel, domain_like):
        self.resolve_threads.append(threading.current_thread().name)
        self.resolve_args.append((rel, domain_like))
        return "a1b2" + "0" * 36  # 40-hex fileID

    def fetch_blob(self, fid):
        self.fetch_threads.append(threading.current_thread().name)
        self.fetch_args.append(fid)
        return None

    def extract_file(self, *, relative_path, domain_like=None, output_filename):
        self.extract_threads.append(threading.current_thread().name)
        with open(output_filename, "wb") as f:
            f.write(b"PLAIN")


class LocalFakeBackend:
    """fetch_blob/_resolve 없는 로컬 backend(기존 경로)."""

    def __init__(self):
        self.extract_threads = []

    def extract_file(self, *, relative_path, domain_like=None, output_filename):
        self.extract_threads.append(threading.current_thread().name)
        with open(output_filename, "wb") as f:
            f.write(b"PLAIN")


def test_cloud_backend_resolves_in_executor_and_fetches_outside():
    be = CloudFakeBackend()
    v = Vault(backend=be)
    main_thread = threading.current_thread().name

    data, _mtime = v.read_bytes_and_mtime("Library/SMS/sms.db", domain_like="%")

    # extract가 실제로 실행되어 평문을 읽어옴
    assert data == b"PLAIN"
    # _resolve는 정확히 1회, 받은 인자 그대로 전달
    assert be.resolve_args == [("Library/SMS/sms.db", "%")]
    # fetch_blob은 resolve가 돌려준 fileID로 정확히 1회
    assert be.fetch_args == ["a1b2" + "0" * 36]
    # _resolve는 executor(워커 스레드)에서 — SQLite 스레드 안전
    assert be.resolve_threads and all(
        t != main_thread for t in be.resolve_threads
    )
    # fetch_blob은 executor 밖(호출 스레드=메인)에서 — 네트워크 직렬화 방지
    assert be.fetch_threads == [main_thread]
    v.close()


def test_cloud_backend_skips_fetch_when_resolve_returns_none():
    be = CloudFakeBackend()
    be._resolve = lambda rel, domain_like: None  # 매니페스트에 없음
    v = Vault(backend=be)

    v.read_bytes_and_mtime("nope", domain_like="%")

    # resolve가 None이면 fetch_blob을 호출하지 않음
    assert be.fetch_threads == []
    v.close()


def test_local_backend_unchanged_no_resolve_or_fetch():
    be = LocalFakeBackend()
    v = Vault(backend=be)
    main_thread = threading.current_thread().name

    data, _mtime = v.read_bytes_and_mtime("Library/SMS/sms.db")

    assert data == b"PLAIN"
    # 로컬 backend는 extract만 executor에서 — 기존 경로 그대로
    assert be.extract_threads and all(t != main_thread for t in be.extract_threads)
    v.close()
