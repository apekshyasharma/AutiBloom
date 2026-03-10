from __future__ import annotations

from typing import Optional
import aiosqlite


async def upsert_session(
    db: aiosqlite.Connection,
    session_id: str,
    created_at: str,
    last_seen_at: str,
    user_agent: Optional[str],
    ip: Optional[str],
) -> None:
    await db.execute(
        """
        INSERT INTO sessions(session_id, created_at, last_seen_at, user_agent, ip)
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
          last_seen_at=excluded.last_seen_at,
          user_agent=COALESCE(excluded.user_agent, sessions.user_agent),
          ip=COALESCE(excluded.ip, sessions.ip)
        """,
        (session_id, created_at, last_seen_at, user_agent, ip),
    )


async def insert_message(
    db: aiosqlite.Connection,
    session_id: str,
    role: str,
    content: str,
    created_at: str,
) -> None:
    await db.execute(
        """
        INSERT INTO messages(session_id, role, content, created_at)
        VALUES(?, ?, ?, ?)
        """,
        (session_id, role, content, created_at),
    )


async def request_started(
    db: aiosqlite.Connection,
    request_id: str,
    session_id: str,
    query: str,
    mode_requested: str,
    created_at: str,
) -> None:
    await db.execute(
        """
        INSERT INTO requests(request_id, session_id, query, mode_requested, status, created_at)
        VALUES(?, ?, ?, ?, 'started', ?)
        """,
        (request_id, session_id, query, mode_requested, created_at),
    )


async def request_completed(
    db: aiosqlite.Connection,
    request_id: str,
    mode_used: str,
    completed_at: str,
    latency_ms: int,
) -> None:
    await db.execute(
        """
        UPDATE requests
        SET status='ok', mode_used=?, completed_at=?, latency_ms=?
        WHERE request_id=?
        """,
        (mode_used, completed_at, latency_ms, request_id),
    )


async def request_error(
    db: aiosqlite.Connection,
    request_id: str,
    error_message: str,
    completed_at: str,
    latency_ms: int | None = None,
) -> None:
    await db.execute(
        """
        UPDATE requests
        SET status='error', error_message=?, completed_at=?, latency_ms=COALESCE(?, latency_ms)
        WHERE request_id=?
        """,
        (error_message, completed_at, latency_ms, request_id),
    )
