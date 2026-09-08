#!/usr/bin/env python3
"""
이티에스 산업 브리핑 — 무료 자동 수집기 (GitHub Actions에서 매일 실행, 과금·API 키·사람 개입 없음)

수집원(3종, 모두 무료):
  1) 언론사 직접 RSS(원문 링크·요약·날짜 포함)  → 섹션 키워드로 필터
  2) Google News RSS 검색(한/영)                   → 링크 해독 후 원문 추출
  3) Bing News RSS 검색(한/영)                     → 원문 링크 직접 제공

각 기사: 제목 · 원문 리드 문단(첫 3~5문장) 또는 RSS 요약 · 매체 · 보도일 · URL
주관적 판단 없음. 최근 7일치와 제목/URL 중복 제외. 오늘 파일이 있으면 아무것도 하지 않음.
"""
from __future__ import annotations

import base64
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

# 언론사 직접 RSS (없는 주소는 자동으로 건너뜀)
PUBLISHER_FEEDS = [
    "https://www.hankyung.com/feed/industry", "https://www.hankyung.com/feed/economy",
    "https://www.yna.co.kr/rss/industry.xml", "https://www.yna.co.kr/rss/economy.xml",
    "https://www.mk.co.kr/rss/30100041/", "https://www.mk.co.kr/rss/50200011/",
    "https://rss.etnews.com/Section901.xml", "https://rss.etnews.com/Section902.xml",
    "https://www.thelec.kr/rss/allArticle.xml", "https://www.industrynews.co.kr/rss/allArticle.xml",
    "https://www.batterynews.co.kr/rss/allArticle.xml", "https://www.hellot.net/rss/allArticle.xml",
    "https://www.newspim.com/rss/newspim_all.xml", "https://rss.edaily.co.kr/edaily_news.xml",
    "https://www.mt.co.kr/rss/mt_news.xml", "https://www.sedaily.com/RSS/S1N1.xml",
    "https://www.ddaily.co.kr/rss/S1N1.xml", "https://www.fnnews.com/rss/fnnews_economy.xml",
]

FRESH_HOURS = 48
FALLBACK_DAYS = 21
MAX_ARTICLE_FETCH = 60
MAX_QUERIES_PER_SECTION = 6
MAX_ENTRIES_PER_FEED = 12
MIN_BODY = 60

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
    return NUM_RE.sub(r"<b>\1</b>", html.escape(text, quote=False))

# 기사 본문에 섞여 들어오는 안내문·홍보문·구독 유도·주가 티커 문장 (걸리면 그 문장만 제거)
BOILERPLATE = re.compile(
    r"(Google 검색에서|구글 검색에서|더 자주 볼 수 있습니다|더 궁금한 점|앨리스가|AI가 요약|"
    r"클릭하세요|클릭하시면|구독하기|구독하세요|뉴스레터|카카오톡 채널|채널 추가|"
    r"무단 전재|무단전재|재배포 금지|저작권자|Copyright|ⓒ|©|"
    r"기사 제보|제보는|광고문의|광고 문의|"
    r"관련 기사|관련기사|기사 원문|원문 보기|사진=|사진 =|\[사진|"
    r"기자\s*=|기자입니다|"
    r"\d{1,3}(,\d{3})+원\s*[▲▼]|"
    r"로그인|회원가입|공유하기|스크랩|글자 크기|글씨 크기)"
)

def sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[다요음임됨함\.\!\?])\s+(?=[\"'“‘\(\[A-Z0-9가-힣])", text)
    return [p.strip() for p in parts if len(p.strip()) >= 12 and not BOILERPLATE.search(p)]

def host(u: str) -> str:
    return urllib.parse.urlparse(u).netloc.replace("www.", "")

# ----------------------------------------------------------------- 피드
def fetch_feed(url: str):
    try:
        r = SESSION.get(url, timeout=(5, 12))
        if r.status_code != 200 or not r.content:
            return []
        return feedparser.parse(r.content).entries
    except Exception:
        return []

def entry_to_item(e, origin: str) -> dict | None:
    title, src_t = split_title_source(e.get("title", ""))
    if not title:
        return None
    src = ""
    if isinstance(e.get("source"), dict):
        src = clean(e["source"].get("title", ""))
    link = e.get("link", "")
    return {"title": title, "link": link, "source": src or src_t or host(link),
            "published": to_dt(e), "summary": clean(e.get("summary", "") or e.get("description", ""))[:700],
            "origin": origin}

_PUB_CACHE: list[dict] | None = None
def publisher_items() -> list[dict]:
    global _PUB_CACHE
    if _PUB_CACHE is None:
        items, ok = [], 0
        for u in PUBLISHER_FEEDS:
            ents = fetch_feed(u)
            if ents:
                ok += 1
            for e in ents[:80]:
                it = entry_to_item(e, "pub")
                if it:
                    items.append(it)
        print(f"  · 언론사 RSS {ok}/{len(PUBLISHER_FEEDS)}개 응답, 기사 {len(items)}건")
        _PUB_CACHE = items
    return _PUB_CACHE

def search(query: str, lang: str) -> list[dict]:
    q = urllib.parse.quote(query)
    urls = [(GN_KO.format(q=q), "gnews"), (BING.format(q=q, mkt="ko-KR"), "bing")] if lang == "ko" \
        else [(GN_EN.format(q=q), "gnews"), (BING.format(q=q, mkt="en-US"), "bing")]
    out = []
    for u, origin in urls:
        for e in fetch_feed(u)[:MAX_ENTRIES_PER_FEED]:
            it = entry_to_item(e, origin)
            if it:
                out.append(it)
    return out

# ----------------------------------------------------------------- 원문 URL·본문
def decode_gnews(link: str) -> str | None:
    """news.google.com/rss/articles/<id> → 실제 기사 URL (구형 base64 / 신형 batchexecute)."""
    try:
        p = urllib.parse.urlparse(link)
        if "news.google.com" not in p.netloc:
            return None
        parts = [x for x in p.path.split("/") if x]
        if "articles" not in parts:
            return None
        gid = parts[parts.index("articles") + 1]
        try:
            raw = base64.urlsafe_b64decode(gid + "=" * (-len(gid) % 4))
            m = re.search(rb"https?://[^\x00-\x20\"']+", raw)
            if m:
                u = m.group(0).decode("utf-8", "ignore")
                if "google.com" not in u:
                    return u
        except Exception:
            pass
        r = SESSION.get(link, timeout=(5, 10))
        m_au = re.search(r'data-n-au="([^"]+)"', r.text)
        if m_au:
            return html.unescape(m_au.group(1))
        sg = re.search(r'data-n-a-sg="([^"]+)"', r.text)
        ts = re.search(r'data-n-a-ts="([^"]+)"', r.text)
        if not (sg and ts):
            return None
        inner = ("[\"garturlreq\",[[\"en-US\",\"US\",[\"FINANCE_TOP_INDICES\",\"WEB_TEST_1_0_0\"],null,null,1,1,"
                 "\"US:en\",null,180,null,null,null,null,null,0,null,null,[1608992183,723341000]],\"en-US\",\"US\",1,"
                 f"[2,3,4,8],1,0,\"655000234\",0,0,null,0],\"{gid}\",{int(ts.group(1))},\"{sg.group(1)}\"]")
        payload = json.dumps([[["Fbv4je", inner, None, "generic"]]])
        resp = SESSION.post("https://news.google.com/_/DotsSplashUi/data/batchexecute",
                            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                                     "Referer": "https://news.google.com/"},
                            data="f.req=" + urllib.parse.quote(payload), timeout=(5, 12))
        try:
            chunk = resp.text.split("\n\n")[1]
            outer = json.loads(chunk)
            for row in outer:
                if isinstance(row, list) and len(row) > 2 and isinstance(row[2], str):
                    dec = json.loads(row[2])
                    if isinstance(dec, list) and len(dec) > 1 and isinstance(dec[1], str) and dec[1].startswith("http"):
                        return dec[1]
        except Exception:
            pass
        m = re.search(r'https?://(?!news\.google)[^"\\\s\]]+', resp.text.replace("\\/", "/"))
        return m.group(0) if m else None
    except Exception:
        return None

