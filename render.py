#!/usr/bin/env python3
"""
이티에스 이차전지 산업 브리핑 — 지면 생성기.

data/*.json (하루치 내용)을 읽어 카드형 지면 HTML을 생성합니다.
- index.html            : 최근 날짜(홈)
- briefings/<날짜>.html : 날짜별
- archive.html          : 지난 자료 목록

주관적 판단 없이 '사실(팩트)' 중심. 각 섹션은 여러 개의 뉴스 아이템으로 구성.
표준 라이브러리만 사용.
"""
from __future__ import annotations
import html, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
BRIEF_DIR = ROOT / "briefings"

SITE = "이티에스 이차전지 산업 브리핑"
SITE_EN = "ETS BATTERY INDUSTRY BRIEFING"

def esc(v) -> str:
    return html.escape(str(v if v is not None else ""), quote=True)

STYLE = """
:root{--ink:#15202b;--bg:#eef1f5;--card:#fff;--muted:#6b7688;--line:#e4e8ee;
  --blue:#1f4e79;--blue-bg:#eaf1f9;--teal:#0f766e;--teal-bg:#e6f4f2;
  --red:#b83b2e;--red-bg:#fbecea;--purple:#6d28d9;--purple-bg:#f1ebfb;
  --gray:#516073;--gray-bg:#eef1f5;--amber:#9a6b00;--amber-bg:#fbf3df}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:'Malgun Gothic','Apple SD Gothic Neo',system-ui,sans-serif;line-height:1.55}
a{color:inherit}
.wrap{max-width:1200px;margin:0 auto;padding:0 16px 44px}
.masthead{background:var(--ink);color:#fff;padding:16px 24px}
.mast-inner{max-width:1200px;margin:0 auto;display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:8px}
.mast-title{font-size:27px;font-weight:800}
.mast-title small{display:block;font-size:11px;font-weight:600;color:#9fb2c9;letter-spacing:.22em;margin-bottom:4px}
.mast-meta{text-align:right;font-size:13px;color:#c7d2e0}
.nav{background:#1e2c3a;border-top:1px solid #2c3e50}
.nav-inner{max-width:1200px;margin:0 auto;display:flex;gap:4px;padding:0 20px}
.nav a{color:#c7d2e0;font-size:13.5px;font-weight:600;padding:10px 14px;text-decoration:none;border-bottom:3px solid transparent}
.nav a:hover{color:#fff}.nav a.on{color:#fff;border-bottom-color:#2a7de1}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:20px}
@media(max-width:820px){.grid{grid-template-columns:1fr}}
.full{grid-column:1 / -1}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;box-shadow:0 1px 3px rgba(20,32,43,.05)}
.card-head{display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:2px solid var(--line)}
.card-head .icon{width:34px;height:34px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:18px;flex:none}
.card-head h3{margin:0;font-size:16.5px;font-weight:800}
.card-head .sub{font-size:12px;color:var(--muted);font-weight:500}
.card-head .cnt{margin-left:auto;font-size:11px;color:var(--muted);background:var(--gray-bg);padding:2px 9px;border-radius:20px}
.card-body{padding:4px 16px 10px}
.item{padding:11px 0;border-bottom:1px solid var(--line)}
.item:last-child{border-bottom:0}
.item .h{font-weight:700;font-size:14.5px;line-height:1.4}
.item .b{font-size:13px;color:#374151;margin-top:4px;line-height:1.65}
.item .b b{color:var(--ink)}
.item .src{display:inline-block;font-size:11px;color:var(--muted);margin-top:5px}
.accent-blue .icon{background:var(--blue-bg)}.accent-blue .card-head{border-bottom-color:var(--blue)}
.accent-teal .icon{background:var(--teal-bg)}.accent-teal .card-head{border-bottom-color:var(--teal)}
.accent-red .icon{background:var(--red-bg)}.accent-red .card-head{border-bottom-color:var(--red)}
.accent-purple .icon{background:var(--purple-bg)}.accent-purple .card-head{border-bottom-color:var(--purple)}
.accent-amber .icon{background:var(--amber-bg)}.accent-amber .card-head{border-bottom-color:var(--amber)}
.accent-gray .icon{background:var(--gray-bg)}
.footer{margin-top:22px;font-size:11.5px;color:var(--muted);border-top:1px solid var(--line);padding-top:12px;line-height:1.7}
.arc-list{margin-top:20px;display:grid;gap:10px}
.arc{display:flex;gap:14px;align-items:center;background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px 16px;text-decoration:none;box-shadow:0 1px 3px rgba(20,32,43,.05)}
.arc:hover{border-color:#2a7de1}
.arc .date{flex:none;font-weight:800;font-size:15px;width:120px}
.arc .date small{display:block;color:var(--muted);font-weight:500;font-size:11px}
.arc .top{font-size:13px;color:var(--muted)}.arc .top b{color:var(--ink)}
.page-title{font-size:20px;font-weight:800;margin:22px 0 4px}
"""

