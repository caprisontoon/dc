"""
개별 글의 본문과 댓글을 수집합니다.
디시인사이드 댓글은 별도 AJAX 엔드포인트로 불러옵니다.
"""
import re
import time
import json
import logging

import requests
from bs4 import BeautifulSoup

import db
from config import HEADERS, REQUEST_DELAY

logger = logging.getLogger(__name__)

COMMENT_API = "https://gall.dcinside.com/board/comment/"
COMMENT_API_MINOR = "https://gall.dcinside.com/mgallery/board/comment/"


def _fetch_body(session: requests.Session, url: str) -> dict:
    """글 본문 파싱."""
    resp = session.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    # 본문 영역
    body_div = (
        soup.find("div", class_="write_div")
        or soup.find("div", class_="gallview_contents")
        or soup.find("div", class_=re.compile(r"writing_view_box"))
    )
    body_text = body_div.get_text("\n", strip=True) if body_div else ""

    # 메타 정보
    info_box = soup.find("div", class_="gall_writer")

    # 조회수
    view_span = soup.find("span", class_=re.compile(r"gall_count|view_count"))
    view_count = 0
    if view_span:
        m = re.search(r"\d+", view_span.get_text())
        view_count = int(m.group()) if m else 0

    # 추천수
    recommend_el = soup.find(id=re.compile(r"recommend_cnt|up_num"))
    recommend_count = 0
    if recommend_el:
        m = re.search(r"\d+", recommend_el.get_text())
        recommend_count = int(m.group()) if m else 0

    # 댓글수
    comment_cnt_el = soup.find(class_=re.compile(r"cmt_cnt|comment_cnt"))
    comment_count = 0
    if comment_cnt_el:
        m = re.search(r"\d+", comment_cnt_el.get_text())
        comment_count = int(m.group()) if m else 0

    # 갤러리 ID와 글번호를 URL에서 추출
    gall_id_m = re.search(r"[?&]id=([^&]+)", url)
    no_m = re.search(r"[?&]no=(\d+)", url)
    gall_id = gall_id_m.group(1) if gall_id_m else ""
    post_no = int(no_m.group(1)) if no_m else 0

    return {
        "body": body_text,
        "view_count": view_count,
        "recommend_count": recommend_count,
        "comment_count": comment_count,
        "_gall_id": gall_id,
        "_post_no": post_no,
        "_html": resp.text,  # 댓글 AJAX에 필요한 e_s_n_o 토큰 추출용
    }


def _extract_e_s_n_o(html: str) -> str:
    """CSRF 토큰(e_s_n_o) 추출."""
    m = re.search(r"'e_s_n_o'\s*:\s*'([^']+)'", html)
    if not m:
        m = re.search(r'"e_s_n_o"\s*:\s*"([^"]+)"', html)
    return m.group(1) if m else ""


def _fetch_comments(
    session: requests.Session,
    gall_id: str,
    post_no: int,
    is_minor: bool,
    e_s_n_o: str,
) -> list[dict]:
    """댓글 AJAX API 호출."""
    api_url = COMMENT_API_MINOR if is_minor else COMMENT_API
    headers = {
        **HEADERS,
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://gall.dcinside.com",
    }

    comments = []
    page = 1
    while True:
        data = {
            "id": gall_id,
            "no": str(post_no),
            "cmt_id": gall_id,
            "cmt_no": str(post_no),
            "e_s_n_o": e_s_n_o,
            "comment_page": str(page),
        }
        try:
            resp = session.post(api_url, data=data, headers=headers, timeout=15)
            resp.raise_for_status()
            result = resp.json()
        except Exception as e:
            logger.debug(f"댓글 API 실패 (page {page}): {e}")
            break

        if not isinstance(result, dict):
            break

        comment_list = result.get("comments", [])
        if not comment_list:
            break

        for c in comment_list:
            parent_id = c.get("parent", None)
            comments.append({
                "author": c.get("name", ""),
                "body": BeautifulSoup(c.get("memo", ""), "lxml").get_text("\n", strip=True),
                "posted_at": c.get("reg_date", ""),
                "parent_comment_id": int(parent_id) if parent_id else None,
            })

        # 마지막 페이지 확인
        total_pages = int(result.get("total_page", 1))
        if page >= total_pages:
            break
        page += 1
        time.sleep(1)

    return comments


def fetch_post(post_info: dict, session: requests.Session) -> dict | None:
    """글 1개 전체 수집 후 DB 저장. 실패 시 None 반환."""
    pid = post_info["id"]
    url = post_info["url"]
    is_minor = "/mgallery/" in url

    try:
        body_data = _fetch_body(session, url)
    except Exception as e:
        logger.warning(f"본문 수집 실패 [{pid}]: {e}")
        return None

    post = {
        **post_info,
        "body": body_data["body"],
        "view_count": body_data.get("view_count") or post_info.get("view_count", 0),
        "recommend_count": body_data.get("recommend_count") or post_info.get("recommend_count", 0),
        "comment_count": body_data.get("comment_count") or post_info.get("comment_count", 0),
    }
    # fetcher 내부 키 제거
    for k in ("_gall_id", "_post_no", "_html"):
        post.pop(k, None)

    db.save_post(post)

    # 댓글 수집
    e_s_n_o = _extract_e_s_n_o(body_data["_html"])
    gall_id = body_data["_gall_id"] or post_info["gallery_id"]
    post_no = body_data["_post_no"] or post_info["post_no"]

    time.sleep(REQUEST_DELAY)
    comments = _fetch_comments(session, gall_id, post_no, is_minor, e_s_n_o)
    db.save_comments(pid, comments)
    logger.info(f"저장 완료 [{pid}] 댓글 {len(comments)}개")

    post["comments"] = comments
    return post


def run_fetcher(posts: list[dict]) -> list[dict]:
    """수집된 글 목록에서 본문+댓글 가져오기."""
    session = requests.Session()
    results = []
    for p in posts:
        result = fetch_post(p, session)
        if result:
            results.append(result)
        time.sleep(REQUEST_DELAY)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # 테스트: DB에서 최근 글 1개 가져와서 본문 출력
    import db as _db
    _db.init_db()
    with _db.get_conn() as conn:
        row = conn.execute("SELECT * FROM posts LIMIT 1").fetchone()
    if row:
        post = dict(row)
        session = requests.Session()
        result = fetch_post(post, session)
        if result:
            print(f"제목: {result['title']}")
            print(f"본문 앞 200자: {result['body'][:200]}")
            print(f"댓글 수: {len(result['comments'])}")
    else:
        print("DB에 글이 없습니다. collector.py를 먼저 실행하세요.")
