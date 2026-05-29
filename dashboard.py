"""
SQLite 데이터를 읽어 정적 HTML 대시보드를 생성합니다.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import db
from config import BASE_DIR, OUTPUT_DIR, GALLERIES

logger = logging.getLogger(__name__)

TEMPLATE_DIR = BASE_DIR / "templates"
OUTPUT_PATH = OUTPUT_DIR / "dashboard.html"


def build_dashboard():
    db.init_db()
    posts = db.get_posts_for_dashboard()
    stats = db.get_stats()

    galleries_map = {g["id"]: g["name"] for g in GALLERIES}

    # topic_tags JSON 문자열 → 리스트
    for p in posts:
        raw = p.get("topic_tags") or "[]"
        try:
            p["topic_tags_list"] = json.loads(raw)
        except Exception:
            p["topic_tags_list"] = []

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    tmpl = env.get_template("dashboard.html.j2")

    html = tmpl.render(
        posts=posts,
        stats=stats,
        galleries=GALLERIES,
        galleries_map=galleries_map,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    OUTPUT_PATH.write_text(html, encoding="utf-8")
    logger.info(f"대시보드 생성 완료: {OUTPUT_PATH} ({len(posts)}개 글)")
    return OUTPUT_PATH


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    path = build_dashboard()
    print(f"열기: file://{path.resolve()}")
