from __future__ import annotations

import asyncio
import uuid
from typing import Dict, Any

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from webapp.app.services.rag_service import stream_rag_sse


router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str
    message: str
    mode: str = "auto"  # fixed | semantic | auto


class ChatAccepted(BaseModel):
    session_id: str
    request_id: str


def _ensure_state(app):
    """Initialize in-memory pending request store once."""
    if not hasattr(app.state, "pending_requests"):
        app.state.pending_requests: Dict[str, Dict[str, Any]] = {}
    if not hasattr(app.state, "pending_lock"):
        app.state.pending_lock = asyncio.Lock()


@router.post("/message", response_model=ChatAccepted)
async def message(req: ChatRequest, request: Request):
    """
    Accept a user message and return a request_id.
    The actual answer is streamed from /api/stream using SSE.
    """
    _ensure_state(request.app)

    # ---- Rate limiting----
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter:
        ip = request.client.host if request.client else None
        allowed, reason = await limiter.check(req.session_id, ip)
        if not allowed:
            raise HTTPException(status_code=429, detail=reason)

    request_id = str(uuid.uuid4())

    payload = {
        "session_id": req.session_id,
        "query": req.message,
        "mode": req.mode,
        "request_id": request_id,
    }

    async with request.app.state.pending_lock:
        request.app.state.pending_requests[request_id] = payload

    # ---- Logging (non-blocking) ----
    log = getattr(request.app.state, "log_service", None)
    if log:
        ua = request.headers.get("user-agent")
        ip = request.client.host if request.client else None
        await log.log_session(req.session_id, ua, ip)
        await log.log_user_message(req.session_id, req.message)
        await log.log_request_started(request_id, req.session_id, req.message, req.mode)

    return ChatAccepted(session_id=req.session_id, request_id=request_id)


@router.get("/stream")
async def stream(session_id: str, request_id: str, request: Request):
    """
    SSE endpoint. Streams token-by-token-ish events:
      event: token  data: {"text":"..."}
      event: done   data: {"ok":true}
      event: error  data: {"message":"..."}
    """
    _ensure_state(request.app)

    # Retrieve and remove the pending payload (one-time stream)
    async with request.app.state.pending_lock:
        payload = request.app.state.pending_requests.pop(request_id, None)

    if not payload:
        raise HTTPException(status_code=404, detail="Unknown or expired request_id")

    if payload["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="session_id mismatch")

    # Get pipeline and logger from startup
    rag = request.app.state.rag_pipeline
    log = getattr(request.app.state, "log_service", None)

    async def event_generator():
        # stream_rag_sse yields properly formatted SSE bytes
        async for chunk in stream_rag_sse(
            rag=rag,
            query=payload["query"],
            mode=payload["mode"],
            request=request,
            log_service=log,
            session_id=session_id,
            request_id=request_id,
        ):
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )
