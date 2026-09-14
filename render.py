#!/usr/bin/env python3
"""
이티에스 영업 브리핑 — 지면 생성기 v4 (신문 형식)

data/<날짜>.json(스키마 v4) → index.html(최신 호) · briefings/<날짜>.html · archive.html(달력) ·
companies/*.html(회사별 누적) · search.html + search-index.json · weekly.html + weekly/<주>.html(주간 종합 3면)
표준 라이브러리 + PyYAML(watchlist 읽기)만 사용.
"""
from __future__ import annotations

import calendar
import html
import json
import re
import sys
from datetime import date as _date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
import brieflib as B  # noqa: E402

ROOT = B.ROOT
DATA = ROOT / "data"
BRIEF = ROOT / "briefings"
COMP = ROOT / "companies"
WEEK = ROOT / "weekly"

WL = B.load_watchlist()
SITE = (WL.get("site") or {}).get("name", "이티에스 영업 브리핑")
SITE_EN = (WL.get("site") or {}).get("name_en", "ETS SALES BRIEFING")
NAV = [("index.html", "오늘 브리핑", "today"), ("archive.html", "지난 호", "archive"),
       ("companies/index.html", "회사별", "companies"), ("search.html", "검색", "search"),
       ("weekly.html", "주간 종합", "weekly")]
CAT_TITLE = {c["id"]: c.get("title", c["id"]) for c in WL.get("categories") or []}
CUSTOMER_NAMES = [c["name"] for c in WL.get("customers") or []]
COMPETITORS = WL.get("competitors") or []
COMPETITOR_NAMES = [c["name"] for c in COMPETITORS]

esc = lambda s: html.escape(str(s or ""), quote=True)  # noqa: E731


def slug(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "-", s).strip("-").lower() or "x"


def parse_date(s: str) -> _date | None:
    try:
        return _date.fromisoformat(s)
    except Exception:
        return None


def short_date(s: str) -> str:
    d = parse_date(s)
    return f"{d.month}/{d.day}" if d else s


FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@600;700;900'
         '&family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">')

