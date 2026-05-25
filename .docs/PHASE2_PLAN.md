# Phase 2 — AI-Native Development Environment: Complete Implementation Plan

## Executive Summary

Phase 2 transforms the Ollama Dashboard into a **full Agentic IDE** — a self-hosted alternative
to Cursor, Windsurf, and GitHub Copilot that runs entirely on local infrastructure.

Based on industry analysis (Cursor 3.1 parallel agents, Windsurf Cascade, Claude Code,
OpenAI Codex app, Tabby ML), this plan includes every feature that top AI coding tools
ship in 2025-2026, plus unique differentiators for self-hosted/local-first deployment.

**Key Differentiator**: Zero vendor lock-in, runs on your hardware, full data privacy.

---

## Folder Structure Convention

All new code MUST follow this structure:


```
src/
├── backend/
│   ├── api/
│   │   └── routes/              # API endpoints only (thin controllers)
│   ├── common/                  # Shared across ALL features
│   │   ├── config/              # Settings, env vars
│   │   ├── contracts/           # Shared request/response envelopes
│   │   ├── db/                  # Base, session, migrations
│   │   ├── logging/             # Structured logging
│   │   ├── observability/       # Prometheus, tracing
│   │   ├── rate_limit/          # Rate limiting
│   │   └── security/            # Auth, RBAC, guards
│   ├── features/                # Domain modules (each self-contained)
│   │   ├── agents/              # ✅ Phase 1
│   │   ├── chat/                # ✅ Phase 1
│   │   ├── code_execution/      # 🆕 Sprint 1
│   │   ├── workspace/           # 🆕 Sprint 2
│   │   ├── ai_coding/           # 🆕 Sprint 4-6
│   │   ├── repo_intelligence/   # 🆕 Sprint 5
│   │   ├── autonomous/          # 🆕 Sprint 7
│   │   ├── mcp_server/          # 🆕 Sprint 9 (NEW)
│   │   ├── rag_pipeline/        # 🆕 Sprint 10 (NEW)
│   │   └── ...existing...
│   ├── services/                # Stateless shared services
│   │   ├── ollama_client.py
│   │   ├── docker_executor.py   # 🆕 Sprint 1
│   │   └── ...existing...
│   └── utils/                   # Pure utility functions (NO state, NO I/O)
│       ├── text/                # Text processing utilities
│       │   ├── __init__.py
│       │   ├── tokenizer.py     # Token counting (shared by chat, completion, prompt_studio)
│       │   ├── differ.py        # Unified diff generation (shared by workspace, ai_coding)
│       │   └── sanitizer.py     # Input sanitization (shared everywhere)
│       ├── async_helpers/       # Async utilities
│       │   ├── __init__.py
│       │   ├── retry.py         # Retry with backoff (shared by all services)
│       │   ├── streaming.py     # SSE/streaming helpers (shared by chat, execution, completion)
│       │   └── timeout.py       # Timeout context managers
│       ├── security/            # Security utilities
│       │   ├── __init__.py
│       │   ├── path_validator.py  # Path traversal prevention (workspace, code_execution)
│       │   ├── code_scanner.py    # Dangerous code detection (code_execution, autonomous)
│       │   └── hash_utils.py      # Hashing (file dedup, cache keys)
│       ├── serialization/       # Data format utilities
│       │   ├── __init__.py
│       │   ├── json_extractor.py  # Extract JSON from LLM output (smart_commands, agents, ai_coding)
│       │   └── diff_parser.py     # Parse unified diffs (workspace, ai_coding)
│       └── ml/                  # ML/AI utilities
│           ├── __init__.py
│           ├── embeddings.py    # Embedding generation (repo_intelligence, rag_pipeline)
│           ├── chunker.py       # Code/text chunking (repo_intelligence, rag_pipeline)
│           └── fim.py           # Fill-in-Middle formatting (ai_coding)
├── frontend/
│   ├── src/
│   │   ├── api/                 # API client layer
│   │   │   ├── client.ts        # Base HTTP/WS client
│   │   │   ├── endpoints/       # 🆕 Typed endpoint modules
│   │   │   │   ├── workspace.ts
│   │   │   │   ├── execution.ts
│   │   │   │   ├── ai-coding.ts
│   │   │   │   └── agents.ts
│   │   │   └── hooks/           # 🆕 React Query hooks per domain
│   │   ├── components/          # 🆕 Shared component library
│   │   │   ├── ui/              # Primitives (Button, Input, Modal, Dropdown)
│   │   │   ├── editor/          # Editor-related components
│   │   │   ├── layout/          # Layout shells, panels, split-panes
│   │   │   └── feedback/        # Toast, loading, error states
│   │   ├── pages/               # Route-level pages
│   │   ├── stores/              # 🆕 Zustand state management
│   │   ├── hooks/               # Custom React hooks
│   │   ├── utils/               # Frontend utilities
│   │   │   ├── formatting.ts    # Date, size, duration formatters
│   │   │   ├── debounce.ts      # Debounce/throttle
│   │   │   └── language.ts      # Language detection from extension
│   │   └── theme/               # Theme system
│   └── ...
├── extensions/                  # 🆕 VS Code extension source
│   └── ollama-copilot/
│       ├── package.json
│       ├── src/
│       │   ├── extension.ts
│       │   ├── providers/       # Completion, code action, hover providers
│       │   ├── views/           # Webview panels (chat, agent status)
│       │   ├── commands/        # Command palette commands
│       │   └── api/             # Backend API client
│       └── webview/             # Webview HTML/CSS/JS
└── tests/
    ├── unit/                    # Pure logic tests (no DB, no network)
    ├── integration/             # DB + service tests
    ├── api/                     # HTTP endpoint tests
    └── e2e/                     # Full flow tests
```

