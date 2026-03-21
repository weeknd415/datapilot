"""MCP Server for the SQL Agent.

Exposes Text-to-SQL capabilities as an MCP server that can be used
by Claude Desktop, Cursor, or any MCP-compatible client.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastmcp import FastMCP

from backend.agents.sql_agent import SQLAgent
from backend.db.database import execute_sql, get_schema_info

mcp = FastMCP(
    "DataPilot SQL Agent",
    description="Convert natural language questions to SQL queries against a business database",
)

_agent: SQLAgent | None = None


def _get_agent() -> SQLAgent:
    global _agent
    if _agent is None:
        _agent = SQLAgent()
    return _agent


@mcp.tool()
async def query_database(question: str) -> str:
    """Convert a natural language question to SQL and execute it against the business database.

    Args:
        question: A natural language question about business data
                  (e.g., "What are the top 5 customers by revenue?")

    Returns:
        A JSON string with the SQL query, results, and natural language explanation.
    """
    agent = _get_agent()
    result, steps = await agent.process(question)
    return json.dumps(
        {
            "sql_query": result.sql_query,
            "explanation": result.explanation,
            "row_count": result.row_count,
            "results": result.results[:20],  # Limit for MCP response size
            "confidence": result.confidence,
            "columns": result.columns,
        },
        indent=2,
        default=str,
    )


@mcp.tool()
def get_database_schema() -> str:
    """Get the complete database schema including table definitions and row counts.

    Returns:
        A string containing SQL CREATE TABLE statements for all tables.
    """
    return get_schema_info()


@mcp.tool()
def run_sql(sql_query: str) -> str:
    """Execute a raw SQL SELECT query against the business database.

    Only SELECT and WITH (CTE) queries are allowed for safety.

    Args:
        sql_query: A valid SQL SELECT query

    Returns:
        JSON string with query results.
    """
    try:
        rows, columns = execute_sql(sql_query)
        return json.dumps(
            {"columns": columns, "rows": rows[:50], "total_rows": len(rows)},
            indent=2,
            default=str,
        )
    except ValueError as e:
        return json.dumps({"error": str(e)})


@mcp.resource("schema://database")
def database_schema_resource() -> str:
    """The complete database schema as a resource."""
    return get_schema_info()


if __name__ == "__main__":
    mcp.run()
