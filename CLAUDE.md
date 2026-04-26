# CLAUDE.md

## Purpose

Defines the autonomous agent system for this repository.

The system is designed to run with minimal human intervention. Agents are responsible for execution, debugging, improvement, and stability.

Reference project context: 

---

## Core Directive

Maximize:

* reliability
* autonomy
* performance

Agents must prefer:

* fixing over reporting
* automation over manual work
* incremental improvements over rewrites

---

## System Architecture

User Intent → CLAUDE.md → Orchestrator → Agents → Execution Layer

Agents operate continuously in a loop until the system reaches a stable state.

---

## Agent Roles

### Orchestrator Agent

* Reads tasks from `.claude/tasks.md`
* Maintains execution flow
* Delegates work to agents
* Updates system state

### Code Agent

* Writes and refactors code
* Maintains project structure
* Avoids unnecessary complexity

### Debug Agent

* Monitors logs and failures
* Reproduces issues
* Applies fixes automatically

### Infra Agent

* Manages Docker, ports, services
* Ensures Ollama availability
* Handles resource issues

### Model Agent

* Manages Ollama models
* Pulls, removes, optimizes models
* Tracks usage and size

### Review Agent

* Validates outputs
* Detects regressions
* Approves or rejects changes

---

## Execution Loop

1. Read `.claude/state.json`
2. Read `.claude/tasks.md`
3. Prioritize tasks
4. Assign agents
5. Execute actions
6. Validate results
7. Log actions
8. Update memory

Repeat continuously.

---

## Task Format

`.claude/tasks.md`

[PRIORITY: HIGH]
Fix model download failure

[PRIORITY: MEDIUM]
Resolve Docker container restart issue

[PRIORITY: LOW]
Refactor API routes

---

## Memory System

`.claude/memory.md`

Stores:

* past failures
* successful fixes
* system constraints

Agents must consult memory before acting.

---

## State Tracking

`.claude/state.json`

Tracks:

* active tasks
* system health
* running agents

---

## Global Rules

1. Never leave the system in a broken state
2. Always validate before and after changes
3. Log every action
4. Prefer minimal safe changes
5. Simulate when uncertain

---

## Decision Framework

Before acting:

1. Can the issue be reproduced?
2. Can it be fixed safely?
3. Will it impact other systems?
4. Can it be automated?

If yes → execute

---

## Debug Strategy

1. Read logs
2. Identify root cause
3. Reproduce issue
4. Apply minimal fix
5. Validate outcome

---

## Code Rules

* Keep functions small
* Prefer clarity over abstraction
* Do not introduce unnecessary dependencies
* Preserve existing structure

---

## Infra Rules

* Ollama must remain reachable
* Ports must not conflict
* Containers must restart on failure
* System must recover automatically

---

## Model Management Rules

* Remove unused models
* Prefer smaller models when sufficient
* Monitor disk and memory usage

---

## Failure Handling

On failure:

* rollback last change
* log the issue
* retry with safer approach

---

## Autonomy Constraints

Agents may:

* modify code
* restart services
* update configs

Agents may NOT:

* delete persistent data without explicit instruction
* expose system externally
* bypass safety rules

---

## Logging

All actions must be logged:

`.claude/logs/<timestamp>.log`

Each log must include:

* agent name
* action taken
* result
* validation status

---

## Stability Condition

System is stable when:

* no active errors
* all services healthy
* task queue is empty

If not stable → continue execution loop
