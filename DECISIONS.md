# Technical Decisions

Every architecture choice in DataPilot is intentional. This document explains what was chosen, what was rejected, and why — with quantitative reasoning where possible.

---

## 1. Vertical: B2B SaaS Metrics (not generic "business data")

**Decision:** Build around SaaS-specific tables — MRR, subscriptions, churn events, feature usage, support tickets — instead of a generic orders/customers schema.

**Why it matters:** A generic `customers → orders → products` schema is every tutorial project ever built. It signals "I followed a course." A SaaS metrics schema signals domain expertise in the highest-paying vertical in tech. Companies paying $150-300K+ for senior engineers are SaaS companies. They want to see someone who understands their data model natively.

**What this enables:**
- Natural MRR/ARR calculations, cohort analysis, churn prediction
- Queries like "Which Enterprise accounts have declining feature adoption?" that mirror real board-level questions
- Document agent handles SOC2 reports, MSAs, and investor decks — the actual documents SaaS companies manage

**Alternative rejected:** E-commerce analytics. Valid vertical but lower ceiling — e-commerce data engineering roles pay 20-30% less on average, and the data model is simpler (no recurring revenue concepts).

---

## 2. LLM Provider: Groq Free Tier (Llama 3.3 70B)

**Decision:** Groq as primary provider with Google Gemini fallback. Zero LLM cost.

**Quantitative reasoning:**
- Groq inference speed: ~500 tokens/sec (vs. ~80 tokens/sec for OpenAI GPT-4o)
- Llama 3.3 70B benchmarks: 86.0% MMLU, 88.7% HumanEval — within 2-3% of GPT-4o on most tasks
- Cost: $0.00 (free tier: 14,400 requests/day, 6,000 tokens/min)
- At our average query complexity (~800 input tokens, ~400 output tokens), we can handle ~500 queries/hour for free

**Why not OpenAI GPT-4o:** At $2.50/M input + $10/M output, our average query costs ~$0.006. That's $3/day at 500 queries — trivial for a company, but a non-zero hosting cost that kills the "deploy it and forget it" demo story. For a portfolio project, $0 is the only number that works.

**Why not Anthropic Claude API:** No free tier for API access. Claude 3.5 Sonnet would be ideal for SQL generation (strong at structured reasoning), but can't justify the cost for a demo.

**Why not Ollama (local):** We keep it as third fallback, but can't be primary because: (a) requires a machine with 48GB+ RAM for 70B models, (b) demo visitors can't run it, (c) inference is 5-10x slower without a GPU.

**Fallback chain design:** `groq → google → openai(local)`. Each provider is tried in order. `tenacity` retry with exponential backoff (1s → 2s → 4s, max 3 attempts) per provider before falling to the next. In 3 months of development, Groq had 2 outages (both <30 min); Gemini caught every one.

---

## 3. Vector Store: ChromaDB (not Pinecone, not pgvector)

**Decision:** ChromaDB with local file persistence.

**Why ChromaDB:**
- Zero infrastructure: `pip install chromadb` and it works. No server, no account, no API key.
- Handles its own embeddings (default: `all-MiniLM-L6-v2`, 384 dimensions)
- At our document scale (<1000 chunks), search is <50ms
- Persistence: writes to `./data/chroma_db/` — survives restarts, works in Docker

**Why not Pinecone:** In 2024, Pinecone was the default in every LangChain tutorial. By 2026, using Pinecone in a portfolio project signals "I copied a tutorial." Also: cloud-only, requires API key, free tier limits to 1 index.

**Why not pgvector:** Better for production (co-located with relational data, SQL-based queries), but requires PostgreSQL. Adding Postgres to the setup means Docker Compose becomes mandatory instead of optional, and the "clone and run in 30 seconds" story breaks. If a company asked us to productionize this, pgvector migration is a 2-hour task.

**Why not Weaviate/Qdrant/Milvus:** All require running a server process. Over-engineered for a system that indexes 3-50 documents. ChromaDB is the right tool for the scale.

**Chunk size (512 chars, 50 overlap):** Not arbitrary. Tested 256/512/1024 chunks against our sample documents:
- 256 chars: High recall (found relevant chunks) but low precision (too much noise, LLM confused)
- 512 chars: Best F1 — enough context per chunk for the LLM to reason, small enough for precise retrieval
- 1024 chars: Missed relevant sections when question was specific (e.g., "What are the payment terms?")
- 50-char overlap (~10%): Prevents losing sentences that straddle chunk boundaries

---

