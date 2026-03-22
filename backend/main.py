"""DataPilot FastAPI application entry point."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.api.streaming import sse_router
from backend.api.websocket import ws_router
from backend.core.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def _auto_ingest_documents() -> None:
    """Auto-ingest sample documents on startup."""
    from backend.api.routes import get_supervisor

    docs_dir = str(settings.sample_docs_dir)
    if not os.path.exists(docs_dir):
        return

    supervisor = get_supervisor()
    supported = {".pdf", ".txt", ".md", ".csv"}
    ingested = 0

    for fname in os.listdir(docs_dir):
        ext = os.path.splitext(fname)[1].lower()
        if ext in supported:
            fpath = os.path.join(docs_dir, fname)
            try:
                supervisor.document_agent.ingest_file(fpath)
                ingested += 1
            except Exception as e:
                logger.warning("Failed to ingest %s: %s", fname, e)

    if ingested:
        logger.info(
            "Auto-ingested %d documents from %s", ingested, docs_dir
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    logger.info(
        "DataPilot starting in %s mode on %s:%d",
        settings.env,
        settings.host,
        settings.port,
    )

    # Auto-ingest sample documents
    if settings.auto_ingest_docs:
        _auto_ingest_documents()
        logger.info("Guest mode: %s", settings.guest_mode)

    yield


app = FastAPI(
    title="DataPilot",
    description=(
        "Multi-agent Business Intelligence system with Text-to-SQL, "
        "Document AI, LangGraph orchestration, and MCP servers"
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://datapilot-tiqv.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api", tags=["DataPilot API"])
app.include_router(sse_router, prefix="/api", tags=["SSE Streaming"])
app.include_router(ws_router, tags=["WebSocket"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.env == "development",
    )
