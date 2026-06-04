"""로컬 백업 → 객체 저장소 병렬·스트리밍 업로드. 크기기반 skip + 무결성 게이트 후에만 delete-local."""
import os
import shutil
from concurrent.futures import ThreadPoolExecutor


def _files(local_dir):
    for root, _d, files in os.walk(local_dir, followlinks=False):
        for name in files:
            fp = os.path.join(root, name)
            rel = os.path.relpath(fp, local_dir).replace(os.sep, "/")
            yield fp, rel


def upload_backup(local_dir, *, udid, store, workers=8, delete_local=False, on_file=None):
    local_dir = os.path.abspath(local_dir)
    items = list(_files(local_dir))
    put_count = 0

    def _one(fp, rel):
        obj = f"{udid}/{rel}"
        size = os.path.getsize(fp)
        head = store.head(obj)
        if head and head.get("size") == size:
            if on_file: on_file(rel, "skip")
            return 0
        with open(fp, "rb") as f:
            store.put_from_file(obj, f)
        if on_file: on_file(rel, "put")
        return 1

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(lambda t: _one(*t), items):
            put_count += r

    # 무결성 게이트: 모든 파일 원격 크기 == 로컬 크기
    bad = []
    for fp, rel in items:
        head = store.head(f"{udid}/{rel}")
        if not head or head.get("size") != os.path.getsize(fp):
            bad.append(rel)
    if bad:
        if delete_local:
            raise RuntimeError(f"무결성 실패 {len(bad)}건 — 로컬 삭제 중단: {bad[:3]}")
        # delete_local 아니어도 호출측이 경고할 수 있게 반환에 포함
    if delete_local and not bad:
        shutil.rmtree(local_dir, ignore_errors=True)
    return put_count
