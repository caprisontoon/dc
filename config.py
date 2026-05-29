import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
DB_PATH = DATA_DIR / "monitor.db"

DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

GALLERIES = [
    {
        "id": "stream",
        "name": "인터넷방송 마이너 갤러리",
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

KEYWORDS = [
    "투네이션",
    "투네",
    "tooneation",
    "toon.at",
    "투네아",
]

# 1차 필터: '투네' 뒤에 다른 한글/영문이 이어지면 제외 (투네이션은 별도 패턴으로 먼저 매칭)
KEYWORD_PATTERNS = {
    "투네이션": r"투네이션",
    "투네아": r"투네아",
    "투네": r"투네(?![가-힣A-Za-z])",
    "tooneation": r"(?i)tooneation",
    "toon.at": r"(?i)toon\.at",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://gall.dcinside.com/",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}

SEARCH_PAGES = 2       # 갤러리당 검색 결과 페이지 수
REQUEST_DELAY = 2.5    # 요청 간격 (초)
COMMENT_LIMIT = 5      # Claude API에 보낼 상위 댓글 수
BODY_CHAR_LIMIT = 1500 # Claude API에 보낼 본문 최대 글자 수

CLAUDE_MODEL = "claude-sonnet-4-5"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
