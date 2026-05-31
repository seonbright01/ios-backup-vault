"""선택 항목을 JSON/HTML/CSV/TXT로 직렬화 + zip 번들링. 순수 함수."""
import csv
import html
import io
import json
import time
import zipfile

_CSV_SPEC = {
    "messages": (["conversation", "chat_identifier", "is_from_me", "timestamp", "text"],
                 lambda c: [[c.get("name", ""), c.get("chat_identifier", ""),
                             m.get("is_from_me", ""), m.get("timestamp", ""), m.get("text", "")]
                            for m in c.get("messages", [])]),
    "whatsapp": (["conversation", "chat_identifier", "is_from_me", "timestamp", "text"],
                 lambda c: [[c.get("name", ""), c.get("chat_identifier", ""),
                             m.get("is_from_me", ""), m.get("timestamp", ""), m.get("text", "")]
                            for m in c.get("messages", [])]),
    "chatgpt": (["title", "role", "timestamp", "text"],
                lambda c: [[c.get("title", ""), m.get("role", ""),
                            m.get("timestamp", ""), m.get("text", "")]
                           for m in c.get("messages", [])]),
    "contacts": (["name", "values"],
                 lambda c: [[c.get("name", ""), "; ".join(c.get("values", []))]]),
    "calls": (["name", "address", "timestamp", "duration_sec", "originated"],
              lambda c: [[c.get("name", ""), c.get("address", ""), c.get("timestamp", ""),
                          c.get("duration_sec", ""), c.get("originated", "")]]),
    "notes": (["title", "created", "modified", "body"],
              lambda c: [[c.get("title", ""), c.get("created", ""),
                          c.get("modified", ""), c.get("body", "")]]),
}


def _serialize_json(items):
    return {"export.json": json.dumps(items, ensure_ascii=False, indent=2).encode("utf-8")}


def _serialize_txt(items):
    lines = []

    def conv_section(rows, title_key, label):
        for c in rows:
            cid = c.get("chat_identifier")
            lines.append(f"## {c.get(title_key, '')}" + (f" ({cid})" if cid else ""))
            for m in c.get("messages", []):
                who = "나" if m.get("is_from_me") else "상대"
                lines.append(f"[{m.get('timestamp', '')}] ({who}) {m.get('text', '')}")
            lines.append("")

    if items.get("messages"):
        conv_section(items["messages"], "name", "messages")
    if items.get("whatsapp"):
        conv_section(items["whatsapp"], "name", "whatsapp")
    for c in items.get("chatgpt") or []:
        lines.append(f"## {c.get('title', '')}")
        for m in c.get("messages", []):
            lines.append(f"[{m.get('timestamp', '')}] {m.get('role', '')}: {m.get('text', '')}")
        lines.append("")
    for c in items.get("contacts") or []:
        lines.append(f"{c.get('name', '')}: {', '.join(c.get('values', []))}")
    for c in items.get("calls") or []:
        direction = "발신" if c.get("originated") else "수신"
        lines.append(f"{c.get('name', '')}({c.get('address', '')}) {c.get('timestamp', '')} "
                     f"{c.get('duration_sec', 0)}s {direction}")
    for c in items.get("notes") or []:
        lines.append(f"# {c.get('title', '')} ({c.get('modified', '')})")
        lines.append(c.get("body", ""))
    return {"export.txt": "\n".join(lines).encode("utf-8")}


