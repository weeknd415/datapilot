"""MCP Server for the Document Agent.

Exposes document processing capabilities as an MCP server.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastmcp import FastMCP

from backend.agents.document_agent import DocumentAgent

mcp = FastMCP(
    "DataPilot Document Agent",
    description="Process and query business documents (PDFs, invoices, contracts)",
)

_agent: DocumentAgent | None = None


def _get_agent() -> DocumentAgent:
    global _agent
    if _agent is None:
        _agent = DocumentAgent()
    return _agent


@mcp.tool()
async def search_documents(question: str) -> str:
    """Search through ingested business documents to answer a question.

    Args:
        question: A natural language question about document contents
                  (e.g., "What are the payment terms in the contract?")

    Returns:
        JSON string with relevant document excerpts and an answer.
    """
    agent = _get_agent()
    result, steps = await agent.process(question)
    return json.dumps(
        {
            "answer": result.summary,
            "confidence": result.confidence,
            "sources": [
                {"file": c.source_file, "page": c.page_number, "excerpt": c.content[:200]}
                for c in result.chunks[:5]
            ],
        },
        indent=2,
    )


@mcp.tool()
def ingest_document(file_path: str) -> str:
    """Ingest a document file for searching. Supports PDF, TXT, MD, CSV.

    Args:
        file_path: Absolute path to the document file

    Returns:
        JSON string with ingestion results.
    """
    agent = _get_agent()
    try:
        chunks = agent.ingest_file(file_path)
        return json.dumps({
            "status": "success",
            "file": Path(file_path).name,
            "chunks_created": len(chunks),
        })
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


@mcp.tool()
async def extract_document_data(file_path: str) -> str:
    """Extract structured data (dates, amounts, parties) from a document.

    Args:
        file_path: Absolute path to the document file

    Returns:
        JSON string with extracted structured data.
    """
    agent = _get_agent()
    try:
        data, steps = await agent.extract_structured(file_path)
        return json.dumps(data, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    mcp.run()
