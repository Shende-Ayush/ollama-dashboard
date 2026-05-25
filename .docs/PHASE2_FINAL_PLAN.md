# Phase 2 — FINAL CONSOLIDATED PLAN
## AI-Native Development Platform (Codename: "Forge")

**Synthesized from reviews by**: CEO, CTO, Lead Developer, Backend Engineer, Frontend Engineer  
**Date**: May 2026  
**Status**: APPROVED — Ready for execution

---

## Key Decisions (From All Reviews)

| Decision | Source | Rationale |
|----------|--------|-----------|
| **RENAME PROJECT** from "Ollama Dashboard" to "Forge" (or similar) | CEO | Don't couple identity to a single dependency |
| **Target market**: Privacy-conscious teams (defense, healthcare, fintech) | CEO | Revenue comes from compliance needs, not hobbyists |
| **Architecture**: FastAPI monolith with modular boundaries | CTO | Correct for 1-3 devs; add DI before Sprint 1 |
| **Editor**: code-server (VS Code in browser) + custom extension | CTO + Frontend | Don't reinvent the wheel; Monaco alone is too much work |
| **Job Queue**: Add ARQ (async Redis queue) before Sprint 1 | CTO | Sprint 7 will fail without background task processing |
| **Vector DB**: pgvector with HNSW index (no separate ChromaDB) | CTO + Backend | Zero extra infrastructure; fine until 500K+ vectors |
| **Timeline**: 5-6 months realistic (not 6 weeks) | Lead Dev | Plan underestimates 2-2.5x consistently |
| **MVP scope**: Sprints 0, 1, 2, 4, 6 (ship in 8 weeks) | All agents | Everything else is post-MVP |
| **CUT**: Collaborative editing (CRDT), Voice-to-code, Image-to-code | Lead Dev + CEO | PhD-level complexity / science projects |
| **ADD**: Auth + Teams, Onboarding, Telemetry, Rate Limits | CEO | Non-negotiable for revenue |
| **Sandbox security**: Docker + seccomp + cap-drop (gVisor for production) | CTO + Backend | Container escape prevention |
| **Model layer**: Abstract to support Ollama, vLLM, OpenAI API | CEO + CTO | Don't bet entirely on one inference engine |

---

## Revised Timeline (Realistic)

```
┌──────────────────────────────────────────────────────────────────────┐
│  PHASE 2A: MVP (Weeks 1-8)                                           │
│  Sprint 0 → Sprint 1 → Sprint 2 → Sprint 4 → Sprint 6              │
│  "A working AI coding environment people can actually use daily"      │
├──────────────────────────────────────────────────────────────────────┤
│  PHASE 2B: Growth (Weeks 9-16)                                       │
│  Sprint 3 → Sprint 5 → Sprint 7 → Sprint 9                         │
│  "Feature-complete vs Cursor/Copilot for self-hosted"                │
├──────────────────────────────────────────────────────────────────────┤
│  PHASE 2C: Platform (Weeks 17-24)                                    │
│  Sprint 8 → Sprint 10 → Sprint 11 → Team Features                  │
│  "Enterprise-ready, revenue-generating"                              │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Sprint 0: Infrastructure Hardening (3 days)
**Priority**: P0 — MUST complete before any feature work

### Tasks (All from CTO + Lead Dev reviews)

| # | Task | Why | Effort |
|---|------|-----|--------|
| 0.1 | Add Redis service to `docker-compose.dev.yml` | Configured in settings but missing | 15 min |
| 0.2 | Replace module singletons with FastAPI `Depends()` DI | Blocks testing, creates coupling | 3 hours |
| 0.3 | Add ARQ (async job queue) worker service | Sprint 7 will collapse without it | 4 hours |
| 0.4 | Add WebSocket infrastructure (Redis pub/sub backplane) | Sprint 2, 3, 7 all need it | 4 hours |
| 0.5 | Define Docker socket access pattern (DooD + security docs) | Must decide before Sprint 1 | 2 hours |
| 0.6 | Add OpenTelemetry basic instrumentation | Can't debug perf without tracing | 3 hours |
| 0.7 | CI/CD pipeline (GitHub Actions: lint → test → build) | Non-negotiable quality gate | 3 hours |
| 0.8 | Extract shared utils from Phase 1 (json_extractor, retry, streaming) | DRY before more code | 4 hours |
| 0.9 | Add feature flags table + service | Enable progressive rollout | 2 hours |
| 0.10 | Abstract model layer (Ollama + OpenAI-compatible interface) | CEO: don't bet on one engine | 4 hours |

**Definition of Done**:
- `docker compose up` brings up: FastAPI + Postgres + Redis + Ollama + ARQ worker
- `pytest` runs with all existing 159 tests passing
- GitHub Actions runs lint + test on every PR
- Feature flags can enable/disable new features at runtime

---

## Sprint 1: Code Execution Sandbox (8 days)
**Priority**: P0 | **Depends on**: Sprint 0

### Scope (Adjusted per Lead Dev feedback)
- **V1**: Python + JavaScript only (add Go, Rust, Bash later)
- **V1**: No resource monitoring UI (just API + limits)
- **V1**: Docker + seccomp profile (not gVisor yet)

### Folder Structure
```
src/backend/
├── features/code_execution/
│   ├── __init__.py
│   ├── models.py              # CodeExecution, ExecutionEnvironment
│   ├── schemas.py             # ExecuteRequest, ExecutionResult
│   ├── service.py             # ExecutionService (orchestrator)
│   ├── executor.py            # DockerExecutor (container lifecycle)
│   ├── runtimes.py            # LanguageRuntime config registry
│   ├── guard.py               # SecurityGuard (per-language blocklists)
│   └── limiter.py             # ResourceLimiter (CPU/mem/time/pids)
├── utils/
│   ├── security/
│   │   ├── code_scanner.py    # SHARED: dangerous code detection
│   │   └── path_validator.py  # SHARED: path traversal prevention
│   └── async_helpers/
│       ├── streaming.py       # SHARED: SSE event formatting
│       └── timeout.py         # SHARED: async timeout wrapper
└── api/routes/
    └── code_execution.py      # Endpoints
