import sqlite3
from contextlib import contextmanager
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
def get_conn():
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


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        _seed_galleries(conn)


def _seed_galleries(conn):
    for g in GALLERIES:
        if g["is_minor"]:
            base_url = f"https://gall.dcinside.com/mgallery/board/lists/?id={g['id']}"
        else:
            base_url = f"https://gall.dcinside.com/board/lists/?id={g['id']}"
        conn.execute(
            "INSERT OR IGNORE INTO galleries (id, name, base_url, is_minor) VALUES (?,?,?,?)",
            (g["id"], g["name"], base_url, int(g["is_minor"])),
        )


def post_exists(post_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM posts WHERE id=?", (post_id,)).fetchone()
        return row is not None


def save_post(post: dict):
    with get_conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO posts
               (id, gallery_id, post_no, title, body, author, posted_at,
                view_count, recommend_count, comment_count, url, matched_keyword)
               VALUES (:id,:gallery_id,:post_no,:title,:body,:author,:posted_at,
                       :view_count,:recommend_count,:comment_count,:url,:matched_keyword)""",
            post,
        )


def save_comments(post_id: str, comments: list[dict]):
    with get_conn() as conn:
        conn.execute("DELETE FROM comments WHERE post_id=?", (post_id,))
        for c in comments:
            conn.execute(
                """INSERT INTO comments (post_id, author, body, posted_at, parent_comment_id)
                   VALUES (:post_id,:author,:body,:posted_at,:parent_comment_id)""",
                {**c, "post_id": post_id},
            )


def save_classification(cls: dict):
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO classifications
               (post_id, is_relevant, sentiment, summary, topic_tags)
               VALUES (:post_id,:is_relevant,:sentiment,:summary,:topic_tags)""",
            cls,
        )


def get_posts_for_dashboard() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT p.*, c.is_relevant, c.sentiment, c.summary, c.topic_tags
               FROM posts p
               LEFT JOIN classifications c ON p.id = c.post_id
               WHERE c.is_relevant IS NULL OR c.is_relevant = 1
               ORDER BY p.posted_at DESC""",
        ).fetchall()
        return [dict(r) for r in rows]


def get_stats() -> dict:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
        relevant = conn.execute(
            "SELECT COUNT(*) FROM classifications WHERE is_relevant=1"
        ).fetchone()[0]
        sentiments = conn.execute(
            """SELECT sentiment, COUNT(*) as cnt FROM classifications
               WHERE is_relevant=1 GROUP BY sentiment"""
        ).fetchall()
        return {
            "total_collected": total,
            "total_relevant": relevant,
            "sentiments": {r["sentiment"]: r["cnt"] for r in sentiments},
        }
