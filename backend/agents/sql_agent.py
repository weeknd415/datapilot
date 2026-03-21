"""SQL Agent: Converts natural language to SQL and executes queries.

This agent handles Text-to-SQL conversion with:
- Schema-aware query generation
- SQL validation and safety checks
- Confidence scoring
- Result explanation in natural language
"""

from __future__ import annotations

import logging
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.llm import get_llm, invoke_llm_with_retry
from backend.core.models import AgentStep, AgentType, SQLQueryResult, SourceReference
from backend.db.database import execute_sql, get_sample_data, get_schema_info

logger = logging.getLogger(__name__)

SQL_SYSTEM_PROMPT = """You are an expert SQL analyst. Your job is to convert natural language questions into accurate SQL queries.

DATABASE SCHEMA:
{schema}

SAMPLE DATA:
{sample_data}

RULES:
1. Only generate SELECT or WITH (CTE) queries — never modify data.
2. Use table and column names exactly as shown in the schema.
3. When the question is ambiguous, make reasonable assumptions and note them.
4. For date-based questions, use SQLite date functions.
5. Always include relevant column aliases for readability.
6. Prefer JOINs over subqueries when both are equally readable.

RESPONSE FORMAT:
Return ONLY a JSON object (no markdown, no code fences):
{{
    "sql": "YOUR SQL QUERY HERE",
    "confidence": 0.0 to 1.0,
    "explanation": "Brief explanation of what the query does and any assumptions made",
    "tables_used": ["table1", "table2"]
}}

If the question cannot be answered with the available schema, return:
{{
    "sql": "",
    "confidence": 0.0,
    "explanation": "Reason why the question cannot be answered",
    "tables_used": []
}}"""

EXPLAIN_SYSTEM_PROMPT = """You are a business analyst. Given a SQL query, its results, and the original question,
provide a clear natural language answer. Be concise and highlight key numbers.
If the results are empty, explain what that means in business context.
Format numbers with commas and currency symbols where appropriate."""


class SQLAgent:
    """Agent that converts natural language to SQL and returns business answers."""

    def __init__(self, provider: str | None = None) -> None:
        self.llm = get_llm(provider=provider, temperature=0)
        self._schema_cache: str | None = None

    def _get_schema(self) -> str:
        if self._schema_cache is None:
            self._schema_cache = get_schema_info()
        return self._schema_cache

    def _get_sample_data_str(self) -> str:
        """Get formatted sample data for a few key tables."""
        schema = self._get_schema()
        # Extract table names from schema
        tables = []
        for line in schema.split("\n"):
            if line.startswith("-- "):
                table_name = line.split(":")[0].replace("-- ", "").strip()
                tables.append(table_name)

        sample_parts = []
        for table in tables[:5]:  # Limit to 5 tables
            try:
                samples = get_sample_data(table, limit=2)
                if samples:
                    sample_parts.append(f"{table}: {samples}")
            except Exception:
                pass
        return "\n".join(sample_parts)

    async def process(self, question: str) -> tuple[SQLQueryResult, list[AgentStep]]:
        """Process a natural language question and return SQL results."""
        steps: list[AgentStep] = []
        start_time = time.time()

        # Step 1: Generate SQL
        schema = self._get_schema()
        sample_data = self._get_sample_data_str()

        gen_start = time.time()
        messages = [
            SystemMessage(content=SQL_SYSTEM_PROMPT.format(schema=schema, sample_data=sample_data)),
            HumanMessage(content=question),
        ]

        response = await invoke_llm_with_retry(self.llm, messages)
        gen_duration = int((time.time() - gen_start) * 1000)

        # Parse the LLM response
        try:
            import json

            content = response.content.strip()
            # Handle potential markdown code fences
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            parsed = json.loads(content)
        except (json.JSONDecodeError, IndexError):
            return SQLQueryResult(
                sql_query="",
                confidence=0.0,
                explanation="Failed to parse LLM response for SQL generation.",
                error="LLM returned invalid JSON",
            ), steps

        sql_query = parsed.get("sql", "")
        confidence = float(parsed.get("confidence", 0.0))
        explanation = parsed.get("explanation", "")
        tables_used = parsed.get("tables_used", [])

        steps.append(AgentStep(
            agent=AgentType.SQL,
            action="generate_sql",
            input_summary=question[:100],
            output_summary=f"SQL: {sql_query[:100]}",
            confidence=confidence,
            duration_ms=gen_duration,
        ))

        if not sql_query:
            return SQLQueryResult(
                sql_query="",
                confidence=confidence,
                explanation=explanation,
            ), steps

        # Step 2: Execute SQL
        exec_start = time.time()
        try:
            rows, columns = execute_sql(sql_query)
            exec_duration = int((time.time() - exec_start) * 1000)

            steps.append(AgentStep(
                agent=AgentType.SQL,
                action="execute_sql",
                input_summary=sql_query[:100],
                output_summary=f"{len(rows)} rows returned",
                confidence=confidence,
                duration_ms=exec_duration,
            ))

        except (ValueError, Exception) as e:
            exec_duration = int((time.time() - exec_start) * 1000)
            steps.append(AgentStep(
                agent=AgentType.SQL,
                action="execute_sql",
                input_summary=sql_query[:100],
                output_summary=f"Error: {str(e)[:100]}",
                confidence=0.0,
                duration_ms=exec_duration,
            ))
            return SQLQueryResult(
                sql_query=sql_query,
                confidence=0.0,
                explanation=explanation,
                error=str(e),
            ), steps

        # Step 3: Generate natural language explanation
        explain_start = time.time()
        explain_messages = [
            SystemMessage(content=EXPLAIN_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Question: {question}\n"
                f"SQL Query: {sql_query}\n"
                f"Results ({len(rows)} rows): {str(rows[:20])}\n"
                f"Columns: {columns}"
            )),
        ]
        explain_response = await invoke_llm_with_retry(self.llm, explain_messages)
        explain_duration = int((time.time() - explain_start) * 1000)

        steps.append(AgentStep(
            agent=AgentType.SQL,
            action="explain_results",
            input_summary=f"{len(rows)} rows to explain",
            output_summary=explain_response.content[:100],
            confidence=confidence,
            duration_ms=explain_duration,
        ))

        return SQLQueryResult(
            sql_query=sql_query,
            results=rows[:100],  # Cap at 100 rows
            columns=columns,
            row_count=len(rows),
            confidence=confidence,
            explanation=explain_response.content,
        ), steps

    def get_sources(self, result: SQLQueryResult) -> list[SourceReference]:
        """Extract source references from SQL result."""
        sources = []
        if result.sql_query:
            sources.append(SourceReference(
                source_type="sql_query",
                source_name="Business Database",
                details=f"Query: {result.sql_query} | {result.row_count} rows",
            ))
        return sources
