"""
PostgreSQL 기반 DB 헬퍼 (Supabase 연결).
로컬 테스트용으로 DATABASE_URL이 없으면 SQLite 폴백.
"""
import json
import os
import sqlite3
from contextlib import contextmanager

from config import GALLERIES

DATABASE_URL = os.getenv("DATABASE_URL", "")
_USE_PG = bool(DATABASE_URL)

# ── PostgreSQL 스키마 ────────────────────────────────────────────────────────
PG_SCHEMA = """
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
    posted_at TEXT,
    view_count INTEGER,
    recommend_count INTEGER,
    comment_count INTEGER,
    url TEXT,
    matched_keyword TEXT,
    collected_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS comments (
    id SERIAL PRIMARY KEY,
    post_id TEXT,
    author TEXT,
    body TEXT,
    posted_at TEXT,
    parent_comment_id INTEGER
);
CREATE TABLE IF NOT EXISTS classifications (
    post_id TEXT PRIMARY KEY,
    is_relevant INTEGER,
    sentiment TEXT,
    summary TEXT,
    topic_tags TEXT,
    classified_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_posts_gallery ON posts(gallery_id);
CREATE INDEX IF NOT EXISTS idx_posts_posted  ON posts(posted_at);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id);
"""

# ── SQLite 스키마 (로컬 폴백) ─────────────────────────────────────────────
SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS galleries (
    id TEXT PRIMARY KEY, name TEXT NOT NULL,
    base_url TEXT NOT NULL, is_minor INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY, gallery_id TEXT, post_no INTEGER,
    title TEXT, body TEXT, author TEXT, posted_at DATETIME,
    view_count INTEGER, recommend_count INTEGER, comment_count INTEGER,
    url TEXT, matched_keyword TEXT,
    collected_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT, post_id TEXT,
    author TEXT, body TEXT, posted_at DATETIME, parent_comment_id INTEGER
);
CREATE TABLE IF NOT EXISTS classifications (
    post_id TEXT PRIMARY KEY, is_relevant INTEGER, sentiment TEXT,
    summary TEXT, topic_tags TEXT,
    classified_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_posts_gallery ON posts(gallery_id);
CREATE INDEX IF NOT EXISTS idx_posts_posted  ON posts(posted_at);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id);
"""


# ── 연결 컨텍스트 매니저 ────────────────────────────────────────────────────
@contextmanager
def get_conn():
    if _USE_PG:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        from config import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _execute(conn, sql: str, params=None):
    """PostgreSQL(%s) / SQLite(?) 플레이스홀더 통일."""
    if _USE_PG:
        sql = sql.replace("?", "%s")
    cur = conn.cursor()
    if params:
        cur.execute(sql, params)
    else:
        cur.execute(sql)
    return cur


def _fetchall(cur) -> list[dict]:
    if _USE_PG:
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    return [dict(r) for r in cur.fetchall()]


def _fetchone(cur):
    if _USE_PG:
        row = cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))
    row = cur.fetchone()
    return dict(row) if row else None


# ── 초기화 ───────────────────────────────────────────────────────────────────
def init_db():
    with get_conn() as conn:
        if _USE_PG:
            cur = conn.cursor()
            for stmt in PG_SCHEMA.split(";"):
                stmt = stmt.strip()
                if stmt:
                    cur.execute(stmt)
        else:
            conn.executescript(SQLITE_SCHEMA)
        _seed_galleries(conn)


def _seed_galleries(conn):
    for g in GALLERIES:
        base_url = (
            f"https://gall.dcinside.com/mgallery/board/lists/?id={g['id']}"
            if g["is_minor"]
            else f"https://gall.dcinside.com/board/lists/?id={g['id']}"
        )
        if _USE_PG:
            _execute(
                conn,
                "INSERT INTO galleries (id, name, base_url, is_minor) VALUES (?,?,?,?) ON CONFLICT DO NOTHING",
                (g["id"], g["name"], base_url, int(g["is_minor"])),
            )
        else:
            _execute(
                conn,
                "INSERT OR IGNORE INTO galleries (id, name, base_url, is_minor) VALUES (?,?,?,?)",
                (g["id"], g["name"], base_url, int(g["is_minor"])),
            )


# ── CRUD ─────────────────────────────────────────────────────────────────────
def post_exists(post_id: str) -> bool:
    with get_conn() as conn:
        cur = _execute(conn, "SELECT 1 FROM posts WHERE id=?", (post_id,))
        return cur.fetchone() is not None


def save_post(post: dict):
    cols = ("id", "gallery_id", "post_no", "title", "body", "author", "posted_at",
            "view_count", "recommend_count", "comment_count", "url", "matched_keyword")
    vals = tuple(post.get(c) for c in cols)
    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT INTO posts ({','.join(cols)}) VALUES ({placeholders})"
    sql += " ON CONFLICT DO NOTHING" if _USE_PG else " ON CONFLICT(id) DO NOTHING"
    # SQLite: INSERT OR IGNORE
    if not _USE_PG:
        sql = f"INSERT OR IGNORE INTO posts ({','.join(cols)}) VALUES ({placeholders})"
    with get_conn() as conn:
        _execute(conn, sql, vals)


def save_comments(post_id: str, comments: list[dict]):
    with get_conn() as conn:
        _execute(conn, "DELETE FROM comments WHERE post_id=?", (post_id,))
        for c in comments:
            _execute(
                conn,
                "INSERT INTO comments (post_id, author, body, posted_at, parent_comment_id) VALUES (?,?,?,?,?)",
                (post_id, c.get("author"), c.get("body"), c.get("posted_at"), c.get("parent_comment_id")),
            )


def save_classification(cls: dict):
    if _USE_PG:
        sql = """INSERT INTO classifications (post_id, is_relevant, sentiment, summary, topic_tags)
                 VALUES (%s,%s,%s,%s,%s)
                 ON CONFLICT (post_id) DO UPDATE SET
                   is_relevant=EXCLUDED.is_relevant, sentiment=EXCLUDED.sentiment,
                   summary=EXCLUDED.summary, topic_tags=EXCLUDED.topic_tags,
                   classified_at=NOW()"""
        params = (cls["post_id"], cls["is_relevant"], cls["sentiment"], cls["summary"], cls["topic_tags"])
    else:
        sql = """INSERT OR REPLACE INTO classifications
                 (post_id, is_relevant, sentiment, summary, topic_tags)
                 VALUES (?,?,?,?,?)"""
        params = (cls["post_id"], cls["is_relevant"], cls["sentiment"], cls["summary"], cls["topic_tags"])
    with get_conn() as conn:
        _execute(conn, sql, params)


def get_posts_for_dashboard() -> list[dict]:
    sql = """SELECT p.*, c.is_relevant, c.sentiment, c.summary, c.topic_tags
             FROM posts p
             LEFT JOIN classifications c ON p.id = c.post_id
             WHERE c.is_relevant IS NULL OR c.is_relevant = 1
             ORDER BY p.posted_at DESC"""
    with get_conn() as conn:
        cur = _execute(conn, sql)
        return _fetchall(cur)


def get_stats() -> dict:
    with get_conn() as conn:
        cur = _execute(conn, "SELECT COUNT(*) FROM posts")
        total = cur.fetchone()[0]
        cur = _execute(conn, "SELECT COUNT(*) FROM classifications WHERE is_relevant=1")
        relevant = cur.fetchone()[0]
        cur = _execute(
            conn,
            "SELECT sentiment, COUNT(*) as cnt FROM classifications WHERE is_relevant=1 GROUP BY sentiment",
        )
        rows = _fetchall(cur)
        return {
            "total_collected": total,
            "total_relevant": relevant,
            "sentiments": {r["sentiment"]: r["cnt"] for r in rows},
        }
