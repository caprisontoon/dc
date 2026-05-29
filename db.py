import sqlite3
import json
from contextlib import contextmanager
from config import DB_PATH, GALLERIES

DDL = """
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


def init_db():
    with get_conn() as conn:
        conn.executescript(DDL)
        _seed_galleries(conn)


def _seed_galleries(conn: sqlite3.Connection):
    for g in GALLERIES:
        board = "mgallery/board" if g["is_minor"] else "board"
        base_url = f"https://gall.dcinside.com/{board}/lists/?id={g['id']}"
        conn.execute(
            "INSERT OR IGNORE INTO galleries (id, name, base_url, is_minor) VALUES (?, ?, ?, ?)",
            (g["id"], g["name"], base_url, int(g["is_minor"])),
        )


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


def post_exists(post_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM posts WHERE id = ?", (post_id,)).fetchone()
        return row is not None


def insert_post(post: dict):
    with get_conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO posts
               (id, gallery_id, post_no, title, body, author, posted_at,
                view_count, recommend_count, comment_count, url, matched_keyword)
               VALUES (:id, :gallery_id, :post_no, :title, :body, :author, :posted_at,
                       :view_count, :recommend_count, :comment_count, :url, :matched_keyword)""",
            post,
        )


def insert_comments(comments: list[dict]):
    if not comments:
        return
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO comments (post_id, author, body, posted_at, parent_comment_id)
               VALUES (:post_id, :author, :body, :posted_at, :parent_comment_id)""",
            comments,
        )


def insert_classification(clf: dict):
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO classifications
               (post_id, is_relevant, sentiment, summary, topic_tags)
               VALUES (:post_id, :is_relevant, :sentiment, :summary, :topic_tags)""",
            {**clf, "topic_tags": json.dumps(clf.get("topic_tags", []), ensure_ascii=False)},
        )


def fetch_posts_for_dashboard() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT p.id, p.gallery_id, p.title, p.author, p.posted_at,
                   p.view_count, p.recommend_count, p.comment_count,
                   p.url, p.matched_keyword, p.collected_at,
                   g.name AS gallery_name,
                   c.is_relevant, c.sentiment, c.summary, c.topic_tags
            FROM posts p
            LEFT JOIN galleries g ON p.gallery_id = g.id
            LEFT JOIN classifications c ON p.id = c.post_id
            ORDER BY p.posted_at DESC
        """).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d["topic_tags"]:
                import json as _json
                try:
                    d["topic_tags"] = _json.loads(d["topic_tags"])
                except Exception:
                    d["topic_tags"] = []
            else:
                d["topic_tags"] = []
            result.append(d)
        return result


def fetch_gallery_stats() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT g.name, g.id,
                   COUNT(p.id) AS total,
                   SUM(CASE WHEN c.sentiment='긍정' THEN 1 ELSE 0 END) AS pos,
                   SUM(CASE WHEN c.sentiment='중립' THEN 1 ELSE 0 END) AS neu,
                   SUM(CASE WHEN c.sentiment='부정' THEN 1 ELSE 0 END) AS neg
            FROM galleries g
            LEFT JOIN posts p ON g.id = p.gallery_id
            LEFT JOIN classifications c ON p.id = c.post_id AND c.is_relevant = 1
            GROUP BY g.id
        """).fetchall()
        return [dict(r) for r in rows]
