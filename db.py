"""
SQLite 초기화 + 자주 쓰는 헬퍼.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterable

from config import DB_PATH, GALLERIES

SCHEMA = """
CREATE TABLE IF NOT EXISTS galleries (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    is_minor INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    gallery_id TEXT,
    post_no INTEGER,
    title TEXT,
    body TEXT,
    author TEXT,
    posted_at DATETIME,
    view_count INTEGER,
    recommend_count INTEGER,
    comment_count INTEGER,
    url TEXT,
    matched_keyword TEXT,
    collected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (gallery_id) REFERENCES galleries(id)
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT,
    author TEXT,
    body TEXT,
    posted_at DATETIME,
    parent_comment_id INTEGER,
    FOREIGN KEY (post_id) REFERENCES posts(id)
);

CREATE TABLE IF NOT EXISTS classifications (
    post_id TEXT PRIMARY KEY,
    is_relevant INTEGER,
    sentiment TEXT,
    summary TEXT,
    topic_tags TEXT,
    classified_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts(id)
);

CREATE INDEX IF NOT EXISTS idx_posts_gallery ON posts(gallery_id);
CREATE INDEX IF NOT EXISTS idx_posts_posted ON posts(posted_at);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id);
"""


@contextmanager
def connect():
    """with 구문으로 안전하게 SQLite 연결."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """테이블 만들고 갤러리 정보 채워넣기."""
    with connect() as conn:
        conn.executescript(SCHEMA)
        for g in GALLERIES:
            prefix = "mgallery/" if g["is_minor"] else ""
            base_url = f"https://gall.dcinside.com/{prefix}board"
            conn.execute(
                """
                INSERT INTO galleries (id, name, base_url, is_minor)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    base_url = excluded.base_url,
                    is_minor = excluded.is_minor
                """,
                (g["id"], g["name"], base_url, 1 if g["is_minor"] else 0),
            )


def post_exists(post_id: str) -> bool:
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM posts WHERE id = ?", (post_id,)
        ).fetchone()
        return row is not None


def insert_post(post: dict) -> None:
    """이미 있으면 무시 (INSERT OR IGNORE)."""
    with connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO posts (
                id, gallery_id, post_no, title, body, author, posted_at,
                view_count, recommend_count, comment_count, url, matched_keyword
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                post["id"],
                post["gallery_id"],
                post["post_no"],
                post.get("title"),
                post.get("body"),
                post.get("author"),
                post.get("posted_at"),
                post.get("view_count"),
                post.get("recommend_count"),
                post.get("comment_count"),
                post.get("url"),
                post.get("matched_keyword"),
            ),
        )


def insert_comments(post_id: str, comments: Iterable[dict]) -> None:
    """글에 달린 댓글 목록 저장. 기존 댓글 다시 가져왔을 수 있어 전부 지우고 다시 넣음."""
    with connect() as conn:
        conn.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
        for c in comments:
            conn.execute(
                """
                INSERT INTO comments (post_id, author, body, posted_at, parent_comment_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    post_id,
                    c.get("author"),
                    c.get("body"),
                    c.get("posted_at"),
                    c.get("parent_comment_id"),
                ),
            )


def upsert_classification(post_id: str, result: dict) -> None:
    """Claude 분류 결과 저장."""
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO classifications (post_id, is_relevant, sentiment, summary, topic_tags)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(post_id) DO UPDATE SET
                is_relevant = excluded.is_relevant,
                sentiment = excluded.sentiment,
                summary = excluded.summary,
                topic_tags = excluded.topic_tags,
                classified_at = CURRENT_TIMESTAMP
            """,
            (
                post_id,
                1 if result.get("is_relevant") else 0,
                result.get("sentiment"),
                result.get("summary"),
                json.dumps(result.get("topic_tags", []), ensure_ascii=False),
            ),
        )


def posts_pending_classification(limit: int | None = None) -> list[sqlite3.Row]:
    """아직 분류 안 된 글 가져오기."""
    sql = """
        SELECT p.*
        FROM posts p
        LEFT JOIN classifications c ON c.post_id = p.id
        WHERE c.post_id IS NULL
        ORDER BY p.collected_at DESC
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    with connect() as conn:
        return conn.execute(sql).fetchall()


def top_comments_for_post(post_id: str, limit: int = 5) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            """
            SELECT * FROM comments
            WHERE post_id = ? AND parent_comment_id IS NULL
            ORDER BY id ASC
            LIMIT ?
            """,
            (post_id, limit),
        ).fetchall()


def all_posts_for_dashboard() -> list[dict]:
    """대시보드에 보여줄 데이터 전체 — 분류 정보까지 조인."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                p.*,
                g.name AS gallery_name,
                c.is_relevant,
                c.sentiment,
                c.summary,
                c.topic_tags
            FROM posts p
            LEFT JOIN galleries g ON g.id = p.gallery_id
            LEFT JOIN classifications c ON c.post_id = p.id
            ORDER BY p.posted_at DESC NULLS LAST, p.collected_at DESC
            """
        ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["topic_tags"] = json.loads(d["topic_tags"]) if d.get("topic_tags") else []
        except (TypeError, ValueError):
            d["topic_tags"] = []
        results.append(d)
    return results