STYLE = r"""
:root{
  --ink:#111417;--text:#2a2f36;--muted:#6b7280;--faint:#9aa3ad;--rule:#1b1f24;--hair:#d9d5cc;--hair2:#e8e4da;
  --paper:#efece4;--sheet:#fbfaf6;--accent:#b3261e;--accent-bg:#fbeeed;--brand:#0e9b86;--brand-bg:#e4f3ef;
  --serif:'Noto Serif KR','Apple SD Gothic Neo','Malgun Gothic',serif;
  --sans:'Noto Sans KR','Apple SD Gothic Neo','Malgun Gothic',system-ui,sans-serif;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--text);font-family:var(--sans);line-height:1.6;
  font-variant-numeric:tabular-nums;word-break:keep-all;overflow-wrap:anywhere;-webkit-font-smoothing:antialiased}
a{color:inherit}
b,strong{font-weight:700}
.sheet{max-width:1180px;margin:14px auto 40px;background:var(--sheet);border:1px solid var(--hair);box-shadow:0 1px 3px rgba(0,0,0,.06);padding:0 28px 34px}

/* ── 제호 ── */
.mast{border-top:4px solid var(--rule);border-bottom:1px solid var(--rule);padding:16px 0 12px;display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:16px}
.mast .left{display:flex;align-items:center;gap:14px}
.mast .logo{height:44px;width:auto;display:block}
.mast .center{text-align:center}
.mast .en{font-family:var(--sans);font-size:11px;letter-spacing:.32em;color:var(--muted);font-weight:500;margin-bottom:2px}
.mast .name{font-family:var(--serif);font-weight:900;font-size:40px;line-height:1.1;color:var(--ink);letter-spacing:.02em;text-decoration:none;display:block}
.mast .right{text-align:right;font-size:12.5px;color:var(--muted);line-height:1.5}
.mast .right b{display:block;color:var(--ink);font-size:14px;font-family:var(--serif)}
.dateline{border-bottom:3px double var(--rule);display:flex;justify-content:space-between;align-items:center;gap:10px;padding:7px 0;font-size:13px;color:var(--ink)}
.dateline .issue{font-family:var(--serif);font-weight:700}
.dateline .pub{color:var(--muted)}
.nav{display:flex;justify-content:center;gap:0;border-bottom:1px solid var(--rule);margin-bottom:6px;overflow-x:auto}
.nav a{padding:9px 18px;font-size:13.5px;font-weight:700;text-decoration:none;color:var(--ink);border-left:1px solid var(--hair);white-space:nowrap;letter-spacing:.02em}
.nav a:first-child{border-left:0}
.nav a.on{color:var(--brand);box-shadow:inset 0 -3px 0 var(--brand)}
.nav a:hover{background:#f1efe8}

/* ── 호 이동 ── */
.issuenav{display:flex;justify-content:space-between;align-items:center;font-size:12.5px;color:var(--muted);padding:8px 0 0}
.issuenav a{color:var(--ink);text-decoration:none;font-weight:700}
.issuenav a:hover{color:var(--brand)}
.issuenav .dis{color:var(--faint)}

/* ── 1면 톱 ── */
.front{display:grid;grid-template-columns:7fr 4fr;gap:0 24px;padding:12px 0 10px;border-bottom:1px solid var(--rule);margin-bottom:0}
.front .lcol{border-right:1px solid var(--hair);padding-right:24px;min-width:0} .front .rcol{min-width:0}
.front .guide{border-right:0;padding-right:0;margin-top:10px} .front .legend{margin-top:10px}
.kicker{font-size:11.5px;letter-spacing:.18em;color:var(--accent);font-weight:700;margin-bottom:6px}
.lead-story h1{font-family:var(--serif);font-weight:900;font-size:27px;line-height:1.3;margin:0 0 6px;color:var(--ink)}
.lead-story h1 a{text-decoration:none}
.lead-story h1 a:hover{color:var(--accent)}
.lead-story .b{font-size:14.5px;line-height:1.7;margin:0 0 4px;color:var(--text)}
.front .side h2{font-family:var(--sans);font-size:11.5px;letter-spacing:.18em;color:var(--muted);font-weight:700;margin:0 0 6px;padding-bottom:5px;border-bottom:1px solid var(--rule)}
.front .side .item{padding:6px 0}
.front .side .item .h{font-size:15px}
.front .side .item .b{display:none}
.summary{font-size:13px;color:var(--muted);padding:6px 0 0;border-top:1px dotted var(--hair);margin-top:6px}
.front{border-bottom:3px double var(--rule)}
.guide-row{display:grid;grid-template-columns:3fr 2fr;gap:0 24px;border-bottom:3px double var(--rule);padding:8px 0 8px}
.guide{border-right:1px solid var(--hair);padding-right:20px}
.guide h2,.legend h2{font-family:var(--sans);font-size:11.5px;letter-spacing:.18em;color:var(--accent);font-weight:700;margin:0 0 5px;padding-bottom:4px;border-bottom:1px solid var(--rule)}
.legend h2{color:var(--muted)} .guide h2 small{letter-spacing:0;font-weight:500;color:var(--muted);margin-left:8px;font-size:11px}
.guide ul{list-style:none;margin:0;padding:0} .guide li{padding:4px 0;border-bottom:1px dotted var(--hair);font-size:13.5px;line-height:1.5;color:var(--ink)}
.guide li:last-child{border-bottom:0} .guide li a{text-decoration:none;font-weight:700} .guide li a:hover{color:var(--accent)}
.guide li small{display:block;font-weight:400;color:var(--muted);font-size:11.5px}
.legend dl{margin:0;font-size:11.5px;line-height:1.55;color:var(--text);display:grid;grid-template-columns:auto 1fr;gap:2px 8px}
.legend dt{font-weight:700;color:var(--ink);white-space:nowrap} .legend dd{margin:0}
.summary b{color:var(--ink)}

/* ── 섹션 ── */
.section{margin:10px 0 0} .section.thin .sec-head{border-top-width:1px;padding:4px 0;margin-bottom:0}
.sec-head{display:flex;align-items:baseline;gap:10px;border-top:3px solid var(--rule);border-bottom:1px solid var(--rule);padding:5px 0 4px;margin-bottom:4px}
.sec-head .no{font-family:var(--serif);font-weight:900;font-size:18px;color:var(--ink)}
.sec-head h2{font-family:var(--serif);font-weight:900;font-size:19px;margin:0;color:var(--ink);letter-spacing:.01em}
.sec-head .sub{font-size:12.5px;color:var(--muted)}
.sec-head .cnt{margin-left:auto;font-size:12px;color:var(--muted);white-space:nowrap}
.cols{column-count:3;column-gap:24px;column-rule:1px solid var(--hair)}
.cols.two{column-count:2} .cols.one{column-count:1}
.group{break-inside:avoid;margin-bottom:4px}
.group h3{font-family:var(--serif);font-size:13.5px;font-weight:700;color:var(--ink);margin:0;padding:3px 0 2px;border-bottom:2px solid var(--ink);display:flex;align-items:center;gap:8px}
.group h3 .gcnt{font-family:var(--sans);font-size:11px;color:var(--muted);font-weight:500;margin-left:auto}
.item{break-inside:avoid;padding:6px 0;border-bottom:1px dotted var(--hair)}
.item:last-child{border-bottom:0}
.item .h{margin:0;font-family:var(--serif);font-size:15px;font-weight:700;line-height:1.4;color:var(--ink);text-wrap:pretty}
.item .h a{text-decoration:none}
.item .h a:hover{color:var(--accent)}
.item .b{margin:2px 0 0;font-size:13px;line-height:1.55;color:var(--text)}
.item .b b{color:var(--ink)}
.meta{margin-top:3px;font-size:11px;line-height:1.5;color:var(--muted);display:flex;flex-wrap:wrap;gap:2px 7px;align-items:center}
.meta .src{color:var(--ink);font-weight:500}
.meta .more{margin-left:auto;text-decoration:none;color:var(--brand);font-weight:700;white-space:nowrap}
.meta .more:hover{text-decoration:underline}
.stars{color:#c9a227;letter-spacing:-.05em;font-size:11px}
.stars .off{color:#d9d5cc}
.g{display:inline-block;font-size:10.5px;font-weight:700;line-height:1.4;padding:0 6px;border-radius:2px;border:1px solid var(--ink);color:var(--ink);letter-spacing:.04em}
.g.A{background:var(--accent);border-color:var(--accent);color:#fff}
.g.B{background:var(--ink);color:#fff}
.g.C{color:var(--muted);border-color:var(--faint)}
.tag{display:inline-block;font-size:10.5px;line-height:1.5;padding:0 6px;border-radius:2px;background:#eeece5;color:#4b5563}
.tag.key{background:var(--brand-bg);color:#0b6f60;font-weight:700}
.ent{font-weight:700;color:var(--ink)}
.rel{color:var(--faint)}
.fu{margin-top:3px;font-size:12px;color:var(--accent);background:var(--accent-bg);border-left:3px solid var(--accent);padding:4px 8px;line-height:1.55}
.fu b{color:var(--accent)}
.empty{font-size:13px;color:var(--faint);font-style:italic;padding:6px 0 10px}

/* ── 지난 호(달력) ── */
.page-title{font-family:var(--serif);font-size:26px;font-weight:900;color:var(--ink);margin:22px 0 4px}
.page-sub{font-size:13px;color:var(--muted);margin:0 0 12px}
.months{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px;margin-top:8px}
.month{border:1px solid var(--hair);background:#fff;padding:12px 14px 14px}
.month h3{font-family:var(--serif);font-size:17px;margin:0 0 8px;color:var(--ink);display:flex;justify-content:space-between;align-items:baseline}
.month h3 small{font-family:var(--sans);font-size:11.5px;color:var(--muted);font-weight:500}
.cal{display:grid;grid-template-columns:repeat(7,1fr);gap:4px;text-align:center;font-size:12.5px}
.cal .wd{font-size:11px;color:var(--muted);font-weight:700;padding:2px 0 4px}
.cal .wd.sun,.cal .d.sun{color:#b3261e}
.cal .wd.sat,.cal .d.sat{color:#1d4f8a}
.cal .d{padding:6px 0;border:1px solid transparent;color:var(--faint);border-radius:3px;line-height:1.2}
.cal .d.has{border-color:var(--ink);color:var(--ink);font-weight:700;text-decoration:none;background:#fff}
.cal .d.has:hover{background:var(--ink);color:#fff}
.cal .d.has small{display:block;font-size:9.5px;font-weight:500;color:var(--muted)}
.cal .d.has:hover small{color:#ddd}
.cal .d.off{opacity:.35}
.arc-list{margin-top:18px;border-top:1px solid var(--rule)}
.arc{display:flex;gap:14px;align-items:baseline;padding:10px 2px;border-bottom:1px dotted var(--hair);text-decoration:none}
.arc:hover{background:#f4f2ec}
.arc .no{font-family:var(--serif);font-weight:700;width:60px;flex:none;color:var(--ink)}
.arc .date{flex:none;width:170px;color:var(--ink);font-weight:500}
.arc .top{font-size:13px;color:var(--muted)}

/* ── 회사별 ── */
.co-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px;margin:8px 0 18px}
.co{background:#fff;border:1px solid var(--hair);padding:12px 14px;text-decoration:none}
.co:hover{border-color:var(--ink)}
.co .n{font-family:var(--serif);font-weight:700;font-size:16px;color:var(--ink)}
.co .m{font-size:12px;color:var(--muted);margin-top:3px}
.co .m b{color:var(--brand)}
.dgroup{margin-top:16px}
.dgroup h3{font-family:var(--serif);font-size:15px;color:var(--ink);margin:0 0 4px;padding-bottom:4px;border-bottom:2px solid var(--ink)}
.dgroup h3 small{font-family:var(--sans);font-weight:500;color:var(--muted);font-size:12px;margin-left:8px}
.list{padding:0 2px}

/* ── 검색 ── */
.sbar{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:8px;margin-top:8px}
.sbar2{display:grid;grid-template-columns:1fr 1fr auto;gap:8px;margin-top:8px;align-items:center}
.sbar input,.sbar select,.sbar2 input,.sbar2 select{font:inherit;font-size:14px;padding:9px 11px;border:1px solid var(--hair);background:#fff;width:100%}
.sbar input:focus,.sbar select:focus,.sbar2 input:focus{outline:2px solid var(--brand);outline-offset:1px}
.sbar2 label{font-size:12.5px;color:var(--muted);display:flex;align-items:center;gap:6px}
.scount{font-size:12.5px;color:var(--muted);margin:10px 2px 0}
.sres{margin-top:6px;border-top:1px solid var(--rule)}

/* ── 주간 종합 ── */
.wk-page{margin-top:18px;border:1px solid var(--rule);padding:14px 18px 16px;background:#fff}
.wk-head{display:flex;align-items:baseline;gap:12px;border-bottom:3px double var(--rule);padding-bottom:8px;margin-bottom:12px}
.wk-head .p{font-family:var(--serif);font-weight:900;font-size:22px;color:var(--ink)}
.wk-head .t{font-family:var(--serif);font-weight:700;font-size:17px;color:var(--ink)}
.wk-head .r{margin-left:auto;font-size:12.5px;color:var(--muted)}
.wk-cols{display:grid;grid-template-columns:repeat(4,1fr);gap:0 18px}
.wk-cols.three{grid-template-columns:repeat(3,1fr)}
.wk-col{border-left:1px solid var(--hair);padding-left:14px;min-width:0}
.wk-col:first-child{border-left:0;padding-left:0}
.wk-col h4{font-family:var(--serif);font-size:15px;font-weight:700;color:var(--ink);margin:0 0 6px;padding:4px 0;border-bottom:2px solid var(--ink);display:flex;gap:8px;align-items:baseline}
.wk-col h4 small{margin-left:auto;font-family:var(--sans);font-weight:500;font-size:11px;color:var(--muted)}
.wk-col .item{padding:8px 0}
.wk-col .item .h{font-size:14.5px}
.wk-col .item .b{font-size:12.5px;line-height:1.6}
.wk-table{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:14px}
.wk-table th,.wk-table td{border-bottom:1px solid var(--hair);padding:6px 8px;text-align:left;vertical-align:top}
.wk-table th{background:#f3f1ea;color:var(--ink);font-weight:700;border-bottom:2px solid var(--ink)}
.wk-table td.c{text-align:center}
.wk-table tr.g td:first-child{font-weight:700}
.wk-nav{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.wk-nav a{font-size:12.5px;padding:4px 10px;border:1px solid var(--hair);text-decoration:none;color:var(--ink);background:#fff}
.wk-nav a.on{background:var(--ink);color:#fff;border-color:var(--ink)}

/* ── 푸터 ── */
.footer{margin-top:26px;border-top:3px double var(--rule);padding-top:10px;font-size:11.5px;color:var(--muted);line-height:1.7}

@media(max-width:1000px){.cols.three{column-count:2} .front{grid-template-columns:1fr} .front .lcol{border-right:0;padding-right:0;padding-bottom:10px;border-bottom:1px solid var(--hair);margin-bottom:6px}
  .wk-cols{grid-template-columns:1fr 1fr} .wk-cols.three{grid-template-columns:1fr 1fr}}
@media(max-width:640px){
  .sheet{margin:0;border:0;padding:0 14px 30px;box-shadow:none}
  .mast{grid-template-columns:1fr;gap:6px;text-align:center;padding:12px 0 8px}
  .mast .left{justify-content:center} .mast .logo{height:34px}
  .mast .name{font-size:26px} .mast .en{font-size:9.5px;letter-spacing:.22em}
  .mast .right{text-align:center;font-size:12px} .mast .right b{display:inline;margin-right:8px;font-size:13px}
  .dateline{font-size:12px;flex-wrap:wrap} .dateline .pub{display:none}
  .nav{justify-content:flex-start} .nav a{padding:9px 11px;font-size:13px}
  .lead-story h1{font-size:21px} .lead-story .b{font-size:14px}
  .cols,.cols.two,.cols.three{column-count:1}
  .guide-row{grid-template-columns:1fr} .guide{border-right:0;padding-right:0}
  .front .lcol{border-right:0;padding-right:0;border-bottom:1px solid var(--hair);padding-bottom:8px;margin-bottom:6px}
  .item .h{font-size:15px} .item .b{font-size:13.5px;line-height:1.6}
  .sec-head h2{font-size:19px} .sec-head .sub{display:none}
  .wk-cols,.wk-cols.three{grid-template-columns:1fr} .wk-col{border-left:0;padding-left:0}
  .wk-page{padding:12px 12px 14px}
  .sbar{grid-template-columns:1fr 1fr} .sbar input{grid-column:1 / -1} .sbar2{grid-template-columns:1fr 1fr}
  .arc .date{width:auto} .arc .no{width:48px}
}
@media print{
  body{background:#fff} .sheet{margin:0;border:0;box-shadow:none;max-width:none;padding:0}
  .nav,.issuenav,.sbar,.sbar2,.scount,.wk-nav{display:none!important}
  .meta .more{display:none} a{text-decoration:none}
  .section,.group,.item,.wk-page{break-inside:avoid;page-break-inside:avoid}
}
"""

