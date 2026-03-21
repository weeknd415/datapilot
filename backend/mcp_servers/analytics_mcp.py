"""MCP Server for the Analytics Agent.

Exposes data analysis and visualization capabilities as an MCP server.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastmcp import FastMCP

from backend.agents.analytics_agent import AnalyticsAgent

mcp = FastMCP(
    "DataPilot Analytics Agent",
    description="Perform data analysis, generate charts, and identify business trends",
)

_agent: AnalyticsAgent | None = None


def _get_agent() -> AnalyticsAgent:
    global _agent
    if _agent is None:
        _agent = AnalyticsAgent()
    return _agent


@mcp.tool()
async def analyze_data(
    question: str,
    data_json: str,
) -> str:
    """Analyze data and provide business insights with optional chart generation.

    Args:
        question: What you want to analyze (e.g., "Show revenue trends by quarter")
        data_json: JSON string of the data to analyze (array of objects)

    Returns:
        JSON string with analysis, key metrics, trends, and base64 chart if applicable.
    """
    agent = _get_agent()
    try:
        data = json.loads(data_json)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON data provided"})

    result, steps = await agent.process(
        question,
        sql_data=data if isinstance(data, list) else None,
        document_data=data_json if isinstance(data, str) else None,
    )

    response = {
        "analysis": result.analysis,
        "data": result.data,
        "confidence": result.confidence,
        "chart_type": result.chart_type,
    }
    if result.chart_base64:
        response["chart_base64"] = result.chart_base64

    return json.dumps(response, indent=2, default=str)


@mcp.tool()
async def compare_datasets(
    question: str,
    dataset1_json: str,
    dataset2_json: str,
) -> str:
    """Compare two datasets and highlight differences, trends, and anomalies.

    Args:
        question: What comparison to make
        dataset1_json: First dataset as JSON string
        dataset2_json: Second dataset as JSON string

    Returns:
        JSON string with comparative analysis.
    """
    agent = _get_agent()
    combined = f"Dataset 1: {dataset1_json}\n\nDataset 2: {dataset2_json}"

    result, steps = await agent.process(question, document_data=combined)
    return json.dumps(
        {
            "analysis": result.analysis,
            "data": result.data,
            "confidence": result.confidence,
        },
        indent=2,
        default=str,
    )


if __name__ == "__main__":
    mcp.run()
