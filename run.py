"""
전체 파이프라인 진입점:
  1) DB 초기화
  2) 갤러리 순회하며 신규 글 ID 수집
  3) 신규 글 본문 + 댓글 가져오기
  4) Claude로 분류
  5) HTML 대시보드 생성
"""
from __future__ import annotations

import logging
import time

from classifier import classify_post
from collector import collect_all
from config import GALLERIES, REQUEST_SLEEP_SECONDS
from dashboard import render_dashboard
from db import (
    init_db,
    insert_comments,
    insert_post,
    post_exists,
    posts_pending_classification,
    top_comments_for_post,
    upsert_classification,
)
from fetcher import fetch_post

log = logging.getLogger(__name__)


def _gallery_by_id(gallery_id: str) -> dict | None:
    return next((g for g in GALLERIES if g["id"] == gallery_id), None)


def step_collect_and_fetch() -> int:
    """검색 → 신규 글 본문/댓글까지 DB에 저장. 새로 받은 글 수 반환."""
    new_count = 0
    for summary in collect_all():
        if post_exists(summary["id"]):
            log.info("이미 수집된 글, 건너뜀: %s", summary["id"])
            continue

        gallery = _gallery_by_id(summary["gallery_id"])
        if gallery is None:
            log.warning("알 수 없는 갤러리: %s", summary["gallery_id"])
            continue

        log.info("새 글 가져오기: %s — %s", summary["id"], summary.get("title", ""))
        detail = fetch_post(summary, gallery)
        if detail is None:
            log.warning("본문 가져오기 실패, 건너뜀: %s", summary["id"])
            continue

        comments = detail.pop("comments", [])
        insert_post(detail)
        insert_comments(detail["id"], comments)
        new_count += 1
        time.sleep(REQUEST_SLEEP_SECONDS)
    return new_count


def step_classify() -> int:
    """아직 분류 안 된 글 모두 Claude로 분류."""
    rows = posts_pending_classification()
    log.info("분류 대기 글 %d개", len(rows))
    classified = 0
    for row in rows:
        post = dict(row)
        comments = [dict(c) for c in top_comments_for_post(post["id"], limit=5)]
        log.info("분류 중: %s", post["id"])
        result = classify_post(post, comments)
        upsert_classification(post["id"], result)
        classified += 1
    return classified


def run_all() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    log.info("=== 1) DB 초기화 ===")
    init_db()

    log.info("=== 2~3) 수집 + 본문/댓글 가져오기 ===")
    new_count = step_collect_and_fetch()
    log.info("새로 수집한 글: %d개", new_count)

    log.info("=== 4) Claude 분류 ===")
    classified = step_classify()
    log.info("분류한 글: %d개", classified)

    log.info("=== 5) 대시보드 생성 ===")
    render_dashboard()
    log.info("완료! output/dashboard.html 을 브라우저로 열어보세요.")


if __name__ == "__main__":
    run_all()