# ---------------------------------------------------------------- 공통 조각
def brand_logo(base: str) -> str:
    png = ROOT / "assets" / "logo.png"
    return f'<img class="logo" src="{base}assets/logo.png" alt="ETS">' if png.exists() else ""


def head(title: str, active: str, base: str, issue_html: str = "", date_html: str = "") -> str:
    nav = "".join(f'<a href="{base}{href}" class="{"on" if key == active else ""}">{esc(label)}</a>' for href, label, key in NAV)
    return (
        f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{esc(title)}</title>{FONTS}<style>{STYLE}</style></head><body><div class="sheet">'
        f'<header class="mast"><div class="left">{brand_logo(base)}</div>'
        f'<div class="center"><div class="en">{esc(SITE_EN)}</div><a class="name" href="{base}index.html">{esc(SITE)}</a></div>'
        f'<div class="right">{issue_html}</div></header>'
        f'<div class="dateline">{date_html or "<span></span>"}<span class="pub">월~금 08:00 발행 · 공개 보도·공시 기반 · 사실만 기록</span></div>'
        f'<nav class="nav">{nav}</nav>'
    )


FOOT_NOTE = ("본 브리핑은 공개 보도·공시의 제목과 리드 문장을 규칙표(watchlist.yml)에 따라 자동 분류·등급화한 사실 정보입니다. "
             "등급 A=즉시보고 B=Daily C=Weekly, ★=출처 신뢰도(공시·IR 5, 정부·주요언론 4, 협회·채용·특허 3). 수치·계약 세부는 원문/공시로 확인하십시오.")


