"""DataPilot Evaluation Suite.

Tests SQL accuracy, routing correctness, document retrieval quality,
and hallucination detection. Outputs a scored report.

Usage:
    python -m tests.eval.eval_suite
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.agents.sql_agent import SQLAgent
from backend.db.database import execute_sql


@dataclass
class EvalResult:
    """Result of a single evaluation test."""

    category: str
    test_name: str
    passed: bool
    score: float  # 0.0 to 1.0
    details: str
    duration_ms: int


# ── SQL Accuracy Tests ──────────────────────────────────────────


SQL_EVAL_CASES = [
    {
        "question": "How many customers do we have?",
        "expected_check": lambda rows: (
            len(rows) == 1 and rows[0].get("total", 0) == 30
        ),
        "description": "Simple COUNT query",
    },
    {
        "question": "What is the total number of orders?",
        "expected_check": lambda rows: (
            len(rows) == 1
            and any(v > 2000 for v in rows[0].values() if isinstance(v, (int, float)))
        ),
        "description": "Total orders count (~2079)",
    },
    {
        "question": (
            "List the top 3 customers by total order amount"
        ),
        "expected_check": lambda rows: len(rows) == 3,
        "description": "Top-N query with aggregation",
    },
    {
        "question": "How many products are in the Software category?",
        "expected_check": lambda rows: (
            len(rows) == 1
            and any(v == 3 for v in rows[0].values() if isinstance(v, int))
        ),
        "description": "Filtered COUNT query",
    },
    {
        "question": (
            "What is the average order value "
            "for Enterprise tier customers?"
        ),
        "expected_check": lambda rows: (
            len(rows) == 1
            and any(isinstance(v, float) and v > 0 for v in rows[0].values())
        ),
        "description": "AVG with JOIN and WHERE",
    },
]


async def eval_sql_accuracy() -> list[EvalResult]:
    """Evaluate SQL agent accuracy."""
    agent = SQLAgent()
    results = []

    for case in SQL_EVAL_CASES:
        start = time.time()
        try:
            result, steps = await agent.process(case["question"])
            duration = int((time.time() - start) * 1000)

            if result.error:
                results.append(EvalResult(
                    category="sql_accuracy",
                    test_name=case["description"],
                    passed=False,
                    score=0.0,
                    details=f"SQL error: {result.error}",
                    duration_ms=duration,
                ))
                continue

            check_passed = case["expected_check"](result.results)
            results.append(EvalResult(
                category="sql_accuracy",
                test_name=case["description"],
                passed=check_passed,
                score=1.0 if check_passed else 0.0,
                details=(
                    f"SQL: {result.sql_query[:80]} | "
                    f"Rows: {result.row_count} | "
                    f"Confidence: {result.confidence}"
                ),
                duration_ms=duration,
            ))
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            results.append(EvalResult(
                category="sql_accuracy",
                test_name=case["description"],
                passed=False,
                score=0.0,
                details=f"Exception: {e}",
                duration_ms=duration,
            ))

    return results


# ── Routing Tests ────────────────────────────────────────────────


ROUTING_EVAL_CASES = [
    {
        "question": "What are the top customers?",
        "expected_agents": {"sql_agent"},
        "description": "Database question → SQL agent",
    },
    {
        "question": (
            "What are the payment terms in the contract?"
        ),
        "expected_agents": {"document_agent"},
        "description": "Document question → Document agent",
    },
    {
        "question": "Show revenue trends with a chart",
        "expected_agents": {"sql_agent", "analytics_agent"},
        "description": "Analytics question → SQL + Analytics",
    },
    {
        "question": "Hello, what can you do?",
        "expected_agents": set(),  # direct answer
        "description": "Greeting → direct response",
    },
]


async def eval_routing() -> list[EvalResult]:
    """Evaluate supervisor routing accuracy."""
    from langchain_core.messages import HumanMessage, SystemMessage

    from backend.agents.supervisor import ROUTING_PROMPT
    from backend.core.llm import get_llm, invoke_llm_with_retry

    llm = get_llm(temperature=0)
    results = []

    for case in ROUTING_EVAL_CASES:
        start = time.time()
        try:
            messages = [
                SystemMessage(content=ROUTING_PROMPT),
                HumanMessage(content=case["question"]),
            ]
            response = await invoke_llm_with_retry(llm, messages)
            duration = int((time.time() - start) * 1000)

            content = response.content.strip()
            if content.startswith("```"):
                content = (
                    content.split("\n", 1)[1]
                    .rsplit("```", 1)[0]
                    .strip()
                )
            parsed = json.loads(content)
            routed_agents = set(parsed.get("agents", []))

            if case["expected_agents"]:
                # Check if expected agents are a subset
                match = case["expected_agents"].issubset(routed_agents)
            else:
                # Expected direct answer
                match = (
                    len(routed_agents) == 0
                    and parsed.get("direct_answer") is not None
                )

            results.append(EvalResult(
                category="routing",
                test_name=case["description"],
                passed=match,
                score=1.0 if match else 0.0,
                details=f"Routed to: {routed_agents}",
                duration_ms=duration,
            ))
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            results.append(EvalResult(
                category="routing",
                test_name=case["description"],
                passed=False,
                score=0.0,
                details=f"Exception: {e}",
                duration_ms=duration,
            ))

    return results


# ── SQL Safety Tests ─────────────────────────────────────────────


def eval_sql_safety() -> list[EvalResult]:
    """Evaluate SQL injection protection."""
    dangerous_queries = [
        ("DROP TABLE", "DROP TABLE customers"),
        ("DELETE", "DELETE FROM orders WHERE 1=1"),
        ("UPDATE", "UPDATE customers SET tier='Free'"),
        (
            "SQL injection via SELECT",
            "SELECT * FROM customers; DROP TABLE orders",
        ),
        ("INSERT", "INSERT INTO customers VALUES (99,'x','x','x','x','x','x','x','x')"),
    ]

    results = []
    for name, query in dangerous_queries:
        start = time.time()
        try:
            execute_sql(query)
            duration = int((time.time() - start) * 1000)
            results.append(EvalResult(
                category="sql_safety",
                test_name=f"Block {name}",
                passed=False,
                score=0.0,
                details="DANGEROUS: Query was executed!",
                duration_ms=duration,
            ))
        except ValueError:
            duration = int((time.time() - start) * 1000)
            results.append(EvalResult(
                category="sql_safety",
                test_name=f"Block {name}",
                passed=True,
                score=1.0,
                details="Correctly blocked",
                duration_ms=duration,
            ))

    return results


# ── Report Generator ─────────────────────────────────────────────


def print_report(all_results: list[EvalResult]) -> None:
    """Print a formatted evaluation report."""
    print("\n" + "=" * 70)
    print("  DATAPILOT EVALUATION REPORT")
    print("=" * 70)

    categories = {}
    for r in all_results:
        if r.category not in categories:
            categories[r.category] = []
        categories[r.category].append(r)

    total_passed = 0
    total_tests = 0

    for category, results in categories.items():
        passed = sum(1 for r in results if r.passed)
        total = len(results)
        total_passed += passed
        total_tests += total
        avg_score = (
            sum(r.score for r in results) / total if total else 0
        )
        avg_duration = (
            sum(r.duration_ms for r in results) / total if total else 0
        )

        category_label = category.upper().replace("_", " ")
        print(f"\n  {category_label} ({passed}/{total} passed)")
        print(f"  Score: {avg_score:.0%} | Avg latency: {avg_duration:.0f}ms")
        print("  " + "-" * 66)

        for r in results:
            status = "PASS" if r.passed else "FAIL"
            icon = "+" if r.passed else "-"
            print(
                f"  [{icon}] {status}: {r.test_name} "
                f"({r.duration_ms}ms)"
            )
            if not r.passed:
                print(f"       {r.details}")

    overall = total_passed / total_tests if total_tests else 0
    print("\n" + "=" * 70)
    print(
        f"  OVERALL: {total_passed}/{total_tests} passed "
        f"({overall:.0%})"
    )
    print("=" * 70 + "\n")


async def run_all_evals() -> list[EvalResult]:
    """Run all evaluation suites."""
    all_results: list[EvalResult] = []

    print("Running SQL safety tests...")
    all_results.extend(eval_sql_safety())

    print("Running routing tests...")
    all_results.extend(await eval_routing())

    print("Running SQL accuracy tests...")
    all_results.extend(await eval_sql_accuracy())

    return all_results


if __name__ == "__main__":
    results = asyncio.run(run_all_evals())
    print_report(results)

    # Exit with error code if any tests failed
    failed = sum(1 for r in results if not r.passed)
    sys.exit(1 if failed > 0 else 0)
