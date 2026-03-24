"""Tests for database operations."""

import pytest

from backend.db.database import execute_sql, get_sample_data, get_schema_info


def test_get_schema_info():
    """Schema info should contain all expected SaaS tables."""
    schema = get_schema_info()
    assert "accounts" in schema
    assert "subscriptions" in schema
    assert "mrr_events" in schema
    assert "feature_usage" in schema
    assert "support_tickets" in schema
    assert "invoices" in schema


def test_execute_select_query():
    """SELECT queries should return results."""
    rows, columns = execute_sql("SELECT COUNT(*) as total FROM accounts")
    assert len(rows) == 1
    assert rows[0]["total"] == 40


def test_execute_join_query():
    """JOIN queries should work correctly."""
    rows, columns = execute_sql("""
        SELECT a.company_name, COUNT(t.id) as ticket_count
        FROM accounts a
        JOIN support_tickets t ON a.id = t.account_id
        GROUP BY a.company_name
        ORDER BY ticket_count DESC
        LIMIT 5
    """)
    assert len(rows) == 5
    assert "company_name" in columns
    assert "ticket_count" in columns


def test_execute_cte_query():
    """CTE (WITH) queries should work."""
    rows, columns = execute_sql("""
        WITH monthly_mrr AS (
            SELECT strftime('%Y-%m', event_date) as month,
                   SUM(mrr_delta) as net_mrr
            FROM mrr_events
            GROUP BY month
        )
        SELECT * FROM monthly_mrr ORDER BY month DESC LIMIT 3
    """)
    assert len(rows) == 3


def test_reject_dangerous_queries():
    """Dangerous queries should be rejected."""
    with pytest.raises(ValueError, match="Only SELECT"):
        execute_sql("DELETE FROM accounts WHERE id = 1")

    with pytest.raises(ValueError, match="Only SELECT"):
        execute_sql("DROP TABLE accounts")

    with pytest.raises(ValueError, match="Only SELECT"):
        execute_sql(
            "INSERT INTO accounts VALUES "
            "(99, 'Evil', 'evil.com', 'Free', 0, 0, 'active', 'Tech', 10, "
            "'2024-01-01', NULL, 'NA', NULL)"
        )

    with pytest.raises(ValueError, match="forbidden keyword"):
        execute_sql("SELECT * FROM accounts; DROP TABLE accounts")


def test_get_sample_data():
    """Sample data should return correct number of rows."""
    samples = get_sample_data("accounts", limit=3)
    assert len(samples) == 3
    assert "company_name" in samples[0]
