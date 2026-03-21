"""Shared data models used across agents and API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    SQL = "sql_agent"
    DOCUMENT = "document_agent"
    ANALYTICS = "analytics_agent"
    SUPERVISOR = "supervisor"


class QueryStatus(str, Enum):
    PENDING = "pending"
    ROUTING = "routing"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_CLARIFICATION = "needs_clarification"


class AgentStep(BaseModel):
    """A single step in the agent execution trace."""

    agent: AgentType
    action: str
    input_summary: str = ""
    output_summary: str = ""
    confidence: float = 0.0
    duration_ms: int = 0
    token_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SourceReference(BaseModel):
    """A reference to the source of information."""

    source_type: str  # "sql_table", "document", "calculation"
    source_name: str
    details: str = ""


class QueryRequest(BaseModel):
    """Incoming user query."""

    query: str
    session_id: str = ""
    include_trace: bool = True


class QueryResponse(BaseModel):
    """Complete response to a user query."""

    query: str
    answer: str
    confidence: float = 0.0
    sources: list[SourceReference] = []
    trace: list[AgentStep] = []
    status: QueryStatus = QueryStatus.COMPLETED
    cost_usd: float = 0.0
    total_tokens: int = 0
    duration_ms: int = 0
    chart_base64: str | None = None
    chart_type: str | None = None
    error: str | None = None


class SQLQueryResult(BaseModel):
    """Result from the SQL agent."""

    sql_query: str
    results: list[dict[str, Any]] = []
    columns: list[str] = []
    row_count: int = 0
    confidence: float = 0.0
    explanation: str = ""
    error: str | None = None


class DocumentChunk(BaseModel):
    """A chunk of extracted document content."""

    content: str
    source_file: str
    page_number: int = 0
    chunk_index: int = 0
    metadata: dict[str, Any] = {}


class DocumentResult(BaseModel):
    """Result from the Document agent."""

    chunks: list[DocumentChunk] = []
    summary: str = ""
    extracted_data: dict[str, Any] = {}
    confidence: float = 0.0
    error: str | None = None


class AnalyticsResult(BaseModel):
    """Result from the Analytics agent."""

    analysis: str = ""
    data: dict[str, Any] = {}
    chart_base64: str | None = None
    chart_type: str | None = None
    confidence: float = 0.0
    error: str | None = None
