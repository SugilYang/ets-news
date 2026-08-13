#!/usr/bin/env python3
"""
이티에스 산업신문 - 뉴스 수집 및 지면 생성기.

구글 뉴스 RSS에서 섹션별 기사를 수집한 뒤,
신문 지면 형태의 정적 HTML(public/index.html)과
아카이브용 JSON(public/data/news.json)을 생성합니다.

- 네트워크 실패 시에도 안전하게 동작하며(플레이스홀더 표시),
  일부 피드만 실패해도 나머지 기사는 정상 게시됩니다.
- GitHub Actions(인터넷 접근 가능) 에서 매일 아침 실행되도록 설계되었습니다.
"""

from __future__ import annotations

import html
import json
import re
import socket
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import feedparser  # type: ignore
except ImportError:  # pragma: no cover
    feedparser = None

from feeds import GOOGLE_NEWS_RSS, SECTIONS, SITE

# ---------------------------------------------------------------------------
KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "public"
DATA_DIR = OUT_DIR / "data"
FEED_TIMEOUT = 20  # 초

WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]


def now_kst() -> datetime:
    return datetime.now(tz=KST)


def clean_text(value: str) -> str:
    """HTML 태그 제거 + 엔티티 정리."""
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def split_title_source(raw_title: str) -> tuple[str, str]:
    """구글 뉴스 제목은 보통 '기사제목 - 매체명' 형태."""
    raw_title = clean_text(raw_title)
    if " - " in raw_title:
        head, _, tail = raw_title.rpartition(" - ")
        if head and len(tail) <= 40:
            return head.strip(), tail.strip()
    return raw_title, ""


def to_kst(struct_time) -> datetime | None:
    if not struct_time:
        return None
    try:
        dt = datetime(*struct_time[:6], tzinfo=timezone.utc)
        return dt.astimezone(KST)
    except Exception:
        return None


