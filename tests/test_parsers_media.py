from ios_backup_vault.parsers.media import list_media


def test_list_media_filters_images_videos():
    rows = [
        ("fid1", "CameraRollDomain", "Media/DCIM/100APPLE/IMG_0001.JPG"),
        ("fid3", "CameraRollDomain", "Media/DCIM/100APPLE/IMG_0003.MOV"),
        ("fid4", "CameraRollDomain", "Media/PhotoData/Thumbnails/x.ithmb"),
    ]
    items = list_media(rows)
    paths = [i["relative_path"] for i in items]
    assert "Media/DCIM/100APPLE/IMG_0001.JPG" in paths
    assert "Media/DCIM/100APPLE/IMG_0003.MOV" in paths
    assert all("Thumbnails" not in p for p in paths)
    assert {i["kind"] for i in items} <= {"image", "video"}
