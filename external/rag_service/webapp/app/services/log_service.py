from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Any

import aiosqlite

from webapp.app.db.sqlite import SQLiteConfig, connect
from webapp.app.db import repos


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LogEvent:
    kind: str
    payload: dict[str, Any]


class LogService:
    """
    Non-blocking logging:
    - API handlers emit events into queue
    - a single background writer writes to SQLite
    """

    def __init__(self, cfg: SQLiteConfig):
        self.cfg = cfg
        self.queue: asyncio.Queue[LogEvent] = asyncio.Queue(maxsize=2000)
        self._stop = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self._db: Optional[aiosqlite.Connection] = None

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._db = await connect(self.cfg)
        self._task = asyncio.create_task(self._worker(), name="sqlite-log-writer")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()
        if self._db:
            # Checkpoint WAL to main DB before closing
            try:
                await self._db.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            except Exception:
                pass
            await self._db.close()
            self._db = None

    async def emit(self, kind: str, **payload) -> None:
        try:
            self.queue.put_nowait(LogEvent(kind=kind, payload=payload))
        except asyncio.QueueFull:
            # Drop logs instead of slowing the chatbot.
            pass

    # Convenience APIs
    async def log_session(self, session_id: str, user_agent: str | None, ip: str | None) -> None:
        ts = now_iso()
        await self.emit(
            "upsert_session",
            session_id=session_id,
            created_at=ts,
            last_seen_at=ts,
            user_agent=user_agent,
            ip=ip,
        )

    async def log_user_message(self, session_id: str, content: str) -> None:
        await self.emit("insert_message", session_id=session_id, role="user", content=content, created_at=now_iso())

    async def log_assistant_message(self, session_id: str, content: str) -> None:
        await self.emit("insert_message", session_id=session_id, role="assistant", content=content, created_at=now_iso())

    async def log_request_started(self, request_id: str, session_id: str, query: str, mode_requested: str) -> None:
        await self.emit(
            "request_started",
            request_id=request_id,
            session_id=session_id,
            query=query,
            mode_requested=mode_requested,
            created_at=now_iso(),
        )

    async def log_request_completed(self, request_id: str, mode_used: str, latency_ms: int) -> None:
        await self.emit(
            "request_completed",
            request_id=request_id,
            mode_used=mode_used,
            completed_at=now_iso(),
            latency_ms=latency_ms,
        )

    async def log_request_error(self, request_id: str, error_message: str, latency_ms: int | None = None) -> None:
        await self.emit(
            "request_error",
            request_id=request_id,
            error_message=error_message,
            completed_at=now_iso(),
            latency_ms=latency_ms,
        )

    async def _worker(self) -> None:
        assert self._db is not None
        db = self._db

        while not self._stop.is_set() or not self.queue.empty():
            try:
                ev = await asyncio.wait_for(self.queue.get(), timeout=0.25)
            except asyncio.TimeoutError:
                continue

            try:
                await self._handle(db, ev)
                await db.commit()
            except Exception as e:
                # Log error for debugging 
                print(f"[LogService] DB write error: {e}")
            finally:
                self.queue.task_done()

    async def _handle(self, db: aiosqlite.Connection, ev: LogEvent) -> None:
        p = ev.payload
        k = ev.kind

        if k == "upsert_session":
            await repos.upsert_session(db, **p)

        elif k == "insert_message":
            await repos.insert_message(db, **p)

        elif k == "request_started":
            await repos.request_started(db, **p)

        elif k == "request_completed":
            await repos.request_completed(db, **p)

        elif k == "request_error":
            await repos.request_error(db, **p)
