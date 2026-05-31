"""manifest Files → 카메라롤 미디어 목록. 순수(cursor 주입)."""
_IMAGE_EXT = (".jpg", ".jpeg", ".png", ".heic", ".gif")
_VIDEO_EXT = (".mov", ".mp4", ".m4v")


def _kind(path: str):
    p = path.lower()
    if p.endswith(_IMAGE_EXT):
        return "image"
    if p.endswith(_VIDEO_EXT):
        return "video"
    return None


def list_media(rows) -> list[dict]:
    """매니페스트 행(fileID, domain, relativePath) 목록에서 카메라롤 이미지/영상만 추출."""
    out = []
    for file_id, domain, rel in rows:
        if "Thumbnails" in rel:
            continue
        k = _kind(rel)
        if k is None:
            continue
        out.append({"file_id": file_id, "domain": domain, "relative_path": rel, "kind": k})
    return out
