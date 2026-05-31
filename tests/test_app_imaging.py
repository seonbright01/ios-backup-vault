"""P9 Task3: 이미징 잡 — precheck/start/status(+stream), 동시1개, 완료 시 자동등록."""
import json

from fastapi.testclient import TestClient

from ios_backup_vault.app import create_app
from ios_backup_vault.imaging import ImagingManager


def _meta(path, *, with_size=True, reveal_pii=False):
    return {"path": path, "device_name": "iPhone X", "id": "x",
            "udid": "U", "product_type": "", "ios_version": "", "build": "",
            "imaged_at": "", "snapshot_date": "", "last_backup_date": "",
            "is_encrypted": False, "is_full": False, "snapshot_state": "",
            "backup_state": "", "app_count": 0, "size_bytes": None,
            "serial": "", "imei": "", "iccid": "", "phone": ""}


def _empty_reg(tmp_path):
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps({"backups": []}), encoding="utf-8")
    return str(reg)


class FakeImagingRunning:
    """precheck/start/status를 즉시 제어하는 가짜 imaging."""
    def __init__(self, *, state="done", backup_path="/img/UDID9", error=None):
        self._state = state
        self._bp = backup_path
        self._error = error
        self.started = []

    def precheck(self, target):
        return {"udid": "U9", "fits": True, "free_bytes": 1000, "required_bytes": 100}

    def start(self, target):
        self.started.append(target)
        return "job123"

    def status(self, job_id):
        if job_id != "job123":
            return None
        out = {"job_id": job_id, "state": self._state, "log": "라인1\n라인2"}
        if self._state == "done":
            out["backup_path"] = self._bp
        if self._error:
            out["error"] = self._error
        return out

    def stream(self, job_id):
        yield {"text": "라인1", "kind": ""}
        if self._state == "done":
            yield {"state": "done", "backup_path": self._bp}
        elif self._state == "error":
            yield {"state": "error", "error": self._error}


def test_precheck_delegates(tmp_path):
    reg = _empty_reg(tmp_path)
    app = create_app(reg, imaging=FakeImagingRunning(), metadata_fn=_meta)
    client = TestClient(app)
    r = client.get("/api/imaging/precheck", params={"target": "/dest"})
    assert r.json()["udid"] == "U9"


def test_start_returns_job_id(tmp_path):
    reg = _empty_reg(tmp_path)
    img = FakeImagingRunning()
    app = create_app(reg, imaging=img, metadata_fn=_meta)
    client = TestClient(app)
    r = client.post("/api/imaging/start", json={"target": "/dest"})
    assert r.json()["job_id"] == "job123"
    assert img.started == ["/dest"]


def test_start_requires_target(tmp_path):
    reg = _empty_reg(tmp_path)
    app = create_app(reg, imaging=FakeImagingRunning(), metadata_fn=_meta)
    client = TestClient(app)
    r = client.post("/api/imaging/start", json={})
    assert r.status_code == 400


def test_status_done_auto_registers(tmp_path):
    reg = _empty_reg(tmp_path)
    added = {}

    def fake_add(reg_path, path, label="", now_iso=""):
        added["path"] = path
        added["label"] = label
        return {"path": path, "label": label}

    app = create_app(reg, imaging=FakeImagingRunning(state="done", backup_path="/img/UDID9"),
                     add_fn=fake_add, metadata_fn=_meta)
    client = TestClient(app)
    client.post("/api/imaging/start", json={"target": "/dest"})
    r = client.get("/api/imaging/status", params={"job_id": "job123"})
    assert r.json()["state"] == "done"
    assert added["path"] == "/img/UDID9"
    assert added["label"] == "iPhone X"  # metadata_fn device_name


def test_status_error_no_register(tmp_path):
    reg = _empty_reg(tmp_path)
    added = {}
    app = create_app(reg, imaging=FakeImagingRunning(state="error", error="실패"),
                     add_fn=lambda *a, **k: added.setdefault("called", True),
                     metadata_fn=_meta)
    client = TestClient(app)
    r = client.get("/api/imaging/status", params={"job_id": "job123"})
    assert r.json()["state"] == "error"
    assert "called" not in added


def test_status_unknown_job_404(tmp_path):
    reg = _empty_reg(tmp_path)
    app = create_app(reg, imaging=FakeImagingRunning(), metadata_fn=_meta)
    client = TestClient(app)
    r = client.get("/api/imaging/status", params={"job_id": "nope"})
    assert r.status_code == 404


def test_stream_emits_sse(tmp_path):
    reg = _empty_reg(tmp_path)
    added = {}
    app = create_app(reg, imaging=FakeImagingRunning(state="done", backup_path="/img/UDID9"),
                     add_fn=lambda rp, p, **k: added.setdefault("path", p),
                     metadata_fn=_meta)
    client = TestClient(app)
    r = client.get("/api/imaging/stream", params={"job_id": "job123"})
    assert "text/event-stream" in r.headers["content-type"]
    body = r.text
    assert "라인1" in body
    assert "done" in body
    assert added["path"] == "/img/UDID9"  # stream 완료도 자동등록


# ---- 실제 ImagingManager(주입 run_backup) ----

def test_manager_runs_and_completes():
    def fake_backup(target, emit):
        emit("핸드셰이크", "info")
        emit("전송 중")
        return target + "/UDID"

    mgr = ImagingManager(run_backup=fake_backup)
    job_id = mgr.start("/dest")
    # 백그라운드 스레드 완료 대기(스트림으로 종료까지 소진).
    events = list(mgr.stream(job_id))
    st = mgr.status(job_id)
    assert st["state"] == "done"
    assert st["backup_path"] == "/dest/UDID"
    assert any(e.get("state") == "done" for e in events)
    assert "핸드셰이크" in st["log"]


def test_manager_concurrent_blocked():
    import threading
    gate = threading.Event()

    def slow_backup(target, emit):
        gate.wait(timeout=2)
        return target

    mgr = ImagingManager(run_backup=slow_backup)
    mgr.start("/a")
    try:
        raised = False
        try:
            mgr.start("/b")
        except RuntimeError:
            raised = True
        assert raised
    finally:
        gate.set()


def test_manager_error_state():
    def boom(target, emit):
        emit("시작")
        raise RuntimeError("백업 실패")

    mgr = ImagingManager(run_backup=boom)
    job_id = mgr.start("/dest")
    list(mgr.stream(job_id))
    st = mgr.status(job_id)
    assert st["state"] == "error"
    assert "백업 실패" in st["error"]
