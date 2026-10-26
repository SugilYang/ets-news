# 이티에스 시장 동향

「일일·주간 시장동향 정보보고 체계」(PPT)와 Market Intelligence(엑셀)의 틀을 그대로 웹 신문으로 옮긴 사이트입니다.
**매주 월요일** 아침, 지난 일주일(168시간)치를 한 호로 묶어 두 단계로 발행됩니다. (2026-10-26까지는 매일 발행)
1. **06:50 GitHub Actions(무료)** — 뉴스 수집·규칙표 분류 → 규칙표 판 먼저 게시 + 후보 목록(`db/candidates-<날짜>.json`)
2. **07:40 Claude 예약(Max 요금제 안, 추가 비용 0, 월요일만)** — 후보를 읽고 회사·카테고리·등급을 확인, 핵심 한 문장·영업 포인트를 정리한 **정제판**으로 덮어씀 (`scripts/refine.py`)

Claude 단계가 실패해도 규칙표 판이 그대로 남습니다. 판단 문장 없음(사실만).

- 공개 주소: `https://sugilyang.github.io/ets-news/`
- **이번 주 브리핑** `index.html` — 1면 톱(A등급) + ①Project·RFQ ②고객사 ③업계 ④기술·정책 ⑤시장·산업 (일간 발행일 때는 '오늘 브리핑')
- **지난 호** `archive.html` — 달력에서 날짜 클릭 · 호별 목록
- **회사별** `companies/` — 고객사·경쟁사별 누적 기록
- **검색** `search.html` — 키워드·카테고리·회사·등급·기간
- **주간 종합** `weekly.html`, `weekly/<주>.html` — 일간 발행일 때만 생성(주간 발행 중에는 호 자체가 일주일치라 메뉴를 숨김)

각 항목: 제목(원문 링크) · 1~2문장 · 매체 · 보도일 · 등급(A 즉시 / B Daily / C Weekly) · ★출처 신뢰도 · 태그(주액·RFQ·리스크 등).
한 번 실은 사안은 30일간 기억해 **수치·일정이 바뀐 경우에만 '후속'** 으로 다시 실립니다(무엇이 바뀌었는지 한 줄 표시).

> 멈추려면: `.github/workflows/daily.yml` 의 `schedule` 두 줄 앞에 `#` 을 붙이고, claude.ai/code → Routines 에서 정제 예약을 끄면 됩니다.

## 매주 어떻게 도나 (무료·무인)
`.github/workflows/daily.yml` 이 일요일 21:50 UTC(=월요일 06:50 KST) 실행:
1. `scripts/collect.py` — `watchlist.yml` 기준으로 언론사·기관 RSS(DART 공시·정책브리핑 포함) + Google News·Bing News 검색(한/영)
   → 원문 리드 추출 → 1~2문장 브리프 → 카테고리·등급·신뢰도·태그 판정 → 사안 기억과 대조(후속/제외) → `data/<오늘>.json`
2. `render.py` — 오늘·지난 호(달력)·회사별·검색·주간 종합 페이지 재생성
3. 커밋·푸시 → Pages 자동 반영

주간 발행은 최근 168시간(7일) 창으로 찾고, 월요일이 공휴일이어도 발행합니다. 일간으로 되돌리려면 `watchlist.yml` 의 `publish_weekdays` 줄을 지우고(메뉴·'오늘' 문구·주간 종합이 자동으로 돌아옴) `daily.yml` 의 cron 을 `50 21 * * 0-4` 로 바꾸세요.

## 감시 대상·규칙 바꾸기 — `watchlist.yml` 하나만
| 바꾸고 싶은 것 | 어디를 고치나 |
|---|---|
| 고객사 추가/삭제, 별칭 | `customers:` |
| 경쟁사 추가/삭제, 등급·범위 | `competitors:` (엑셀 Competitor DB 22개사 기준) |
| 검색어 | `customer_watch:` `competitor_watch:` `market_queries:` |
| 중요도 A/B 판정 단어, 금액 기준 | `importance:` |
| 출처 신뢰도 ★ | `reliability:` (도메인) |
| 태그 | `tags:` |
| 카테고리 켜고 끄기·순서·소제목 | `categories:` (`enabled`, `order`, `groups`) |
| 공휴일, 검색 창(시간) | `schedule:` |
| 문장 수·글자 수·기억 기간 | `rules:` |

저장하면 다음 발행부터 반영됩니다(또는 Actions 탭 → Run workflow 로 즉시).

## 구조
```
scripts/collect.py        수집·분류·등급·사안 기억 → data JSON (무료, API 키 없음)
scripts/brieflib.py       분류·등급·후속 판정 공통 라이브러리(규칙표 적용만 함)
scripts/refine.py         Claude 정제 단계 도우미(prepare: 후보 출력 / apply: 정제 결과 반영·검증)
render.py                 신문 지면 생성기 (오늘·지난 호 달력·회사별·검색·주간 3면)
watchlist.yml             감시 대상·규칙 (여기만 고치면 됨)
data/<날짜>.json          하루치 내용(영구 보관)   db/topics.json  사안 기억(30일)
index.html archive.html search.html weekly.html briefings/ companies/ weekly/   자동 생성
.github/workflows/daily.yml   매주 월 06:50 수집(무료)   build.yml  data 수정 시 지면 재생성
assets/logo.png           회사 로고(원본, 44px 높이로 축소 표시)
```

> 본 브리핑은 공개 보도·공시의 제목과 리드 문장을 규칙표에 따라 자동 분류·등급화한 사실 정보이며, 수치·계약 세부는 원문/공시로 최종 확인하시기 바랍니다.