def resolve_url(link: str) -> str:
    try:
        p = urllib.parse.urlparse(link)
        if "bing.com" in p.netloc:
            qs = urllib.parse.parse_qs(p.query)
            if qs.get("url"):
                return qs["url"][0]
        if "news.google.com" in p.netloc:
            real = decode_gnews(link)
            return real or link
        return link
    except Exception:
        return link

BODY_SELECTORS = [
    "article", "#articleBody", "#article-view-content-div", ".article_body", ".article-body",
    "#articeBody", "#newsEndContents", ".news_view", ".article_txt", "#article_body", ".article-view-content",
    "#dic_area", ".news-article-body", "#news_body_area", ".view_con", "#CmAdContent", ".article-content",
]

def extract_lead(url: str) -> tuple[str, str]:
    try:
        r = SESSION.get(url, timeout=(5, 10), allow_redirects=True)
        if r.status_code != 200 or not r.text:
            return "", url
        soup = BeautifulSoup(r.text, "lxml")
        for t in soup(["script", "style", "nav", "header", "footer", "aside", "figure", "iframe", "noscript"]):
            t.decompose()
        node = None
        for sel in BODY_SELECTORS:
            cand = soup.select_one(sel)
            if cand and len(cand.get_text(" ", strip=True)) > 300:
                node = cand
                break
        paras = [p.get_text(" ", strip=True) for p in (node or soup).find_all("p")]
        paras = [p for p in paras if len(p) >= 30 and "기자" not in p[:12] and "©" not in p and "무단" not in p and "저작권" not in p]
        text = " ".join(paras) if paras else (node.get_text(" ", strip=True) if node else "")
        text = re.sub(r"^\[[^\]]{2,25}\]\s*", "", text)
        text = re.sub(r"^[가-힣A-Za-z\s]{2,15}기자\s*=\s*", "", text)
        lead, total = [], 0
        for s in sentences(text):
            lead.append(s); total += len(s)
            if (len(lead) >= 3 and total >= 180) or len(lead) >= 5 or total >= 420:
                break
        body = " ".join(lead).strip()
        return (body if len(body) >= MIN_BODY else ""), r.url
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

def section_terms(sec: dict) -> list[str]:
    names = (sec.get("companies") or []) + (sec.get("companies_filling") or []) + (sec.get("companies_line") or []) \
            + (sec.get("keywords") or []) + (sec.get("sites") or [])
    return [n.split("(")[0].strip() for n in names if n and len(n.split("(")[0].strip()) >= 2]

def section_queries(sec: dict) -> list[tuple[str, str]]:
    watch = sec.get("watch") or []
    names = (sec.get("companies") or []) + (sec.get("companies_filling") or []) + (sec.get("companies_line") or []) + (sec.get("keywords") or [])
    qs: list[tuple[str, str]] = []
    for n in names[:MAX_QUERIES_PER_SECTION]:
        w = " ".join(watch[:2]) if watch else ""
        is_en = bool(re.fullmatch(r"[A-Za-z0-9 \-\(\)\.]+", n)) and sec.get("type") in ("global", "policy")
        qs.append((f"{n} {w}".strip(), "en" if is_en else "ko"))
    return qs

def entity_of(sec: dict, text: str) -> str:
    low = text.lower()
    for key in section_terms(sec):
        if key.lower() in low:
            return key
    return sec.get("title", "")

def matches_section(sec: dict, it: dict) -> bool:
    hay = f"{it['title']} {it['summary']}".lower()
    return any(t.lower() in hay for t in section_terms(sec))

