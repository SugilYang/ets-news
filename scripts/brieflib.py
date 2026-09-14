#!/usr/bin/env python3
"""
이티에스 영업 브리핑 — 분류·등급·사안 기억 공통 라이브러리 (표준 라이브러리 + PyYAML 만 사용)

collect.py(매일 수집), migrate_v4.py(구 데이터 변환), render.py(지면 생성)가 함께 씁니다.
모든 판정은 watchlist.yml 의 규칙표를 그대로 적용한 결과이며 별도의 주관적 판단은 없습니다.
"""
from __future__ import annotations

import html
import json
import re
import urllib.parse
from datetime import date as _date, datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST = ROOT / "watchlist.yml"
DB_DIR = ROOT / "db"
TOPICS = DB_DIR / "topics.json"
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


# ----------------------------------------------------------------- 설정
def load_watchlist() -> dict:
    return yaml.safe_load(WATCHLIST.read_text(encoding="utf-8")) or {}


# ----------------------------------------------------------------- 문자열
def strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s or ""))


def norm_title(t: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", (t or "").lower())[:40]


def tokens(text: str) -> set[str]:
    """제목 비교용 토큰(2자 이상 한글/영문/숫자 덩어리, 소문자)."""
    out = set()
    for w in re.findall(r"[0-9A-Za-z가-힣]+", strip_tags(text).lower()):
        if len(w) >= 2:
            out.add(w)
    return out


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def host(u: str) -> str:
    try:
        return urllib.parse.urlparse(u).netloc.lower().replace("www.", "")
    except Exception:
        return ""


NUM_RE = re.compile(
    r"(\d[\d,\.]*\s?(?:조|억|만|천|GWh|MWh|kWh|Wh|%|달러|유로|원|배|년|개월|건|개|톤|대|GW|MW|억원|만원|명|ppm|만대|만톤|kW))"
)


def highlight(text: str) -> str:
    """숫자+단위를 <b>로 감쌈(이미 태그가 있으면 제거 후 다시)."""
    return NUM_RE.sub(r"<b>\1</b>", html.escape(strip_tags(text), quote=False))


def numbers_of(text: str) -> set[str]:
    """변경 감지용 수치 집합(공백 제거)."""
    t = strip_tags(text)
    out = set(re.sub(r"\s", "", m) for m in NUM_RE.findall(t))
    for m in re.findall(r"\$\s?\d[\d,\.]*\s?(?:billion|million|bn|m)\b", t, flags=re.I):
        out.add(re.sub(r"\s", "", m.lower()))
    for m in re.findall(r"\b\d{4}년|\b\d{1,2}월\s?\d{1,2}일|\b20\d\d\b|\bQ[1-4]\b|\b[1-4]분기", t):
        out.add(re.sub(r"\s", "", m))
    return out


def krw_100m(text: str) -> float:
    """본문에서 가장 큰 금액을 억원 단위로 추정(조/억/달러). 없으면 0."""
    t = strip_tags(text).replace(",", "")
    best = 0.0
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*조(?:\s*(\d+(?:\.\d+)?)\s*억)?", t):
        v = float(m.group(1)) * 10000 + (float(m.group(2)) if m.group(2) else 0)
        best = max(best, v)
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*억", t):
        best = max(best, float(m.group(1)))
    for m in re.finditer(r"\$\s?(\d+(?:\.\d+)?)\s*(billion|bn|million|m)\b", t, flags=re.I):
        v = float(m.group(1)) * (14000 if m.group(2).lower() in ("billion", "bn") else 14)
        best = max(best, v)
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(billion|million)\s*(?:won|dollars|USD|euros?)", t, flags=re.I):
        v = float(m.group(1)) * (14000 if m.group(2).lower() == "billion" else 14)
        best = max(best, v)
    return best


# ----------------------------------------------------------------- 문장·브리프
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
    text = re.sub(r"\s+", " ", strip_tags(text)).strip()
    text = re.sub(r"^\[[^\]]{2,30}\]\s*", "", text)                     # [매체명 = 기자] 접두어
    text = re.sub(r"^[가-힣A-Za-z\s]{2,15}기자\s*=\s*", "", text)          # 홍길동 기자 =
    text = re.sub(r"(?<=[가-힣]다\.)(?=[가-힣\"'“‘\(])", " ", text)       # '…했다.다음' 붙은 문장 분리
    parts = re.split(r"(?<=[다요음임됨함\.\!\?])\s+(?=[\"'“‘\(\[A-Z0-9가-힣])", text)
    return [p.strip() for p in parts if len(p.strip()) >= 12 and not BOILERPLATE.search(p)]


def make_brief(text: str, n_sent: int = 2, max_chars: int = 170) -> str:
    """1~2문장 브리프: 첫 문장 + (수치가 있는 다음 문장). 문장 경계에서만 끊고, 너무 길면 단어 경계에서 자름."""
    ss = sentences(text)
    if not ss:
        return ""
    slack = max_chars + 40
    first = ss[0]
    if len(first) > slack:
        return first[:max_chars].rsplit(" ", 1)[0].rstrip(",·;:") + "…"
    out = [first]
    if n_sent >= 2 and len(ss) > 1:
        pick = next((s for s in ss[1:4] if NUM_RE.search(s)), ss[1])
        if len(first) + 1 + len(pick) <= slack:
            out.append(pick)
    return " ".join(out)


# ----------------------------------------------------------------- 엔티티·분류
class Classifier:
    def __init__(self, wl: dict):
        self.wl = wl
        self.customers = wl.get("customers") or []
        self.competitors = wl.get("competitors") or []
        self.cats = {c["id"]: c for c in (wl.get("categories") or []) if c.get("enabled", True)}
        self.cat_order = [c["id"] for c in sorted((wl.get("categories") or []), key=lambda c: c.get("order", 99)) if c.get("enabled", True)]
        self.tags = wl.get("tags") or {}
        imp = wl.get("importance") or {}
        self.A = imp.get("A") or {}
        self.B = imp.get("B") or {}
        self.rel = {int(k): [d.lower() for d in v] for k, v in (wl.get("reliability") or {}).items()}
        self._ent_patterns = self._build_entities()

    # 이름·별칭 → 정규식 (짧은 영문 약어는 단어 경계 필수)
    def _build_entities(self):
        pats = []
        for kind, lst in (("customer", self.customers), ("competitor", self.competitors)):
            for e in lst:
                names = [e["name"]] + list(e.get("aliases") or [])
                regs = []
                for n in names:
                    n = n.strip()
                    if not n:
                        continue
                    if not re.fullmatch(r"[A-Za-z0-9&\-\+\. ]+", n) and len(n) < 3:
                        continue   # 2글자 한글 별칭은 오탐(인명 등)이 잦아 쓰지 않음
                    esc = re.escape(n)
                    if re.fullmatch(r"[A-Za-z0-9&\-\+\. ]+", n) and len(n) <= 6:
                        regs.append(rf"(?<![A-Za-z0-9]){esc}(?![A-Za-z0-9])")
                    else:
                        regs.append(esc)
                pats.append((kind, e, re.compile("|".join(regs), flags=re.I)))
        return pats

    def entities(self, text: str) -> list[tuple[str, dict]]:
        t = strip_tags(text)
        for bad in self.wl.get("entity_not") or []:      # 이름이 겹치는 다른 회사(SFA반도체 등)는 지우고 판정
            t = t.replace(bad, " ")
        found = []
        for kind, e, rx in self._ent_patterns:
            if rx.search(t):
                found.append((kind, e))
        return found

    @staticmethod
    def _any(terms, text: str) -> list[str]:
        """키워드 포함 여부. 짧은 영문(4자 이하: EV, ESS, SDI…)은 단어 경계를 요구해 오탐(process, less…)을 막음."""
        low = text.lower()
        hit = []
        for k in terms or []:
            kl = str(k).lower().strip()
            if not kl:
                continue
            if re.fullmatch(r"[a-z0-9&\-\+\.]+", kl) and len(kl) <= 4:
                if re.search(rf"(?<![a-z0-9]){re.escape(kl)}(?![a-z0-9])", low):
                    hit.append(k)
            elif kl in low:
                hit.append(k)
        return hit

    def anchored(self, text: str) -> bool:
        """시장·기술/정책 항목은 산업 앵커 단어(배터리·전기차·반도체·AMR…)가 있어야 함."""
        anchors = self.wl.get("anchors") or []
        return not anchors or bool(self._any(anchors, text))

    def tags_of(self, text: str) -> list[str]:
        out = []
        for tag, kws in self.tags.items():
            if self._any(kws, text):
                out.append(tag)
        return out

    def grade(self, text: str) -> str:
        if self._any(self.A.get("any"), text):
            return "A"
        if self._any(self.A.get("money_with"), text) and krw_100m(text) >= float(self.A.get("money_min_krw_100m", 500)):
            return "A"
        if self._any(self.B.get("any"), text):
            return "B"
        return "C"

    def reliability(self, url: str) -> int:
        h = host(url)
        if not h:
            return 2
        for lvl in sorted(self.rel, reverse=True):
            for d in self.rel[lvl]:
                if h == d or h.endswith("." + d):
                    return lvl
        return 2

    def market_group(self, text: str) -> str | None:
        cat = self.cats.get("market") or {}
        best, best_n = None, 0
        for g in cat.get("groups") or []:
            n = len(self._any(g.get("keywords"), text))
            if n > best_n:
                best, best_n = g["id"], n
        return best

    def classify(self, title: str, body: str) -> dict | None:
        """→ {cat, group, entity, related, tags, grade} 또는 None(감시 대상 아님)."""
        text = f"{title} {body}"
        head = title
        if self._any(self.wl.get("exclude_all"), text):          # 정치·부동산 등 무관 기사
            return None
        if self._any(self.wl.get("exclude_title"), head):        # 주식·증권 기사(제목 기준)
            return None
        ents = self.entities(text)
        comp = [e for k, e in ents if k == "competitor"]
        cust = [e for k, e in ents if k == "customer"]
        # 제목에 등장하는 엔티티를 우선
        comp.sort(key=lambda e: 0 if self.entities_in(head, e) else 1)
        cust.sort(key=lambda e: 0 if self.entities_in(head, e) else 1)
        tags = self.tags_of(text)
        grade = self.grade(text)
        proj = self.cats.get("project") or {}
        techpol = self.cats.get("tech_policy") or {}

        if comp and "competitor" in self.cats:
            e = comp[0]
            return {"cat": "competitor", "group": f"grade_{e.get('grade','B')}", "entity": e["name"],
                    "related": [c["name"] for c in cust[:2]], "tags": tags, "grade": grade}
        if cust:
            e = cust[0]
            if "project" in self.cats and self._any(proj.get("signals"), text):
                return {"cat": "project", "group": "all", "entity": e["name"],
                        "related": [c["name"] for c in cust[1:3]], "tags": tags, "grade": grade}
            if "customer" in self.cats:
                grp = "global"
                for g in (self.cats["customer"].get("groups") or []):
                    if e["name"] in (g.get("companies") or []):
                        grp = g["id"]
                        break
                return {"cat": "customer", "group": grp, "entity": e["name"],
                        "related": [c["name"] for c in cust[1:3]], "tags": tags, "grade": grade}
        if self._any(self.wl.get("exclude_market"), head):      # 시장·정책면에서는 증권 시황·ETF·목표가 기사 제외
            return None
        if "tech_policy" in self.cats and self._any(techpol.get("signals"), text) and self.anchored(text):
            mg = self.market_group(text)
            return {"cat": "tech_policy", "group": "all", "entity": "", "related": [], "tags": tags, "grade": grade, "market_group": mg}
        if "market" in self.cats and self.anchored(text):
            mg = self.market_group(text)
            if mg:
                return {"cat": "market", "group": mg, "entity": "", "related": [], "tags": tags, "grade": grade}
        return None

    def entities_in(self, text: str, e: dict) -> bool:
        for kind, ee, rx in self._ent_patterns:
            if ee is e:
                return bool(rx.search(strip_tags(text)))
        return False

    # 지면용 섹션 골격 (카테고리 → 그룹)
    def skeleton(self) -> list[dict]:
        out = []
        for cid in self.cat_order:
            c = self.cats[cid]
            if cid == "competitor":
                groups = [{"id": "grade_A", "title": "A등급 경쟁사"}, {"id": "grade_B", "title": "B등급 경쟁사"}]
            elif c.get("groups"):
                groups = [{"id": g["id"], "title": g["title"]} for g in c["groups"]]
            else:
                groups = [{"id": "all", "title": ""}]
            out.append({"id": cid, "title": c.get("title", cid), "subtitle": c.get("subtitle", ""),
                        "groups": [{"id": g["id"], "title": g["title"], "items": []} for g in groups]})
        return out


# ----------------------------------------------------------------- 사안 기억(30일)
class TopicMemory:
    """db/topics.json — 한 번 실은 사안을 기억. 같은 사안은 수치·일정이 달라질 때만 '후속'."""

    def __init__(self, days: int = 30):
        self.days = days
        self.rows: list[dict] = []
        if TOPICS.exists():
            try:
                self.rows = json.loads(TOPICS.read_text(encoding="utf-8")).get("topics", [])
            except Exception:
                self.rows = []

    def prune(self, today: _date):
        lim = (today - timedelta(days=self.days)).isoformat()
        self.rows = [r for r in self.rows if r.get("date", "") >= lim]

    def find(self, entity: str, cat: str, group: str, title: str, url: str) -> dict | None:
        tk = tokens(title)
        nt = norm_title(title)
        u = (url or "").split("?")[0]
        best, best_s = None, 0.0
        for r in self.rows:
            if u and r.get("url", "").split("?")[0] == u:
                return r
            if nt and r.get("nt") == nt:
                return r
            s = jaccard(tk, set(r.get("tk", [])))
            same_ent = bool(entity) and r.get("entity") == entity
            same_scope = (r.get("cat") == cat and r.get("group") == group)
            thr = 0.30 if same_ent else (0.45 if same_scope else 0.6)
            if s >= thr and s > best_s:
                best, best_s = r, s
        return best

    @staticmethod
    def change(prev: dict, title: str, brief: str) -> list[str]:
        new = numbers_of(f"{title} {brief}")
        old = set(prev.get("nums", []))
        return sorted(new - old, key=lambda x: (len(x), x))

    def remember(self, item: dict, date: str):
        self.rows.append({
            "date": date, "entity": item.get("entity", ""), "cat": item.get("cat", ""), "group": item.get("group", ""),
            "h": strip_tags(item.get("h", ""))[:120], "nt": norm_title(strip_tags(item.get("h", ""))),
            "tk": sorted(tokens(item.get("h", ""))), "nums": sorted(numbers_of(f"{item.get('h','')} {item.get('b','')}")),
            "url": item.get("url", ""),
        })

    def save(self):
        DB_DIR.mkdir(exist_ok=True)
        TOPICS.write_text(json.dumps({"days": self.days, "topics": self.rows}, ensure_ascii=False, indent=1), encoding="utf-8")


# ----------------------------------------------------------------- 날짜·호수
def issue_no(first: str, day: str, holidays: set[str] | None = None) -> int:
    """제1호 날짜부터 평일(공휴일 제외)만 세어 호수 계산."""
    try:
        f = _date.fromisoformat(first); d = _date.fromisoformat(day)
    except Exception:
        return 0
    if d < f:
        return 0
    n, cur = 0, f
    hol = holidays or set()
    while cur <= d:
        if cur.weekday() < 5 and cur.isoformat() not in hol:
            n += 1
        cur += timedelta(days=1)
    return n


def kdate(day: str) -> str:
    """2026-09-15 → 2026년 9월 15일 화요일"""
    try:
        d = _date.fromisoformat(day)
        return f"{d.year}년 {d.month}월 {d.day}일 {WEEKDAYS[d.weekday()]}요일"
    except Exception:
        return day


def week_of(day: str) -> tuple[str, str, str]:
    """→ (ISO 주 라벨 'YYYY-Www', 월요일, 금요일)"""
    d = _date.fromisoformat(day)
    mon = d - timedelta(days=d.weekday())
    fri = mon + timedelta(days=4)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}", mon.isoformat(), fri.isoformat()
