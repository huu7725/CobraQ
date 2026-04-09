"""MySQL connection pool + schema init for CobraQ."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(_ROOT / ".env")
    except ImportError:
        pass


_load_dotenv()

_pool = None


def _config():
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "cobraq"),
        "charset": "utf8mb4",
        "autocommit": True,
    }


def get_pool():
    global _pool
    if _pool is not None:
        return _pool
    try:
        from mysql.connector import pooling
    except ImportError as e:
        raise RuntimeError(
            "Thiếu mysql-connector-python. Chạy: pip install mysql-connector-python"
        ) from e
    cfg = _config()
    _pool = pooling.MySQLConnectionPool(
        pool_name="cobraq_pool",
        pool_size=int(os.getenv("DB_POOL_SIZE", "8")),
        pool_reset_session=True,
        **{k: v for k, v in cfg.items() if k != "autocommit"},
    )
    return _pool


def get_connection():
    return get_pool().get_connection()


def _run_post_schema_migrations(conn) -> None:
    cur = conn.cursor()
    try:
        cur.execute("SHOW COLUMNS FROM users")
        cols = {r[0] for r in (cur.fetchall() or [])}

        if "email" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN email VARCHAR(255) DEFAULT NULL")
        if "password_hash" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) DEFAULT NULL")
        if "role" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'")
        if "display_name" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN display_name VARCHAR(255) DEFAULT NULL")
        if "created_at" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")

        # Chuẩn hóa độ dài cột hash cho bcrypt
        cur.execute("SHOW COLUMNS FROM users LIKE 'password_hash'")
        row = cur.fetchone()
        if row:
            cur.execute("ALTER TABLE users MODIFY COLUMN password_hash VARCHAR(255) DEFAULT NULL")

        # Đảm bảo unique email nếu chưa có
        cur.execute("SHOW INDEX FROM users WHERE Key_name = 'uq_users_email'")
        if cur.fetchone() is None:
            cur.execute("ALTER TABLE users ADD UNIQUE KEY uq_users_email (email)")

        conn.commit()
    finally:
        cur.close()


def init_schema_from_file() -> None:
    """Run schema.sql (CREATE IF NOT EXISTS) + safe lightweight migrations."""
    sql_path = Path(__file__).resolve().parent / "schema.sql"
    raw = sql_path.read_text(encoding="utf-8")
    lines = []
    for line in raw.splitlines():
        s = line.strip()
        if s.startswith("--"):
            continue
        lines.append(line)
    blob = "\n".join(lines)
    statements = []
    for part in blob.split(";"):
        st = part.strip()
        if st:
            statements.append(st)
    conn = get_connection()
    try:
        cur = conn.cursor()
        for stmt in statements:
            cur.execute(stmt)
        conn.commit()
        cur.close()
        _run_post_schema_migrations(conn)
    finally:
        conn.close()


def ping_db() -> bool:
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            return True
        finally:
            conn.close()
    except Exception:
        return False
