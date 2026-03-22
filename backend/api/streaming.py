"""Server-Sent Events (SSE) endpoint for streaming agent responses."""

from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.agents.supervisor import SupervisorAgent
from backend.core.config import settings
from backend.core.models import QueryRequest
from backend.core.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)

sse_router = APIRouter()

_supervisor: SupervisorAgent | None = None


def get_supervisor() -> SupervisorAgent:
    global _supervisor
    if _supervisor is None:
        _supervisor = SupervisorAgent()
    return _supervisor


def _sse_event(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event."""
    payload = json.dumps(data)
    return f"event: {event_type}\ndata: {payload}\n\n"


@sse_router.post("/query/stream")
async def stream_query(request: QueryRequest, req: Request) -> StreamingResponse:
    """Stream query processing via Server-Sent Events.

    Events emitted:
    - event: status   — routing/processing updates
    - event: step     — individual agent step completed
    - event: result   — final answer with sources and confidence
    - event: error    — error occurred during processing
    """
    if settings.guest_mode:
        rate_limiter.check(req)

    async def event_generator():
        yield _sse_event("status", {
            "agent": "supervisor",
            "action": "routing",
            "message": "Analyzing your question...",
        })

        start = time.time()
        supervisor = get_supervisor()

        try:
            response = await supervisor.process(
                request.query,
                session_id=request.session_id,
            )
            duration = int((time.time() - start) * 1000)

            # Stream each trace step
            for step in response.trace:
                yield _sse_event("step", {
                    "agent": step.agent.value,
                    "action": step.action,
                    "input": step.input_summary,
                    "output": step.output_summary,
                    "confidence": step.confidence,
                    "duration_ms": step.duration_ms,
                })

            # Final result
            result_data = {
                "answer": response.answer,
                "confidence": response.confidence,
                "sources": [s.model_dump() for s in response.sources],
                "status": response.status.value,
                "duration_ms": duration,
                "total_tokens": response.total_tokens,
            }

            if response.chart_base64:
                result_data["chart_base64"] = response.chart_base64
                result_data["chart_type"] = response.chart_type

            yield _sse_event("result", result_data)

        except Exception as e:
            logger.error("SSE stream error: %s", e, exc_info=True)
            yield _sse_event("error", {"message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
