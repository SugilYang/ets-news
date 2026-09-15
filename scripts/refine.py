#!/usr/bin/env python3
"""
Claude 정제 단계 도우미 (Max 예약 세션이 매일 아침 사용)

  python3 scripts/refine.py prepare [날짜]      → 오늘 후보를 읽기 쉬운 텍스트로 출력(Claude가 읽음)
  python3 scripts/refine.py apply  <정제 JSON>   → Claude가 쓴 정제 결과를 data/<날짜>.json 에 반영 + 검증 + 사안 DB 갱신

정제 JSON 형식 (Claude가 작성, db/refined-<날짜>.json):
{
  "date": "2026-09-16",
  "summary": "한 줄 요약(선택)",
  "items": [
    {"cid": 12, "cat": "customer", "group": "lgensol", "entity": "LG에너지솔루션", "grade": "A",
     "tags": ["ESS", "수주"], "h": "제목(원문 제목을 다듬어 40자 이내)", "b": "핵심 한 문장(90자 이내, 수치 포함)",
     "followup": null | {"prev_date": "2026-09-15", "change": "1GW → 1.5GW"}}
  ],
  "top": [12, 3, 7],                      # 1면 후보 cid (1~4개, A등급 우선)
  "guide": [{"cid": 12, "say": "LG에너지솔루션 ESS 3차 입찰 → 셀 라인 증설 여부·주액 장비 수요 확인"}]
}
cat: project | customer | competitor | tech_policy | market
group: customer → lgensol/sdi/skon/global, competitor → grade_A/grade_B, market → ev/battery/semi/fa, 그 외 → all
"""
from __future__ import annotations

import html
import json
import sys
from datetime import date as _date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brieflib as B  # noqa: E402

DATA = B.ROOT / "data"
KST = timezone(timedelta(hours=9))


def today_kst() -> str:
    return datetime.now(tz=KST).strftime("%Y-%m-%d")


def load_cands(day: str) -> dict:
    f = B.DB_DIR / f"candidates-{day}.json"
    if not f.exists():
        raise SystemExit(f"후보 파일 없음: {f}  (GitHub Actions 수집이 아직 안 돌았거나 그날은 발행일이 아님)")
    return json.loads(f.read_text(encoding="utf-8"))


def prepare(day: str) -> None:
    d = load_cands(day)
    cands = d.get("candidates", [])
    wl = B.load_watchlist()
    print(f"# {day} 후보 {len(cands)}건 (수집 창 {d.get('window_hours')}시간)")
    print("# 상태: published=규칙표 게재, capped=건수초과로 미게재, sameday=같은날 중복, unchanged=이미 실린 사안, unclassified=분류불가")
    print("# 카테고리: project | customer(lgensol/sdi/skon/global) | competitor(grade_A/grade_B) | tech_policy | market(ev/battery/semi/fa)")
    print("# 고객사:", ", ".join(c["name"] for c in wl.get("customers") or []))
    print("# 경쟁사:", ", ".join(f'{c["name"]}({c.get("grade","")})' for c in wl.get("competitors") or []))
    print()
    for c in cands:
        pre = c.get("pre") or {}
        print(f"[cid {c['cid']}] {c['title']}")
        print(f"   출처 {c.get('src','')} ★{c.get('rel',2)} {c.get('date','')} | 규칙표: {pre.get('cat','-')}/{pre.get('entity') or '-'}/{pre.get('grade','-')} "
              f"태그 {','.join(pre.get('tags') or [])} | 상태 {c.get('status','')}")
        lead = B.strip_tags(c.get("lead", "")).replace("\n", " ")
        print(f"   본문: {lead[:420]}")
        print(f"   URL: {c.get('url','')}")
        print()