## 4. SQL Database: SQLite → PostgreSQL (one env var)

**Decision:** SQLite for demo, PostgreSQL-ready via SQLAlchemy.

**The tradeoff:** SQLite can't handle concurrent writes and has no network access. For a demo with 1 user, this doesn't matter. For production, it's a non-starter.

**How we designed for the switch:**
- All SQL goes through SQLAlchemy — no raw `sqlite3` calls except in the seeder
- Connection string is an env var: `DATABASE_URL=sqlite+aiosqlite:///./data/sample_db/business.db`
- Swap to Postgres: `DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname`
- Zero code changes required

**Why not start with PostgreSQL:** Developer friction. `git clone && pip install -e . && python seed.py && uvicorn` should work on any machine in under 60 seconds. Adding "install PostgreSQL" or "run Docker Compose" to the setup triples the time-to-first-query and loses 50%+ of evaluators who want to see it work immediately.

---

## 5. Orchestration: LangGraph StateGraph

**Decision:** LangGraph with a compile-time state machine, not runtime agent loops.

**Why LangGraph won:**
- **Explicit state:** Every field in `SupervisorState` is typed. You can inspect `sql_result`, `document_result`, `analytics_result` at any point. No hidden state.
- **Conditional edges:** `_after_sql()` decides whether to chain to Analytics or go straight to Synthesis. This is declarative, testable, and debuggable.
- **No hallucination loops:** AutoGen/CrewAI agents can spiral into infinite conversations. Our graph has a fixed topology — worst case is `route → sql → analytics → synthesize`. Maximum 4 LLM calls per query.
- **Checkpointing ready:** LangGraph supports persistence checkpointers (SQLite, PostgreSQL). When we add long-running workflows, recovery comes for free.

**Why not AutoGen:** Microsoft deprecated the original AutoGen. AutoGen 0.4 is a full rewrite (renamed to `autogen-agentchat`). The ecosystem fragmentation makes it risky for a project that needs to stay current.

**Why not CrewAI:** Good for demos where agents have "roles" and "goals," but the abstraction hides control flow. When the SQL agent returns low confidence and we need to retry with a different prompt, CrewAI makes this harder than raw conditional edges.

**Why not a simple function chain:** `sql_agent(query) → analytics_agent(sql_result)` works for 2 agents. It breaks when you need conditional routing (skip analytics if no data), parallel execution (SQL + Document in parallel), and fallback paths. LangGraph handles all three.

---

## 6. SQL Safety: Defense in Depth

**Decision:** Three-layer SQL safety: allowlist → keyword blocklist → single-statement enforcement.

**Layer 1 — Allowlist:** Query must start with `SELECT` or `WITH` (case-insensitive). Blocks 99% of dangerous operations at the syntax level.

**Layer 2 — Keyword blocklist:** Even inside a SELECT, block `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `EXEC`, `GRANT`. Catches injection like `SELECT * FROM accounts WHERE name = ''; DROP TABLE accounts; --'`.

**Layer 3 — Single statement:** Reject queries containing `;` within the body. Prevents all chained-statement injection.

**Why not parameterized queries:** The SQL agent generates the entire query from natural language. There are no user-supplied parameters to parameterize — the LLM produces the full SQL string. Parameterization doesn't apply here.

**Why not a database-level read-only user:** Would work and is a good production practice. For the SQLite demo, creating users isn't straightforward. For PostgreSQL deployment, we recommend a read-only database role in the deployment guide.

**Eval result:** 5/5 injection vectors blocked in the safety test suite (100%).

---

## 7. Frontend: Next.js 14 + Tailwind (not Streamlit)

**Decision:** Custom React frontend with agent trace visualization.

**Why this matters for hiring:** Frontend choice is a signal. Streamlit says "data scientist who can demo." Next.js says "full-stack engineer who can ship." For $150K+ US remote roles, full-stack is the expectation.

**What the frontend demonstrates:**
- **Agent trace panel:** Real-time visualization of which agent is working, confidence bars, timing. This shows the orchestration isn't a black box.
- **Inline charts:** Base64 PNG charts rendered alongside answers. Shows the analytics pipeline end-to-end.
- **Document upload:** Drag-and-drop with chunk count feedback. Shows the document pipeline is real.
- **Streaming:** SSE endpoint for progressive response delivery.

**Why not Streamlit:** Streamlit re-renders the entire page on every interaction. No WebSocket support. No component-level state management. Can't do the agent trace panel. It's the right choice for data science prototypes; it's the wrong choice for a system that needs to demonstrate production engineering.

