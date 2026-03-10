from __future__ import annotations

import time
import asyncio
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Tuple


@dataclass(frozen=True)
class RateLimitRule:
    max_requests: int
    window_seconds: int


class RateLimiter:
    """
    In-memory sliding-window rate limiter.
    Good for single-node dev/prod. For multi-node, replace with Redis.
    """
    def __init__(self, per_session: RateLimitRule, per_ip: RateLimitRule):
        self.per_session = per_session
        self.per_ip = per_ip
        self._session_hits: Dict[str, Deque[float]] = {}
        self._ip_hits: Dict[str, Deque[float]] = {}
        self._lock = asyncio.Lock()

    def _allow(self, dq: Deque[float], rule: RateLimitRule, now: float) -> bool:
        cutoff = now - rule.window_seconds
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= rule.max_requests:
            return False
        dq.append(now)
        return True

    async def check(self, session_id: str, ip: str | None) -> Tuple[bool, str]:
        """
        Returns (allowed, reason_if_denied).
        """
        now = time.time()
        async with self._lock:
            sdq = self._session_hits.setdefault(session_id, deque())
            if not self._allow(sdq, self.per_session, now):
                return False, f"Rate limit exceeded for session: {self.per_session.max_requests}/{self.per_session.window_seconds}s"

            if ip:
                idq = self._ip_hits.setdefault(ip, deque())
                if not self._allow(idq, self.per_ip, now):
                    return False, f"Rate limit exceeded for IP: {self.per_ip.max_requests}/{self.per_ip.window_seconds}s"

        return True, ""
