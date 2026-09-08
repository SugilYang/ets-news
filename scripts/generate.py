#!/usr/bin/env python3
"""
이티에스 산업 브리핑 — 무인 자동 생성기 (GitHub Actions에서 매일 실행)

1) watchlist.yml(감시 대상·작성 규칙)과 최근 data/*.json(스키마·문체·중복제거용)을 읽고
2) Claude(웹 검색 도구)로 섹션별 최신 사실을 조사한 뒤
3) 구조화 출력(JSON 스키마)으로 data/<오늘>.json 을 만든다.

- 사람 개입 없음. 사실(팩트) 중심, 주관적 판단 금지 규칙은 프롬프트로 강제.
- 오늘 파일이 이미 있으면 아무것도 하지 않는다(멱등).
- 환경변수 ANTHROPIC_API_KEY 필요 (GitHub Secrets).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
WATCHLIST = ROOT / "watchlist.yml"

MODEL = os.environ.get("BRIEF_MODEL", "claude-opus-5")
KST = timezone(timedelta(hours=9))
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
MAX_SEARCHES = int(os.environ.get("BRIEF_MAX_SEARCHES", "24"))

# ---------------------------------------------------------------- 출력 스키마
ITEM = {
    "type": "object",
    "properties": {
        "h": {"type": "string", "description": "제목(핵심 수치·사실 포함, 25자 내외)"},
        "b": {"type": "string", "description": "3~5문장 사실 요약. 중요한 수치는 <b></b>로 감쌀 수 있음"},
        "src": {"type": "string", "description": "매체명"},
        "url": {"type": "string", "description": "원문 URL. 없으면 빈 문자열"},
        "company": {"type": "string", "description": "관련 회사/주제명"},
        "date": {"type": "string", "description": "보도일 YYYY-MM-DD (모르면 YYYY-MM)"},
    },
    "required": ["h", "b", "src", "url", "company", "date"],
    "additionalProperties": False,
}
CARD = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "accent": {"type": "string", "enum": ["blue", "teal", "violet", "rust", "amber", "slate"]},
        "icon": {"type": "string"},
        "title": {"type": "string"},
        "subtitle": {"type": "string"},
        "full": {"type": "boolean"},
        "items": {"type": "array", "items": ITEM},
    },
    "required": ["id", "accent", "icon", "title", "subtitle", "full", "items"],
    "additionalProperties": False,
}
SCHEMA = {
    "type": "object",
    "properties": {
        "date": {"type": "string"},
        "weekday": {"type": "string"},
        "edition": {"type": "string"},
        "summary": {"type": "string", "description": "그날 핵심 4~6개를 ' · '로 이은 한 줄"},
        "cards": {"type": "array", "items": CARD},
        "sources": {"type": "string"},
        "note": {"type": "string"},
    },
    "required": ["date", "weekday", "edition", "summary", "cards", "sources", "note"],
    "additionalProperties": False,
}

STYLE_RULES = """
[작성 원칙 — 반드시 준수]
- 철저히 '사실' 중심: 무슨 일이 있었는지, 수치·날짜·출처. 주관적 판단·영업 시사점·우선순위·고객/경쟁사 라벨 금지.
- 확인되지 않은 수치·계약 내용은 쓰지 않는다. 추정 금지.
- 아이템당 3~5문장(배경 → 핵심 수치 → 후속 일정). 제목은 핵심 수치/사실을 담아 25자 내외.
- 섹션당 최소 3건·최대 8건. 정말 없으면 있는 만큼만(억지로 채우지 않는다).
- 최근 1~2일 우선, 없으면 최근 1주. 각 아이템에 보도일·매체·가능하면 원문 URL.
- 중복 제거: 아래 '최근 게재 목록'과 같은 기사·같은 사안은 제외. 후속 보도만 "후속: " 접두어로 1건.
- 한국어로 작성. 영문 소스 기사는 사실을 한국어로 정리하고 매체명은 원어(예: Reuters).
"""


def kst_today() -> datetime:
    return datetime.now(tz=KST)


def load_recent(days: int = 7) -> list[dict]:
    out = []
    for f in sorted(DATA.glob("*.json"), reverse=True)[:days]:
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return out


def recent_headlines(recent: list[dict]) -> str:
    lines = []
    for d in recent:
        for c in d.get("cards", []):
            for it in c.get("items", []):
                lines.append(f"- [{d.get('date')}] {it.get('h','')} ({it.get('url','') or it.get('src','')})")
    return "\n".join(lines[:200]) or "(없음)"


def text_of(msg) -> str:
    return "\n".join(b.text for b in msg.content if b.type == "text")


def research(client: anthropic.Anthropic, today: str, watchlist: str, exemplar: dict, recent_list: str) -> str:
    """웹 검색으로 섹션별 사실을 조사해 메모(텍스트)로 반환."""
    prompt = f"""오늘은 {today}(KST)입니다. 아래 감시 대상 설정(YAML)의 enabled: true 섹션마다 최신 뉴스를 웹 검색으로 조사하세요.
한국어 매체 우선, 글로벌·정책 섹션은 영문 매체(Reuters, Bloomberg, Electrive 등)도 검색하세요.

