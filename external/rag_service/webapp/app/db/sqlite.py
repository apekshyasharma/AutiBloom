from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import aiosqlite


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  user_agent TEXT,
  ip TEXT
);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,           -- user | assistant | system
  content TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS requests (
  request_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  query TEXT NOT NULL,
  mode_requested TEXT NOT NULL, -- fixed | semantic | auto
  mode_used TEXT,               -- actual mode used (may differ if auto)
  status TEXT NOT NULL,         -- started | ok | error
  error_message TEXT,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  latency_ms INTEGER,
  FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_session_time ON messages(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_requests_session_time ON requests(session_id, created_at);
"""


@dataclass(frozen=True)
class SQLiteConfig:
    db_path: Path


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


async def init_db(cfg: SQLiteConfig) -> None:
    """
    Initialize SQLite DB and schema. Safe to call multiple times.
    """
    ensure_parent_dir(cfg.db_path)
    async with aiosqlite.connect(str(cfg.db_path)) as db:
        await db.executescript(SCHEMA_SQL)
        await db.commit()


async def connect(cfg: SQLiteConfig) -> aiosqlite.Connection:
    """
    Create a connection. Used by background worker (single writer).
    """
    ensure_parent_dir(cfg.db_path)
    db = await aiosqlite.connect(str(cfg.db_path))
    await db.execute("PRAGMA journal_mode=WAL;")
    await db.execute("PRAGMA synchronous=NORMAL;")
    return db