def foot(extra: str = "") -> str:
    return f'<div class="footer">{extra}{("<br>" if extra else "")}{esc(FOOT_NOTE)}<br>{esc(SITE)}</div></div></body></html>'


def stars(n: int) -> str:
    n = max(1, min(5, int(n or 2)))
    return f'<span class="stars" title="출처 신뢰도 {n}/5">{"★" * n}<span class="off">{"★" * (5 - n)}</span></span>'


def grade_badge(g: str) -> str:
    label = {"A": "A 즉시", "B": "B", "C": "C"}.get(g, g)
    return f'<span class="g {esc(g)}" title="중요도 {esc(g)}">{esc(label)}</span>'


def tag_html(tags: list[str]) -> str:
    return "".join(f'<span class="tag{" key" if t in ("주액", "RFQ", "리스크") else ""}">{esc(t)}</span>' for t in (tags or [])[:5])


BRIEF_MAX = int((WL.get("rules") or {}).get("brief_max_chars", 90))


def clamp_brief(b: str, max_chars: int = BRIEF_MAX) -> str:
    """핵심 한 문장만. 길면 단어 경계에서 자름. (예전 호의 긴 본문도 지면에서는 짧게)"""
    raw = B.strip_tags(b or "").strip()
    if not raw:
        return ""
    ss = B.sentences(raw)
    s = ss[0] if ss else raw
    if len(s) > max_chars + 15:
        s = s[:max_chars].rsplit(" ", 1)[0].rstrip(",·;:(") + "…"
    return B.highlight(s)


def render_item(it: dict, show_entity: bool = True, show_cat: bool = False, brief: bool = True) -> str:
    url = it.get("url")
    h = it.get("h", "")
    hh = f'<a href="{esc(url)}" target="_blank" rel="noopener">{h}</a>' if url else h
    bb = clamp_brief(it.get("b", "")) if brief else ""
    body = f'<p class="b">{bb}</p>' if bb else ""
    meta = [grade_badge(it.get("grade", "C"))]
    if show_entity and it.get("entity"):
        meta.append(f'<span class="ent">{esc(it["entity"])}</span>')
    if show_cat:
        meta.append(f'<span class="tag">{esc(CAT_TITLE.get(it.get("cat",""), it.get("cat","")))}</span>')
    if it.get("src"):
        meta.append(f'<span class="src">{esc(it["src"])}</span>')
    if it.get("date"):
        meta.append(f'<span>{esc(it["date"])}</span>')
    meta.append(stars(it.get("rel", 2)))
    if it.get("tags"):
        meta.append(tag_html(it["tags"]))
    if url:
        meta.append(f'<a class="more" href="{esc(url)}" target="_blank" rel="noopener">원문 보기 ↗</a>')
    fu = ""
    f = it.get("followup")
    if f:
        ch = f.get("change") or ""
        fu = (f'<div class="fu"><b>후속</b> · {esc(short_date(f.get("prev_date","")))} 게재분 대비 달라진 수치·일정: {esc(ch) if ch else "—"}</div>')
    return f'<article class="item" id="{esc(it.get("id",""))}"><h4 class="h">{hh}</h4>{body}{fu}<div class="meta">{" ".join(meta)}</div></article>'


# ---------------------------------------------------------------- 호(일간) 지면
def all_items(d: dict) -> list[dict]:
    return [it for s in d.get("sections", []) for g in s.get("groups", []) for it in g.get("items", [])]


def sales_guide_html(d: dict) -> str:
    """watchlist.sales_guide 규칙표에 맞는 항목 → '오늘의 영업 포인트' 한 줄씩(회사·신호·할 일)."""
    rules = WL.get("sales_guide") or []
    lines, seen = [], set()
    for it in all_items(d):
        for r in rules:
            if it.get("cat") not in (r.get("cats") or []):
                continue
            if it.get("grade", "C") not in (r.get("grades") or ["A", "B"]):
                continue
            if not set(r.get("tags_any") or []) & set(it.get("tags") or []):
                continue
            ent = it.get("entity") or (it.get("related") or [""])[0] or CAT_TITLE.get(it.get("cat", ""), "")
            say = str(r.get("say", "")).replace("{entity}", ent)
            key = say
            if key in seen:
                break
            seen.add(key)
            lines.append(f'<li><a href="#{esc(it["id"])}">{grade_badge(it.get("grade","C"))} {esc(say)}</a>'
                         f'<small>{esc(B.strip_tags(it.get("h",""))[:44])}</small></li>')
            break
        if len(lines) >= 7:
            break
    body = f'<ul>{"".join(lines)}</ul>' if lines else '<p class="empty">오늘은 규칙에 걸린 영업 신호가 없습니다.</p>'
    return f'<div class="guide"><h2>오늘의 영업 포인트 <small>규칙표(watchlist.yml sales_guide) 자동 연결</small></h2>{body}</div>'


