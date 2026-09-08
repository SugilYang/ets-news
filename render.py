#!/usr/bin/env python3
"""
이티에스 산업 브리핑 — 지면 생성기 v3

data/*.json (하루치 내용)을 읽어 정적 사이트를 생성합니다.
  index.html                : 홈 = 가장 최근 브리핑
  briefings/<날짜>.html     : 날짜별 브리핑 (◀ 이전 / 다음 ▶ 이동)
  archive.html              : 지난 자료 목록
  companies/index.html      : 회사별 모아보기 목록
  companies/<회사>.html     : 회사별 누적 타임라인
  search.html               : 검색(키워드·회사)
  weekly.html               : 최근 7일 회사별 주간 요약(사실 롤업)
  search-index.json         : 검색 인덱스

원칙: 사실(팩트) 중심. 디자인은 이 파일에 고정, 내용은 data/로 매일 추가.
표준 라이브러리만 사용.
"""
from __future__ import annotations
import html, json, re, sys
from datetime import date as _date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
BRIEF = ROOT / "briefings"
COMP = ROOT / "companies"

SITE = "이티에스 산업 브리핑"
SITE_EN = "ETS INDUSTRY BRIEFING"
LOGO = "assets/logo.png"   # 회사 로고 (없으면 자동 숨김)

NAV = [
    ("index.html", "오늘 브리핑", "today"),
    ("archive.html", "지난 자료", "archive"),
    ("companies/index.html", "회사별", "companies"),
    ("search.html", "검색", "search"),
    ("weekly.html", "주간 요약", "weekly"),
]

# ---------------------------------------------------------------- utils
def esc(v) -> str:
    return html.escape(str(v if v is not None else ""), quote=True)

def strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "")

def slug(name: str) -> str:
    s = re.sub(r"[^0-9A-Za-z가-힣]+", "-", name or "").strip("-").lower()
    return s or "etc"

def parse_date(s: str) -> _date | None:
    try:
        y, m, d = s.split("-"); return _date(int(y), int(m), int(d))
    except Exception:
        return None

# ---------------------------------------------------------------- style
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@700;900'
         '&family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">')

