# DataPilot

**Multi-agent Business Intelligence system that lets non-technical users ask questions in plain English and get answers from both databases and documents.**

Built with LangGraph orchestration, Text-to-SQL, Document AI, and MCP servers — every agent is simultaneously a standalone MCP server usable from Claude Desktop, Cursor, or any MCP-compatible client.

---

## The Problem

Business teams waste hours waiting for analysts to write SQL queries or dig through documents. Ad-hoc reporting requests create bottlenecks that slow down decision-making across the organization.

## The Solution

DataPilot routes natural language questions to specialized AI agents that query databases, search documents, and generate analytics — returning answers with source attribution and confidence scores.

**Key results from the architecture this is based on:**
- ~50% reduction in ad-hoc reporting requests
- Sub-5-second response time for most queries
- 98%+ system reliability with multi-provider LLM fallback

---

## Architecture

```
                         ┌──────────────────────┐
                         │    User Interface     │
                         │   (Next.js + WS)      │
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
              │ NL → SQL   │ │ PDF/OCR    │ │ Stats +     │
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

**Each agent is both a component of the orchestrated system AND a standalone MCP server.** This means the SQL Agent can be used from Claude Desktop independently, while also participating in multi-step queries orchestrated by the Supervisor.

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Orchestration | **LangGraph** | Production-grade state machines with checkpointing |
| MCP | **FastMCP** | Simplest MCP server framework |
| Primary LLM | **Groq** (Llama 3.3 70B) | Free tier, fastest inference, GPT-4 competitive |
| Fallback LLM | **Google Gemini** | Free tier, automatic failover |
| Backend | **FastAPI** + WebSocket | Async-first, streaming support |
| Frontend | **Next.js** + Tailwind | Production-grade UI with agent trace visualization |
| Database | **SQLite** (demo) / **PostgreSQL** (prod) | Zero-setup demo, one-line prod switch |
| Vector Store | **ChromaDB** | Zero-infrastructure document search |
| Charts | **matplotlib** | Server-side rendering, works across all clients |

**Total cost: $0/month** using free tiers of Groq and Google Gemini.

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend)
- A free Groq API key from [console.groq.com](https://console.groq.com)

### 1. Clone and setup

```bash
git clone https://github.com/yourusername/datapilot.git
cd datapilot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Configure environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 2. Seed the demo database

```bash
python scripts/seed_database.py
```

This creates a SQLite database with:
- 30 customers across 7 industries
- 12 products in 4 categories
- 2,000+ orders spanning 18 months with seasonal patterns
- 5,000+ order line items
- 1,500+ invoices with payment status tracking
- 46 employees across 6 departments

### 3. Start the backend

```bash
python -m backend.main
```

API available at `http://localhost:8000` | Docs at `http://localhost:8000/docs`

### 4. Start the frontend (optional)

```bash
cd frontend
npm install
npm run dev
```

UI available at `http://localhost:3000`

### 5. Use via MCP (Claude Desktop / Cursor)

Add to your Claude Desktop config (`claude_desktop_config.json`):

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

### Docker (one command)

```bash
cp .env.example .env  # add your API keys
docker compose up
```

---

## Example Queries

| Query | Agents Used |
|-------|-------------|
| "What are the top 5 customers by revenue?" | SQL |
| "Show monthly revenue trends for 2024" | SQL + Analytics |
| "Do any top customers have overdue invoices in the documents folder?" | SQL + Document |
| "What are the payment terms in the CloudHost contract?" | Document |
| "Compare Q3 vs Q4 2024 and generate a chart" | SQL + Analytics |
| "Summarize the Q4 board report and compare projected vs actual revenue" | Document + SQL + Analytics |

---

## Project Structure

```
datapilot/
├── backend/
│   ├── agents/           # Specialist agents
│   │   ├── sql_agent.py          # Text-to-SQL with confidence scoring
│   │   ├── document_agent.py     # PDF processing + ChromaDB search
│   │   ├── analytics_agent.py    # Calculations + chart generation
│   │   └── supervisor.py         # LangGraph orchestrator
│   ├── mcp_servers/      # MCP server wrappers
│   │   ├── sql_mcp.py            # SQL Agent as MCP server
│   │   ├── document_mcp.py       # Document Agent as MCP server
│   │   └── analytics_mcp.py      # Analytics Agent as MCP server
│   ├── api/              # FastAPI routes + WebSocket
│   ├── core/             # Config, LLM providers, models
│   └── db/               # Database operations
├── frontend/             # Next.js UI with agent trace panel
├── data/                 # Sample database + documents
├── tests/                # Unit + integration tests
├── scripts/              # Database seeding
├── DECISIONS.md          # Technical decision log
└── docker-compose.yml    # One-command deployment
```

---

## Key Design Decisions

See [DECISIONS.md](./DECISIONS.md) for detailed reasoning behind every technical choice.

Highlights:
- **Why Groq over OpenAI?** $0 cost with comparable quality (Llama 3.3 70B)
- **Why ChromaDB over pgvector?** Zero-infrastructure setup for portfolio demo
- **Why LangGraph over AutoGen?** Production consensus, explicit state machines
- **Why not Streamlit?** Signals "prototype" — Next.js signals "production-ready"
- **Why 512-token chunks?** Empirically optimal balance of context vs. retrieval precision

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=backend --cov-report=term-missing

# Lint
ruff check backend/ tests/
```

---

## License

MIT
