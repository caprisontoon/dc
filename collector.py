"""
갤러리 검색 결과 페이지에서 글 ID와 메타 정보만 수집.
본문/댓글은 fetcher.py에서.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Iterator

import requests
from bs4 import BeautifulSoup

from config import (
    DEFAULT_HEADERS,
    GALLERIES,
    KEYWORDS,
    MAX_PAGES_PER_GALLERY,
    REQUEST_SLEEP_SECONDS,
    gallery_list_url,
    gallery_view_url,
)

log = logging.getLogger(__name__)


@dataclass
class PostSummary:
    gallery_id: str
    post_no: int
    title: str
    author: str | None
    view_count: int | None
    recommend_count: int | None
    comment_count: int | None
    matched_keyword: str

    @property
    def post_id(self) -> str:
        return f"{self.gallery_id}_{self.post_no}"


def _http_get(url: str) -> requests.Response | None:
    """지수 백오프 재시도 포함 GET."""
    delay = 2.0
    for attempt in range(4):
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (403, 429):
                log.warning("차단 의심 응답 %s — %.1fs 대기 후 재시도", resp.status_code, delay)
                time.sleep(delay)
                delay *= 2
                continue
            log.warning("예상치 못한 상태코드 %s for %s", resp.status_code, url)
            return None
        except requests.RequestException as e:
            log.warning("요청 실패: %s (재시도 %d) — %.1fs 대기", e, attempt + 1, delay)
            time.sleep(delay)
            delay *= 2
    return None


def _parse_int(text: str | None) -> int | None:
    if not text:
        return None
    cleaned = re.sub(r"[^\d]", "", text)
    return int(cleaned) if cleaned else None


def parse_list_page(html: str, gallery_id: str, keyword: str) -> list[PostSummary]:
    """검색결과 페이지 HTML 파싱."""
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select("tr.ub-content.us-post")
    posts: list[PostSummary] = []
    for tr in rows:
        # 글 번호 셀
        num_cell = tr.select_one("td.gall_num")
        if not num_cell:
            continue
        num_text = num_cell.get_text(strip=True)
        if not num_text.isdigit():
            # "공지" 같은 비숫자 — 건너뛰기
            continue
        post_no = int(num_text)

        # 제목
        title_cell = tr.select_one("td.gall_tit a")
        if not title_cell:
            continue
        title = title_cell.get_text(strip=True)

        # 댓글수 (제목 옆 span.reply_num)
        reply_span = tr.select_one("td.gall_tit span.reply_num")
        comment_count = _parse_int(reply_span.get_text() if reply_span else None)

        # 작성자
        writer_cell = tr.select_one("td.gall_writer")
        author = writer_cell.get("data-nick") if writer_cell else None
        if not author and writer_cell:
            author = writer_cell.get_text(strip=True)

        # 조회/추천
        view_cell = tr.select_one("td.gall_count")
        recommend_cell = tr.select_one("td.gall_recommend")

        posts.append(
            PostSummary(
                gallery_id=gallery_id,
                post_no=post_no,
                title=title,
                author=author,
                view_count=_parse_int(view_cell.get_text() if view_cell else None),
                recommend_count=_parse_int(recommend_cell.get_text() if recommend_cell else None),
                comment_count=comment_count,
                matched_keyword=keyword,
            )
        )
    return posts


def collect_gallery(gallery: dict) -> Iterator[dict]:
    """한 갤러리에서 모든 키워드 × 페이지 순회. 중복은 제거."""
    seen: set[str] = set()
    for keyword in KEYWORDS:
        for page in range(1, MAX_PAGES_PER_GALLERY + 1):
            url = gallery_list_url(gallery, keyword, page=page)
            log.info("[%s] keyword=%s page=%d → GET %s", gallery["id"], keyword, page, url)
            resp = _http_get(url)
            if resp is None:
                break
            summaries = parse_list_page(resp.text, gallery["id"], keyword)
            log.info("[%s] keyword=%s page=%d → %d개 글 발견", gallery["id"], keyword, page, len(summaries))
            if not summaries:
                break
            for s in summaries:
                if s.post_id in seen:
                    continue
                seen.add(s.post_id)
                yield {
                    "id": s.post_id,
                    "gallery_id": s.gallery_id,
                    "post_no": s.post_no,
                    "title": s.title,
                    "author": s.author,
                    "view_count": s.view_count,
                    "recommend_count": s.recommend_count,
                    "comment_count": s.comment_count,
                    "matched_keyword": s.matched_keyword,
                    "url": gallery_view_url(gallery, s.post_no),
                }
            time.sleep(REQUEST_SLEEP_SECONDS)


def collect_all() -> Iterator[dict]:
    for g in GALLERIES:
        log.info("===== 갤러리 시작: %s (%s) =====", g["name"], g["id"])
        yield from collect_gallery(g)


if __name__ == "__main__":
    # 단독 실행: 트위치 갤러리만 시험 출력
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    test_gallery = next(g for g in GALLERIES if g["id"] == "twitch")
    for post in collect_gallery(test_gallery):
        print(post)
