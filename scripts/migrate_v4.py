#!/usr/bin/env python3
"""
구 스키마(cards, v3) data/*.json → v4(sections·등급·태그·사안 기억) 일괄 변환.
한 번만 실행. 이미 v4인 파일은 건너뜀. 변환 후 db/topics.json 을 날짜순으로 다시 만듭니다.
"""
from __future__ import annotations

import html
import json
import sys
from datetime import date as _date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brieflib as B  # noqa: E402

DATA = B.ROOT / "data"


def convert(d: dict, clf: B.Classifier, wl: dict, mem: B.TopicMemory) -> dict:
    rules = wl.get("rules") or {}
    n_sent = int(rules.get("brief_sentences", 2)); max_chars = int(rules.get("brief_max_chars", 170))
    day = d["date"]
    sections = clf.skeleton()
    idx = {s["id"]: s for s in sections}
    seq, kept, dropped = 0, 0, 0
    for c in d.get("cards", []):
        for it in c.get("items", []):
            title = B.strip_tags(it.get("h", ""))
            raw_b = B.strip_tags(it.get("b", ""))
            brief = B.make_brief(raw_b, n_sent, max_chars) or raw_b[:max_chars]
            cls = clf.classify(title, f"{it.get('company','')} {c.get('title','')} {raw_b}")
            if not cls:
                dropped += 1
                continue
            url = it.get("url", "")
            item = {
                "id": f"{day}-{seq}", "h": html.escape(title, quote=False), "b": B.highlight(brief),
                "src": it.get("src", ""), "url": url, "date": it.get("date", day),
                "cat": cls["cat"], "group": cls["group"], "entity": cls["entity"], "related": cls["related"],
                "tags": cls["tags"], "grade": cls["grade"], "rel": clf.reliability(url), "followup": None,
            }
            prev = mem.find(item["entity"], item["cat"], item["group"], title, url)
            if prev and prev.get("date") != day:
                ch = B.TopicMemory.change(prev, title, brief)
                if not ch:
                    dropped += 1
                    continue
                item["followup"] = {"prev_date": prev["date"], "prev_h": prev.get("h", ""), "change": ", ".join(ch[:5])}
            sec = idx[cls["cat"]]
            grp = next((g for g in sec["groups"] if g["id"] == cls["group"]), None)
            if grp is None:
                grp = {"id": cls["group"], "title": "", "items": []}; sec["groups"].append(grp)
            grp["items"].append(item)
            mem.remember(item, day)
            seq += 1; kept += 1
    allitems = [it for s in sections for g in s["groups"] for it in g["items"]]
    tops = sorted([it for it in allitems if it["grade"] == "A"], key=lambda it: (-it["rel"], -int(it["date"].replace("-", ""))))[:4]
    if not tops:
        tops = sorted([it for it in allitems if it["grade"] == "B"], key=lambda it: -it["rel"])[:1]
    site = wl.get("site") or {}
    hol = set((wl.get("schedule") or {}).get("holidays") or [])
    wd = B.WEEKDAYS[_date.fromisoformat(day).weekday()]
    print(f"  {day}: {kept}건 변환, {dropped}건 제외(감시 대상 아님/미변경)")
    return {
        "schema": 4, "date": day, "weekday": wd, "edition": site.get("edition", "조간"),
        "issue_no": B.issue_no(site.get("first_issue_date", day), day, hol), "window_hours": 0,
        "summary": " · ".join(B.strip_tags(it["h"])[:30] for it in tops[:4]),
        "top": [it["id"] for it in tops], "sections": sections,
        "stats": {"published": kept, "migrated_from": "v3"},
        "sources": sorted({it["src"] for it in allitems if it.get("src")}),
        "note": "공개 보도·공시의 제목과 리드 문장을 규칙표(watchlist.yml)에 따라 자동 분류·등급화한 사실 정보입니다. 수치·계약 세부는 원문/공시로 확인하십시오.",
    }


def main() -> int:
    wl = B.load_watchlist()
    clf = B.Classifier(wl)
    mem = B.TopicMemory(int((wl.get("rules") or {}).get("topic_memory_days", 30)))
    mem.rows = []
    files = sorted(DATA.glob("*.json"))
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("schema") == 4:
            for s in d["sections"]:
                for g in s["groups"]:
                    for it in g["items"]:
                        mem.remember(it, d["date"])
            print(f"  {f.name}: 이미 v4")
            continue
        nd = convert(d, clf, wl, mem)
        f.write_text(json.dumps(nd, ensure_ascii=False, indent=1), encoding="utf-8")
    mem.save()
    print(f"완료: {len(files)}개 파일 · 사안 DB {len(mem.rows)}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
