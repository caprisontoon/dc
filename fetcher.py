"""
글 본문과 댓글을 수집.

디시 본문 HTML 구조:
  <div class="write_div"> 또는 <div class="s_write"> 안에 본문

댓글은 AJAX 엔드포인트:
  POST https://gall.dcinside.com/board/comment/
  Form: id={gallery_id}&no={post_no}&com_page=1&_rp_c=10
  (또는 GET /board/comment/ 파라미터로도 동작)
  응답: HTML fragment
"""

import time
import logging
import re

import requests
from bs4 import BeautifulSoup

from config import HEADERS, REQUEST_DELAY, BASE_URL, GALLERY_MAP

logger = logging.getLogger(__name__)


def _fetch_body(soup: BeautifulSoup) -> str:
    """본문 텍스트 추출."""
    for selector in ("div.write_div", "div.s_write", "div#thum_su", "div.gallview_head"):
        el = soup.select_one(selector)
        if el:
            return el.get_text(separator="\n", strip=True)
    # fallback: 본문 영역 추측
    el = soup.select_one("div.gallview_contents")
    return el.get_text(separator="\n", strip=True) if el else ""


def _fetch_comment_count(soup: BeautifulSoup) -> int:
    el = soup.select_one("span.cmt_count") or soup.select_one(".gall_comment_count")
    if el:
        text = re.sub(r"[^\d]", "", el.get_text())
        return int(text) if text else 0
    return 0


def _parse_comments(html: str, post_id: str) -> list[dict]:
    """댓글 HTML fragment 파싱."""
    soup = BeautifulSoup(html, "lxml")
    comments = []
    for li in soup.select("li.ub-content"):
        cmt_id_raw = li.get("data-no", "")
        parent_raw = li.get("data-parent_no", "")

        author_el = li.select_one("span.nickname") or li.select_one(".writer_nikcon")
        author = author_el.get_text(strip=True) if author_el else ""

        body_el = li.select_one("p.usertxt") or li.select_one(".usertxt")
        body = body_el.get_text(separator=" ", strip=True) if body_el else ""

        date_el = li.select_one("span.date_time")
        posted_at = date_el.get_text(strip=True) if date_el else None

        comments.append({
            "post_id": post_id,
            "author": author,
            "body": body,
            "posted_at": posted_at,
            "parent_comment_id": int(parent_raw) if parent_raw.isdigit() else None,
        })
    return comments


def fetch_post(post_meta: dict, session: requests.Session) -> dict | None:
    """
    글 URL에서 본문+댓글 수집 후 post_meta에 병합해 반환.
    실패 시 None.
    """
    url = post_meta["url"]
    gallery_id = post_meta["gallery_id"]
    post_no = post_meta["post_no"]
    post_id = post_meta["id"]
    is_minor = GALLERY_MAP.get(gallery_id, {}).get("is_minor", False)

    try:
        resp = session.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("본문 수집 실패 [%s]: %s", post_id, e)
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    body = _fetch_body(soup)
    comment_count = _fetch_comment_count(soup)

    # 댓글 AJAX 수집
    board = "mgallery/board" if is_minor else "board"
    comment_url = f"{BASE_URL}/{board}/comment/"
    comments = []
    try:
        time.sleep(0.5)
        cmt_resp = session.post(
            comment_url,
            data={"id": gallery_id, "no": post_no, "com_page": 1, "_rp_c": 20},
            headers={**HEADERS, "X-Requested-With": "XMLHttpRequest",
                     "Referer": url},
            timeout=15,
        )
        if cmt_resp.ok:
            comments = _parse_comments(cmt_resp.text, post_id)
    except requests.RequestException as e:
        logger.warning("댓글 수집 실패 [%s]: %s", post_id, e)

    result = {
        **post_meta,
        "body": body,
        "comment_count": comment_count or len(comments),
    }
    return result, comments


def fetch_all(post_metas: list[dict], session: requests.Session | None = None):
    """
    여러 글의 본문+댓글 수집.
    Yields (post_dict, comments_list) 튜플.
    """
    if session is None:
        session = requests.Session()
    for meta in post_metas:
        result = fetch_post(meta, session)
        if result is None:
            continue
        post, comments = result
        yield post, comments
        time.sleep(REQUEST_DELAY)
