"""WebSocket endpoint for streaming agent responses."""

from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.agents.supervisor import SupervisorAgent

logger = logging.getLogger(__name__)

ws_router = APIRouter()

_supervisor: SupervisorAgent | None = None


def get_supervisor() -> SupervisorAgent:
    global _supervisor
    if _supervisor is None:
        _supervisor = SupervisorAgent()
    return _supervisor


@ws_router.websocket("/ws/query")
async def websocket_query(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming query processing.

    Sends real-time updates as each agent processes the query:
    - {"type": "status", "agent": "supervisor", "action": "routing", ...}
    - {"type": "step", "agent": "sql_agent", "action": "generating_sql", ...}
    - {"type": "result", "answer": "...", "confidence": 0.9, ...}
    """
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            query = message.get("query", "")

            if not query:
                await websocket.send_json({"type": "error", "message": "Empty query"})
                continue

            # Send routing status
            await websocket.send_json({
                "type": "status",
                "agent": "supervisor",
                "action": "routing",
                "message": "Analyzing your question...",
            })

            start = time.time()
            supervisor = get_supervisor()
            response = await supervisor.process(query)
            duration = int((time.time() - start) * 1000)

            # Send trace steps
            for step in response.trace:
                await websocket.send_json({
                    "type": "step",
                    "agent": step.agent.value,
                    "action": step.action,
                    "input": step.input_summary,
                    "output": step.output_summary,
                    "confidence": step.confidence,
                    "duration_ms": step.duration_ms,
                })

            # Send final result
            result_data = {
                "type": "result",
                "answer": response.answer,
                "confidence": response.confidence,
                "sources": [s.model_dump() for s in response.sources],
                "status": response.status.value,
                "duration_ms": duration,
                "total_tokens": response.total_tokens,
            }

            # Include chart if analytics produced one
            if response.trace:
                for step in response.trace:
                    if step.agent.value == "analytics_agent" and step.action == "generate_chart":
                        # Chart data would be in the analytics result
                        pass

            await websocket.send_json(result_data)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error("WebSocket error: %s", e, exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