def collect_section(sec: dict, rules: dict, seen_titles: set, seen_urls: set, budget: dict) -> list[dict]:
    now = now_kst()
    lim = rules.get("items_per_section", {}) if isinstance(rules, dict) else {}
    mn, mx = int(lim.get("min", 3)), int(lim.get("max", 8))

    pool: dict[str, dict] = {}
    # 1) 언론사 RSS(키워드 필터) 2) 검색 RSS
    for it in publisher_items():
        if matches_section(sec, it):
            k = norm_title(it["title"])
            if k and k not in pool and k not in seen_titles:
                pool[k] = it
    for q, lang in section_queries(sec):
        for it in search(q, lang):
            k = norm_title(it["title"])
            if k and k not in pool and k not in seen_titles:
                pool[k] = it

    cands = list(pool.values())
    for it in cands:
        if it["published"] is None:
            it["published"] = now - timedelta(hours=FRESH_HOURS - 1)   # 날짜 없으면 최근으로 간주
    fresh = [e for e in cands if (now - e["published"]) <= timedelta(hours=FRESH_HOURS)]
    if len(fresh) < mn:
        fresh = [e for e in cands if (now - e["published"]) <= timedelta(days=FALLBACK_DAYS)]
    # 원문 링크가 확실한 것(언론사·Bing) 우선, 그다음 최신순
    fresh.sort(key=lambda e: (e["origin"] == "gnews", -e["published"].timestamp()))

    stats = {"pub": 0, "bing": 0, "gnews": 0, "extracted": 0, "summary": 0, "skipped": 0}
    items = []
    for e in fresh:
        if len(items) >= mx or budget["fetch"] <= 0:
            break
        budget["fetch"] -= 1
        url = resolve_url(e["link"])
        if url.split("?")[0] in seen_urls:
            continue
        body, final = ("", url)
        if "news.google.com" not in host(url):
            body, final = extract_lead(url)
        if body:
            stats["extracted"] += 1
        elif len(e["summary"]) >= MIN_BODY:
            body = e["summary"]; stats["summary"] += 1
        else:
            stats["skipped"] += 1
            continue
        stats[e["origin"]] = stats.get(e["origin"], 0) + 1
        items.append({
            "h": html.escape(e["title"], quote=False),
            "b": highlight(body),
            "src": e["source"] or host(final),
            "url": final if "news.google.com" not in host(final) else e["link"],
            "company": entity_of(sec, f"{e['title']} {body}"),
            "date": e["published"].strftime("%Y-%m-%d"),
        })
        seen_titles.add(norm_title(e["title"])); seen_urls.add(final.split("?")[0])
        time.sleep(0.2)
    print(f"  · {sec.get('title')}: 후보 {len(cands)}(최근 {len(fresh)}) → 게재 {len(items)} "
          f"[원문추출 {stats['extracted']}, 요약사용 {stats['summary']}, 제외 {stats['skipped']} | 언론사 {stats['pub']}, bing {stats['bing']}, gnews {stats['gnews']}]")
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
        cards.append({"id": sec.get("id"), "accent": sec.get("accent", "slate"), "icon": sec.get("icon", "•"),
                      "title": sec.get("title", ""), "subtitle": sec.get("subtitle", ""),
                      "full": bool(sec.get("full", False)), "items": items})

    if total < 3:
        print(f"수집 결과가 너무 적어({total}건) 오늘 파일을 만들지 않습니다.", file=sys.stderr)
        return 1

    heads = [c["items"][0]["h"] for c in cards if c["items"]][:6]
    summary = " · ".join(re.sub(r"<[^>]+>", "", h)[:28] for h in heads)
    srcs = sorted({it["src"] for c in cards for it in c["items"] if it.get("src")})
    data = {"date": today, "weekday": wd, "edition": "조간", "summary": summary, "cards": cards,
            "sources": "출처: " + "·".join(srcs[:14]) + " 등. 제목을 누르면 원문으로 이동합니다.",
            "note": "본 브리핑은 공개 보도의 원문 리드 문단(또는 요약)을 자동 추출·정리한 사실 정보이며, 수치·계약 세부는 원문/공시로 최종 확인하시기 바랍니다."}
    DATA.mkdir(exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장 {out.name} · 섹션 {len(cards)}개 · 아이템 {total}건")
    return 0

if __name__ == "__main__":
    sys.exit(main())
