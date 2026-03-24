"""Supervisor Agent: Orchestrates specialist agents using LangGraph.

This agent:
- Routes queries to the appropriate specialist agent(s)
- Handles multi-step reasoning across agents
- Manages fallback when confidence is low
- Aggregates results into a unified response
"""

from __future__ import annotations

import json
import logging
import time
from typing import Annotated, Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from backend.agents.analytics_agent import AnalyticsAgent
from backend.agents.document_agent import DocumentAgent
from backend.agents.sql_agent import SQLAgent
from backend.core.llm import get_llm, invoke_llm_with_retry
from backend.core.models import (
    AgentStep,
    AgentType,
    QueryResponse,
    QueryStatus,
    SourceReference,
)

logger = logging.getLogger(__name__)

ROUTING_PROMPT = """\
You are the DataPilot supervisor. Route the user's question to the right specialist agent(s).

AVAILABLE AGENTS:
1. sql_agent - Queries the SaaS metrics database (accounts, subscriptions, MRR, churn, tickets)
2. document_agent - Searches uploaded documents (SOC2 reports, contracts, board decks)
3. analytics_agent - Performs calculations, generates charts, identifies trends
4. direct - Answer directly if the question is general/conversational

ROUTING RULES:
- If the question involves database data (MRR, accounts, churn, tickets): route to sql_agent
- If the question involves uploaded documents or files: route to document_agent
- If the question needs both database AND documents: route to sql_agent AND document_agent
- If the question asks for analysis, trends, or charts: include analytics_agent AFTER getting data
- If the question is conversational ("hello", "what can you do"): route to direct

RESPONSE FORMAT (JSON, no code fences):
{{
    "agents": ["sql_agent", "document_agent", "analytics_agent"],
    "reasoning": "Why these agents were chosen",
    "needs_analytics": true,
    "direct_answer": null
}}

If routing to direct, set "agents": [] and provide "direct_answer": "your answer"."""


class SupervisorState(TypedDict):
    """State that flows through the LangGraph supervisor."""

    messages: Annotated[list, add_messages]
    query: str
    routing_decision: dict[str, Any]
    sql_result: dict[str, Any] | None
    document_result: dict[str, Any] | None
    analytics_result: dict[str, Any] | None
    steps: list[dict[str, Any]]
    final_answer: str
    confidence: float
    sources: list[dict[str, Any]]
    status: str


