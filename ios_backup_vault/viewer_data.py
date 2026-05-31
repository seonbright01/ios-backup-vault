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


class ViewerData:
    def __init__(self, vault):
        self._v = vault
        self._media_index = None
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
