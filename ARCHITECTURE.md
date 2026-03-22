# DataPilot Architecture

A deep-dive into how DataPilot works internally. This document is written for developers who want to understand, extend, or contribute to the codebase.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Directory Structure](#directory-structure)
3. [Request Lifecycle](#request-lifecycle)
4. [Backend Architecture](#backend-architecture)
5. [Agent System](#agent-system)
6. [LangGraph Orchestration](#langgraph-orchestration)
7. [Database Layer](#database-layer)
8. [Document Processing Pipeline](#document-processing-pipeline)
9. [LLM Provider Abstraction](#llm-provider-abstraction)
10. [API Layer](#api-layer)
11. [Frontend Architecture](#frontend-architecture)
12. [MCP Servers](#mcp-servers)
13. [Configuration & Environment](#configuration--environment)
14. [Testing & Evaluation](#testing--evaluation)
15. [Deployment](#deployment)
16. [Key Design Decisions](#key-design-decisions)

---

## System Overview

DataPilot is a multi-agent Business Intelligence system. A user asks a natural language question; a supervisor agent routes it to one or more specialist agents (SQL, Document, Analytics), aggregates results, and returns a structured answer with confidence scores, source citations, and optional charts.

```
┌─────────────────────────────────────────────────────┐
│                   Next.js Frontend                  │
│         Chat UI · Agent Trace · Chart Display       │
└──────────────────────┬──────────────────────────────┘
                       │  REST / SSE / WebSocket
┌──────────────────────▼──────────────────────────────┐
│                   FastAPI Backend                    │
│  Rate Limiter · Session Memory · CORS · Lifespan    │
├─────────────────────────────────────────────────────┤
│              Supervisor (LangGraph)                  │
│         route → execute agents → synthesize         │
├────────────┬──────────────┬─────────────────────────┤
│ SQL Agent  │ Document Agent│ Analytics Agent         │
│ Text→SQL   │ PDF/ChromaDB  │ pandas/matplotlib      │
├────────────┴──────────────┴─────────────────────────┤
│  SQLite (SQLAlchemy)  │  ChromaDB (vector store)    │
└───────────────────────┴─────────────────────────────┘
```

---

## Directory Structure

```
datapilot/
├── backend/
│   ├── main.py                    # FastAPI app, lifespan, CORS
│   ├── agents/
│   │   ├── supervisor.py          # LangGraph state machine
│   │   ├── sql_agent.py           # Text-to-SQL agent
│   │   ├── document_agent.py      # Document RAG agent
│   │   └── analytics_agent.py     # Analysis + chart agent
│   ├── api/
│   │   ├── routes.py              # REST endpoints
│   │   ├── streaming.py           # SSE endpoint
│   │   └── websocket.py           # WebSocket endpoint
│   ├── core/
│   │   ├── config.py              # pydantic-settings config
│   │   ├── llm.py                 # LLM provider factory + retry
│   │   ├── models.py              # Shared Pydantic models
│   │   ├── memory.py              # Conversation memory
│   │   └── rate_limiter.py        # Token-bucket rate limiter
│   ├── db/
│   │   └── database.py            # SQLAlchemy engine, schema, execute
│   └── mcp_servers/
│       ├── sql_mcp.py             # MCP server for SQL agent
│       ├── document_mcp.py        # MCP server for Document agent
│       └── analytics_mcp.py       # MCP server for Analytics agent
├── frontend/
│   └── src/
│       ├── app/page.tsx           # Main chat page
│       └── components/
│           ├── ChatMessage.tsx    # Message + chart rendering
│           ├── AgentTrace.tsx     # Execution trace panel
│           └── Header.tsx         # Top bar
├── tests/
│   ├── unit/
│   │   ├── test_database.py
│   │   └── test_models.py
│   └── eval/
│       └── eval_suite.py          # SQL accuracy, routing, safety evals
├── scripts/
│   └── seed_database.py           # Generate demo business data
├── data/
│   ├── sample_db/business.db      # SQLite database (auto-seeded)
│   ├── sample_docs/               # Sample PDFs/contracts for demo
│   └── chroma_db/                 # ChromaDB persistence
├── pyproject.toml                 # Dependencies, ruff, pytest config
├── render.yaml                    # Render.com deployment
├── docker-compose.yml             # Local Docker setup
├── Dockerfile                     # Backend container
├── mcp_config.json                # Claude Desktop MCP config
└── .github/workflows/ci.yml      # CI pipeline
```

---

## Request Lifecycle

Here's what happens when a user sends "What are the top 5 customers by revenue?":

```
1. Frontend POSTs to /api/query
   → { "query": "What are the top 5 customers by revenue?", "session_id": "abc" }

2. Rate limiter checks IP (guest mode)

3. SupervisorAgent.process() is called
   ├── Conversation memory enriches query with prior context
   ├── LangGraph state machine starts
   │
   ├── [route] node: LLM reads ROUTING_PROMPT, returns JSON
   │   → { "agents": ["sql_agent"], "needs_analytics": false }
   │
   ├── [sql_agent] node: SQLAgent.process()
   │   ├── Reads database schema (cached)
   │   ├── LLM generates SQL: SELECT c.name, SUM(o.total) ...
   │   ├── execute_sql() runs query against SQLite
   │   ├── LLM explains results in natural language
   │   └── Returns SQLQueryResult with confidence 0.92
   │
   ├── [synthesize] node: LLM combines all agent outputs
   │   └── Returns final answer with bullet points
   │
   └── QueryResponse assembled with answer, sources, trace, timing

4. Response returned as JSON (or streamed via SSE)
```

---

## Backend Architecture

### Entry Point (`backend/main.py`)

The FastAPI app is created with a lifespan context manager that:
- Auto-ingests sample documents from `data/sample_docs/` on startup
- Logs configuration and guest mode status

Three routers are mounted:
- `router` → REST API at `/api/*`
- `sse_router` → SSE streaming at `/api/query/stream`
- `ws_router` → WebSocket at `/ws/query`

CORS is configured for localhost dev servers and Vercel deployments.

### Singleton Pattern

The `SupervisorAgent` is instantiated lazily as a module-level singleton via `get_supervisor()`. This ensures all agents, LLM connections, and ChromaDB collections are initialized once and shared across requests.

---

## Agent System

All agents follow the same contract:

```python
class Agent:
    async def process(self, question: str, **kwargs) -> tuple[Result, list[AgentStep]]
    def get_sources(self, result) -> list[SourceReference]
```

Each agent returns:
- A typed result object (e.g., `SQLQueryResult`)
- A list of `AgentStep` objects for the execution trace

### SQL Agent (`backend/agents/sql_agent.py`)

Converts natural language to SQL and executes it.

**Flow:**
1. Loads database schema via `get_schema_info()` (column names, types, foreign keys)
2. Fetches sample data from each table for LLM context
3. LLM generates SQL query (constrained to SELECT/WITH only)
4. `execute_sql()` runs the query with safety checks
5. LLM generates natural language explanation of results
6. Returns `SQLQueryResult` with sql_query, results, explanation, confidence

**Safety:** The `execute_sql()` function blocks all non-SELECT statements (DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE) and rejects multi-statement queries (semicolons within the body).

### Document Agent (`backend/agents/document_agent.py`)

Processes uploaded documents and answers questions about their content.

**Ingestion flow:**
1. `ingest_file()` reads PDF (via pdfplumber), TXT, MD, or CSV
2. Text is split into chunks (512 chars, 50 char overlap)
3. Chunks are stored in ChromaDB with metadata (filename, page, chunk index)

**Query flow:**
1. ChromaDB semantic search finds top-k relevant chunks
2. LLM synthesizes answer from retrieved chunks
3. Returns `DocumentResult` with summary, relevant_chunks, confidence

### Analytics Agent (`backend/agents/analytics_agent.py`)

Performs calculations and generates charts from structured data.

**Flow:**
1. Receives data from SQL agent output and/or document agent output
2. LLM decides chart type (bar, line, pie, scatter) and analysis approach
3. matplotlib generates the chart server-side
4. Chart is returned as base64-encoded PNG
5. Returns `AnalyticsResult` with analysis text, key_metrics, chart_base64, chart_type

---

## LangGraph Orchestration

The Supervisor uses LangGraph's `StateGraph` to build a compile-time state machine:

```
               ┌──────────┐
               │  route   │
               └────┬─────┘
        ┌───────────┼───────────┬──────────┐
        ▼           ▼           ▼          ▼
   sql_agent  document_agent  analytics  END (direct)
        │           │          agent
        ▼           ▼           │
   _after_sql  _after_document  │
        │           │           │
        └───────┬───┘───────────┘
                ▼
           synthesize
                │
               END
```

### State Schema (`SupervisorState`)

```python
class SupervisorState(TypedDict):
    messages: Annotated[list, add_messages]  # LangGraph message accumulator
    query: str                                # Original user question
    routing_decision: dict                    # Which agents to invoke
    sql_result: dict | None                   # SQL agent output
    document_result: dict | None              # Document agent output
    analytics_result: dict | None             # Analytics agent output
    steps: list[dict]                         # Execution trace
    final_answer: str                         # Synthesized response
    confidence: float                         # Aggregated confidence
    sources: list[dict]                       # Source citations
    status: str                               # pending → processing → completed
```

### Routing Logic

The routing node sends the user query + a system prompt to the LLM. The LLM returns JSON specifying which agents to invoke:

```json
{
    "agents": ["sql_agent", "analytics_agent"],
    "reasoning": "Needs revenue data from DB, then trend analysis",
    "needs_analytics": true,
    "direct_answer": null
}
```

Conditional edges after each agent decide whether to proceed to the next agent or jump to synthesis.

### Multi-Agent Chaining

Agents execute sequentially when dependent. For example, "Show revenue trends with a chart":
1. `sql_agent` fetches revenue data from the database
2. `analytics_agent` receives SQL results and generates a chart
3. `synthesize` combines everything into the final answer

---

## Database Layer

### Engine (`backend/db/database.py`)

Uses SQLAlchemy with SQLite. The engine is a module-level singleton created on first access.

Key functions:
- `get_engine()` — Returns the SQLAlchemy engine (creates if needed)
- `get_schema_info()` — Inspects the database and returns CREATE TABLE DDL strings. This is what the SQL agent sends to the LLM for context.
- `get_sample_data(table, limit)` — Fetches N rows from a table to help the LLM understand data patterns
- `execute_sql(query)` — Executes a SQL query with safety validation. Returns `(rows, columns)` where rows are dicts.

### Schema (7 tables)

Seeded by `scripts/seed_database.py`:

| Table | Records | Purpose |
|-------|---------|---------|
| departments | 6 | Organization structure |
| employees | ~46 | Staff with department FK |
| customers | 30 | Business customers with tier (Free/Starter/Professional/Enterprise) |
| products | 12 | Products with category and pricing |
| orders | ~2079 | 2-year order history |
| order_items | ~5125 | Line items per order |
| invoices | ~1578 | Invoice records with payment status |

### SQL Safety

`execute_sql()` enforces read-only access:
1. Strips and normalizes the query
2. Checks it starts with SELECT or WITH (case-insensitive)
3. Blocks dangerous keywords: DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, EXEC, GRANT
4. Rejects queries containing semicolons (prevents injection via chained statements)

---

## Document Processing Pipeline

### Ingestion

```
PDF/TXT/MD/CSV → Extract text → Chunk (512 chars) → ChromaDB
                    │
                    ├─ PDF: pdfplumber extracts text per page
                    ├─ TXT/MD: Read as plain text
                    └─ CSV: Read as text rows
```

Each chunk is stored with metadata:
```python
{
    "source": "vendor_contract.pdf",
    "page": 3,
    "chunk_index": 7,
    "total_chunks": 24
}
```

### Retrieval

ChromaDB handles embedding generation internally (default model). On query:
1. Query text is embedded
2. Top-k most similar chunks are retrieved (cosine similarity)
3. Chunks + query are sent to LLM for answer synthesis

### Auto-Ingestion

On startup (when `auto_ingest_docs=True`), the lifespan handler scans `data/sample_docs/` and ingests all supported files. This ensures the demo always has documents available.

---

## LLM Provider Abstraction

### Provider Factory (`backend/core/llm.py`)

`get_llm()` returns a LangChain chat model based on the configured provider:

| Provider | Model | Package |
|----------|-------|---------|
| `groq` (primary) | Llama 3.3 70B | `langchain-groq` |
| `google` (fallback) | Gemini 2.0 Flash | `langchain-google-genai` |
| `openai` (local) | Any OpenAI-compatible | `langchain-openai` |

### Fallback Chain

If the primary provider fails (rate limit, network error), the factory tries the next available provider automatically.

### Retry Logic

`invoke_llm_with_retry()` wraps LLM calls with `tenacity`:
- Exponential backoff: 1s → 2s → 4s
- Max 3 retries
- Retries on any exception (rate limits, timeouts, transient errors)

---

## API Layer

### REST Endpoints (`/api/*`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/query` | Process a query synchronously |
| POST | `/api/query/stream` | Process with SSE streaming |
| POST | `/api/upload` | Upload a document (PDF/TXT/MD/CSV) |
| GET | `/api/documents` | List uploaded documents |
| GET | `/api/export/csv` | Run query and download results as CSV |
| GET | `/api/schema` | Get database schema info |
| GET | `/api/health` | Health check |

### SSE Streaming (`/api/query/stream`)

Returns a `text/event-stream` response with these event types:

```
event: status
data: {"agent": "supervisor", "action": "routing", "message": "Analyzing..."}

event: step
data: {"agent": "sql_agent", "action": "generate_sql", "confidence": 0.92, ...}

event: result
data: {"answer": "...", "confidence": 0.9, "sources": [...], "chart_base64": "..."}
```

### WebSocket (`/ws/query`)

Similar to SSE but bidirectional. Client sends `{"query": "..."}`, receives step-by-step updates and final result.

### Rate Limiting

Token-bucket algorithm keyed by client IP. Default: 10 requests per 60 seconds. Only active when `guest_mode=True`. Returns HTTP 429 when exceeded.

### Conversation Memory

In-memory store keyed by `session_id`. Keeps last 10 turns per session, auto-expires after 1 hour. The supervisor prepends conversation context to queries for multi-turn understanding.

---

## Frontend Architecture

### Stack

- **Framework:** Next.js 14 (App Router)
- **Styling:** Tailwind CSS
- **Icons:** Lucide React
- **Markdown:** react-markdown for rendering agent responses

### Components

**`page.tsx`** — Main chat interface:
- Manages messages, loading state, document uploads
- Sends queries to `/api/query`
- Displays example queries on empty state
- Upload panel with file type validation

**`ChatMessage.tsx`** — Individual message display:
- User messages (right-aligned, blue)
- Assistant messages (left-aligned, with confidence badge)
- Inline chart rendering from base64 data
- Markdown support for formatted responses

**`AgentTrace.tsx`** — Execution trace panel:
- Color-coded by agent type (SQL=blue, Document=green, Analytics=purple, Supervisor=gray)
- Shows each step with action, timing, confidence bar
- Expandable input/output details

**`Header.tsx`** — Top navigation:
- Logo and title
- Uploaded documents count badge
- Toggle button for document panel

### Data Flow

```
User types query
  → page.tsx calls fetch("/api/query", { body: { query, session_id } })
  → Response parsed as QueryResponse
  → Message added to state with answer, sources, trace, chart
  → ChatMessage renders answer + optional chart
  → AgentTrace renders execution steps
```

---

## MCP Servers

Three standalone FastMCP servers expose agent capabilities to Claude Desktop and Cursor:

| Server | Port | Tools |
|--------|------|-------|
| `sql_mcp.py` | 8010 | `query_database`, `get_database_schema`, `run_sql` |
| `document_mcp.py` | 8011 | `search_documents`, `ingest_document`, `extract_document_data` |
| `analytics_mcp.py` | 8012 | `analyze_data`, `compare_datasets` |

### Configuration (`mcp_config.json`)

Add to Claude Desktop's MCP config to use DataPilot tools directly from Claude:

```json
{
  "mcpServers": {
    "datapilot-sql": {
      "command": "python",
      "args": ["-m", "backend.mcp_servers.sql_mcp"],
      "env": { "GROQ_API_KEY": "..." }
    }
  }
}
```

---

## Configuration & Environment

### Settings (`backend/core/config.py`)

Uses `pydantic-settings` with `env_prefix=""` so environment variable names match exactly (e.g., `GROQ_API_KEY` in `.env` maps to `groq_api_key` in Settings).

### Required Environment Variables

```bash
GROQ_API_KEY=gsk_...          # Primary LLM (free tier)
GOOGLE_API_KEY=AI...          # Fallback LLM (free tier)
```

### Optional Environment Variables

```bash
PRIMARY_MODEL=groq             # groq | google | openai
ENV=development                # development | production
GUEST_MODE=true                # Enable rate limiting
AUTO_INGEST_DOCS=true          # Ingest sample docs on startup
DATABASE_URL=sqlite+aiosqlite:///./data/sample_db/business.db
LOG_LEVEL=INFO
```

---

## Testing & Evaluation

### Unit Tests (`tests/unit/`)

Run with: `pytest tests/unit/`

- **test_database.py** — Schema loading, SELECT execution, CTE support, SQL injection blocking
- **test_models.py** — Pydantic model validation, serialization, enum handling

### Evaluation Suite (`tests/eval/eval_suite.py`)

Run with: `python -m tests.eval.eval_suite`

A scored evaluation pipeline that tests the system end-to-end:

**SQL Accuracy (5 cases):**
- Simple COUNT queries
- Aggregation with GROUP BY
- Top-N with ORDER BY
- Filtered counts (WHERE clause)
- AVG with JOIN

**Routing Correctness (4 cases):**
- Database questions → SQL agent
- Document questions → Document agent
- Analytics questions → SQL + Analytics agents
- Greetings → Direct response

**SQL Safety (5 cases):**
- DROP TABLE blocked
- DELETE blocked
- UPDATE blocked
- SQL injection via chained statements blocked
- INSERT blocked

Output is a scored report with pass/fail per test, latency, and overall percentage.

### CI Pipeline (`.github/workflows/ci.yml`)

On every push/PR:
1. Lint with `ruff` (import sorting, unused imports, line length, modern Python patterns)
2. Run `pytest` with coverage

---

## Deployment

### Local Development

```bash
# Backend
pip install -e ".[dev]"
python scripts/seed_database.py
uvicorn backend.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

### Docker

```bash
docker-compose up --build
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
```

### Production (Render + Vercel)

**Backend → Render.com** (`render.yaml`):
- Free tier web service
- Python 3.11, auto-seeds database on build
- Set `GROQ_API_KEY` and `GOOGLE_API_KEY` as environment variables in Render dashboard
- Health check at `/api/health`

**Frontend → Vercel** (`frontend/vercel.json`):
- Next.js auto-detected
- API requests proxied to Render backend via rewrites
- Zero config deployment from GitHub

**Steps:**
1. Push to GitHub
2. Connect repo to Render → backend auto-deploys
3. Connect `frontend/` directory to Vercel → frontend auto-deploys
4. Set `NEXT_PUBLIC_API_URL` in Vercel to your Render URL

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Orchestration | LangGraph StateGraph | Compile-time state machine with typed state, conditional edges, and built-in checkpointing support |
| LLM access | Groq free tier (Llama 3.3 70B) | Zero-cost, fast inference, 70B parameter model quality |
| Vector store | ChromaDB | Embedded (no server), persistent, handles embeddings internally |
| SQL database | SQLite | Zero-config, single-file, swap to PostgreSQL by changing `DATABASE_URL` |
| API framework | FastAPI | Async, auto-docs, Pydantic integration, WebSocket + SSE support |
| Frontend | Next.js 14 | App Router, React Server Components, easy Vercel deployment |
| MCP | FastMCP | First-class Claude Desktop/Cursor integration |
| Configuration | pydantic-settings | Type-safe config with .env file loading |
| Rate limiting | In-memory token bucket | Simple, no Redis dependency, sufficient for demo/guest mode |
| Charts | matplotlib (server-side) | No client-side charting library needed, base64 PNG works everywhere |

See `DECISIONS.md` for the full decision log with context and trade-offs.
