import re

GALLERIES = [
    {
        "id": "stream",
        "name": "인터넷방송 마이너 갤러리 (이방갤)",
        "is_minor": True,
    },
    {
        "id": "vyutuber",
        "name": "버츄얼 유튜버 마이너 갤러리",
        "is_minor": True,
    },
    {
        "id": "twitch",
        "name": "트위치 갤러리",
        "is_minor": False,
    },
    {
        "id": "africatv",
        "name": "아프리카TV 갤러리",
        "is_minor": False,
    },
    {
        "id": "streamer",
        "name": "스트리머 갤러리",
        "is_minor": False,
    },
]

# 갤러리 ID -> 설정 dict 빠른 조회
GALLERY_MAP = {g["id"]: g for g in GALLERIES}

KEYWORDS = [
    "투네이션",
    "tooneation",
    "toon.at",
    "투네아",
    "투네",  # 가장 오탐 많음 — 마지막에 둬서 다른 키워드 먼저 매칭
]

# 투네 뒤에 한글/영문 자모가 오면 오탐 (투네이션은 별도 키워드라 여기선 제외)
_TUNE_BOUNDARY = re.compile(r"투네(?!이션)(?![가-힣A-Za-z])")
_EXACT_PATTERNS = [
    re.compile(r"투네이션", re.IGNORECASE),
    re.compile(r"tooneation", re.IGNORECASE),
    re.compile(r"toon\.at", re.IGNORECASE),
    re.compile(r"투네아"),
    _TUNE_BOUNDARY,
]

def keyword_match(text: str) -> str | None:
    """텍스트에서 첫 번째로 매칭된 키워드를 반환. 없으면 None."""
    for pattern in _EXACT_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None

BASE_URL = "https://gall.dcinside.com"
SEARCH_TYPE = "search_subject_memo"  # 제목+내용 검색
REQUEST_DELAY = 2.5  # 요청 간 sleep 초
MAX_PAGES = 2        # 갤러리당 최대 수집 페이지
MAX_COMMENTS = 5     # Claude에 넘길 상위 댓글 수

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://gall.dcinside.com/",
}

DB_PATH = "data/monitor.db"
OUTPUT_PATH = "output/dashboard.html"
TEMPLATE_PATH = "templates/dashboard.html.j2"
