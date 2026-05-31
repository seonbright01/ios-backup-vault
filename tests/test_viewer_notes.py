import gzip
import sqlite3
import tempfile
from ios_backup_vault.viewer_data import ViewerData
from ios_backup_vault.parsers.appscan import summarize_apps


def _varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def _build_proto(text):
    def ld(fn, payload):
        return bytes([(fn << 3) | 2]) + _varint(len(payload)) + payload
    return ld(2, ld(3, ld(2, text.encode("utf-8"))))


def _make_db_bytes():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        path = tf.name
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE ZICNOTEDATA (Z_PK INTEGER PRIMARY KEY, ZNOTE INTEGER, ZDATA BLOB)")
        conn.execute(
            "CREATE TABLE ZICCLOUDSYNCINGOBJECT ("
            "Z_PK INTEGER PRIMARY KEY, ZTITLE1 TEXT, ZNOTEDATA INTEGER, "
            "ZCREATIONDATE1 REAL, ZMODIFICATIONDATE1 REAL, ZMARKEDFORDELETION INTEGER)"
        )
        conn.execute(
            "INSERT INTO ZICNOTEDATA (Z_PK, ZNOTE, ZDATA) VALUES (1, 1, ?)",
            (gzip.compress(_build_proto("안녕 메모")),),
        )
        conn.execute(
            "INSERT INTO ZICCLOUDSYNCINGOBJECT "
            "(Z_PK, ZTITLE1, ZNOTEDATA, ZCREATIONDATE1, ZMODIFICATIONDATE1, ZMARKEDFORDELETION) "
            "VALUES (1, '제목A', 1, 700000000.0, 700000100.0, 0)"
        )
        conn.commit()
    finally:
        conn.close()
    with open(path, "rb") as f:
        return f.read()


class FakeVault:
    def __init__(self):
        self._raw = _make_db_bytes()

    def find_files(self, *, domain_like=None, path_like=None):
        return [("f", "AppDomainGroup-group.com.apple.notes", "NoteStore.sqlite")]

    def read_bytes(self, rel, *, domain_like=None):
        return self._raw


def test_viewer_notes():
    notes = ViewerData(FakeVault()).notes()
    assert notes[0]["body"] == "안녕 메모"
    assert notes[0]["title"] == "제목A"


def test_appscan_includes_notes():
    rows = [("f", "AppDomainGroup-group.com.apple.notes", "NoteStore.sqlite")]
    apps = {a["label"]: a for a in summarize_apps(rows)}
    assert apps["Notes"]["readable"] is True
