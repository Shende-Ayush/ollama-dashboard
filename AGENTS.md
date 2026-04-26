# PROJECT KNOWLEDGE BASE

**Generated:** 2026-04-26
**Branch:** main

---
## OVERVIEW
Autonomous agent-driven system built around Ollama Dashboard.
System is designed to:
* operate with minimal human intervention
* self-debug, self-heal, and continuously improve
* manage backend, frontend, database, and system behavior through a constrained agent set
Base system: Ollama Dashboard (Flask + Docker + Ollama API)
Extended with: multi-agent execution layer defined in `CLAUDE.md`
---

## ACTIVE AGENTS (FINAL SET)
```
.claude/agents/
├── orchestrator-agent.md   # Control plane (decision + routing)
├── debugger-agent.md       # Root-cause analysis + fixes
├── reviewer-agent.md       # Validation + quality gate
├── backend-engineer.md     # Backend systems + APIs
├── frontend-engineer.md    # UI + client logic
├── db-expert.md            # Database + queries
├── lead-developer.md       # Planning + integration
└── visionary-cto.md        # System design + direction
```
---

## SYSTEM MODEL
```
User Intent / Task
        ↓
CLAUDE.md (rules + execution logic)
        ↓
orchestrator-agent
        ↓
Task Routing

IF system issue:
    → debugger-agent
    → reviewer-agent (validation)

IF feature / build:
    → visionary-cto (architecture)
    → lead-developer (planning)
    → db-expert (data layer)
    → backend-engineer (APIs)
    → frontend-engineer (UI)
    → reviewer-agent (validation)

IF failure:
    → debugger-agent → fix → reviewer-agent
```
---

## STRUCTURE
```
.
├── CLAUDE.md                # System brain (highest authority)
├── .claude/
│   ├── agents/              # All agent definitions (ONLY source of behavior)
│   ├── memory.md            # Learned fixes + patterns
│   ├── tasks.md             # Task queue
│   ├── state.json           # Runtime state
│   └── logs/                # Execution logs
├── app/                     # Flask backend
├── docker/                  # Deployment configs
├── conversations/           # Stored sessions
├── tests/                   # Validation tests
└── main.py                  # Entry point
```
---

## AGENT RESPONSIBILITY MODEL
### orchestrator-agent
* controls execution loop
* reads tasks
* routes work to correct agents
* prevents conflicts
---

### visionary-cto
* defines architecture
* selects tech approach
* sets constraints
---

### lead-developer
* breaks work into modules
* assigns responsibilities
* ensures integration consistency
---

### db-expert
* owns schema, queries, indexing
* ensures performance + data integrity
---

### backend-engineer
* implements APIs + business logic
* integrates with DB (ONLY after schema defined)
---

### frontend-engineer
* builds UI + integrates APIs
* handles UX states
---

### debugger-agent
* investigates failures
* finds root cause
* applies minimal fixes
---

### reviewer-agent
* validates ALL outputs
* enforces quality + consistency
* blocks invalid implementations
---

## EXECUTION LOOP
1. Read `.claude/tasks.md`
2. Select highest priority task
3. orchestrator-agent decides execution path
### If BUILD task:
CTO → Lead → DB → Backend → Frontend → Review
### If BUG / FAILURE:
Debugger → Fix → Review
4. If FAIL → loop continues
5. If PASS → update memory
6. Move to next task
---

## WHERE TO LOOK
| Task                   | Location             | Notes                |
| ---------------------- | -------------------- | -------------------- |
| Modify system behavior | `CLAUDE.md`          | Source of truth      |
| Agent logic            | `.claude/agents/`    | One file per agent   |
| Task queue             | `.claude/tasks.md`   | Input                |
| Debug issues           | `.claude/logs/`      | Execution logs       |
| System state           | `.claude/state.json` | Runtime tracking     |
| Learned fixes          | `.claude/memory.md`  | Persistent knowledge |
| Backend code           | `app/`               | Flask services       |
| Infra config           | `docker/`            | Containers           |
---

## CONVENTIONS
### Naming
* Agents: `<role>-agent.md` (fixed)
* Logs: timestamp-based
* Tasks: priority-tagged
---

### Task Format
```
[PRIORITY: HIGH]
<clear actionable task>
```
---

### Agent Rules
* One responsibility per agent
* No cross-domain decisions
* All actions must be logged
* All outputs must go through reviewer-agent
---

## QUALITY STANDARDS
System must maintain:
* zero unresolved critical errors
* all services functional
* reproducible fixes
* no partial implementations
Priority:
1. Stability
2. Correctness
3. Performance
4. Optimization
---

## AUTONOMOUS OPERATION RULES

Agents must:
* detect issues via logs/tasks
* attempt fixes before escalation
* validate every change
* update memory after success
Agents must not:
* bypass orchestrator
* skip review phase
* introduce breaking changes
* modify system blindly
---

## FAILURE HANDLING
On failure:
1. Detect (logs / task)
2. Route to debugger-agent
3. Identify root cause
4. Apply minimal fix
5. Send to reviewer-agent
6. If PASS → log + memory
7. If FAIL → retry or escalate
---

## ANTI-PATTERNS
| Forbidden                   | Reason                 |
| --------------------------- | ---------------------- |
| Skipping orchestrator       | breaks system flow     |
| Direct fixes without review | introduces instability |
| Guess-based debugging       | unreliable fixes       |
| Large blind changes         | high failure risk      |
| Ignoring memory             | no learning            |
---

## COMMANDS
```bash
# Start base system
ollama serve
python main.py
# Run agent loop
python agents/orchestrator.py
# Docker deployment
cd docker
docker compose up -d
# View logs
tail -f .claude/logs/latest.log
```
---

## STABILITY CONDITION
System is stable when:
* no active errors
* all services responding
* no HIGH priority tasks pending
If not stable:
→ system continues execution loop
---

## FINAL RULE
CLAUDE.md overrides everything.
Agents do not interpret system behavior — they execute it.