LEGEND = (
    '<div class="legend"><h2>범례</h2><dl>'
    '<dt>등급</dt><dd><span class="g A">A 즉시</span> 대규모 투자·RFQ/입찰·투자 취소/연기·경쟁사 대형수주(500억 이상) &nbsp;'
    '<span class="g B">B</span> 수주·투자 진행·실적·정책 변화(Daily) &nbsp;<span class="g C">C</span> 일반 동향(Weekly)</dd>'
    '<dt>★ 신뢰도</dt><dd>★5 공시(DART·SEC)·고객 IR &nbsp;★4 정부·주요 언론 &nbsp;★3 전문지·협회·채용·특허 &nbsp;★2 그 외 매체·검색 결과</dd>'
    '<dt>태그</dt><dd><span class="tag key">주액</span> 당사 핵심 장비 &nbsp;<span class="tag key">RFQ</span> 입찰·발주 &nbsp;<span class="tag key">리스크</span> 연기·취소 &nbsp;'
    '<span class="tag">투자</span><span class="tag">수주</span><span class="tag">ESS</span> 등 키워드 자동 표식</dd>'
    '<dt>후속</dt><dd>이미 실린 사안이 수치·일정만 바뀌어 다시 실린 것. 무엇이 바뀌었는지 붉은 줄로 표시</dd>'
    '<dt>원칙</dt><dd>공개 보도·공시의 제목과 핵심 한 문장만 기록. 판단 문장 없음. 세부는 원문 보기 ↗</dd>'
    '</dl></div>'
)


def issue_meta_html(d: dict) -> tuple[str, str]:
    no = d.get("issue_no") or 0
    right = f'<b>제{no}호</b>{esc(B.kdate(d.get("date","")))}'
    dl = f'<span class="issue">제{no}호 · {esc(B.kdate(d.get("date","")))} · {esc(d.get("edition","조간"))}</span>'
    return right, dl


def issuenav(dates: list[str], cur: str, base: str) -> str:
    i = dates.index(cur) if cur in dates else -1
    older = dates[i + 1] if 0 <= i < len(dates) - 1 else None
    newer = dates[i - 1] if i > 0 else None
    left = f'<a href="{base}briefings/{older}.html">◀ 이전 호 {esc(older)}</a>' if older else '<span class="dis">◀ 이전 호</span>'
    right = f'<a href="{base}briefings/{newer}.html">다음 호 {esc(newer)} ▶</a>' if newer else '<span class="dis">다음 호 ▶</span>'
    return f'<div class="issuenav">{left}<span>{esc(cur)}</span>{right}</div>'


def front_html(d: dict) -> str:
    items = {it["id"]: it for it in all_items(d)}
    tops = [items[i] for i in d.get("top", []) if i in items]
    if not tops:
        return ""
    lead, side = tops[0], tops[1:]
    url = lead.get("url")
    h1 = f'<a href="{esc(url)}" target="_blank" rel="noopener">{lead["h"]}</a>' if url else lead["h"]
    kicker = f'{esc(CAT_TITLE.get(lead.get("cat",""), ""))}' + (f' · {esc(lead["entity"])}' if lead.get("entity") else "")
    meta = render_item(lead, show_entity=False, brief=False)
    meta = re.sub(r'^<article[^>]*><h4 class="h">.*?</h4>', "", meta, flags=re.S).replace("</article>", "")
    lead_html = (f'<div class="lead-story"><div class="kicker">오늘의 1면 · {kicker}</div><h1>{h1}</h1>'
                 f'<p class="b">{clamp_brief(lead.get("b",""), BRIEF_MAX + 40)}</p>{meta}</div>')
    side_html = ('<div class="side"><h2>주요 기사</h2>' + "".join(render_item(it, brief=False) for it in side) + "</div>") if side else ""
    # 왼쪽: 1면 톱 + 영업 포인트 / 오른쪽: 주요 기사 + 범례  (빈 공간 없이)
    return (f'<div class="front"><div class="lcol">{lead_html}{sales_guide_html(d)}</div>'
            f'<div class="rcol">{side_html}{LEGEND}</div></div>')


def section_html(sec: dict, no: int, exclude: set[str]) -> str:
    groups = []
    total = 0
    for g in sec.get("groups", []):
        its = [it for it in g.get("items", []) if it["id"] not in exclude]
        if not its:
            continue
        total += len(its)
        title = g.get("title") or ""
        gh = f'<h3>{esc(title)}<span class="gcnt">{len(its)}건</span></h3>' if title else ""
        groups.append(f'<div class="group">{gh}{"".join(render_item(it, show_entity=not title or title in ("글로벌 · 기타",) or sec["id"] in ("project","competitor")) for it in its)}</div>')
    n_front = sum(1 for g in sec.get("groups", []) for it in g.get("items", []) if it["id"] in exclude)
    circ = "①②③④⑤⑥⑦⑧⑨"[no - 1] if 1 <= no <= 9 else str(no)
    if not groups:   # 빈 면은 제목 한 줄로만(공백 없이)
        note = "오늘 소식은 1면에 실렸습니다" if n_front else "새 소식 없음"
        return (f'<section class="section thin" id="{esc(sec["id"])}"><div class="sec-head"><span class="no">{circ}</span>'
                f'<h2>{esc(sec.get("title",""))}</h2><span class="cnt">{note}</span></div></section>')
    cnt = f'{total}건' + (f' · 1면 {n_front}건' if n_front else "")
    ncol = "one" if total <= 4 else ("two" if total <= 10 else "three")
    body = f'<div class="cols {ncol}">{"".join(groups)}</div>'
    return (f'<section class="section" id="{esc(sec["id"])}"><div class="sec-head"><span class="no">{circ}</span>'
            f'<h2>{esc(sec.get("title",""))}</h2><span class="sub">{esc(sec.get("subtitle",""))}</span><span class="cnt">{cnt}</span></div>{body}</section>')


def brief_page(d: dict, dates: list[str], base: str, active: str, week_link: str = "") -> str:
    right, dl = issue_meta_html(d)
    tops = set(d.get("top", []))
    secs = "".join(section_html(s, i + 1, tops) for i, s in enumerate(d.get("sections", [])))
    n = len(all_items(d))
    guide = '' if d.get('top') else f'<div class="guide-row">{sales_guide_html(d)}{LEGEND}</div>'
    wk = f'<div class="summary">이번 주 <a href="{week_link}">주간 종합면</a>이 준비되었습니다.</div>' if week_link else ""
    srcs = d.get("sources") or []
    src_line = ("출처: " + esc("·".join(srcs[:16])) + (" 등" if len(srcs) > 16 else "")) if srcs else ""
    return (head(f"{SITE} 제{d.get('issue_no',0)}호 — {d.get('date','')}", active, base, right, dl) +
            issuenav(dates, d.get("date", ""), base) + front_html(d) + guide + wk + secs +
            foot(f"{src_line} · 오늘 {n}건"))