def apply(path: str) -> None:
    ref = json.loads(Path(path).read_text(encoding="utf-8"))
    day = ref.get("date") or today_kst()
    d = load_cands(day)
    cands = {c["cid"]: c for c in d.get("candidates", [])}
    wl = B.load_watchlist()
    clf = B.Classifier(wl)
    rules = wl.get("rules") or {}
    max_chars = int(rules.get("brief_max_chars", 90))
    sections = clf.skeleton()
    idx = {s["id"]: s for s in sections}
    valid_groups = {s["id"]: {g["id"] for g in s["groups"]} for s in sections}
    items, cid_to_id = [], {}
    errors = []
    for n, r in enumerate(ref.get("items", [])):
        cid = r.get("cid")
        if cid not in cands:
            errors.append(f"cid {cid}: 후보에 없음"); continue
        c = cands[cid]
        cat = r.get("cat")
        if cat not in idx:
            errors.append(f"cid {cid}: cat '{cat}' 불명"); continue
        group = r.get("group") or "all"
        if group not in valid_groups[cat]:
            group = next(iter(valid_groups[cat]))
        grade = r.get("grade", "C")
        if grade not in ("A", "B", "C"):
            grade = "C"
        h = B.strip_tags(r.get("h") or c["title"]).strip()
        b = B.strip_tags(r.get("b") or "").strip()
        if len(b) > max_chars + 30:
            b = b[:max_chars + 20].rsplit(" ", 1)[0] + "…"
        fu = r.get("followup")
        if isinstance(fu, dict) and fu.get("prev_date"):
            fu = {"prev_date": fu.get("prev_date", ""), "prev_h": fu.get("prev_h", ""), "change": fu.get("change", "")}
        else:
            fu = None
        item = {
            "id": f"{day}-{n}", "h": html.escape(h, quote=False), "b": B.highlight(b) if b else "",
            "src": c.get("src", ""), "url": c.get("url", ""), "date": c.get("date", day),
            "cat": cat, "group": group, "entity": r.get("entity") or "", "related": r.get("related") or [],
            "tags": [t for t in (r.get("tags") or []) if t in (wl.get("tags") or {})][:5],
            "grade": grade, "rel": int(c.get("rel", 2)), "followup": fu,
        }
        grp = next(g for g in idx[cat]["groups"] if g["id"] == group)
        grp["items"].append(item)
        items.append(item); cid_to_id[cid] = item["id"]
    if errors:
        print("경고:", "; ".join(errors), file=sys.stderr)
    if len(items) < int(rules.get("min_items_to_publish", 2)):
        raise SystemExit(f"정제 항목이 너무 적음({len(items)}건) — 반영하지 않음")
    top = [cid_to_id[c] for c in (ref.get("top") or []) if c in cid_to_id][:4]
    if not top:
        top = [it["id"] for it in sorted(items, key=lambda it: (it["grade"], -it["rel"]))[:3]]
    guide = [{"item_id": cid_to_id[g["cid"]], "say": B.strip_tags(str(g.get("say", "")))[:80]}
             for g in (ref.get("guide") or []) if g.get("cid") in cid_to_id and g.get("say")][:6]
    site = wl.get("site") or {}
    hol = set((wl.get("schedule") or {}).get("holidays") or [])
    first = str(site.get("first_issue_date") or "").strip()
    if not first:
        older = sorted(f.stem for f in DATA.glob("????-??-??.json"))
        first = older[0] if older else day
    old = {}
    out = DATA / f"{day}.json"
    if out.exists():
        try:
            old = json.loads(out.read_text(encoding="utf-8"))
        except Exception:
            old = {}
    data = {
        "schema": 4, "date": day, "weekday": B.WEEKDAYS[_date.fromisoformat(day).weekday()],
        "edition": site.get("edition", "조간"), "issue_no": old.get("issue_no") or B.issue_no(first, day, hol),
        "window_hours": d.get("window_hours", 0), "refined": True,
        "summary": B.strip_tags(ref.get("summary") or "")[:160] or " · ".join(B.strip_tags(it["h"])[:30] for it in items[:4]),
        "top": top, "sections": sections, "guide": guide,
        "stats": {"published": len(items), "refined_by": "claude", "rule_published": old.get("stats", {}).get("published")},
        "sources": sorted({it["src"] for it in items if it.get("src")}),
        "note": "공개 보도·공시를 규칙표로 수집한 뒤 Claude가 회사·카테고리·등급을 확인하고 핵심 한 문장으로 정리한 사실 정보입니다. 수치·계약 세부는 원문/공시로 확인하십시오.",
    }
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    # 사안 DB: 그날 규칙표 기록을 지우고 정제본으로 다시 기억
    mem = B.TopicMemory(int(rules.get("topic_memory_days", 30)))
    mem.rows = [r for r in mem.rows if r.get("date") != day]
    for it in items:
        mem.remember(it, day)
        # 원문 제목도 함께 기억해 다음 날 같은 기사가 다른 제목으로 재등장하는 것을 막음
        c = cands.get(next((k for k, v in cid_to_id.items() if v == it["id"]), None))
        if c and B.norm_title(c["title"]) != B.norm_title(B.strip_tags(it["h"])):
            mem.remember({**it, "h": c["title"]}, day)
    mem.save()
    print(f"반영 완료: {out.name} · 제{data['issue_no']}호 · {len(items)}건 · 톱 {len(top)} · 영업 포인트 {len(guide)}줄 · 사안 DB {len(mem.rows)}건")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "prepare":
        prepare(sys.argv[2] if len(sys.argv) > 2 else today_kst())
    elif len(sys.argv) >= 3 and sys.argv[1] == "apply":
        apply(sys.argv[2])
    else:
        print(__doc__); sys.exit(1)
