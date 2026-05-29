"""
전체 파이프라인 실행 진입점.

사용법:
  python run.py                     # 전체 갤러리 수집
  python run.py --gallery twitch    # 특정 갤러리만
  python run.py --no-classify       # Claude 분류 생략 (비용 절감 테스트)
  python run.py --dashboard-only    # 수집 없이 대시보드만 재생성
"""

import argparse
import logging
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run")


def main():
    parser = argparse.ArgumentParser(description="투네이션 디시 모니터")
    parser.add_argument("--gallery", help="특정 갤러리 ID만 수집")
    parser.add_argument("--no-classify", action="store_true", help="Claude 분류 생략")
    parser.add_argument("--dashboard-only", action="store_true", help="대시보드만 재생성")
    args = parser.parse_args()

    # DB 초기화
    os.makedirs("data", exist_ok=True)
    from db import init_db
    init_db()
    logger.info("DB 초기화 완료")

    if args.dashboard_only:
        from dashboard import generate
        generate()
        return

    # 1단계: 수집
    from collector import collect_gallery, collect_all
    session = requests.Session()

    if args.gallery:
        from config import GALLERY_MAP
        if args.gallery not in GALLERY_MAP:
            logger.error("알 수 없는 갤러리: %s (가능: %s)", args.gallery, list(GALLERY_MAP))
            sys.exit(1)
        new_posts = collect_gallery(args.gallery, session)
    else:
        new_posts = collect_all(session)

    logger.info("수집 완료: 신규 글 %d개", len(new_posts))

    if not new_posts:
        logger.info("신규 글 없음 — 대시보드 재생성만 진행")
        from dashboard import generate
        generate()
        return

    # 2단계: 본문+댓글 수집
    from fetcher import fetch_all
    from db import insert_post, insert_comments

    posts_with_comments: list[tuple[dict, list]] = []
    for post, comments in fetch_all(new_posts, session):
        insert_post(post)
        insert_comments(comments)
        posts_with_comments.append((post, comments))
        logger.info("저장: [%s] %s", post["id"], post["title"][:40])

    logger.info("본문+댓글 저장 완료: %d개", len(posts_with_comments))

    # 3단계: Claude 분류
    if not args.no_classify:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            logger.warning("ANTHROPIC_API_KEY 없음 — 분류 건너뜀. .env 파일을 확인하세요.")
        else:
            from classifier import classify_all
            from db import insert_classification
            clfs = classify_all(posts_with_comments)
            for clf in clfs:
                insert_classification(clf)
            logger.info("분류 완료: %d개", len(clfs))
    else:
        logger.info("--no-classify 옵션: 분류 생략")

    # 4단계: 대시보드 생성
    from dashboard import generate
    generate()


if __name__ == "__main__":
    main()
