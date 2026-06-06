import time
from ios_backup_vault.imaging import ImagingManager


def _wait(mgr, job_id, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        st = mgr.status(job_id)
        if st and st["state"] != "running":
            return st
        time.sleep(0.01)
    raise AssertionError("이미징 잡이 시간 내 종료되지 않음")


def test_local_destination_does_not_upload():
    calls = {}
    mgr = ImagingManager(
        run_backup=lambda target, emit: target + "/UDID",
        upload_fn=lambda bp, emit: calls.setdefault("uploaded", bp),
    )
    jid = mgr.start("/tmp/x", destination="local")
    st = _wait(mgr, jid)
    assert st["state"] == "done" and st["backup_path"] == "/tmp/x/UDID"
    assert "uploaded" not in calls


def test_cloud_destination_uploads_then_omits_backup_path():
    calls = {}
    def fake_upload(bp, emit):
        calls["uploaded"] = bp
        emit("업로드 중…", "info")
        return {"cloud_udid": "UDID", "uploaded": 3}
    mgr = ImagingManager(
        run_backup=lambda target, emit: target + "/UDID",
        upload_fn=fake_upload,
    )
    jid = mgr.start("/tmp/x", destination="cloud")
    st = _wait(mgr, jid)
    assert st["state"] == "done"
    assert calls["uploaded"] == "/tmp/x/UDID"
    assert st.get("backup_path") is None          # 클라우드는 로컬 삭제 → backup_path 없음
    assert st["result"]["cloud_udid"] == "UDID" and st["result"]["uploaded"] == 3


def test_cloud_upload_failure_marks_error():
    def boom(bp, emit):
        raise RuntimeError("업로드 실패")
    mgr = ImagingManager(
        run_backup=lambda target, emit: target + "/UDID",
        upload_fn=boom,
    )
    jid = mgr.start("/tmp/x", destination="cloud")
    st = _wait(mgr, jid)
    assert st["state"] == "error" and "업로드 실패" in st["error"]


def test_cloud_without_upload_fn_errors():
    mgr = ImagingManager(run_backup=lambda target, emit: target + "/UDID")  # upload_fn 없음
    jid = mgr.start("/tmp/x", destination="cloud")
    st = _wait(mgr, jid)
    assert st["state"] == "error" and "구성되지" in st["error"]
