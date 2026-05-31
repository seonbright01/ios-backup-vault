"""매니페스트 도메인에서 알려진 메신저 앱 탐지·읽기가능 판정. 순수."""

# (도메인 부분문자열, 라벨, 읽기가능, 비고)
_KNOWN = [
    ("net.whatsapp", "WhatsApp", True, "평문 SQLite — 읽기 가능"),
    ("com.openai.chat", "ChatGPT", True, "로컬 대화 캐시(JSON) — 읽기 가능"),
    ("group.com.apple.notes", "Notes", True, "메모 — gzip+protobuf 본문 추출(평문 메모 가능)"),
    ("com.apple.mobilenotes", "Notes", True, "메모 — gzip+protobuf 본문 추출(평문 메모 가능)"),
    ("ai.perplexity", "Perplexity", False, "로컬 저장 형식 미검증 — 내용 확인 필요"),
    ("com.kakao.talk", "KakaoTalk", False, "앱 자체 암호화 — 내용 불가"),
    ("iwilab.kakaotalk", "KakaoTalk", False, "앱 자체 암호화 — 내용 불가"),
    ("telegra", "Telegram", False, "암호화 로컬 컨테이너 — 내용 불가"),
    ("org.telegram", "Telegram", False, "암호화 로컬 컨테이너 — 내용 불가"),
    ("signal", "Signal", False, "앱 자체 암호화 — 내용 불가"),
    ("net.line.naver", "LINE", False, "앱 자체 암호화 가능성 — 내용 불가"),
]


def summarize_apps(rows) -> list[dict]:
    counts: dict[str, int] = {}
    domains: dict[str, set] = {}
    for _file_id, domain, _rel in rows:
        low = (domain or "").lower()
        for needle, label, _readable, _note in _KNOWN:
            if needle in low:
                counts[label] = counts.get(label, 0) + 1
                domains.setdefault(label, set()).add(domain)
                break
    meta = {label: (readable, note) for _n, label, readable, note in _KNOWN}
    out = []
    for label, n in sorted(counts.items()):
        readable, note = meta[label]
        out.append({"label": label, "file_count": n,
                    "domains": sorted(domains[label]), "readable": readable, "note": note})
    return out
