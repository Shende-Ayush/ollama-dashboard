# Ollama Dashboard v2

A full-featured local LLM management dashboard — multi-page React SPA + FastAPI backend.

## Pages
| Route | Description |
|---|---|
| `/models` | Installed models, runtime GPU/RAM stats, pull by ID with live progress |
| `/discover` | Curated catalog of 18 popular models — filter, search, one-click pull |
| `/chat` | Full chat interface — streaming, markdown, code highlighting, conversation persistence |
| `/conversations` | Browse, rename, archive, delete saved conversations |
| `/terminal` | WebSocket terminal for safe Ollama commands with history & suggestions |
| `/analytics` | KPIs, token usage charts, request timeseries, system health (Recharts) |

## Quick Start

```bash
# Start everything
cd docker
docker compose -f ../docker-compose.dev.yml up --build

# App available at http://localhost:7000
```

## Auth
Auth is **disabled** by default — all endpoints are open.  
To re-enable: swap `from backend.common.security.no_auth import require_api_key`  
back to `from backend.common.security.api_key import require_api_key` in each route file.

## Stack
- **Backend**: FastAPI · SQLAlchemy async · PostgreSQL · Redis · Prometheus
- **Frontend**: React 18 · React Router v6 · Recharts · react-markdown · react-syntax-highlighter
- **Infra**: Docker Compose · Nginx · Ollama