STYLE = """
:root{
  --ink:#16202b;--text:#2b3644;--muted:#6a7688;--paper:#f3f5f8;--card:#fff;--line:#e1e6ed;
  --accent:#0e9b86;--accent-bg:#e3f4f0;--accent-ink:#0b7a6a;--brand-gray:#5b6670;
  --c-blue:#1d4f8a;--c-blue-bg:#e9f0f9;--c-teal:#0e9b86;--c-teal-bg:#e3f4f0;
  --c-violet:#5b3fb8;--c-violet-bg:#efeafb;--c-rust:#b8442e;--c-rust-bg:#fbebe7;
  --c-amber:#946400;--c-amber-bg:#faf2dc;--c-slate:#4b5b70;--c-slate-bg:#eceff4;
  --serif:'Noto Serif KR','Apple SD Gothic Neo','Malgun Gothic',serif;
  --sans:'Noto Sans KR','Apple SD Gothic Neo','Malgun Gothic',system-ui,sans-serif;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--text);font-family:var(--sans);line-height:1.6;
  font-variant-numeric:tabular-nums}
a{color:inherit}
.wrap{max-width:1200px;margin:0 auto;padding:0 18px 48px}

/* 브랜드 바(제호) */
.masthead{background:#fff;border-bottom:3px solid var(--accent)}
.mast-inner{max-width:1200px;margin:0 auto;padding:14px 18px;display:flex;align-items:center;gap:18px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:16px;min-width:0}
.brand .logo{height:44px;width:auto;display:block}
.brand .divider{width:1px;height:38px;background:var(--line)}
.brand .name{font-family:var(--serif);font-weight:800;font-size:23px;color:var(--ink);line-height:1.15;letter-spacing:.01em}
.brand .name small{display:block;font-family:var(--sans);font-weight:500;font-size:10.5px;color:var(--brand-gray);
  letter-spacing:.22em;margin-bottom:3px}
.mast-meta{margin-left:auto;text-align:right;font-size:13px;color:var(--muted);line-height:1.4}
.mast-meta b{display:block;color:var(--ink);font-size:14px}

/* 내비 */
.nav{background:#1e2a36}
.nav-inner{max-width:1200px;margin:0 auto;display:flex;gap:2px;padding:0 10px;overflow-x:auto}
.nav a{color:#c9d3df;font-size:13.5px;font-weight:600;padding:11px 14px;text-decoration:none;
  border-bottom:3px solid transparent;white-space:nowrap}
.nav a:hover{color:#fff}
.nav a.on{color:#fff;border-bottom-color:var(--accent)}

/* 날짜 이동 */
.datenav{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:16px 0 0;
  background:#fff;border:1px solid var(--line);border-radius:10px;padding:8px 12px;font-size:13px}
.datenav a{text-decoration:none;color:var(--accent-ink);font-weight:700;padding:4px 8px;border-radius:6px}
.datenav a:hover{background:var(--accent-bg)}
.datenav .cur{font-weight:800;color:var(--ink);font-size:14px}
.datenav .dis{color:#b9c2cd;padding:4px 8px}
.lead{margin:14px 0 0;background:var(--accent-bg);border-left:4px solid var(--accent);border-radius:0 8px 8px 0;
  padding:10px 14px;font-size:13.5px;color:var(--accent-ink)}
.lead b{color:var(--ink)}

/* 카드 */
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:18px}
@media(max-width:840px){.grid{grid-template-columns:1fr}}
.full{grid-column:1 / -1}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;
  box-shadow:0 1px 2px rgba(22,32,43,.04)}
.card-head{display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:2px solid var(--line)}
.card-head .icon{width:34px;height:34px;border-radius:9px;display:flex;align-items:center;justify-content:center;
  font-size:17px;flex:none}
.card-head h3{margin:0;font-family:var(--serif);font-size:17px;font-weight:800;color:var(--ink)}
.card-head .sub{font-family:var(--sans);font-size:12px;color:var(--muted);font-weight:500;margin-left:4px}
.card-head .cnt{margin-left:auto;font-size:11px;color:var(--muted);background:var(--c-slate-bg);padding:2px 9px;border-radius:20px}
.card-body{padding:2px 16px 8px}
.item{padding:12px 0;border-bottom:1px solid var(--line)}
.item:last-child{border-bottom:0}
.item .h{margin:0;font-size:15px;font-weight:700;line-height:1.45;color:var(--ink);text-wrap:balance}
.item .h a{text-decoration:none;border-bottom:1px solid transparent}
.item .h a:hover{color:var(--accent-ink);border-bottom-color:var(--accent)}
.item .h a::after{content:" ↗";font-size:11px;color:var(--accent);font-weight:500}
.item .b{margin:5px 0 0;font-size:13.2px;color:var(--text);line-height:1.7;max-width:72ch}
.item .b b{color:var(--ink)}
.item .meta{margin-top:6px;font-size:11.5px;color:var(--muted);display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.chip{display:inline-block;font-size:11px;font-weight:700;padding:1px 8px;border-radius:20px;
  background:var(--accent-bg);color:var(--accent-ink)}
.chip.k{background:var(--c-slate-bg);color:var(--c-slate)}
.accent-blue .icon{background:var(--c-blue-bg)} .accent-blue .card-head{border-bottom-color:var(--c-blue)}
.accent-teal .icon{background:var(--c-teal-bg)} .accent-teal .card-head{border-bottom-color:var(--c-teal)}
.accent-violet .icon{background:var(--c-violet-bg)} .accent-violet .card-head{border-bottom-color:var(--c-violet)}
.accent-rust .icon{background:var(--c-rust-bg)} .accent-rust .card-head{border-bottom-color:var(--c-rust)}
.accent-amber .icon{background:var(--c-amber-bg)} .accent-amber .card-head{border-bottom-color:var(--c-amber)}
.accent-slate .icon{background:var(--c-slate-bg)} .accent-slate .card-head{border-bottom-color:var(--c-slate)}
/* 구버전 호환 */
.accent-purple .icon{background:var(--c-violet-bg)} .accent-purple .card-head{border-bottom-color:var(--c-violet)}
.accent-red .icon{background:var(--c-rust-bg)} .accent-red .card-head{border-bottom-color:var(--c-rust)}
.accent-gray .icon{background:var(--c-slate-bg)}

/* 목록 페이지 공통 */
.page-title{font-family:var(--serif);font-size:22px;font-weight:800;color:var(--ink);margin:22px 0 4px}
.page-sub{font-size:13px;color:var(--muted);margin:0 0 6px}
.arc-list{margin-top:16px;display:grid;gap:10px}
.arc{display:flex;gap:14px;align-items:center;background:#fff;border:1px solid var(--line);border-radius:10px;
  padding:13px 16px;text-decoration:none}
.arc:hover{border-color:var(--accent)}
.arc .date{flex:none;font-weight:800;font-size:15px;width:118px;color:var(--ink)}
.arc .date small{display:block;color:var(--muted);font-weight:500;font-size:11px}
.arc .top{font-size:13px;color:var(--muted)} .arc .top b{color:var(--ink)}

/* 회사별 */
.co-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin-top:16px}
.co{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px 16px;text-decoration:none}
.co:hover{border-color:var(--accent)}
.co .n{font-family:var(--serif);font-weight:800;font-size:16px;color:var(--ink)}
.co .m{font-size:12px;color:var(--muted);margin-top:4px}
.co .m b{color:var(--accent-ink)}
.dgroup{margin-top:18px}
.dgroup h3{font-size:13px;color:var(--muted);font-weight:700;letter-spacing:.04em;margin:0 0 6px;
  padding-bottom:6px;border-bottom:2px solid var(--line)}
.dgroup h3 b{color:var(--ink);font-size:15px;margin-right:8px}
.list{background:#fff;border:1px solid var(--line);border-radius:12px;padding:2px 16px 8px}

/* 검색 */
.sbar{display:flex;gap:8px;margin-top:16px;flex-wrap:wrap}
.sbar input,.sbar select{font:inherit;font-size:14px;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:#fff}
.sbar input{flex:1;min-width:220px}
.sbar input:focus,.sbar select:focus{outline:2px solid var(--accent);outline-offset:1px}
.scount{font-size:12.5px;color:var(--muted);margin:10px 2px 0}
.sres{margin-top:10px}
.sres .item .meta{margin-top:4px}

/* 푸터 */
.footer{margin-top:24px;font-size:11.5px;color:var(--muted);border-top:1px solid var(--line);padding-top:12px;line-height:1.7}

@media(max-width:640px){
  .mast-inner{gap:12px} .brand .logo{height:36px} .brand .name{font-size:19px}
  .mast-meta{margin-left:0;text-align:left;width:100%}
  .item .h{font-size:14.5px}
}
@media print{
  .nav,.datenav,.sbar,.scount{display:none!important}
  body{background:#fff} .masthead{border-bottom:2px solid #000}
  .card,.list{box-shadow:none;border-color:#bbb;break-inside:avoid;page-break-inside:avoid}
  .item .h a::after{content:""}
  a{text-decoration:none}
}
"""

