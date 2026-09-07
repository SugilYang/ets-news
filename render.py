#!/usr/bin/env python3
"""
이티에스 영업 인텔리전스 — 지면 생성기.

data/*.json (하루치 브리핑 내용)을 읽어 카드형 대시보드 HTML을 생성합니다.
- index.html            : 가장 최근 날짜의 브리핑(홈)
- briefings/<날짜>.html : 날짜별 브리핑
- archive.html          : 지난 자료 목록

디자인은 이 파일에 고정돼 있고, 내용만 data/*.json 으로 매일 바뀝니다.
표준 라이브러리만 사용(외부 패키지 불필요).
"""
from __future__ import annotations
import html, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
BRIEF_DIR = ROOT / "briefings"

SITE = "이티에스 영업 인텔리전스"
SITE_EN = "ETS SALES INTELLIGENCE"

def esc(v) -> str:
    return html.escape(str(v if v is not None else ""), quote=True)

# --- 공통 스타일/헤더/푸터 ---------------------------------------------------
STYLE = """
:root{
  --ink:#15202b;--bg:#eef1f5;--card:#fff;--muted:#657084;--line:#e2e6ec;
  --blue:#1f4e79;--blue-bg:#eaf1f9;--teal:#0f766e;--teal-bg:#e6f4f2;
  --red:#c0322b;--red-bg:#fbecea;--purple:#6d28d9;--purple-bg:#f1ebfb;
  --gold:#9a6b00;--gold-bg:#fbf3df;--gray:#516073;--gray-bg:#eef1f5;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:'Malgun Gothic','Apple SD Gothic Neo',system-ui,sans-serif;line-height:1.5}
a{color:inherit}
.wrap{max-width:1200px;margin:0 auto;padding:0 16px 44px}
.masthead{background:var(--ink);color:#fff;padding:16px 24px}
.mast-inner{max-width:1200px;margin:0 auto;display:flex;justify-content:space-between;
  align-items:flex-end;flex-wrap:wrap;gap:8px}
.mast-title{font-size:28px;font-weight:800}
.mast-title small{display:block;font-size:11px;font-weight:600;color:#9fb2c9;letter-spacing:.25em;margin-bottom:4px}
.mast-meta{text-align:right;font-size:13px;color:#c7d2e0}
.mast-meta .badge{display:inline-block;background:#2a7de1;color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:4px;letter-spacing:.04em}
.nav{background:#1e2c3a;border-top:1px solid #2c3e50}
.nav-inner{max-width:1200px;margin:0 auto;display:flex;gap:4px;padding:0 20px}
.nav a{color:#c7d2e0;font-size:13.5px;font-weight:600;padding:10px 14px;text-decoration:none;border-bottom:3px solid transparent}
.nav a:hover{color:#fff}
.nav a.on{color:#fff;border-bottom-color:#2a7de1}
.priority{background:#fff;border:1px solid var(--line);border-top:4px solid var(--red);
  border-radius:0 0 10px 10px;padding:16px 18px;box-shadow:0 1px 3px rgba(20,32,43,.06)}
.priority h2{margin:0 0 12px;font-size:16px;display:flex;align-items:center;gap:8px}
.priority h2 .tag{background:var(--red);color:#fff;font-size:12px;padding:2px 8px;border-radius:4px}
.prio-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
@media(max-width:800px){.prio-grid{grid-template-columns:1fr}}
.prio{display:flex;gap:10px;background:#fbfcfe;border:1px solid var(--line);border-radius:8px;padding:12px}
.prio .num{flex:none;width:26px;height:26px;border-radius:50%;background:var(--ink);color:#fff;
  font-weight:800;font-size:14px;display:flex;align-items:center;justify-content:center}
.prio .body{font-size:13.5px}
.prio .body b{display:block;margin-bottom:2px}
.stars{color:#e0a400;font-size:12px;letter-spacing:1px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:20px}
@media(max-width:800px){.grid{grid-template-columns:1fr}}
.full{grid-column:1 / -1}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;box-shadow:0 1px 3px rgba(20,32,43,.05)}
.card-head{display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid var(--line)}
.card-head .icon{width:34px;height:34px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:18px;flex:none}
.card-head h3{margin:0;font-size:16px;font-weight:700}
.card-head .sub{font-size:12px;color:var(--muted);font-weight:500}
.pill{font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;margin-left:auto;white-space:nowrap}
.pill.cust{background:var(--blue-bg);color:var(--blue)}
.pill.pros{background:var(--teal-bg);color:var(--teal)}
.pill.comp{background:var(--red-bg);color:var(--red)}
.card-body{padding:10px 16px 14px}
.row{display:flex;gap:8px;padding:7px 0;border-bottom:1px dashed var(--line);font-size:13.5px}
.row:last-child{border-bottom:0}
.row .k{flex:none;width:80px;font-weight:700;color:var(--muted);font-size:12px;padding-top:1px}
.row.act{background:var(--gold-bg);margin:8px -16px -4px;padding:10px 16px;border:0}
.row.act .k{color:var(--gold)}
.row.act .v{font-weight:600}
.accent-blue .icon{background:var(--blue-bg)}.accent-blue .card-head{border-bottom-color:var(--blue)}
.accent-teal .icon{background:var(--teal-bg)}
.accent-red .icon{background:var(--red-bg)}.accent-red .card-head{border-bottom-color:var(--red)}
.accent-purple .icon{background:var(--purple-bg)}
.accent-gray .icon{background:var(--gray-bg)}
.mini{display:grid;grid-template-columns:1fr 1fr;gap:8px 16px}
@media(max-width:600px){.mini{grid-template-columns:1fr}}
.mini .m{font-size:13px;padding:8px 0;border-bottom:1px dashed var(--line)}
.flag{font-size:11px;font-weight:700;padding:1px 6px;border-radius:4px;margin-left:4px}
.flag.up{background:var(--teal-bg);color:var(--teal)}
.flag.down{background:#eee;color:#888}
.flag.watch{background:var(--gold-bg);color:var(--gold)}
.footer{margin-top:22px;font-size:11.5px;color:var(--muted);border-top:1px solid var(--line);padding-top:12px;line-height:1.7}
/* 아카이브 */
.arc-list{margin-top:20px;display:grid;gap:10px}
.arc{display:flex;gap:14px;align-items:center;background:#fff;border:1px solid var(--line);
  border-radius:10px;padding:14px 16px;text-decoration:none;box-shadow:0 1px 3px rgba(20,32,43,.05)}
.arc:hover{border-color:#2a7de1}
.arc .date{flex:none;font-weight:800;font-size:15px;width:120px}
.arc .date small{display:block;color:var(--muted);font-weight:500;font-size:11px}
.arc .top{font-size:13px;color:var(--muted)}
.arc .top b{color:var(--ink)}
.page-title{font-size:20px;font-weight:800;margin:22px 0 4px}
"""

