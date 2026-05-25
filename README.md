# Ollama Dashboard

**A full-stack AI-native development environment for managing, chatting with, and coding alongside local LLMs.**

Built on [Ollama](https://ollama.com) — gives you a polished web UI for model management, streaming chat, prompt engineering, multi-agent orchestration, AI code completion, and system health monitoring.

---

## Features

### Core Dashboard

| Route | Page | Description |
|-------|------|-------------|
| `/models` | Models | Installed models, runtime GPU/RAM stats, pull by ID with live progress |
| `/discover` | Discover | Scraped Ollama library — search, filter, sort, one-click pull |
| `/chat` | Chat | Streaming chat interface with markdown, code highlighting, conversation persistence |
| `/conversations` | Conversations | Browse, rename, archive, delete saved chat sessions |
| `/terminal` | Terminal | WebSocket terminal for safe Ollama commands with history and suggestions |
| `/analytics` | Analytics | KPIs, token usage charts, request timeseries, system metrics (Recharts) |

### AI-Powered Tools (Phase 1)

| Route | Page | Description |
|-------|------|-------------|
| `/smart-commands` | Smart Commands | Natural language to Ollama commands, command explanations, error analysis, smart autocomplete |
| `/prompt-studio` | Prompt Studio | Template CRUD with versioning, multi-model comparison testing, token analysis |
| `/agents` | Agents | Multi-agent framework with 8 agent types, sequential/parallel/pipeline orchestration |
| `/health` | Health Monitor | Multi-component health checks, incident tracking, auto-recovery actions |

### AI Development Environment (Phase 2)

| Feature | Description |
|---------|-------------|
| Code Execution | Sandboxed runner for Python, JavaScript, TypeScript, Bash, Go with resource limits |
| Workspace Management | Virtual workspaces with file CRUD, directory listing, search, and Git integration |
| AI Code Completion | FIM-based completion with model routing, LRU caching, and code actions (explain, refactor, fix, optimize) |
| AI Chat + Diff | Conversational coding with diff generation, preview, and apply workflow |

---

## Quick Start

### Docker (Recommended)

```bash
cd src
docker compose -f docker-compose.dev.yml up --build
```

App available at **http://localhost:7000**

### Manual Setup

**Backend:**

```bash
cd src
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/ollama_dashboard"
export OLLAMA_HOST="http://localhost:11434"
uvicorn backend.main:app --reload --port 8000
```

**Frontend:**

```bash
cd src/frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`, proxied to the backend.

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python 3.12 · FastAPI · SQLAlchemy (async) · PostgreSQL · Redis · Alembic |
| **Frontend** | React 18 · TypeScript · Vite · React Router v6 · Recharts · react-markdown |
| **Infra** | Docker Compose · Nginx · Ollama · Prometheus |
| **Testing** | pytest · pytest-asyncio · ruff (linting) |
| **CI/CD** | GitHub Actions (lint + test on push/PR) |

---

## API Reference

API docs auto-generated at `/docs` (Swagger) and `/redoc` (ReDoc) when the backend is running.

### Endpoint Groups

| Prefix | Module | Endpoints |
|--------|--------|-----------|
| `/api/models` | Model Management | List, pull (SSE stream), stop, delete, GPU clear, runtime metrics |
| `/api/chat` | Chat | Start session, stream tokens (SSE), stop generation |
| `/api/conversations` | Conversations | CRUD, message history, archive |
| `/api/commands` | Terminal | WebSocket command execution, history, suggestions |
| `/api/analytics` | Analytics | Overview, tokens-by-model, timeseries, system metrics |
| `/api/smart-commands` | Smart Commands | NL-to-command, explain, error analysis, autocomplete |
| `/api/prompt-studio` | Prompt Studio | Template CRUD, versioning, multi-model test, token analysis |
| `/api/agents` | Agents | CRUD, execute, orchestrate, execution history |
| `/api/health` | Health | System check, incidents, recovery actions |
| `/api/execute` | Code Execution | Run code, validate, stop, list runtimes |
| `/api/workspace` | Workspace | File CRUD, Git ops, search |
| `/api/ai-coding` | AI Completion | FIM complete, code actions, cache stats |
| `/api/ai-chat` | AI Chat | Message, diff preview, diff apply |

---

## Project Structure

```
ollama-dashboard/
├── .github/workflows/ci.yml    # Lint + test pipeline
├── .docs/                      # Architecture & planning docs
├── src/
│   ├── backend/
│   │   ├── main.py             # FastAPI app entry point
│   │   ├── api/routes/         # 17 route modules (thin controllers)
│   │   ├── common/             # Config, DB, logging, observability, security
│   │   ├── features/           # Domain modules (self-contained)
│   │   │   ├── agents/         # Multi-agent orchestration
│   │   │   ├── ai_coding/      # Completion + Chat + Diff
│   │   │   ├── code_execution/ # Sandboxed code runner
│   │   │   ├── health/         # Health monitoring & recovery
│   │   │   ├── prompt_studio/  # Prompt templates & testing
│   │   │   ├── smart_commands/ # AI command assistant
│   │   │   ├── workspace/      # File system + Git
│   │   │   └── ...             # chat, models, analytics, etc.
│   │   ├── services/           # Shared services (ollama_client, model_provider)
│   │   └── utils/              # Pure utilities (text, async, security, ML)
│   ├── frontend/
│   │   └── src/
│   │       ├── app/App.tsx     # Router + navigation shell
│   │       ├── pages/          # 10 page components
│   │       ├── api/client.ts   # Typed API client
│   │       ├── hooks/          # useToast, custom hooks
│   │       └── theme/          # Dark/light theme provider
│   ├── alembic/                # Database migrations
│   ├── tests/                  # pytest test suite (294+ tests)
│   ├── docker/                 # Dockerfiles
│   ├── requirements.txt        # Python dependencies
│   ├── requirements-test.txt   # Test dependencies
│   └── docker-compose.dev.yml  # Full dev stack
└── README.md
```

---

## Testing

```bash
cd src
pip install -r requirements.txt -r requirements-test.txt

# Run all tests
DATABASE_URL="sqlite+aiosqlite:///:memory:" python -m pytest tests/ -v

# Run with coverage
DATABASE_URL="sqlite+aiosqlite:///:memory:" python -m pytest tests/ --cov=backend --cov-report=term-missing
```

**294+ tests** covering:
- Smart Commands, Prompt Studio, Agents, Health Monitoring
- Code Execution sandbox with security guards
- Workspace file system and Git integration
- AI Coding completion engine
- AI Chat with diff generation
- Existing services (circuit breaker, token counter, pagination, OllamaClient)
- Full HTTP endpoint integration tests

---

## Configuration

Environment variables (see `src/.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async database connection string |
| `REDIS_URL` | `redis://localhost:6379` | Redis for rate limiting and caching |
| `OLLAMA_HOST` | `http://ollama:11434` | Ollama API base URL |
| `LOG_LEVEL` | `INFO` | Logging level |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |

---

## Auth

Auth is **disabled** by default — all endpoints are open for local development.

To re-enable API key authentication, swap:
```python
from backend.common.security.no_auth import require_api_key
```
back to:
```python
from backend.common.security.api_key import require_api_key
```

---

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feat/my-feature`)
3. Run linting: `ruff check src/backend/ src/tests/`
4. Run tests: `DATABASE_URL="sqlite+aiosqlite:///:memory:" python -m pytest src/tests/ -v`
5. Commit and push
6. Open a Pull Request

---

## License

This project is for personal/educational use. See repository for details.
