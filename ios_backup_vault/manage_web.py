"""로컬 전용 백업 관리 대시보드(FastAPI). 패스프레이즈 불필요(공개 메타만).

metadata_fn 주입으로 단위 테스트 용이. 실제 내용 열람은 기존 `view` 명령으로.
모든 사용자 문자열은 HTML 이스케이프. 127.0.0.1 바인드는 호출자(cli manage)가 담당.
"""
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ios_backup_vault import registry
from ios_backup_vault.metadata import read_backup_metadata

logger = logging.getLogger(__name__)

_HEAD = """<!doctype html><html lang=ko><meta charset=utf-8>
<title>iOS Backup 관리</title>
<style>body{font-family:-apple-system,sans-serif;margin:0;background:#f4f4f6;color:#111}
header{background:#111;color:#eee;padding:14px 20px;font-weight:600}
main{padding:20px;max-width:1000px;margin:0 auto}
.card{background:#fff;border:1px solid #ddd;border-radius:10px;padding:14px;margin:10px 0}
.card h3{margin:0 0 6px}.badge{display:inline-block;font-size:12px;padding:2px 8px;border-radius:10px;margin-right:4px}
.badge.on{background:#2563eb;color:#fff}.badge.off{background:#ddd;color:#333}
.kv{color:#555;font-size:13px;margin:2px 0}
code{background:#f0f0f0;padding:2px 6px;border-radius:5px;font-size:13px}
button{padding:5px 12px;cursor:pointer;border:1px solid #bbb;border-radius:6px;background:#fafafa}
input[type=text]{padding:6px;border:1px solid #ccc;border-radius:6px;min-width:280px}
.panel{background:#fff;border:1px solid #ddd;border-radius:10px;padding:14px;margin:10px 0}
.muted{color:#888;font-size:13px}</style>
<header>📦 iOS Backup 관리 (로컬 전용 · 외부 전송 없음)</header><main>
<div class=panel><h3>백업 추가</h3>
<p class=muted>이 툴로 만들지 않은 백업(타툴/외부)도 폴더 경로로 등록·열람할 수 있습니다.</p>
<input id=addpath type=text placeholder="/path/to/backup/&lt;UDID&gt;">
<input id=addlabel type=text placeholder="라벨(선택)" style=min-width:140px>
<button onclick=addBackup()>추가</button> <span id=addmsg class=muted></span></div>
<div class=panel><h3>새 이미징</h3>
<p class=muted>새 백업 생성은 CLI에서 진행합니다(패스프레이즈는 CLI에서만 입력):</p>
<p><code>python -m ios_backup_vault.cli precheck --target &lt;폴더&gt;</code></p>
<p><code>python -m ios_backup_vault.cli backup --target &lt;폴더&gt;</code></p>
<p class=muted>열람: <code>python -m ios_backup_vault.cli view --backup &lt;폴더&gt;</code></p></div>
<h2>등록된 백업</h2><div id=list class=muted>로딩…</div></main>
<script>
function esc(s){return (s==null?'':String(s)).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function jget(u){const r=await fetch(u);return r.json()}
async function jpost(u,b){const r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});return r.json()}
function card(x){const enc=x.is_encrypted?'<span class="badge on">암호화</span>':'<span class="badge off">평문</span>';
 const full=x.is_full?'<span class="badge on">전체</span>':'<span class="badge off">부분</span>';
 const size=x.size_bytes==null?'-':(x.size_bytes/1e9).toFixed(2)+'GB';
 const p=esc(x.path);
 return `<div class=card><h3>${esc(x.device_name)||'(이름 없음)'} <small class=muted>${esc(x.product_type)}</small></h3>
 ${enc}${full}
 <div class=kv>iOS ${esc(x.ios_version)} · 빌드 ${esc(x.build)} · UDID ${esc(x.udid)}</div>
 <div class=kv>이미징 ${esc(x.imaged_at)} · 용량 ${size} · 앱 ${Number(x.app_count)}개</div>
 <div class=kv>시리얼 <span class="pii">${esc(x.serial)}</span> · IMEI <span class="pii">${esc(x.imei)}</span> · 전화 <span class="pii">${esc(x.phone)}</span>
 <button class=revealbtn data-path="${p}">PII 보기</button></div>
 <div class=kv>열람: <code>python -m ios_backup_vault.cli view --backup ${p}</code></div>
 <button class=rmbtn data-path="${p}">목록에서 제거</button></div>`}
async function load(){const a=await jget('/api/backups');const el=document.getElementById('list');
 if(!a.length){el.innerHTML='<p class=muted>등록된 백업이 없습니다.</p>';return}
 el.innerHTML=a.map(card).join('')}
document.getElementById('list').addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;
 if(b.classList.contains('revealbtn'))reveal(b.dataset.path,b);
 else if(b.classList.contains('rmbtn'))rm(b.dataset.path)});
async function reveal(path,btn){const m=await jget('/api/meta?reveal=1&path='+encodeURIComponent(path));
 const card=btn.closest('.card');const piis=card.querySelectorAll('.pii');
 if(piis[0])piis[0].textContent=m.serial;if(piis[1])piis[1].textContent=m.imei;if(piis[2])piis[2].textContent=m.phone}
async function addBackup(){const p=document.getElementById('addpath').value.trim();const l=document.getElementById('addlabel').value.trim();
 const msg=document.getElementById('addmsg');if(!p){msg.textContent='경로를 입력하세요';return}
 const r=await jpost('/api/registry/add',{path:p,label:l});
 if(r.error){msg.textContent='오류: '+r.error}else{msg.textContent='추가됨';document.getElementById('addpath').value='';load()}}
async function rm(path){const r=await jpost('/api/registry/remove',{path:path});load()}
load();
</script></html>"""


