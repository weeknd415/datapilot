"""FastAPI routes for DataPilot API."""

from __future__ import annotations

import logging
import os
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.agents.supervisor import SupervisorAgent
from backend.core.config import settings
from backend.core.models import QueryRequest, QueryResponse

logger = logging.getLogger(__name__)

router = APIRouter()

_supervisor: SupervisorAgent | None = None


def get_supervisor() -> SupervisorAgent:
    global _supervisor
    if _supervisor is None:
        _supervisor = SupervisorAgent()
    return _supervisor


@router.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest) -> QueryResponse:
    """Process a natural language query through the agent pipeline.

    The supervisor agent routes the query to appropriate specialist agents
    (SQL, Document, Analytics) and returns a synthesized answer.
    """
    supervisor = get_supervisor()
    response = await supervisor.process(request.query)
    return response


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)) -> dict:
    """Upload a document for the Document Agent to process.

    Supports PDF, TXT, MD, and CSV files.
    """
    allowed_extensions = {".pdf", ".txt", ".md", ".csv"}
    ext = Path(file.filename or "").suffix.lower()

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {allowed_extensions}",
        )

    # Save uploaded file
    upload_dir = settings.sample_docs_dir
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{uuid.uuid4().hex[:8]}_{file.filename}")

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Ingest into Document Agent
    supervisor = get_supervisor()
    chunks = supervisor.document_agent.ingest_file(file_path)

    return {
        "status": "success",
        "filename": file.filename,
        "file_path": file_path,
        "chunks_created": len(chunks),
        "message": f"Document ingested successfully. {len(chunks)} chunks indexed.",
    }


@router.get("/schema")
async def get_schema() -> dict:
    """Get the database schema information."""
    from backend.db.database import get_schema_info

    return {"schema": get_schema_info()}


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "environment": settings.env,
    }