---

## Features Analysis: What Industry Leaders Ship That We're Missing

### Critical (Must-Have) — Used by 70%+ of developers daily


| Feature | Cursor | Copilot | Windsurf | Tabby | Ours (Phase 2) |
|---------|--------|---------|----------|-------|----------------|
| Inline code completion (FIM) | ✅ | ✅ | ✅ | ✅ | Sprint 4 |
| Multi-file editing (Agent Mode) | ✅ | ✅ | ✅ | ❌ | Sprint 7 |
| Parallel agents (8+ simultaneous) | ✅ | ✅ | ✅ | ❌ | Sprint 7 |
| Codebase-aware context (RAG) | ✅ | ✅ | ✅ | ✅ | Sprint 10 🆕 |
| Chat with code context | ✅ | ✅ | ✅ | ✅ | Sprint 6 |
| MCP server support | ✅ | ✅ | ✅ | ❌ | Sprint 9 🆕 |
| Terminal command generation | ✅ | ✅ | ✅ | ❌ | ✅ Phase 1 |
| Git integration | ✅ | ✅ | ✅ | ❌ | Sprint 2 |
| Multi-model support | ✅ | ❌ | ✅ | ✅ | ✅ Phase 1 |
| Self-hosted / local-first | ❌ | ❌ | ❌ | ✅ | ✅ Core DNA |
| Code execution sandbox | ❌ | ✅ | ❌ | ❌ | Sprint 1 |
| Prompt caching/optimization | ✅ | ✅ | ✅ | ❌ | Sprint 4 |

### Important (Should-Have) — Key differentiators in 2026

| Feature | Status in Industry | Our Sprint | Why It Matters |
|---------|-------------------|------------|----------------|
| **MCP Server** (Model Context Protocol) | Adopted by Anthropic, OpenAI, Google as standard | Sprint 9 | Lets external tools (IDEs, agents) connect to our platform |
| **RAG Pipeline** (codebase knowledge) | Every top tool uses it for context | Sprint 10 | Without RAG, AI suggestions lack project awareness |
| **Arena Mode** (model comparison) | Windsurf ships it, Cursor testing | Sprint 11 | Compare model outputs side-by-side for same prompt |
| **Background agents** (survive disconnects) | OpenAI Codex, Windsurf 2.0 | Sprint 7 | Agents continue working even if user closes browser |
| **Diff preview & approval** | All tools | Sprint 6 | Never apply AI changes without human review |
| **@ mentions** (file/symbol context) | Cursor, Copilot, Claude Code | Sprint 6 | `@file.py` or `@function_name` in chat for precise context |
| **Rules/Instructions files** | Cursor (.cursorrules), Copilot (.github/copilot) | Sprint 8 | Project-specific AI behavior customization |
| **Token budget visibility** | Emerging standard | Sprint 4 | Show users how much context they're using |
| **Streaming diff application** | Cursor Composer | Sprint 7 | Apply changes file-by-file as AI generates them |
| **Voice-to-code** | Emerging (Supermaven, Cursor labs) | Sprint 12 🆕 | Dictate code instructions hands-free |
| **Image-to-code** | GPT-4V, Claude Vision | Sprint 12 🆕 | Upload mockup → generate UI code |
| **Collaborative editing** | Standard in modern IDEs | Sprint 11 🆕 | Multiple users editing same workspace |