def create_manager_app(registry_path, *, metadata_fn=read_backup_metadata) -> FastAPI:
    app = FastAPI(title="ios-backup-vault manager")

    def _meta(path, *, reveal=False):
        return metadata_fn(path, with_size=True, reveal_pii=reveal)

    @app.exception_handler(ValueError)
    async def _value_error(request: Request, exc: ValueError):
        return JSONResponse({"error": str(exc)}, status_code=200)

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return _HEAD

    @app.get("/api/backups")
    async def api_backups():
        out = []
        for b in registry.load(registry_path):
            try:
                m = _meta(b["path"])
            except (ValueError, OSError) as exc:
                m = {
                    "path": b["path"], "udid": "", "device_name": "(없음)",
                    "product_type": "", "ios_version": "", "build": "",
                    "imaged_at": "", "last_backup_date": "", "is_encrypted": False,
                    "is_full": False, "snapshot_state": "", "backup_state": "",
                    "app_count": 0, "size_bytes": None,
                    "serial": "", "imei": "", "iccid": "", "phone": "",
                    "error": str(exc),
                }
            m["label"] = b.get("label", "")
            out.append(m)
        return out

    @app.get("/api/meta")
    async def api_meta(path: str, reveal: int = 0):
        # 임의 경로 plist 읽기/무제한 PII 노출 방지: 레지스트리에 등록된 경로만 허용.
        registered = {str(Path(b["path"]).resolve()) for b in registry.load(registry_path)}
        if str(Path(path).resolve()) not in registered:
            return JSONResponse({"error": "등록되지 않은 경로입니다."}, status_code=403)
        return _meta(path, reveal=bool(reveal))

    @app.post("/api/registry/add")
    async def api_add(payload: dict):
        path = (payload or {}).get("path", "")
        label = (payload or {}).get("label", "")
        try:
            entry = registry.add(registry_path, path, label=label)
        except (ValueError, OSError) as exc:
            return {"error": str(exc)}
        return entry

    @app.post("/api/registry/remove")
    async def api_remove(payload: dict):
        path = (payload or {}).get("path", "")
        return {"removed": registry.remove(registry_path, path)}

    return app
