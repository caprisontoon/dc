"""
Vercel 서버리스 Flask 앱 — 대시보드 웹 서버.
"""
import json
import sys
import os
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template_string, jsonify
import db
from config import GALLERIES

app = Flask(__name__)


def _load_template() -> str:
    path = Path(__file__).parent.parent / "templates" / "dashboard.html.j2"
    return path.read_text(encoding="utf-8")


@app.route("/")
def index():
    try:
        db.init_db()
        posts = db.get_posts_for_dashboard()
        stats = db.get_stats()
        galleries_map = {g["id"]: g["name"] for g in GALLERIES}

        for p in posts:
            raw = p.get("topic_tags") or "[]"
            try:
                p["topic_tags_list"] = json.loads(raw)
            except Exception:
                p["topic_tags_list"] = []

        return render_template_string(
            _load_template(),
            posts=posts,
            stats=stats,
            galleries=GALLERIES,
            galleries_map=galleries_map,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
    except Exception as e:
        import traceback
        return (
            "<h2>오류가 발생했습니다</h2><pre>"
            + traceback.format_exc()
            + "</pre>",
            500,
        )


@app.route("/api/stats")
def api_stats():
    db.init_db()
    return jsonify(db.get_stats())


@app.route("/health")
def health():
    return "ok"
