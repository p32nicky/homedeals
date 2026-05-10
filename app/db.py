import os
import sqlite3
from contextlib import contextmanager
from typing import Optional

_DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_POSTGRES = bool(_DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras


@contextmanager
def _pg_conn():
    conn = psycopg2.connect(_DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def _sqlite_conn(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _get_conn(db_path: str):
    return _pg_conn() if USE_POSTGRES else _sqlite_conn(db_path)


_CREATE_SQLITE = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    asin TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    image_url TEXT,
    price REAL,
    original_price REAL,
    savings REAL,
    savings_percent REAL,
    category TEXT,
    description TEXT,
    first_seen_at TEXT,
    last_seen_at TEXT,
    bluesky_posted_at TEXT,
    tumblr_posted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_asin ON products(asin);
"""

_CREATE_PG = """
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    asin TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    image_url TEXT,
    price REAL,
    original_price REAL,
    savings REAL,
    savings_percent REAL,
    category TEXT,
    description TEXT,
    first_seen_at TEXT,
    last_seen_at TEXT,
    bluesky_posted_at TEXT,
    tumblr_posted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_asin ON products(asin);
"""


def init_db(db_path: str) -> None:
    if not USE_POSTGRES:
        try:
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        except OSError:
            pass
    with _get_conn(db_path) as conn:
        # Add bluesky_posted_at column if missing (migration)
        for col in ["bluesky_posted_at", "tumblr_posted_at"]:
            try:
                if USE_POSTGRES:
                    conn.cursor().execute(f"ALTER TABLE products ADD COLUMN IF NOT EXISTS {col} TEXT")
                else:
                    conn.execute(f"ALTER TABLE products ADD COLUMN {col} TEXT")
            except Exception:
                pass
        sql = _CREATE_PG if USE_POSTGRES else _CREATE_SQLITE
        for stmt in sql.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    if USE_POSTGRES:
                        conn.cursor().execute(stmt)
                    else:
                        conn.execute(stmt)
                except Exception:
                    pass


def upsert_products(db_path: str, items: list[dict]) -> int:
    inserted = 0
    ph = "%s" if USE_POSTGRES else "?"
    now = items[0]["last_seen_at"] if items else ""
    with _get_conn(db_path) as conn:
        for item in items:
            if USE_POSTGRES:
                cur = conn.cursor()
                cur.execute(f"""
                    INSERT INTO products (asin, title, url, image_url, price, original_price,
                        savings, savings_percent, category, description, first_seen_at, last_seen_at)
                    VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
                    ON CONFLICT (asin) DO UPDATE SET
                        price = EXCLUDED.price,
                        savings = EXCLUDED.savings,
                        savings_percent = EXCLUDED.savings_percent,
                        last_seen_at = EXCLUDED.last_seen_at
                    RETURNING (xmax = 0) AS is_new
                """, (item["asin"], item["title"], item["url"], item["image_url"],
                      item["price"], item["original_price"], item["savings"],
                      item["savings_percent"], item["category"], item["description"],
                      item["first_seen_at"], item["last_seen_at"]))
                row = cur.fetchone()
                if row and row["is_new"]:
                    inserted += 1
            else:
                ex = conn.execute("SELECT id FROM products WHERE asin=?", (item["asin"],)).fetchone()
                if not ex:
                    conn.execute("""
                        INSERT INTO products (asin, title, url, image_url, price, original_price,
                            savings, savings_percent, category, description, first_seen_at, last_seen_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (item["asin"], item["title"], item["url"], item["image_url"],
                          item["price"], item["original_price"], item["savings"],
                          item["savings_percent"], item["category"], item["description"],
                          item["first_seen_at"], item["last_seen_at"]))
                    inserted += 1
                else:
                    conn.execute(
                        "UPDATE products SET price=?, savings=?, savings_percent=?, last_seen_at=? WHERE asin=?",
                        (item["price"], item["savings"], item["savings_percent"],
                         item["last_seen_at"], item["asin"])
                    )
    return inserted


def _rows(conn, sql, params=()):
    if USE_POSTGRES:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
    return conn.execute(sql, params).fetchall()


def _one(conn, sql, params=()):
    if USE_POSTGRES:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchone()
    return conn.execute(sql, params).fetchone()


def list_products(db_path: str, query: str = "", page: int = 1, per_page: int = 24):
    ph = "%s" if USE_POSTGRES else "?"
    like_op = "ILIKE" if USE_POSTGRES else "LIKE"
    offset = (page - 1) * per_page
    with _get_conn(db_path) as conn:
        if query:
            like = f"%{query}%"
            rows = _rows(conn,
                f"SELECT * FROM products WHERE title {like_op} {ph} ORDER BY savings_percent DESC NULLS LAST LIMIT {ph} OFFSET {ph}",
                (like, per_page, offset))
            total = (_one(conn, f"SELECT COUNT(*) as count FROM products WHERE title {like_op} {ph}", (like,)) or {}).get("count", 0) \
                if USE_POSTGRES else (_one(conn, f"SELECT COUNT(*) FROM products WHERE title {like_op} {ph}", (like,)) or [0])[0]
        else:
            rows = _rows(conn,
                f"SELECT * FROM products ORDER BY savings_percent DESC NULLS LAST LIMIT {ph} OFFSET {ph}",
                (per_page, offset))
            total = (_one(conn, "SELECT COUNT(*) as count FROM products") or {}).get("count", 0) \
                if USE_POSTGRES else (_one(conn, "SELECT COUNT(*) FROM products") or [0])[0]
    return rows, total


def get_latest_products(db_path: str, limit: int = 20, offset: int = 0):
    ph = "%s" if USE_POSTGRES else "?"
    with _get_conn(db_path) as conn:
        return _rows(conn,
            f"SELECT * FROM products ORDER BY first_seen_at DESC LIMIT {ph} OFFSET {ph}",
            (limit, offset))


def get_unposted_products(db_path: str, limit: int = 10) -> list[dict]:
    """Get products not yet posted to Bluesky, prioritising those with images."""
    ph = "%s" if USE_POSTGRES else "?"
    with _get_conn(db_path) as conn:
        return _rows(conn,
            f"SELECT * FROM products WHERE bluesky_posted_at IS NULL ORDER BY id LIMIT {ph}",
            (limit,))


def mark_bluesky_posted(db_path: str, asins: list[str]) -> None:
    if not asins:
        return
    ph = "%s" if USE_POSTGRES else "?"
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    placeholders = ",".join([ph] * len(asins))
    with _get_conn(db_path) as conn:
        if USE_POSTGRES:
            conn.cursor().execute(
                f"UPDATE products SET bluesky_posted_at={ph} WHERE asin IN ({placeholders})",
                (now, *asins))
        else:
            conn.execute(
                f"UPDATE products SET bluesky_posted_at=? WHERE asin IN ({placeholders})",
                (now, *asins))


def reset_bluesky_posted(db_path: str) -> None:
    with _get_conn(db_path) as conn:
        if USE_POSTGRES:
            conn.cursor().execute("UPDATE products SET bluesky_posted_at = NULL")
        else:
            conn.execute("UPDATE products SET bluesky_posted_at = NULL")


def reset_tumblr_posted(db_path: str) -> None:
    with _get_conn(db_path) as conn:
        if USE_POSTGRES:
            conn.cursor().execute("UPDATE products SET tumblr_posted_at = NULL")
        else:
            conn.execute("UPDATE products SET tumblr_posted_at = NULL")


def get_untumblrd_products(db_path: str, limit: int = 25) -> list[dict]:
    ph = "%s" if USE_POSTGRES else "?"
    with _get_conn(db_path) as conn:
        return _rows(conn,
            f"SELECT * FROM products WHERE tumblr_posted_at IS NULL ORDER BY id LIMIT {ph}",
            (limit,))


def mark_tumblr_posted(db_path: str, asins: list[str]) -> None:
    if not asins:
        return
    ph = "%s" if USE_POSTGRES else "?"
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    placeholders = ",".join([ph] * len(asins))
    with _get_conn(db_path) as conn:
        if USE_POSTGRES:
            conn.cursor().execute(
                f"UPDATE products SET tumblr_posted_at={ph} WHERE asin IN ({placeholders})",
                (now, *asins))
        else:
            conn.execute(
                f"UPDATE products SET tumblr_posted_at=? WHERE asin IN ({placeholders})",
                (now, *asins))


def get_products_by_asins(db_path: str, asins: list[str]) -> list[dict]:
    if not asins:
        return []
    ph = "%s" if USE_POSTGRES else "?"
    placeholders = ",".join([ph] * len(asins))
    with _get_conn(db_path) as conn:
        return _rows(conn, f"SELECT * FROM products WHERE asin IN ({placeholders})", tuple(asins))


def get_product_by_asin(db_path: str, asin: str) -> Optional[dict]:
    ph = "%s" if USE_POSTGRES else "?"
    with _get_conn(db_path) as conn:
        return _one(conn, f"SELECT * FROM products WHERE asin={ph}", (asin,))
