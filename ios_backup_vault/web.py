"""로컬 전용 FastAPI 뷰어. data 제공자 주입."""
import logging

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

from ios_backup_vault.vault import VaultError

logger = logging.getLogger(__name__)

_INDEX_HTML = """<!doctype html><html lang=ko><meta charset=utf-8>
<title>iOS Backup Viewer</title>
<style>body{font-family:-apple-system,sans-serif;margin:0;display:flex}
nav{width:150px;background:#111;color:#eee;height:100vh;padding:10px;box-sizing:border-box}
nav a{display:block;color:#eee;text-decoration:none;padding:6px;border-radius:6px;cursor:pointer}
nav a:hover{background:#333}main{flex:1;padding:16px;overflow:auto;height:100vh}
.msg{max-width:60%;padding:6px 10px;border-radius:12px;margin:3px;background:#eee}
.me{background:#2563eb;color:#fff;margin-left:auto}.row{display:flex}
img,video{max-width:160px;margin:4px;border-radius:8px}table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:4px 8px}
.expbar{position:sticky;top:0;background:#f6f6f6;padding:8px;border-radius:8px;margin-bottom:10px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;z-index:5}
.expbar button{padding:4px 10px;cursor:pointer}.expbar label{cursor:pointer}.thumb{display:inline-block;position:relative}.thumb .mchk{position:absolute;top:6px;left:6px;width:18px;height:18px}</style>
<nav><b>📦 열람</b><a onclick="show('summary')">요약</a><a onclick="show('messages')">메시지</a>
<a onclick="show('media')">사진/영상</a><a onclick="show('contacts')">연락처</a><a onclick="show('calls')">통화</a><a onclick="show('whatsapp')">WhatsApp</a><a onclick="show('chatgpt')">ChatGPT</a><a onclick="show('notes')">메모</a><a onclick="show('appscan')">앱 스캔</a>
<input id=q placeholder=검색><a onclick=doSearch()>검색</a></nav><main id=main>로딩…</main>
<script>
async function j(u){const r=await fetch(u);let d=null;try{d=await r.json()}catch(e){}
 if(!r.ok)throw new Error((d&&d.error)?d.error:('HTTP '+r.status));
 if(d&&!Array.isArray(d)&&d.error)throw new Error(d.error);
 return d}
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function err(m,e){m.innerHTML='<h2 style="color:#c00">오류</h2><pre style="white-space:pre-wrap">'+esc(String((e&&e.message)||e))+'</pre>'}
window._cache={}
function expbar(tab,media){const fmts=media?'(미디어 자동 포함)':'<label><input type=checkbox class=fmt value=json checked>JSON</label> <label><input type=checkbox class=fmt value=html>HTML</label> <label><input type=checkbox class=fmt value=csv>CSV</label> <label><input type=checkbox class=fmt value=txt>TXT</label>';
 return `<div class=expbar><label><input type=checkbox onclick="selAll('${tab}',this.checked)"> 전체선택</label> ${fmts} <button onclick="doExport('${tab}')">내보내기</button></div>`}
function selAll(tab,on){document.querySelectorAll('#main input.convchk,#main input.msgchk,#main input.rowchk,#main input.mchk').forEach(c=>{c.checked=on})}
function syncConv(cb){const d=cb.closest('details');if(d)d.querySelectorAll('input.msgchk').forEach(m=>{m.checked=cb.checked})}
function convHtml(tab,i,title,sub,msgs,clsFn){let h=`<details><summary><input type=checkbox class=convchk data-i=${i} onclick="syncConv(this)"> ${esc(title)} (${msgs.length})`+(sub?` <small>${esc(sub)}</small>`:'')+'</summary>';
 h+=msgs.map((g,mi)=>`<div class=row><label class="msg ${clsFn(g)?'me':''}"><input type=checkbox class=msgchk data-i=${i} data-mi=${mi}> ${esc(g.text)}<br><small>${esc(g.timestamp||'')}${g.role?' · '+esc(g.role):''}</small></label></div>`).join('');
 return h+'</details>'}
async function show(v){const m=document.getElementById('main');m.textContent='로딩…';try{
 if(v=='summary'){const s=await j('/api/summary');m.innerHTML='<h2>요약</h2><ul>'+Object.entries(s).map(([k,n])=>`<li>${esc(String(k))}: ${Number(n)}</li>`).join('')+'</ul>'}
 else if(v=='messages'){const c=await j('/api/messages');window._cache.messages=c;m.innerHTML=expbar('messages')+'<h2>메시지 ('+c.length+')</h2>'+c.map((x,i)=>convHtml('messages',i,x.name||x.display_name||x.chat_identifier,'',x.messages,g=>g.is_from_me)).join('')}
 else if(v=='media'){return showMedia(0)}
 else if(v=='contacts'){const a=await j('/api/contacts');window._cache.contacts=a;m.innerHTML=expbar('contacts')+'<h2>연락처 ('+a.length+')</h2><table><tr><th></th><th>이름</th><th>값</th></tr>'+a.map((x,i)=>`<tr><td><input type=checkbox class=rowchk data-i=${i}></td><td>${esc(x.name)}</td><td>${x.values.map(esc).join(', ')}</td></tr>`).join('')+'</table>'}
 else if(v=='calls'){const a=await j('/api/calls');window._cache.calls=a;m.innerHTML=expbar('calls')+'<h2>통화 ('+a.length+')</h2><table><tr><th></th><th>상대</th><th>시각</th><th>초</th><th>방향</th></tr>'+a.map((x,i)=>`<tr><td><input type=checkbox class=rowchk data-i=${i}></td><td>${esc(x.name? x.name+' ('+x.address+')' : x.address)}</td><td>${esc(x.timestamp)}</td><td>${Number(x.duration_sec)}</td><td>${x.originated?'발신':'수신'}</td></tr>`).join('')+'</table>'}
 else if(v=='whatsapp'){const c=await j('/api/whatsapp');window._cache.whatsapp=c;m.innerHTML=expbar('whatsapp')+'<h2>WhatsApp ('+c.length+')</h2>'+c.map((x,i)=>convHtml('whatsapp',i,x.name,'',x.messages,g=>g.is_from_me)).join('')}
 else if(v=='chatgpt'){const c=await j('/api/chatgpt');window._cache.chatgpt=c;m.innerHTML=expbar('chatgpt')+'<h2>ChatGPT ('+c.length+')</h2>'+c.map((x,i)=>convHtml('chatgpt',i,x.title,x.created,x.messages,g=>g.role=='user')).join('')}
 else if(v=='notes'){const c=await j('/api/notes');window._cache.notes=c;m.innerHTML=expbar('notes')+'<h2>메모 ('+c.length+')</h2>'+c.map((x,i)=>`<details><summary><input type=checkbox class=rowchk data-i=${i}> ${esc(x.title)} <small>${esc(x.modified)}</small></summary><pre style="white-space:pre-wrap;font-family:inherit">${esc(x.body)}</pre></details>`).join('')}
 else if(v=='appscan'){const a=await j('/api/appscan');m.innerHTML='<h2>백업 앱 스캔</h2>'+(a.length?('<table><tr><th>앱</th><th>파일수</th><th>내용 읽기</th><th>비고</th></tr>'+a.map(x=>`<tr><td>${esc(x.label)}</td><td>${Number(x.file_count)}</td><td>${x.readable?'✅ 가능':'❌ 불가'}</td><td>${esc(x.note)}</td></tr>`).join('')+'</table>'):'<p>알려진 메신저 앱이 백업에 없습니다.</p>')}
 }catch(e){err(m,e)}}
async function showMedia(off){const m=document.getElementById('main');m.textContent='로딩…';try{
 const d=await j('/api/media?limit=200&offset='+off);const a=d.items||[];let nav='';
 if(off>0)nav+=`<button onclick="showMedia(${Math.max(0,off-200)})">◀ 이전</button> `;
 if(off+200<d.total)nav+=`<button onclick="showMedia(${off+200})">다음 200개 ▶</button>`;
 m.innerHTML=expbar('media',true)+'<h2>사진/영상 (전체 '+d.total+'개 중 '+(d.total?off+1:0)+'–'+(off+a.length)+')</h2>'+nav+'<div>'+a.map(x=>`<span class=thumb><input type=checkbox class=mchk data-fid="${esc(x.file_id)}">`+(x.kind=='image'?`<img loading=lazy src="/media/${esc(x.file_id)}">`:`<video controls width=200 src="/media/${esc(x.file_id)}"></video>`)+'</span>').join('')+'</div>'+nav}catch(e){err(m,e)}}
function pickFormats(){let f=[...document.querySelectorAll('#main input.fmt:checked')].map(c=>c.value);return f.length?f:['json']}
function convPayload(tab){const cache=window._cache[tab]||[];const out=[];
 document.querySelectorAll('#main details').forEach(d=>{const cv=d.querySelector('input.convchk');if(!cv)return;const i=+cv.dataset.i;const src=cache[i];if(!src)return;
  const mchecks=[...d.querySelectorAll('input.msgchk:checked')];if(!cv.checked&&mchecks.length==0)return;
  const msgs=mchecks.length?mchecks.map(c=>src.messages[+c.dataset.mi]).filter(Boolean):src.messages;
  out.push(Object.assign({},src,{messages:msgs}))});return out}
function rowPayload(tab){const cache=window._cache[tab]||[];return [...document.querySelectorAll('#main input.rowchk:checked')].map(c=>cache[+c.dataset.i]).filter(Boolean)}
async function doExport(tab){const items={};let media=[];
 if(tab=='messages'||tab=='whatsapp'||tab=='chatgpt')items[tab]=convPayload(tab);
 else if(tab=='contacts'||tab=='calls'||tab=='notes')items[tab]=rowPayload(tab);
 else if(tab=='media')media=[...document.querySelectorAll('#main input.mchk:checked')].map(c=>c.dataset.fid);
 const count=Object.values(items).reduce((a,b)=>a+b.length,0)+media.length;
 if(count==0){alert('선택된 항목이 없습니다');return}
 const payload={formats:tab=='media'?[]:pickFormats(),items:items,media_file_ids:media};
 try{const res=await fetch('/api/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  if(!res.ok)throw new Error('HTTP '+res.status);
  const cd=res.headers.get('Content-Disposition')||'';const mt=cd.match(/filename="([^"]+)"/);const fn=mt?mt[1]:'export.bin';
  const blob=await res.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=fn;document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url)}
 catch(e){alert('내보내기 실패: '+((e&&e.message)||e))}}
async function doSearch(){const m=document.getElementById('main');const q=document.getElementById('q').value;m.textContent='로딩…';try{const r=await j('/api/search?q='+encodeURIComponent(q));
 m.innerHTML='<h2>검색: '+esc(q)+'</h2><h3>연락처</h3>'+(r.contacts||[]).map(x=>`<div>${esc(x.name)} — ${x.values.map(esc).join(', ')}</div>`).join('')+'<h3>메시지</h3>'+(r.messages||[]).map(x=>`<div>${esc(x.text)} <small>${esc(x.timestamp)}</small></div>`).join('')}catch(e){err(m,e)}}
show('summary')
</script></html>"""