# ---------------------------------------------------------------- shell
def head(title: str, active: str, base: str, meta_html: str = "") -> str:
    nav = "".join(
        f'<a href="{base}{href}" class="{"on" if key == active else ""}">{esc(label)}</a>'
        for href, label, key in NAV
    )
    return (
        f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{esc(title)}</title>{FONTS}<style>{STYLE}</style></head><body>'
        f'<header class="masthead"><div class="mast-inner">'
        f'<div class="brand"><img class="logo" src="{base}{LOGO}" alt="ETS" '
        f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'none\'">'
        f'<span class="divider"></span>'
        f'<div class="name"><small>{esc(SITE_EN)}</small>{esc(SITE)}</div></div>'
        f'<div class="mast-meta">{meta_html}</div>'
        f'</div></header>'
        f'<nav class="nav"><div class="nav-inner">{nav}</div></nav>'
    )

FOOT = "</body></html>"

# ---------------------------------------------------------------- pieces
def render_item(it: dict, base: str, card_title: str = "", show_card: bool = False) -> str:
    h = it.get("h", "")
    url = it.get("url")
    hh = f'<a href="{esc(url)}" target="_blank" rel="noopener">{h}</a>' if url else h
    body = f'<p class="b">{it.get("b","")}</p>' if it.get("b") else ""
    meta = []
    co = it.get("company")
    if co and co != card_title:
        meta.append(f'<span class="chip">{esc(co)}</span>')
    if show_card and card_title:
        meta.append(f'<span class="chip k">{esc(card_title)}</span>')
    if it.get("src"):
        meta.append(esc(it["src"]))
    if it.get("date"):
        meta.append(esc(it["date"]))
    return (f'<article class="item"><h4 class="h">{hh}</h4>{body}'
            f'<div class="meta">{" · ".join(meta)}</div></article>')