# ---------------------------------------------------------------- 지난 호(달력)
def archive_page(issues: list[dict]) -> str:
    by_date = {d["date"]: d for d in issues}
    dates = sorted(by_date)
    if not dates:
        return head(f"{SITE} — 지난 호", "archive", "") + '<div class="page-title">지난 호</div>' + foot()
    first, last = parse_date(dates[0]), parse_date(dates[-1])
    hol = set((WL.get("schedule") or {}).get("holidays") or [])
    months = []
    y, m = last.year, last.month
    while (y, m) >= (first.year, first.month):
        cal = calendar.Calendar(firstweekday=6)  # 일요일 시작
        cells = []
        for wd, lab in enumerate(["일", "월", "화", "수", "목", "금", "토"]):
            cells.append(f'<div class="wd{" sun" if wd == 0 else (" sat" if wd == 6 else "")}">{lab}</div>')
        n_month = 0
        for day in cal.itermonthdates(y, m):
            if day.month != m:
                cells.append('<div class="d off"></div>'); continue
            key = day.isoformat()
            wdc = " sun" if day.weekday() == 6 else (" sat" if day.weekday() == 5 else "")
            if key in by_date:
                n_month += 1
                cnt = len(all_items(by_date[key]))
                cells.append(f'<a class="d has{wdc}" href="briefings/{key}.html" title="제{by_date[key].get("issue_no",0)}호">{day.day}<small>{cnt}건</small></a>')
            else:
                off = " off" if (day.weekday() >= 5 or key in hol) else ""
                cells.append(f'<div class="d{wdc}{off}">{day.day}</div>')
        months.append(f'<div class="month"><h3>{y}년 {m}월<small>{n_month}호</small></h3><div class="cal">{"".join(cells)}</div></div>')
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    rows = []
    for d in issues:
        rows.append(f'<a class="arc" href="briefings/{esc(d["date"])}.html"><span class="no">제{d.get("issue_no",0)}호</span>'
                    f'<span class="date">{esc(B.kdate(d["date"]))}</span><span class="top">{esc(d.get("summary",""))}</span></a>')
    return (head(f"{SITE} — 지난 호", "archive", "") +
            f'<div class="page-title">지난 호</div><p class="page-sub">총 {len(issues)}호 · 달력의 날짜를 누르면 그날 지면으로 이동합니다. 회색은 주말·공휴일(발행 없음).</p>'
            f'<div class="months">{"".join(months)}</div><div class="arc-list">{"".join(rows)}</div>' + foot())


# ---------------------------------------------------------------- 회사별
def flat(issues: list[dict]) -> list[tuple[str, dict]]:
    return [(d["date"], it) for d in issues for it in all_items(d)]


def companies_pages(issues: list[dict]) -> dict[str, str]:
    by: dict[str, list] = {}
    for date, it in flat(issues):
        names = ([it["entity"]] if it.get("entity") else []) + list(it.get("related") or [])
        for n in names:
            by.setdefault(n, []).append((date, it))
    def tiles(names: list[str]) -> str:
        out = []
        for n in names:
            rows = by.get(n, [])
            if not rows:
                continue
            out.append(f'<a class="co" href="{slug(n)}.html"><div class="n">{esc(n)}</div><div class="m"><b>{len(rows)}건</b> · 최근 {esc(rows[0][0])}</div></a>')
        return "".join(out)
    cust = tiles(CUSTOMER_NAMES); comp = tiles(COMPETITOR_NAMES)
    others = tiles(sorted(n for n in by if n not in CUSTOMER_NAMES and n not in COMPETITOR_NAMES))
    idx = (head(f"{SITE} — 회사별", "companies", "../") +
           '<div class="page-title">회사별 모아보기</div><p class="page-sub">회사를 누르면 날짜별 누적 기록을 볼 수 있습니다.</p>' +
           (f'<div class="dgroup"><h3>고객사</h3></div><div class="co-grid">{cust}</div>' if cust else "") +
           (f'<div class="dgroup"><h3>경쟁사</h3></div><div class="co-grid">{comp}</div>' if comp else "") +
           (f'<div class="dgroup"><h3>기타</h3></div><div class="co-grid">{others}</div>' if others else "") + foot())
    pages = {"index.html": idx}
    for name, rows in by.items():
        groups: dict[str, list] = {}
        for date, it in rows:
            groups.setdefault(date, []).append(it)
        blocks = []
        for date in sorted(groups, reverse=True):
            inner = "".join(render_item(it, show_entity=it.get("entity") != name, show_cat=True) for it in groups[date])
            blocks.append(f'<div class="dgroup"><h3>{esc(B.kdate(date))}<small>{len(groups[date])}건</small></h3><div class="list">{inner}</div></div>')
        info = next((c for c in COMPETITORS if c["name"] == name), None)
        sub = f'경쟁사 {esc(info.get("grade",""))}등급 · {esc(info.get("country",""))} · {esc(info.get("scope",""))}' if info else ("고객사" if name in CUSTOMER_NAMES else "")
        pages[f"{slug(name)}.html"] = (head(f"{SITE} — {name}", "companies", "../") +
                                       f'<div class="page-title">{esc(name)}</div><p class="page-sub">{sub}{" · " if sub else ""}누적 {len(rows)}건 · 최신순</p>{"".join(blocks)}' + foot())
    return pages