---

## Revised Sprint Plan (12 Sprints)

### Sprint 1: Code Execution Sandbox
**Duration**: 3-4 days | **Priority**: P0 (Foundation)

**Goal**: Safe, isolated, multi-language code execution with live output streaming.

#### Backend Structure
```
src/backend/features/code_execution/
├── __init__.py
├── models.py              # CodeExecution, ExecutionEnvironment
├── schemas.py             # ExecuteRequest, ExecutionResult, StreamEvent
├── service.py             # ExecutionService (orchestrates runs)
├── executor.py            # DockerExecutor (container lifecycle)
├── runtimes.py            # LanguageRuntime registry (Python, JS, Go, Rust, etc.)
├── guard.py               # SecurityGuard (block dangerous patterns per language)
└── limiter.py             # ResourceLimiter (CPU, memory, time, disk, process count)

src/backend/utils/security/
├── code_scanner.py        # SHARED: detect dangerous imports/syscalls
└── path_validator.py      # SHARED: prevent path traversal

src/backend/utils/async_helpers/
├── streaming.py           # SHARED: SSE event formatting
└── timeout.py             # SHARED: async timeout context manager

src/backend/api/routes/
└── code_execution.py      # REST + SSE endpoints
```

#### Key Design Decisions
- **Docker-based isolation**: Each execution runs in a fresh container
- **Language runtimes as config**: Add new languages without code changes
- **Streaming output**: Real-time stdout/stderr via SSE (reuse pattern from chat)
- **Resource limits**: Configurable per-language defaults + per-request overrides

#### API Endpoints
```
POST   /api/execute                    → Start execution (returns execution_id)
GET    /api/execute/{id}               → Get execution result
GET    /api/execute/{id}/stream        → Stream output (SSE)
POST   /api/execute/{id}/stop          → Kill execution
GET    /api/execute/runtimes           → List available language runtimes
POST   /api/execute/validate           → Validate code safety without running
```

#### Tests
```
tests/unit/test_code_scanner.py        # Security scanning logic
tests/unit/test_resource_limiter.py    # Limit calculation/enforcement
tests/integration/test_executor.py     # Docker execution lifecycle
tests/api/test_code_execution_api.py   # Full endpoint testing
```

---

### Sprint 2: Workspace & File System Management
**Duration**: 3-4 days | **Priority**: P0 (Foundation)

**Goal**: Virtual workspace management with file CRUD, git integration, and real-time sync.

#### Backend Structure
```
src/backend/features/workspace/
├── __init__.py
├── models.py              # Workspace, WorkspaceFile, FileVersion, WorkspaceSettings
├── schemas.py             # CRUD schemas, file operations, git operations
├── service.py             # WorkspaceService (high-level orchestration)
├── filesystem.py          # FileSystemService (read, write, rename, delete, search)
├── git_service.py         # GitService (init, clone, commit, diff, branch, log, status)
├── watcher.py             # FileWatcher (inotify-based change detection)
└── templates.py           # WorkspaceTemplates (FastAPI starter, React app, etc.)

src/backend/utils/text/
├── differ.py              # SHARED: unified diff generation/parsing
└── sanitizer.py           # SHARED: filename/path sanitization

src/backend/utils/security/
└── path_validator.py      # SHARED: prevent ../../ traversal attacks

src/backend/api/routes/
├── workspace.py           # REST API for workspace/file ops
└── workspace_ws.py        # WebSocket for real-time file change notifications
```

#### Key Design Decisions
- **Isolated workspaces**: Each workspace is a separate directory (supports multi-user)
- **Git-native**: Every workspace is a git repo by default (enables rollback, history)
- **File versioning**: Track changes independently of git (for undo/redo in editor)
- **Template system**: One-click project scaffolding

