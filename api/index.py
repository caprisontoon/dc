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

import threading

from flask import Flask, render_template_string, jsonify, request, redirect

import db

app = Flask(__name__)

# Vercel(클라우드)에서는 디시가 차단하므로 수집 불가. 로컬(PC)에서만 수집 버튼 노출.
IS_LOCAL = not bool(os.getenv("VERCEL"))

# 수집 진행 상태 (PC 로컬 실행 시)
_collect = {"running": False, "log": [], "started_at": None}


def _run_pipeline():
    _collect["running"] = True
    _collect["log"] = ["수집을 시작합니다..."]
    try:
        from collector import run_collector
        from fetcher import run_fetcher
        from classifier import run_classifier

        _collect["log"].append("갤러리에서 새 글을 검색하는 중...")
        new_posts = run_collector()
        _collect["log"].append(f"신규 글 {len(new_posts)}개 발견")

        if new_posts:
            _collect["log"].append("본문과 댓글을 수집하는 중... (몇 분 걸려요)")
            fetched = run_fetcher(new_posts)
            _collect["log"].append(f"{len(fetched)}개 글 저장 완료")
            run_classifier(fetched)
        _collect["log"].append("✅ 완료! 잠시 후 새로고침하면 반영됩니다.")
    except Exception as e:
        _collect["log"].append(f"❌ 오류: {e}")
    finally:
        _collect["running"] = False


def _load_template() -> str:
    path = Path(__file__).parent.parent / "templates" / "dashboard.html.j2"
    return path.read_text(encoding="utf-8")


@app.route("/")
def index():
    try:
        db.init_db()
        posts = db.get_posts_for_dashboard()
        stats = db.get_stats()
        galleries = db.get_galleries()
        galleries_map = {g["id"]: g["name"] for g in galleries}

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
            galleries=galleries,
            galleries_map=galleries_map,
            is_local=IS_LOCAL,
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


@app.route("/gallery/add", methods=["POST"])
def gallery_add():
    db.init_db()
    name = request.form.get("name", "")
    url = request.form.get("url", "")
    try:
        db.add_gallery(name, url)
    except Exception:
        pass
    return redirect("/")


@app.route("/gallery/delete", methods=["POST"])
def gallery_delete():
    db.init_db()
    gid = request.form.get("id", "")
    if gid:
        db.delete_gallery(gid)
    return redirect("/")


@app.route("/collect", methods=["POST"])
def collect():
    if not IS_LOCAL:
        return jsonify({"ok": False, "error": "클라우드에서는 수집할 수 없어요. PC에서 실행하세요."}), 400
    if not _collect["running"]:
        threading.Thread(target=_run_pipeline, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/collect/status")
def collect_status():
    return jsonify({"running": _collect["running"], "log": _collect["log"]})


@app.route("/api/stats")
def api_stats():
    db.init_db()
    return jsonify(db.get_stats())


@app.route("/health")
def health():
    return "ok"
