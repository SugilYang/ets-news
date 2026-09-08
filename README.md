# 이티에스 산업 브리핑

이차전지 장비·전해액 주액 설비·AMR 관련 **고객사·장비·시장 동향을 사실 중심으로 정리**해
매일 아침 8시(KST) **자동 생성·발행**되는 산업 브리핑 사이트입니다. (사람 개입 없음)

- **홈(오늘)** `index.html` · **지난 자료** `archive.html`(날짜별 영구 보관) · **회사별** `companies/` · **검색** `search.html` · **주간 요약** `weekly.html`
- 각 항목: 제목(원문 링크) · 3~5문장 사실 요약(수치·날짜) · 매체 · 보도일
- 공개 주소: `https://sugilyang.github.io/ets-news/` (Settings → Pages → Deploy from a branch → main / (root))

## 매일 어떻게 도나 (Max 요금제 안에서, 추가 비용 0)
매일 23:00 UTC(=08:00 KST) **Claude 예약 세션**이 자동으로 열려:
1. `watchlist.yml`(감시 대상·작성 규칙)을 읽고 웹을 조사해 사실 위주로 정리 → `data/<오늘>.json`
2. `render.py`로 홈·아카이브·회사별·검색·주간 페이지 재생성
3. GitHub에 커밋·푸시 → Pages 자동 반영

세션이 GitHub에 올릴 수 있도록 **토큰 하나만** 환경에 넣어두면 됩니다(아래).

## 처음 한 번만 (약 3분)
1. **GitHub 토큰 만들기** — GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens → Generate**
   - Repository access: **Only select repositories → `ets-news`**
   - Permissions → Repository permissions → **Contents: Read and write**
   - 만료(Expiration)는 넉넉히(예: 1년). 생성 후 토큰 값을 복사
2. **Claude 환경변수에 등록** — claude.ai/code → 환경(Environments) 설정 → 이 저장소를 쓰는 환경 → **Environment variables**
   - 이름 `GH_PUSH_TOKEN`, 값 = 토큰 → 저장
   - ⚠️ 토큰은 여기에만 넣으세요(채팅·메일에 붙여넣지 않기). 아침 세션은 값을 출력하지 않도록 설계돼 있습니다.
3. (선택) **회사 로고** — `assets/logo.png` 로 업로드하면 상단 브랜드 바에 자동 표시(44px 높이로 축소)
   - 저장소 → Add file → Upload files → 경로 `assets/logo.png`

## 감시 대상·규칙 바꾸기
`watchlist.yml` 하나만 고치면 됩니다(회사·키워드 넣고 빼기, `enabled: false`로 끄기, 섹션별 건수·문체 규칙). 다음 아침부터 반영.

## 예비 수단 (선택, 별도 과금)
Claude 예약 세션이 어떤 이유로 실패한 날엔, `ANTHROPIC_API_KEY`를 Secrets에 등록해 두었다면
Actions 탭 → "(예비) API 키로 브리핑 생성" → Run workflow 로 수동 생성할 수 있습니다. (`scripts/generate.py`, 하루 약 450~1,500원)

## 구조
```
render.py                  디자인 고정 지면 생성기 (홈·아카이브·회사별·검색·주간)
watchlist.yml              감시 대상·작성 규칙 (여기만 고치면 됨)
data/<날짜>.json           하루치 내용(영구 보관, 매일 아침 추가)
briefings/ companies/ index.html archive.html search.html weekly.html   자동 생성
.github/workflows/build.yml   data 수정 시 지면 재생성(안전망)
.github/workflows/daily.yml   (예비) API 키 수동 생성
scripts/generate.py        (예비) API 기반 생성기
assets/logo.png            회사 로고(선택)
```

> 본 브리핑은 공개 보도를 정제·요약한 사실 정보이며, 수치·계약 세부는 원문/공시로 최종 확인하시기 바랍니다.
