"""
전체 파이프라인 실행: collect → fetch → classify → dashboard
"""
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("run.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def main():
    import db
    from collector import run_collector
    from fetcher import run_fetcher
    from classifier import run_classifier
    from dashboard import build_dashboard

    logger.info("=== 투네이션 디시 모니터링 시작 ===")

    db.init_db()

    logger.info("[1/4] 갤러리 검색 — 신규 글 ID 수집")
    new_posts = run_collector()
    logger.info(f"  → 신규 글 {len(new_posts)}개")

    if new_posts:
        logger.info("[2/4] 본문 + 댓글 수집")
        fetched = run_fetcher(new_posts)
        logger.info(f"  → {len(fetched)}개 저장")

        logger.info("[3/4] Claude API 분류")
        run_classifier(fetched)
    else:
        logger.info("[2-3/4] 신규 글 없음 — 건너뜀")

    logger.info("[4/4] 대시보드 생성")
    output_path = build_dashboard()
    logger.info(f"  → {output_path}")

    logger.info("=== 완료 ===")
    print(f"\n대시보드: file://{output_path.resolve()}")


if __name__ == "__main__":
    main()