def page_head(title, active, meta=""):
    nav = ('<div class="nav"><div class="nav-inner">'
           f'<a href="index.html" class="{"on" if active=="today" else ""}">오늘 브리핑</a>'
           f'<a href="archive.html" class="{"on" if active=="archive" else ""}">지난 자료</a>'
           '</div></div>')
    return (f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{esc(title)}</title><style>{STYLE}</style></head><body>'
            f'<header class="masthead"><div class="mast-inner">'
            f'<div class="mast-title"><small>{esc(SITE_EN)}</small>{esc(SITE)}</div>'
            f'<div class="mast-meta">{meta}</div></div></header>{nav}')

FOOT = "</body></html>"

def render_item(it):
    src = f'<span class="src">{esc(it.get("src",""))}</span>' if it.get("src") else ""
    body = f'<div class="b">{it.get("b","")}</div>' if it.get("b") else ""
    return f'<div class="item"><div class="h">{it.get("h","")}</div>{body}{src}</div>'

def render_card(c):
    items = c.get("items", [])
    sub = f' <span class="sub">{esc(c["subtitle"])}</span>' if c.get("subtitle") else ""
    full = " full" if c.get("full") else ""
    body = "".join(render_item(it) for it in items)
    return (f'<div class="card accent-{esc(c.get("accent","gray"))}{full}">'
            f'<div class="card-head"><div class="icon">{esc(c.get("icon","•"))}</div>'
            f'<div><h3>{esc(c.get("title"))}{sub}</h3></div>'
            f'<span class="cnt">{len(items)}건</span></div>'
            f'<div class="card-body">{body}</div></div>')

def render_brief_page(d, active="today"):
    date = d.get("date", "")
    meta = f'{esc(date)} ({esc(d.get("weekday",""))}) · {esc(d.get("edition","조간"))}'
    cards = "".join(render_card(c) for c in d.get("cards", []))
    return (page_head(f'{SITE} — {date}', active, meta) +
            f'<div class="wrap"><div class="grid">{cards}</div>'
            f'<div class="footer">{d.get("sources","")}<br>{d.get("note","")}<br>'
            f'{esc(SITE)} · 매일 아침 8시 자동 발행</div></div>' + FOOT)

def load_all():
    items = []
    for f in sorted(DATA.glob("*.json"), reverse=True):
        try: items.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e: print(f"  ! {f.name}: {e}", file=sys.stderr)
    items.sort(key=lambda x: x.get("date",""), reverse=True)
    return items

def render_archive(items):
    rows = []
    for d in items:
        summ = d.get("summary")
        if not summ and d.get("cards"):
            c0 = d["cards"][0]
            summ = (c0.get("items") or [{}])[0].get("h","")
        rows.append(f'<a class="arc" href="briefings/{esc(d.get("date"))}.html">'
                    f'<div class="date">{esc(d.get("date"))}<small>{esc(d.get("weekday",""))}요일 · {esc(d.get("edition","조간"))}</small></div>'
                    f'<div class="top">{summ}</div></a>')
    return (page_head(f'{SITE} — 지난 자료', "archive") +
            f'<div class="wrap"><div class="page-title">지난 자료 ({len(items)}건)</div>'
            f'<div class="arc-list">{"".join(rows)}</div></div>' + FOOT)

def main():
    items = load_all()
    if not items:
        print("data/*.json 없음", file=sys.stderr); return 1
    BRIEF_DIR.mkdir(exist_ok=True)
    for d in items:
        (BRIEF_DIR / f'{d["date"]}.html').write_text(render_brief_page(d, "archive"), encoding="utf-8")
    (ROOT / "index.html").write_text(render_brief_page(items[0], "today"), encoding="utf-8")
    (ROOT / "archive.html").write_text(render_archive(items), encoding="utf-8")
    print(f"생성 완료: {len(items)}일치, 홈=최신({items[0]['date']})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