#### API Endpoints
```
POST   /api/workspaces                          → Create workspace
GET    /api/workspaces                          → List workspaces
GET    /api/workspaces/{id}                     → Get workspace details
DELETE /api/workspaces/{id}                     → Delete workspace
POST   /api/workspaces/{id}/clone               → Clone from git URL

GET    /api/workspaces/{id}/tree                → File tree (recursive)
GET    /api/workspaces/{id}/files/{path:path}   → Read file content
PUT    /api/workspaces/{id}/files/{path:path}   → Write/update file
POST   /api/workspaces/{id}/files/{path:path}   → Create new file
DELETE /api/workspaces/{id}/files/{path:path}   → Delete file
POST   /api/workspaces/{id}/rename              → Rename/move file
POST   /api/workspaces/{id}/search              → Search in files (content + filename)

GET    /api/workspaces/{id}/git/status          → Git status
GET    /api/workspaces/{id}/git/diff            → Git diff (staged/unstaged)
GET    /api/workspaces/{id}/git/log             → Commit history
POST   /api/workspaces/{id}/git/commit          → Commit changes
POST   /api/workspaces/{id}/git/branch          → Create/switch branch
POST   /api/workspaces/{id}/git/checkout        → Checkout file/branch
```

---

### Sprint 3: VS Code Integration (code-server)
**Duration**: 3-4 days | **Priority**: P0

**Goal**: Embed full VS Code in the platform via code-server, with workspace bridging.

#### Infrastructure
```
docker/
├── Dockerfile.code-server    # Custom code-server with our extension pre-installed
└── docker-compose.dev.yml    # Add code-server service

src/backend/features/workspace/
└── bridge.py                 # WorkspaceBridge: sync between dashboard ↔ code-server filesystem
```

#### Tasks
1. Add `code-server` (or `openvscode-server`) to Docker Compose
2. Nginx routing: `/editor/*` proxied to code-server, `/` to dashboard
3. Workspace bridge: mount workspace directories into code-server
4. Session sharing: pass auth tokens between dashboard and code-server
5. Pre-install our custom Ollama Copilot extension

#### Frontend
```
src/frontend/src/pages/
└── EditorPage.tsx            # Embedded iframe to code-server OR redirect
src/frontend/src/components/layout/
└── EditorLauncher.tsx        # Button to open workspace in VS Code
```

---

### Sprint 4: AI Code Completion Engine
**Duration**: 4-5 days | **Priority**: P0

**Goal**: Real-time inline code completion rivaling GitHub Copilot.

#### Backend Structure
```
src/backend/features/ai_coding/
├── __init__.py
├── models.py              # CompletionRequest, CompletionLog, CompletionMetrics
├── schemas.py             # Request/response for all AI coding operations
├── completion/
│   ├── __init__.py
│   ├── service.py         # CompletionService (main entry point)
│   ├── context_builder.py # Build context window from surrounding code + related files
│   ├── fim_formatter.py   # Format Fill-in-Middle prompts per model
│   ├── cache.py           # Redis LRU cache for repeated completions
│   ├── debouncer.py       # Server-side debouncing for rapid requests
│   └── model_router.py    # Select best model for language/task
├── actions/
│   ├── __init__.py
│   ├── service.py         # CodeActionService
│   ├── explain.py         # Explain selected code
│   ├── refactor.py        # Refactor suggestions
│   ├── optimize.py        # Performance optimization suggestions
│   └── fix.py             # Bug fix suggestions
└── metrics.py             # Track acceptance rate, latency, token usage

src/backend/utils/ml/
├── fim.py                 # SHARED: FIM prompt formatting (prefix/suffix/middle)
├── chunker.py             # SHARED: Split code into context-appropriate chunks
└── embeddings.py          # SHARED: Generate embeddings for code

src/backend/api/routes/
└── ai_coding.py           # Completion + code action endpoints
```

#### VS Code Extension (Sprint 4 output)
```
extensions/ollama-copilot/
├── package.json           # Extension manifest with activation events
├── src/
│   ├── extension.ts       # Main activation
│   ├── providers/
│   │   ├── completion.ts  # InlineCompletionItemProvider
│   │   ├── codeAction.ts  # CodeActionProvider (explain, refactor, fix)
│   │   └── hover.ts       # HoverProvider (AI-enhanced docs)
│   ├── api/
│   │   └── client.ts      # HTTP client → our backend
│   ├── commands/
│   │   ├── explain.ts     # "Ollama: Explain Selection"
│   │   ├── refactor.ts    # "Ollama: Refactor"
│   │   ├── generateTests.ts
│   │   └── toggleCompletion.ts
│   └── config.ts          # Extension settings
└── README.md
```

#### Performance Targets
| Metric | Target |
|--------|--------|
| Single-line completion latency | <400ms P95 |
| Multi-line suggestion latency | <1500ms P95 |
| Cache hit rate | >35% |
| Acceptance rate | >25% |
| Zero impact on typing latency | <16ms frame budget |

