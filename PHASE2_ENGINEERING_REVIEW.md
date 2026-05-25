# Phase 2 Engineering Review — Lead Developer Assessment

**Reviewer**: Lead Developer / Engineering Manager  
**Date**: Review of PHASE2_PLAN.md  
**Verdict**: Ambitious plan with good architecture vision, but **severely underestimated timeline** and **scope that would challenge a team of 4**, let alone a solo developer.

---

## 1. Sprint Estimation Reality Check

Assuming **1 senior full-stack developer** (strong Python/React, familiar with Docker, git internals, and LLM APIs):

| Sprint | Plan Estimate | My Estimate | Delta | Reasoning |
|--------|--------------|-------------|-------|-----------|
| **1: Code Execution Sandbox** | 3-4 days | **7-9 days** | +100% | Docker container orchestration, security hardening, streaming output, language runtime configs, resource limits, and the security test suite alone is 2+ days. You're building a mini-Repl.it. |
| **2: Workspace & File System** | 3-4 days | **8-10 days** | +150% | Git integration (clone, branch, diff, merge conflict handling), file watcher, WebSocket real-time sync, path traversal prevention, multi-workspace isolation. This is basically building a mini-GitHub. |
| **3: VS Code Integration** | 3-4 days | **5-7 days** | +75% | code-server integration sounds simple but auth proxying, workspace mounting, and extension pre-installation always has edge cases. Nginx routing + session sharing is fiddly. |
| **4: AI Code Completion** | 4-5 days | **10-14 days** | +150% | This is the HARDEST sprint. FIM formatting per model, context window building, cache layer, debouncing, VS Code extension (TypeScript, unfamiliar to many Python devs), performance targets (<400ms P95). You're building Copilot. |
| **5: Repo Intelligence** | 4-5 days | **10-12 days** | +120% | tree-sitter AST parsing across multiple languages, pgvector setup, embedding pipeline, incremental indexing, hybrid search with RRF ranking. Each of these is a project in itself. |
| **6: AI Chat-in-Editor + Diff** | 4-5 days | **8-10 days** | +80% | Multi-file diff generation, preview/approval workflow, @mentions resolution, .ollamarules parsing, VS Code webview panels. The diff application logic alone needs extensive edge-case handling. |
| **7: Autonomous Mode** | 5-6 days | **14-18 days** | +150% | This is literally what Cursor/Codex spent **teams of 20+** engineers building. Parallel agents, background workers, planning → writing → testing → validation loops, rollback. This is the riskiest sprint. |
| **8: Project Rules** | 2-3 days | **3-4 days** | +50% | Relatively straightforward YAML parsing and prompt injection. Most reasonable estimate in the plan. |
| **9: MCP Server** | 4-5 days | **8-10 days** | +80% | MCP protocol is well-documented but implementing all three transports (stdio, SSE, WebSocket) + 10 tools + proper session management is significant. Testing with 3+ clients adds time. |
| **10: RAG Pipeline** | 4-5 days | **8-10 days** | +80% | pgvector setup is straightforward, but the chunking strategy, incremental sync, re-ranking, and ensuring retrieval quality (70% MRR@5 target) requires iteration and tuning. |
| **11: Arena + Collaboration** | 3-4 days | **6-8 days** | +75% | Arena mode is doable quickly. Collaborative editing (multi-cursor sync, conflict resolution) is a MASSIVE underestimate if done properly. OT/CRDT is PhD-level complexity. |
| **12: Voice + Image** | 3-4 days | **5-7 days** | +60% | Whisper integration is well-trodden. Image-to-code with llava is experimental. Screenshot diffing adds unexpected complexity. |

### Timeline Summary

