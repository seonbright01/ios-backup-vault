"""Vault + parsers를 web 제공자 인터페이스로 묶음."""
import json
import logging
import mimetypes
import sqlite3
import tempfile

from iphone_backup_decrypt import RelativePath
from ios_backup_vault.parsers.messages import parse_messages
from ios_backup_vault.parsers.contacts import parse_contacts, build_contact_index, resolve_name
from ios_backup_vault.parsers.calls import parse_calls
from ios_backup_vault.parsers.media import list_media
from ios_backup_vault.parsers.whatsapp import parse_whatsapp
from ios_backup_vault.parsers.appscan import summarize_apps
from ios_backup_vault.parsers.chatgpt import parse_chatgpt
from ios_backup_vault.parsers.notes import parse_notes
from ios_backup_vault.vault import VaultError

logger = logging.getLogger(__name__)

# 저장 파일 탭: 사용자 문서/미디어 확장자 화이트리스트 (카메라롤·노이즈 제외)
_FILE_CATEGORY = {
    # document
    "pdf": "document", "hwp": "document", "hwpx": "document", "doc": "document",
    "docx": "document", "xls": "document", "xlsx": "document", "ppt": "document",
    "pptx": "document", "csv": "document", "rtf": "document", "epub": "document",
    "pages": "document", "numbers": "document", "key": "document",
    # image
    "jpg": "image", "jpeg": "image", "png": "image", "heic": "image", "heif": "image",
    "gif": "image", "webp": "image", "bmp": "image", "tiff": "image",
    # video
    "mp4": "video", "mov": "video", "m4v": "video", "avi": "video", "mkv": "video",
    # audio
    "m4a": "audio", "mp3": "audio", "wav": "audio", "aac": "audio", "caf": "audio", "flac": "audio",
    # archive
    "zip": "archive",
}
# 경로/도메인에 이 조각이 있으면 노이즈로 제외(캐시·웹킷·분석·크래시·로그)
_FILE_NOISE = ("/caches/", "/webkit/", "/tmp/", ".tipkit", "fbsdk", "facebook-sdk",
               "/logs/", "googleanalytics", "/ssoauth/", "com.braze", "bugsnag",
               "/crashreporter/", "/library/cookies/")
# 앱 도메인 → 친근한 라벨(없으면 번들 id 노출)
_APP_LABEL = {
    "com.iwilab.KakaoTalk": "카카오톡", "net.whatsapp.WhatsApp": "WhatsApp",
    "com.burbn.instagram": "Instagram", "com.openai.chat": "ChatGPT",
    "com.google.chrome.ios": "Chrome", "com.adobe.scan.ios": "Adobe Scan",
}


def _app_label_from_domain(domain: str) -> str:
    d = domain or ""
    for pre in ("AppDomainGroup-group.", "AppDomain-", "SysContainerDomain-"):
        if d.startswith(pre):
            d = d[len(pre):]
            break
    return _APP_LABEL.get(d, d or "(기타)")