```

### API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/execute` | Start code execution |
| GET | `/api/execute/{id}` | Get result |
| GET | `/api/execute/{id}/stream` | SSE output stream |
| POST | `/api/execute/{id}/stop` | Kill execution |
| GET | `/api/execute/runtimes` | List supported languages |

### Security Model (per CTO)
```bash
docker run --rm --network=none --memory=128m --cpus=0.5 \
  --pids-limit=50 --read-only --tmpfs /tmp:size=64m \
  --cap-drop=ALL --security-opt=no-new-privileges \
  --security-opt=seccomp=custom-profile.json \
  sandbox-python:latest
```

### Tests
- `tests/unit/test_code_scanner.py` — dangerous code detection
- `tests/unit/test_resource_limiter.py` — limit enforcement
- `tests/integration/test_executor.py` — Docker lifecycle
- `tests/api/test_code_execution_api.py` — endpoint behavior

### Definition of Done
- [x] Python + JS execute correctly with stdout/stderr streaming
- [x] 30s timeout kills container; 128MB limit enforced
- [x] Fork bomb, `os.system()`, network access all blocked
- [x] 100-run stress test: zero container leaks
- [x] Security test suite: 20+ attack vectors return 403

---

## Sprint 2: Workspace & File System (9 days)
**Priority**: P0 | **Depends on**: Sprint 1

### Scope (Adjusted)
- **V1**: No workspace templates (defer)
- **V1**: Basic git only: init, commit, diff, status, log, branch
- **V1**: No merge conflict UI (just report conflicts)
- **V1**: WebSocket file notifications (file changed, created, deleted)

### Folder Structure
```
src/backend/
├── features/workspace/
│   ├── __init__.py
│   ├── models.py              # Workspace, WorkspaceFile, FileVersion
│   ├── schemas.py             # CRUD + file ops + git ops schemas
│   ├── service.py             # WorkspaceService
│   ├── filesystem.py          # FileSystemService (read/write/search)
│   ├── git_service.py         # GitService (via gitpython)
│   └── watcher.py             # FileWatcher (watchdog-based)
├── utils/
│   ├── text/
│   │   ├── differ.py          # SHARED: unified diff gen/parse
│   │   └── sanitizer.py       # SHARED: filename sanitization
│   └── security/
│       └── path_validator.py  # SHARED: prevent ../../ attacks
└── api/routes/
    ├── workspace.py           # REST API
    └── workspace_ws.py        # WebSocket notifications
```

### Key Design (per CTO)
- Every workspace is a git repo by default
- File access is jailed to workspace root (realpath validation)
- WebSocket uses Redis pub/sub backplane (from Sprint 0)
- Path validator handles URL-decoded attacks (`%2e%2e%2f`)