---

### Sprint 5: Repository Intelligence (Codebase RAG)
**Duration**: 4-5 days | **Priority**: P1

**Goal**: Deep codebase understanding for context-aware AI.


#### Backend Structure
```
src/backend/features/repo_intelligence/
├── __init__.py
├── models.py              # CodeSymbol, CodeEmbedding, DependencyEdge, ArchPattern
├── schemas.py             # Search, symbol, architecture responses
├── service.py             # RepoIntelligenceService (orchestrator)
├── indexer/
│   ├── __init__.py
│   ├── ast_parser.py      # tree-sitter multi-language AST extraction
│   ├── symbol_extractor.py # Extract functions, classes, vars, imports
│   ├── dependency_graph.py # Build import/dependency DAG
│   └── incremental.py     # Only re-index changed files (watch integration)
├── search/
│   ├── __init__.py
│   ├── semantic.py        # Vector similarity search (pgvector)
│   ├── keyword.py         # Traditional text search (trigram)
│   └── hybrid.py          # Combine semantic + keyword with RRF ranking
├── context/
│   ├── __init__.py
│   ├── ranker.py          # Rank relevant files/symbols for a task
│   ├── at_mentions.py     # Resolve @file.py, @ClassName references
│   └── window_builder.py  # Build optimal context window for LLM
└── architecture.py        # Auto-detect architecture patterns

src/backend/utils/ml/
├── embeddings.py          # SHARED: nomic-embed-text via Ollama
└── chunker.py             # SHARED: Intelligent code chunking with overlap
```

#### Key Innovation: `@mentions` system
Like Cursor/Copilot, users can reference code in chat:
- `@src/backend/services/ollama_client.py` — include entire file
- `@OllamaClient` — include class definition + methods
- `@list_models` — include function + docstring + call sites

---

### Sprint 6: AI Chat-in-Editor + Diff Application
**Duration**: 4-5 days | **Priority**: P0

**Goal**: Conversational AI that can modify code directly with preview/approval workflow.

#### Backend Structure
```
src/backend/features/ai_coding/
├── chat/
│   ├── __init__.py
│   ├── service.py         # EditorChatService (chat with code context)
│   ├── context_resolver.py # Resolve @mentions, selected code, open files
│   └── response_parser.py # Extract code blocks + file paths from AI output
├── apply/
│   ├── __init__.py
│   ├── diff_generator.py  # Generate unified diffs from AI suggestions
│   ├── diff_applier.py    # Apply diffs to workspace files
│   ├── multi_file.py      # Handle changes across multiple files
│   └── rollback.py        # Undo applied changes (git-based)
├── generators/
│   ├── __init__.py
│   ├── test_gen.py        # Generate tests for selected code
│   ├── doc_gen.py         # Generate docstrings, README, API docs
│   └── boilerplate.py     # Generate CRUD, endpoints, models from spec
└── rules/
    ├── __init__.py
    ├── loader.py          # Load .ollamarules / project instructions
    └── applier.py         # Inject rules into system prompts

src/backend/utils/text/
└── differ.py              # SHARED: Unified diff generation/parsing

src/backend/utils/serialization/
├── json_extractor.py      # SHARED: Extract JSON from LLM responses
└── diff_parser.py         # SHARED: Parse unified diffs into file changes
```

#### VS Code Extension Updates
```
extensions/ollama-copilot/src/
├── views/
│   ├── chatPanel.ts       # Webview chat sidebar
│   ├── diffPreview.ts     # Show changes before applying
│   └── agentStatus.ts     # Show agent execution progress
├── providers/
│   └── inlineChat.ts      # Ctrl+I inline chat (like Cursor)
└── commands/
    ├── applyDiff.ts       # Accept AI suggestion
    ├── rejectDiff.ts      # Reject AI suggestion
    └── atMention.ts       # @ autocomplete for files/symbols
```

#### Project Rules System (`.ollamarules`)
```yaml
# .ollamarules (project root)
language: python
framework: fastapi
style:
  - Use async/await everywhere
  - Type hints required on all functions
  - Docstrings in Google format
  - Error handling with custom exceptions
conventions:
  - Service layer pattern (no business logic in routes)
  - Pydantic schemas for all request/response
  - SQLAlchemy async ORM
testing:
  - pytest + pytest-asyncio
  - Mock external services
  - Factory fixtures for test data
```

