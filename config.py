"""
설정 상수들. 갤러리 목록, 키워드, 경로 등을 여기서 한 번에 관리.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
# 경로
# ──────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"
TEMPLATE_DIR = ROOT_DIR / "templates"

DB_PATH = DATA_DIR / "monitor.db"
DASHBOARD_HTML = OUTPUT_DIR / "dashboard.html"

DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ──────────────────────────────────────────────
# 환경변수
# ──────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")
MAX_PAGES_PER_GALLERY = int(os.getenv("MAX_PAGES_PER_GALLERY", "2"))
REQUEST_SLEEP_SECONDS = float(os.getenv("REQUEST_SLEEP_SECONDS", "2.5"))

# ──────────────────────────────────────────────
# HTTP 헤더 (브라우저 위장 — 디시는 User-Agent 없으면 차단)
# ──────────────────────────────────────────────
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ──────────────────────────────────────────────
# 대상 갤러리
# is_minor=True → mgallery 경로 사용
# id 값은 디시 실제 갤러리 ID. 안 잡히면 여기 수정.
# ──────────────────────────────────────────────
GALLERIES: list[dict] = [
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

# ──────────────────────────────────────────────
# 검색 키워드 (1차 필터)
# ──────────────────────────────────────────────
KEYWORDS = [
    "투네이션",
    "투네",
    "tooneation",
    "toon.at",
    "투네아",
]

# "투네"는 줄임말이라 오탐 많음.
# "투네이트", "투네라이즈" 같이 뒤에 한글/영문이 붙으면 다른 단어로 보고 제외.
# "투네이션"은 별도 단어이므로 통과시키기 위해 미리 우선순위 매칭.
KEYWORD_BOUNDARY_REGEX = r"(?<![가-힣A-Za-z])(투네이션|tooneation|toon\.at|투네아|투네(?![가-힣A-Za-z]))"

# ──────────────────────────────────────────────
# Claude 분류기 파라미터
# ──────────────────────────────────────────────
CLASSIFIER_MAX_BODY_CHARS = 1500
CLASSIFIER_TOP_COMMENTS = 5


def gallery_base_url(gallery: dict) -> str:
    """갤러리의 검색용 기본 URL."""
    prefix = "mgallery/" if gallery["is_minor"] else ""
    return f"https://gall.dcinside.com/{prefix}board"


def gallery_list_url(gallery: dict, keyword: str, page: int = 1) -> str:
    """제목+내용 검색 결과 페이지 URL."""
    from urllib.parse import quote
    base = gallery_base_url(gallery)
    encoded = quote(keyword)
    return (
        f"{base}/lists/?id={gallery['id']}"
        f"&s_type=search_subject_memo"
        f"&s_keyword={encoded}"
        f"&page={page}"
    )


def gallery_view_url(gallery: dict, post_no: int) -> str:
    """글 상세 페이지 URL."""
    base = gallery_base_url(gallery)
    return f"{base}/view/?id={gallery['id']}&no={post_no}"