{STYLE_RULES}

[감시 대상 설정 — watchlist.yml]
{watchlist}

[최근 게재 목록 — 이와 같은 기사/사안은 제외]
{recent_list}

[출력 형식]
섹션별로 아래 형식의 '조사 메모'를 작성하세요. 나중에 JSON으로 정리할 재료이므로 사실·수치·날짜·URL을 빠짐없이 적으세요.
## <섹션 id> | <제목> | <부제>
- 제목: ...
  사실요약(3~5문장): ...
  회사: ... | 매체: ... | 보도일: YYYY-MM-DD | URL: ...
(섹션당 3~8건)
마지막에 '## 요약' 으로 그날 핵심 4~6개를 한 줄로 적으세요."""

    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": MAX_SEARCHES}]
    final = None
    for _ in range(6):  # pause_turn 재개 상한
        with client.messages.stream(
            model=MODEL,
            max_tokens=32000,
            output_config={"effort": "high"},
            tools=tools,
            messages=messages,
        ) as stream:
            msg = stream.get_final_message()
        if msg.stop_reason == "refusal":
            raise RuntimeError(f"조사 단계 거부: {getattr(msg, 'stop_details', None)}")
        if msg.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": msg.content})
            continue
        final = msg
        break
    if final is None:
        raise RuntimeError("조사 단계가 반복 일시정지로 끝나지 않음")
    notes = text_of(final)
    if len(notes) < 500:
        raise RuntimeError("조사 메모가 너무 짧음")
    return notes


def format_json(client: anthropic.Anthropic, today: str, weekday: str, notes: str, exemplar: dict) -> dict:
    """조사 메모를 지면 데이터 JSON(스키마 고정)으로 변환."""
    exemplar_cards = [
        {k: c.get(k) for k in ("id", "accent", "icon", "title", "subtitle", "full")}
        for c in exemplar.get("cards", [])
    ]
    prompt = f"""아래 '조사 메모'를 지면 데이터 JSON으로 변환하세요.

{STYLE_RULES}

[고정 값]
- date: "{today}", weekday: "{weekday}", edition: "조간"
- cards 의 id/accent/icon/title/subtitle/full 은 아래 예시 카드 구성을 그대로 따르세요(순서 포함). 메모에 해당 섹션 내용이 없으면 items 를 빈 배열로 두세요.
{json.dumps(exemplar_cards, ensure_ascii=False)}
- sources: 사용한 매체명을 '·'로 이은 한 줄 + "제목을 누르면 원문으로 이동합니다."
- note: "본 브리핑은 공개 보도를 정제·요약한 사실 정보이며, 수치·계약 세부는 원문/공시로 최종 확인하시기 바랍니다."
- b 안의 핵심 수치는 <b></b> 로 감싸도 됩니다(다른 HTML 태그 금지).

[조사 메모]
{notes}"""
    with client.messages.stream(
        model=MODEL,
        max_tokens=32000,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError("변환 단계 거부")
    return json.loads(text_of(msg))


def validate(d: dict, today: str) -> int:
    assert d.get("date") == today, f"date 불일치: {d.get('date')}"
    n = sum(len(c.get("items", [])) for c in d.get("cards", []))
    assert n >= 6, f"아이템이 너무 적음({n}건)"
    for c in d["cards"]:
        c["items"] = c["items"][:8]
    return n


def main() -> int:
    now = kst_today()
    today, weekday = now.strftime("%Y-%m-%d"), WEEKDAYS[now.weekday()]
    out = DATA / f"{today}.json"
    if out.exists():
        print(f"이미 생성됨: {out.name}"); return 0
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY 가 없습니다 (GitHub Secrets 확인)", file=sys.stderr); return 2

    recent = load_recent()
    if not recent:
        print("기준이 될 data/*.json 이 없습니다", file=sys.stderr); return 2
    exemplar, recent_list = recent[0], recent_headlines(recent)
    watchlist = WATCHLIST.read_text(encoding="utf-8")

    client = anthropic.Anthropic(max_retries=3, timeout=900.0)
    print(f"[1/3] 조사 시작 {today} ({weekday}) · 모델 {MODEL} · 검색 최대 {MAX_SEARCHES}회")
    notes = research(client, today, watchlist, exemplar, recent_list)
    print(f"[2/3] 조사 메모 {len(notes)}자 → JSON 변환")
    data = format_json(client, today, weekday, notes, exemplar)
    n = validate(data, today)
    DATA.mkdir(exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[3/3] 저장 {out.name} · 섹션 {len(data['cards'])}개 · 아이템 {n}건")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except anthropic.AuthenticationError:
        print("API 키가 잘못됐습니다", file=sys.stderr); sys.exit(2)
    except anthropic.RateLimitError as e:
        print(f"요청 한도 초과: {e}", file=sys.stderr); sys.exit(3)
    except anthropic.APIStatusError as e:
        print(f"API 오류 {e.status_code}: {e.message}", file=sys.stderr); sys.exit(3)
    except anthropic.APIConnectionError as e:
        print(f"네트워크 오류: {e}", file=sys.stderr); sys.exit(3)