---

### Sprint 7: Autonomous Development Mode (Agentic Coding)
**Duration**: 5-6 days | **Priority**: P0

**Goal**: "Build Mode" — describe a feature → AI plans, implements, tests, validates autonomously.

#### Backend Structure
```
src/backend/features/autonomous/
├── __init__.py
├── models.py              # BuildTask, BuildStep, BuildApproval
├── schemas.py             # BuildRequest, ProgressEvent, ApprovalRequest
├── service.py             # AutonomousService (main orchestrator)
├── planner.py             # TaskPlanner: break goal → implementation steps
├── writer.py              # CodeWriter: generate code per step
├── tester.py              # TestRunner: generate + execute tests
├── validator.py           # Validator: run code, check errors, iterate
├── reviewer.py            # AIReviewer: self-review before presenting
├── parallel.py            # ParallelExecutor: run agents on separate branches
├── background.py          # BackgroundWorker: survive user disconnects
└── rollback.py            # RollbackManager: git-based safe rollback

src/backend/api/routes/
└── autonomous.py          # Build mode endpoints + SSE progress
```

#### Key Features (matching Cursor/Codex/Claude Code)
1. **Parallel agents**: Up to 4 agents working on separate branches simultaneously
2. **Background execution**: Agents continue even if user closes browser (like OpenAI Codex)
3. **Approval workflow**: Human reviews diff before merge (never auto-commit to main)
4. **Iterative validation**: Write → Run → Fix → Re-run loop (max 5 iterations)
5. **Streaming progress**: Real-time step-by-step visibility via SSE
6. **Safe rollback**: Every autonomous session starts on a new git branch

#### API Endpoints
```
POST   /api/build                       → Start autonomous build task
GET    /api/build/{id}                  → Get task status + steps
GET    /api/build/{id}/stream           → Stream progress events (SSE)
POST   /api/build/{id}/approve          → Approve and merge changes
POST   /api/build/{id}/reject           → Reject and rollback
POST   /api/build/{id}/pause            → Pause agent execution
POST   /api/build/{id}/resume           → Resume paused task
GET    /api/build/active                → List running build tasks
```

---

### Sprint 8: Project Rules, Instructions & Configuration
**Duration**: 2-3 days | **Priority**: P1

**Goal**: Project-specific AI behavior customization (like .cursorrules / .github/copilot).

#### Backend Structure
```
src/backend/features/ai_coding/rules/
├── __init__.py
├── loader.py              # Find and parse rule files from workspace
├── applier.py             # Inject rules into system prompts
├── validator.py           # Validate rule file syntax
└── defaults.py            # Built-in rule templates per language/framework

src/backend/features/workspace/
└── settings.py            # WorkspaceSettings: model preferences, rules path, ignore patterns
```

#### Supported Rule Files
- `.ollamarules` — Our native format (YAML)
- `.cursorrules` — Compatibility with Cursor users migrating
- `.github/copilot-instructions.md` — Compatibility with Copilot

---

### Sprint 9: MCP Server (Model Context Protocol) 🆕
**Duration**: 4-5 days | **Priority**: P1

**Goal**: Expose our platform as an MCP server so external tools can use our AI capabilities.

#### Why This Matters
MCP became the de facto standard for AI tool integration in 2025-2026. By implementing an
MCP server, ANY MCP-compatible client (Claude Desktop, VS Code extensions, other IDEs)
can connect to our platform and use our local Ollama models.

#### Backend Structure
```
src/backend/features/mcp_server/
├── __init__.py
├── models.py              # MCPSession, MCPTool, MCPResource
├── schemas.py             # MCP protocol messages (jsonrpc)
├── server.py              # MCPServer: handles protocol lifecycle
├── transport/
│   ├── __init__.py
│   ├── stdio.py           # stdio transport (for local connections)
│   ├── sse.py             # SSE transport (for remote connections)
│   └── websocket.py       # WebSocket transport
├── tools/
│   ├── __init__.py
│   ├── code_tools.py      # Tools: execute_code, generate_code, explain_code
│   ├── file_tools.py      # Tools: read_file, write_file, search_files
│   ├── model_tools.py     # Tools: list_models, pull_model, chat
│   └── workspace_tools.py # Tools: create_workspace, git_commit, etc.
├── resources/
│   ├── __init__.py
│   ├── file_resource.py   # Expose workspace files as MCP resources
│   └── model_resource.py  # Expose model info as MCP resources
└── prompts/
    └── prompt_templates.py # Expose prompt templates as MCP prompts

src/backend/api/routes/
└── mcp.py                 # MCP HTTP/SSE endpoint
```

