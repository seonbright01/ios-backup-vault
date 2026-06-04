"""통합 SPA HTML(시각 셸). 디자인 목업을 임베드하고 JS를 실제 API에 연결.

cli view --backup 사전선택은 app 측에서 window.__PRESELECT_ID 주입으로 처리.
모든 동적 사용자 문자열은 JS esc() 로 이스케이프한다.
"""
INDEX_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>iOS 백업 도구</title>
<!--
  P9 통합 시각 셸 (로컬 전용 SPA, 시안)
  - 순수 HTML + CSS + 바닐라 JS. 외부 프레임워크/CDN 없음. 오프라인 로컬에서 열림.
  - 이 파일은 이후 FastAPI 앱의 _INDEX_HTML 문자열로 임베드된다.
  - 데이터는 정적 더미. 백엔드 연결 지점은 모두 "// TODO: GET/POST /api/..." 로 표시.
  - 모든 동적 사용자 문자열은 esc() 로 이스케이프한다.
-->
<style>
  /* ===== 디자인 토큰 (light = 기본, dark = prefers-color-scheme) ===== */
  :root {
    color-scheme: light dark;

    --bg:            #f6f7f9;
    --surface:       #ffffff;
    --surface-2:     #f0f2f5;
    --surface-sunken:#eceff3;
    --border:        #d8dde4;
    --border-strong: #c2c9d2;

    --text:          #1a1f27;
    --text-2:        #515b69;
    --text-3:        #76808f;

    --accent:        #2563eb;
    --accent-hover:  #1d4ed8;
    --accent-weak:   #e7effe;
    --on-accent:     #ffffff;

    --success:       #15803d;
    --success-weak:  #e3f3e9;
    --warn:          #b45309;
    --warn-weak:     #fbf0dd;
    --danger:        #b91c1c;
    --danger-weak:   #fbe6e6;
    --info:          #1d6fa5;
    --info-weak:     #e2f0f8;

    --console-bg:    #0e1320;
    --console-text:  #d4dbe7;
    --console-dim:   #6c7689;

    --shadow-sm: 0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.05);
    --shadow-md: 0 4px 12px rgba(16,24,40,.10);
    --shadow-lg: 0 16px 40px rgba(16,24,40,.20);

    --r-sm: 6px;
    --r-md: 10px;
    --r-lg: 14px;

    --sp-1: 4px;  --sp-2: 8px;  --sp-3: 12px; --sp-4: 16px;
    --sp-5: 20px; --sp-6: 24px; --sp-8: 32px; --sp-10: 40px;

    --focus: 0 0 0 2px var(--surface), 0 0 0 4px var(--accent);
  }

  @media (prefers-color-scheme: dark) {
    :root {
      --bg:            #0d1017;
      --surface:       #161b24;
      --surface-2:     #1d242f;
      --surface-sunken:#11161e;
      --border:        #2a323e;
      --border-strong: #3a434f;

      --text:          #e7ebf1;
      --text-2:        #aab4c2;
      --text-3:        #7f8b9b;

      --accent:        #5b8bf5;
      --accent-hover:  #6f9aff;
      --accent-weak:   #1a2740;
      --on-accent:     #0d1017;

      --success:       #4ade80;
      --success-weak:  #14271b;
      --warn:          #e0a64b;
      --warn-weak:     #2b2113;
      --danger:        #f17878;
      --danger-weak:   #2c1717;
      --info:          #6cc2ee;
      --info-weak:     #142733;

      --console-bg:    #090c12;
      --console-text:  #cdd6e3;
      --console-dim:   #5b6678;

      --shadow-sm: 0 1px 2px rgba(0,0,0,.4);
      --shadow-md: 0 4px 14px rgba(0,0,0,.5);
      --shadow-lg: 0 18px 44px rgba(0,0,0,.6);

      --focus: 0 0 0 2px var(--surface), 0 0 0 4px var(--accent);
    }
  }

  * { box-sizing: border-box; }

  html, body { height: 100%; }

  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue",
                 "Apple SD Gothic Neo", "Malgun Gothic", system-ui, sans-serif;
    font-size: 15px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }

  /* 데이터/식별자용 모노스페이스 + tabular figures */
  .mono { font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
          font-variant-numeric: tabular-nums; }

  a { color: var(--accent); }

  :focus-visible { outline: none; box-shadow: var(--focus); border-radius: var(--r-sm); }

  .visually-hidden {
    position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0;
    overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0;
  }

  .skip-link {
    position: absolute; left: var(--sp-3); top: -48px; z-index: 2000;
    background: var(--accent); color: var(--on-accent);
    padding: var(--sp-2) var(--sp-4); border-radius: var(--r-sm);
    transition: top .15s ease;
  }
  .skip-link:focus { top: var(--sp-3); }

  /* ===== 앱 레이아웃 ===== */
  .app { display: grid; grid-template-columns: 248px 1fr; min-height: 100dvh; }

  .sidebar {
    background: var(--surface);
    border-right: 1px solid var(--border);
    padding: var(--sp-5) var(--sp-3);
    display: flex; flex-direction: column; gap: var(--sp-2);
    position: sticky; top: 0; height: 100dvh;
  }

  .brand {
    display: flex; align-items: center; gap: var(--sp-3);
    padding: var(--sp-2) var(--sp-3) var(--sp-5);
  }
  .brand .logo {
    width: 32px; height: 32px; border-radius: 8px;
    background: var(--accent); color: var(--on-accent);
    display: grid; place-items: center; flex: none;
  }
  .brand .logo svg { width: 18px; height: 18px; }
  .brand .name { font-weight: 650; font-size: 15px; }
  .brand .sub { font-size: 12px; color: var(--text-3); }

  .nav-section { font-size: 11px; letter-spacing: .04em; text-transform: uppercase;
                 color: var(--text-3); padding: var(--sp-3) var(--sp-3) var(--sp-1); }

  .nav-item {
    appearance: none; border: 0; width: 100%; text-align: left;
    background: transparent; color: var(--text-2);
    font: inherit; cursor: pointer;
    display: flex; align-items: center; gap: var(--sp-3);
    padding: var(--sp-3); border-radius: var(--r-md);
    transition: background .12s ease, color .12s ease;
  }
  .nav-item svg { width: 18px; height: 18px; flex: none; }
  .nav-item:hover { background: var(--surface-2); color: var(--text); }
  .nav-item[aria-current="page"] {
    background: var(--accent-weak); color: var(--accent); font-weight: 600;
  }
  .nav-item:disabled { opacity: .45; cursor: not-allowed; }

  .sidebar-foot { margin-top: auto; padding: var(--sp-3); font-size: 12px; color: var(--text-3); }

  .main { min-width: 0; }

  /* 상단 탭 (좁은 화면에서 사이드바 대신 노출) */
  .topbar { display: none; }

  .page { padding: var(--sp-8); max-width: 1280px; margin: 0 auto; }
  .page-head { display: flex; align-items: flex-start; justify-content: space-between;
               gap: var(--sp-4); margin-bottom: var(--sp-6); flex-wrap: wrap; }
  .page-title { margin: 0; font-size: 22px; font-weight: 680; letter-spacing: -.01em; }
  .page-desc { margin: 4px 0 0; color: var(--text-2); font-size: 14px; }

  .view[hidden] { display: none; }

  /* ===== 버튼 ===== */
  .btn {
    appearance: none; cursor: pointer; font: inherit; font-weight: 550;
    border: 1px solid var(--border-strong); background: var(--surface); color: var(--text);
    padding: 9px 14px; border-radius: var(--r-md);
    display: inline-flex; align-items: center; gap: var(--sp-2);
    min-height: 38px; line-height: 1;
    transition: background .12s ease, border-color .12s ease, transform .04s ease;
  }
  .btn svg { width: 16px; height: 16px; }
  .btn:hover { background: var(--surface-2); }
  .btn:active { transform: translateY(1px); }
  .btn[disabled] { opacity: .5; cursor: not-allowed; }
  .btn-primary { background: var(--accent); border-color: var(--accent); color: var(--on-accent); }
  .btn-primary:hover { background: var(--accent-hover); border-color: var(--accent-hover); }
  .btn-danger { color: var(--danger); border-color: var(--border-strong); }
  .btn-danger:hover { background: var(--danger-weak); border-color: var(--danger); }
  .btn-ghost { border-color: transparent; background: transparent; }
  .btn-ghost:hover { background: var(--surface-2); }
  .btn-sm { min-height: 32px; padding: 6px 10px; font-size: 13px; }

  /* ===== 입력 ===== */
  .field { display: flex; flex-direction: column; gap: 6px; }
  .field label { font-size: 13px; font-weight: 550; color: var(--text-2); }
  .input {
    font: inherit; color: var(--text); background: var(--surface);
    border: 1px solid var(--border-strong); border-radius: var(--r-md);
    padding: 9px 12px; min-height: 38px; width: 100%;
  }
  .input::placeholder { color: var(--text-3); }
  .input:focus-visible { box-shadow: var(--focus); }
  .helper { font-size: 12px; color: var(--text-3); }
  .input-group { display: flex; gap: var(--sp-2); }
  .input-group .input { flex: 1; }
  .pw-wrap { position: relative; display: flex; }
  .pw-wrap .input { padding-right: 44px; }
  .pw-toggle {
    position: absolute; right: 4px; top: 50%; transform: translateY(-50%);
    appearance: none; border: 0; background: transparent; cursor: pointer;
    color: var(--text-3); padding: 6px; border-radius: var(--r-sm);
    display: grid; place-items: center;
  }
  .pw-toggle:hover { color: var(--text); background: var(--surface-2); }
  .pw-toggle svg { width: 18px; height: 18px; }

  /* ===== 배지 ===== */
  .badge {
    display: inline-flex; align-items: center; gap: 5px;
    font-size: 12px; font-weight: 600; line-height: 1;
    padding: 4px 8px; border-radius: 999px;
    border: 1px solid transparent;
  }
  .badge svg { width: 12px; height: 12px; }
  .badge-enc   { background: var(--accent-weak);  color: var(--accent); }
  .badge-full  { background: var(--info-weak);     color: var(--info); }
  .badge-incr  { background: var(--surface-2);     color: var(--text-2); border-color: var(--border); }
  .badge-ok    { background: var(--success-weak);  color: var(--success); }
  .badge-warn  { background: var(--warn-weak);      color: var(--warn); }
  .badge-err   { background: var(--danger-weak);    color: var(--danger); }
  .badge-idle  { background: var(--surface-2);      color: var(--text-2); border-color: var(--border); }
  .badge-run   { background: var(--info-weak);      color: var(--info); }

  /* ===== 백업 대시보드 ===== */
  .actionbar {
    display: flex; gap: var(--sp-3); align-items: flex-end; flex-wrap: wrap;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--r-lg); padding: var(--sp-4); margin-bottom: var(--sp-6);
    box-shadow: var(--shadow-sm);
  }
  .actionbar .field { flex: 1; min-width: 220px; }

  .card-grid {
    display: grid; gap: var(--sp-4);
    grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
  }

  .bcard {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--r-lg); box-shadow: var(--shadow-sm);
    display: flex; flex-direction: column; overflow: hidden;
    transition: box-shadow .15s ease, border-color .15s ease;
  }
  .bcard:hover { box-shadow: var(--shadow-md); border-color: var(--border-strong); }

  .bcard-head { display: flex; gap: var(--sp-3); padding: var(--sp-4) var(--sp-4) var(--sp-3); }
  .device-ico {
    width: 40px; height: 40px; flex: none; border-radius: 10px;
    background: var(--surface-2); color: var(--text-2);
    display: grid; place-items: center;
  }
  .device-ico svg { width: 22px; height: 22px; }
  .bcard-title { font-weight: 650; font-size: 16px; }
  .bcard-model { font-size: 13px; color: var(--text-2); }
  .bcard-badges { display: flex; gap: 6px; flex-wrap: wrap; padding: 0 var(--sp-4) var(--sp-3); }

  .bcard-meta {
    display: grid; grid-template-columns: auto 1fr; gap: 6px var(--sp-3);
    padding: var(--sp-3) var(--sp-4); font-size: 13px;
    border-top: 1px solid var(--border);
  }
  .bcard-meta dt { color: var(--text-3); }
  .bcard-meta dd { margin: 0; text-align: right; color: var(--text); }

  .pii-row { display: grid; grid-template-columns: auto 1fr; gap: 6px var(--sp-3);
             padding: var(--sp-3) var(--sp-4); font-size: 13px;
             border-top: 1px solid var(--border); background: var(--surface-sunken); }
  .pii-row dt { color: var(--text-3); }
  .pii-row dd { margin: 0; text-align: right; display: flex; align-items: center;
                justify-content: flex-end; gap: var(--sp-2); }
  .pii-val { min-width: 0; }
  .pii-toggle {
    appearance: none; border: 1px solid var(--border); background: var(--surface);
    color: var(--text-2); font: inherit; font-size: 11px; cursor: pointer;
    padding: 2px 7px; border-radius: var(--r-sm); line-height: 1.4;
  }
  .pii-toggle:hover { color: var(--text); background: var(--surface-2); }

  .bcard-foot { margin-top: auto; display: flex; gap: var(--sp-2);
                padding: var(--sp-3) var(--sp-4); border-top: 1px solid var(--border); }
  .bcard-foot .btn { flex: 1; justify-content: center; }

  /* ===== 모달 ===== */
  .modal-scrim {
    position: fixed; inset: 0; z-index: 1000;
    background: rgba(8,12,20,.55);
    display: grid; place-items: center; padding: var(--sp-4);
  }
  .modal-scrim[hidden] { display: none; }
  .modal {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--r-lg); box-shadow: var(--shadow-lg);
    width: 100%; max-width: 440px; overflow: hidden;
  }
  .modal-head { display: flex; align-items: flex-start; justify-content: space-between;
                gap: var(--sp-3); padding: var(--sp-5) var(--sp-5) var(--sp-3); }
  .modal-title { margin: 0; font-size: 17px; font-weight: 650; }
  .modal-sub { margin: 4px 0 0; font-size: 13px; color: var(--text-2); }
  .modal-body { padding: var(--sp-3) var(--sp-5) var(--sp-5); display: flex;
                flex-direction: column; gap: var(--sp-4); }
  .modal-foot { display: flex; gap: var(--sp-2); justify-content: flex-end;
                padding: var(--sp-4) var(--sp-5); border-top: 1px solid var(--border);
                background: var(--surface-2); }
  .modal-close { appearance: none; border: 0; background: transparent; cursor: pointer;
                 color: var(--text-3); padding: 4px; border-radius: var(--r-sm); }
  .modal-close:hover { color: var(--text); background: var(--surface-2); }
  .modal-close svg { width: 20px; height: 20px; display: block; }

  .alert { display: none; align-items: flex-start; gap: var(--sp-2);
           padding: var(--sp-3); border-radius: var(--r-md); font-size: 13px; }
  .alert svg { width: 16px; height: 16px; flex: none; margin-top: 1px; }
  .alert.is-error { display: flex; background: var(--danger-weak); color: var(--danger); }
  .alert.is-loading { display: flex; background: var(--info-weak); color: var(--info); }

  .spinner { width: 15px; height: 15px; border: 2px solid currentColor;
             border-top-color: transparent; border-radius: 50%; flex: none;
             animation: spin .7s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) { .spinner { animation-duration: 1.6s; } }

  /* ===== 열람 ===== */
  .viewer-bar {
    display: flex; align-items: center; justify-content: space-between;
    gap: var(--sp-4); flex-wrap: wrap;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--r-lg); padding: var(--sp-4); margin-bottom: var(--sp-5);
    box-shadow: var(--shadow-sm);
  }
  .viewer-open { display: flex; align-items: center; gap: var(--sp-3); }
  .viewer-open .device-ico { width: 36px; height: 36px; }
  .viewer-open .lbl { font-size: 12px; color: var(--text-3); }
  .viewer-open .nm { font-weight: 650; }

  .export-bar { display: flex; align-items: center; gap: var(--sp-3); flex-wrap: wrap; }
  .pick-row { display: flex; gap: var(--sp-2); align-items: flex-start; padding: 3px 0; cursor: pointer; }
  .pick-row input { margin-top: 3px; flex: none; }
  .conv > summary { list-style: revert; }
  .fmt-set { display: flex; gap: var(--sp-1); border: 1px solid var(--border);
             border-radius: var(--r-md); padding: 3px; background: var(--surface-2); }
  .fmt-chip { position: relative; }
  .fmt-chip input { position: absolute; opacity: 0; pointer-events: none; }
  .fmt-chip label { display: inline-flex; cursor: pointer; font-size: 13px; font-weight: 550;
                    padding: 5px 10px; border-radius: var(--r-sm); color: var(--text-2); }
  .fmt-chip input:checked + label { background: var(--surface); color: var(--text); box-shadow: var(--shadow-sm); }
  .fmt-chip input:focus-visible + label { box-shadow: var(--focus); }

  .tabs { display: flex; gap: 2px; border-bottom: 1px solid var(--border);
          margin-bottom: var(--sp-5); overflow-x: auto; }
  .tab {
    appearance: none; border: 0; background: transparent; font: inherit; cursor: pointer;
    color: var(--text-2); padding: var(--sp-3) var(--sp-4);
    border-bottom: 2px solid transparent; white-space: nowrap;
    margin-bottom: -1px; font-weight: 550;
  }
  .tab:hover { color: var(--text); }
  .tab[aria-selected="true"] { color: var(--accent); border-bottom-color: var(--accent); }

  .tabpanel[hidden] { display: none; }

  .summary-grid { display: grid; gap: var(--sp-4);
                  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); margin-bottom: var(--sp-5); }
  .stat { background: var(--surface); border: 1px solid var(--border);
          border-radius: var(--r-md); padding: var(--sp-4); }
  .stat .k { font-size: 12px; color: var(--text-3); }
  .stat .v { font-size: 24px; font-weight: 680; margin-top: 4px; letter-spacing: -.01em; }

  .panel { background: var(--surface); border: 1px solid var(--border);
           border-radius: var(--r-lg); box-shadow: var(--shadow-sm); overflow: hidden; }
  .panel-head { padding: var(--sp-4); border-bottom: 1px solid var(--border); font-weight: 600; }

  .msg-row { display: flex; gap: var(--sp-3); padding: var(--sp-3) var(--sp-4);
             border-bottom: 1px solid var(--border); }
  .msg-row:last-child { border-bottom: 0; }
  .avatar { width: 32px; height: 32px; border-radius: 50%; flex: none;
            background: var(--surface-2); color: var(--text-2); display: grid; place-items: center;
            font-size: 13px; font-weight: 600; }
  .msg-body { min-width: 0; flex: 1; }
  .msg-top { display: flex; gap: var(--sp-2); align-items: baseline; }
  .msg-name { font-weight: 600; font-size: 14px; }
  .msg-time { font-size: 12px; color: var(--text-3); }
  .msg-text { font-size: 14px; color: var(--text); margin-top: 2px; }

  .media-grid { display: grid; gap: var(--sp-2); padding: var(--sp-4);
                grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); }
  .media-tile { aspect-ratio: 1; border-radius: var(--r-md); background: var(--surface-2);
                border: 1px solid var(--border); display: grid; place-items: center; color: var(--text-3);
                position: relative; }
  .media-tile svg { width: 28px; height: 28px; }
  .media-tile .dur { position: absolute; right: 6px; bottom: 6px; font-size: 11px;
                     background: rgba(8,12,20,.7); color: #fff; padding: 1px 5px; border-radius: 4px; }

  .data-table { width: 100%; border-collapse: collapse; font-size: 14px; }
  .data-table th, .data-table td { text-align: left; padding: var(--sp-3) var(--sp-4);
                                   border-bottom: 1px solid var(--border); }
  .data-table th { font-size: 12px; text-transform: uppercase; letter-spacing: .03em;
                   color: var(--text-3); font-weight: 600; }
  .data-table tr:last-child td { border-bottom: 0; }

  /* ===== 새 이미징 (마법사) ===== */
  .wizard { display: grid; gap: var(--sp-5); max-width: 860px; }
  .steps { display: flex; gap: var(--sp-3); }
  .step-pill { flex: 1; display: flex; gap: var(--sp-3); align-items: center;
               background: var(--surface); border: 1px solid var(--border);
               border-radius: var(--r-md); padding: var(--sp-3) var(--sp-4); }
  .step-pill .n { width: 26px; height: 26px; flex: none; border-radius: 50%;
                  display: grid; place-items: center; font-size: 13px; font-weight: 650;
                  background: var(--surface-2); color: var(--text-2); }
  .step-pill[data-state="active"] { border-color: var(--accent); }
  .step-pill[data-state="active"] .n { background: var(--accent); color: var(--on-accent); }
  .step-pill[data-state="done"] .n { background: var(--success); color: #fff; }
  .step-pill .st { font-size: 12px; color: var(--text-3); }
  .step-pill .sl { font-weight: 600; font-size: 14px; }

  .wcard { background: var(--surface); border: 1px solid var(--border);
           border-radius: var(--r-lg); box-shadow: var(--shadow-sm); overflow: hidden; }
  .wcard-head { padding: var(--sp-4) var(--sp-5); border-bottom: 1px solid var(--border);
                display: flex; align-items: center; justify-content: space-between; gap: var(--sp-3); }
  .wcard-head h3 { margin: 0; font-size: 16px; }
  .wcard-body { padding: var(--sp-5); display: flex; flex-direction: column; gap: var(--sp-4); }

  .path-display { display: flex; align-items: center; gap: var(--sp-3);
                  background: var(--surface-sunken); border: 1px solid var(--border);
                  border-radius: var(--r-md); padding: var(--sp-3) var(--sp-4); }
  .path-display svg { width: 18px; height: 18px; color: var(--text-3); flex: none; }
  .path-display .p { font-size: 13px; word-break: break-all; }
  .path-display .empty { color: var(--text-3); }

  .check-grid { display: grid; gap: var(--sp-3);
                grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }
  .check { display: flex; gap: var(--sp-3); align-items: flex-start;
           background: var(--surface-sunken); border: 1px solid var(--border);
           border-radius: var(--r-md); padding: var(--sp-3) var(--sp-4); }
  .check .ic { width: 22px; height: 22px; flex: none; border-radius: 50%;
               display: grid; place-items: center; }
  .check .ic svg { width: 14px; height: 14px; }
  .check[data-ok="true"]  .ic { background: var(--success-weak); color: var(--success); }
  .check[data-ok="warn"]  .ic { background: var(--warn-weak); color: var(--warn); }
  .check[data-ok="false"] .ic { background: var(--danger-weak); color: var(--danger); }
  .check .ck { font-weight: 600; font-size: 14px; }
  .check .cv { font-size: 13px; color: var(--text-2); }

  .notice { display: flex; gap: var(--sp-3); align-items: center;
            background: var(--warn-weak); color: var(--warn);
            border: 1px solid color-mix(in srgb, var(--warn) 30%, transparent);
            border-radius: var(--r-md); padding: var(--sp-4); font-weight: 550; }
  .notice svg { width: 22px; height: 22px; flex: none; }

  .console {
    background: var(--console-bg); color: var(--console-text);
    border-radius: var(--r-md); padding: var(--sp-4);
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
    font-size: 13px; line-height: 1.6; height: 280px; overflow-y: auto;
    border: 1px solid var(--border);
  }
  .console .ln { display: flex; gap: var(--sp-3); }
  .console .t { color: var(--console-dim); flex: none; }
  .console .ok   { color: #5fd38a; }
  .console .warn { color: #e6b357; }
  .console .err  { color: #f08a8a; }
  .console .info { color: #79c2ee; }

  .run-foot { display: flex; align-items: center; justify-content: space-between;
              gap: var(--sp-3); flex-wrap: wrap; }

  /* ===== 반응형 ===== */
  @media (max-width: 880px) {
    .app { grid-template-columns: 1fr; }
    .sidebar { display: none; }
    .topbar {
      display: flex; gap: 2px; overflow-x: auto;
      position: sticky; top: 0; z-index: 50;
      background: var(--surface); border-bottom: 1px solid var(--border);
      padding: var(--sp-2);
    }
    .topbar .nav-item { width: auto; white-space: nowrap; }
    .page { padding: var(--sp-4); }
    .card-grid { grid-template-columns: 1fr; }
    .steps { flex-direction: column; }
  }
</style>
</head>
<body>
<a class="skip-link" href="#main">본문으로 건너뛰기</a>

<div class="app">
  <!-- ===== 사이드바 (넓은 화면) ===== -->
  <aside class="sidebar">
    <div class="brand">
      <span class="logo" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="2.5"/><line x1="9.5" y1="18.5" x2="14.5" y2="18.5"/></svg>
      </span>
      <span>
        <div class="name">iOS 백업 도구</div>
        <div class="sub">로컬 · 클라우드</div>
      </span>
    </div>

    <div class="nav-section">작업</div>
    <button class="nav-item" data-nav="dashboard" aria-current="page">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
      백업
    </button>
    <button class="nav-item" data-nav="imaging">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>
      새 이미징
    </button>

    <div class="nav-section">현재 백업</div>
    <button class="nav-item" data-nav="viewer" id="navViewer" disabled>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>
      열람
    </button>

    <div class="sidebar-foot">모든 데이터는 이 컴퓨터에만 저장됩니다.</div>
  </aside>

  <main class="main" id="main">
    <!-- ===== 상단 탭 (좁은 화면) ===== -->
    <nav class="topbar" aria-label="주요 탐색">
      <button class="nav-item" data-nav="dashboard" aria-current="page">백업</button>
      <button class="nav-item" data-nav="imaging">새 이미징</button>
      <button class="nav-item" data-nav="viewer" disabled>열람</button>
    </nav>

    <!-- ============ 화면 1: 백업 대시보드 ============ -->
    <section class="view page" id="view-dashboard" aria-labelledby="dash-title">
      <div class="page-head">
        <div>
          <h1 class="page-title" id="dash-title">백업</h1>
          <p class="page-desc">이 컴퓨터에서 발견된 iOS 백업입니다.</p>
        </div>
      </div>

      <div class="actionbar">
        <button class="btn btn-primary" id="addFolder">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M12 11v5M9.5 13.5h5"/></svg>
          폴더로 추가
        </button>
        <div class="field">
          <label for="pathInput">경로 직접 입력</label>
          <div class="input-group">
            <input class="input mono" id="pathInput" type="text" placeholder="/Users/me/Library/Application Support/MobileSync/Backup" autocomplete="off" spellcheck="false">
            <button class="btn" id="addPath">추가</button>
          </div>
        </div>
      </div>

      <div class="card-grid" id="cardGrid"><!-- renderDashboard() 가 채움 --></div>

      <!-- ===== 클라우드 소스 (GCS) ===== -->
      <div class="page-head" style="margin-top:var(--sp-6)">
        <div>
          <h2 class="page-title" style="font-size:18px">클라우드 백업</h2>
          <p class="page-desc">GCS에 보관된 백업입니다. [열기]를 누르면 보는 파일만 받아 로컬에서 복호화합니다.</p>
        </div>
        <button class="btn" id="cloudRefresh">새로고침</button>
      </div>
      <div class="card-grid" id="cloudGrid"><!-- renderCloud() 가 채움 --></div>

      <div class="cache-foot" style="margin-top:var(--sp-4);display:flex;align-items:center;justify-content:space-between;gap:var(--sp-3);border-top:1px solid var(--border);padding-top:var(--sp-3)">
        <span class="helper">캐시 용량: <span class="mono" id="cacheSize">—</span></span>
        <button class="btn btn-sm" id="cacheClear">캐시 비우기</button>
      </div>
    </section>

    <!-- ============ 화면 3: 열람 ============ -->
    <section class="view page" id="view-viewer" aria-labelledby="viewer-title" hidden>
      <h1 class="visually-hidden" id="viewer-title">백업 열람</h1>

      <div class="viewer-bar">
        <div class="viewer-open">
          <span class="device-ico" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="2" width="12" height="20" rx="2.5"/><line x1="10" y1="18.5" x2="14" y2="18.5"/></svg>
          </span>
          <span>
            <div class="lbl">현재 열린 백업 <span class="badge" id="openSource" hidden></span></div>
            <div class="nm" id="openDeviceName">—</div>
          </span>
        </div>
        <div class="export-bar">
          <label class="fmt-chip" title="현재 탭의 항목을 전체 선택/해제"><input type="checkbox" id="selectAll"><span>전체선택</span></label>
          <fieldset class="fmt-set" aria-label="내보내기 형식">
            <span class="fmt-chip"><input type="checkbox" id="fmt-json" checked><label for="fmt-json">JSON</label></span>
            <span class="fmt-chip"><input type="checkbox" id="fmt-html"><label for="fmt-html">HTML</label></span>
            <span class="fmt-chip"><input type="checkbox" id="fmt-csv"><label for="fmt-csv">CSV</label></span>
            <span class="fmt-chip"><input type="checkbox" id="fmt-txt"><label for="fmt-txt">TXT</label></span>
          </fieldset>
          <button class="btn" id="exportBtn">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12M7 10l5 5 5-5"/><path d="M5 21h14"/></svg>
            내보내기
          </button>
          <button class="btn btn-ghost" id="closeBackup">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
            닫기
          </button>
        </div>
      </div>

      <div class="tabs" role="tablist" aria-label="백업 내용">
        <button class="tab" role="tab" id="vtab-summary"   aria-controls="vp-summary"   aria-selected="true"  data-vtab="summary">요약</button>
        <button class="tab" role="tab" id="vtab-messages"  aria-controls="vp-messages"  aria-selected="false" data-vtab="messages" tabindex="-1">메시지</button>
        <button class="tab" role="tab" id="vtab-media"     aria-controls="vp-media"     aria-selected="false" data-vtab="media" tabindex="-1">사진·영상</button>
        <button class="tab" role="tab" id="vtab-contacts"  aria-controls="vp-contacts"  aria-selected="false" data-vtab="contacts" tabindex="-1">연락처</button>
        <button class="tab" role="tab" id="vtab-calls"     aria-controls="vp-calls"     aria-selected="false" data-vtab="calls" tabindex="-1">통화</button>
        <button class="tab" role="tab" id="vtab-whatsapp"  aria-controls="vp-whatsapp"  aria-selected="false" data-vtab="whatsapp" tabindex="-1">WhatsApp</button>
        <button class="tab" role="tab" id="vtab-chatgpt"   aria-controls="vp-chatgpt"   aria-selected="false" data-vtab="chatgpt" tabindex="-1">ChatGPT</button>
        <button class="tab" role="tab" id="vtab-notes"     aria-controls="vp-notes"     aria-selected="false" data-vtab="notes" tabindex="-1">메모</button>
      </div>

      <div class="tabpanel" role="tabpanel" id="vp-summary" aria-labelledby="vtab-summary"><!-- renderViewer() --></div>
      <div class="tabpanel" role="tabpanel" id="vp-messages" aria-labelledby="vtab-messages" hidden></div>
      <div class="tabpanel" role="tabpanel" id="vp-media" aria-labelledby="vtab-media" hidden></div>
      <div class="tabpanel" role="tabpanel" id="vp-contacts" aria-labelledby="vtab-contacts" hidden></div>
      <div class="tabpanel" role="tabpanel" id="vp-calls" aria-labelledby="vtab-calls" hidden></div>
      <div class="tabpanel" role="tabpanel" id="vp-whatsapp" aria-labelledby="vtab-whatsapp" hidden></div>
      <div class="tabpanel" role="tabpanel" id="vp-chatgpt" aria-labelledby="vtab-chatgpt" hidden></div>
      <div class="tabpanel" role="tabpanel" id="vp-notes" aria-labelledby="vtab-notes" hidden></div>
    </section>

    <!-- ============ 화면 4: 새 이미징 ============ -->
    <section class="view page" id="view-imaging" aria-labelledby="img-title" hidden>
      <div class="page-head">
        <div>
          <h1 class="page-title" id="img-title">새 이미징</h1>
          <p class="page-desc">연결된 기기를 이 컴퓨터로 백업합니다.</p>
        </div>
      </div>

      <div class="wizard">
        <ol class="steps" style="list-style:none;margin:0;padding:0">
          <li class="step-pill" data-state="active"><span class="n">1</span><span><span class="st">단계 1</span><span class="sl">저장 폴더</span></span></li>
          <li class="step-pill"><span class="n">2</span><span><span class="st">단계 2</span><span class="sl">사전점검</span></span></li>
          <li class="step-pill"><span class="n">3</span><span><span class="st">단계 3</span><span class="sl">백업 시작</span></span></li>
        </ol>

        <!-- 단계 1 -->
        <div class="wcard">
          <div class="wcard-head"><h3>① 저장 폴더 선택</h3></div>
          <div class="wcard-body">
            <button class="btn" id="pickFolder">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
              저장 폴더 선택
            </button>
            <div class="path-display">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
              <span class="p empty mono" id="targetPath">선택된 폴더가 없습니다</span>
            </div>
          </div>
        </div>

        <!-- 단계 2 -->
        <div class="wcard">
          <div class="wcard-head">
            <h3>② 사전점검</h3>
            <button class="btn btn-sm" id="runPrecheck">점검 실행</button>
          </div>
          <div class="wcard-body">
            <div class="notice">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/></svg>
              <span>아이폰 화면에서 <strong>“이 컴퓨터를 신뢰하시겠습니까?”</strong>가 나오면 <strong>“신뢰”</strong>를 누르세요.</span>
            </div>
            <div class="check-grid" id="checkGrid"><!-- renderPrecheck() --></div>
          </div>
        </div>

        <!-- 단계 3 -->
        <div class="wcard">
          <div class="wcard-head">
            <h3>③ 백업 시작</h3>
            <span class="badge badge-idle" id="runStatus">대기</span>
          </div>
          <div class="wcard-body">
            <div class="console" id="console" role="log" aria-live="polite" aria-label="백업 진행 로그">
              <div class="ln"><span class="t">--:--:--</span><span class="info">콘솔이 여기에 표시됩니다.</span></div>
            </div>
            <div class="run-foot">
              <span class="helper">로그는 이 컴퓨터에만 기록됩니다.</span>
              <div style="display:flex;gap:var(--sp-2)">
                <button class="btn" id="clearLog">로그 지우기</button>
                <button class="btn btn-primary" id="startBackup" disabled>백업 시작</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </main>
</div>

<!-- ===== 화면 2: 열기 모달 ===== -->
<div class="modal-scrim" id="openModal" hidden>
  <div class="modal" role="dialog" aria-modal="true" aria-labelledby="openModalTitle">
    <div class="modal-head">
      <div>
        <h2 class="modal-title" id="openModalTitle">백업 열기</h2>
        <p class="modal-sub" id="openModalSub">—</p>
      </div>
      <button class="modal-close" id="modalCloseX" aria-label="닫기">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
      </button>
    </div>
    <div class="modal-body">
      <div class="field">
        <label for="passphrase">패스프레이즈</label>
        <div class="pw-wrap">
          <input class="input" id="passphrase" type="password" autocomplete="off" placeholder="암호화 백업 패스프레이즈">
          <button class="pw-toggle" id="pwToggle" type="button" aria-label="패스프레이즈 표시" aria-pressed="false">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
        <span class="helper">암호화되지 않은 백업이면 비워 두세요.</span>
      </div>
      <div class="alert" id="modalAlert" role="alert" aria-live="assertive">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg>
        <span id="modalAlertText"></span>
      </div>
    </div>
    <div class="modal-foot">
      <button class="btn" id="modalCancel">취소</button>
      <button class="btn btn-primary" id="modalOpen">열기</button>
    </div>
  </div>
</div>

<script>
/* =========================================================================
   유틸: 모든 동적 사용자 문자열은 esc() 로 이스케이프한다.
   ========================================================================= */
function esc(s){
  return String(s == null ? "" : s)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}
function $(sel, root){ return (root||document).querySelector(sel); }
function $$(sel, root){ return Array.from((root||document).querySelectorAll(sel)); }

async function jget(u){
  const r = await fetch(u);
  let d = null; try { d = await r.json(); } catch(e) {}
  if(!r.ok) throw new Error((d && d.error) ? d.error : ("HTTP " + r.status));
  if(d && !Array.isArray(d) && d.error) throw new Error(d.error);
  return d;
}
async function jpost(u, body){
  const r = await fetch(u, {method:"POST", headers:{"Content-Type":"application/json"},
                           body: JSON.stringify(body || {})});
  let d = null; try { d = await r.json(); } catch(e) {}
  if(!r.ok && !(d && d.error)) throw new Error("HTTP " + r.status);
  return d || {};
}

function fmtSize(bytes){
  if(bytes == null) return "—";
  return (bytes / 1e9).toFixed(2) + " GB";
}

/* 백엔드에서 받은 백업 목록(메타 포함). renderDashboard 가 채운다. */
let BACKUPS = [];
const piiShown = {}; // { "<id>:serial": true }

/* =========================================================================
   라우팅 (사이드바/상단 탭으로 view 전환)
   ========================================================================= */
const VIEWS = ["dashboard", "viewer", "imaging"];
function navigate(view){
  VIEWS.forEach(v=>{ const el=$("#view-"+v); if(el) el.hidden = (v!==view); });
  $$(".nav-item[data-nav]").forEach(b=>{
    if(b.dataset.nav===view) b.setAttribute("aria-current","page");
    else b.removeAttribute("aria-current");
  });
  window.scrollTo(0,0);
}
$$(".nav-item[data-nav]").forEach(b=>{
  b.addEventListener("click", ()=>{ if(!b.disabled) navigate(b.dataset.nav); });
});

/* =========================================================================
   화면 1: 백업 대시보드
   ========================================================================= */
function maskShown(m){
  // 서버가 마스킹된 값을 보낸다. "보기"는 메타 reveal=1 재요청으로 처리.
  return m;
}

function piiRow(id, label, key, masked, revealed){
  if(masked == null || masked === "") {
    return '<dt>'+esc(label)+'</dt><dd><span class="pii-val mono">—</span></dd>';
  }
  const shownKey = id + ":" + key;
  const shown = !!piiShown[shownKey];
  const display = shown ? (revealed != null ? revealed : masked) : masked;
  return '<dt>'+esc(label)+'</dt>'
    + '<dd><span class="pii-val mono">'+esc(display)+'</span>'
    + '<button class="pii-toggle" data-pii="'+esc(shownKey)+'" '
    +   'aria-pressed="'+(shown?'true':'false')+'">'+(shown?'숨기기':'보기')+'</button></dd>';
}

function deviceLabel(b){ return b.device_name || "(이름 없음)"; }

async function loadDashboard(){
  const grid = $("#cardGrid");
  grid.innerHTML = '<p class="page-desc">로딩…</p>';
  try {
    BACKUPS = await jget("/api/backups");
  } catch(e) {
    grid.innerHTML = '<p class="page-desc">목록을 불러오지 못했습니다: '+esc(String(e.message||e))+'</p>';
    return;
  }
  renderDashboard();
}

function renderDashboard(){
  const grid = $("#cardGrid");
  if(!BACKUPS.length){
    grid.innerHTML = '<p class="page-desc">발견된 백업이 없습니다. 폴더를 추가하세요.</p>';
    return;
  }
  grid.innerHTML = BACKUPS.map(b => {
    const encBadge = b.is_encrypted
      ? '<span class="badge badge-enc"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>암호화</span>'
      : '<span class="badge badge-idle">비암호화</span>';
    const typeBadge = b.is_full
      ? '<span class="badge badge-full">전체</span>'
      : '<span class="badge badge-incr">증분</span>';
    const errRow = b.error
      ? '<dt>상태</dt><dd>'+esc(b.error)+'</dd>'
      : '';
    return ''
    + '<article class="bcard">'
    +   '<div class="bcard-head">'
    +     '<span class="device-ico" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="2" width="12" height="20" rx="2.5"/><line x1="10" y1="18.5" x2="14" y2="18.5"/></svg></span>'
    +     '<div><div class="bcard-title">'+esc(deviceLabel(b))+'</div><div class="bcard-model">'+esc(b.product_type)+'</div></div>'
    +   '</div>'
    +   '<div class="bcard-badges">'+encBadge+typeBadge+'</div>'
    +   '<dl class="bcard-meta">'
    +     '<dt>iOS / 빌드</dt><dd class="mono">'+esc(b.ios_version)+' ('+esc(b.build)+')</dd>'
    +     '<dt>UDID</dt><dd class="mono">'+esc(b.udid)+'</dd>'
    +     '<dt>이미징 시점</dt><dd class="mono">'+esc(b.imaged_at)+'</dd>'
    +     '<dt>스냅샷 기준일</dt><dd class="mono">'+esc(b.snapshot_date)+'</dd>'
    +     '<dt>용량</dt><dd class="mono">'+esc(fmtSize(b.size_bytes))+'</dd>'
    +     errRow
    +   '</dl>'
    +   '<dl class="pii-row">'
    +     piiRow(b.id, "시리얼", "serial", b.serial, b._serial)
    +     piiRow(b.id, "IMEI", "imei", b.imei, b._imei)
    +     piiRow(b.id, "전화번호", "phone", b.phone, b._phone)
    +   '</dl>'
    +   '<div class="bcard-foot">'
    +     '<button class="btn btn-primary btn-sm" data-open="'+esc(b.id)+'">열기</button>'
    +     '<button class="btn btn-danger btn-sm" data-remove="'+esc(b.id)+'">제거</button>'
    +   '</div>'
    + '</article>';
  }).join("");
}

/* 대시보드 이벤트 위임 */
$("#cardGrid").addEventListener("click", async (e)=>{
  const piiBtn = e.target.closest("[data-pii]");
  if(piiBtn){
    const shownKey = piiBtn.dataset.pii;
    const id = shownKey.split(":")[0];
    piiShown[shownKey] = !piiShown[shownKey];
    const b = BACKUPS.find(x=>x.id===id);
    // 처음 "보기"를 누르면 reveal=1 메타를 한 번 가져와 캐시.
    if(piiShown[shownKey] && b && b._serial == null){
      try {
        const m = await jget("/api/backups/"+encodeURIComponent(id)+"?reveal=1");
        b._serial = m.serial; b._imei = m.imei; b._phone = m.phone;
      } catch(e) {}
    }
    renderDashboard();
    return;
  }
  const openBtn = e.target.closest("[data-open]");
  if(openBtn){ openModal(openBtn.dataset.open); return; }
  const rmBtn = e.target.closest("[data-remove]");
  if(rmBtn){
    const id = rmBtn.dataset.remove;
    const b = BACKUPS.find(x=>x.id===id);
    if(!confirm("목록에서 제거할까요? (실제 파일은 삭제되지 않습니다)\\n" + (b ? deviceLabel(b) : id))) return;
    try { await jpost("/api/backups/"+encodeURIComponent(id)+"/remove", {}); }
    catch(e) { alert("제거 실패: " + (e.message||e)); }
    loadDashboard();
    return;
  }
});

/* =========================================================================
   화면 1b: 클라우드 백업(GCS) + 캐시
   ========================================================================= */
let CLOUD = [];
function cloudLabel(c){ return c.device_name || c.udid || "(클라우드 백업)"; }

async function loadCloud(){
  const grid = $("#cloudGrid");
  grid.innerHTML = '<p class="page-desc">불러오는 중…</p>';
  let d;
  try { d = await jget("/api/cloud/backups"); }
  catch(e){ grid.innerHTML = '<p class="page-desc">클라우드를 불러오지 못했습니다: '+esc(String(e.message||e))+'</p>'; return; }
  if(d && d.error){
    grid.innerHTML = '<p class="page-desc">클라우드 미설정 또는 오프라인: '+esc(String(d.error))+'</p>';
    return;
  }
  CLOUD = Array.isArray(d) ? d : [];
  renderCloud();
}
function renderCloud(){
  const grid = $("#cloudGrid");
  if(!CLOUD.length){ grid.innerHTML = '<p class="page-desc">클라우드에 백업이 없습니다.</p>'; return; }
  grid.innerHTML = CLOUD.map(c => {
    const encBadge = c.is_encrypted
      ? '<span class="badge badge-enc"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>암호화</span>'
      : '<span class="badge badge-idle">비암호화</span>';
    const typeBadge = c.is_full
      ? '<span class="badge badge-full">전체</span>'
      : '<span class="badge badge-incr">증분</span>';
    const errRow = c.error ? '<dt>상태</dt><dd>'+esc(c.error)+'</dd>' : '';
    return ''
    + '<article class="bcard">'
    +   '<div class="bcard-head">'
    +     '<span class="device-ico" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 10a4 4 0 0 0-7.6-1.5A3.5 3.5 0 1 0 6 16h11a3 3 0 0 0 1-5.8z"/></svg></span>'
    +     '<div><div class="bcard-title">'+esc(cloudLabel(c))+'</div><div class="bcard-model">'+esc(c.product_type||"")+'</div></div>'
    +   '</div>'
    +   '<div class="bcard-badges">'+encBadge+typeBadge+'</div>'
    +   '<dl class="bcard-meta">'
    +     '<dt>iOS / 빌드</dt><dd class="mono">'+esc(c.ios_version||"")+(c.build?' ('+esc(c.build)+')':'')+'</dd>'
    +     '<dt>UDID</dt><dd class="mono">'+esc(c.udid)+'</dd>'
    +     '<dt>이미징 시점</dt><dd class="mono">'+esc(c.imaged_at||"—")+'</dd>'
    +     '<dt>스냅샷 기준일</dt><dd class="mono">'+esc(c.snapshot_date||"—")+'</dd>'
    +     '<dt>용량</dt><dd class="mono">'+(c.size_bytes==null?"클라우드(원격)":esc(fmtSize(c.size_bytes)))+'</dd>'
    +     errRow
    +   '</dl>'
    +   '<dl class="pii-row">'
    +     piiRow(c.udid, "시리얼", "serial", c.serial, c._serial)
    +     piiRow(c.udid, "IMEI", "imei", c.imei, c._imei)
    +     piiRow(c.udid, "전화번호", "phone", c.phone, c._phone)
    +   '</dl>'
    +   '<div class="bcard-foot">'
    +     '<button class="btn btn-primary btn-sm" data-cloud-open="'+esc(c.udid)+'">열기</button>'
    +   '</div>'
    + '</article>';
  }).join("");
}
$("#cloudGrid").addEventListener("click", async (e)=>{
  const piiBtn = e.target.closest("[data-pii]");
  if(piiBtn){
    const shownKey = piiBtn.dataset.pii;
    const udid = shownKey.split(":")[0];
    piiShown[shownKey] = !piiShown[shownKey];
    const c = CLOUD.find(x=>x.udid===udid);
    if(piiShown[shownKey] && c && c._serial == null){
      try {
        const m = await jget("/api/cloud/backups/"+encodeURIComponent(udid)+"?reveal=1");
        c._serial = m.serial; c._imei = m.imei; c._phone = m.phone;
      } catch(e) {}
    }
    renderCloud();
    return;
  }
  const btn = e.target.closest("[data-cloud-open]");
  if(btn){ openCloudModal(btn.dataset.cloudOpen); return; }
});
$("#cloudRefresh").addEventListener("click", loadCloud);

async function loadCacheSize(){
  try {
    const d = await jget("/api/cache/size");
    $("#cacheSize").textContent = fmtSize(d.bytes);
  } catch(e){ $("#cacheSize").textContent = "—"; }
}
$("#cacheClear").addEventListener("click", async ()=>{
  if(!confirm("로컬 캐시를 모두 비울까요? (열린 클라우드 백업은 닫힙니다)")) return;
  try { await jpost("/api/cache/clear", {}); }
  catch(e){ alert("캐시 비우기 실패: " + (e.message||e)); }
  loadCacheSize();
});

$("#addFolder").addEventListener("click", async ()=>{
  try {
    const r = await jpost("/api/backups/scan-folder", {});
    if(r.error){ alert("폴더 추가 실패: " + r.error); return; }
    loadDashboard();
  } catch(e) { alert("폴더 추가 실패: " + (e.message||e)); }
});
$("#addPath").addEventListener("click", async ()=>{
  const p = $("#pathInput").value.trim();
  if(!p){ alert("경로를 입력하세요."); return; }
  try {
    const r = await jpost("/api/backups/scan-path", {path: p});
    if(r.error){ alert("경로 추가 실패: " + r.error); return; }
    $("#pathInput").value = "";
    loadDashboard();
  } catch(e) { alert("경로 추가 실패: " + (e.message||e)); }
});

/* =========================================================================
   화면 2: 열기 모달
   ========================================================================= */
let activeBackupId = null;
let activeBackupName = "—";
let lastFocused = null;
let cloudOpenUdid = null;  // 비-null이면 클라우드 열기 모드

function openModal(backupId){
  cloudOpenUdid = null;
  const b = BACKUPS.find(x=>x.id===backupId);
  activeBackupId = backupId;
  lastFocused = document.activeElement;
  $("#openModalSub").textContent = b ? (deviceLabel(b) + " · " + (b.product_type||"")) : "";
  $("#passphrase").value = "";
  setAlert(null);
  $("#openModal").hidden = false;
  $("#passphrase").focus();
}
function openCloudModal(udid){
  const c = CLOUD.find(x=>x.udid===udid);
  cloudOpenUdid = udid;
  activeBackupId = null;
  lastFocused = document.activeElement;
  $("#openModalSub").textContent = c ? ("클라우드 · " + cloudLabel(c)) : ("클라우드 · " + udid);
  $("#passphrase").value = "";
  setAlert(null);
  $("#openModal").hidden = false;
  $("#passphrase").focus();
}
function closeModal(){
  $("#openModal").hidden = true;
  cloudOpenUdid = null;
  if(lastFocused) lastFocused.focus();
}
function setAlert(kind, text){
  const a = $("#modalAlert");
  a.className = "alert" + (kind ? " is-"+kind : "");
  if(kind === "loading"){
    a.innerHTML = '<span class="spinner"></span><span>백업을 여는 중…</span>';
  } else if(kind === "error"){
    a.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg><span>'+esc(text)+'</span>';
  }
}

$("#modalCloseX").addEventListener("click", closeModal);
$("#modalCancel").addEventListener("click", closeModal);
$("#openModal").addEventListener("click", (e)=>{ if(e.target.id==="openModal") closeModal(); });
document.addEventListener("keydown", (e)=>{
  if(e.key==="Escape" && !$("#openModal").hidden) closeModal();
});

$("#pwToggle").addEventListener("click", ()=>{
  const inp = $("#passphrase");
  const show = inp.type === "password";
  inp.type = show ? "text" : "password";
  const btn = $("#pwToggle");
  btn.setAttribute("aria-pressed", show ? "true" : "false");
  btn.setAttribute("aria-label", show ? "패스프레이즈 숨기기" : "패스프레이즈 표시");
});

$("#modalOpen").addEventListener("click", async ()=>{
  const pass = $("#passphrase").value;
  setAlert("loading");
  // 클라우드 열기 분기
  if(cloudOpenUdid){
    const udid = cloudOpenUdid;
    try {
      const r = await jpost("/api/cloud/open", {udid: udid, passphrase: pass});
      if(r.ok){
        const c = CLOUD.find(x=>x.udid===udid);
        activeBackupName = (c && cloudLabel(c)) || udid;
        closeModal();
        openViewer(r.id);
        loadCacheSize();
      } else {
        setAlert("error", r.error || "패스프레이즈가 올바르지 않거나 클라우드에 연결할 수 없습니다.");
      }
    } catch(e) {
      setAlert("error", String(e.message||e));
    }
    return;
  }
  if(!activeBackupId) return;
  try {
    const r = await jpost("/api/backups/"+encodeURIComponent(activeBackupId)+"/open",
                          {passphrase: pass});
    if(r.ok){
      const b = BACKUPS.find(x=>x.id===activeBackupId);
      activeBackupName = (r.meta && r.meta.device_name) || (b && deviceLabel(b)) || "백업";
      closeModal();
      openViewer(activeBackupId);
    } else {
      setAlert("error", r.error || "패스프레이즈가 올바르지 않습니다.");
    }
  } catch(e) {
    setAlert("error", String(e.message||e));
  }
});

/* =========================================================================
   화면 3: 열람
   ========================================================================= */
function vurl(suffix){ return "/api/backups/"+encodeURIComponent(activeBackupId)+suffix; }

function openViewer(backupId){
  activeBackupId = backupId;
  $("#openDeviceName").textContent = activeBackupName || "—";
  const isCloud = String(backupId).startsWith("cloud-");
  const src = $("#openSource");
  if(src){
    src.hidden = false;
    src.textContent = isCloud ? "클라우드(GCS)" : "로컬";
    src.className = "badge " + (isCloud ? "badge-enc" : "badge-idle");
  }
  $("#navViewer").disabled = false;
  $$('.nav-item[data-nav="viewer"]').forEach(el=>el.disabled=false);
  navigate("viewer");
  selectVTab("summary");
}

function stat(k, v){ return '<div class="stat"><div class="k">'+esc(k)+'</div><div class="v mono">'+esc(v)+'</div></div>'; }
function msgRow(initial, name, text, time){
  return '<div class="msg-row"><span class="avatar" aria-hidden="true">'+esc(initial)+'</span>'
    + '<div class="msg-body"><div class="msg-top"><span class="msg-name">'+esc(name)+'</span>'
    + '<span class="msg-time">'+esc(time)+'</span></div>'
    + '<div class="msg-text">'+esc(text)+'</div></div></div>';
}
function dataTable(headers, rows){
  return '<div class="panel"><table class="data-table"><thead><tr>'
    + headers.map(h=>'<th>'+esc(h)+'</th>').join("")
    + '</tr></thead><tbody>'
    + rows.map(r=>'<tr>'+r.map(c=>'<td class="mono">'+esc(c)+'</td>').join("")+'</tr>').join("")
    + '</tbody></table></div>';
}
function panelErr(e){
  return '<div class="panel"><div class="panel-head" style="color:var(--danger)">오류</div>'
    + '<div style="padding:var(--sp-4)"><pre style="white-space:pre-wrap;margin:0">'+esc(String(e.message||e))+'</pre></div></div>';
}
function firstChar(s){ s = String(s||"?"); return s ? s[0] : "?"; }

/* 내보내기 선택용: 탭별 원본 데이터 캐시 + 체크박스 렌더 헬퍼 */
const vcache = {};
function pickText(g){
  return esc(g.text) + ' <small style="color:var(--text-3)">'
    + esc(g.timestamp||'') + (g.role ? ' · '+esc(g.role) : '') + '</small>';
}
function convBlock(i, title, sub, msgs){
  return '<details class="conv panel" style="margin-bottom:var(--sp-3)">'
    + '<summary style="padding:var(--sp-3) var(--sp-4);cursor:pointer">'
    + '<input type="checkbox" class="convchk" data-ci="'+i+'"> <b>'+esc(title)+'</b>'
    + (sub ? ' <small style="color:var(--text-3)">'+esc(sub)+'</small>' : '')
    + ' <small style="color:var(--text-3)">('+(msgs.length)+')</small></summary>'
    + '<div style="padding:0 var(--sp-4) var(--sp-3);display:flex;flex-direction:column;gap:4px">'
    + msgs.map((g,mi)=>'<label class="pick-row"><input type="checkbox" class="msgchk" data-ci="'+i+'" data-mi="'+mi+'"><span>'+pickText(g)+'</span></label>').join('')
    + '</div></details>';
}
function selTable(headers, rows){
  return '<div class="panel"><table class="data-table"><thead><tr><th></th>'
    + headers.map(h=>'<th>'+esc(h)+'</th>').join('')
    + '</tr></thead><tbody>'
    + rows.map((r,i)=>'<tr><td><input type="checkbox" class="rowchk" data-ri="'+i+'"></td>'
        + r.map(c=>'<td class="mono">'+esc(c)+'</td>').join('')+'</tr>').join('')
    + '</tbody></table></div>';
}

async function renderVPanel(name){
  const panel = $("#vp-"+name);
  panel.innerHTML = '<p class="page-desc">로딩…</p>';
  try {
    if(name === "summary"){
      const s = await jget(vurl("/summary"));
      panel.innerHTML = '<div class="summary-grid">'
        + Object.entries(s).map(([k,v])=>stat(String(k), String(v))).join("")
        + '</div>';
    } else if(name === "messages"){
      const c = await jget(vurl("/messages")); vcache.messages = c;
      panel.innerHTML = c.map((conv,i)=>convBlock(i,
          conv.name||conv.chat_identifier||"(대화)", conv.chat_identifier||"",
          conv.messages||[])).join("") || '<p class="page-desc">메시지가 없습니다.</p>';
    } else if(name === "media"){
      const d = await jget(vurl("/media?limit=200&offset=0"));
      const items = d.items || [];
      panel.innerHTML = '<div class="panel"><div class="media-grid">'
        + items.map(x=>{
            const u = esc(vurl("/media/"+encodeURIComponent(x.file_id)));
            const chk = '<input type="checkbox" class="mchk" data-fid="'+esc(x.file_id)+'" aria-label="선택" style="position:absolute;top:6px;left:6px;width:18px;height:18px;z-index:2">';
            const inner = x.kind === "video"
              ? '<video controls src="'+u+'"></video>'
              : '<img loading="lazy" style="width:100%;height:100%;object-fit:cover;border-radius:inherit" src="'+u+'">';
            return '<div class="media-tile" style="position:relative">'+chk+inner+'</div>';
          }).join("") + '</div></div>';
    } else if(name === "contacts"){
      const a = await jget(vurl("/contacts")); vcache.contacts = a;
      panel.innerHTML = selTable(["이름","값"],
        a.map(x=>[x.name, (x.values||[]).join(", ")]));
    } else if(name === "calls"){
      const a = await jget(vurl("/calls")); vcache.calls = a;
      panel.innerHTML = selTable(["상대","시각","길이(초)","방향"],
        a.map(x=>[x.name ? (x.name+" ("+x.address+")") : x.address,
                  x.timestamp, x.duration_sec, x.originated?"발신":"수신"]));
    } else if(name === "whatsapp"){
      const c = await jget(vurl("/whatsapp")); vcache.whatsapp = c;
      panel.innerHTML = c.map((conv,i)=>convBlock(i, conv.name||"(대화)", "",
          conv.messages||[])).join("") || '<p class="page-desc">대화가 없습니다.</p>';
    } else if(name === "chatgpt"){
      const c = await jget(vurl("/chatgpt")); vcache.chatgpt = c;
      panel.innerHTML = c.map((conv,i)=>convBlock(i, conv.title||"(대화)", conv.created||"",
          conv.messages||[])).join("") || '<p class="page-desc">대화가 없습니다.</p>';
    } else if(name === "notes"){
      const c = await jget(vurl("/notes")); vcache.notes = c;
      panel.innerHTML = c.map((n,i)=>
        '<details class="panel" style="margin-bottom:var(--sp-3)"><summary style="padding:var(--sp-3) var(--sp-4);cursor:pointer">'
        + '<input type="checkbox" class="rowchk" data-ri="'+i+'"> '
        + esc(n.title) + ' <small style="color:var(--text-3)">'+esc(n.modified)+'</small></summary>'
        + '<pre style="white-space:pre-wrap;font-family:inherit;padding:0 var(--sp-4) var(--sp-4);margin:0">'+esc(n.body)+'</pre></details>'
      ).join("") || '<p class="page-desc">메모가 없습니다.</p>';
    }
    if($("#selectAll")) $("#selectAll").checked = false;
  } catch(e) {
    panel.innerHTML = panelErr(e);
  }
}

/* 열람 탭 (role=tablist, 키보드 화살표 지원) */
const VTABS = ["summary","messages","media","contacts","calls","whatsapp","chatgpt","notes"];
let currentVTab = "summary";
function selectVTab(name){
  currentVTab = name;
  VTABS.forEach(t=>{
    const tab = $("#vtab-"+t), panel = $("#vp-"+t);
    const on = (t===name);
    tab.setAttribute("aria-selected", on?"true":"false");
    tab.tabIndex = on?0:-1;
    panel.hidden = !on;
  });
  renderVPanel(name);
}
$$(".tab[data-vtab]").forEach(tab=>{
  tab.addEventListener("click", ()=>selectVTab(tab.dataset.vtab));
  tab.addEventListener("keydown",(e)=>{
    const i = VTABS.indexOf(tab.dataset.vtab);
    let ni = null;
    if(e.key==="ArrowRight") ni=(i+1)%VTABS.length;
    else if(e.key==="ArrowLeft") ni=(i-1+VTABS.length)%VTABS.length;
    else if(e.key==="Home") ni=0;
    else if(e.key==="End") ni=VTABS.length-1;
    if(ni!==null){ e.preventDefault(); selectVTab(VTABS[ni]); $("#vtab-"+VTABS[ni]).focus(); }
  });
});

$("#closeBackup").addEventListener("click", async ()=>{
  if(activeBackupId){
    try { await jpost("/api/backups/"+encodeURIComponent(activeBackupId)+"/close", {}); }
    catch(e) {}
  }
  activeBackupId = null;
  $("#navViewer").disabled = true;
  $$('.nav-item[data-nav="viewer"]').forEach(el=>el.disabled=true);
  navigate("dashboard");
  loadDashboard();
});

/* 전체선택: 현재 패널의 모든 체크박스 토글 */
$("#selectAll").addEventListener("change", (e)=>{
  const panel = $("#vp-"+currentVTab); if(!panel) return;
  panel.querySelectorAll("input.convchk,input.msgchk,input.rowchk,input.mchk")
       .forEach(c=>{ c.checked = e.target.checked; });
});
/* 대화 체크 시 하위 메시지 동기화 */
document.addEventListener("change", (e)=>{
  const t = e.target;
  if(t && t.classList && t.classList.contains("convchk")){
    const d = t.closest("details");
    if(d) d.querySelectorAll("input.msgchk").forEach(m=>{ m.checked = t.checked; });
  }
});

$("#exportBtn").addEventListener("click", async ()=>{
  const fmts = ["json","html","csv","txt"].filter(f=>$("#fmt-"+f).checked);
  const tab = currentVTab;
  const panel = $("#vp-"+tab);
  const cache = vcache[tab] || [];
  const items = {}; let media = [];
  if(["messages","whatsapp","chatgpt"].includes(tab)){
    const out = [];
    (panel ? panel.querySelectorAll("details.conv") : []).forEach(d=>{
      const cv = d.querySelector("input.convchk"); if(!cv) return;
      const i = +cv.dataset.ci; const src = cache[i]; if(!src) return;
      const checks = [...d.querySelectorAll("input.msgchk:checked")];
      if(!cv.checked && checks.length === 0) return;
      const msgs = checks.length ? checks.map(c=>src.messages[+c.dataset.mi]).filter(Boolean) : src.messages;
      out.push(Object.assign({}, src, {messages: msgs}));
    });
    items[tab] = out;
  } else if(["contacts","calls","notes"].includes(tab)){
    items[tab] = [...(panel ? panel.querySelectorAll("input.rowchk:checked") : [])]
      .map(c=>cache[+c.dataset.ri]).filter(Boolean);
  } else if(tab === "media"){
    media = [...(panel ? panel.querySelectorAll("input.mchk:checked") : [])].map(c=>c.dataset.fid);
  } else {
    alert("이 탭(요약)은 내보내기 대상이 아닙니다. 메시지·연락처·사진 등에서 선택하세요."); return;
  }
  const count = Object.values(items).reduce((a,b)=>a+(b?b.length:0),0) + media.length;
  if(count === 0){ alert("선택된 항목이 없습니다. 항목을 체크하거나 '전체선택'을 누르세요."); return; }
  const payload = {formats: fmts.length?fmts:["json"], items: items, media_file_ids: media};
  try {
    const res = await fetch(vurl("/export"), {method:"POST",
      headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload)});
    if(!res.ok) throw new Error("HTTP " + res.status);
    const cd = res.headers.get("Content-Disposition")||"";
    const mt = cd.match(/filename="([^"]+)"/);
    const fn = mt ? mt[1] : "export.bin";
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href=url; a.download=fn;
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  } catch(e) { alert("내보내기 실패: " + (e.message||e)); }
});

/* =========================================================================
   화면 4: 새 이미징 (마법사)
   ========================================================================= */
let targetPath = null;
let precheckPassed = false;

function setStep(n, state){
  const pill = $$(".step-pill")[n-1];
  if(pill) pill.dataset.state = state;
}

$("#pickFolder").addEventListener("click", async ()=>{
  try {
    const r = await jpost("/api/imaging/pick-folder", {});
    if(r.error){ alert("폴더 선택 실패: " + r.error); return; }
    if(!r.path) return; // 취소
    targetPath = r.path;
    const el = $("#targetPath");
    el.textContent = r.path;
    el.classList.remove("empty");
    setStep(1, "done"); setStep(2, "active");
  } catch(e) { alert("폴더 선택 실패: " + (e.message||e)); }
});

$("#runPrecheck").addEventListener("click", async ()=>{
  const grid = $("#checkGrid");
  grid.innerHTML = '<p class="cv">점검 중…</p>';
  let p;
  try { p = await jget("/api/imaging/precheck" + (targetPath ? ("?target="+encodeURIComponent(targetPath)) : "")); }
  catch(e) { grid.innerHTML = '<div class="check" data-ok="false"><span class="ic" aria-hidden="true"></span><div><div class="ck">점검 실패</div><div class="cv">'+esc(String(e.message||e))+'</div></div></div>'; return; }

  let checks;
  if(p.error){
    checks = [{ ok:"false", label:"기기 점검", value: p.error + (p.hint ? (" — " + p.hint) : "") }];
    precheckPassed = false;
  } else {
    checks = [
      { ok:"true",  label:"기기 연결",   value: p.udid ? (p.udid + " 인식됨") : "인식됨" },
      { ok:"true",  label:"신뢰 상태",   value:"이 컴퓨터를 신뢰함" },
      { ok: p.backup_encryption_enabled ? "true":"warn", label:"백업 암호화",
        value: p.backup_encryption_enabled ? "설정됨" : "미설정 — 권장됨" },
      { ok:"true",  label:"예상 용량",   value:"약 " + fmtSize(p.estimated_backup_bytes) },
      { ok: p.fits ? "true":"false", label:"여유 공간",
        value: fmtSize(p.free_bytes) + " 사용 가능 / 필요 " + fmtSize(p.required_bytes) },
    ];
    precheckPassed = !!p.fits;
  }
  grid.innerHTML = checks.map(c=>{
    const ic = c.ok==="true"
      ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 6"/></svg>'
      : c.ok==="warn"
      ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8v5M12 17h.01"/></svg>'
      : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12M18 6 6 18"/></svg>';
    return '<div class="check" data-ok="'+esc(c.ok)+'"><span class="ic" aria-hidden="true">'+ic+'</span>'
      + '<div><div class="ck">'+esc(c.label)+'</div><div class="cv">'+esc(c.value)+'</div></div></div>';
  }).join("");
  $("#startBackup").disabled = !precheckPassed || !targetPath;
  setStep(2, precheckPassed ? "done" : "active");
  if(precheckPassed) setStep(3, "active");
});

/* 콘솔 로그 헬퍼 (모노스페이스, 자동 스크롤) */
function nowTs(){
  const d = new Date();
  const p = n => String(n).padStart(2,"0");
  return p(d.getHours())+":"+p(d.getMinutes())+":"+p(d.getSeconds());
}
function logLine(text, kind){
  const con = $("#console");
  const ln = document.createElement("div");
  ln.className = "ln";
  ln.innerHTML = '<span class="t">'+esc(nowTs())+'</span><span class="'+esc(kind||"")+'">'+esc(text)+'</span>';
  con.appendChild(ln);
  con.scrollTop = con.scrollHeight;
}
function setRunStatus(label, cls){
  const b = $("#runStatus");
  b.textContent = label;
  b.className = "badge " + cls;
}

$("#clearLog").addEventListener("click", ()=>{ $("#console").innerHTML = ""; });

let imagingSource = null;
$("#startBackup").addEventListener("click", async ()=>{
  if(!targetPath){ alert("저장 폴더를 먼저 선택하세요."); return; }
  $("#startBackup").disabled = true;
  setRunStatus("진행", "badge-run");
  let jobId;
  try {
    const r = await jpost("/api/imaging/start", {target: targetPath});
    if(r.error){ logLine(r.error, "err"); setRunStatus("오류","badge-err"); $("#startBackup").disabled=false; return; }
    jobId = r.job_id;
  } catch(e) {
    logLine(String(e.message||e), "err"); setRunStatus("오류","badge-err"); $("#startBackup").disabled=false; return;
  }
  // SSE 라이브 로그.
  if(imagingSource){ imagingSource.close(); imagingSource = null; }
  imagingSource = new EventSource("/api/imaging/stream?job_id=" + encodeURIComponent(jobId));
  imagingSource.onmessage = (ev)=>{
    let m; try { m = JSON.parse(ev.data); } catch(e) { return; }
    if(m.state === "done"){
      setRunStatus("완료", "badge-ok");
      logLine("백업 완료 — 목록에 등록되었습니다.", "ok");
      imagingSource.close(); imagingSource = null;
      $("#startBackup").disabled = false;
      loadDashboard();
    } else if(m.state === "error"){
      setRunStatus("오류", "badge-err");
      logLine("오류: " + (m.error||""), "err");
      imagingSource.close(); imagingSource = null;
      $("#startBackup").disabled = false;
    } else if(m.text != null){
      logLine(m.text, m.kind || "");
    }
  };
  imagingSource.onerror = ()=>{
    if(imagingSource){ imagingSource.close(); imagingSource = null; }
    setRunStatus("연결 끊김", "badge-warn");
    $("#startBackup").disabled = false;
  };
});

/* =========================================================================
   초기 렌더
   ========================================================================= */
loadDashboard();
loadCloud();
loadCacheSize();
navigate("dashboard");

/* 서버가 사전선택 백업 id를 주입하면 열기 모달을 띄운다(cli view --backup). */
if(window.__PRESELECT_ID){
  // 목록 로딩 후 모달 오픈.
  setTimeout(()=>openModal(window.__PRESELECT_ID), 300);
}

</script>
</body>
</html>
"""
