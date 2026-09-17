"""
Lightweight SQLite data layer. No ORM — just plain SQL, easy to read and
easy to extend as your catalog grows.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    description   TEXT NOT NULL,
    details       TEXT,               -- longer pitch shown on the detail page (optional)
    price         REAL NOT NULL,
    currency      TEXT NOT NULL,
    category      TEXT NOT NULL DEFAULT 'General',
    file_id       TEXT NOT NULL,      -- Telegram file_id of the document
    cover_file_id TEXT,               -- Telegram file_id of a cover photo (optional)
    reminder_cover_file_id TEXT,      -- optional cover used only in reminder ads
    reminder_text TEXT,                -- optional per-book reminder message
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS book_images (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id  INTEGER NOT NULL,
    file_id  TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (book_id) REFERENCES books (id)
);

CREATE TABLE IF NOT EXISTS orders (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL,
    username           TEXT,
    book_id            INTEGER NOT NULL,
    status             TEXT NOT NULL DEFAULT 'pending', -- pending/approved/rejected
    screenshot_file_id TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    FOREIGN KEY (book_id) REFERENCES books (id)
);

CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    username   TEXT,
    first_name TEXT,
    joined_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ebook_engagement (
    user_id          INTEGER NOT NULL,
    book_id          INTEGER NOT NULL,
    last_engaged_at  TEXT NOT NULL,
    last_reminder_at TEXT,
    reminder_count   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, book_id),
    FOREIGN KEY (user_id) REFERENCES users (user_id),
    FOREIGN KEY (book_id) REFERENCES books (id)
);

CREATE TABLE IF NOT EXISTS reminder_settings (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    text       TEXT NOT NULL,
    image_file_id TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO reminder_settings (id, text) VALUES (1, ?)",
            ("👋 ሰላም {name}!\n\n💻 «{title}» መጽሐፉን ተመልክተው ነበር… ግን እስካሁን አልገዙትም። 👀\n\n👇 መጽሐፉን ይግዙና ዛሬውኑ ይጀምሩ! 🚀📚",),
        )
        # Migration: 'details' was added after the initial release, so an
        # already-live database (like the one on Railway) won't have this
        # column yet. SQLite has no "ADD COLUMN IF NOT EXISTS", so we just
        # try it and ignore the error if it's already there.
        try:
            conn.execute("ALTER TABLE books ADD COLUMN details TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE books ADD COLUMN reminder_cover_file_id TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE books ADD COLUMN reminder_text TEXT")
        except sqlite3.OperationalError:
            pass


# ---------- users ----------

def upsert_user(user_id: int, username: Optional[str], first_name: Optional[str]):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO users (user_id, username, first_name, joined_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,
                                                    first_name=excluded.first_name""",
            (user_id, username, first_name, _now()),
        )


def record_book_engagement(user_id: int, book_id: int):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO ebook_engagement (user_id, book_id, last_engaged_at)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, book_id) DO UPDATE SET
                   last_engaged_at = excluded.last_engaged_at""",
            (user_id, book_id, _now()),
        )


def list_reminder_candidates(max_reminders: int = 6, min_interval_hours: int = 10):
    eligible_after = (datetime.now(timezone.utc) - timedelta(hours=min_interval_hours)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT e.user_id, e.book_id, u.first_name, b.title,
                      b.reminder_text,
                      COALESCE(b.reminder_cover_file_id, b.cover_file_id) AS reminder_cover_file_id
               FROM ebook_engagement e
               JOIN users u ON u.user_id = e.user_id
               JOIN books b ON b.id = e.book_id
               WHERE b.active = 1
                 AND e.reminder_count < ?
                 AND (e.last_reminder_at IS NULL OR e.last_reminder_at <= ?)
                 AND NOT EXISTS (
                     SELECT 1 FROM orders o
                     WHERE o.user_id = e.user_id
                       AND o.book_id = e.book_id
                       AND o.status IN ('pending', 'approved')
                 )""",
            (max_reminders, eligible_after),
        ).fetchall()
        return [dict(row) for row in rows]