def render_card(c: dict, base: str) -> str:
    items = c.get("items", [])
    sub = f'<span class="sub">{esc(c["subtitle"])}</span>' if c.get("subtitle") else ""
    full = " full" if c.get("full") else ""
    body = "".join(render_item(it, base, c.get("title", "")) for it in items)
    return (f'<section class="card accent-{esc(c.get("accent","slate"))}{full}">'
            f'<div class="card-head"><div class="icon">{esc(c.get("icon","•"))}</div>'
            f'<h3>{esc(c.get("title"))}{sub}</h3><span class="cnt">{len(items)}건</span></div>'
            f'<div class="card-body">{body}</div></section>')

def datenav(dates: list[str], cur: str, base: str, weekday: str, edition: str) -> str:
    # dates: 최신순
    i = dates.index(cur) if cur in dates else -1
    older = dates[i + 1] if 0 <= i < len(dates) - 1 else None
    newer = dates[i - 1] if i > 0 else None
    left = (f'<a href="{base}briefings/{older}.html">◀ 이전 {older}</a>' if older else '<span class="dis">◀ 이전</span>')
    right = (f'<a href="{base}briefings/{newer}.html">다음 {newer} ▶</a>' if newer else '<span class="dis">다음 ▶</span>')
    return (f'<div class="datenav">{left}<span class="cur">{esc(cur)} ({esc(weekday)}) · {esc(edition)}</span>{right}</div>')

# ---------------------------------------------------------------- pages
def brief_page(d: dict, dates: list[str], base: str, active: str) -> str:
    date = d.get("date", ""); wd = d.get("weekday", ""); ed = d.get("edition", "조간")
    meta = f'<b>{esc(date)} ({esc(wd)})</b>{esc(ed)} · 매일 08:00 발행'
    cards = "".join(render_card(c, base) for c in d.get("cards", []))
    lead = f'<div class="lead"><b>오늘의 요약</b> · {d["summary"]}</div>' if d.get("summary") else ""
    return (head(f"{SITE} — {date}", active, base, meta) +
            f'<div class="wrap">{datenav(dates, date, base, wd, ed)}{lead}'
            f'<div class="grid">{cards}</div>'
            f'<div class="footer">{d.get("sources","")}<br>{d.get("note","")}<br>{esc(SITE)} · 매일 아침 8시 자동 발행</div>'
            f'</div>' + FOOT)

def archive_page(items: list[dict]) -> str:
    rows = []
    for d in items:
        summ = d.get("summary") or ((d.get("cards") or [{}])[0].get("items") or [{}])[0].get("h", "")
        rows.append(f'<a class="arc" href="briefings/{esc(d["date"])}.html">'
                    f'<div class="date">{esc(d["date"])}<small>{esc(d.get("weekday",""))}요일 · {esc(d.get("edition","조간"))}</small></div>'
                    f'<div class="top">{summ}</div></a>')
    return (head(f"{SITE} — 지난 자료", "archive", "") +
            f'<div class="wrap"><div class="page-title">지난 자료</div><p class="page-sub">총 {len(items)}건 · 날짜를 누르면 그날 브리핑으로 이동</p>'
            f'<div class="arc-list">{"".join(rows)}</div></div>' + FOOT)

