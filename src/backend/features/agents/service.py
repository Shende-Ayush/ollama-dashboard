"""
Agents Framework — Service layer.

Multi-agent orchestration engine with specialized agent types,
execution tracking, and inter-agent communication.
"""
import asyncio
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.features.agents.models import AgentConfig, AgentExecution, AgentStep
from backend.features.agents.schemas import (
    AGENT_TYPES,
    AgentConfigResponse,
    AgentExecutionResponse,
    AgentStepResponse,
    CreateAgentRequest,
    OrchestrationResponse,
    UpdateAgentRequest,
)
from backend.services.ollama_client import OllamaClient
from backend.services.token_counter import token_counter

logger = logging.getLogger(__name__)



# ---------------------------------------------------------------------------
# Default agent system prompts
# ---------------------------------------------------------------------------
DEFAULT_SYSTEM_PROMPTS = {
    "backend_engineer": (
        "You are a senior backend engineer. You implement APIs, business logic, "
        "database queries, and service integrations. You write clean, efficient, "
        "well-tested code following SOLID principles. Always consider error handling, "
        "performance, and security."
    ),
    "frontend_engineer": (
        "You are a senior frontend engineer. You build responsive UIs, "
        "manage state, integrate APIs, and ensure great UX. You write clean "
        "React/TypeScript code with proper component architecture."
    ),
    "debugger": (
        "You are an expert debugger. You analyze errors, trace root causes, "
        "and suggest minimal safe fixes. You read logs, identify patterns, "
        "and never guess — you verify before acting."
    ),
    "security_auditor": (
        "You are a security expert. You identify vulnerabilities, review code "
        "for security issues, and recommend fixes. You consider OWASP top 10, "
        "injection attacks, and access control flaws."
    ),
    "devops": (
        "You are a DevOps engineer. You manage infrastructure, CI/CD pipelines, "
        "Docker containers, and deployments. You optimize for reliability, "
        "scalability, and observability."
    ),
    "testing": (
        "You are a QA engineer. You write comprehensive test cases, identify "
        "edge cases, and ensure code quality. You create unit, integration, "
        "and end-to-end tests with proper coverage."
    ),
    "performance": (
        "You are a performance engineer. You profile code, identify bottlenecks, "
        "optimize queries, and improve response times. You use metrics-driven "
        "approaches to measure improvements."
    ),
    "orchestrator": (
        "You are a task orchestrator. You break down complex tasks into subtasks, "
        "assign them to specialized agents, coordinate their work, and synthesize "
        "results into a cohesive output."
    ),
}



