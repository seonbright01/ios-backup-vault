from ios_backup_vault.viewer_data import ViewerData


class _FakeVault:
    def __init__(self, rows, blobs):
        self._rows = rows          # [(fileID, domain, relativePath)]
        self._blobs = blobs        # {(domain, rel): (bytes, mtime)}

    def manifest_files(self, domain=None):
        if domain is None:
            return list(self._rows)
        return [r for r in self._rows if r[1] == domain]

    def read_bytes_and_mtime(self, rel, *, domain_like=None):
        return self._blobs.get((domain_like, rel))


def _vd():
    rows = [
        ("f1", "AppDomain-com.iwilab.KakaoTalk", "Library/PrivateDocuments/DownloadFiles/report.pdf"),
        ("f2", "AppDomain-com.iwilab.KakaoTalk", "Library/PrivateDocuments/DownloadFiles/doc.hwp"),
        ("f3", "AppDomain-com.iwilab.KakaoTalk", "Documents/photo.jpg"),
        ("f4", "AppDomain-com.iwilab.KakaoTalk", "Documents/photo_thumb.jpg"),   # 썸네일 → 제외
        ("f5", "CameraRollDomain", "Media/DCIM/IMG_0001.HEIC"),                    # 카메라롤 → 제외
        ("f6", "AppDomain-x", "Library/Caches/cached.jpg"),                        # 캐시 노이즈 → 제외
        ("f7", "AppDomain-x", "Library/Application Support/data.sqlite"),          # 비화이트리스트 → 제외
    ]
    blobs = {("AppDomain-com.iwilab.KakaoTalk", "Library/PrivateDocuments/DownloadFiles/report.pdf"): (b"%PDF-1.4 hi", 111.0)}
    return ViewerData(_FakeVault(rows, blobs))


def test_files_filters_and_categorizes():
    vd = _vd()
    items = vd.files()
    ids = {i["file_id"] for i in items}
    assert ids == {"f1", "f2", "f3"}                    # 썸네일·카메라롤·캐시·비문서 제외
    by = {i["file_id"]: i for i in items}
    assert by["f1"]["category"] == "document" and by["f1"]["ext"] == "pdf"
    assert by["f2"]["category"] == "document" and by["f2"]["ext"] == "hwp"
    assert by["f3"]["category"] == "image"
    assert by["f1"]["app"] == "카카오톡" and by["f1"]["filename"] == "report.pdf"


def test_file_bytes_reads_blob():
    vd = _vd()
    vd.files()
    raw, mime = vd.file_bytes("f1")
    assert raw == b"%PDF-1.4 hi" and mime == "application/pdf"
    assert vd.file_bytes("nope") is None
