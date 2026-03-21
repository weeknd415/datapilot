"""Analytics Agent: Performs calculations, generates visualizations, identifies trends.

This agent:
- Takes outputs from SQL and Document agents
- Performs statistical analysis and calculations
- Generates charts using matplotlib/plotly
- Identifies business trends and anomalies
"""

from __future__ import annotations

import base64
import io
import json
import logging
import time
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.llm import get_llm, invoke_llm_with_retry
from backend.core.models import AgentStep, AgentType, AnalyticsResult, SourceReference

matplotlib.use("Agg")  # Non-interactive backend

logger = logging.getLogger(__name__)

ANALYTICS_PROMPT = """You are a business analytics expert. Analyze the provided data and answer the question.

DATA:
{data}

INSTRUCTIONS:
1. Perform any necessary calculations.
2. Identify trends, patterns, or anomalies.
3. Provide actionable business insights.
4. If a chart would be helpful, specify the chart type and data.

RESPONSE FORMAT (JSON, no code fences):
{{
    "analysis": "Your detailed analysis in plain language",
    "key_metrics": {{"metric_name": "value"}},
    "trends": ["trend1", "trend2"],
    "recommendations": ["recommendation1"],
    "chart": {{
        "type": "bar|line|pie|scatter|none",
        "title": "Chart title",
        "x_label": "X axis label",
        "y_label": "Y axis label",
        "data": {{"labels": ["a","b"], "values": [1,2]}}
    }}
}}"""


class AnalyticsAgent:
    """Agent that performs analytics on data from other agents."""

    def __init__(self, provider: str | None = None) -> None:
        self.llm = get_llm(provider=provider, temperature=0)

    def _generate_chart(self, chart_spec: dict[str, Any]) -> str | None:
        """Generate a chart from specification and return as base64 PNG."""
        chart_type = chart_spec.get("type", "none")
        if chart_type == "none":
            return None

        try:
            fig, ax = plt.subplots(figsize=(10, 6))
            data = chart_spec.get("data", {})
            labels = data.get("labels", [])
            values = data.get("values", [])

            if not labels or not values:
                return None

            if chart_type == "bar":
                ax.bar(labels, values, color="#4F46E5")
            elif chart_type == "line":
                ax.plot(labels, values, marker="o", color="#4F46E5", linewidth=2)
            elif chart_type == "pie":
                ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
            elif chart_type == "scatter":
                ax.scatter(labels, values, color="#4F46E5", s=100)

            ax.set_title(chart_spec.get("title", ""), fontsize=14, fontweight="bold")
            if chart_type != "pie":
                ax.set_xlabel(chart_spec.get("x_label", ""), fontsize=12)
                ax.set_ylabel(chart_spec.get("y_label", ""), fontsize=12)
                ax.tick_params(axis="x", rotation=45)
            plt.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)
            return base64.b64encode(buf.read()).decode("utf-8")

        except Exception as e:
            logger.warning("Chart generation failed: %s", e)
            plt.close("all")
            return None

    async def process(
        self,
        question: str,
        sql_data: list[dict[str, Any]] | None = None,
        document_data: str | None = None,
    ) -> tuple[AnalyticsResult, list[AgentStep]]:
        """Analyze data from SQL and/or Document agents."""
        steps: list[AgentStep] = []

        # Prepare data context
        data_parts = []
        if sql_data:
            df = pd.DataFrame(sql_data)
            data_parts.append(f"SQL QUERY RESULTS:\n{df.to_string(index=False)}")
            # Add basic statistics
            numeric_cols = df.select_dtypes(include="number").columns
            if len(numeric_cols) > 0:
                data_parts.append(f"\nBASIC STATISTICS:\n{df[numeric_cols].describe().to_string()}")
        if document_data:
            data_parts.append(f"DOCUMENT DATA:\n{document_data}")

        if not data_parts:
            return AnalyticsResult(
                analysis="No data provided for analysis.",
                confidence=0.0,
                error="No input data",
            ), steps

        combined_data = "\n\n".join(data_parts)

        # Step 1: Analyze data
        analysis_start = time.time()
        messages = [
            SystemMessage(content=ANALYTICS_PROMPT.format(data=combined_data)),
            HumanMessage(content=question),
        ]
        response = await invoke_llm_with_retry(self.llm, messages)
        analysis_duration = int((time.time() - analysis_start) * 1000)

        # Parse response
        try:
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            parsed = json.loads(content)
        except (json.JSONDecodeError, IndexError):
            parsed = {"analysis": response.content, "chart": {"type": "none"}}

        steps.append(AgentStep(
            agent=AgentType.ANALYTICS,
            action="analyze_data",
            input_summary=f"Analyzing {len(sql_data or [])} rows + document data",
            output_summary=parsed.get("analysis", "")[:100],
            confidence=0.85,
            duration_ms=analysis_duration,
        ))

        # Step 2: Generate chart if specified
        chart_base64 = None
        chart_type = None
        chart_spec = parsed.get("chart", {})
        if chart_spec and chart_spec.get("type", "none") != "none":
            chart_start = time.time()
            chart_base64 = self._generate_chart(chart_spec)
            chart_type = chart_spec.get("type")
            chart_duration = int((time.time() - chart_start) * 1000)

            steps.append(AgentStep(
                agent=AgentType.ANALYTICS,
                action="generate_chart",
                input_summary=f"Chart type: {chart_type}",
                output_summary="Chart generated" if chart_base64 else "Chart generation failed",
                confidence=0.9 if chart_base64 else 0.0,
                duration_ms=chart_duration,
            ))

        return AnalyticsResult(
            analysis=parsed.get("analysis", response.content),
            data={
                "key_metrics": parsed.get("key_metrics", {}),
                "trends": parsed.get("trends", []),
                "recommendations": parsed.get("recommendations", []),
            },
            chart_base64=chart_base64,
            chart_type=chart_type,
            confidence=0.85,
        ), steps

    def get_sources(self, result: AnalyticsResult) -> list[SourceReference]:
        """Extract source references from analytics result."""
        sources = []
        if result.data.get("key_metrics"):
            sources.append(SourceReference(
                source_type="calculation",
                source_name="Analytics Engine",
                details=f"Metrics: {list(result.data['key_metrics'].keys())}",
            ))
        return sources
