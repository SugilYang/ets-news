"""
섹션 및 검색어(피드) 설정.

각 섹션은 구글 뉴스 RSS 검색을 사용해 관련 기사를 수집합니다.
검색어를 바꾸면 수집되는 기사 주제가 바뀝니다. (한국어 OR 검색 지원)
"""

# 구글 뉴스 RSS 검색 URL 템플릿 (한국/한국어)
# {q} 자리에 URL 인코딩된 검색어가 들어갑니다.
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"

# 섹션 정의 -------------------------------------------------------------------
# id      : HTML 앵커/식별자
# name    : 화면에 표시되는 섹션 이름
# tagline : 섹션 부제
# accent  : 강조 색상 키 (css 클래스로 사용: default | red | blue | green | gold)
# queries : 구글 뉴스에 넣을 검색어 목록 (여러 개면 합쳐서 중복 제거)
# limit   : 이 섹션에 표시할 최대 기사 수
SECTIONS = [
    {
        "id": "headline",
        "name": "종합 헤드라인",
        "tagline": "이차전지 장비 산업 주요 뉴스",
        "accent": "default",
        "lead": True,
        "limit": 9,
        "queries": [
            "이차전지 장비",
            "2차전지 장비",
            "배터리 제조장비",
            "전해액 주액 설비",
        ],
    },
    {
        "id": "company",
        "name": "기업·고객사 동향",
        "tagline": "이티에스(ETS) · LG에너지솔루션 · 장비업계",
        "accent": "blue",
        "limit": 8,
        "queries": [
            "이티에스 이차전지",
            "LG에너지솔루션 장비",
            "LG에너지솔루션 투자",
            "이차전지 장비업체",
        ],
    },
    {
        "id": "safety",
        "name": "안전·산업재해",
        "tagline": "배터리 공장 화재 · 산업안전 · 중대재해",
        "accent": "red",
        "limit": 8,
        "queries": [
            "이차전지 공장 화재",
            "배터리 공장 안전",
            "이차전지 산업안전",
            "리튬 배터리 화재",
        ],
    },
    {
        "id": "labor",
        "name": "고용노동부·산업안전보건",
        "tagline": "정책 · 중대재해처벌법 · 근로환경",
        "accent": "green",
        "limit": 7,
        "queries": [
            "고용노동부 산업안전",
            "중대재해처벌법",
            "산업안전보건법",
            "고용노동부 제조업",
        ],
    },
    {
        "id": "economy",
        "name": "경제·산업 전망",
        "tagline": "이차전지 시황 · 투자 · 수주",
        "accent": "gold",
        "limit": 8,
        "queries": [
            "이차전지 산업 전망",
            "배터리 산업 투자",
            "이차전지 수주",
            "배터리 소재 시장",
        ],
    },
    {
        "id": "automation",
        "name": "AMR·스마트팩토리",
        "tagline": "자율주행로봇 · 물류자동화 · 스마트공장",
        "accent": "blue",
        "limit": 7,
        "queries": [
            "AMR 물류로봇",
            "자율주행로봇 공장",
            "스마트팩토리 자동화",
            "제조 물류자동화",
        ],
    },
    {
        "id": "global",
        "name": "글로벌 배터리",
        "tagline": "해외 공장 · 북미/유럽 · 공급망",
        "accent": "default",
        "limit": 7,
        "queries": [
            "배터리 공장 미국",
            "배터리 공장 유럽",
            "전기차 배터리 공급망",
            "battery gigafactory",
        ],
    },
    {
        "id": "tech",
        "name": "기술 동향",
        "tagline": "전해액 · 전고체 · 차세대 배터리",
        "accent": "default",
        "limit": 7,
        "queries": [
            "전고체 배터리",
            "이차전지 신기술",
            "배터리 전해액 기술",
            "차세대 배터리",
        ],
    },
]

# 사이트 기본 정보 ------------------------------------------------------------
SITE = {
    "paper_name": "이티에스",         # 제호 (한글만 표시)
    "epoch": "2025-01-01",           # 발행 호수 계산 기준일
    "articles_per_source": 12,       # 피드 하나당 읽어올 최대 항목 수
}
