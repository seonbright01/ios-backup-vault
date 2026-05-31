import io
import time
import zipfile

from ios_backup_vault.viewer_data import ViewerData


class FakeVault:
    def __init__(self, media=None):
        self._media = media or {}

    def manifest_files(self, domain=None):
        return []

    def read_bytes(self, *a, **k):
        return None

    def find_files(self, **k):
        return []


_ITEMS = {"messages": [{"name": "A", "messages": [{"text": "hi", "timestamp": "t", "is_from_me": True}]}]}


def _viewer(media=None):
    v = ViewerData(FakeVault())
    if media is not None:
        v._media_index = {}
        v.media_bytes_and_mtime = lambda fid: media.get(fid)
    return v


def test_single_json():
    v = _viewer()
    name, content, mime = v.export({"formats": ["json"], "items": _ITEMS})
    assert name == "export.json"
    assert mime == "application/json"
    assert b"hi" in content


def test_two_formats_zip():
    v = _viewer()
    name, content, mime = v.export({"formats": ["json", "html"], "items": _ITEMS})
    assert name == "export.zip"
    assert mime == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(content))
    assert "export.json" in zf.namelist()
    assert "export.html" in zf.namelist()


def test_media_zip():
    mtime = 1700000000.0  # 2023-11
    v = _viewer(media={"FID1": (b"JPG", "image/jpeg", mtime)})
    name, content, mime = v.export(
        {"formats": ["json"], "items": _ITEMS, "media_file_ids": ["FID1"]})
    assert name == "export.zip"
    zf = zipfile.ZipFile(io.BytesIO(content))
    assert "media/FID1.jpg" in zf.namelist()
    assert zf.read("media/FID1.jpg") == b"JPG"
    # zip 항목 타임스탬프가 현재 시각이 아니라 원본 mtime이어야 함
    assert zf.getinfo("media/FID1.jpg").date_time[0] == time.localtime(mtime)[0]
