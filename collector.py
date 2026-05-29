"""
갤러리 검색 결과 페이지에서 신규 글 ID 목록을 수집합니다.
"""
import re
import time
import logging
from urllib.parse import urlencode, quote

import requests
from bs4 import BeautifulSoup

import db
from config import GALLERIES, KEYWORDS, KEYWORD_PATTERNS, HEADERS, SEARCH_PAGES, REQUEST_DELAY

logger = logging.getLogger(__name__)


def _search_url(gallery_id: str, is_minor: bool, keyword: str, page: int = 1) -> str:
    board = "mgallery" if is_minor else "board"
    params = {
        "id": gallery_id,
        "s_type": "search_subject_memo",
        "s_keyword": keyword,
        "page": page,
    }
    return f"https://gall.dcinside.com/{board}/lists/?{urlencode(params, encoding='utf-8')}"


def _parse_post_list(html: str, gallery_id: str) -> list[dict]:
    """게시글 목록 HTML에서 글 정보를 파싱합니다."""
    soup = BeautifulSoup(html, "lxml")
    posts = []

    # 디시인사이드 글 목록 테이블: class="gall_list"
    table = soup.find("table", class_="gall_list")
    if not table:
        logger.warning("gall_list 테이블을 찾지 못했습니다.")
        return posts

    for tr in table.find_all("tr", class_=re.compile(r"ub-content")):
        try:
            # 공지/광고 행 제외
            num_td = tr.find("td", class_="gall_num")
            if not num_td:
                continue
            num_text = num_td.get_text(strip=True)
            if not num_text.isdigit():
                continue
            post_no = int(num_text)

            title_td = tr.find("td", class_="gall_tit")
            if not title_td:
                continue
            a_tag = title_td.find("a", href=True)
            if not a_tag:
                continue

            title = a_tag.get_text(strip=True)
            href = a_tag["href"]

            # 댓글수 괄호 제거
            title = re.sub(r"\s*\[\d+\]\s*$", "", title)

            # URL 재구성
            if href.startswith("/"):
                url = "https://gall.dcinside.com" + href
            else:
                url = href

            # author
            author_td = tr.find("td", class_="gall_writer")
            author = ""
            if author_td:
                nick = author_td.find(class_=re.compile(r"nick|writer_nikname"))
                author = nick.get_text(strip=True) if nick else author_td.get_text(strip=True)

            # 날짜
            date_td = tr.find("td", class_="gall_date")
            posted_at = date_td["title"] if date_td and date_td.get("title") else (
                date_td.get_text(strip=True) if date_td else ""
            )

            # 조회/추천
            view_td = tr.find("td", class_="gall_count")
            recommend_td = tr.find("td", class_="gall_recommend")
            view_count = int(view_td.get_text(strip=True) or 0) if view_td else 0
            recommend_count = int(recommend_td.get_text(strip=True) or 0) if recommend_td else 0

            posts.append({
                "gallery_id": gallery_id,
                "post_no": post_no,
                "title": title,
                "author": author,
                "posted_at": posted_at,
                "view_count": view_count,
                "recommend_count": recommend_count,
                "url": url,
            })
        except Exception as e:
            logger.debug(f"행 파싱 오류: {e}")
            continue

    return posts


def _keyword_match(text: str) -> str | None:
    """텍스트에서 매칭된 첫 번째 키워드 반환, 없으면 None."""
    # 투네이션/투네아를 먼저 검사 (투네보다 긴 패턴 우선)
    for kw in ["투네이션", "투네아", "투네", "tooneation", "toon.at"]:
        pattern = KEYWORD_PATTERNS[kw]
        if re.search(pattern, text, re.IGNORECASE):
            return kw
    return None


def collect_gallery(gallery: dict, session: requests.Session) -> list[dict]:
    """갤러리 1곳에서 모든 키워드 검색 후 신규 글 목록 반환."""
    gid = gallery["id"]
    is_minor = gallery["is_minor"]
    found: dict[str, dict] = {}  # post_id → post_info (중복 제거)

    for keyword in KEYWORDS:
        for page in range(1, SEARCH_PAGES + 1):
            url = _search_url(gid, is_minor, keyword, page)
            try:
                resp = session.get(url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
            except requests.HTTPError as e:
                logger.warning(f"HTTP 오류 {e} — {url}")
                break
            except requests.RequestException as e:
                logger.warning(f"요청 실패 {e} — {url}")
                break

            posts = _parse_post_list(resp.text, gid)
            if not posts:
                break  # 결과 없으면 다음 키워드로

            for p in posts:
                pid = f"{gid}_{p['post_no']}"
                if pid in found or db.post_exists(pid):
                    continue
                matched = _keyword_match(p["title"])
                p["id"] = pid
                p["matched_keyword"] = matched or keyword
                found[pid] = p

            time.sleep(REQUEST_DELAY)

    logger.info(f"[{gid}] 신규 글 {len(found)}개 발견")
    return list(found.values())


def run_collector() -> list[dict]:
    """전체 갤러리 순회하여 신규 글 목록 반환."""
    db.init_db()
    session = requests.Session()
    all_posts = []
    for gallery in GALLERIES:
        posts = collect_gallery(gallery, session)
        all_posts.extend(posts)
    return all_posts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    posts = run_collector()
    for p in posts:
        print(f"[{p['gallery_id']}] #{p['post_no']} {p['title']} ({p['matched_keyword']})")
    print(f"\n총 {len(posts)}개 신규 글")
