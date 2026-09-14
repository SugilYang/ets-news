#!/usr/bin/env python3
"""
이티에스 영업 브리핑 — 무료 자동 수집기 v3 (GitHub Actions에서 월~금 아침 실행, 과금·API 키·사람 개입 없음)

흐름:  watchlist.yml(고객·경쟁사·키워드·규칙)
       → 언론사/기관 RSS + Google News·Bing News 검색(한/영)
       → 원문 링크 해독 → 리드 문단 추출 → 1~2문장 브리프
       → 카테고리(①시장 ②고객사 ③업계 ④Project ⑤기술/정책) · 등급(A/B/C) · 신뢰도(★) · 태그
       → 사안 기억(db/topics.json, 30일): 이미 실은 사안은 수치·일정이 바뀐 경우에만 '후속'으로 재게재
       → data/<날짜>.json (스키마 v4)

주말·공휴일은 발행하지 않음. 오늘 파일이 있으면 아무것도 하지 않음. 판단 문장 없음(규칙표 결과만 기록).
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
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brieflib as B  # noqa: E402

ROOT = B.ROOT
DATA = ROOT / "data"
KST = timezone(timedelta(hours=9))

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}
GN_KO = "https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
GN_EN = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
BING = "https://www.bing.com/news/search?q={q}&format=rss&mkt={mkt}"

MAX_ARTICLE_FETCH = 110
MAX_ENTRIES_PER_FEED = 10
MIN_BODY = 40

SESSION = requests.Session()
SESSION.headers.update(UA)


# ----------------------------------------------------------------- 유틸
def now_kst() -> datetime:
    return datetime.now(tz=KST)


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


# ----------------------------------------------------------------- 피드
def fetch_feed(url: str):
    try:
        r = SESSION.get(url, timeout=(5, 12))
        if r.status_code != 200 or not r.content:
            return []
        return feedparser.parse(r.content).entries
    except Exception:
        return []


def entry_to_item(e, origin: str, feed_url: str = "") -> dict | None:
    raw = e.get("title", "")
    link = e.get("link", "")
    if "dart.fss.or.kr" in (feed_url + link):
        title, src_t = clean(raw), "DART 공시"
    else:
        title, src_t = split_title_source(raw)
    if not title:
        return None
    src = ""
    if isinstance(e.get("source"), dict):
        src = clean(e["source"].get("title", ""))
    return {"title": title, "link": link, "source": src or src_t or B.host(link),
            "published": to_dt(e), "summary": clean(e.get("summary", "") or e.get("description", ""))[:900],
            "origin": origin}


def feed_items(feeds: list[str]) -> list[dict]:
    items, ok = [], 0
    for u in feeds:
        ents = fetch_feed(u)
        if ents:
            ok += 1
        for e in ents[:120]:
            it = entry_to_item(e, "pub", u)
            if it:
                items.append(it)
    print(f"  · 언론사/기관 RSS {ok}/{len(feeds)}개 응답, 기사 {len(items)}건")
    return items


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
            return decode_gnews(link) or link
        return link
    except Exception:
        return link


BODY_SELECTORS = [
    "article", "#articleBody", "#article-view-content-div", ".article_body", ".article-body",
    "#articeBody", "#newsEndContents", ".news_view", ".article_txt", "#article_body", ".article-view-content",
    "#dic_area", ".news-article-body", "#news_body_area", ".view_con", "#CmAdContent", ".article-content",
]


def extract_lead(url: str) -> tuple[str, str]:
    """→ (본문 앞부분 텍스트, 최종 URL)"""
    try:
        r = SESSION.get(url, timeout=(5, 10), allow_redirects=True)
        if r.status_code != 200 or not r.text:
            return "", url
        soup = BeautifulSoup(r.content, "lxml")   # 바이트로 넘겨 페이지의 charset(EUC-KR 등)을 스스로 읽게 함
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
        if sum(1 for ch in text[:400] if "À" <= ch <= "ÿ") > 20:   # 인코딩 깨짐(ÀÌ±â¼ö…)이면 버림
            return "", r.url
        return text[:1500], r.url
    except Exception:
        return "", url


# ----------------------------------------------------------------- 검색어 생성
def build_queries(wl: dict) -> list[tuple[str, str, str]]:
    """→ [(query, lang, label)]"""
    qs: list[tuple[str, str, str]] = []
    cw = wl.get("customer_watch") or {}
    for c in wl.get("customers") or []:
        lang = c.get("lang", "ko")
        watch = cw.get(lang) or []
        if watch:
            qs.append((f'{c["name"]} ({" OR ".join(watch[:6])})', lang, f'고객 {c["name"]}'))
        if lang == "en" and cw.get("ko"):
            qs.append((f'{c["name"]} ({" OR ".join((cw.get("ko") or [])[:4])})', "ko", f'고객 {c["name"]}(국내보도)'))
    kw = wl.get("competitor_watch") or {}
    for c in wl.get("competitors") or []:
        lang = c.get("lang", "ko")
        watch = kw.get(lang) or []
        qs.append((f'{c["name"]} ({" OR ".join(watch[:4])})' if watch else c["name"], lang, f'경쟁 {c["name"]}'))
        if c.get("grade") == "A" and lang == "ko" and len(c["name"]) >= 3:
            qs.append((c["name"], "ko", f'경쟁 {c["name"]}(전체)'))   # A등급 국내 경쟁사는 회사명만으로도 한 번 더
    mq = wl.get("market_queries") or {}
    for q in mq.get("ko") or []:
        qs.append((q, "ko", f"시장 {q}"))
    for q in mq.get("en") or []:
        qs.append((q, "en", f"시장 {q}"))
    return qs


# ----------------------------------------------------------------- 발행 여부
def should_publish(now: datetime, wl: dict) -> tuple[bool, str]:
    sch = wl.get("schedule") or {}
    today = now.strftime("%Y-%m-%d")
    if sch.get("weekdays_only", True) and now.weekday() >= 5:
        return False, f"{today} 은 주말이라 발행하지 않습니다."
    if today in set(sch.get("holidays") or []):
        return False, f"{today} 은 공휴일이라 발행하지 않습니다."
    return True, ""


def window_hours(now: datetime, wl: dict) -> int:
    sch = wl.get("schedule") or {}
    if now.weekday() == 0:
        return int(sch.get("window_hours_monday", 84))
    return int(sch.get("window_hours", 36))


# ----------------------------------------------------------------- 본체
def main() -> int:
    now = now_kst()
    today = now.strftime("%Y-%m-%d")
    wl = B.load_watchlist()
    ok, why = should_publish(now, wl)
    if not ok:
        print(why); return 0
    out = DATA / f"{today}.json"
    if out.exists():
        print(f"이미 생성됨: {out.name}"); return 0

    rules = wl.get("rules") or {}
    clf = B.Classifier(wl)
    mem = B.TopicMemory(int(rules.get("topic_memory_days", 30)))
    mem.prune(now.date())
    hours = window_hours(now, wl)
    print(f"=== {today} ({B.WEEKDAYS[now.weekday()]}) 수집 시작 · 최근 {hours}시간 · 기억된 사안 {len(mem.rows)}건")

    # 1) 후보 수집
    pool: dict[str, dict] = {}
    seen_nt = {r.get("nt") for r in mem.rows}
    seen_url = {r.get("url", "").split("?")[0] for r in mem.rows}

    def add(it: dict, label: str):
        k = B.norm_title(it["title"])
        if not k or k in pool or k in seen_nt:
            return
        if re.search(r"\d{6}\.(SZ|SS|HK|KS|KQ)\b|\(\d{6}\)|주가 정보|Stock Price|stock quote", it["title"], flags=re.I):
            return   # 종목 시세 페이지
        pre = clf.classify(it["title"], it["summary"])
        if not pre:
            return
        it["pre"] = pre; it["label"] = label
        pool[k] = it

    for it in feed_items(wl.get("feeds") or []):
        add(it, "RSS")
    queries = build_queries(wl)
    print(f"  · 검색어 {len(queries)}개 (Google News + Bing News)")
    for q, lang, label in queries:
        for it in search(q, lang):
            add(it, label)
        time.sleep(0.15)

    cands = list(pool.values())
    for it in cands:
        if it["published"] is None:
            it["published"] = now - timedelta(hours=1)
    fresh = [e for e in cands if (now - e["published"]) <= timedelta(hours=hours)]
    order = {"A": 0, "B": 1, "C": 2}
    fresh.sort(key=lambda e: (order.get(e["pre"]["grade"], 3), e["origin"] == "gnews", -e["published"].timestamp()))
    print(f"  · 후보 {len(cands)}건 → 기간 내 {len(fresh)}건")

    # 2) 원문 확인·브리프·분류·사안 기억
    n_sent = int(rules.get("brief_sentences", 2)); max_chars = int(rules.get("brief_max_chars", 170))
    cap = int(rules.get("items_per_section_max", 12))
    cap_co = int(rules.get("items_per_company_max", 3))
    cap_grp = int(rules.get("items_per_group_max", 3))
    need_change = bool(rules.get("followup_needs_change", True))
    sections = clf.skeleton()
    sec_index = {s["id"]: s for s in sections}
    counts: dict[str, int] = {}
    co_counts: dict[tuple, int] = {}
    stats = {"fetched": 0, "published": 0, "headline_only": 0, "followup": 0, "suppressed": 0, "sameday": 0,
             "nobody": 0, "unclassified": 0, "capped": 0}
    budget = MAX_ARTICLE_FETCH
    seq = 0

    for e in fresh:
        if budget <= 0:
            break
        budget -= 1; stats["fetched"] += 1
        url = resolve_url(e["link"])
        if url.split("?")[0] in seen_url:
            continue
        lead, final = ("", url)
        if "news.google.com" not in B.host(url):
            lead, final = extract_lead(url)
        text = lead if len(lead) >= MIN_BODY else e["summary"]
        brief = B.make_brief(text, n_sent, max_chars)
        nt_b, nt_t = B.norm_title(brief)[:30], B.norm_title(e["title"])[:30]
        if brief and (nt_b == nt_t or nt_b.startswith(nt_t[:20]) and len(brief) < len(e["title"]) + 30):
            brief = ""            # RSS 요약이 제목을 되풀이한 것 → 제목만 싣고 본문은 원문 링크로
        if not brief:
            stats["headline_only"] += 1
        cls = clf.classify(e["title"], f"{brief} {lead[:600]} {e['summary'][:300]}")
        if not cls:
            stats["unclassified"] += 1
            continue
        if (counts.get(cls["cat"], 0) >= cap or co_counts.get((cls["cat"], cls["entity"]), 0) >= (cap_co if cls["entity"] else 10**6)
                or co_counts.get(("grp", cls["cat"], cls["group"]), 0) >= cap_grp):
            stats["capped"] += 1
            continue
        final_url = final if "news.google.com" not in B.host(final) else e["link"]
        item = {
            "id": f"{today}-{seq}",
            "h": html.escape(e["title"], quote=False),
            "b": B.highlight(brief),
            "src": e["source"] or B.host(final_url),
            "url": final_url,
            "date": e["published"].strftime("%Y-%m-%d"),
            "cat": cls["cat"], "group": cls["group"], "entity": cls["entity"], "related": cls["related"],
            "tags": cls["tags"], "grade": cls["grade"], "rel": clf.reliability(final_url),
            "followup": None,
        }
        prev = mem.find(item["entity"], item["cat"], item["group"], e["title"], final_url)
        if prev and prev.get("date") == today:
            stats["sameday"] += 1     # 같은 날 같은 사안의 다른 매체 보도 → 1건만
            continue
        if prev:
            changes = B.TopicMemory.change(prev, e["title"], brief)
            if need_change and not changes:
                stats["suppressed"] += 1
                continue
            item["followup"] = {"prev_date": prev.get("date", ""), "prev_h": prev.get("h", ""),
                                "change": ", ".join(changes[:5])}
            stats["followup"] += 1
        sec = sec_index[cls["cat"]]
        grp = next((g for g in sec["groups"] if g["id"] == cls["group"]), None)
        if grp is None:
            grp = {"id": cls["group"], "title": "", "items": []}; sec["groups"].append(grp)
        grp["items"].append(item)
        counts[cls["cat"]] = counts.get(cls["cat"], 0) + 1
        co_counts[(cls["cat"], cls["entity"])] = co_counts.get((cls["cat"], cls["entity"]), 0) + 1
        co_counts[("grp", cls["cat"], cls["group"])] = co_counts.get(("grp", cls["cat"], cls["group"]), 0) + 1
        mem.remember(item, today)
        seen_nt.add(B.norm_title(e["title"])); seen_url.add(final_url.split("?")[0])
        seq += 1; stats["published"] += 1
        time.sleep(0.2)

    total = stats["published"]
    print(f"  · 원문확인 {stats['fetched']} → 게재 {total} (후속 {stats['followup']}, 제목만 {stats['headline_only']}) | "
          f"미변경 제외 {stats['suppressed']}, 같은날 중복 {stats['sameday']}, 분류불가 {stats['unclassified']}, 건수초과 {stats['capped']}")
    for s in sections:
        n = sum(len(g["items"]) for g in s["groups"])
        print(f"    - {s['title']}: {n}건")

    if total < int(rules.get("min_items_to_publish", 2)):
        print(f"수집 결과가 너무 적어({total}건) 오늘 호를 만들지 않습니다.", file=sys.stderr)
        return 1

    # 3) 1면 톱(A등급 → 신뢰도 → 최신)
    allitems = [it for s in sections for g in s["groups"] for it in g["items"]]
    corder = {cid: i for i, cid in enumerate(clf.cat_order)}
    def topkey(it):   # 카테고리 순서(Project → 고객사 → 업계 …) → 신뢰도 → 최신
        return (corder.get(it["cat"], 9), -it["rel"], -int(it["date"].replace("-", "")))
    tops = sorted([it for it in allitems if it["grade"] == "A" and it["b"]], key=topkey)[:4]
    if not tops:
        tops = sorted([it for it in allitems if it["grade"] == "B" and it["b"]], key=topkey)[:1]
    site = wl.get("site") or {}
    hol = set((wl.get("schedule") or {}).get("holidays") or [])
    first = str(site.get("first_issue_date") or "").strip()
    if not first:   # 비어 있으면 가장 오래된 발행일(없으면 오늘)이 제1호
        older = sorted(f.stem for f in DATA.glob("????-??-??.json"))
        first = older[0] if older else today
    data = {
        "schema": 4,
        "date": today, "weekday": B.WEEKDAYS[now.weekday()],
        "edition": site.get("edition", "조간"),
        "issue_no": B.issue_no(first, today, hol),
        "window_hours": hours,
        "summary": " · ".join(B.strip_tags(it["h"])[:30] for it in tops[:4]),
        "top": [it["id"] for it in tops],
        "sections": sections,
        "stats": stats,
        "sources": sorted({it["src"] for it in allitems if it.get("src")}),
        "note": "공개 보도·공시의 제목과 리드 문장을 규칙표(watchlist.yml)에 따라 자동 분류·등급화한 사실 정보입니다. 수치·계약 세부는 원문/공시로 확인하십시오.",
    }
    DATA.mkdir(exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    mem.save()
    print(f"저장 {out.name} · 제{data['issue_no']}호 · {total}건 · 톱 {len(tops)}건 · 사안 DB {len(mem.rows)}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