def create_app(data) -> FastAPI:
    app = FastAPI(title="ios-backup-vault viewer")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return _INDEX_HTML

    @app.get("/api/summary")
    async def summary():
        return data.summary()

    @app.get("/api/messages")
    async def messages():
        return data.messages()

    @app.get("/api/contacts")
    async def contacts():
        return data.contacts()

    @app.get("/api/calls")
    async def calls():
        return data.calls()

    @app.get("/api/media")
    async def media(limit: int = 200, offset: int = 0):
        items = data.media()
        return {"total": len(items), "offset": offset, "items": items[offset:offset + limit]}

    @app.get("/media/{file_id}")
    async def media_bytes(file_id: str):
        got = data.media_bytes(file_id)
        if got is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        content, mime = got
        return Response(content=content, media_type=mime)

    @app.get("/api/whatsapp")
    async def whatsapp():
        return data.whatsapp()

    @app.get("/api/chatgpt")
    async def chatgpt():
        return data.chatgpt()

    @app.get("/api/notes")
    async def notes():
        return data.notes()

    @app.get("/api/appscan")
    async def appscan():
        return data.appscan()

    @app.get("/api/search")
    async def search(q: str = ""):
        return data.search(q)

    @app.post("/api/export")
    async def export(payload: dict):
        name, content, mime = data.export(payload)
        return Response(content=content, media_type=mime,
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})

    @app.exception_handler(VaultError)
    async def _vault_error_handler(request: Request, exc: VaultError):
        return JSONResponse({"error": str(exc)}, status_code=503)

    @app.exception_handler(Exception)
    async def _generic_error_handler(request: Request, exc: Exception):
        logger.exception("뷰어 엔드포인트 오류")
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)

    return app
