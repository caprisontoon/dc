"""
SQLite에서 데이터 읽어 정적 HTML 대시보드 생성.
필터/정렬은 클라이언트 JS가 담당.
"""
from __future__ import annotations

import datetime as dt
import logging
from collections import Counter

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import DASHBOARD_HTML, GALLERIES, TEMPLATE_DIR
from db import all_posts_for_dashboard

log = logging.getLogger(__name__)


def render_dashboard() -> None:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml", "j2"]),
    )
    template = env.get_template("dashboard.html.j2")

    posts = all_posts_for_dashboard()
    relevant_count = sum(1 for p in posts if p.get("is_relevant"))
    sentiment_counts = Counter(
        p.get("sentiment") or "중립" for p in posts if p.get("is_relevant")
    )
    for s in ("긍정", "중립", "부정"):
        sentiment_counts.setdefault(s, 0)

    html = template.render(
        posts=posts,
        galleries=GALLERIES,
        generated_at=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        relevant_count=relevant_count,
        sentiment_counts=sentiment_counts,
    )

    DASHBOARD_HTML.parent.mkdir(exist_ok=True)
    DASHBOARD_HTML.write_text(html, encoding="utf-8")
    log.info("대시보드 생성: %s", DASHBOARD_HTML)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    render_dashboard()
