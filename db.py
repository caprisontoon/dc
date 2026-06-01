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
    is_minor INTEGER DEFAULT 0,
    board_type TEXT DEFAULT 'board'
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
    base_url TEXT NOT NULL, is_minor INTEGER DEFAULT 0,
    board_type TEXT DEFAULT 'board'
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


def _parse_db_url(url: str) -> dict:
    """
    postgresql://USER:PASSWORD@HOST:PORT/DBNAME 를 안전하게 분해.
    비밀번호에 @ : / 같은 특수문자가 있어도 동작하도록 수동 파싱.
    또는 개별 환경변수(PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE)도 지원.
    """
    # 개별 환경변수가 모두 있으면 그것을 우선 사용 (가장 안전)
    if os.getenv("PGHOST") and os.getenv("PGPASSWORD"):
        return {
            "host": os.getenv("PGHOST"),
            "port": int(os.getenv("PGPORT", "5432")),
            "user": os.getenv("PGUSER", "postgres"),
            "password": os.getenv("PGPASSWORD"),
            "dbname": os.getenv("PGDATABASE", "postgres"),
        }

    rest = url.split("://", 1)[1]                     # USER:PASS@HOST:PORT/DB
    userinfo, hostpart = rest.rsplit("@", 1)          # 마지막 @ 기준 분리
    user, password = userinfo.split(":", 1)           # 첫 : 기준 분리
    if "/" in hostpart:
        hostport, dbname = hostpart.split("/", 1)
        dbname = dbname.split("?", 1)[0]              # 쿼리스트링 제거
    else:
        hostport, dbname = hostpart, "postgres"
    if ":" in hostport:
        host, port = hostport.rsplit(":", 1)
        port = int(port)
    else:
        host, port = hostport, 5432
    return {"host": host, "port": port, "user": user, "password": password, "dbname": dbname}


# ── 연결 컨텍스트 매니저 ────────────────────────────────────────────────────
@contextmanager
def get_conn():
    if _USE_PG:
        import psycopg2
        import psycopg2.extras
        # 비밀번호에 특수문자(@, : 등)가 있어도 안전하게 파싱
        params = _parse_db_url(DATABASE_URL)
        conn = psycopg2.connect(
            sslmode="require",
            connect_timeout=10,
            **params,
        )
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
            # 기존 테이블에 board_type 컬럼이 없으면 추가 (마이그레이션)
            try:
                cur.execute("ALTER TABLE galleries ADD COLUMN IF NOT EXISTS board_type TEXT DEFAULT 'board'")
            except Exception:
                pass
        else:
            conn.executescript(SQLITE_SCHEMA)
            try:
                _execute(conn, "ALTER TABLE galleries ADD COLUMN board_type TEXT DEFAULT 'board'")
            except Exception:
                pass
        _seed_galleries(conn)


def _board_path(board_type: str) -> str:
    return {"mgallery": "mgallery/board", "mini": "mini/board"}.get(board_type, "board")


def _seed_galleries(conn):
    """config의 갤러리를 INSERT(없으면) + board_type/base_url 교정(있으면).
    UI에서 삭제한 갤러리는 되살리지 않는다."""
    cur = _execute(conn, "SELECT id FROM galleries")
    existing_ids = {r[0] if not isinstance(r, dict) else r["id"] for r in cur.fetchall()}

    for g in GALLERIES:
        board_type = g.get("board_type", "board")
        base_url = f"https://gall.dcinside.com/{_board_path(board_type)}/lists/?id={g['id']}"
        is_minor = 1 if board_type in ("mgallery", "mini") else 0

        if g["id"] in existing_ids:
            # board_type이 잘못 저장된 경우를 교정한다
            _execute(
                conn,
                "UPDATE galleries SET board_type=?, base_url=?, is_minor=? WHERE id=?",
                (board_type, base_url, is_minor, g["id"]),
            )
        else:
            if _USE_PG:
                _execute(
                    conn,
                    "INSERT INTO galleries (id, name, base_url, is_minor, board_type) VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING",
                    (g["id"], g["name"], base_url, is_minor, board_type),
                )
            else:
                _execute(
                    conn,
                    "INSERT OR IGNORE INTO galleries (id, name, base_url, is_minor, board_type) VALUES (?,?,?,?,?)",
                    (g["id"], g["name"], base_url, is_minor, board_type),
                )


# ── 갤러리 관리 ───────────────────────────────────────────────────────────────
def parse_gallery_url(url: str) -> dict:
    """
    디시 갤러리 URL에서 id와 종류를 추출.
    예) https://gall.dcinside.com/mini/board/lists/?id=sparta_ → {id:'sparta_', board_type:'mini'}
    """
    import re
    url = url.strip()
    if "/mgallery/" in url:
        board_type = "mgallery"
    elif "/mini/" in url:
        board_type = "mini"
    else:
        board_type = "board"
    m = re.search(r"[?&]id=([A-Za-z0-9_]+)", url)
    if not m:
        # id= 가 없으면 URL 전체가 갤러리 ID라고 가정
        m2 = re.search(r"([A-Za-z0-9_]+)\s*$", url)
        gid = m2.group(1) if m2 else ""
    else:
        gid = m.group(1)
    return {"id": gid, "board_type": board_type}


def get_galleries() -> list[dict]:
    with get_conn() as conn:
        cur = _execute(conn, "SELECT id, name, base_url, is_minor, board_type FROM galleries ORDER BY name")
        rows = _fetchall(cur)
    for r in rows:
        if not r.get("board_type"):
            r["board_type"] = "board"
    return rows


def add_gallery(name: str, url: str) -> dict:
    parsed = parse_gallery_url(url)
    gid = parsed["id"]
    board_type = parsed["board_type"]
    if not gid:
        raise ValueError("URL에서 갤러리 ID를 찾지 못했습니다.")
    base_url = f"https://gall.dcinside.com/{_board_path(board_type)}/lists/?id={gid}"
    is_minor = 1 if board_type in ("mgallery", "mini") else 0
    name = name.strip() or gid
    with get_conn() as conn:
        if _USE_PG:
            _execute(
                conn,
                """INSERT INTO galleries (id, name, base_url, is_minor, board_type)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name,
                     base_url=EXCLUDED.base_url, is_minor=EXCLUDED.is_minor,
                     board_type=EXCLUDED.board_type""",
                (gid, name, base_url, is_minor, board_type),
            )
        else:
            _execute(
                conn,
                "INSERT OR REPLACE INTO galleries (id, name, base_url, is_minor, board_type) VALUES (?,?,?,?,?)",
                (gid, name, base_url, is_minor, board_type),
            )
    return {"id": gid, "name": name, "board_type": board_type}


def delete_gallery(gid: str):
    with get_conn() as conn:
        _execute(conn, "DELETE FROM galleries WHERE id=?", (gid,))


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
