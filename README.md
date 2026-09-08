# 이티에스 산업 브리핑

이차전지 장비·전해액 주액 설비·AMR 관련 **고객사·장비·시장 동향을 사실 중심으로 정리**해
매일 아침 8시(KST) **GitHub이 혼자 무료로 생성·발행**하는 산업 브리핑 사이트입니다.
사람 개입·API 키·유료 결제 **없음**.

- **홈(오늘)** `index.html` · **지난 자료** `archive.html`(날짜별 영구 보관) · **회사별** `companies/` · **검색** `search.html` · **주간 요약** `weekly.html`
- 각 항목: 제목(원문 링크) · 원문 리드 문단 3~5문장(수치 강조) · 매체 · 보도일
- 공개 주소: `https://sugilyang.github.io/ets-news/` (Settings → Pages → Deploy from a branch → main / (root))

## 매일 어떻게 도나 (무료·무인)
> **현재 자동 실행은 일시 중지 상태**입니다(최종 확정 전). `.github/workflows/daily.yml` 의 `schedule` 두 줄 앞 `#` 을 지우면 다시 매일 아침 돕니다.
> 중지 중에도 Actions 탭 → Run workflow 로 수동 생성은 가능합니다.

`.github/workflows/daily.yml` 이 매일 23:00 UTC(=08:00 KST) 자동 실행:
1. `scripts/collect.py` — `watchlist.yml` 기준으로 뉴스 검색(Google News·Bing News RSS, 한/영) → 기사 원문에서 **리드 문단 추출** → 최근 7일과 중복 제거 → `data/<오늘>.json`
2. `render.py` — 홈·아카이브·회사별·검색·주간 페이지 재생성
3. 커밋·푸시 → Pages 자동 반영

주관적 판단은 넣지 않습니다. 기사 제목과 원문 리드 문단을 **그대로** 정리합니다.

## 감시 대상·규칙 바꾸기
`watchlist.yml` 하나만 고치면 됩니다 — 회사·키워드 넣고 빼기, `enabled: false`로 섹션 끄기, 섹션별 건수(`items_per_section`).
저장하면 자동으로 반영됩니다(다음 아침, 또는 Actions 탭 → Run workflow로 즉시).

## 회사 로고
상단 브랜드 바에 원본 로고 `assets/logo.png` 가 높이 44px(모바일 34px)로 축소 표시됩니다. 파일을 바꿔 넣으면 그대로 반영됩니다.

## 구조
```
scripts/collect.py         뉴스 검색 → 원문 리드 추출 → data JSON (무료, API 키 없음)
render.py                  디자인 고정 지면 생성기 (홈·아카이브·회사별·검색·주간)
watchlist.yml              감시 대상·작성 규칙 (여기만 고치면 됨)
data/<날짜>.json           하루치 내용(영구 보관)
briefings/ companies/ index.html archive.html search.html weekly.html   자동 생성
.github/workflows/daily.yml   매일 아침 자동 실행
.github/workflows/build.yml   data 직접 수정 시 지면 재생성(안전망)
assets/logo.svg | logo.png  회사 로고
```

> 본 브리핑은 공개 보도의 원문 리드 문단을 자동 추출·정리한 사실 정보이며, 수치·계약 세부는 원문/공시로 최종 확인하시기 바랍니다.