def _serialize_html(items):
    e = html.escape
    parts = ["<!doctype html><meta charset=utf-8>",
             "<style>body{font-family:sans-serif}.msg{max-width:60%;padding:6px 10px;"
             "border-radius:12px;margin:3px;background:#eee}.me{background:#2563eb;"
             "color:#fff;margin-left:auto}.row{display:flex}</style>"]

    def conv_block(rows, title_key, heading):
        parts.append(f"<h2>{e(heading)}</h2>")
        for c in rows:
            cid = c.get("chat_identifier")
            title = str(c.get(title_key, "")) + (f" ({cid})" if cid else "")
            parts.append(f"<details><summary>{e(title)}</summary>")
            for m in c.get("messages", []):
                cls = "msg me" if m.get("is_from_me") else "msg"
                parts.append(f'<div class=row><div class="{cls}">{e(str(m.get("text", "")))}'
                             f'<br><small>{e(str(m.get("timestamp", "")))}</small></div></div>')
            parts.append("</details>")

    if items.get("messages"):
        conv_block(items["messages"], "name", "메시지")
    if items.get("whatsapp"):
        conv_block(items["whatsapp"], "name", "WhatsApp")
    if items.get("chatgpt"):
        parts.append("<h2>ChatGPT</h2>")
        for c in items["chatgpt"]:
            parts.append(f"<details><summary>{e(str(c.get('title', '')))}</summary>")
            for m in c.get("messages", []):
                cls = "msg me" if m.get("role") == "user" else "msg"
                parts.append(f'<div class=row><div class="{cls}">{e(str(m.get("text", "")))}'
                             f'<br><small>{e(str(m.get("role", "")))} · '
                             f'{e(str(m.get("timestamp", "")))}</small></div></div>')
            parts.append("</details>")
    if items.get("contacts"):
        parts.append("<h2>연락처</h2><table>")
        for c in items["contacts"]:
            vals = ", ".join(e(str(v)) for v in c.get("values", []))
            parts.append(f"<tr><td>{e(str(c.get('name', '')))}</td><td>{vals}</td></tr>")
        parts.append("</table>")
    if items.get("calls"):
        parts.append("<h2>통화</h2><table>")
        for c in items["calls"]:
            direction = "발신" if c.get("originated") else "수신"
            parts.append(f"<tr><td>{e(str(c.get('name', '')))}</td>"
                         f"<td>{e(str(c.get('address', '')))}</td>"
                         f"<td>{e(str(c.get('timestamp', '')))}</td>"
                         f"<td>{e(str(c.get('duration_sec', '')))}</td><td>{direction}</td></tr>")
        parts.append("</table>")
    if items.get("notes"):
        parts.append("<h2>메모</h2>")
        for c in items["notes"]:
            parts.append(f"<h3>{e(str(c.get('title', '')))} "
                         f"<small>{e(str(c.get('modified', '')))}</small></h3>"
                         f"<pre>{e(str(c.get('body', '')))}</pre>")
    return {"export.html": "".join(parts).encode("utf-8")}


def _serialize_csv(items):
    out = {}
    for cat, (header, row_fn) in _CSV_SPEC.items():
        rows = items.get(cat) or []
        if not rows:
            continue
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(header)
        for c in rows:
            for r in row_fn(c):
                w.writerow(r)
        out[f"{cat}.csv"] = buf.getvalue().encode("utf-8-sig")
    return out


_SERIALIZERS = {
    "json": _serialize_json,
    "txt": _serialize_txt,
    "html": _serialize_html,
    "csv": _serialize_csv,
}


def serialize(items, fmt):
    """items dict를 fmt(json/html/csv/txt)로 직렬화. 반환 = {파일명: bytes}."""
    fn = _SERIALIZERS.get(fmt)
    if fn is None:
        raise ValueError(f"알 수 없는 형식: {fmt}")
    return fn(items or {})


def bundle(files, dates=None):
    """{파일명: bytes}를 단일 zip 바이트로 묶음.

    dates: {파일명: epoch초}. 주어지면 해당 zip 항목 타임스탬프를 원본 시각으로 설정
    (미디어의 원본 수정일 보존). 없으면 zip 기본(현재 시각).
    """
    dates = dates or {}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            ts = dates.get(name)
            if ts:
                # zip 포맷 최소 연도는 1980 — 그 이전이면 그대로 두지 않고 보정.
                dt = time.localtime(ts)[:6]
                if dt[0] < 1980:
                    zf.writestr(name, content)
                    continue
                zi = zipfile.ZipInfo(name, date_time=dt)
                zi.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(zi, content)
            else:
                zf.writestr(name, content)
    return buf.getvalue()