class AgentEngine:
    """
    Core agent execution engine.

    Handles single-agent execution with:
    - Iterative reasoning loops
    - Step tracking
    - Token counting
    - Error recovery
    """

    def __init__(self, ollama_client: OllamaClient | None = None) -> None:
        self.client = ollama_client or OllamaClient()

    async def execute_agent(
        self,
        agent: AgentConfig,
        task: str,
        context: dict[str, Any],
        session: AsyncSession,
    ) -> AgentExecution:
        """Execute a single agent on a task with iterative reasoning."""
        execution = AgentExecution(
            agent_id=agent.id,
            task=task,
            status="running",
            context_data=context,
            started_at=datetime.now(timezone.utc),
        )
        session.add(execution)
        await session.flush()

        total_tokens = 0
        start_time = time.time()

        try:
            messages = [
                {"role": "system", "content": agent.system_prompt},
                {"role": "user", "content": self._build_task_prompt(task, context)},
            ]

            for iteration in range(1, agent.max_iterations + 1):
                step_start = time.time()

                # Generate response
                response_text = ""
                async for token in self.client.chat_stream(
                    model=agent.model_name,
                    messages=messages,
                    options={"temperature": agent.temperature},
                ):
                    response_text += token

                step_tokens = token_counter.count_text(response_text)
                total_tokens += step_tokens
                step_duration = int((time.time() - step_start) * 1000)

                # Parse agent action from response
                action, reasoning = self._parse_agent_response(response_text)

                # Record step
                step = AgentStep(
                    execution_id=execution.id,
                    step_number=iteration,
                    action=action,
                    input_data={"messages_count": len(messages)},
                    output_data={"response_length": len(response_text)},
                    status="completed",
                    reasoning=reasoning,
                    tokens_used=step_tokens,
                    duration_ms=step_duration,
                )
                session.add(step)

                # Check if agent signals completion
                if self._is_task_complete(response_text):
                    execution.result = response_text
                    execution.status = "completed"
                    execution.iterations_used = iteration
                    break

                # Add response to conversation for next iteration
                messages.append({"role": "assistant", "content": response_text})
                messages.append({
                    "role": "user",
                    "content": "Continue. If the task is complete, say TASK_COMPLETE.",
                })
            else:
                # Max iterations reached
                execution.result = response_text
                execution.status = "completed"
                execution.iterations_used = agent.max_iterations

        except Exception as exc:
            logger.error("Agent execution failed: %s", exc)
            execution.status = "failed"
            execution.error = str(exc)

        execution.tokens_consumed = total_tokens
        execution.duration_ms = int((time.time() - start_time) * 1000)
        execution.completed_at = datetime.now(timezone.utc)

        await session.commit()
        await session.refresh(execution, ["steps", "agent"])
        return execution

    @staticmethod
    def _build_task_prompt(task: str, context: dict[str, Any]) -> str:
        """Build a structured task prompt with context."""
        parts = [f"## Task\n{task}"]
        if context:
            parts.append(f"\n## Context\n```json\n{json.dumps(context, indent=2)}\n```")
        parts.append(
            "\n## Instructions\n"
            "- Break this task into clear steps\n"
            "- Execute each step methodically\n"
            "- Show your reasoning\n"
            "- When finished, include TASK_COMPLETE in your response"
        )
        return "\n".join(parts)

    @staticmethod
    def _parse_agent_response(response: str) -> tuple[str, str]:
        """Parse action and reasoning from agent response."""
        # Try to find structured action
        action_match = re.search(r"(?:Action|Step):\s*(.+?)(?:\n|$)", response)
        action = action_match.group(1).strip() if action_match else "reasoning"

        # Extract reasoning
        reasoning_match = re.search(
            r"(?:Reasoning|Thought|Analysis):\s*(.+?)(?:\n\n|$)",
            response, re.DOTALL
        )
        reasoning = reasoning_match.group(1).strip() if reasoning_match else response[:500]

        return action, reasoning

    @staticmethod
    def _is_task_complete(response: str) -> bool:
        """Check if agent signals task completion."""
        completion_markers = ["TASK_COMPLETE", "task complete", "done", "finished"]
        response_lower = response.lower()
        return any(marker.lower() in response_lower for marker in completion_markers)