#### MCP Tools We Expose
| Tool | Description |
|------|-------------|
| `ollama_chat` | Chat with any installed Ollama model |
| `execute_code` | Run code in sandboxed environment |
| `search_codebase` | Semantic + keyword code search |
| `read_file` | Read file from workspace |
| `write_file` | Write file to workspace |
| `generate_code` | Generate code from description |
| `explain_code` | Explain selected code |
| `run_tests` | Execute test suite |
| `git_status` | Get git status of workspace |
| `list_models` | List available Ollama models |

---

### Sprint 10: RAG Pipeline (Codebase Knowledge) 🆕
**Duration**: 4-5 days | **Priority**: P1

**Goal**: Full RAG pipeline so AI has deep understanding of the entire codebase.

#### Backend Structure
```
src/backend/features/rag_pipeline/
├── __init__.py
├── models.py              # EmbeddingDocument, RAGQuery, RAGResult
├── schemas.py             # Pipeline configuration, query interfaces
├── service.py             # RAGService (query entry point)
├── ingestion/
│   ├── __init__.py
│   ├── pipeline.py        # Ingestion orchestrator
│   ├── file_loader.py     # Load files from workspace
│   ├── chunker.py         # Intelligent code-aware chunking
│   ├── embedder.py        # Generate embeddings via Ollama (nomic-embed-text)
│   └── metadata.py        # Extract metadata (language, function names, imports)
├── storage/
│   ├── __init__.py
│   ├── pgvector.py        # pgvector storage backend (uses existing Postgres!)
│   └── index_manager.py   # Manage vector indexes, rebuild, prune
├── retrieval/
│   ├── __init__.py
│   ├── retriever.py       # Hybrid retrieval (vector + keyword)
│   ├── reranker.py        # Re-rank results for relevance
│   └── context_assembler.py # Assemble retrieved chunks into LLM context
└── sync/
    ├── __init__.py
    ├── incremental.py     # Watch for file changes → update embeddings
    └── scheduler.py       # Background re-indexing on schedule

src/backend/utils/ml/
├── embeddings.py          # SHARED: Ollama embedding generation
└── chunker.py             # SHARED: Code-aware text chunking
```

#### Key Design: Use pgvector (no extra DB!)
We already run PostgreSQL — just enable the `pgvector` extension.
No need for ChromaDB, Pinecone, or any external vector database.

```sql
-- Migration: enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Embeddings table
CREATE TABLE code_embeddings (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL,
    file_path TEXT NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_metadata JSONB DEFAULT '{}',
    embedding vector(768),  -- nomic-embed-text dimension
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_embeddings_vector ON code_embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

---

### Sprint 11: Arena Mode & Collaborative Editing 🆕
**Duration**: 3-4 days | **Priority**: P2

**Goal**: Compare model outputs side-by-side + basic multi-user editing.

#### Backend Structure
```
src/backend/features/ai_coding/arena/
├── __init__.py
├── service.py             # ArenaService: run same prompt on multiple models
├── comparator.py          # Compare outputs (latency, tokens, quality heuristics)
└── voting.py              # Track user preference votes for model ranking