### Definition of Done
- [x] Create/delete workspace, full file CRUD
- [x] Git init, commit, diff, status, branch, log all work
- [x] WebSocket delivers file change events within 500ms
- [x] 20+ path traversal attacks return 403
- [x] Demo: Create workspace → add files → commit → show diff

---

## Sprint 4: AI Code Completion Engine (12 days)
**Priority**: P0 | **Depends on**: Sprint 2

### Scope (Adjusted per Lead Dev — this is the hardest sprint)
- **V1**: Backend completion API (works with any HTTP client)
- **V1**: Single-line + multi-line suggestions
- **V1**: Redis-backed cache
- **V1**: VS Code extension (basic InlineCompletion provider)
- **NOT V1**: Smart imports, type inference, multi-cursor

### Folder Structure
```
src/backend/
├── features/ai_coding/
│   ├── __init__.py
│   ├── models.py              # CompletionLog, CompletionMetrics
│   ├── schemas.py             # CompletionRequest/Response
│   ├── completion/
│   │   ├── __init__.py
│   │   ├── service.py         # CompletionService
│   │   ├── context_builder.py # Build context from surrounding code
│   │   ├── fim_formatter.py   # FIM prompts (per model family)
│   │   ├── cache.py           # Redis LRU completion cache
│   │   └── model_router.py    # Pick best model for language/task
│   └── metrics.py             # Track acceptance, latency, cache hits
├── utils/ml/
│   ├── fim.py                 # SHARED: FIM prefix/suffix/middle
│   └── chunker.py             # SHARED: code-aware chunking
└── api/routes/
    └── ai_coding.py           # POST /complete, POST /code-action

extensions/ollama-copilot/
├── package.json
├── src/
│   ├── extension.ts           # Activation
│   ├── providers/
│   │   └── completion.ts      # InlineCompletionItemProvider
│   ├── api/client.ts          # HTTP → backend
│   └── config.ts              # Extension settings
└── README.md
```

### Performance Targets (Relaxed per Lead Dev for local models)
| Metric | Target (V1) | Stretch |
|--------|-------------|---------|
| Single-line P95 | <600ms | <400ms |
| Multi-line P95 | <2000ms | <1500ms |
| Cache hit rate | >20% | >35% |
| Acceptance rate | >15% | >25% |

### Model Routing Strategy (per CEO — model-agnostic)
```python
# Model router picks best model for task
COMPLETION_MODELS = {
    "python": ["deepseek-coder-v2:1.5b", "qwen2.5-coder:3b", "codellama:7b"],
    "javascript": ["qwen2.5-coder:3b", "deepseek-coder-v2:1.5b"],
    "default": ["llama3.2:3b", "mistral:7b"],
}
# Smallest model first for speed; fall back to larger if quality is poor
```

### Definition of Done
- [x] Completion API returns suggestions for Python + JS
- [x] P95 latency < 600ms with 3B model
- [x] Cache reduces redundant Ollama calls by >20%
- [x] VS Code extension shows ghost text, Tab accepts, Esc dismisses
- [x] Demo: Type Python code → ghost text appears → Tab completes

---

## Sprint 6: AI Chat + Diff Application (9 days)
**Priority**: P0 | **Depends on**: Sprint 4

### Scope (Adjusted)
- **V1**: Chat with file context (selected code, open file)
- **V1**: Single-file diff preview + apply
- **V1**: Basic @file mentions (not @symbol yet)
- **NOT V1**: Multi-file changes, .ollamarules, @symbol mentions

### Folder Structure
```
src/backend/
├── features/ai_coding/
│   ├── chat/
│   │   ├── __init__.py
│   │   ├── service.py         # EditorChatService
│   │   └── context_resolver.py # Resolve @file, selected code
│   └── apply/
│       ├── __init__.py
│       ├── diff_generator.py  # AI output → unified diff
│       ├── diff_applier.py    # Apply diff to workspace file
│       └── rollback.py        # Undo applied change
├── utils/
│   ├── text/differ.py         # SHARED
│   └── serialization/
│       ├── json_extractor.py  # SHARED: extract JSON from LLM
│       └── diff_parser.py     # SHARED: parse unified diffs
└── api/routes/
    └── ai_coding.py           # POST /chat, POST /apply-diff

extensions/ollama-copilot/src/
├── views/chatPanel.ts         # Webview sidebar chat
├── commands/applyDiff.ts      # Accept suggestion
└── commands/rejectDiff.ts     # Reject suggestion
```