class AgentOrchestratorService:
    """
    Multi-agent orchestration service.

    Manages agent lifecycle, execution strategies, and coordination.
    Supports: sequential, parallel, and pipeline execution modes.
    """

    def __init__(self, ollama_client: OllamaClient | None = None) -> None:
        self.client = ollama_client or OllamaClient()
        self.engine = AgentEngine(self.client)

    # -----------------------------------------------------------------------
    # Agent CRUD
    # -----------------------------------------------------------------------
    async def create_agent(
        self, request: CreateAgentRequest, session: AsyncSession
    ) -> AgentConfigResponse:
        """Create a new agent configuration."""
        if request.agent_type not in AGENT_TYPES:
            raise ValueError(
                f"Invalid agent type '{request.agent_type}'. "
                f"Must be one of: {AGENT_TYPES}"
            )

        agent = AgentConfig(
            name=request.name,
            agent_type=request.agent_type,
            description=request.description,
            system_prompt=request.system_prompt,
            capabilities=request.capabilities,
            model_name=request.model_name,
            max_iterations=request.max_iterations,
            temperature=request.temperature,
        )
        session.add(agent)
        await session.commit()
        await session.refresh(agent)
        return self._agent_to_response(agent)

    async def get_agent(
        self, agent_id: str, session: AsyncSession
    ) -> AgentConfigResponse:
        """Get an agent configuration by ID."""
        agent = await session.get(AgentConfig, uuid.UUID(agent_id))
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        return self._agent_to_response(agent)

    async def list_agents(
        self,
        session: AsyncSession,
        agent_type: Optional[str] = None,
        active_only: bool = True,
    ) -> list[AgentConfigResponse]:
        """List all agent configurations."""
        stmt = select(AgentConfig).order_by(AgentConfig.name)
        if agent_type:
            stmt = stmt.where(AgentConfig.agent_type == agent_type)
        if active_only:
            stmt = stmt.where(AgentConfig.is_active == True)  # noqa: E712
        result = await session.execute(stmt)
        return [self._agent_to_response(a) for a in result.scalars().all()]

    async def update_agent(
        self, agent_id: str, request: UpdateAgentRequest, session: AsyncSession
    ) -> AgentConfigResponse:
        """Update an agent configuration."""
        agent = await session.get(AgentConfig, uuid.UUID(agent_id))
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        if request.name is not None:
            agent.name = request.name
        if request.description is not None:
            agent.description = request.description
        if request.system_prompt is not None:
            agent.system_prompt = request.system_prompt
        if request.capabilities is not None:
            agent.capabilities = request.capabilities
        if request.model_name is not None:
            agent.model_name = request.model_name
        if request.max_iterations is not None:
            agent.max_iterations = request.max_iterations
        if request.temperature is not None:
            agent.temperature = request.temperature
        if request.is_active is not None:
            agent.is_active = request.is_active

        agent.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(agent)
        return self._agent_to_response(agent)

    async def delete_agent(
        self, agent_id: str, session: AsyncSession
    ) -> None:
        """Delete an agent configuration."""
        agent = await session.get(AgentConfig, uuid.UUID(agent_id))
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        await session.delete(agent)
        await session.commit()


    # -----------------------------------------------------------------------
    # Agent execution
    # -----------------------------------------------------------------------
    async def execute(
        self,
        agent_id: str,
        task: str,
        context: dict[str, Any],
        session: AsyncSession,
    ) -> AgentExecutionResponse:
        """Execute a single agent on a task."""
        agent = await session.get(AgentConfig, uuid.UUID(agent_id))
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        if not agent.is_active:
            raise ValueError(f"Agent '{agent.name}' is not active")

        execution = await self.engine.execute_agent(agent, task, context, session)
        return self._execution_to_response(execution)

    async def orchestrate(
        self,
        task: str,
        agent_ids: list[str],
        strategy: str,
        context: dict[str, Any],
        session: AsyncSession,
    ) -> OrchestrationResponse:
        """Orchestrate multiple agents to complete a task."""
        # Resolve agents
        if agent_ids:
            agents = []
            for aid in agent_ids:
                agent = await session.get(AgentConfig, uuid.UUID(aid))
                if agent and agent.is_active:
                    agents.append(agent)
        else:
            # Auto-select based on task keywords
            agents = await self._auto_select_agents(task, session)

        if not agents:
            raise ValueError("No active agents available for this task")

        executions: list[AgentExecution] = []

        if strategy == "parallel":
            executions = await self._run_parallel(agents, task, context, session)
        elif strategy == "pipeline":
            executions = await self._run_pipeline(agents, task, context, session)
        else:  # sequential (default)
            executions = await self._run_sequential(agents, task, context, session)

        # Synthesize final result
        total_tokens = sum(e.tokens_consumed for e in executions)
        total_duration = sum(e.duration_ms for e in executions)
        final_result = self._synthesize_results(executions)
        all_completed = all(e.status == "completed" for e in executions)

        return OrchestrationResponse(
            task=task,
            strategy=strategy,
            executions=[self._execution_to_response(e) for e in executions],
            final_result=final_result,
            total_tokens=total_tokens,
            total_duration_ms=total_duration,
            status="completed" if all_completed else "partial",
        )

    async def _run_sequential(
        self,
        agents: list[AgentConfig],
        task: str,
        context: dict[str, Any],
        session: AsyncSession,
    ) -> list[AgentExecution]:
        """Run agents sequentially, passing output as context to next."""
        executions = []
        running_context = dict(context)

        for agent in agents:
            execution = await self.engine.execute_agent(
                agent, task, running_context, session
            )
            executions.append(execution)

            # Pass result as context to next agent
            if execution.result:
                running_context[f"{agent.agent_type}_output"] = execution.result[:2000]

        return executions

    async def _run_parallel(
        self,
        agents: list[AgentConfig],
        task: str,
        context: dict[str, Any],
        session: AsyncSession,
    ) -> list[AgentExecution]:
        """Run agents in parallel (each gets same context)."""
        # Note: With async SQLAlchemy we execute sequentially but independently
        executions = []
        for agent in agents:
            execution = await self.engine.execute_agent(
                agent, task, context, session
            )
            executions.append(execution)
        return executions

    async def _run_pipeline(
        self,
        agents: list[AgentConfig],
        task: str,
        context: dict[str, Any],
        session: AsyncSession,
    ) -> list[AgentExecution]:
        """Run agents in pipeline: each transforms the task for the next."""
        executions = []
        current_task = task

        for agent in agents:
            execution = await self.engine.execute_agent(
                agent, current_task, context, session
            )
            executions.append(execution)

            # Next agent works on the output of the previous
            if execution.result:
                current_task = (
                    f"Previous agent ({agent.name}) produced:\n"
                    f"{execution.result[:3000]}\n\n"
                    f"Original task: {task}\n"
                    f"Continue or refine this work."
                )

        return executions


    # -----------------------------------------------------------------------
    # Execution history
    # -----------------------------------------------------------------------
    async def get_execution(
        self, execution_id: str, session: AsyncSession
    ) -> AgentExecutionResponse:
        """Get an execution by ID with steps."""
        result = await session.execute(
            select(AgentExecution)
            .options(selectinload(AgentExecution.steps), selectinload(AgentExecution.agent))
            .where(AgentExecution.id == uuid.UUID(execution_id))
        )
        execution = result.scalar_one_or_none()
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")
        return self._execution_to_response(execution)

    async def list_executions(
        self,
        session: AsyncSession,
        agent_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> list[AgentExecutionResponse]:
        """List executions with optional filtering."""
        stmt = (
            select(AgentExecution)
            .options(selectinload(AgentExecution.agent))
            .order_by(AgentExecution.created_at.desc())
            .limit(limit)
        )
        if agent_id:
            stmt = stmt.where(AgentExecution.agent_id == uuid.UUID(agent_id))
        if status:
            stmt = stmt.where(AgentExecution.status == status)

        result = await session.execute(stmt)
        return [
            self._execution_to_response(e) for e in result.scalars().all()
        ]

    # -----------------------------------------------------------------------
    # Auto-selection
    # -----------------------------------------------------------------------
    async def _auto_select_agents(
        self, task: str, session: AsyncSession
    ) -> list[AgentConfig]:
        """Automatically select agents based on task keywords."""
        task_lower = task.lower()
        selected_types = set()

        type_keywords = {
            "backend_engineer": ["api", "endpoint", "database", "query", "backend", "server"],
            "frontend_engineer": ["ui", "component", "react", "frontend", "page", "css"],
            "debugger": ["bug", "error", "fix", "debug", "crash", "issue"],
            "security_auditor": ["security", "vulnerability", "auth", "injection", "xss"],
            "devops": ["deploy", "docker", "ci/cd", "infrastructure", "kubernetes"],
            "testing": ["test", "coverage", "qa", "assert", "mock"],
            "performance": ["performance", "optimize", "slow", "latency", "bottleneck"],
        }

        for agent_type, keywords in type_keywords.items():
            if any(kw in task_lower for kw in keywords):
                selected_types.add(agent_type)

        if not selected_types:
            selected_types = {"backend_engineer"}

        stmt = (
            select(AgentConfig)
            .where(
                AgentConfig.agent_type.in_(list(selected_types)),
                AgentConfig.is_active == True,  # noqa: E712
            )
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # Utilities
    # -----------------------------------------------------------------------
    @staticmethod
    def _synthesize_results(executions: list[AgentExecution]) -> str:
        """Synthesize results from multiple agent executions."""
        parts = []
        for ex in executions:
            status = "completed" if ex.status == "completed" else f"failed: {ex.error}"
            result_preview = (ex.result or "")[:500]
            parts.append(
                f"## Agent: {ex.agent.name if ex.agent else 'Unknown'}\n"
                f"Status: {status}\n"
                f"Result: {result_preview}\n"
            )
        return "\n---\n".join(parts)

    @staticmethod
    def _agent_to_response(agent: AgentConfig) -> AgentConfigResponse:
        return AgentConfigResponse(
            id=str(agent.id),
            name=agent.name,
            agent_type=agent.agent_type,
            description=agent.description,
            system_prompt=agent.system_prompt,
            capabilities=agent.capabilities,
            model_name=agent.model_name,
            max_iterations=agent.max_iterations,
            temperature=agent.temperature,
            is_active=agent.is_active,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )

    @staticmethod
    def _execution_to_response(execution: AgentExecution) -> AgentExecutionResponse:
        steps = []
        if hasattr(execution, "steps") and execution.steps:
            steps = [
                AgentStepResponse(
                    id=str(s.id),
                    step_number=s.step_number,
                    action=s.action,
                    input_data=s.input_data,
                    output_data=s.output_data,
                    status=s.status,
                    reasoning=s.reasoning,
                    tokens_used=s.tokens_used,
                    duration_ms=s.duration_ms,
                    created_at=s.created_at,
                )
                for s in sorted(execution.steps, key=lambda x: x.step_number)
            ]

        return AgentExecutionResponse(
            id=str(execution.id),
            agent_id=str(execution.agent_id),
            agent_name=execution.agent.name if execution.agent else "Unknown",
            task=execution.task,
            status=execution.status,
            result=execution.result,
            error=execution.error,
            iterations_used=execution.iterations_used,
            tokens_consumed=execution.tokens_consumed,
            duration_ms=execution.duration_ms,
            steps=steps,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            created_at=execution.created_at,
        )


# Module singleton
agent_service = AgentOrchestratorService()
