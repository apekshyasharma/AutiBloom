from __future__ import annotations

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator, Optional

from fastapi import Request

# Thread pool for CPU-bound RAG operations
_executor = ThreadPoolExecutor(max_workers=4)


def _sse(event: str, data: dict) -> bytes:
    payload = f"event: {event}\n" + f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    return payload.encode("utf-8")


def _chunk_text_words(text: str, words_per_chunk: int = 1):
    if not text:
        return
    words = text.split(" ")
    buf = []
    for w in words:
        buf.append(w)
        if len(buf) >= words_per_chunk:
            yield " ".join(buf) + " "
            buf = []
    if buf:
        yield " ".join(buf) + " "


async def stream_rag_sse(
    rag,
    query: str,
    mode: str,
    request: Request,
    log_service: Optional[object] = None,
    session_id: Optional[str] = None,
    request_id: Optional[str] = None,
    delay_s: float = 0.07,
) -> AsyncGenerator[bytes, None]:
    t0 = time.perf_counter()
    answer_text = ""
    mode_used = mode

    try:
        if await request.is_disconnected():
            return

        # Run blocking RAG in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            lambda: rag.answer(query=query, mode=mode)
        )
        answer_text = result.answer or ""
        mode_used = getattr(result, "mode_used", mode)

        latency_ms = int((time.perf_counter() - t0) * 1000)

        # Log assistant message + request completed (non-blocking)
        if log_service and session_id and request_id:
            await log_service.log_assistant_message(session_id, answer_text)
            await log_service.log_request_completed(request_id, mode_used, latency_ms)

        # Stream word-by-word
        for piece in _chunk_text_words(answer_text, words_per_chunk=1):
            if await request.is_disconnected():
                return
            yield _sse("token", {"text": piece})
            await asyncio.sleep(delay_s)

        yield _sse("done", {"ok": True, "mode_used": mode_used})

    except Exception as e:
        latency_ms = int((time.perf_counter() - t0) * 1000)

        if log_service and request_id:
            await log_service.log_request_error(request_id, str(e), latency_ms)

        yield _sse("error", {"message": str(e)})
