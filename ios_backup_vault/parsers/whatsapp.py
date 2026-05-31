"""WhatsApp ChatStorage.sqlite → 대화별 구조화. 순수."""
import sqlite3
from ios_backup_vault.parsers.messages import mac_time_to_iso


def parse_whatsapp(chatstorage_path: str) -> list[dict]:
    con = sqlite3.connect(chatstorage_path); con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT s.Z_PK AS sid, s.ZPARTNERNAME AS name, s.ZCONTACTJID AS jid,
                   m.ZTEXT AS text, m.ZMESSAGEDATE AS date, m.ZISFROMME AS from_me
            FROM ZWAMESSAGE m
            JOIN ZWACHATSESSION s ON m.ZCHATSESSION = s.Z_PK
            ORDER BY s.Z_PK, m.ZMESSAGEDATE
            """
        ).fetchall()
    finally:
        con.close()
    convos: dict = {}
    for r in rows:
        sid = r["sid"]
        if sid not in convos:
            convos[sid] = {"name": r["name"] or r["jid"] or "(이름 없음)", "jid": r["jid"] or "", "messages": []}
        convos[sid]["messages"].append({
            "text": r["text"] or "",
            "timestamp": mac_time_to_iso(int(r["date"])) if r["date"] is not None else "",
            "is_from_me": bool(r["from_me"]),
        })
    return list(convos.values())
