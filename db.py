"""DB layer for CobraQ: MySQL (production) or SQLite fallback (easy local run)."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(_ROOT / ".env")
    except ImportError:
        pass


_load_dotenv()

_pool = None
_sqlite_conn = None


def _engine() -> str:
    eng = (os.getenv("DB_ENGINE", "sqlite") or "sqlite").strip().lower()
    return "mysql" if eng == "mysql" else "sqlite"


# ---------- SQLite compatibility wrappers ----------
class SQLiteCursorWrapper:
    def __init__(self, cur: sqlite3.Cursor, dictionary: bool = False):
        self._cur = cur
        self._dictionary = dictionary

    @property
    def rowcount(self):
        return self._cur.rowcount

    def _rewrite(self, query: str, params):
        q = (query or "").strip()
        p = list(params or [])

        # MySQL placeholder -> SQLite placeholder
        q = q.replace("%s", "?")

        # MySQL functions
        q = q.replace("UTC_TIMESTAMP()", "CURRENT_TIMESTAMP")

        # mysql upsert: users
        if "INSERT INTO users (uid, email) VALUES (?, ?) ON DUPLICATE KEY UPDATE email = COALESCE(?, email)" in q:
            q = "INSERT INTO users (uid, email) VALUES (?, ?) ON CONFLICT(uid) DO UPDATE SET email = COALESCE(excluded.email, users.email)"
            p = p[:2]

        # mysql upsert: app_config
        if "INSERT INTO app_config (id, ai_parse_enabled) VALUES (1, ?) ON DUPLICATE KEY UPDATE ai_parse_enabled = ?" in q:
            q = "INSERT INTO app_config (id, ai_parse_enabled) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET ai_parse_enabled = excluded.ai_parse_enabled"
        if "INSERT INTO app_config (id, ai_fill_enabled) VALUES (1, %s) ON DUPLICATE KEY UPDATE ai_fill_enabled" in q:
            q = q  # keep as-is for mysql
            p = p[:1]

        # mysql upsert: question_files
        if "INSERT INTO question_files" in q and "ON DUPLICATE KEY UPDATE" in q:
            q = (
                "INSERT INTO question_files (user_uid, file_id, name, filename, parse_method, uploaded_at, file_count, with_answer) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(user_uid, file_id) DO UPDATE SET "
                "name=excluded.name, filename=excluded.filename, parse_method=excluded.parse_method, "
                "uploaded_at=excluded.uploaded_at, file_count=excluded.file_count, with_answer=excluded.with_answer"
            )

        # mysql upsert: quiz_sessions
        if "INSERT INTO quiz_sessions" in q and "ON DUPLICATE KEY UPDATE" in q:
            q = (
                "INSERT INTO quiz_sessions (session_id, user_uid, file_id, payload_json, expires_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(session_id) DO UPDATE SET "
                "payload_json=excluded.payload_json, file_id=excluded.file_id, expires_at=excluded.expires_at"
            )

        # mysql upsert: revoked_tokens
        if "INSERT INTO revoked_tokens" in q and "ON DUPLICATE KEY UPDATE" in q:
            q = (
                "INSERT INTO revoked_tokens (token_hash, token_type, user_uid, expires_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(token_hash) DO UPDATE SET "
                "token_type=excluded.token_type, user_uid=excluded.user_uid, expires_at=excluded.expires_at"
            )

        # SHOW COLUMNS not supported in sqlite
        if q.upper().startswith("SHOW COLUMNS FROM USERS LIKE"):
            q = "SELECT name FROM pragma_table_info('users') WHERE name = 'password_hash'"
            p = []
        if q.upper().startswith("SHOW COLUMNS FROM QUESTIONS LIKE"):
            col_name = ""
            try:
                col_name = q.split("LIKE", 1)[1].strip().strip("'").strip('"')
            except Exception:
                col_name = ""
            if not col_name:
                col_name = "question_rich"
            q = f"SELECT name FROM pragma_table_info('questions') WHERE name = '{col_name}'"
            p = []

        # ALTER MODIFY not supported in sqlite -> no-op statement
        if "ALTER TABLE users MODIFY COLUMN password_hash" in q:
            q = "SELECT 1"
            p = []

        return q, p

    def execute(self, query, params=None):
        q, p = self._rewrite(query, params)
        return self._cur.execute(q, p)

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        if self._dictionary and isinstance(row, sqlite3.Row):
            return dict(row)
        return row

    def fetchall(self):
        rows = self._cur.fetchall()
        if self._dictionary:
            return [dict(r) if isinstance(r, sqlite3.Row) else r for r in rows]
        return rows

    def close(self):
        self._cur.close()


class SQLiteConnWrapper:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def cursor(self, dictionary: bool = False):
        return SQLiteCursorWrapper(self._conn.cursor(), dictionary=dictionary)

    def commit(self):
        self._conn.commit()

    def close(self):
        # keep single sqlite connection open for process lifetime
        return None


# ---------- MySQL ----------
def _mysql_config():
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "cobraq"),
        "charset": "utf8mb4",
        "autocommit": True,
    }


def _get_mysql_pool():
    global _pool
    if _pool is not None:
        return _pool
    from mysql.connector import pooling

    cfg = _mysql_config()
    _pool = pooling.MySQLConnectionPool(
        pool_name="cobraq_pool",
        pool_size=int(os.getenv("DB_POOL_SIZE", "8")),
        pool_reset_session=True,
        **{k: v for k, v in cfg.items() if k != "autocommit"},
    )
    return _pool


# ---------- SQLite ----------
def _sqlite_path() -> Path:
    v = os.getenv("SQLITE_PATH", "cobraq.sqlite3").strip() or "cobraq.sqlite3"
    p = Path(v)
    if not p.is_absolute():
        p = _ROOT / p
    return p


def _get_sqlite_conn():
    global _sqlite_conn
    if _sqlite_conn is not None:
        return _sqlite_conn
    path = _sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _sqlite_conn = conn
    return _sqlite_conn


def get_connection():
    if _engine() == "mysql":
        return _get_mysql_pool().get_connection()
    return SQLiteConnWrapper(_get_sqlite_conn())


def _run_post_schema_migrations(conn) -> None:
    cur = conn.cursor()
    try:
        if _engine() == "mysql":
            cur.execute("SHOW COLUMNS FROM users LIKE 'password_hash'")
            row = cur.fetchone()
            if row:
                cur.execute("ALTER TABLE users MODIFY COLUMN password_hash VARCHAR(255) DEFAULT NULL")
            cur.execute("SHOW COLUMNS FROM users LIKE 'avatar_url'")
            avatar_col = cur.fetchone()
            if not avatar_col:
                cur.execute("ALTER TABLE users ADD COLUMN avatar_url LONGTEXT")

            # app_config ai_fill_enabled migration
            cur.execute("SHOW COLUMNS FROM app_config LIKE 'ai_fill_enabled'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE app_config ADD COLUMN ai_fill_enabled INTEGER NOT NULL DEFAULT 0")

            # questions rich/math fields migrations
            cur.execute("SHOW COLUMNS FROM questions LIKE 'question_rich'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE questions ADD COLUMN question_rich LONGTEXT NULL")
            cur.execute("SHOW COLUMNS FROM questions LIKE 'choices_rich'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE questions ADD COLUMN choices_rich JSON NULL")
            cur.execute("SHOW COLUMNS FROM questions LIKE 'parse_confidence'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE questions ADD COLUMN parse_confidence DECIMAL(5,4) DEFAULT 0")
            cur.execute("SHOW COLUMNS FROM questions LIKE 'parse_flags'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE questions ADD COLUMN parse_flags JSON NULL")
            cur.execute("SHOW COLUMNS FROM questions LIKE 'reviewed'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE questions ADD COLUMN reviewed TINYINT(1) NOT NULL DEFAULT 0")
            cur.execute("SHOW COLUMNS FROM questions LIKE 'reviewed_at'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE questions ADD COLUMN reviewed_at DATETIME NULL")

            conn.commit()
            return

        # sqlite lightweight users migration
        cur.execute("PRAGMA table_info(users)")
        cols = {r[1] if not isinstance(r, dict) else r.get('name') for r in cur.fetchall()}
        wanted = {
            "email": "TEXT",
            "password_hash": "TEXT",
            "role": "TEXT NOT NULL DEFAULT 'user'",
            "display_name": "TEXT",
            "avatar_url": "TEXT",
            "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        }
        for c, t in wanted.items():
            if c not in cols:
                cur.execute(f"ALTER TABLE users ADD COLUMN {c} {t}")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users(email)")

        # sqlite app_config migration (ai_fill_enabled)
        cur.execute("PRAGMA table_info(app_config)")
        ac_cols = {r[1] if not isinstance(r, dict) else r.get('name') for r in cur.fetchall()}
        if "ai_fill_enabled" not in ac_cols:
            cur.execute("ALTER TABLE app_config ADD COLUMN ai_fill_enabled INTEGER NOT NULL DEFAULT 0")

        # sqlite questions migration (rich/math fields)
        cur.execute("PRAGMA table_info(questions)")
        q_cols = {r[1] if not isinstance(r, dict) else r.get('name') for r in cur.fetchall()}
        q_wanted = {
            "question_rich": "TEXT",
            "choices_rich": "TEXT",
            "parse_confidence": "REAL DEFAULT 0",
            "parse_flags": "TEXT",
        }
        for c, t in q_wanted.items():
            if c not in q_cols:
                cur.execute(f"ALTER TABLE questions ADD COLUMN {c} {t}")
        if "reviewed" not in q_cols:
            cur.execute("ALTER TABLE questions ADD COLUMN reviewed INTEGER NOT NULL DEFAULT 0")
        if "reviewed_at" not in q_cols:
            cur.execute("ALTER TABLE questions ADD COLUMN reviewed_at DATETIME")

        # === AI PIPELINE TABLES ===
        # ai_cache
        cur.execute("PRAGMA table_info(ai_cache)")
        ai_cache_cols = {r[1] if not isinstance(r, dict) else r.get('name') for r in cur.fetchall()}
        ai_cache_wanted = {
            "user_id": "TEXT",
            "question_hash": "TEXT",
            "question_text": "TEXT",
            "answer": "TEXT",
            "explanation": "TEXT",
            "confidence": "REAL DEFAULT 0.0",
            "source": "TEXT DEFAULT 'llm'",
            "subject": "TEXT DEFAULT ''",
            "file_id": "TEXT DEFAULT ''",
            "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "DATETIME DEFAULT CURRENT_TIMESTAMP"
        }
        for c, t in ai_cache_wanted.items():
            if c not in ai_cache_cols:
                cur.execute(f"ALTER TABLE ai_cache ADD COLUMN {c} {t}")
        # SQLite: không hỗ trợ prefix length (32) trong index
        # MySQL cho phép INDEX(column(32)), SQLite thì không
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_cache_user_q ON ai_cache(user_id, question_hash)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_cache_subject ON ai_cache(subject)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_cache_file ON ai_cache(file_id)")

        # ai_llm_logs
        cur.execute("PRAGMA table_info(ai_llm_logs)")
        ai_logs_cols = {r[1] if not isinstance(r, dict) else r.get('name') for r in cur.fetchall()}
        ai_logs_wanted = {
            "user_id": "TEXT",
            "question_id": "INTEGER",
            "file_id": "TEXT DEFAULT ''",
            "model": "TEXT DEFAULT 'gemini-1.5-flash'",
            "prompt_text": "TEXT",
            "response_text": "TEXT",
            "prompt_tokens": "INTEGER DEFAULT 0",
            "response_tokens": "INTEGER DEFAULT 0",
            "total_tokens": "INTEGER DEFAULT 0",
            "cost_estimate": "REAL DEFAULT 0.0",
            "success": "INTEGER DEFAULT 1",
            "error_message": "TEXT",
            "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP"
        }
        for c, t in ai_logs_wanted.items():
            if c not in ai_logs_cols:
                cur.execute(f"ALTER TABLE ai_llm_logs ADD COLUMN {c} {t}")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_logs_user_created ON ai_llm_logs(user_id, created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_logs_file ON ai_llm_logs(file_id)")

        conn.commit()
    finally:
        cur.close()


def init_schema_from_file() -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        if _engine() == "sqlite":
            sqlite_schema = [
                """
                CREATE TABLE IF NOT EXISTS users (
                  uid TEXT PRIMARY KEY,
                  email TEXT,
                  password_hash TEXT,
                  role TEXT NOT NULL DEFAULT 'user',
                  display_name TEXT,
                  avatar_url TEXT,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """,
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users(email)",
                """
                CREATE TABLE IF NOT EXISTS app_config (
                  id INTEGER PRIMARY KEY,
                  ai_parse_enabled INTEGER NOT NULL DEFAULT 1,
                  ai_fill_enabled INTEGER NOT NULL DEFAULT 0
                )
                """,
                "INSERT OR IGNORE INTO app_config (id, ai_parse_enabled, ai_fill_enabled) VALUES (1, 1, 0)",
                """
                CREATE TABLE IF NOT EXISTS question_files (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_uid TEXT NOT NULL,
                  file_id TEXT NOT NULL,
                  name TEXT NOT NULL,
                  filename TEXT NOT NULL,
                  parse_method TEXT DEFAULT 'normal',
                  uploaded_at TEXT NOT NULL,
                  file_count INTEGER NOT NULL DEFAULT 0,
                  with_answer INTEGER NOT NULL DEFAULT 0,
                  UNIQUE(user_uid, file_id),
                  FOREIGN KEY(user_uid) REFERENCES users(uid) ON DELETE CASCADE
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS questions (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_uid TEXT NOT NULL,
                  file_id TEXT NOT NULL,
                  q_id INTEGER NOT NULL,
                  question_text TEXT NOT NULL,
                  question_rich TEXT,
                  choices_json TEXT NOT NULL,
                  choices_rich TEXT,
                  answer TEXT DEFAULT '',
                  explanation TEXT,
                  parse_confidence REAL DEFAULT 0,
                  parse_flags TEXT,
                  reviewed INTEGER NOT NULL DEFAULT 0,
                  reviewed_at DATETIME,
                  UNIQUE(user_uid, file_id, q_id),
                  FOREIGN KEY(user_uid) REFERENCES users(uid) ON DELETE CASCADE
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS quiz_sessions (
                  session_id TEXT PRIMARY KEY,
                  user_uid TEXT NOT NULL,
                  file_id TEXT,
                  payload_json TEXT NOT NULL,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  expires_at DATETIME,
                  FOREIGN KEY(user_uid) REFERENCES users(uid) ON DELETE CASCADE
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS quiz_history (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_uid TEXT NOT NULL,
                  file_id TEXT,
                  score INTEGER NOT NULL,
                  total INTEGER NOT NULL,
                  percent INTEGER NOT NULL,
                  time_taken INTEGER DEFAULT 0,
                  wrong_questions_json TEXT,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  date_display TEXT NOT NULL,
                  FOREIGN KEY(user_uid) REFERENCES users(uid) ON DELETE CASCADE
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS revoked_tokens (
                  token_hash TEXT PRIMARY KEY,
                  token_type TEXT NOT NULL,
                  user_uid TEXT,
                  expires_at DATETIME,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """,
                # === AI PIPELINE TABLES ===
                """
                CREATE TABLE IF NOT EXISTS ai_cache (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT NOT NULL,
                  question_hash TEXT NOT NULL,
                  question_text LONGTEXT NOT NULL,
                  answer TEXT DEFAULT '',
                  explanation TEXT,
                  confidence REAL DEFAULT 0.0,
                  source TEXT DEFAULT 'llm',
                  subject TEXT DEFAULT '',
                  file_id TEXT DEFAULT '',
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(user_id, question_hash)
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_ai_cache_subject ON ai_cache(subject)",
                "CREATE INDEX IF NOT EXISTS idx_ai_cache_file ON ai_cache(file_id)",
                """
                CREATE TABLE IF NOT EXISTS ai_llm_logs (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT NOT NULL,
                  question_id INTEGER,
                  file_id TEXT DEFAULT '',
                  model TEXT DEFAULT 'gemini-1.5-flash',
                  prompt_text LONGTEXT,
                  response_text LONGTEXT,
                  prompt_tokens INTEGER DEFAULT 0,
                  response_tokens INTEGER DEFAULT 0,
                  total_tokens INTEGER DEFAULT 0,
                  cost_estimate REAL DEFAULT 0.0,
                  success INTEGER DEFAULT 1,
                  error_message TEXT,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_ai_logs_user_created ON ai_llm_logs(user_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_ai_logs_file ON ai_llm_logs(file_id)",
            ]
            for stmt in sqlite_schema:
                cur.execute(stmt)
            conn.commit()
            cur.close()
            _run_post_schema_migrations(conn)
            return

        # mysql path: use schema.sql
        sql_path = _ROOT / "schema.sql"
        raw = sql_path.read_text(encoding="utf-8")
        lines = []
        for line in raw.splitlines():
            s = line.strip()
            if s.startswith("--"):
                continue
            lines.append(line)
        blob = "\n".join(lines)
        for part in blob.split(";"):
            st = part.strip()
            if st:
                cur.execute(st)
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
