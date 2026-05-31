"""CallHistory.storedata → 통화기록. 순수."""
import sqlite3
from ios_backup_vault.parsers.messages import mac_time_to_iso


def parse_calls(callhistory_path: str) -> list[dict]:
    con = sqlite3.connect(callhistory_path); con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT ZADDRESS, ZDATE, ZDURATION, ZORIGINATED FROM ZCALLRECORD ORDER BY ZDATE DESC"
        ).fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        addr = r["ZADDRESS"]
        if isinstance(addr, bytes):
            addr = addr.decode("utf-8", errors="ignore")
        out.append({
            "address": addr or "",
            "timestamp": mac_time_to_iso(int(r["ZDATE"])) if r["ZDATE"] is not None else "",
            "duration_sec": int(r["ZDURATION"] or 0),
            "originated": bool(r["ZORIGINATED"]),
        })
    return out
