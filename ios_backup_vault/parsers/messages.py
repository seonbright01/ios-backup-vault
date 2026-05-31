"""sms.db → 대화별 구조화. 순수(경로 입력)."""
import sqlite3
from datetime import datetime, timezone

_MAC_EPOCH = 978307200  # 2001-01-01T00:00:00Z (unix sec)


def mac_time_to_iso(value: int | None) -> str:
    if value is None:
        return ""
    seconds = value / 1_000_000_000 if value > 10_000_000_000 else value
    return datetime.fromtimestamp(seconds + _MAC_EPOCH, tz=timezone.utc).isoformat()


def _text_from_attributed_body(blob: bytes) -> str:
    if not blob:
        return ""
    s = blob.decode("utf-8", errors="ignore")
    idx = s.find("NSString")
    if idx == -1:
        return ""
    tail = s[idx + len("NSString"):]
    out, started = [], False
    for ch in tail:
        if ch.isprintable() and ch != "\x00":
            out.append(ch); started = True
        elif started:
            break
    return "".join(out).strip("+ \t")


def parse_messages(sms_db_path: str) -> list[dict]:
    con = sqlite3.connect(sms_db_path); con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT c.ROWID AS chat_id, c.chat_identifier, c.display_name,
                   m.text, m.attributedBody, m.date, m.is_from_me, h.id AS handle
            FROM chat c
            JOIN chat_message_join cmj ON cmj.chat_id = c.ROWID
            JOIN message m ON m.ROWID = cmj.message_id
            LEFT JOIN handle h ON h.ROWID = m.handle_id
            ORDER BY c.ROWID, m.date
            """
        ).fetchall()
    finally:
        con.close()
    convos: dict[int, dict] = {}
    for r in rows:
        cid = r["chat_id"]
        if cid not in convos:
            convos[cid] = {"chat_id": cid, "chat_identifier": r["chat_identifier"],
                           "display_name": r["display_name"] or "", "messages": []}
        text = r["text"]
        if not text and r["attributedBody"] is not None:
            text = _text_from_attributed_body(r["attributedBody"])
        convos[cid]["messages"].append({
            "text": text or "", "timestamp": mac_time_to_iso(r["date"]),
            "is_from_me": bool(r["is_from_me"]), "handle": r["handle"] or "",
        })
    return list(convos.values())