def humanize(dt: datetime | None, ref: datetime) -> str:
    if dt is None:
        return ""
    delta = ref - dt
    secs = delta.total_seconds()
    if secs < 0:
        secs = 0
    if secs < 3600:
        mins = int(secs // 60)
        return f"{max(mins, 1)}분 전"
    if secs < 86400:
        return f"{int(secs // 3600)}시간 전"
    if secs < 86400 * 7:
        return f"{int(secs // 86400)}일 전"
    return dt.strftime("%m.%d")


def fetch_feed(url: str) -> list[dict]:
    """단일 RSS 피드에서 기사 목록 추출. 실패 시 빈 리스트."""
    if feedparser is None:
        return []
    try:
        socket.setdefaulttimeout(FEED_TIMEOUT)
        parsed = feedparser.parse(
            url,
            agent="Mozilla/5.0 (compatible; ETS-IndustryDaily/1.0)",
        )
    except Exception as exc:  # pragma: no cover
        print(f"  ! 피드 오류: {exc}", file=sys.stderr)
        return []

    items = []
    for entry in getattr(parsed, "entries", []):
        title, src_from_title = split_title_source(entry.get("title", ""))
        if not title:
            continue
        source = ""
        if isinstance(entry.get("source"), dict):
            source = clean_text(entry["source"].get("title", ""))
        source = source or src_from_title
        published = to_kst(entry.get("published_parsed")) or to_kst(
            entry.get("updated_parsed")
        )
        items.append(
            {
                "title": title,
                "link": entry.get("link", ""),
                "source": source,
                "published": published,
            }
        )
    return items


def collect_section(section: dict, ref: datetime) -> list[dict]:
    """섹션의 모든 검색어를 수집·병합·중복제거·정렬."""
    seen: set[str] = set()
    articles: list[dict] = []
    per_source = SITE["articles_per_source"]

    for query in section["queries"]:
        url = GOOGLE_NEWS_RSS.format(q=urllib.parse.quote(query))
        feed_items = fetch_feed(url)[:per_source]
        print(f"  · '{query}' → {len(feed_items)}건")
        for item in feed_items:
            key = re.sub(r"\W+", "", item["title"].lower())[:60]
            if not key or key in seen:
                continue
            seen.add(key)
            articles.append(item)

    # 최신순 정렬 (published 없으면 뒤로)
    articles.sort(
        key=lambda a: a["published"] or datetime(1970, 1, 1, tzinfo=KST),
        reverse=True,
    )
    return articles[: section["limit"]]


def placeholder_articles(section: dict) -> list[dict]:
    """네트워크가 없거나 수집 결과가 0건일 때의 안내용 카드."""
    return [
        {
            "title": "첫 자동 수집이 완료되면 이 자리에 실제 기사가 표시됩니다",
            "link": "#",
            "source": "안내 · 아직 수집 전",
            "published": None,
            "placeholder": True,
        },
        {
            "title": f"‘{section['name']}’ 섹션은 매일 아침 8시에 자동으로 갱신됩니다",
            "link": "#",
            "source": "이티에스 산업신문",
            "published": None,
            "placeholder": True,
        },
    ]


# --- HTML 렌더링 -------------------------------------------------------------

def esc(value: str) -> str:
    return html.escape(value or "", quote=True)


def render_article_card(art: dict, ref: datetime, big: bool = False) -> str:
    is_ph = art.get("placeholder")
    time_txt = humanize(art.get("published"), ref)
    source = art.get("source") or "출처 미상"
    tag = f'<span class="src">{esc(source)}</span>'
    if time_txt:
        tag += f'<span class="dot">·</span><span class="time">{esc(time_txt)}</span>'
    title = esc(art["title"])
    link = art.get("link") or "#"
    cls = "article big" if big else "article"
    if is_ph:
        cls += " placeholder"
        return (
            f'<article class="{cls}">'
            f'<h3 class="headline">{title}</h3>'
            f'<div class="meta">{tag}</div>'
            f"</article>"
        )
    target = ' target="_blank" rel="noopener"' if link != "#" else ""
    return (
        f'<article class="{cls}">'
        f'<h3 class="headline"><a href="{esc(link)}"{target}>{title}</a></h3>'
        f'<div class="meta">{tag}</div>'
        f"</article>"
    )


def render_section(section: dict, articles: list[dict], ref: datetime) -> str:
    accent = section.get("accent", "default")
    header = (
        f'<div class="section-head accent-{accent}">'
        f'<h2 id="{section["id"]}">{esc(section["name"])}</h2>'
        f'<span class="tagline">{esc(section["tagline"])}</span>'
        f"</div>"
    )

    if section.get("lead") and articles and not articles[0].get("placeholder"):
        lead = render_article_card(articles[0], ref, big=True)
        rest = "".join(render_article_card(a, ref) for a in articles[1:])
        body = (
            f'<div class="lead-wrap">'
            f'<div class="lead">{lead}</div>'
            f'<div class="lead-rest columns">{rest}</div>'
            f"</div>"
        )
    else:
        cards = "".join(render_article_card(a, ref) for a in articles)
        body = f'<div class="columns">{cards}</div>'

    return f'<section class="news-section accent-{accent}">{header}{body}</section>'


def render_ticker(all_articles: list[dict]) -> str:
    live = [a for a in all_articles if not a.get("placeholder")]
    heads = [esc(a["title"]) for a in live[:12]]
    if not heads:
        heads = ["첫 자동 수집을 기다리는 중입니다 — 매일 아침 8시 자동 갱신"]
    items = " <span class='tk-dot'>◆</span> ".join(heads)
    # 끊김 없는 스크롤을 위해 두 번 반복
    return (
        '<div class="ticker" aria-label="속보">'
        '<span class="ticker-label">속보</span>'
        f'<div class="ticker-track"><span>{items}</span><span aria-hidden="true">{items}</span></div>'
        "</div>"
    )


def render_briefing(sections_data: list[tuple[dict, list[dict]]], ref: datetime) -> str:
    total = sum(
        len([a for a in arts if not a.get("placeholder")]) for _, arts in sections_data
    )
    rows = []
    for section, arts in sections_data:
        n = len([a for a in arts if not a.get("placeholder")])
        rows.append(
            f'<li><a href="#{section["id"]}">{esc(section["name"])}</a>'
            f'<span class="cnt">{n}</span></li>'
        )
    return (
        '<aside class="briefing">'
        '<h2>오늘의 브리핑</h2>'
        f'<p class="brief-total">오늘 지면에 <strong>{total}</strong>건의 기사가 실렸습니다.</p>'
        f'<ul class="brief-list">{"".join(rows)}</ul>'
        f'<p class="brief-time">최종 갱신: {ref.strftime("%Y.%m.%d %H:%M")} (KST)</p>'
        "</aside>"
    )


def render_nav() -> str:
    links = "".join(
        f'<a href="#{s["id"]}">{esc(s["name"])}</a>' for s in SECTIONS
    )
    return f'<nav class="section-nav"><div class="nav-inner">{links}</div></nav>'


def build_html(sections_data: list[tuple[dict, list[dict]]], ref: datetime) -> str:
    epoch = datetime.strptime(SITE["epoch"], "%Y-%m-%d").date()
    issue_no = (ref.date() - epoch).days + 1
    date_line = (
        f'{ref.year}년 {ref.month}월 {ref.day}일 '
        f'{WEEKDAYS_KO[ref.weekday()]}요일'
    )

    all_articles = [a for _, arts in sections_data for a in arts]
    sections_html = "".join(
        render_section(s, arts, ref) for s, arts in sections_data
    )

    css = STYLE
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(SITE['paper_name'])}</title>
<meta name="description" content="{esc(SITE['paper_name'])} — 관련 뉴스를 매일 아침 자동 업데이트합니다.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@400;700;800&family=Noto+Sans+KR:wght@300;400;500;700&display=swap" rel="stylesheet">
<style>{css}</style>
</head>
<body>
<header class="masthead">
  <div class="masthead-top">
    <span>제 {issue_no:,} 호</span>
    <span>{esc(date_line)}</span>
  </div>
  <div class="masthead-main">
    <h1 class="paper-title">{esc(SITE['paper_name'])}</h1>
  </div>
