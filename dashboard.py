"""
SQLite DB 읽어서 정적 HTML 대시보드 생성.
"""

import os
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

from config import OUTPUT_PATH, TEMPLATE_PATH
from db import fetch_posts_for_dashboard, fetch_gallery_stats


def generate():
    posts = fetch_posts_for_dashboard()
    gallery_stats = fetch_gallery_stats()

    total = len(posts)
    relevant = sum(1 for p in posts if p.get("is_relevant") != 0)
    pos = sum(1 for p in posts if p.get("sentiment") == "긍정" and p.get("is_relevant") != 0)
    neu = sum(1 for p in posts if p.get("sentiment") == "중립" and p.get("is_relevant") != 0)
    neg = sum(1 for p in posts if p.get("sentiment") == "부정" and p.get("is_relevant") != 0)

    template_dir = os.path.dirname(TEMPLATE_PATH)
    template_file = os.path.basename(TEMPLATE_PATH)
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
    tmpl = env.get_template(template_file)

    html = tmpl.render(
        posts=posts,
        gallery_stats=gallery_stats,
        total_posts=total,
        relevant_posts=relevant,
        pos_count=pos,
        neu_count=neu,
        neg_count=neg,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"대시보드 생성 완료: {OUTPUT_PATH}  (총 {total}개 글, 관련 {relevant}개)")


if __name__ == "__main__":
    generate()
