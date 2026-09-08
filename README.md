# 이티에스 산업 브리핑

이차전지 장비·전해액 주액 설비·AMR 관련 **고객사·장비·시장 동향을 사실 중심으로 정리**해
매일 아침 8시(KST) **GitHub이 혼자 생성·발행**하는 산업 브리핑 사이트입니다. (사람 개입 없음)

- **홈(오늘)** `index.html` · **지난 자료** `archive.html`(날짜별 보관) · **회사별** `companies/` · **검색** `search.html` · **주간 요약** `weekly.html`
- 각 항목: 제목(원문 링크) · 3~5문장 사실 요약(수치·날짜) · 매체 · 보도일

## 처음 한 번만 (약 3분)
1. **API 키 등록** — 매일 조사·정제를 하는 Claude API 키
   - https://console.anthropic.com → API Keys → **Create Key** (이름: ets-brief)
   - 이 저장소 → **Settings → Secrets and variables → Actions → New repository secret**
     이름 `ANTHROPIC_API_KEY`, 값 = 방금 만든 키 → Add secret
   - ⚠️ 키는 GitHub Secrets에만 넣으세요(채팅·메일에 붙여넣지 않기)
2. **공개 웹주소** — **Settings → Pages → Source: Deploy from a branch → main / (root)** → Save
   → `https://sugilyang.github.io/ets-news/`
3. **회사 로고(선택)** — `assets/logo.png` 로 올리면 상단 브랜드 바에 자동 표시(높이 44px로 축소)
   - 저장소에서 **Add file → Upload files** → 파일명을 `logo.png`로, 폴더는 `assets` (경로 `assets/logo.png`)

## 매일 어떻게 도나
`.github/workflows/daily.yml` 이 매일 23:00 UTC(=08:00 KST)에 실행:
1. `scripts/generate.py` — `watchlist.yml` 기준으로 Claude가 웹 검색 → 사실 위주 정리 → `data/<오늘>.json`
2. `render.py` — 홈·아카이브·회사별·검색·주간 페이지 재생성
3. 커밋·푸시 → GitHub Pages 자동 반영

**지금 바로 실행:** Actions 탭 → "매일 아침 브리핑 자동 생성" → Run workflow

## 감시 대상·규칙 바꾸기
`watchlist.yml` 하나만 고치면 됩니다(회사·키워드 넣고 빼기, `enabled: false`로 끄기, 섹션별 건수·문체 규칙).

## 비용
- GitHub: 무료 범위(하루 수 분)
- Claude API: 하루 1회, 대략 **1~2달러/일** 수준(검색 24회 기준). 줄이려면 저장소 **Settings → Variables**에
  `BRIEF_MAX_SEARCHES`(예: 12) 또는 `BRIEF_MODEL`(예: `claude-sonnet-5`)을 설정하세요.

## 구조
```
scripts/generate.py   조사·정제 → data JSON (Claude API + 웹 검색)
render.py             디자인 고정 지면 생성기
watchlist.yml         감시 대상·작성 규칙 (여기만 고치면 됨)
data/<날짜>.json      하루치 내용(영구 보관)
index.html / archive.html / search.html / weekly.html / briefings/ / companies/   자동 생성
.github/workflows/daily.yml   매일 아침 자동 실행
.github/workflows/build.yml   data 수정 시 지면 재생성(안전망)
assets/logo.png       회사 로고(선택)
```

> 본 브리핑은 공개 보도를 정제·요약한 사실 정보이며, 수치·계약 세부는 원문/공시로 최종 확인하시기 바랍니다.