# ---------------------------------------------------------------- 검색
def search_page(issues: list[dict]) -> tuple[str, list[dict]]:
    idx = []
    for date, it in flat(issues):
        idx.append({"d": date, "c": it.get("cat", ""), "ct": CAT_TITLE.get(it.get("cat", ""), ""), "e": it.get("entity", ""),
                    "r": " ".join(it.get("related") or []), "t": " ".join(it.get("tags") or []), "g": it.get("grade", "C"),
                    "rl": it.get("rel", 2), "h": B.strip_tags(it.get("h", "")), "b": B.strip_tags(it.get("b", "")),
                    "u": it.get("url", ""), "s": it.get("src", ""), "f": 1 if it.get("followup") else 0})
    ents = sorted({r["e"] for r in idx if r["e"]})
    cats = [(c["id"], c.get("title", "")) for c in WL.get("categories") or []]
    ent_opts = "".join(f'<option value="{esc(e)}">{esc(e)}</option>' for e in ents)
    cat_opts = "".join(f'<option value="{esc(i)}">{esc(t)}</option>' for i, t in cats)
    js = r"""
(function(){
  var idx=JSON.parse(document.getElementById('idx').textContent);
  var $=function(i){return document.getElementById(i)};
  var q=$('q'),cat=$('cat'),ent=$('ent'),gr=$('gr'),df=$('df'),dt=$('dt'),res=$('res'),cnt=$('cnt');
  function esc(s){return String(s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]});}
  function stars(n){n=Math.max(1,Math.min(5,n|0));return '<span class="stars">'+'★'.repeat(n)+'<span class="off">'+'★'.repeat(5-n)+'</span></span>';}
  function run(){
    var t=q.value.trim().toLowerCase(),c=cat.value,e=ent.value,g=gr.value,a=df.value,b=dt.value;
    var terms=t?t.split(/\s+/):[];
    var out=idx.filter(function(r){
      if(c&&r.c!==c)return false; if(e&&r.e!==e&&r.r.indexOf(e)<0)return false; if(g&&r.g!==g)return false;
      if(a&&r.d<a)return false; if(b&&r.d>b)return false;
      if(!terms.length)return true;
      var hay=(r.h+' '+r.b+' '+r.e+' '+r.r+' '+r.t+' '+r.s).toLowerCase();
      return terms.every(function(w){return hay.indexOf(w)>=0});
    });
    cnt.textContent=out.length+'건';
    res.innerHTML=out.map(function(r){
      var h=r.u?'<a href="'+esc(r.u)+'" target="_blank" rel="noopener">'+esc(r.h)+'</a>':esc(r.h);
      var tags=r.t?r.t.split(' ').map(function(x){return '<span class="tag">'+esc(x)+'</span>'}).join(''):'';
      return '<article class="item"><h4 class="h">'+h+'</h4>'+(r.b?'<p class="b">'+esc(r.b)+'</p>':'')+
        '<div class="meta"><span class="g '+esc(r.g)+'">'+esc(r.g)+'</span>'+(r.e?'<span class="ent">'+esc(r.e)+'</span>':'')+
        '<span class="tag">'+esc(r.ct)+'</span><span class="src">'+esc(r.s)+'</span><span>'+esc(r.d)+'</span>'+stars(r.rl)+tags+
        (r.f?'<span class="tag key">후속</span>':'')+(r.u?'<a class="more" href="'+esc(r.u)+'" target="_blank" rel="noopener">원문 보기 ↗</a>':'')+'</div></article>';
    }).join('')||'<p class="page-sub">결과가 없습니다.</p>';
  }
  [q,cat,ent,gr,df,dt].forEach(function(el){el.addEventListener('input',run);el.addEventListener('change',run);});
  var p=new URLSearchParams(location.search); if(p.get('q')){q.value=p.get('q');} if(p.get('e')){ent.value=p.get('e');}
  run();
})();"""
    page = (head(f"{SITE} — 검색", "search", "") +
            f'<div class="page-title">검색</div><p class="page-sub">키워드·카테고리·회사·등급·기간으로 누적 {len(idx)}건에서 찾습니다. 여러 단어는 모두 포함된 것만.</p>'
            f'<div class="sbar"><input id="q" type="search" placeholder="예: 전해액 주액, ESS 수주, 46시리즈, 착공">'
            f'<select id="cat"><option value="">모든 카테고리</option>{cat_opts}</select>'
            f'<select id="ent"><option value="">모든 회사</option>{ent_opts}</select>'
            f'<select id="gr"><option value="">모든 등급</option><option value="A">A 즉시</option><option value="B">B Daily</option><option value="C">C Weekly</option></select></div>'
            f'<div class="sbar2"><label>부터 <input id="df" type="date"></label><label>까지 <input id="dt" type="date"></label><span class="scount" id="cnt"></span></div>'
            f'<div class="sres list" id="res"></div>'
            f'<script id="idx" type="application/json">{json.dumps(idx, ensure_ascii=False)}</script>'
            f'<script>{js}</script>' + foot())
    return page, idx


# ---------------------------------------------------------------- 주간 종합(3면)
def weekly_html(issues_in_week: list[dict], label: str, mon: str, fri: str, all_labels: list[str], cur_label: str, base: str) -> str:
    rows = flat(sorted(issues_in_week, key=lambda d: d["date"], reverse=True))
    n_issues = len(issues_in_week)

    def col(title: str, its: list[dict], show_entity=True) -> str:
        inner = "".join(render_item(it, show_entity=show_entity) for it in its) or '<div class="empty">이번 주 새 소식 없음</div>'
        return f'<div class="wk-col"><h4>{esc(title)}<small>{len(its)}건</small></h4>{inner}</div>'

    # 1면: 시장/산업동향 (전기차·이차전지·반도체·스마트팩토리/AMR) — market + tech_policy
    mk = {"ev": [], "battery": [], "semi": [], "fa": []}
    for d, it in rows:
        if it["cat"] == "market":
            mk.setdefault(it.get("group", "battery"), []).append(it)
        elif it["cat"] == "tech_policy":
            mk.setdefault(it.get("market_group") or "battery", []).append(it)
    p1 = ('<div class="wk-page"><div class="wk-head"><span class="p">1면</span><span class="t">시장 / 산업 동향</span><span class="r">시장규모·수요전망·정책·기술 Trend</span></div>'
          f'<div class="wk-cols">{col("전기차", mk["ev"], False)}{col("이차전지", mk["battery"], False)}{col("반도체", mk["semi"], False)}{col("스마트팩토리 · AMR", mk["fa"], False)}</div></div>')
    # 2면: 고객사 동향 (LG엔솔·SDI·SK on·기타) — customer + project
    cu = {"LG에너지솔루션": [], "삼성SDI": [], "SK온": [], "기타": []}
    for d, it in rows:
        if it["cat"] in ("customer", "project"):
            cu[it["entity"] if it.get("entity") in cu else "기타"].append(it)
    p2 = ('<div class="wk-page"><div class="wk-head"><span class="p">2면</span><span class="t">고객사 동향</span><span class="r">CAPEX·신공장·증설·JV·연기/취소 · Project/RFQ</span></div>'
          f'<div class="wk-cols">{col("LG에너지솔루션", cu["LG에너지솔루션"], False)}{col("삼성SDI", cu["삼성SDI"], False)}{col("SK온", cu["SK온"], False)}{col("글로벌 · 기타", cu["기타"], True)}</div></div>')
    # 3면: 업계 동향 (경쟁사 A/B + 등급표)
    co = {"A": [], "B": [], "기타": []}
    cnt_by: dict[str, int] = {}
    for d, it in rows:
        if it["cat"] == "competitor":
            g = next((c.get("grade") for c in COMPETITORS if c["name"] == it.get("entity")), None)
            co["A" if g == "A" else ("B" if g == "B" else "기타")].append(it)
            cnt_by[it.get("entity", "")] = cnt_by.get(it.get("entity", ""), 0) + 1
    trs = []
    for c in COMPETITORS:
        n = cnt_by.get(c["name"], 0)
        link = f'<a href="{base}companies/{slug(c["name"])}.html">{esc(c["name"])}</a>' if n else esc(c["name"])
        trs.append(f'<tr class="g"><td>{link}</td><td class="c">{esc(c.get("grade",""))}</td><td>{esc(c.get("country",""))}</td><td>{esc(c.get("scope",""))}</td><td class="c">{n or "–"}</td></tr>')
    table = ('<table class="wk-table"><thead><tr><th>경쟁사</th><th>등급</th><th>국가</th><th>주요 장비·범위</th><th>이번 주 보도</th></tr></thead>'
             f'<tbody>{"".join(trs)}</tbody></table>')
    p3 = ('<div class="wk-page"><div class="wk-head"><span class="p">3면</span><span class="t">업계 동향</span><span class="r">경쟁사 수주·신규장비·기술·해외진출</span></div>'
          f'<div class="wk-cols three">{col("A등급 경쟁사", co["A"])}{col("B등급 경쟁사", co["B"])}{col("기타 업계", co["기타"])}</div>{table}</div>')
    nav = "".join(f'<a href="{base}weekly/{l}.html" class="{"on" if l == cur_label else ""}">{esc(l)}</a>' for l in all_labels)
    total = len(rows)
    right = f'<b>주간 종합</b>{esc(mon)} ~ {esc(fri)}'
    dl = f'<span class="issue">주간 종합 {esc(label)} · {esc(B.kdate(mon))} ~ {esc(B.kdate(fri))}</span>'
    return (head(f"{SITE} — 주간 종합 {label}", "weekly", base, right, dl) +
            f'<div class="page-title">주간 종합 <small style="font-family:var(--sans);font-size:14px;color:var(--muted);font-weight:500">{esc(label)} · 발행 {n_issues}호 · {total}건</small></div>'
            f'<p class="page-sub">그 주 월~금 지면을 「시장/산업 · 고객사 · 업계」 3면으로 모았습니다. 회의 자료로 그대로 인쇄해 쓸 수 있습니다.</p>'
            f'<div class="wk-nav">{nav}</div>{p1}{p2}{p3}' + foot())


