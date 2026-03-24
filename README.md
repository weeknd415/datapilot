# DataPilot

**AI-powered SaaS metrics intelligence.** Ask questions about MRR, churn, subscriptions, and support in plain English — get answers backed by SQL, documents, and analytics.

Built with LangGraph orchestration, Text-to-SQL, Document AI (RAG), and MCP servers. Every agent is simultaneously a standalone MCP server usable from Claude Desktop, Cursor, or any MCP-compatible client.

## Live Demo

**Try it now:** [https://datapilot-tiqv.vercel.app](https://datapilot-tiqv.vercel.app)

> The backend runs on Render's free tier and spins down after 15 minutes of inactivity. First request after idle takes 30-60 seconds to cold-start. Subsequent requests are fast.

---

## Eval Results

Scored by the built-in evaluation suite (`python -m tests.eval.eval_suite`):

| Category | Score | Details |
|----------|-------|---------|
| SQL Accuracy | **100%** (7/7) | COUNT, filtered COUNT, Top-N, SUM, AVG, JOIN, multi-table |
| Routing Accuracy | **80%** (4/5) | SaaS metrics, documents, analytics, greetings, complex queries |
| SQL Safety | **100%** (5/5) | DROP, DELETE, UPDATE, INSERT, injection all blocked |
| **Overall** | **94%** (16/17) | |

| Metric | Value |
|--------|-------|
| Avg query latency | 1.2s (simple) — 9.5s (complex multi-agent) |
| Cost per query | ~$0.000 (Groq free tier) |
| LLM fallback chain | Groq → Google Gemini → Local (zero downtime) |
| SQL injection vectors blocked | 5/5 (100%) |

---

## The Problem

SaaS companies drown in metrics across Stripe, databases, Salesforce, and spreadsheets. Getting answers to questions like "Which Enterprise accounts have declining feature adoption and open critical tickets?" requires an analyst to write SQL, cross-reference documents, and build a chart. That takes hours.

## The Solution

DataPilot routes natural language questions to specialized AI agents that query your SaaS database, search documents (SOC2 reports, contracts, board decks), and generate analytics — returning answers with source attribution and confidence scores in seconds.

---

## Architecture

```
                         ┌──────────────────────┐
                         │    User Interface     │
                         │   (Next.js + SSE)     │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │   FastAPI Backend     │
                         │   /api/query          │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │     Supervisor Agent           │
                    │  (LangGraph State Machine)     │
                    │  Routes → Orchestrates →       │
                    │  Synthesizes                    │
                    └───┬───────────┬───────────┬───┘
                        │           │           │
              ┌─────────▼──┐ ┌─────▼──────┐ ┌──▼──────────┐
              │ SQL Agent  │ │ Document   │ │ Analytics   │
              │            │ │ Agent      │ │ Agent       │
              │ NL → SQL   │ │ PDF/RAG    │ │ Stats +     │
              │ Execute    │ │ ChromaDB   │ │ Charts      │
              │ Explain    │ │ Search     │ │ Trends      │
              └─────┬──────┘ └─────┬──────┘ └──────┬──────┘
                    │              │                │
              ┌─────▼──────┐ ┌────▼───────┐ ┌──────▼──────┐
              │ MCP Server │ │ MCP Server │ │ MCP Server  │
              │ :8010      │ │ :8011      │ │ :8012       │
              └────────────┘ └────────────┘ └─────────────┘
                    ▲              ▲                ▲
                    │              │                │
              Claude Desktop / Cursor / Any MCP Client
```

**Each agent is both a component of the orchestrated system AND a standalone MCP server.**

---

## SaaS Data Model

DataPilot ships with a realistic B2B SaaS metrics database:

| Table | Records | Contains |
|-------|---------|----------|
| `accounts` | 40 | Company name, plan tier, MRR, ARR, status, industry, churn date |
| `subscriptions` | 47 | Plan changes, seat counts, billing cycles |
| `mrr_events` | 95 | New, expansion, contraction, churn, reactivation events |
| `feature_usage` | 4,796 | Daily active users and event counts per feature |
| `support_tickets` | 1,754 | Priority, category, CSAT scores, resolution times |
| `invoices` | 399 | Billing status, payment tracking |

Key metrics from the seed data: **$102K MRR**, **34 active accounts**, **12.8% churn rate**, **118% NRR**.

Sample documents included:
- Series A board deck with Q1 2025 metrics
- SOC 2 Type I compliance summary
- Enterprise MSA with GlobalSync Ltd ($39K ACV)

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Orchestration | **LangGraph** | Explicit state machines, conditional routing, checkpointing |
| MCP | **FastMCP** | Decorator-based MCP servers, 20 lines per server |
| Primary LLM | **Groq** (Llama 3.3 70B) | Free tier, 500 tok/sec, GPT-4 competitive |
| Fallback LLM | **Google Gemini** | Free tier, automatic failover |
| Backend | **FastAPI** + SSE + WebSocket | Async, streaming, auto-docs |
| Frontend | **Next.js 14** + Tailwind | Agent trace visualization, chart display |
| Database | **SQLite** (demo) / **PostgreSQL** (prod) | One env var to switch |
| Vector Store | **ChromaDB** | Zero-infrastructure document search |
| Charts | **matplotlib** | Server-side rendering, base64 PNG |

**Total cost: $0/month** using free tiers of Groq and Google Gemini.

See [DECISIONS.md](./DECISIONS.md) for detailed reasoning behind every choice.

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend)
- A free Groq API key from [console.groq.com](https://console.groq.com)

### 1. Clone and setup

```bash
git clone https://github.com/weeknd415/datapilot.git
cd datapilot

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -e .

cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 2. Seed the SaaS database

```bash
python scripts/seed_database.py
```

### 3. Start the backend

```bash
python -m backend.main
```

API at `http://localhost:8000` | Docs at `http://localhost:8000/docs`

### 4. Start the frontend

```bash
cd frontend && npm install && npm run dev
```

UI at `http://localhost:3000`

### 5. Use via MCP (Claude Desktop / Cursor)

Add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "datapilot-sql": {
      "command": "python",
      "args": ["-m", "backend.mcp_servers.sql_mcp"],
      "cwd": "/path/to/datapilot",
      "env": { "GROQ_API_KEY": "your-key" }
    }
  }
}
```

See `mcp_config.json` for all three MCP server configurations.

### Docker

```bash
cp .env.example .env  # add your API keys
docker compose up
```

---

## Example Queries

| Query | Agents Used | What it demonstrates |
|-------|-------------|---------------------|
| "What is our total MRR?" | SQL | Simple aggregation |
| "Which accounts have churned and why?" | SQL | JOIN + churn analysis |
| "Show MRR growth trends with a chart" | SQL + Analytics | Multi-agent chaining |
| "What are the SLA terms in the GlobalSync contract?" | Document | RAG retrieval |
| "Which Enterprise accounts have declining feature adoption?" | SQL | Complex SaaS query |
| "Compare our SOC2 compliance status with actual support metrics" | Document + SQL + Analytics | Full pipeline |

---

## Project Structure

```
datapilot/
├── backend/
│   ├── agents/           # Specialist agents
│   │   ├── sql_agent.py          # Text-to-SQL with confidence scoring
│   │   ├── document_agent.py     # PDF/RAG + ChromaDB search
│   │   ├── analytics_agent.py    # Analysis + chart generation
│   │   └── supervisor.py         # LangGraph orchestrator
│   ├── mcp_servers/      # MCP server wrappers
│   ├── api/              # REST + SSE + WebSocket endpoints
│   ├── core/             # Config, LLM providers, models, memory, rate limiter
│   └── db/               # Database operations + SQL safety
├── frontend/             # Next.js UI with agent trace panel
├── data/                 # SaaS database + sample documents
├── tests/
│   ├── unit/             # 10 unit tests
│   └── eval/             # 17-case evaluation suite
├── scripts/              # Database seeding
├── ARCHITECTURE.md       # Deep-dive developer documentation
├── DECISIONS.md          # Engineering decision log (12 decisions)
└── docker-compose.yml
```

---

## Testing

```bash
# Unit tests (10 tests)
pytest tests/unit/ -v

# Evaluation suite (17 tests — requires LLM API key)
python -m tests.eval.eval_suite

# Lint
ruff check backend/ tests/
```

---

## License

MIT
