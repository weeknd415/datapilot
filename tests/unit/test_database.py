"""Tests for database operations."""

import pytest

from backend.db.database import execute_sql, get_sample_data, get_schema_info


def test_get_schema_info():
    """Schema info should contain all expected tables."""
    schema = get_schema_info()
    assert "customers" in schema
    assert "orders" in schema
    assert "products" in schema
    assert "invoices" in schema
    assert "employees" in schema
    assert "departments" in schema
    assert "order_items" in schema


def test_execute_select_query():
    """SELECT queries should return results."""
    rows, columns = execute_sql("SELECT COUNT(*) as total FROM customers")
    assert len(rows) == 1
    assert rows[0]["total"] == 30


def test_execute_join_query():
    """JOIN queries should work correctly."""
    rows, columns = execute_sql("""
        SELECT c.company_name, COUNT(o.id) as order_count
        FROM customers c
        JOIN orders o ON c.id = o.customer_id
        GROUP BY c.company_name
        ORDER BY order_count DESC
        LIMIT 5
    """)
    assert len(rows) == 5
    assert "company_name" in columns
    assert "order_count" in columns


def test_execute_cte_query():
    """CTE (WITH) queries should work."""
    rows, columns = execute_sql("""
        WITH monthly_revenue AS (
            SELECT strftime('%Y-%m', order_date) as month,
                   SUM(total_amount) as revenue
            FROM orders
            WHERE status != 'Cancelled'
            GROUP BY month
        )
        SELECT * FROM monthly_revenue ORDER BY month DESC LIMIT 3
    """)
    assert len(rows) == 3


def test_reject_dangerous_queries():
    """Dangerous queries should be rejected."""
    with pytest.raises(ValueError, match="Only SELECT"):
        execute_sql("DELETE FROM customers WHERE id = 1")

    with pytest.raises(ValueError, match="Only SELECT"):
        execute_sql("DROP TABLE customers")

    with pytest.raises(ValueError, match="Only SELECT"):
        execute_sql(
            "INSERT INTO customers VALUES (99, 'Evil', 'H', '', '', '', '', '', '')"
        )

    # Keyword check catches dangerous keywords inside SELECT
    with pytest.raises(ValueError, match="forbidden keyword"):
        execute_sql("SELECT * FROM customers; DROP TABLE customers")


def test_get_sample_data():
    """Sample data should return correct number of rows."""
    samples = get_sample_data("customers", limit=3)
    assert len(samples) == 3
    assert "company_name" in samples[0]
