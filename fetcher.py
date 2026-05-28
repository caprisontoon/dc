"""
글 상세 페이지에서 본문과 댓글을 가져온다.
- 본문: 글 페이지 HTML에서 바로 파싱
- 댓글: 디시는 댓글을 별도 AJAX(`/board/comment/`)로 가져옴
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

from config import DEFAULT_HEADERS, REQUEST_SLEEP_SECONDS, gallery_view_url

log = logging.getLogger(__name__)

COMMENT_AJAX_URL = "https://gall.dcinside.com/board/comment/"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    return s


def _get(session: requests.Session, url: str, referer: str | None = None) -> requests.Response | None:
    headers = {}
    if referer:
        headers["Referer"] = referer
    delay = 2.0
    for attempt in range(4):
        try:
            resp = session.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (403, 429):
                log.warning("차단 의심 %s, %.1fs 대기", resp.status_code, delay)
                time.sleep(delay)
                delay *= 2
                continue
            return None
        except requests.RequestException as e:
            log.warning("GET 실패: %s (재시도 %d)", e, attempt + 1)
            time.sleep(delay)
            delay *= 2
    return None


def _post(
    session: requests.Session,
    url: str,
    data: dict,
    referer: str,
) -> requests.Response | None:
    headers = {
        "Referer": referer,
        "X-Requested-With": "XMLHttpRequest",
    }
    delay = 2.0
    for attempt in range(4):
        try:
            resp = session.post(url, data=data, headers=headers, timeout=15)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (403, 429):
                time.sleep(delay)
                delay *= 2
                continue
            return None
        except requests.RequestException as e:
            log.warning("POST 실패: %s (재시도 %d)", e, attempt + 1)
            time.sleep(delay)
            delay *= 2
    return None


def parse_post_body(html: str) -> dict[str, Any]:
    """글 상세 페이지에서 본문/메타 추출."""
    soup = BeautifulSoup(html, "lxml")

    # 본문
    body_el = soup.select_one("div.write_div")
    body = body_el.get_text("\n", strip=True) if body_el else ""

    # 작성일
    posted_at = None
    date_el = soup.select_one(".gall_date") or soup.select_one(".fl span.gall_date")
    if date_el:
        posted_at = date_el.get("title") or date_el.get_text(strip=True)

    # 조회/추천 (숫자 추출)
    def _num(selector: str) -> int | None:
        el = soup.select_one(selector)
        if not el:
            return None
        digits = re.sub(r"[^\d]", "", el.get_text())
        return int(digits) if digits else None

    return {
        "body": body,
        "posted_at": posted_at,
        "view_count": _num(".gall_count") or _num(".view_content_wrap .gall_count"),
        "recommend_count": _num(".up_num") or _num(".gall_recommend"),
    }


def fetch_comments(
    session: requests.Session,
    gallery_id: str,
    post_no: int,
    referer: str,
    is_minor: bool,
) -> list[dict]:
    """디시 AJAX 댓글 엔드포인트로 댓글 전부 긁어오기.

    응답 형식은 종종 바뀌므로 JSON / HTML 둘 다 대비.
    """
    all_comments: list[dict] = []
    page = 1
    while True:
        data = {
            "id": gallery_id,
            "no": str(post_no),
            "cmt_id": gallery_id,
            "cmt_no": str(post_no),
            "focus_cno": "",
            "focus_pno": "",
            "e_s_n_o": "3eabc219ebdd65f53d",  # 디시 내부 토큰 (없어도 되는 경우 많음)
            "comment_page": str(page),
            "sort": "",
            "prevCnt": "0",
            "board_type": "" if is_minor else "",
        }
        resp = _post(session, COMMENT_AJAX_URL, data, referer=referer)
        if resp is None:
            break
        try:
            payload = resp.json()
        except ValueError:
            log.debug("댓글 응답이 JSON이 아님 — 빈 댓글로 처리")
            break

        comments = payload.get("comments") or []
        if not comments:
            break

        for c in comments:
            # type이 "dccon"(디시콘), "voice"(음성) 등이면 본문 비어있을 수 있음
            body = c.get("memo", "") or ""
            body = BeautifulSoup(body, "lxml").get_text("\n", strip=True)
            all_comments.append(
                {
                    "author": c.get("name") or c.get("user_id"),
                    "body": body,
                    "posted_at": c.get("reg_date") or c.get("date"),
                    "parent_comment_id": c.get("parent") if c.get("parent") not in (None, "0", 0) else None,
                }
            )

        total_cnt = int(payload.get("total_cnt", 0) or 0)
        if len(all_comments) >= total_cnt:
            break
        page += 1
        time.sleep(0.8)
        if page > 50:
            log.warning("댓글 페이지 50 초과 — 중단")
            break

    return all_comments


def fetch_post(post_summary: dict, gallery: dict) -> dict | None:
    """글 본문+댓글까지 한 번에. 실패하면 None."""
    session = _session()
    view_url = gallery_view_url(gallery, post_summary["post_no"])
    resp = _get(session, view_url)
    if resp is None:
        log.warning("본문 가져오기 실패: %s", view_url)
        return None

    parsed = parse_post_body(resp.text)
    time.sleep(REQUEST_SLEEP_SECONDS)

    comments = fetch_comments(
        session=session,
        gallery_id=gallery["id"],
        post_no=post_summary["post_no"],
        referer=view_url,
        is_minor=gallery["is_minor"],
    )
    time.sleep(REQUEST_SLEEP_SECONDS)

    return {
        **post_summary,
        **parsed,
        "url": view_url,
        "comments": comments,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # 수동 디버깅용
    from config import GALLERIES
    test_gallery = next(g for g in GALLERIES if g["id"] == "twitch")
    summary = {"post_no": 100, "gallery_id": "twitch", "title": "테스트"}
    result = fetch_post(summary, test_gallery)
    print(result)
