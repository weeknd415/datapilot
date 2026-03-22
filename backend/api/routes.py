"""FastAPI routes for DataPilot API."""

from __future__ import annotations

import csv
import io
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from backend.agents.supervisor import SupervisorAgent
from backend.core.config import settings
from backend.core.models import QueryRequest, QueryResponse
from backend.core.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)

router = APIRouter()

_supervisor: SupervisorAgent | None = None


def get_supervisor() -> SupervisorAgent:
    global _supervisor
    if _supervisor is None:
        _supervisor = SupervisorAgent()
    return _supervisor


@router.post("/query", response_model=QueryResponse)
async def process_query(
    request: QueryRequest,
    req: Request,
) -> QueryResponse:
    """Process a natural language query through the agent pipeline.

    Rate-limited in guest mode (10 queries/minute per IP).
    """
    if settings.guest_mode:
        rate_limiter.check(req)

    supervisor = get_supervisor()
    response = await supervisor.process(
        request.query,
        session_id=request.session_id,
    )
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
            detail=(
                f"Unsupported file type: {ext}. "
                f"Allowed: {allowed_extensions}"
            ),
        )

    # Save uploaded file
    upload_dir = settings.sample_docs_dir
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(
        upload_dir, f"{uuid.uuid4().hex[:8]}_{file.filename}"
    )

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
        "message": (
            f"Document ingested successfully. "
            f"{len(chunks)} chunks indexed."
        ),
    }


@router.get("/documents")
async def list_documents() -> dict:
    """List all documents in the sample docs directory."""
    docs_dir = settings.sample_docs_dir
    if not os.path.exists(docs_dir):
        return {"documents": []}

    supported_exts = {".pdf", ".txt", ".md", ".csv"}
    documents = []
    for f in os.listdir(docs_dir):
        if Path(f).suffix.lower() in supported_exts:
            full_path = os.path.join(docs_dir, f)
            stat = os.stat(full_path)
            documents.append({
                "filename": f,
                "size_bytes": stat.st_size,
                "modified": stat.st_mtime,
            })

    return {"documents": documents, "count": len(documents)}


@router.get("/export/csv")
async def export_csv(query: str, req: Request) -> StreamingResponse:
    """Run a query and export results as CSV download."""
    if settings.guest_mode:
        rate_limiter.check(req)

    supervisor = get_supervisor()
    response = await supervisor.process(query)

    # Build CSV from SQL results if available
    output = io.StringIO()
    writer = csv.writer(output)

    # Find SQL result data from trace
    sql_data = None
    for source in response.sources:
        if source.source_type == "sql_query":
            # Re-run the SQL to get raw data
            from backend.db.database import execute_sql

            try:
                # Extract SQL from source details
                details = source.details
                if "Query: " in details:
                    sql = details.split("Query: ")[1].split(" |")[0]
                    rows, columns = execute_sql(sql)
                    sql_data = (rows, columns)
            except Exception:
                pass

    if sql_data:
        rows, columns = sql_data
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row.get(col, "") for col in columns])
    else:
        writer.writerow(["answer", "confidence", "sources"])
        source_str = "; ".join(
            s.source_name for s in response.sources
        )
        writer.writerow([
            response.answer, response.confidence, source_str,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=datapilot_export.csv"
        },
    )


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
        "guest_mode": settings.guest_mode,
    }
