"""AddressBook.sqlitedb → 연락처. 순수."""
import sqlite3


def parse_contacts(addressbook_path: str) -> list[dict]:
    con = sqlite3.connect(addressbook_path); con.row_factory = sqlite3.Row
    try:
        people = con.execute("SELECT ROWID, First, Last FROM ABPerson").fetchall()
        values_by_rec: dict[int, list[str]] = {}
        for r in con.execute("SELECT record_id, value FROM ABMultiValue WHERE value IS NOT NULL"):
            values_by_rec.setdefault(r["record_id"], []).append(r["value"])
    finally:
        con.close()
    out = []
    for p in people:
        name = " ".join(x for x in [p["First"], p["Last"]] if x).strip()
        out.append({"name": name or "(이름 없음)", "values": values_by_rec.get(p["ROWID"], [])})
    return out


def normalize_value(value: str) -> str:
    """매칭용 정규화: 이메일은 소문자, 전화는 끝 8자리 숫자."""
    if value is None:
        return ""
    if "@" in value:
        return value.strip().lower()
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits[-8:] if len(digits) >= 8 else digits


def build_contact_index(contacts: list[dict]) -> dict:
    idx: dict[str, str] = {}
    for c in contacts:
        for v in c.get("values", []):
            k = normalize_value(v)
            if k:
                idx.setdefault(k, c["name"])
    return idx


def resolve_name(index: dict, raw_value: str) -> str | None:
    if not raw_value:
        return None
    return index.get(normalize_value(raw_value))
