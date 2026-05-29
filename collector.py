"""
갤러리 검색결과 페이지를 순회해 신규 글 ID 목록을 반환.

디시인사이드 글 목록 HTML 구조 (2024년 기준):
  <tr class="ub-content us-post" data-no="12345">
    <td class="gall_num">12345</td>
    <td class="gall_tit">
      <a href="/board/view/?id=twitch&no=12345">제목</a>
    </td>
    <td class="gall_writer" data-nick="닉네임">닉네임</td>
    <td class="gall_date" title="2024-01-01 12:34:56">01.01</td>
    <td class="gall_count">100</td>
    <td class="gall_recommend">10</td>
  </tr>
"""

import time
import re
import logging
from urllib.parse import urlencode, quote

import requests
from bs4 import BeautifulSoup

from config import (
    HEADERS, REQUEST_DELAY, MAX_PAGES, KEYWORDS, BASE_URL,
    SEARCH_TYPE, GALLERY_MAP, keyword_match,
)
from db import post_exists

logger = logging.getLogger(__name__)


def _gallery_search_url(gallery_id: str, keyword: str, page: int, is_minor: bool) -> str:
    board = "mgallery/board" if is_minor else "board"
    params = {
        "id": gallery_id,
        "s_type": SEARCH_TYPE,
        "s_keyword": keyword,
        "page": page,
    }
    return f"{BASE_URL}/{board}/lists/?{urlencode(params, quote_via=quote)}"


def _parse_post_list(html: str, gallery_id: str, keyword: str) -> list[dict]:
    """HTML에서 글 메타데이터 목록 추출."""
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select("tr.ub-content")
    posts = []
    for row in rows:
        post_no_str = row.get("data-no", "").strip()
        if not post_no_str or not post_no_str.isdigit():
            continue
        post_no = int(post_no_str)
        post_id = f"{gallery_id}_{post_no}"

        title_tag = row.select_one("td.gall_tit a")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)

        author_td = row.select_one("td.gall_writer")
        author = author_td.get("data-nick", "").strip() if author_td else ""
        if not author:
            author = (author_td.get_text(strip=True) if author_td else "")

        date_td = row.select_one("td.gall_date")
        posted_at = date_td.get("title", "") if date_td else ""
        if not posted_at and date_td:
            posted_at = date_td.get_text(strip=True)

        view_td = row.select_one("td.gall_count")
        view_count = _to_int(view_td.get_text(strip=True) if view_td else "0")

        rec_td = row.select_one("td.gall_recommend")
        recommend_count = _to_int(rec_td.get_text(strip=True) if rec_td else "0")

        href = title_tag.get("href", "")
        if href.startswith("http"):
            url = href
        else:
            url = BASE_URL + href

        matched = keyword_match(title) or keyword

        posts.append({
            "id": post_id,
            "gallery_id": gallery_id,
            "post_no": post_no,
            "title": title,
            "body": None,
            "author": author,
            "posted_at": posted_at or None,
            "view_count": view_count,
            "recommend_count": recommend_count,
            "comment_count": 0,
            "url": url,
            "matched_keyword": matched,
        })
    return posts


def _to_int(s: str) -> int:
    s = re.sub(r"[^\d]", "", s)
    return int(s) if s else 0


def _has_next_page(html: str) -> bool:
    soup = BeautifulSoup(html, "lxml")
    # 다음 페이지 링크가 있으면 True
    next_link = soup.select_one("a.page_next") or soup.select_one(".paging a[class*='next']")
    return next_link is not None


def collect_gallery(gallery_id: str, session: requests.Session) -> list[dict]:
    """갤러리 하나에서 모든 키워드를 검색해 신규 글 목록 반환."""
    gallery = GALLERY_MAP.get(gallery_id)
    if not gallery:
        logger.error("알 수 없는 갤러리 ID: %s", gallery_id)
        return []

    is_minor = gallery["is_minor"]
    seen_ids: set[str] = set()
    new_posts: list[dict] = []

    for keyword in KEYWORDS:
        logger.info("[%s] 키워드 검색: '%s'", gallery_id, keyword)
        for page in range(1, MAX_PAGES + 1):
            url = _gallery_search_url(gallery_id, keyword, page, is_minor)
            try:
                resp = session.get(url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
            except requests.HTTPError as e:
                logger.warning("HTTP 오류 %s — %s", e.response.status_code, url)
                break
            except requests.RequestException as e:
                logger.warning("요청 실패: %s", e)
                break

            posts = _parse_post_list(resp.text, gallery_id, keyword)
            if not posts:
                logger.debug("[%s] '%s' p%d: 결과 없음", gallery_id, keyword, page)
                break

            added = 0
            for p in posts:
                if p["id"] in seen_ids:
                    continue
                seen_ids.add(p["id"])
                if post_exists(p["id"]):
                    continue
                new_posts.append(p)
                added += 1

            logger.info("[%s] '%s' p%d: %d개 신규", gallery_id, keyword, page, added)

            if not _has_next_page(resp.text):
                break

            time.sleep(REQUEST_DELAY)

        time.sleep(REQUEST_DELAY)

    logger.info("[%s] 총 신규 글: %d개", gallery_id, len(new_posts))
    return new_posts


def collect_all(session: requests.Session | None = None) -> list[dict]:
    """모든 갤러리 수집."""
    if session is None:
        session = requests.Session()
    all_posts = []
    for gallery in GALLERY_MAP.values():
        all_posts.extend(collect_gallery(gallery["id"], session))
        time.sleep(REQUEST_DELAY)
    return all_posts