class SupervisorAgent:
    """LangGraph-based supervisor that orchestrates specialist agents."""

    def __init__(self, provider: str | None = None) -> None:
        self.llm = get_llm(provider=provider, temperature=0)
        self.sql_agent = SQLAgent(provider=provider)
        self.document_agent = DocumentAgent(provider=provider)
        self.analytics_agent = AnalyticsAgent(provider=provider)
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine for agent orchestration."""
        graph = StateGraph(SupervisorState)

        # Add nodes
        graph.add_node("route", self._route_query)
        graph.add_node("sql_agent", self._run_sql_agent)
        graph.add_node("document_agent", self._run_document_agent)
        graph.add_node("analytics_agent", self._run_analytics_agent)
        graph.add_node("synthesize", self._synthesize_response)

        # Set entry point
        graph.set_entry_point("route")

        # Add conditional edges from router
        graph.add_conditional_edges(
            "route",
            self._decide_next_agent,
            {
                "sql_agent": "sql_agent",
                "document_agent": "document_agent",
                "analytics_agent": "analytics_agent",
                "synthesize": "synthesize",
                END: END,
            },
        )

        # After SQL agent
        graph.add_conditional_edges(
            "sql_agent",
            self._after_sql,
            {
                "document_agent": "document_agent",
                "analytics_agent": "analytics_agent",
                "synthesize": "synthesize",
            },
        )

        # After Document agent
        graph.add_conditional_edges(
            "document_agent",
            self._after_document,
            {
                "analytics_agent": "analytics_agent",
                "synthesize": "synthesize",
            },
        )

        # After Analytics agent → always synthesize
        graph.add_edge("analytics_agent", "synthesize")

        # Synthesize → END
        graph.add_edge("synthesize", END)

        return graph.compile()

    async def _route_query(self, state: SupervisorState) -> dict[str, Any]:
        """Route the user query to appropriate agents."""
        start = time.time()
        messages = [
            SystemMessage(content=ROUTING_PROMPT),
            HumanMessage(content=state["query"]),
        ]
        response = await invoke_llm_with_retry(self.llm, messages)
        duration = int((time.time() - start) * 1000)

        try:
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            routing = json.loads(content)
        except (json.JSONDecodeError, IndexError):
            routing = {
                "agents": ["sql_agent"],
                "reasoning": "Default routing to SQL",
                "needs_analytics": False,
            }

        step = AgentStep(
            agent=AgentType.SUPERVISOR,
            action="route_query",
            input_summary=state["query"][:100],
            output_summary=f"Routing to: {routing.get('agents', [])}",
            confidence=0.9,
            duration_ms=duration,
        )

        # Handle direct answer
        if not routing.get("agents") and routing.get("direct_answer"):
            return {
                "routing_decision": routing,
                "final_answer": routing["direct_answer"],
                "confidence": 1.0,
                "status": "completed",
                "steps": state.get("steps", []) + [step.model_dump()],
            }

        return {
            "routing_decision": routing,
            "steps": state.get("steps", []) + [step.model_dump()],
            "status": "processing",
        }

    def _decide_next_agent(self, state: SupervisorState) -> str:
        """Determine which agent to run first based on routing."""
        routing = state.get("routing_decision", {})

        if state.get("status") == "completed":
            return END

        agents = routing.get("agents", [])
        if "sql_agent" in agents:
            return "sql_agent"
        if "document_agent" in agents:
            return "document_agent"
        if "analytics_agent" in agents:
            return "analytics_agent"
        return "synthesize"

    async def _run_sql_agent(self, state: SupervisorState) -> dict[str, Any]:
        """Execute the SQL agent."""
        result, steps = await self.sql_agent.process(state["query"])
        sources = self.sql_agent.get_sources(result)

        return {
            "sql_result": result.model_dump(),
            "steps": state.get("steps", []) + [s.model_dump() for s in steps],
            "sources": state.get("sources", []) + [s.model_dump() for s in sources],
        }

    def _after_sql(self, state: SupervisorState) -> str:
        """Decide what to do after SQL agent completes."""
        routing = state.get("routing_decision", {})
        agents = routing.get("agents", [])

        if "document_agent" in agents:
            return "document_agent"
        if routing.get("needs_analytics") or "analytics_agent" in agents:
            return "analytics_agent"
        return "synthesize"

    async def _run_document_agent(self, state: SupervisorState) -> dict[str, Any]:
        """Execute the Document agent."""
        result, steps = await self.document_agent.process(state["query"])
        sources = self.document_agent.get_sources(result)

        return {
            "document_result": result.model_dump(),
            "steps": state.get("steps", []) + [s.model_dump() for s in steps],
            "sources": state.get("sources", []) + [s.model_dump() for s in sources],
        }

    def _after_document(self, state: SupervisorState) -> str:
        """Decide what to do after Document agent completes."""
        routing = state.get("routing_decision", {})
        if routing.get("needs_analytics") or "analytics_agent" in routing.get("agents", []):
            return "analytics_agent"
        return "synthesize"

    async def _run_analytics_agent(self, state: SupervisorState) -> dict[str, Any]:
        """Execute the Analytics agent."""
        sql_data = None
        doc_data = None

        if state.get("sql_result"):
            sql_data = state["sql_result"].get("results", [])
        if state.get("document_result"):
            doc_data = state["document_result"].get("summary", "")

        result, steps = await self.analytics_agent.process(
            state["query"],
            sql_data=sql_data,
            document_data=doc_data,
        )
        sources = self.analytics_agent.get_sources(result)

        return {
            "analytics_result": result.model_dump(),
            "steps": state.get("steps", []) + [s.model_dump() for s in steps],
            "sources": state.get("sources", []) + [s.model_dump() for s in sources],
        }

    async def _synthesize_response(self, state: SupervisorState) -> dict[str, Any]:
        """Synthesize a final answer from all agent results."""
        start = time.time()
        parts = []

        if state.get("sql_result"):
            sr = state["sql_result"]
            parts.append(f"DATABASE RESULTS:\n{sr.get('explanation', '')}")
        if state.get("document_result"):
            dr = state["document_result"]
            parts.append(f"DOCUMENT FINDINGS:\n{dr.get('summary', '')}")
        if state.get("analytics_result"):
            ar = state["analytics_result"]
            parts.append(f"ANALYSIS:\n{ar.get('analysis', '')}")

        if not parts and state.get("final_answer"):
            return {"status": "completed"}

        combined = "\n\n".join(parts)

        messages = [
            SystemMessage(content=(
                "You are DataPilot, a business intelligence assistant. "
                "Synthesize the following agent results into a clear, concise answer for the user. "
                "Lead with the key finding. Use bullet points for multiple data points. "
                "Include specific numbers and cite sources."
            )),
            HumanMessage(content=f"Question: {state['query']}\n\nAgent Results:\n{combined}"),
        ]
        response = await invoke_llm_with_retry(self.llm, messages)
        duration = int((time.time() - start) * 1000)

        # Calculate overall confidence
        confidences = []
        sql_r = state.get("sql_result")
        doc_r = state.get("document_result")
        ana_r = state.get("analytics_result")
        if sql_r and sql_r.get("confidence"):
            confidences.append(sql_r["confidence"])
        if doc_r and doc_r.get("confidence"):
            confidences.append(doc_r["confidence"])
        if ana_r and ana_r.get("confidence"):
            confidences.append(ana_r["confidence"])
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

        step = AgentStep(
            agent=AgentType.SUPERVISOR,
            action="synthesize",
            input_summary=f"{len(parts)} agent results",
            output_summary=response.content[:100],
            confidence=avg_confidence,
            duration_ms=duration,
        )

        return {
            "final_answer": response.content,
            "confidence": avg_confidence,
            "status": "completed",
            "steps": state.get("steps", []) + [step.model_dump()],
        }

    async def process(
        self, query: str, session_id: str = "",
    ) -> QueryResponse:
        """Process a user query through the full agent pipeline."""
        from backend.core.memory import conversation_memory

        start = time.time()

        # Add conversation context if available
        context = conversation_memory.get_context_string(session_id)
        enriched_query = query
        if context:
            enriched_query = f"{context}\n\nCURRENT QUESTION: {query}"

        initial_state: SupervisorState = {
            "messages": [],
            "query": enriched_query,
            "routing_decision": {},
            "sql_result": None,
            "document_result": None,
            "analytics_result": None,
            "steps": [],
            "final_answer": "",
            "confidence": 0.0,
            "sources": [],
            "status": "pending",
        }

        try:
            final_state = await self.graph.ainvoke(initial_state)
            duration = int((time.time() - start) * 1000)

            # Reconstruct typed objects
            steps = [AgentStep(**s) for s in final_state.get("steps", [])]
            sources = [SourceReference(**s) for s in final_state.get("sources", [])]
            total_tokens = sum(s.token_count for s in steps)

            # Extract chart from analytics result if present
            chart_base64 = None
            chart_type = None
            analytics_r = final_state.get("analytics_result")
            if analytics_r:
                chart_base64 = analytics_r.get("chart_base64")
                chart_type = analytics_r.get("chart_type")

            answer = final_state.get(
                "final_answer", "I could not generate an answer."
            )

            # Save to conversation memory
            conversation_memory.add_turn(session_id, query, answer)

            return QueryResponse(
                query=query,
                answer=answer,
                confidence=final_state.get("confidence", 0.0),
                sources=sources,
                trace=steps,
                status=QueryStatus.COMPLETED,
                total_tokens=total_tokens,
                duration_ms=duration,
                chart_base64=chart_base64,
                chart_type=chart_type,
            )
        except Exception as e:
            logger.error("Supervisor pipeline failed: %s", e, exc_info=True)
            duration = int((time.time() - start) * 1000)
            return QueryResponse(
                query=query,
                answer="",
                status=QueryStatus.FAILED,
                error=str(e),
                duration_ms=duration,
            )