def list_manual_reminder_candidates():
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT e.user_id, e.book_id, u.first_name, b.title,
                      b.reminder_text,
                      COALESCE(b.reminder_cover_file_id, b.cover_file_id) AS reminder_cover_file_id
               FROM ebook_engagement e
               JOIN users u ON u.user_id = e.user_id
               JOIN books b ON b.id = e.book_id
               WHERE b.active = 1
                 AND NOT EXISTS (
                     SELECT 1 FROM orders o
                     WHERE o.user_id = e.user_id
                       AND o.book_id = e.book_id
                       AND o.status IN ('pending', 'approved')
                 )"""
        ).fetchall()
        return [dict(row) for row in rows]


def get_reminder_settings():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT text, image_file_id FROM reminder_settings WHERE id = 1"
        ).fetchone()
        return dict(row)


def update_reminder_setting(field: str, value):
    if field not in {"text", "image_file_id"}:
        raise ValueError("Unsupported reminder setting")
    with get_conn() as conn:
        conn.execute(f"UPDATE reminder_settings SET {field} = ? WHERE id = 1", (value,))


def mark_reminder_sent(user_id: int, book_id: int):
    with get_conn() as conn:
        conn.execute(
            """UPDATE ebook_engagement
               SET last_reminder_at = ?, reminder_count = reminder_count + 1
               WHERE user_id = ? AND book_id = ?""",
            (_now(), user_id, book_id),
        )


# ---------- books ----------

def add_book(title, description, price, currency, category, file_id, cover_file_id=None, details=None):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO books (title, description, details, price, currency, category,
                                   file_id, cover_file_id, active, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (title, description, details, price, currency, category, file_id, cover_file_id, _now()),
        )
        return cur.lastrowid


# ---------- book detail images ----------

def add_book_image(book_id: int, file_id: str, position: int = 0):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO book_images (book_id, file_id, position) VALUES (?, ?, ?)",
            (book_id, file_id, position),
        )


def get_book_images(book_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT file_id FROM book_images WHERE book_id = ? ORDER BY position",
            (book_id,),
        ).fetchall()
        return [r["file_id"] for r in rows]


def clear_book_images(book_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM book_images WHERE book_id = ?", (book_id,))


def remove_book_image(book_id: int, image_id: int):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM book_images WHERE book_id = ? AND id = ?",
            (book_id, image_id),
        )


def list_book_images(book_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, file_id FROM book_images WHERE book_id = ? ORDER BY position, id",
            (book_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_book(book_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        return dict(row) if row else None


def list_categories():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT category FROM books WHERE active = 1 ORDER BY category"
        ).fetchall()
        return [r["category"] for r in rows]


def list_books(category: Optional[str] = None, active_only: bool = True, offset: int = 0, limit: int = 100):
    query = "SELECT * FROM books"
    conditions = []
    params = []
    if active_only:
        conditions.append("active = 1")
    if category:
        conditions.append("category = ?")
        params.append(category)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def count_books(category: Optional[str] = None, active_only: bool = True):
    query = "SELECT COUNT(*) as c FROM books"
    conditions = []
    params = []
    if active_only:
        conditions.append("active = 1")
    if category:
        conditions.append("category = ?")
        params.append(category)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    with get_conn() as conn:
        return conn.execute(query, params).fetchone()["c"]


def deactivate_book(book_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE books SET active = 0 WHERE id = ?", (book_id,))


# Fields an admin is allowed to edit one at a time via /editbook.
EDITABLE_BOOK_FIELDS = {
    "title", "description", "details", "price", "currency", "category",
    "file_id", "cover_file_id", "reminder_cover_file_id", "reminder_text",
}


def update_book_field(book_id: int, field: str, value):
    if field not in EDITABLE_BOOK_FIELDS:
        raise ValueError(f"Field '{field}' is not editable")
    with get_conn() as conn:
        conn.execute(f"UPDATE books SET {field} = ? WHERE id = ?", (value, book_id))


def delete_book(book_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM books WHERE id = ?", (book_id,))


# ---------- orders ----------

def create_order(user_id: int, username: Optional[str], book_id: int, screenshot_file_id: str):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO orders (user_id, username, book_id, status,
                                    screenshot_file_id, created_at, updated_at)
               VALUES (?, ?, ?, 'pending', ?, ?, ?)""",
            (user_id, username, book_id, screenshot_file_id, _now(), _now()),
        )
        return cur.lastrowid


def get_order(order_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        return dict(row) if row else None


def set_order_status(order_id: int, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE orders SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now(), order_id),
        )


def list_orders_for_user(user_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT orders.*, books.title as book_title
               FROM orders JOIN books ON orders.book_id = books.id
               WHERE orders.user_id = ? ORDER BY orders.id DESC""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def stats():
    with get_conn() as conn:
        total_orders = conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]
        approved = conn.execute(
            "SELECT COUNT(*) c FROM orders WHERE status='approved'"
        ).fetchone()["c"]
        pending = conn.execute(
            "SELECT COUNT(*) c FROM orders WHERE status='pending'"
        ).fetchone()["c"]
        revenue = conn.execute(
            """SELECT COALESCE(SUM(books.price), 0) as r
               FROM orders JOIN books ON orders.book_id = books.id
               WHERE orders.status = 'approved'"""
        ).fetchone()["r"]
        total_books = conn.execute("SELECT COUNT(*) c FROM books WHERE active=1").fetchone()["c"]
        return {
            "total_orders": total_orders,
            "approved": approved,
            "pending": pending,
            "revenue": revenue,
            "total_books": total_books,
        }