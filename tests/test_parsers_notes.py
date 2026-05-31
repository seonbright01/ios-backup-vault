import gzip
import sqlite3
from ios_backup_vault.parsers.notes import extract_note_text, parse_notes


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


def _tag(fn, wt):
    return bytes([(fn << 3) | wt])


def _ld(fn, payload):
    return _tag(fn, 2) + _varint(len(payload)) + payload


def _build_proto(text):
    note_text_field = _ld(2, text.encode("utf-8"))   # note.note_text (field 2)
    note_msg = note_text_field
    note_field = _ld(3, note_msg)                     # document.note (field 3)
    document_msg = note_field
    document_field = _ld(2, document_msg)             # top.document (field 2)
    return document_field


def test_extract_note_text_plain():
    proto = _build_proto("안녕 메모")
    assert extract_note_text(proto) == "안녕 메모"


def test_extract_note_text_gzip():
    proto = _build_proto("안녕 메모")
    assert extract_note_text(gzip.compress(proto)) == "안녕 메모"


def test_extract_note_text_corrupt_gzip_returns_empty():
    # gzip magic이지만 본문이 손상된 경우 — 예외 대신 "" 반환(탭 전체 보호)
    assert extract_note_text(b"\x1f\x8b\xff\xff\xff\xff") == ""


def _make_db(path, zdata):
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE ZICNOTEDATA (Z_PK INTEGER PRIMARY KEY, ZNOTE INTEGER, ZDATA BLOB)"
        )
        conn.execute(
            "CREATE TABLE ZICCLOUDSYNCINGOBJECT ("
            "Z_PK INTEGER PRIMARY KEY, ZTITLE1 TEXT, ZSNIPPET TEXT, ZNOTEDATA INTEGER, "
            "ZCREATIONDATE1 REAL, ZMODIFICATIONDATE1 REAL, ZMARKEDFORDELETION INTEGER, ZFOLDER INTEGER)"
        )
        conn.execute("INSERT INTO ZICNOTEDATA (Z_PK, ZNOTE, ZDATA) VALUES (1, 1, ?)", (zdata,))
        conn.execute(
            "INSERT INTO ZICCLOUDSYNCINGOBJECT "
            "(Z_PK, ZTITLE1, ZSNIPPET, ZNOTEDATA, ZCREATIONDATE1, ZMODIFICATIONDATE1, ZMARKEDFORDELETION, ZFOLDER) "
            "VALUES (1, '제목A', 's', 1, 700000000.0, 700000100.0, 0, 1)"
        )
        conn.commit()
    finally:
        conn.close()


def test_parse_notes(tmp_path):
    zdata = gzip.compress(_build_proto("안녕 메모"))
    db = tmp_path / "NoteStore.sqlite"
    _make_db(str(db), zdata)
    notes = parse_notes(str(db))
    assert len(notes) == 1
    n = notes[0]
    assert n["title"] == "제목A"
    assert n["body"] == "안녕 메모"
    assert n["created"].startswith("20")
    assert n["modified"].startswith("20")
