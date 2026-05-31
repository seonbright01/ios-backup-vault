"""Apple Notes(NoteStore.sqlite) → 구조화. 본문은 gzip+protobuf에서 추출. 순수."""
import gzip
import sqlite3
import zlib
from datetime import datetime, timezone


def _ts_to_iso(v) -> str:
    if v is None:
        return ""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    if v < 1e9:  # Mac 절대시간(2001) → unix
        v += 978307200
    return datetime.fromtimestamp(v, tz=timezone.utc).isoformat()


def _read_varint(buf, i):
    shift = 0
    result = 0
    while i < len(buf):
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return result, i


def _fields(buf):
    """protobuf 와이어 파싱 → [(field_number, wire_type, value)]."""
    out = []
    i = 0
    n = len(buf)
    while i < n:
        key, i = _read_varint(buf, i)
        fn, wt = key >> 3, key & 7
        if wt == 0:
            val, i = _read_varint(buf, i)
        elif wt == 2:
            ln, i = _read_varint(buf, i)
            val = buf[i:i + ln]
            i += ln
        elif wt == 5:
            val = buf[i:i + 4]
            i += 4
        elif wt == 1:
            val = buf[i:i + 8]
            i += 8
        else:
            break
        out.append((fn, wt, val))
    return out


def _first(fields, fn, wt=2):
    for f, w, v in fields:
        if f == fn and w == wt:
            return v
    return None


def extract_note_text(zdata: bytes) -> str:
    if not zdata:
        return ""
    try:
        raw = gzip.decompress(zdata) if zdata[:2] == b"\x1f\x8b" else zdata
    except (OSError, EOFError, zlib.error):  # 손상된 gzip 1건이 메모 탭 전체를 죽이지 않도록
        return ""
    doc = _first(_fields(raw), 2)
    if doc is None:
        return ""
    note = _first(_fields(doc), 3)
    if note is None:
        return ""
    txt = _first(_fields(note), 2)
    if txt is None:
        return ""
    return txt.decode("utf-8", "replace")


def parse_notes(db_path: str) -> list:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cols = {r[1] for r in cur.execute("PRAGMA table_info(ZICCLOUDSYNCINGOBJECT)")}
        title_c = "ZTITLE1" if "ZTITLE1" in cols else ("ZTITLE" if "ZTITLE" in cols else "NULL")
        cre = "ZCREATIONDATE1" if "ZCREATIONDATE1" in cols else "NULL"
        mod = "ZMODIFICATIONDATE1" if "ZMODIFICATIONDATE1" in cols else "NULL"
        delc = "ZMARKEDFORDELETION" if "ZMARKEDFORDELETION" in cols else None
        where = f" WHERE COALESCE(c.{delc},0)=0" if delc else ""
        sql = (
            f"SELECT c.{title_c}, c.{cre}, c.{mod}, d.ZDATA "
            "FROM ZICNOTEDATA d JOIN ZICCLOUDSYNCINGOBJECT c ON c.ZNOTEDATA = d.Z_PK"
            f"{where}"
        )
        rows = cur.execute(sql).fetchall()
    finally:
        conn.close()
    notes = []
    for title, created, modified, zdata in rows:
        body = extract_note_text(zdata) if zdata else ""
        t = (title or "").strip() or (body.split("\n", 1)[0][:60] if body else "(제목 없음)")
        notes.append({"title": t, "body": body,
                      "created": _ts_to_iso(created), "modified": _ts_to_iso(modified)})
    notes.sort(key=lambda n: n.get("modified", ""), reverse=True)
    return notes