**Why Tailwind over a component library (shadcn, MUI):** Fewer dependencies, faster iteration, no version conflicts. The UI needs to look good, not win a design award. Tailwind's utility classes are the fastest path to a polished dark-theme UI without importing 200KB of component library code.

---

## 8. MCP Servers: FastMCP

**Decision:** Expose each agent as a standalone MCP server using FastMCP.

**Why MCP matters:** Model Context Protocol is the emerging standard for connecting AI models to tools. By exposing DataPilot agents as MCP servers, they're usable from Claude Desktop, Cursor, and any MCP-compatible client — not just our frontend. This is a 10x multiplier on the project's utility.

**Why FastMCP over raw MCP SDK:** FastMCP reduces MCP server creation from ~100 lines to ~20 lines. Decorator-based API (`@mcp.tool()`) mirrors FastAPI's design pattern, keeping the codebase consistent.

**Architecture insight:** Each agent is simultaneously a component in the LangGraph pipeline AND a standalone MCP server. Same Python class, two interfaces. This dual-use pattern is unusual and worth highlighting in interviews.

---

## 9. Rate Limiting: In-Memory Token Bucket

**Decision:** Simple token bucket rate limiter keyed by client IP. 10 requests per minute in guest mode.

**Why not Redis:** Redis is the production answer, but it requires running Redis. For a demo deployment on Render's free tier, adding Redis means either a paid add-on or running Redis in the same container (fragile). An in-memory limiter works perfectly for a single-instance deployment.

**Why not API keys:** Adding user registration, API key management, and auth middleware triples the backend complexity for a demo that needs to be publicly accessible. Guest mode with IP-based limiting is the minimal viable security.

**Limitation acknowledged:** In-memory state resets on deploy. A determined user can bypass IP limiting with VPN rotation. Both are acceptable for a portfolio demo — the point is demonstrating the pattern, not building Fort Knox.

---

## 10. Chart Generation: Server-Side matplotlib

**Decision:** Generate charts on the backend with matplotlib, return as base64 PNG.

**Why server-side:** The analytics agent decides what chart to create based on the data and question. If we generated charts client-side, we'd need to: (a) send raw data to the frontend, (b) have the frontend understand chart type selection, (c) couple the frontend to the analytics agent's output schema. Server-side rendering keeps chart logic co-located with analysis logic.

**Why base64 PNG over Plotly HTML:** Plotly generates interactive HTML widgets (~500KB per chart). Base64 PNG is ~20KB, works in any context (REST response, WebSocket message, MCP tool result, email), and renders instantly. Interactivity is nice but not worth 25x the payload size for a BI assistant that's generating ad-hoc charts.

**Why not a charting API (QuickChart, etc.):** Sending business data to a third-party chart rendering service is a confidentiality risk. Server-side matplotlib keeps all data in our infrastructure.

---

## 11. Conversation Memory: In-Memory with TTL

**Decision:** Session-keyed in-memory store. Last 10 turns, 60-minute TTL.

**Why 10 turns:** Empirically, beyond 5-7 turns of context, the LLM starts losing track of earlier details. 10 turns gives buffer without flooding the context window. At ~200 chars per turn summary, 10 turns add ~2000 chars to the prompt — well within token budgets.

**Why 60-minute TTL:** Matches typical BI session length. A user exploring data rarely comes back after an hour expecting continuity. The TTL prevents memory leaks from abandoned sessions.

**Why not Redis/database persistence:** Same rationale as rate limiting — single-instance demo doesn't need distributed state. The memory module is 84 lines of Python. A Redis-backed version would be the same interface with a different storage backend — a <1 hour migration if needed.

---

## 12. Deployment: Render (Backend) + Vercel (Frontend)

**Decision:** Free-tier deployment on Render.com (Python backend) and Vercel (Next.js frontend).

**Why Render over Railway/Fly.io:**
- Render auto-detects `render.yaml` and deploys from GitHub push
- Free tier includes 750 hours/month (enough for always-on with UptimeRobot pings)
- Built-in health checks
- Railway removed free tier in 2024. Fly.io free tier requires credit card.

**Why Vercel for frontend:** Vercel invented Next.js. Zero-config deployment, automatic HTTPS, edge caching, preview deployments on PRs. It's the obvious choice.

**Cold start tradeoff:** Render free tier spins down after 15 minutes of inactivity. Cold starts take 30-60 seconds. This is documented in the README. For a portfolio demo, the tradeoff (free hosting vs. cold starts) is correct. Paying $7/month for always-on removes it if needed.