def weekly_pages(issues: list[dict]) -> tuple[dict[str, str], str, dict[str, str]]:
    """→ (weekly/<label>.html 들, 최신 label, {date: label})"""
    weeks: dict[str, list] = {}
    meta: dict[str, tuple[str, str]] = {}
    date_label: dict[str, str] = {}
    for d in issues:
        label, mon, fri = B.week_of(d["date"])
        weeks.setdefault(label, []).append(d); meta[label] = (mon, fri); date_label[d["date"]] = label
    labels = sorted(weeks, reverse=True)
    pages = {}
    for l in labels:
        mon, fri = meta[l]
        pages[f"{l}.html"] = weekly_html(weeks[l], l, mon, fri, labels, l, "../")
    latest = labels[0] if labels else ""
    return pages, latest, date_label


# ---------------------------------------------------------------- main
def load_all() -> list[dict]:
    out = []
    for f in sorted(DATA.glob("*.json"), reverse=True):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ! {f.name}: {e}", file=sys.stderr); continue
        if d.get("schema") != 4:
            print(f"  ! {f.name}: 구 스키마 — scripts/migrate_v4.py 실행 필요, 건너뜀", file=sys.stderr); continue
        out.append(d)
    out.sort(key=lambda x: x.get("date", ""), reverse=True)
    return out


def placeholder_page() -> str:
    right = "<b>준비 중</b>첫 호 발행 전"
    dl = '<span class="issue">아직 발행된 호가 없습니다</span>'
    body = ('<div class="page-title">첫 호를 기다리고 있습니다</div>'
            '<p class="page-sub">월~금 아침 8시 자동 발행이 시작되면 이 자리에 제1호가 실립니다. '
            '(GitHub → Actions → "영업 브리핑 자동 발행" → Run workflow 로 지금 바로 만들 수도 있습니다.)</p>')
    return head(SITE, "today", "", right, dl) + body + foot()


def main() -> int:
    issues = load_all()
    if not issues:
        ph = placeholder_page()
        for name in ("index.html", "archive.html", "search.html", "weekly.html"):
            (ROOT / name).write_text(ph, encoding="utf-8")
        COMP.mkdir(exist_ok=True); (COMP / "index.html").write_text(placeholder_page().replace('href="index.html"', 'href="../index.html"'), encoding="utf-8")
        print("data/*.json 없음 — 첫 호 발행 전 안내 페이지를 생성했습니다."); return 0
    dates = [d["date"] for d in issues]
    BRIEF.mkdir(exist_ok=True); COMP.mkdir(exist_ok=True); WEEK.mkdir(exist_ok=True)
    wpages, latest_week, date_label = weekly_pages(issues)
    for name, html_ in wpages.items():
        (WEEK / name).write_text(html_, encoding="utf-8")
    for d in issues:
        wl = f'../weekly/{date_label[d["date"]]}.html' if parse_date(d["date"]).weekday() == 4 else ""
        (BRIEF / f'{d["date"]}.html').write_text(brief_page(d, dates, "../", "archive", wl), encoding="utf-8")
    top = issues[0]
    wl0 = f'weekly/{date_label[top["date"]]}.html' if parse_date(top["date"]).weekday() == 4 else ""
    (ROOT / "index.html").write_text(brief_page(top, dates, "", "today", wl0), encoding="utf-8")
    (ROOT / "archive.html").write_text(archive_page(issues), encoding="utf-8")
    for name, html_ in companies_pages(issues).items():
        (COMP / name).write_text(html_, encoding="utf-8")
    spage, idx = search_page(issues)
    (ROOT / "search.html").write_text(spage, encoding="utf-8")
    (ROOT / "search-index.json").write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
    if latest_week:
        wk = weekly_html([d for d in issues if date_label[d["date"]] == latest_week], latest_week,
                         *B.week_of(next(d["date"] for d in issues if date_label[d["date"]] == latest_week))[1:],
                         sorted(set(date_label.values()), reverse=True), latest_week, "")
        (ROOT / "weekly.html").write_text(wk, encoding="utf-8")
    n_items = sum(len(all_items(d)) for d in issues)
    print(f"생성 완료: {len(issues)}호 · {n_items}건 · 최신 제{top.get('issue_no',0)}호({top['date']}) · 회사별 {len(list(COMP.glob('*.html')))-1}개 · 주간 {len(wpages)}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