class ViewerData:
    def __init__(self, vault):
        self._v = vault
        self._media_index = None
        self._files_index = None
        self._contact_idx = None

    def _parse_sqlite(self, relative_path, parser):
        raw = self._v.read_bytes(relative_path)
        if raw is None:
            logger.warning("백업에서 파일을 찾지 못함: %s (해당 항목은 비어있게 표시됨)", relative_path)
            return []
        with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as tf:
            tf.write(raw); tf.flush()
            try:
                return parser(tf.name)
            except sqlite3.Error as exc:
                raise VaultError(f"'{relative_path}' 파싱 실패(스키마 불일치/손상 가능): {exc}") from exc

    def _contacts_index(self):
        if self._contact_idx is None:
            self._contact_idx = build_contact_index(self.contacts())
        return self._contact_idx

    def calls(self):
        idx = self._contacts_index()
        rows = self._parse_sqlite(RelativePath.CALL_HISTORY, parse_calls)
        for c in rows:
            c["name"] = resolve_name(idx, c.get("address", ""))
        return rows

    def messages(self):
        idx = self._contacts_index()
        convos = self._parse_sqlite(RelativePath.TEXT_MESSAGES, parse_messages)
        for conv in convos:
            conv["name"] = conv.get("display_name") or resolve_name(idx, conv.get("chat_identifier", "")) or ""
        return convos

    def contacts(self):
        return self._parse_sqlite(RelativePath.ADDRESS_BOOK, parse_contacts)

    def whatsapp(self):
        return self._parse_sqlite(RelativePath.WHATSAPP_MESSAGES, parse_whatsapp)

    def appscan(self):
        return summarize_apps(self._v.manifest_files())

    def chatgpt(self):
        rows = self._v.find_files(domain_like="AppDomain-com.openai.chat",
                                  path_like="%conversations-v3-%/%.json")
        convos = []
        for _fid, domain, rel in rows:
            raw = self._v.read_bytes(rel, domain_like=domain)
            if raw is None:
                continue
            try:
                convos.append(parse_chatgpt(json.loads(raw)))
            except (ValueError, KeyError, TypeError):
                continue
        convos.sort(key=lambda c: c.get("created", ""), reverse=True)
        return convos

    def notes(self):
        rows = self._v.find_files(domain_like="AppDomainGroup-group.com.apple.notes",
                                  path_like="%NoteStore.sqlite")
        out = []
        for _fid, domain, rel in rows:
            raw = self._v.read_bytes(rel, domain_like=domain)
            if raw is None:
                continue
            with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as tf:
                tf.write(raw); tf.flush()
                try:
                    out.extend(parse_notes(tf.name))
                except sqlite3.Error:
                    continue
        out.sort(key=lambda n: n.get("modified", ""), reverse=True)
        return out

    def media(self):
        self._media_index = {}
        rows = self._v.manifest_files(domain="CameraRollDomain")
        items = list_media(rows)
        self._media_index = {i["file_id"]: i["relative_path"] for i in items}
        return items

    def media_bytes_and_mtime(self, file_id):
        """(bytes, mime, mtime) 반환. mtime은 원본 수정일(epoch). 없으면 None 튜플 요소."""
        if self._media_index is None:
            self.media()
        rel = self._media_index.get(file_id)
        if rel is None:
            return None
        got = self._v.read_bytes_and_mtime(rel, domain_like="CameraRollDomain")
        if got is None:
            return None
        raw, mtime = got
        return raw, (mimetypes.guess_type(rel)[0] or "application/octet-stream"), mtime

    def files(self):
        """백업에 저장된 문서/미디어 파일 목록(카메라롤·노이즈·썸네일 제외)."""
        self._files_index = {}
        out = []
        for fid, domain, rel in self._v.manifest_files():
            if not rel or domain == "CameraRollDomain":
                continue
            low = (domain + "/" + rel).lower()
            if any(n in low for n in _FILE_NOISE):
                continue
            name = rel.rsplit("/", 1)[-1]
            if "_thumb" in name.lower():        # 썸네일 중복 제외
                continue
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            cat = _FILE_CATEGORY.get(ext)
            if not cat:
                continue
            self._files_index[fid] = (domain, rel)
            out.append({
                "file_id": fid, "filename": name, "ext": ext, "category": cat,
                "app": _app_label_from_domain(domain), "path": rel,
            })
        out.sort(key=lambda e: (e["category"], e["app"], e["filename"].lower()))
        return out

    def file_bytes_and_mtime(self, file_id):
        """(bytes, mime, mtime). 없으면 None."""
        if self._files_index is None:
            self.files()
        loc = self._files_index.get(file_id)
        if loc is None:
            return None
        domain, rel = loc
        got = self._v.read_bytes_and_mtime(rel, domain_like=domain)
        if got is None:
            return None
        raw, mtime = got
        return raw, (mimetypes.guess_type(rel)[0] or "application/octet-stream"), mtime

    def file_bytes(self, file_id):
        got = self.file_bytes_and_mtime(file_id)
        if got is None:
            return None
        raw, mime, _ = got
        return raw, mime

    def media_bytes(self, file_id):
        got = self.media_bytes_and_mtime(file_id)
        if got is None:
            return None
        raw, mime, _ = got
        return raw, mime

    def export(self, payload):
        formats = payload.get("formats") or ["json"]
        items = payload.get("items") or {}
        media_ids = payload.get("media_file_ids") or []
        from ios_backup_vault.parsers.export import serialize, bundle
        files = {}
        dates = {}
        for fmt in formats:
            files.update(serialize(items, fmt))
        has_media = False
        for fid in media_ids:
            got = self.media_bytes_and_mtime(fid)
            if got is None:
                continue
            content, mime, mtime = got
            ext = mimetypes.guess_extension(mime or "") or ".bin"
            name = f"media/{fid}{ext}"
            files[name] = content
            if mtime:
                dates[name] = mtime  # 원본 수정일 보존(zip 항목 타임스탬프)
            has_media = True
        if len(files) == 1 and not has_media:
            name, content = next(iter(files.items()))
            mime = {"json": "application/json", "html": "text/html",
                    "txt": "text/plain", "csv": "text/csv"}.get(
                        name.rsplit(".", 1)[-1], "application/octet-stream")
            return name, content, mime
        return "export.zip", bundle(files, dates), "application/zip"

    def summary(self):
        return {"messages": sum(len(c["messages"]) for c in self.messages()),
                "contacts": len(self.contacts()), "calls": len(self.calls()),
                "media": len(self.media())}

    def search(self, q):
        q = (q or "").lower().strip()
        if not q:
            return {"messages": [], "contacts": []}
        msgs = []
        for c in self.messages():
            for m in c["messages"]:
                if q in (m["text"] or "").lower():
                    msgs.append({"text": m["text"], "timestamp": m["timestamp"]})
        contacts = [c for c in self.contacts()
                    if q in c["name"].lower() or any(q in v.lower() for v in c["values"])]
        return {"messages": msgs[:200], "contacts": contacts}
