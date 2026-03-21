"""Database connection and schema introspection for SQL Agent."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.engine import Engine

from backend.core.config import settings

logger = logging.getLogger(__name__)

_engine: Engine | None = None


def get_engine() -> Engine:
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        db_url = settings.database_url.replace("sqlite+aiosqlite", "sqlite")
        _engine = create_engine(db_url, echo=False)
    return _engine


def get_schema_info() -> str:
    """Get human-readable database schema for LLM context."""
    engine = get_engine()
    inspector = inspect(engine)
    schema_parts: list[str] = []

    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        col_defs = []
        for col in columns:
            nullable = "" if col.get("nullable", True) else " NOT NULL"
            col_defs.append(f"  {col['name']} {col['type']}{nullable}")

        pk = inspector.get_pk_constraint(table_name)
        pk_cols = pk.get("constrained_columns", []) if pk else []

        fks = inspector.get_foreign_keys(table_name)
        fk_lines = []
        for fk in fks:
            fk_lines.append(
                f"  FOREIGN KEY ({', '.join(fk['constrained_columns'])}) "
                f"REFERENCES {fk['referred_table']}({', '.join(fk['referred_columns'])})"
            )

        table_sql = f"CREATE TABLE {table_name} (\n"
        table_sql += ",\n".join(col_defs)
        if pk_cols:
            table_sql += f",\n  PRIMARY KEY ({', '.join(pk_cols)})"
        if fk_lines:
            table_sql += ",\n" + ",\n".join(fk_lines)
        table_sql += "\n);"

        # Get row count
        with engine.connect() as conn:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()

        schema_parts.append(f"-- {table_name}: {count} rows\n{table_sql}")

    return "\n\n".join(schema_parts)


def get_sample_data(table_name: str, limit: int = 3) -> list[dict[str, Any]]:
    """Get sample rows from a table for LLM context."""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT * FROM {table_name} LIMIT {limit}"))
        columns = list(result.keys())
        return [dict(zip(columns, row)) for row in result.fetchall()]


def execute_sql(query: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Execute a SQL query and return results.

    Only allows SELECT queries for safety.
    """
    normalized = query.strip().upper()
    if not normalized.startswith("SELECT") and not normalized.startswith("WITH"):
        raise ValueError("Only SELECT and WITH (CTE) queries are allowed for safety.")

    dangerous_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "EXEC"]
    for kw in dangerous_keywords:
        if kw in normalized:
            raise ValueError(f"Query contains forbidden keyword: {kw}")

    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(query))
        columns = list(result.keys())
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
        return rows, columns
