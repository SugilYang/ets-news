# 이티에스 영업 인텔리전스 (ETS Sales Intelligence)

이차전지 장비·전해액 주액 설비·AMR 영업을 위한 **고객사·경쟁사·수주 인텔리전스**를
매일 아침 정제해 **홈페이지 + 날짜별 아카이브**로 보여 줍니다.

- **홈(오늘 브리핑):** `index.html` — 매일 아침 자동 갱신
- **지난 자료:** `archive.html` — 날짜별 보관, 클릭하면 그날 브리핑
- 구성: 오늘의 영업 우선순위(TOP3) · 고객사(LG엔솔) · 잠재고객 스캔 · 경쟁사(주액기) · 전후공정 · AMR · 업계 동향

## 감시 대상 바꾸기 (넣고 빼기)
`watchlist.yml` 파일만 고치면 됩니다. 코드 몰라도 회사명·키워드 목록을 추가/삭제하거나
`enabled: false` 로 잠시 끌 수 있습니다. 수정하면 다음 아침 브리핑부터 반영됩니다.

## 구조
```
render.py         # 디자인 고정 지면 생성기(내용은 data/로 매일 바뀜)
watchlist.yml     # 감시 대상 설정 (여기만 고치면 됨)
data/<날짜>.json  # 하루치 브리핑 내용 (매일 아침 자동 생성)
index.html        # 홈 = 최신 브리핑 (자동 생성)
archive.html      # 지난 자료 목록 (자동 생성)
briefings/<날짜>.html  # 날짜별 브리핑 (자동 생성)
```

## 공개 웹주소로 보기 (무료)
Settings → Pages → Source: **Deploy from a branch → main → /(root)** → Save
→ `https://sugilyang.github.io/ets-news/`

> ‘🎯 시사점’은 공개뉴스 기반 분석이며, ‘확인 필요’ 항목은 실제 발주정보로 검증 후 활용하세요.