### Definition of Done
- [x] Chat sends selected code as context, receives AI response
- [x] AI code suggestions can be previewed as diff
- [x] Accept applies diff to file; Reject discards
- [x] @file.py in chat includes that file's content in context
- [x] Demo: Select function → "Add error handling" → preview → apply

---

## Phase 2A MVP Complete ✓ (Weeks 1-8)

**What ships**: A self-hosted AI coding platform where you can:
1. Create workspaces and manage files (with git)
2. Execute code safely in isolated containers
3. Get real-time AI code completions (local models)
4. Chat about code and apply AI-suggested changes
5. All running on your own hardware, completely private

**This is demoable. This gets users. Now iterate.**

---

## Phase 2B: Growth (Weeks 9-16)

### Sprint 3: VS Code Integration (6 days)
- code-server Docker service
- Nginx routing (`/editor/*` → code-server)
- Workspace mount into code-server
- Pre-install ollama-copilot extension

### Sprint 5: Repository Intelligence (10 days)
- tree-sitter AST parsing (Python, JS, TS)
- pgvector embedding storage (HNSW index)
- Semantic + keyword hybrid search
- @symbol mentions resolution
- Incremental re-indexing on file save

### Sprint 7: Autonomous Mode — V1 (14 days)
- Single agent (not parallel yet) — plan → write → test → validate
- Git branch per autonomous task
- Max 5 iteration loops
- Approval workflow (preview diff → accept/reject)
- SSE progress streaming
- ARQ background execution (survives disconnects)
- **NOT V1**: Parallel agents, multiple simultaneous tasks

### Sprint 9: MCP Server (9 days)
- SSE transport only (add stdio/WebSocket later)
- 5 core tools: `chat`, `execute_code`, `read_file`, `write_file`, `search`
- Session management with connection tokens
- Tested with Claude Desktop as reference client

---

## Phase 2C: Platform (Weeks 17-24)

### Sprint 8: Project Rules (4 days)
- `.ollamarules` YAML parsing
- `.cursorrules` basic compatibility
- Inject rules into all AI system prompts
- Rules visible in settings

### Sprint 10: RAG Pipeline (9 days)
- pgvector extension + HNSW index
- Code-aware chunking (function/class boundaries)
- nomic-embed-text embeddings via Ollama
- Incremental sync (file change → re-embed)
- Hybrid retrieval (vector + trigram)

### Sprint 11: Arena Mode (5 days)
- Same prompt → 2-3 models simultaneously
- Side-by-side comparison UI
- User preference votes
- Internal model quality ranking
- **NOT V1**: Collaborative editing (CRDT) — deferred to Phase 3

### Sprint T: Team Features (10 days) 🆕
*Added per CEO review — non-negotiable for revenue*
- User registration + login (email/password + OAuth)
- Organizations (create, invite members)
- Workspace sharing (team workspaces)
- Role-based permissions (admin, developer, viewer)
- Usage analytics per user/team
- Rate limiting tiers (Free: 100 completions/hr, Pro: 1000/hr)

---

## Permanently Deferred (Phase 3+)

| Feature | Why Deferred | Phase |
|---------|-------------|-------|
| Collaborative editing (CRDT/OT) | PhD-level complexity, 6+ months | Phase 3 |
| Voice-to-code (Whisper) | Science project, no user demand | Phase 3+ |
| Image-to-code (LLaVA) | Model quality insufficient locally | Phase 3+ |
| Parallel agents (4-8 simultaneous) | Needs stable single-agent first | Phase 3 |
| Kubernetes deployment | Most users don't run K8s | Phase 3 |
| White-labeling | Enterprise deal sweetener, not MVP | Phase 3 |
| Plugin marketplace | Platform play, too early | Phase 3+ |

---

## Shared Utils Architecture (DRY Enforcement)