def page_head(title, active):
    nav = (
        '<div class="nav"><div class="nav-inner">'
        f'<a href="index.html" class="{"on" if active=="today" else ""}">오늘 브리핑</a>'
        f'<a href="archive.html" class="{"on" if active=="archive" else ""}">지난 자료</a>'
        '</div></div>'
    )
    return (
        f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{esc(title)}</title><style>{STYLE}</style></head><body>'
        f'<header class="masthead"><div class="mast-inner">'
        f'<div class="mast-title"><small>{esc(SITE_EN)}</small>{esc(SITE)}</div>'
        f'<div class="mast-meta"><span class="badge">공개</span></div>'
        f'</div></header>{nav}'
    )

FOOT = "</body></html>"

# --- 카드 렌더링 -------------------------------------------------------------
def render_rows(rows):
    out = []
    for r in rows or []:
        cls = "row act" if r.get("act") else "row"
        out.append(f'<div class="{cls}"><div class="k">{esc(r.get("k"))}</div>'
                   f'<div class="v">{r.get("v","")}</div></div>')
    return "".join(out)

def render_mini(mini):
    out = []
    for m in mini or []:
        flag = ""
        if m.get("flag"):
            flag = f'<span class="flag {esc(m.get("flag_cls","watch"))}">{esc(m["flag"])}</span>'
        out.append(f'<div class="m"><b>{esc(m.get("name"))}</b>{flag}<br>{m.get("text","")}</div>')
    return f'<div class="mini">{"".join(out)}</div>'

