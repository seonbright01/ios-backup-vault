"""ChatGPT 로컬 대화 JSON(conversations-v3) → 구조화. 순수."""
from datetime import datetime, timezone


def _ts_to_iso(v) -> str:
    if v is None:
        return ""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    if v > 1e11:
        v = v / 1000.0
    if v < 1e9:  # Mac 절대시간(2001) → unix
        v += 978307200
    return datetime.fromtimestamp(v, tz=timezone.utc).isoformat()


def _node_text(message: dict) -> str:
    content = message.get("content") or {}
    if content.get("content_type") not in ("text", "multimodal_text"):
        return ""
    parts = content.get("parts") or []
    return "\n".join(p for p in parts if isinstance(p, str)).strip()


def parse_chatgpt(data: dict) -> dict:
    title = data.get("title") or "(제목 없음)"
    storage = (data.get("tree") or {}).get("storage") or []
    msgs = []
    for node in storage:
        if not isinstance(node, dict):
            continue
        message = node.get("content") or {}
        role = (message.get("author") or {}).get("role")
        text = _node_text(message)
        if role in ("user", "assistant") and text:
            msgs.append({"role": role, "text": text,
                         "_t": message.get("create_time") or node.get("created_at") or 0})
    msgs.sort(key=lambda m: m["_t"] or 0)
    for m in msgs:
        m["timestamp"] = _ts_to_iso(m.pop("_t"))
    return {"title": title, "created": _ts_to_iso(data.get("creation_date")), "messages": msgs}