</header>
{render_ticker(all_articles)}
{render_nav()}
<main class="wrap">
  <div class="top-grid">
    {render_briefing(sections_data, ref)}
    <div class="lead-column">
      {render_section(sections_data[0][0], sections_data[0][1], ref)}
    </div>
  </div>
  <div class="rest-sections">
    {''.join(render_section(s, arts, ref) for s, arts in sections_data[1:])}
  </div>
</main>
<footer class="site-footer">
  <div class="footer-inner">
    <div class="footer-brand">
      <div class="footer-title">{esc(SITE['paper_name'])}</div>
    </div>
    <div class="footer-note">
      <p>본 지면의 기사는 구글 뉴스(Google News)에서 관련 키워드로 자동 수집·요약한 것으로,
         각 기사의 저작권은 해당 언론사에 있습니다. 제목을 누르면 원문으로 이동합니다.</p>
      <p>매일 아침 8시(KST) 자동 갱신 · 최종 갱신 {ref.strftime('%Y.%m.%d %H:%M')}</p>
    </div>
  </div>
</footer>
<button class="to-top" onclick="window.scrollTo({{top:0,behavior:'smooth'}})" aria-label="맨 위로">▲</button>
</body>
</html>
"""


# --- 스타일 (신문 지면) ------------------------------------------------------
STYLE = """
:root{
  --ink:#1a1a1a; --paper:#f7f4ec; --paper2:#fffdf8; --rule:#1a1a1a;
  --muted:#6b6459; --line:#d8d1c2; --link:#111;
  --red:#b3261e; --blue:#1f4e79; --green:#1f6b3b; --gold:#8a6d1a;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:'Noto Sans KR',system-ui,sans-serif; line-height:1.5;
  -webkit-font-smoothing:antialiased;
}
a{color:var(--link); text-decoration:none}
a:hover{text-decoration:underline}