src/backend/features/workspace/collaboration/
├── __init__.py
├── service.py             # CollaborationService
├── presence.py            # Track who's viewing/editing which files
├── cursors.py             # Multi-cursor sync via WebSocket
└── conflict.py            # Conflict detection + resolution
```

#### Arena Mode Features
- Same prompt → 2-3 models simultaneously
- Side-by-side output comparison
- User votes on which is better
- Builds internal model quality ranking for your use cases
- Like Windsurf's Arena Mode but self-hosted

---

### Sprint 12: Voice-to-Code & Image-to-Code 🆕
**Duration**: 3-4 days | **Priority**: P2

**Goal**: Multimodal coding — speak instructions or upload mockups.

#### Backend Structure
```
src/backend/features/ai_coding/multimodal/
├── __init__.py
├── voice/
│   ├── __init__.py
│   ├── transcriber.py     # Whisper-based speech-to-text (via Ollama or local)
│   ├── intent_parser.py   # Parse coding intent from transcription
│   └── executor.py        # Route intent to appropriate action
├── vision/
│   ├── __init__.py
│   ├── image_analyzer.py  # Analyze UI mockups (llava, bakllava models)
│   ├── ui_generator.py    # Generate HTML/CSS/React from mockup analysis
│   └── screenshot_diff.py # Compare screenshot vs generated UI
└── schemas.py             # Multimodal request/response types
```

---

## Shared Utils — DRY Principle Enforcement

These utils are extracted because they're used by 3+ features:

| Utility Module | Used By | Purpose |
|---------------|---------|---------|
| `utils/text/tokenizer.py` | chat, ai_coding, prompt_studio, agents, rag_pipeline | Token counting/estimation |
| `utils/text/differ.py` | workspace, ai_coding, autonomous | Generate/parse unified diffs |
| `utils/text/sanitizer.py` | workspace, code_execution, mcp_server | Input sanitization |
| `utils/async_helpers/retry.py` | ALL services that call Ollama | Exponential backoff retry |
| `utils/async_helpers/streaming.py` | chat, code_execution, ai_coding, autonomous | SSE event formatting |
| `utils/async_helpers/timeout.py` | code_execution, agents, autonomous | Async timeout wrapper |
| `utils/security/path_validator.py` | workspace, code_execution, mcp_server | Path traversal prevention |
| `utils/security/code_scanner.py` | code_execution, autonomous | Dangerous code detection |
| `utils/security/hash_utils.py` | workspace, rag_pipeline, cache | Content hashing |
| `utils/serialization/json_extractor.py` | smart_commands, agents, ai_coding | Extract JSON from LLM output |
| `utils/serialization/diff_parser.py` | workspace, ai_coding, autonomous | Parse diff format |
| `utils/ml/embeddings.py` | repo_intelligence, rag_pipeline | Embedding generation |
| `utils/ml/chunker.py` | repo_intelligence, rag_pipeline | Code-aware chunking |
| `utils/ml/fim.py` | ai_coding (completion) | FIM prompt formatting |

---

## New Dependencies

### Backend
```
# Sprint 1: Code execution
docker==7.1.0
aiodocker==0.23.0

# Sprint 2: Workspace
gitpython==3.1.44
watchdog==5.0.0

# Sprint 4: AI coding
diskcache==5.6.0          # Local cache fallback if Redis unavailable

# Sprint 5: Repo intelligence
tree-sitter==0.23.0
tree-sitter-python==0.23.0
tree-sitter-javascript==0.23.0
tree-sitter-typescript==0.23.0

# Sprint 9: MCP
mcp==1.9.0                # Official MCP Python SDK

# Sprint 10: RAG
pgvector==0.3.0           # pgvector Python bindings (uses existing Postgres)

# Sprint 12: Multimodal
openai-whisper==20240930  # Local speech-to-text (optional)
```

### Frontend
```json
{
  "zustand": "^5.0.0",
  "react-resizable-panels": "^2.1.0",
  "@tanstack/react-query": "^5.60.0",
  "react-virtuoso": "^4.12.0",
  "cmdk": "^1.0.0"
}
```

---

## Success Metrics (Phase 2 Complete)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Completion acceptance rate | >30% | completion_requests.accepted / total |
| Completion P95 latency | <600ms | Prometheus histogram |
| Build mode success rate | >55% | build_tasks completed / total |
| RAG retrieval relevance | >70% MRR@5 | Manual evaluation set |
| Code execution security | 0 escapes | Automated security test suite |
| MCP client compatibility | 3+ clients tested | Integration tests |
| Arena mode preference signal | >60% agreement | User vote consistency |
| Overall test coverage | >80% | pytest-cov |

---

## Implementation Priority Matrix

```
         HIGH IMPACT
              │
   Sprint 7   │   Sprint 4
  (Autonomous) │  (Completion)
              │
LOW ──────────┼────────── HIGH EFFORT
 EFFORT       │
   Sprint 9   │   Sprint 10
   (MCP)      │   (RAG)
              │
         LOW IMPACT
```

**Critical Path**: Sprint 1 → 2 → 3 → 4 → 6 → 7 (these block each other)
**Parallel Track**: Sprint 5, 9, 10 can be done in parallel after Sprint 2

---

## Getting Started

Say **"Start Sprint 1"** and I'll implement the Code Execution Sandbox with:
- Docker-based isolation
- Multi-language support (Python, JavaScript, Go, Rust, Bash)
- Security guards
- Live output streaming
- Full test suite
- Proper shared utils extraction