def render_card(c):
    accent = c.get("accent", "gray")
    full = " full" if c.get("full") else ""
    pill = ""
    if c.get("pill"):
        pill = f'<span class="pill {esc(c.get("pill_cls",""))}">{esc(c["pill"])}</span>'
    sub = f' <span class="sub">{esc(c["subtitle"])}</span>' if c.get("subtitle") else ""
    body = ""
    if c.get("mini"):
        body += render_mini(c["mini"])
    body += render_rows(c.get("rows"))
    return (
        f'<div class="card accent-{esc(accent)}{full}">'
        f'<div class="card-head"><div class="icon">{esc(c.get("icon","•"))}</div>'
        f'<div><h3>{esc(c.get("title"))}{sub}</h3></div>{pill}</div>'
        f'<div class="card-body">{body}</div></div>'
    )

def render_priorities(pr):
    cells = []
    for p in pr or []:
        stars = '<span class="stars">' + "★" * int(p.get("stars", 0)) + "</span>"
        cells.append(
            f'<div class="prio"><div class="num">{esc(p.get("rank"))}</div>'
            f'<div class="body"><b>{esc(p.get("title"))} {stars}</b>{p.get("text","")}</div></div>'
        )
    return (
        '<section class="priority"><h2><span class="tag">오늘의 초점</span> 영업 우선순위 TOP '
        f'{len(pr or [])}</h2><div class="prio-grid">{"".join(cells)}</div></section>'
    )

def render_brief_page(d, active="today"):
    date = d.get("date", "")
    meta = f'{esc(date)} ({esc(d.get("weekday",""))}) · {esc(d.get("edition","조간"))}'
    cards = "".join(render_card(c) for c in d.get("cards", []))
    head = page_head(f'{SITE} — {date}', active)
    # 상단 날짜 라인은 masthead 메타에 날짜 넣기 위해 재구성
    head = head.replace('<span class="badge">공개</span>',
                        f'<span class="badge">공개</span><br>{meta}')
    return (
        head +
        f'<div class="wrap">{render_priorities(d.get("priorities"))}'
        f'<div class="grid">{cards}</div>'
        f'<div class="footer">{d.get("sources","")}<br>{d.get("note","")}<br>'
        f'{esc(SITE)} · 매일 아침 8시 자동 발행</div></div>' + FOOT
    )

def load_all():
    items = []
    for f in sorted(DATA.glob("*.json"), reverse=True):
        try:
            items.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"  ! {f.name} 로드 실패: {e}", file=sys.stderr)
    items.sort(key=lambda x: x.get("date", ""), reverse=True)
    return items

def render_archive(items):
    rows = []
    for d in items:
        top = d.get("priorities", [{}])[0].get("title", "") if d.get("priorities") else ""
        rows.append(
            f'<a class="arc" href="briefings/{esc(d.get("date"))}.html">'
            f'<div class="date">{esc(d.get("date"))}<small>{esc(d.get("weekday",""))}요일 · {esc(d.get("edition","조간"))}</small></div>'
            f'<div class="top">오늘의 1순위 · <b>{esc(top)}</b></div></a>'
        )
    head = page_head(f'{SITE} — 지난 자료', "archive")
    return (head + f'<div class="wrap"><div class="page-title">지난 자료 ({len(items)}건)</div>'
            f'<div class="arc-list">{"".join(rows)}</div></div>' + FOOT)

def main():
    items = load_all()
    if not items:
        print("data/*.json 이 없습니다.", file=sys.stderr); return 1
    BRIEF_DIR.mkdir(exist_ok=True)
    for d in items:
        (BRIEF_DIR / f'{d["date"]}.html').write_text(render_brief_page(d, "archive"), encoding="utf-8")
    # 홈 = 최신
    (ROOT / "index.html").write_text(render_brief_page(items[0], "today"), encoding="utf-8")
    (ROOT / "archive.html").write_text(render_archive(items), encoding="utf-8")
    print(f"생성 완료: 총 {len(items)}일치, 홈=최신({items[0]['date']})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