def collect(items: list[dict]):
    """모든 아이템을 (date, weekday, card_title, item) 로 펼침(최신순)."""
    out = []
    for d in items:
        for c in d.get("cards", []):
            for it in c.get("items", []):
                out.append((d.get("date", ""), d.get("weekday", ""), c.get("title", ""), it))
    return out

def company_of(card_title: str, it: dict) -> str:
    return it.get("company") or card_title

def companies_pages(items: list[dict]):
    flat = collect(items)
    by: dict[str, list] = {}
    for date, wd, ct, it in flat:
        by.setdefault(company_of(ct, it), []).append((date, wd, ct, it))
    # 목록
    tiles = []
    for name, rows in sorted(by.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        latest = max(r[0] for r in rows)
        tiles.append(f'<a class="co" href="{slug(name)}.html"><div class="n">{esc(name)}</div>'
                     f'<div class="m"><b>{len(rows)}건</b> · 최근 {esc(latest)}</div></a>')
    index_html = (head(f"{SITE} — 회사별", "companies", "../") +
                  f'<div class="wrap"><div class="page-title">회사별 모아보기</div>'
                  f'<p class="page-sub">회사를 누르면 날짜별 누적 기록을 볼 수 있습니다 · {len(by)}개 회사</p>'
                  f'<div class="co-grid">{"".join(tiles)}</div></div>' + FOOT)
    pages = {"index.html": index_html}
    for name, rows in by.items():
        groups: dict[str, list] = {}
        for date, wd, ct, it in rows:
            groups.setdefault(date, []).append((wd, ct, it))
        blocks = []
        for date in sorted(groups, reverse=True):
            wd = groups[date][0][0]
            inner = "".join(render_item(it, "../", ct, show_card=True) for _, ct, it in groups[date])
            blocks.append(f'<div class="dgroup"><h3><b>{esc(date)}</b>{esc(wd)}요일 · {len(groups[date])}건</h3>'
                          f'<div class="list">{inner}</div></div>')
        pages[f"{slug(name)}.html"] = (
            head(f"{SITE} — {name}", "companies", "../") +
            f'<div class="wrap"><div class="page-title">{esc(name)}</div>'
            f'<p class="page-sub">누적 {len(rows)}건 · 최신순</p>{"".join(blocks)}</div>' + FOOT)
    return pages

def search_page(items: list[dict]) -> tuple[str, list[dict]]:
    flat = collect(items)
    idx = []
    for date, wd, ct, it in flat:
        idx.append({"d": date, "c": ct, "co": company_of(ct, it), "h": strip_tags(it.get("h", "")),
                    "b": strip_tags(it.get("b", "")), "u": it.get("url", ""), "s": it.get("src", "")})
    cos = sorted({r["co"] for r in idx})
    opts = "".join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in cos)
    js = """
(function(){
  var idx=JSON.parse(document.getElementById('idx').textContent);
  var q=document.getElementById('q'),co=document.getElementById('co'),res=document.getElementById('res'),cnt=document.getElementById('cnt');
  function esc(s){return String(s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]});}
  function run(){
    var t=q.value.trim().toLowerCase(),c=co.value;
    var out=idx.filter(function(r){
      if(c&&r.co!==c)return false;
      if(!t)return true;
      return (r.h+' '+r.b+' '+r.co+' '+r.c).toLowerCase().indexOf(t)>=0;
    });
    cnt.textContent=out.length+'건';
    res.innerHTML=out.map(function(r){
      var h=r.u?'<a href="'+esc(r.u)+'" target="_blank" rel="noopener">'+esc(r.h)+'</a>':esc(r.h);
      return '<article class="item"><h4 class="h">'+h+'</h4><p class="b">'+esc(r.b)+'</p>'+
        '<div class="meta"><span class="chip">'+esc(r.co)+'</span><span class="chip k">'+esc(r.c)+'</span>'+esc(r.s)+' · '+esc(r.d)+'</div></article>';
    }).join('')||'<p class="page-sub">결과가 없습니다.</p>';
  }
  q.addEventListener('input',run);co.addEventListener('change',run);run();
})();"""
    page = (head(f"{SITE} — 검색", "search", "") +
            f'<div class="wrap"><div class="page-title">검색</div><p class="page-sub">키워드나 회사로 누적 기사를 찾습니다 (총 {len(idx)}건)</p>'
            f'<div class="sbar"><input id="q" type="search" placeholder="예: 전해액, ESS, 46시리즈, 수주">'
            f'<select id="co"><option value="">모든 회사</option>{opts}</select></div>'
            f'<div class="scount" id="cnt"></div><div class="sres list" id="res"></div>'
            f'<script id="idx" type="application/json">{json.dumps(idx, ensure_ascii=False)}</script>'
            f'<script>{js}</script></div>' + FOOT)
    return page, idx

