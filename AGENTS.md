# PROJECT KNOWLEDGE BASE

**Generated:** 2026-04-26
**Branch:** main

---

## OVERVIEW

Autonomous agent-driven system built around Ollama Dashboard.

System is designed to:

* operate with minimal human intervention
* self-debug, self-heal, and improve continuously
* manage models, infrastructure, and code through agents

Base system: Ollama Dashboard (Flask + Docker + Ollama API)
Extended with: multi-agent execution layer defined in `CLAUDE.md`

Reference implementation: 

---

## STRUCTURE

```
.
├── CLAUDE.md                # System brain (mandatory)
├── agents/                  # All agent definitions
│   ├── orchestrator.md
│   ├── code_agent.md
│   ├── debug_agent.md
│   ├── infra_agent.md
│   ├── model_agent.md
│   └── review_agent.md
├── .claude/                 # Runtime state + memory
│   ├── memory.md
│   ├── tasks.md
│   ├── state.json
│   └── logs/
├── app/                     # Flask backend
├── docker/                  # Deployment configs
├── conversations/           # Stored chat sessions
├── tests/                   # System + agent tests
└── main.py                  # Entry point
```

---

## SYSTEM MODEL

```
User Intent
   ↓
CLAUDE.md (rules + decision system)
   ↓
Orchestrator Agent
   ↓
Specialized Agents
   ↓
Execution Layer (Python / Docker / Ollama)
```

---

## WHERE TO LOOK

| Task                   | Location             | Notes                   |
| ---------------------- | -------------------- | ----------------------- |
| Modify system behavior | `CLAUDE.md`          | Source of truth         |
| Add new agent          | `agents/`            | One file per agent      |
| Add task               | `.claude/tasks.md`   | Input queue             |
| Debug failure          | `.claude/logs/`      | Execution logs          |
| Track system state     | `.claude/state.json` | Runtime status          |
| Persistent knowledge   | `.claude/memory.md`  | Learned behavior        |
| Backend logic          | `app/`               | Flask routes + services |
| Infra changes          | `docker/`            | Compose + deployment    |
| Conversations          | `conversations/`     | Stored sessions         |

---

## CONVENTIONS

### Naming

* Agents: `<role>_agent.md`
* Logs: timestamp-based
* Tasks: priority-tagged entries

### Task Format

```
[PRIORITY: HIGH]
Fix container restart loop
```

### Agent Rules

* One responsibility per agent
* No overlapping authority
* All actions must be logged
* All outputs must be validated

---

## QUALITY STANDARDS

System must maintain:

* zero unresolved critical errors
* all services healthy
* reproducible fixes
* minimal manual intervention

Priority order:

1. Stability
2. Correctness
3. Performance
4. Optimization

---

## AUTONOMOUS OPERATION RULES

Agents must:

* detect issues automatically
* attempt fixes before reporting
* validate all changes
* update memory after resolution

Agents must not:

* delete persistent data without explicit task
* introduce breaking changes without validation
* bypass CLAUDE.md rules

---

## FAILURE HANDLING

On failure:

1. Detect via logs or health checks
2. Reproduce issue
3. Apply minimal fix
4. Validate system state
5. Log result
6. Retry if necessary

If repeated failure:

* rollback last stable state
* escalate priority in tasks

---

## ANTI-PATTERNS

| Forbidden                    | Reason                 |
| ---------------------------- | ---------------------- |
| Manual fixes without logging | breaks auditability    |
| Large unvalidated changes    | risk of system failure |
| Ignoring CLAUDE.md           | violates system design |
| Silent failures              | prevents recovery      |
| Hardcoding configs           | reduces adaptability   |

---

## COMMANDS

```bash
# Start base system
ollama serve
python main.py

# Docker deployment
cd docker
docker compose up -d

# Run agent system
python agents/orchestrator.py

# View logs
tail -f .claude/logs/latest.log
```

---

## CI/CD (Recommended)

| Workflow     | Purpose                   |
| ------------ | ------------------------- |
| test         | validate agents + backend |
| lint         | enforce code standards    |
| deploy       | build and run containers  |
| health-check | verify system stability   |

---

## NOTES

* CLAUDE.md is the highest authority
* Agents must follow defined roles strictly
* System is designed for continuous execution
* Human role is limited to defining intent and constraints

---

## STABILITY CONDITION

System is considered stable when:

* no active errors
* all containers/services are healthy
* no high-priority tasks pending

If not stable:
system continues execution loop
