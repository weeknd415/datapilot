"""Tests for data models."""

from backend.core.models import (
    AgentStep,
    AgentType,
    QueryRequest,
    QueryResponse,
    QueryStatus,
    SQLQueryResult,
    SourceReference,
)


def test_query_request():
    req = QueryRequest(query="What are the top customers?")
    assert req.query == "What are the top customers?"
    assert req.include_trace is True


def test_query_response():
    resp = QueryResponse(
        query="test",
        answer="The top customer is Acme Corp.",
        confidence=0.95,
        sources=[
            SourceReference(
                source_type="sql_query",
                source_name="Business Database",
                details="SELECT * FROM customers",
            )
        ],
        status=QueryStatus.COMPLETED,
    )
    assert resp.confidence == 0.95
    assert len(resp.sources) == 1
    assert resp.status == QueryStatus.COMPLETED


def test_agent_step():
    step = AgentStep(
        agent=AgentType.SQL,
        action="generate_sql",
        input_summary="What are the top customers?",
        confidence=0.9,
        duration_ms=150,
    )
    assert step.agent == AgentType.SQL
    assert step.duration_ms == 150


def test_sql_query_result():
    result = SQLQueryResult(
        sql_query="SELECT * FROM customers LIMIT 5",
        results=[{"id": 1, "company_name": "Acme Corp"}],
        columns=["id", "company_name"],
        row_count=1,
        confidence=0.88,
        explanation="Query returns customer data",
    )
    assert result.row_count == 1
    assert result.error is None