def weekly_page(items: list[dict]) -> str:
    if not items:
        return ""
    latest = parse_date(items[0].get("date", "")) or _date.today()
    start = latest - timedelta(days=6)
    flat = [(d, wd, ct, it) for d, wd, ct, it in collect(items)
            if (parse_date(d) or latest) >= start]
    by: dict[str, list] = {}
    for d, wd, ct, it in flat:
        by.setdefault(company_of(ct, it), []).append((d, ct, it))
    blocks = []
    for name, rows in sorted(by.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        inner = "".join(
            f'<article class="item"><h4 class="h">'
            + (f'<a href="{esc(it.get("url"))}" target="_blank" rel="noopener">{it.get("h","")}</a>' if it.get("url") else it.get("h",""))
            + f'</h4><div class="meta"><span class="chip k">{esc(ct)}</span>{esc(it.get("src",""))} · {esc(d)}</div></article>'
            for d, ct, it in sorted(rows, key=lambda r: r[0], reverse=True))
        blocks.append(f'<div class="dgroup"><h3><b>{esc(name)}</b>{len(rows)}건</h3><div class="list">{inner}</div></div>')
    return (head(f"{SITE} — 주간 요약", "weekly", "") +
            f'<div class="wrap"><div class="page-title">주간 요약</div>'
            f'<p class="page-sub">{start.isoformat()} ~ {latest.isoformat()} · 회사별 사실 기록 롤업 · {len(flat)}건</p>'
            f'{"".join(blocks) or "<p class=page-sub>해당 기간 자료가 없습니다.</p>"}</div>' + FOOT)

# ---------------------------------------------------------------- main
def load_all() -> list[dict]:
    out = []
    for f in sorted(DATA.glob("*.json"), reverse=True):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"  ! {f.name}: {e}", file=sys.stderr)
    out.sort(key=lambda x: x.get("date", ""), reverse=True)
    return out

def main() -> int:
    items = load_all()
    if not items:
        print("data/*.json 없음", file=sys.stderr); return 1
    dates = [d["date"] for d in items]
    BRIEF.mkdir(exist_ok=True); COMP.mkdir(exist_ok=True)
    for d in items:
        (BRIEF / f'{d["date"]}.html').write_text(brief_page(d, dates, "../", "archive"), encoding="utf-8")
    (ROOT / "index.html").write_text(brief_page(items[0], dates, "", "today"), encoding="utf-8")
    (ROOT / "archive.html").write_text(archive_page(items), encoding="utf-8")
    for name, html_ in companies_pages(items).items():
        (COMP / name).write_text(html_, encoding="utf-8")
    spage, idx = search_page(items)
    (ROOT / "search.html").write_text(spage, encoding="utf-8")
    (ROOT / "search-index.json").write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
    (ROOT / "weekly.html").write_text(weekly_page(items), encoding="utf-8")
    n_items = sum(len(c.get("items", [])) for d in items for c in d.get("cards", []))
    print(f"생성 완료: {len(items)}일치 · 아이템 {n_items}건 · 홈={items[0]['date']} · 회사별 {len(list(COMP.glob('*.html')))-1}개")
    return 0

if __name__ == "__main__":
    sys.exit(main())
