#!/usr/bin/env python3
"""
이티에스 산업 브리핑 — 무료 자동 수집기 (GitHub Actions에서 매일 실행, 과금·API 키·사람 개입 없음)

watchlist.yml 의 섹션별 키워드로 뉴스 검색(RSS: Google News·Bing News, 한/영) →
기사 원문에서 리드 문단(첫 3~5문장)을 추출 → 사실 그대로 정리 → data/<오늘>.json

- 주관적 판단 없음: 제목·원문 리드 문단·매체·보도일·URL 만 기록
- 최근 7일치와 중복(제목/URL)되는 기사는 제외
- 오늘 파일이 이미 있으면 아무것도 하지 않음(멱등)
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
WATCHLIST = ROOT / "watchlist.yml"
KST = timezone(timedelta(hours=9))
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}
GN_KO = "https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
GN_EN = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
BING = "https://www.bing.com/news/search?q={q}&format=rss&mkt={mkt}"

FRESH_HOURS = 48          # 우선 수집 범위
FALLBACK_DAYS = 7         # 부족할 때 확장 범위
MAX_ARTICLE_FETCH = 70    # 원문 추출 시도 상한(실행 시간 보호)

SESSION = requests.Session()
SESSION.headers.update(UA)

# ----------------------------------------------------------------- 유틸
def now_kst() -> datetime:
    return datetime.now(tz=KST)

def norm_title(t: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", (t or "").lower())[:40]

def clean(s: str) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()

def split_title_source(raw: str) -> tuple[str, str]:
    raw = clean(raw)
    if " - " in raw:
        head, _, tail = raw.rpartition(" - ")
        if head and len(tail) <= 30:
            return head.strip(), tail.strip()
    return raw, ""

def to_dt(entry) -> datetime | None:
    st = entry.get("published_parsed") or entry.get("updated_parsed")
    if not st:
        return None
    try:
        return datetime(*st[:6], tzinfo=timezone.utc).astimezone(KST)
    except Exception:
        return None

NUM_RE = re.compile(r"(\d[\d,\.]*\s?(?:조|억|만|천|GWh|MWh|kWh|Wh|%|달러|유로|원|배|년|개월|건|개|톤|대|GW|MW|억원|만원|명))")

def highlight(text: str) -> str:
    text = html.escape(text, quote=False)
    return NUM_RE.sub(r"<b>\1</b>", text)

def sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[다요음임됨함\.\!\?])\s+(?=[\"'“‘\(\[A-Z0-9가-힣])", text)
    return [p.strip() for p in parts if len(p.strip()) >= 12]

# ----------------------------------------------------------------- 검색(RSS)
def fetch_feed(url: str):
    try:
        r = SESSION.get(url, timeout=(5, 12))
        if r.status_code != 200:
            return []
        return feedparser.parse(r.content).entries
    except Exception:
        return []

def search(query: str, lang: str) -> list[dict]:
    q = urllib.parse.quote(query)
    urls = [GN_KO.format(q=q), BING.format(q=q, mkt="ko-KR")] if lang == "ko" else [GN_EN.format(q=q), BING.format(q=q, mkt="en-US")]
    out = []
    for u in urls:
        for e in fetch_feed(u)[:15]:
            title, src_t = split_title_source(e.get("title", ""))
            if not title:
                continue
            src = ""
            if isinstance(e.get("source"), dict):
                src = clean(e["source"].get("title", ""))
            out.append({
                "title": title, "link": e.get("link", ""), "source": src or src_t,
                "published": to_dt(e), "summary": clean(e.get("summary", ""))[:600],
            })
    return out

# ----------------------------------------------------------------- 원문 URL·본문
def resolve_url(link: str) -> str:
    """Google/Bing 중간 링크를 실제 기사 URL로."""
    try:
        p = urllib.parse.urlparse(link)
        if "bing.com" in p.netloc:
            qs = urllib.parse.parse_qs(p.query)
            if qs.get("url"):
                return qs["url"][0]
        r = SESSION.get(link, timeout=(5, 10), allow_redirects=True)
        final = r.url
        if "news.google.com" in urllib.parse.urlparse(final).netloc:
            m = re.search(r'data-n-au="([^"]+)"', r.text) or re.search(r'<a[^>]+href="(https?://(?!news\.google)[^"]+)"', r.text)
            if m:
                return html.unescape(m.group(1))
        return final
    except Exception:
        return link

BODY_SELECTORS = [
    "article", "#articleBody", "#article-view-content-div", ".article_body", ".article-body",
    "#articeBody", "#newsEndContents", ".news_view", ".article_txt", "#article_body", ".article-view-content",
    "#dic_area", ".news-article-body", "#news_body_area", ".view_con", "#CmAdContent",
]

def extract_lead(url: str) -> tuple[str, str]:
    """기사 원문에서 리드 문단(3~5문장)과 최종 URL 반환. 실패 시 빈 문자열."""
    try:
        r = SESSION.get(url, timeout=(5, 10), allow_redirects=True)
        if r.status_code != 200 or not r.text:
            return "", url
        soup = BeautifulSoup(r.text, "lxml")
        for t in soup(["script", "style", "nav", "header", "footer", "aside", "figure", "iframe", "noscript"]):
            t.decompose()
        node = None
        for sel in BODY_SELECTORS:
            node = soup.select_one(sel)
            if node and len(node.get_text(" ", strip=True)) > 300:
                break
            node = None
        paras = [p.get_text(" ", strip=True) for p in (node or soup).find_all("p")]
        paras = [p for p in paras if len(p) >= 30 and "기자" not in p[:12] and "©" not in p and "무단" not in p]
        text = " ".join(paras) if paras else (node.get_text(" ", strip=True) if node else "")
        text = re.sub(r"^\[[^\]]{2,25}\]\s*", "", text)               # [서울=뉴스핌]
        text = re.sub(r"^[가-힣A-Za-z\s]{2,15}기자\s*=\s*", "", text)   # 홍길동 기자 =
        sents = sentences(text)
        lead, total = [], 0
        for s in sents:
            lead.append(s); total += len(s)
            if len(lead) >= 3 and total >= 180 or len(lead) >= 5 or total >= 420:
                break
        body = " ".join(lead).strip()
        return (body if len(body) >= 80 else ""), r.url
    except Exception:
        return "", url

# ----------------------------------------------------------------- 수집 본체
def load_recent_keys(days: int = 7) -> tuple[set, set]:
    titles, urls = set(), set()
    for f in sorted(DATA.glob("*.json"), reverse=True)[:days]:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for c in d.get("cards", []):
            for it in c.get("items", []):
                titles.add(norm_title(it.get("h", "")))
                if it.get("url"):
                    urls.add(it["url"].split("?")[0])
    return titles, urls

def section_queries(sec: dict) -> list[tuple[str, str]]:
    watch = sec.get("watch") or []
    names = (sec.get("companies") or []) + (sec.get("companies_filling") or []) + (sec.get("companies_line") or []) \
            + (sec.get("keywords") or [])
    qs: list[tuple[str, str]] = []
    for n in names[:12]:
        w = " OR ".join(watch[:3]) if watch else ""
        qs.append((f"{n} {w}".strip(), "en" if re.fullmatch(r"[A-Za-z0-9 \-\(\)\.]+", n) and sec.get("type") in ("global", "policy") else "ko"))
    if sec.get("type") in ("global",):
        for n in names[:4]:
            qs.append((f"{n} battery plant OR gigafactory OR investment", "en"))
    return qs[:16]

def entity_of(sec: dict, title: str, body: str) -> str:
    hay = f"{title} {body}"
    for n in (sec.get("companies") or []) + (sec.get("companies_filling") or []) + (sec.get("companies_line") or []) + (sec.get("keywords") or []):
        key = n.split("(")[0].strip()
        if key and key.lower() in hay.lower():
            return key
    return sec.get("title", "")

def collect_section(sec: dict, rules: dict, seen_titles: set, seen_urls: set, budget: dict) -> list[dict]:
    now = now_kst()
    lim = rules.get("items_per_section", {}) if isinstance(rules, dict) else {}
    mn, mx = int(lim.get("min", 3)), int(lim.get("max", 8))
    pool: dict[str, dict] = {}
    for q, lang in section_queries(sec):
        for e in search(q, lang):
            k = norm_title(e["title"])
            if not k or k in pool or k in seen_titles:
                continue
            pool[k] = e
    cands = list(pool.values())
    fresh = [e for e in cands if e["published"] and (now - e["published"]) <= timedelta(hours=FRESH_HOURS)]
    if len(fresh) < mn:
        fresh = [e for e in cands if e["published"] and (now - e["published"]) <= timedelta(days=FALLBACK_DAYS)]
    fresh.sort(key=lambda e: e["published"], reverse=True)

    items = []
    for e in fresh:
        if len(items) >= mx or budget["fetch"] <= 0:
            break
        budget["fetch"] -= 1
        url = resolve_url(e["link"])
        if url.split("?")[0] in seen_urls:
            continue
        body, final = extract_lead(url)
        if not body:
            body = e["summary"] if len(e["summary"]) >= 80 else ""
        if not body:
            continue
        items.append({
            "h": html.escape(e["title"], quote=False),
            "b": highlight(body),
            "src": e["source"] or urllib.parse.urlparse(final).netloc.replace("www.", ""),
            "url": final,
            "company": entity_of(sec, e["title"], body),
            "date": e["published"].strftime("%Y-%m-%d"),
        })
        seen_titles.add(norm_title(e["title"])); seen_urls.add(final.split("?")[0])
        time.sleep(0.3)
    print(f"  · {sec.get('title')}: 후보 {len(cands)} → 게재 {len(items)}")
    return items

def main() -> int:
    now = now_kst()
    today, wd = now.strftime("%Y-%m-%d"), WEEKDAYS[now.weekday()]
    out = DATA / f"{today}.json"
    if out.exists():
        print(f"이미 생성됨: {out.name}"); return 0

    wl = yaml.safe_load(WATCHLIST.read_text(encoding="utf-8")) or {}
    rules = wl.get("rules") or {}
    seen_titles, seen_urls = load_recent_keys()
    budget = {"fetch": MAX_ARTICLE_FETCH}

    cards, total = [], 0
    for sec in wl.get("sections", []):
        if not sec.get("enabled", True):
            continue
        items = collect_section(sec, rules, seen_titles, seen_urls, budget)
        total += len(items)
        cards.append({
            "id": sec.get("id"), "accent": sec.get("accent", "slate"), "icon": sec.get("icon", "•"),
            "title": sec.get("title", ""), "subtitle": sec.get("subtitle", ""),
            "full": bool(sec.get("full", False)), "items": items,
        })

    if total < 3:
        print(f"수집 결과가 너무 적어({total}건) 오늘 파일을 만들지 않습니다.", file=sys.stderr)
        return 1

    heads = [c["items"][0]["h"] for c in cards if c["items"]][:6]
    summary = " · ".join(re.sub(r"<[^>]+>", "", h)[:28] for h in heads)
    srcs = sorted({it["src"] for c in cards for it in c["items"] if it.get("src")})
    data = {
        "date": today, "weekday": wd, "edition": "조간", "summary": summary, "cards": cards,
        "sources": "출처: " + "·".join(srcs[:14]) + " 등. 제목을 누르면 원문으로 이동합니다.",
        "note": "본 브리핑은 공개 보도의 원문 리드 문단을 자동 추출·정리한 사실 정보이며, 수치·계약 세부는 원문/공시로 최종 확인하시기 바랍니다.",
    }
    DATA.mkdir(exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장 {out.name} · 섹션 {len(cards)}개 · 아이템 {total}건")
    return 0

if __name__ == "__main__":
    sys.exit(main())