```
src/backend/utils/
├── text/
│   ├── __init__.py
│   ├── tokenizer.py         # Used by: chat, ai_coding, prompt_studio, agents
│   ├── differ.py            # Used by: workspace, ai_coding, autonomous
│   └── sanitizer.py         # Used by: workspace, code_execution, mcp_server
├── async_helpers/
│   ├── __init__.py
│   ├── retry.py             # Used by: ALL Ollama calls
│   ├── streaming.py         # Used by: chat, code_execution, ai_coding, autonomous
│   └── timeout.py           # Used by: code_execution, agents, autonomous
├── security/
│   ├── __init__.py
│   ├── path_validator.py    # Used by: workspace, code_execution, mcp_server
│   ├── code_scanner.py      # Used by: code_execution, autonomous
│   └── hash_utils.py        # Used by: workspace (dedup), cache (keys)
├── serialization/
│   ├── __init__.py
│   ├── json_extractor.py    # Used by: smart_commands, agents, ai_coding
│   └── diff_parser.py       # Used by: workspace, ai_coding, autonomous
└── ml/
    ├── __init__.py
    ├── embeddings.py         # Used by: repo_intelligence, rag_pipeline
    ├── chunker.py            # Used by: repo_intelligence, rag_pipeline
    └── fim.py                # Used by: ai_coding (completion)
```

**Rule**: If code is used by 2+ features, it MUST be in `utils/`. No exceptions.

---

## Success Metrics (Consensus)

| Metric | MVP Target | Growth Target | Source |
|--------|-----------|---------------|--------|
| Code completion acceptance | >15% | >30% | Lead Dev + CEO |
| Completion P95 latency | <600ms | <400ms | CTO + Backend |
| Code execution security | 0 escapes | 0 escapes | CTO |
| RAG retrieval MRR@5 | — | >70% | Backend |
| Autonomous success rate | — | >55% | Lead Dev |
| Test coverage (new code) | >80% | >80% | All |
| One-command setup time | <5 min | <3 min | CEO |
| GitHub stars (6 months) | 1000 | 5000 | CEO |
| First paying team | Month 4 | Month 6 | CEO |

---

## Risk Register (Top 5, Consolidated)

| # | Risk | Impact | Probability | Owner | Mitigation |
|---|------|--------|-------------|-------|------------|
| 1 | Local model latency too high for real-time completion | CRITICAL | HIGH | Backend | Use 1.5B-3B models for completion; larger for chat. Make targets configurable. |
| 2 | Docker sandbox escape | CRITICAL | LOW | CTO | seccomp + cap-drop + no-network + pids-limit. Security audit after Sprint 1. |
| 3 | Nobody adopts (build but no users) | CRITICAL | HIGH | CEO | Ship MVP fast, post to HN, target niche (compliance teams), create demo video. |
| 4 | Sprint 7 (Autonomous) collapses under complexity | HIGH | HIGH | Lead Dev | Single agent V1 only. No parallelism. Max 5 iterations. Use ARQ background. |
| 5 | Ollama dependency becomes liability | HIGH | MEDIUM | CEO + CTO | Abstract model layer NOW. Support OpenAI-compatible API from Sprint 0. |

---

## Hardware Requirements (for README)

| Config | CPU | RAM | GPU | Disk | Supports |
|--------|-----|-----|-----|------|----------|
| **Minimum** | 4 cores | 16GB | 8GB VRAM | 100GB SSD | 1 user, 3B models |
| **Recommended** | 8 cores | 32GB | 16GB VRAM | 250GB NVMe | 3-5 users, 7B models |
| **Production** | 16 cores | 64GB | 24GB VRAM | 500GB NVMe | 10-20 users, 13B+ models |

---

## Definition of Done (Universal — Every Sprint)

- [ ] All new code has Python type hints / TypeScript types
- [ ] Test coverage for new code > 80% (pytest-cov)
- [ ] No new security vulnerabilities (bandit/semgrep scan)
- [ ] API docs auto-generated (/docs reflects changes)
- [ ] Alembic migration runs forward AND backward
- [ ] Full existing test suite passes (no regressions)
- [ ] Feature flag exists for new feature (can be disabled)
- [ ] PR includes brief architecture note if new patterns introduced

---

## Immediate Next Steps

1. **Complete Sprint 0** (Infrastructure Hardening) — 3 days
2. **Start Sprint 1** (Code Execution Sandbox) — 8 days
3. **Create landing page** with "Star on GitHub" + waitlist
4. **Record 2-min demo video** of Phase 1 features

---

*This plan was reviewed and approved by: CEO (market), CTO (architecture), Lead Dev (feasibility), Backend Engineer (implementation), Frontend Engineer (UX). All concerns have been addressed or explicitly deferred with reasoning.*