| | Plan | My Estimate |
|---|---|---|
| **Total working days** | ~42-54 days (~6 weeks) | **92-119 days (18-24 weeks)** |
| **Calendar time (1 dev)** | 6 weeks | **5-6 months** |
| **Calendar time (2 devs)** | 3 weeks (plan's implication) | **3-4 months** |
| **Calendar time (3 devs, optimal)** | N/A | **2.5-3 months** |

**The plan underestimates by roughly 2-2.5x across the board.** This is typical for plans that describe *what* to build without accounting for debugging, edge cases, testing, documentation, CI/CD, and the inevitable "oh wait, this doesn't work the way I thought."

---

## 2. Dependency Analysis

### Critical Path (Blocks Everything)

```
Sprint 1 (Execution) ──→ Sprint 2 (Workspace) ──→ Sprint 4 (Completion) ──→ Sprint 6 (Chat+Diff) ──→ Sprint 7 (Autonomous)
                              │
                              └──→ Sprint 3 (VS Code) ──→ Sprint 4 (VS Code Extension part)
```

**True blockers:**
- Sprint 2 BLOCKS: Sprints 3, 4, 5, 6, 7, 8, 9, 10 (everything needs workspace/file access)
- Sprint 4 BLOCKS: Sprint 6 (chat needs completion infrastructure)
- Sprint 5 BLOCKS: Sprint 10 partially (RAG builds on repo intelligence patterns)
- Sprint 6 BLOCKS: Sprint 7 (autonomous mode needs diff application)

### Parallelizable Tracks (After Sprint 2)

```
Track A (Core IDE):     Sprint 3 → Sprint 4 → Sprint 6 → Sprint 7
Track B (Intelligence): Sprint 5 → Sprint 10
Track C (Platform):     Sprint 8, Sprint 9 (independent)
Track D (Nice-to-have): Sprint 11, Sprint 12 (no dependencies)
```

### Minimum Viable Path to "Demoable Product"

**4-sprint MVP (6-8 weeks with 1 dev):**
```
Sprint 1 (Execution) → Sprint 2 (Workspace) → Sprint 4 (Completion, simplified) → Sprint 6 (Chat+Diff, basic)
```

This gives you: *"Write code, execute it safely, get AI completions, chat about code and apply changes."*  
That's demoable. Everything else is enhancement.

---

## 3. Scope Creep Warnings

### Sprints with Hidden Complexity

| Sprint | What Looks Simple | What's Actually Hard |
|--------|-------------------|---------------------|
| **Sprint 1** | "Docker-based isolation" | Container cleanup, zombie process handling, resource monitoring, image caching, network isolation, handling Docker daemon crashes |
| **Sprint 2** | "Git integration" | Merge conflicts, large file handling, `.gitignore` parsing, symlinks, permission issues, binary files, submodules |
| **Sprint 4** | "Inline completion" | VS Code extension lifecycle, activation events, telemetry, handling multiple cursors, multi-line vs single-line heuristics, cancellation of in-flight requests |
| **Sprint 5** | "tree-sitter parsing" | Language grammar versions, incomplete/broken code parsing, incremental re-parsing, memory usage with large repos |
| **Sprint 7** | "Parallel agents" | State synchronization, merge conflicts between agent branches, deadlock prevention, resource contention, error recovery |
| **Sprint 11** | "Collaborative editing" | CRDT/OT algorithms, cursor position broadcasting, undo/redo with multiple users, network partition handling |

### Where "Just One More Thing" Will Hit Hardest

1. **Sprint 4 (Completion)**: "Can we add multi-line?" → "Can we add smart imports?" → "Can we add type inference?" → endless feature expansion
2. **Sprint 7 (Autonomous)**: "Can the agent also run tests?" → "Can it fix CI?" → "Can it handle PRs?" → you're building Devin
3. **Sprint 9 (MCP)**: "Can we support this client?" → "And this one?" → "And this protocol extension?" → compatibility matrix explosion

### Explicit "V2 — NOT IN INITIAL RELEASE" List

Move these OUT of Phase 2 entirely:

| Feature | Current Sprint | Why Defer |
|---------|---------------|-----------|
| Collaborative editing (multi-cursor, CRDT) | Sprint 11 | PhD-level complexity, zero users asking for this day 1 |
| Voice-to-code | Sprint 12 | Gimmick for self-hosted tool, add when base is solid |
| Image-to-code | Sprint 12 | Experimental, model quality not there for local models |
| Parallel agents (4+ simultaneous) | Sprint 7 | Start with 1 agent, add parallelism later |
| Background execution (survive disconnects) | Sprint 7 | Add after single-agent mode is stable |
| Arena mode voting system | Sprint 11 | Simple side-by-side comparison is V1, voting is V2 |
| All 3 MCP transports | Sprint 9 | Ship SSE only first, add stdio/WebSocket later |
| Template system for workspaces | Sprint 2 | Nice-to-have, not blocking anything |

---

## 4. Team Structure Recommendation

### Can 1 Developer Do This?

**NO.** Not in any reasonable timeline. Here's why:

- The plan spans backend (Python), frontend (React/TypeScript), VS Code extension (TypeScript/VS Code API), DevOps (Docker, Nginx), database (PostgreSQL, pgvector), and ML/AI (embeddings, RAG).
- No single developer is equally strong across all of these.
- Burnout risk is extreme for a 5-6 month solo project of this complexity.

### Recommended Team (Optimal: 3 developers)

| Role | Focus | Sprints |
|------|-------|---------|
| **Senior Backend Engineer** | Python/FastAPI, Docker, security, execution engine | 1, 2 (backend), 5, 7, 9, 10 |
| **Senior Frontend/Extension Dev** | React, TypeScript, VS Code API | 3, 4 (extension), 6 (frontend), 11, 12 |
| **Full-Stack/AI Engineer** | LLM integration, RAG, completion, chat | 4 (backend), 6 (backend), 8, 10 |

### If Budget Allows: Add a 4th (DevOps/QA)
- CI/CD pipeline
- Security testing
- Performance benchmarking
- Docker image optimization
- Deployment automation

### Minimum Viable Team: 2 Developers
- **Dev A** (Backend-heavy): Sprints 1, 2, 5, 7, 9, 10
- **Dev B** (Frontend + AI): Sprints 3, 4, 6, 8, 11, 12

With 2 devs working in parallel (Track A + Track B), realistic timeline: **3-4 months**.

---

## 5. Definition of Done per Sprint

### Sprint 1: Code Execution Sandbox
- [ ] Docker executor creates/destroys containers without leaks (verified by 1000-run stress test)
- [ ] Python, JavaScript, Bash execute correctly with stdout/stderr streaming
- [ ] Resource limits enforced: 30s timeout, 256MB RAM, no network access
- [ ] Security: `fork bomb`, `rm -rf /`, `import os; os.system()` all blocked
- [ ] API returns proper error codes for all failure modes
- [ ] Integration tests pass in CI (requires Docker-in-Docker or similar)
- [ ] **Demo**: Execute Python code from UI, see live output streaming

### Sprint 2: Workspace & File System
- [ ] Create/delete workspace, CRUD files, rename/move
- [ ] Git init, clone (public repo), commit, branch, status, diff all work
- [ ] WebSocket file change notifications delivered within 500ms
- [ ] Path traversal attacks return 403 (tested with 20+ attack vectors)
- [ ] **Demo**: Create workspace, clone a repo, edit files, commit changes

### Sprint 3: VS Code Integration
- [ ] code-server accessible at `/editor/` path
- [ ] Workspace files visible in code-server's file explorer
- [ ] Auth session shared (no re-login required)
- [ ] Custom extension loads on startup
- [ ] **Demo**: Click "Open in Editor" → full VS Code with project files

### Sprint 4: AI Code Completion
- [ ] Single-line completion works for Python and JavaScript
- [ ] P95 latency < 600ms (relaxed from plan's 400ms for local models)
- [ ] Cache reduces duplicate requests by >20%
- [ ] VS Code extension shows ghost text completions
- [ ] Completion can be accepted with Tab, dismissed with Esc
- [ ] **Demo**: Type code in VS Code, see inline suggestions appear

### Sprint 5: Repo Intelligence
- [ ] Index a 1000-file repo in < 60 seconds
- [ ] Semantic search returns relevant results for natural language queries
- [ ] @file and @function mentions resolve correctly
- [ ] Incremental re-index on file save (< 2s for single file)
- [ ] **Demo**: Ask "where is authentication handled?" → get relevant files

### Sprint 6: AI Chat-in-Editor + Diff
- [ ] Chat panel in VS Code sidebar sends/receives messages
- [ ] AI responses with code blocks can be applied as diffs
- [ ] Diff preview shows before/after with accept/reject buttons
- [ ] @mentions auto-complete file paths and symbols
- [ ] Multi-file changes shown as grouped diff
- [ ] **Demo**: Ask "add error handling to this function" → preview diff → apply

### Sprint 7: Autonomous Mode
- [ ] Natural language task → plan → implement → test flow works end-to-end
- [ ] Agent creates git branch, makes changes, presents for approval
- [ ] Approval merges to target branch; rejection rolls back
- [ ] Max 5 iteration loops (write → run → fix)
- [ ] SSE progress events stream to UI in real-time
- [ ] **Demo**: "Add a /health endpoint with version info" → agent does it autonomously

### Sprint 8: Project Rules
- [ ] `.ollamarules` file detected and parsed on workspace load
- [ ] Rules injected into all AI prompts for that workspace
- [ ] `.cursorrules` compatibility (basic parsing)
- [ ] Rules visible in settings UI
- [ ] **Demo**: Add rules file → AI responses follow project conventions

### Sprint 9: MCP Server
- [ ] SSE transport works with Claude Desktop as client
- [ ] At least 5 tools functional: chat, execute_code, read_file, write_file, search
- [ ] Session management handles connect/disconnect gracefully
- [ ] **Demo**: Connect Claude Desktop → use our local models through it

### Sprint 10: RAG Pipeline
- [ ] pgvector extension enabled, embeddings table created
- [ ] Full repo indexed with nomic-embed-text embeddings
- [ ] Retrieval returns top-5 relevant chunks for a query
- [ ] Incremental updates on file change (< 5s latency)
- [ ] **Demo**: Chat asks about codebase → gets context-aware answers

### Sprint 11: Arena Mode
- [ ] Same prompt sent to 2+ models simultaneously
- [ ] Side-by-side output display with timing/token metrics
- [ ] User can vote on preferred output
- [ ] **Demo**: Compare codellama vs deepseek-coder on same task

### Sprint 12: Multimodal
- [ ] Voice recording → transcription → code action works
- [ ] Image upload → llava analysis → UI code generation works
- [ ] **Demo**: Upload mockup screenshot → get React component

### Universal DoD (Every Sprint)
- [ ] All new code has type hints
- [ ] Test coverage for new code > 80%
- [ ] No new security vulnerabilities (bandit scan passes)
- [ ] API documentation auto-generated (FastAPI /docs updated)
- [ ] Migration runs forward and backward cleanly
- [ ] No regressions in existing features (full test suite passes)

---

## 6. Risk Register

| Sprint | #1 Risk | Likelihood | Impact | Mitigation |
|--------|---------|-----------|--------|------------|
| **1** | Docker-in-Docker doesn't work in deployment environments (K8s, shared hosting) | HIGH | HIGH | Design executor interface that can swap Docker for gVisor/Firecracker/Podman |
| **2** | Git operations hang on large repos or corrupt state | MEDIUM | HIGH | Timeout all git ops, use `--depth 1` by default, implement health checks |
| **3** | code-server version conflicts with our extension API version | MEDIUM | MEDIUM | Pin code-server version, maintain compatibility matrix |
| **4** | Local model latency too high for real-time completion (<400ms impossible with 7B+ models) | HIGH | CRITICAL | Accept higher latency for local, add "fast mode" with smaller models (1.5B-3B), make targets configurable |
| **5** | tree-sitter grammars crash on malformed code | MEDIUM | MEDIUM | Wrap all parsing in try/catch, fall back to regex-based extraction |
| **6** | LLM output doesn't reliably produce parseable diffs | HIGH | HIGH | Multiple output formats (JSON, unified diff, search/replace), retry with reformatting prompt |
| **7** | Autonomous agent infinite loops (write bad code → fail → write same bad code) | HIGH | HIGH | Strict iteration cap, diff-based loop detection, escalate to human after 3 failures |
| **8** | Low risk sprint | LOW | LOW | N/A |
| **9** | MCP spec changes (it's still evolving in 2025) | MEDIUM | MEDIUM | Pin to specific MCP SDK version, abstract protocol layer |
| **10** | Embedding quality with local models insufficient for good retrieval | HIGH | HIGH | Allow optional API-based embeddings (OpenAI), tune chunking strategy aggressively |
| **11** | Collaborative editing conflicts corrupt file state | HIGH | CRITICAL | **Cut CRDT from V1**, use simple lock-based editing instead |
| **12** | Whisper model too large for typical local hardware (requires ~4GB VRAM) | MEDIUM | LOW | Make it optional, offer API fallback, document hardware requirements |

---

## 7. Cut List (Ruthless)

### If We Must Ship in 4 Weeks (1 developer)

**KEEP (Core MVP):**
- Sprint 1: Code Execution (simplified — Python + JS only, no resource monitoring UI)
- Sprint 2: Workspace (simplified — no templates, basic git only: init/commit/diff)
- Sprint 4: AI Completion (backend only — no VS Code extension, web-only editor)
- Sprint 6: Chat + Diff (simplified — single-file diffs only, no @mentions)

**CUT ENTIRELY:**
- Sprint 3 (VS Code) → Use web-based code editor (Monaco) instead
- Sprint 5 (Repo Intelligence) → Defer to Phase 3
- Sprint 7 (Autonomous) → Defer to Phase 3
- Sprint 8 (Rules) → Hardcode conventions, add file-based rules later
- Sprint 9 (MCP) → Defer to Phase 3
- Sprint 10 (RAG) → Defer to Phase 3
- Sprint 11 (Arena) → Defer to Phase 3
- Sprint 12 (Multimodal) → Defer to Phase 3

### Absolute Minimum v0.1 Feature Set

```
1. Web-based code editor (Monaco) with file tree
2. Code execution (Python, JavaScript) with streaming output
3. AI inline completion (web editor only)
4. AI chat with code context (selected code → chat → apply suggestion)
5. Basic git: init, commit, diff, log
```

That's it. Everything else is enhancement. This ships in **4-5 weeks** with one focused developer.

### Phase 3 Backlog (Ordered by Value)

1. Autonomous agent mode (Sprint 7) — highest user demand
2. RAG pipeline (Sprint 10) — biggest quality improvement
3. MCP server (Sprint 9) — ecosystem play
4. VS Code extension (Sprint 3 + 4 extension parts) — power users
5. Repo intelligence (Sprint 5) — enables better completions
6. Arena mode (Sprint 11) — differentiator
7. Project rules (Sprint 8) — quality of life
8. Multimodal (Sprint 12) — experimental
9. Collaborative editing (Sprint 11 CRDT part) — V3 at earliest

---

## 8. Quality Gates

### Before Sprint 1 Starts (Week 0 — "Sprint 0")

**CI/CD Must-Haves:**
- [ ] GitHub Actions (or equivalent) pipeline: lint → test → build → deploy
- [ ] `pytest` running on every PR with coverage reporting
- [ ] `ruff` or `flake8` for Python linting
- [ ] `eslint` + `prettier` for frontend
- [ ] Docker image builds succeed on CI
- [ ] Database migration runs in CI (test database)
- [ ] Branch protection: no direct push to `main`

**This "Sprint 0" takes 2-3 days and is NON-NEGOTIABLE.**

### Code Review Cadence

| When | What | Who |
|------|------|-----|
| Every PR | Code review required (self-review if solo, but structured checklist) | Developer + automated checks |
| End of each sprint | Architecture review: does this still compose cleanly? | Lead dev |
| Sprint 4, 7, 10 | Security review: new attack surfaces | Security-minded reviewer |
| Sprint 4, 7 | Performance review: latency regressions? | Load test results |

### Performance Testing Schedule

| Sprint | What to Test | Tool | Threshold |
|--------|-------------|------|-----------|
| Sprint 1 | Container startup time | Custom benchmark | < 2s cold start |
| Sprint 4 | Completion latency | `locust` or `k6` | P95 < 600ms |
| Sprint 5 | Indexing throughput | Custom benchmark | 1000 files < 60s |
| Sprint 7 | Concurrent agent load | `k6` | 4 agents, no OOM |
| Sprint 10 | RAG query latency | Custom benchmark | P95 < 500ms |

### Security Audit Points

| After Sprint | Focus Area |
|-------------|-----------|
| Sprint 1 | Container escape, resource exhaustion |
| Sprint 2 | Path traversal, arbitrary file read/write |
| Sprint 4 | Prompt injection via code context |
| Sprint 7 | Agent privilege escalation, unintended file access |
| Sprint 9 | MCP authentication, session hijacking |

---

## 9. Developer Experience (DX) for Contributors

### Folder Structure Assessment

**Current state**: The proposed structure is **well-organized but deep**. The `features/` pattern with self-contained modules is correct. However:

**Problems for new contributors:**
1. **Too many nested `__init__.py` files** — Python packaging confusion for less experienced devs
2. **`utils/` vs `common/` vs `services/`** — the boundary is unclear (when does a util become a service?)
3. **Frontend lacks clear patterns** — no established component library, no design system docs
4. **VS Code extension is a completely different skill set** — most contributors won't touch it

**Recommendations:**
- Add a `CONTRIBUTING.md` with clear "where does this code go?" decision tree
- Create an `ARCHITECTURE.md` that explains the layering (routes → services → features → utils)
- Use `make` commands for common operations (`make test`, `make lint`, `make dev`, `make sprint1`)

### Onboarding Checklist (Must Exist Before Accepting PRs)

```markdown
# New Contributor Setup (must take < 30 minutes)

1. Clone repo
2. `cp src/.env.example src/.env`
3. `docker compose -f src/docker-compose.dev.yml up`
4. Verify: http://localhost:5173 shows dashboard
5. Verify: http://localhost:8000/docs shows API docs
6. Run tests: `docker compose exec backend pytest`
7. Read: ARCHITECTURE.md (5 min)
8. Read: CONTRIBUTING.md (5 min)
9. Pick an issue labeled "good-first-issue"
```

### Documentation Requirements Before Accepting External PRs

| Document | Purpose | Must Contain |
|----------|---------|--------------|
| `CONTRIBUTING.md` | How to contribute | Setup, coding standards, PR process, commit format |
| `ARCHITECTURE.md` | System design | Layer diagram, data flow, key decisions, module responsibilities |
| `API.md` (or /docs) | API reference | Auto-generated from FastAPI + manual examples |
| `SECURITY.md` | Security model | Threat model, trust boundaries, how to report vulnerabilities |
| `ADR/` folder | Decision records | Why Docker? Why pgvector? Why not ChromaDB? |

---

## 10. Executive Summary & Recommendation

### The Honest Assessment

This plan describes building a **simplified Cursor/Copilot clone**. The industry leaders have:
- Teams of 50-200 engineers
- Billions in funding
- Years of iteration

We're trying to do a local-first version with 1-3 developers. That's **realistic IF we ruthlessly scope.**

### My Recommendation

**Option A (Recommended): Ruthless MVP — Ship in 6 weeks**
- 1 developer, Sprints 1 + 2 + 4 (web only) + 6 (basic)
- No VS Code extension (use Monaco in web)
- No autonomous mode
- No RAG, no MCP
- Result: A self-hosted AI coding assistant with execution, completion, and chat

**Option B: Full Vision — Ship in 4 months**
- 3 developers, all 12 sprints (with cuts from Section 7)
- Cut: collaborative editing, voice-to-code, parallel agents
- Result: Competitive self-hosted alternative to Cursor

**Option C (What the plan implies): Solo dev, 6 weeks, all 12 sprints**
- This is **not possible**. It will result in 12 half-built features instead of 4 polished ones.

### Final Word

> "A shipped product with 4 solid features beats a demo with 12 broken ones."

The architecture in this plan is good. The feature prioritization is good. The timeline is fantasy. Adjust expectations, cut scope, and ship incrementally.

---

*Review complete. Ready to discuss any section in detail or help refine the sprint plan.*