/* 제호 */
.masthead{max-width:1180px;margin:0 auto;padding:18px 20px 0}
.masthead-top{
  display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;
  font-size:12.5px;color:var(--muted);letter-spacing:.02em;
  border-bottom:1px solid var(--ink);padding-bottom:8px;
}
.masthead-main{text-align:center;padding:14px 0 6px;
  border-bottom:3px double var(--ink)}
.paper-title{
  font-family:'Nanum Myeongjo',serif;font-weight:800;
  font-size:clamp(38px,7vw,74px);margin:0;letter-spacing:.04em;line-height:1;
}
.paper-en{font-size:12px;letter-spacing:.5em;color:var(--muted);
  margin-top:8px;padding-left:.5em}
.masthead-sub{text-align:center;font-size:13.5px;color:var(--muted);
  padding:8px 0 12px;letter-spacing:.03em}

/* 속보 티커 */
.ticker{display:flex;align-items:stretch;background:var(--ink);color:#f7f4ec;
  overflow:hidden;max-width:1180px;margin:0 auto}
.ticker-label{background:var(--red);color:#fff;font-weight:700;font-size:12.5px;
  padding:7px 14px;white-space:nowrap;display:flex;align-items:center;letter-spacing:.1em}
.ticker-track{display:flex;white-space:nowrap;animation:tick 60s linear infinite}
.ticker-track span{padding:7px 0 7px 18px;font-size:13px}
.tk-dot{color:#c9a227;padding:0 4px}
@keyframes tick{from{transform:translateX(0)}to{transform:translateX(-50%)}}
.ticker:hover .ticker-track{animation-play-state:paused}

/* 섹션 내비게이션 */
.section-nav{position:sticky;top:0;z-index:20;background:var(--paper2);
  border-bottom:2px solid var(--ink);border-top:1px solid var(--line)}
.nav-inner{max-width:1180px;margin:0 auto;display:flex;gap:2px;overflow-x:auto;
  padding:0 12px}
.nav-inner a{font-size:13px;font-weight:500;padding:11px 12px;white-space:nowrap;
  color:var(--ink);border-bottom:2px solid transparent}
.nav-inner a:hover{border-bottom-color:var(--red);text-decoration:none}

.wrap{max-width:1180px;margin:0 auto;padding:22px 20px 40px}

/* 상단: 브리핑 + 리드 */
.top-grid{display:grid;grid-template-columns:260px 1fr;gap:26px;
  padding-bottom:18px;margin-bottom:8px;border-bottom:3px double var(--ink)}
.briefing{border:1px solid var(--line);background:var(--paper2);padding:16px 16px 14px;
  align-self:start}
.briefing h2{font-family:'Nanum Myeongjo',serif;font-size:19px;margin:0 0 10px;
  border-bottom:2px solid var(--ink);padding-bottom:6px}
.brief-total{font-size:13px;color:var(--muted);margin:0 0 10px}
.brief-total strong{color:var(--red);font-size:15px}
.brief-list{list-style:none;margin:0;padding:0}
.brief-list li{display:flex;justify-content:space-between;align-items:center;
  padding:6px 0;border-bottom:1px dotted var(--line);font-size:13.5px}
.brief-list a{font-weight:500}
.brief-list .cnt{font-size:11px;color:#fff;background:var(--ink);border-radius:10px;
  padding:1px 8px;min-width:22px;text-align:center}
.brief-time{font-size:11.5px;color:var(--muted);margin:12px 0 0}

/* 섹션 공통 */
.news-section{margin:26px 0 8px;padding-top:6px}
.rest-sections .news-section{border-top:1px solid var(--line);margin-top:0;padding-top:22px}
.section-head{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;
  border-bottom:2px solid var(--ink);padding-bottom:8px;margin-bottom:16px}
.section-head h2{font-family:'Nanum Myeongjo',serif;font-weight:800;font-size:24px;
  margin:0;letter-spacing:.02em;scroll-margin-top:52px}
.section-head .tagline{font-size:12.5px;color:var(--muted)}
.accent-red .section-head{border-bottom-color:var(--red)}
.accent-red .section-head h2{color:var(--red)}
.accent-blue .section-head h2{color:var(--blue)}
.accent-green .section-head h2{color:var(--green)}
.accent-gold .section-head h2{color:var(--gold)}

/* 기사 카드 */
.columns{column-count:3;column-gap:26px}
@media(max-width:900px){.columns{column-count:2}}
@media(max-width:620px){.columns{column-count:1}}
.article{break-inside:avoid;padding:0 0 14px;margin:0 0 14px;
  border-bottom:1px solid var(--line)}
.article .headline{font-family:'Nanum Myeongjo',serif;font-weight:700;
  font-size:16.5px;line-height:1.35;margin:0 0 6px}
.article .headline a:hover{color:var(--red)}
.article .meta{font-size:12px;color:var(--muted)}
.article .meta .src{font-weight:500;color:#4a4a4a}
.article .meta .dot{padding:0 5px}
.article.placeholder{opacity:.7}
.article.placeholder .headline{font-style:italic;font-weight:400;font-size:15px}

/* 리드(머리기사) */
.lead-wrap{display:block}
.lead .article.big{border-bottom:2px solid var(--ink);padding-bottom:16px;margin-bottom:16px}
.lead .article.big .headline{font-size:clamp(24px,3vw,32px);line-height:1.2}
.lead .article.big .meta{font-size:13px}
.lead-rest.columns{column-count:2}
@media(max-width:620px){.lead-rest.columns{column-count:1}}

@media(max-width:820px){
  .top-grid{grid-template-columns:1fr}
}

/* 푸터 */
.site-footer{background:var(--ink);color:#e7e2d6;margin-top:20px}
.footer-inner{max-width:1180px;margin:0 auto;padding:26px 20px;
  display:grid;grid-template-columns:1fr 1.4fr;gap:24px}
@media(max-width:700px){.footer-inner{grid-template-columns:1fr}}
.footer-title{font-family:'Nanum Myeongjo',serif;font-size:22px;font-weight:800}
.footer-desc{font-size:12.5px;color:#b7b1a3;margin-top:6px}
.footer-note p{font-size:12px;color:#b7b1a3;line-height:1.7;margin:0 0 8px}

/* 맨 위로 */
.to-top{position:fixed;right:18px;bottom:18px;width:42px;height:42px;
  border:none;border-radius:50%;background:var(--ink);color:#fff;cursor:pointer;
  font-size:14px;box-shadow:0 2px 10px rgba(0,0,0,.25);z-index:30}
.to-top:hover{background:var(--red)}

@media print{
  .ticker,.section-nav,.to-top{display:none}
  body{background:#fff}
}
"""


def main() -> int:
    ref = now_kst()
    print(f"== 이티에스 산업신문 생성 시작 {ref.isoformat()} ==")

    sections_data: list[tuple[dict, list[dict]]] = []
    for section in SECTIONS:
        print(f"[{section['name']}]")
        arts = collect_section(section, ref)
        if not arts:
            print("  → 수집 0건, 플레이스홀더 사용")
            arts = placeholder_articles(section)
        sections_data.append((section, arts))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    html_out = build_html(sections_data, ref)
    (OUT_DIR / "index.html").write_text(html_out, encoding="utf-8")

    # JSON 아카이브
    json_payload = {
        "generated_at": ref.isoformat(),
        "paper": SITE["paper_name"],
        "sections": [
            {
                "id": s["id"],
                "name": s["name"],
                "articles": [
                    {
                        "title": a["title"],
                        "link": a["link"],
                        "source": a["source"],
                        "published": a["published"].isoformat()
                        if a.get("published")
                        else None,
                        "placeholder": bool(a.get("placeholder")),
                    }
                    for a in arts
                ],
            }
            for s, arts in sections_data
        ],
    }
    (DATA_DIR / "news.json").write_text(
        json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    total = sum(
        len([a for a in arts if not a.get("placeholder")]) for _, arts in sections_data
    )
    print(f"== 완료: 실기사 {total}건, index.html 생성 ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
