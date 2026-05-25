"""
Smart Command Center — Service layer.

Handles AI-powered command generation, error analysis, and autocomplete.
Uses Ollama models for inference with proper fallback mechanisms.
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.features.smart_commands.models import (
    CommandContext,
    CommandErrorAnalysis,
    CommandSuggestion,
)
from backend.features.smart_commands.schemas import (
    AutocompleteItem,
    CommandExplanation,
    CommandSuggestionResponse,
    ErrorAnalysisResponse,
    NaturalLanguageCommandResponse,
    SmartAutocompleteResponse,
)
from backend.services.command_guard import validate_command
from backend.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Known command catalog for autocomplete
# ---------------------------------------------------------------------------
OLLAMA_COMMANDS = [
    {"cmd": "ollama ps", "desc": "List running models", "category": "status"},
    {"cmd": "ollama list", "desc": "List installed models", "category": "status"},
    {"cmd": "ollama version", "desc": "Show Ollama version", "category": "status"},
    {"cmd": "ollama pull", "desc": "Download a model", "category": "model"},
    {"cmd": "ollama rm", "desc": "Remove a model", "category": "model"},
    {"cmd": "ollama show", "desc": "Show model details", "category": "model"},
    {"cmd": "ollama stop", "desc": "Unload model from memory", "category": "model"},
]

POPULAR_MODELS = [
    "llama3.2:3b", "llama3.2:1b", "llama3.1:8b", "llama3.1:70b",
    "mistral:7b", "mistral:latest", "mixtral:8x7b",
    "qwen2.5:7b", "qwen2.5:14b", "qwen2.5:72b",
    "deepseek-r1:7b", "deepseek-r1:14b",
    "phi4:latest", "phi3:mini",
    "gemma3:4b", "gemma3:12b",
    "codellama:7b", "codellama:13b",
    "nomic-embed-text", "mxbai-embed-large",
]

# Severity classification keywords
SEVERITY_KEYWORDS = {
    "critical": ["corrupt", "data loss", "unrecoverable", "fatal", "segfault"],
    "high": ["connection refused", "permission denied", "out of memory", "disk full"],
    "medium": ["timeout", "not found", "invalid", "failed"],
    "low": ["warning", "deprecated", "slow"],
}


class SmartCommandService:
    """
    AI-powered command intelligence service.

    Provides:
    - Natural language → command conversion
    - Command explanation in plain English
    - Error analysis with fix suggestions
    - Context-aware autocomplete
    """

    def __init__(self, ollama_client: OllamaClient | None = None) -> None:
        self.client = ollama_client or OllamaClient()
        self._default_model = "llama3.2:3b"

    async def _get_available_model(self) -> str:
        """Get the best available model for command intelligence."""
        try:
            models = await self.client.list_models()
            model_names = [m.get("name", "") for m in models]

            # Prefer smaller, faster models for command tasks
            preferred = ["llama3.2:3b", "llama3.2:1b", "phi4:latest", "mistral:7b", "qwen2.5:7b"]
            for pref in preferred:
                if pref in model_names:
                    return pref

            # Fallback to any available model
            if model_names:
                return model_names[0]
        except Exception as exc:
            logger.warning("Could not query Ollama for models: %s", exc)

        return self._default_model

    async def _generate_response(self, prompt: str, model: str | None = None) -> str:
        """Generate a response from Ollama for command intelligence tasks."""
        model = model or await self._get_available_model()
        response_text = ""

        try:
            messages = [{"role": "user", "content": prompt}]
            async for token in self.client.chat_stream(model=model, messages=messages):
                response_text += token
        except Exception as exc:
            logger.error("Ollama generation failed: %s", exc)
            raise

        return response_text.strip()

    # ---------------------------------------------------------------------------
    # Natural language → Command
    # ---------------------------------------------------------------------------
    async def natural_language_to_command(
        self,
        intent: str,
        context: Optional[str],
        session: AsyncSession,
    ) -> NaturalLanguageCommandResponse:
        """Convert natural language intent to Ollama commands."""
        model = await self._get_available_model()

        prompt = f"""You are an Ollama CLI expert. Convert the user's intent into valid Ollama commands.

User intent: "{intent}"
{f'Context: {context}' if context else ''}

Available Ollama commands:
- ollama pull <model> — Download a model
- ollama rm <model> — Remove a model
- ollama ps — List running models
- ollama list — List installed models
- ollama show <model> — Show model info
- ollama stop <model> — Unload from memory
- ollama version — Show version

Popular models: {', '.join(POPULAR_MODELS[:10])}

Respond in JSON format:
{{
  "suggestions": [
    {{"command": "ollama <cmd>", "explanation": "...", "confidence": 0.95, "warnings": []}}
  ],
  "intent_understood": "Brief summary of what user wants"
}}

Provide 1-3 suggestions ranked by relevance. Only suggest valid Ollama commands."""

        try:
            raw_response = await self._generate_response(prompt, model)
            parsed = self._parse_json_response(raw_response)

            suggestions = []
            for s in parsed.get("suggestions", []):
                cmd = s.get("command", "")
                is_safe = validate_command(cmd)
                suggestions.append(CommandSuggestionResponse(
                    suggested_command=cmd,
                    explanation=s.get("explanation", ""),
                    confidence=min(1.0, max(0.0, float(s.get("confidence", 0.7)))),
                    is_safe=is_safe,
                    warnings=s.get("warnings", []) + (["Command not in allowlist"] if not is_safe else []),
                ))

            # Store in DB
            for suggestion in suggestions:
                session.add(CommandSuggestion(
                    user_input=intent,
                    suggested_command=suggestion.suggested_command,
                    explanation=suggestion.explanation,
                    confidence=suggestion.confidence,
                    model_used=model,
                ))
            await session.commit()

            return NaturalLanguageCommandResponse(
                suggestions=suggestions,
                intent_understood=parsed.get("intent_understood", intent),
                model_used=model,
            )

        except Exception as exc:
            logger.error("Natural language command generation failed: %s", exc)
            # Fallback: pattern matching
            return self._fallback_command_generation(intent, model)

    def _fallback_command_generation(self, intent: str, model: str) -> NaturalLanguageCommandResponse:
        """Rule-based fallback when AI is unavailable."""
        intent_lower = intent.lower()
        suggestions = []

        if any(w in intent_lower for w in ["install", "download", "pull", "get"]):
            # Try to extract model name
            for m in POPULAR_MODELS:
                if m.split(":")[0].lower() in intent_lower or m.split(":")[0].split("-")[0] in intent_lower:
                    suggestions.append(CommandSuggestionResponse(
                        suggested_command=f"ollama pull {m}",
                        explanation=f"Download {m} model",
                        confidence=0.7,
                        is_safe=True,
                        warnings=[],
                    ))
                    break

        if any(w in intent_lower for w in ["remove", "delete", "uninstall"]):
            suggestions.append(CommandSuggestionResponse(
                suggested_command="ollama rm <model_name>",
                explanation="Remove a model (replace <model_name> with actual name)",
                confidence=0.5,
                is_safe=False,
                warnings=["Replace <model_name> with the model to remove"],
            ))

        if any(w in intent_lower for w in ["running", "active", "loaded", "status"]):
            suggestions.append(CommandSuggestionResponse(
                suggested_command="ollama ps",
                explanation="Show currently running/loaded models",
                confidence=0.9,
                is_safe=True,
                warnings=[],
            ))

        if any(w in intent_lower for w in ["list", "installed", "available"]):
            suggestions.append(CommandSuggestionResponse(
                suggested_command="ollama list",
                explanation="List all installed models",
                confidence=0.9,
                is_safe=True,
                warnings=[],
            ))

        if not suggestions:
            suggestions.append(CommandSuggestionResponse(
                suggested_command="ollama list",
                explanation="List installed models (could not understand specific intent)",
                confidence=0.3,
                is_safe=True,
                warnings=["Could not fully understand intent — showing default"],
            ))

        return NaturalLanguageCommandResponse(
            suggestions=suggestions,
            intent_understood=intent,
            model_used=f"{model} (fallback)",
        )

    # ---------------------------------------------------------------------------
    # Command explanation
    # ---------------------------------------------------------------------------
    async def explain_command(self, command: str) -> CommandExplanation:
        """Explain an Ollama command in plain English."""
        model = await self._get_available_model()

        prompt = f"""Explain this Ollama command in plain English:

Command: {command}

Respond in JSON:
{{
  "summary": "One-line summary",
  "detailed_explanation": "Full explanation of what this does",
  "parameters": [{{"name": "param", "description": "what it does"}}],
  "side_effects": ["list of side effects"],
  "safety_level": "safe|caution|dangerous"
}}"""

        try:
            raw = await self._generate_response(prompt, model)
            parsed = self._parse_json_response(raw)

            return CommandExplanation(
                command=command,
                summary=parsed.get("summary", "Ollama command"),
                detailed_explanation=parsed.get("detailed_explanation", ""),
                parameters=parsed.get("parameters", []),
                side_effects=parsed.get("side_effects", []),
                safety_level=parsed.get("safety_level", "safe"),
            )
        except Exception:
            # Fallback with known command info
            return self._fallback_explain(command)

    def _fallback_explain(self, command: str) -> CommandExplanation:
        """Rule-based command explanation fallback."""
        parts = command.strip().split()
        action = parts[1] if len(parts) > 1 else ""
        arg = parts[2] if len(parts) > 2 else ""

        explanations = {
            "ps": ("List running models", "Shows all models currently loaded in memory with GPU/CPU allocation details.", "safe"),
            "list": ("List installed models", "Shows all models downloaded to your local machine with sizes.", "safe"),
            "version": ("Show version", "Displays the installed Ollama version.", "safe"),
            "pull": (f"Download model {arg}", f"Downloads the '{arg}' model from the Ollama registry to your machine.", "safe"),
            "show": (f"Show model info for {arg}", f"Displays detailed information about '{arg}' including parameters, template, and license.", "safe"),
            "rm": (f"Remove model {arg}", f"Permanently deletes the '{arg}' model from local storage. This frees disk space but you'll need to re-download if needed later.", "caution"),
            "stop": (f"Unload {arg}", f"Removes '{arg}' from GPU/CPU memory. The model stays installed but won't use resources until loaded again.", "safe"),
        }

        info = explanations.get(action, ("Unknown command", "Command not recognized.", "caution"))

        return CommandExplanation(
            command=command,
            summary=info[0],
            detailed_explanation=info[1],
            parameters=[{"name": arg, "description": "Model name"}] if arg else [],
            side_effects=["Frees disk space" if action == "rm" else "Frees GPU memory" if action == "stop" else "No significant side effects"],
            safety_level=info[2],
        )

    # ---------------------------------------------------------------------------
    # Error analysis
    # ---------------------------------------------------------------------------
    async def analyze_error(
        self,
        command: str,
        error_output: str,
        system_context: Optional[dict],
        session: AsyncSession,
    ) -> ErrorAnalysisResponse:
        """Analyze a command error and suggest fixes."""
        model = await self._get_available_model()
        severity = self._classify_severity(error_output)

        prompt = f"""You are an Ollama troubleshooting expert. Analyze this error and suggest a fix.

Command: {command}
Error output: {error_output}
{f'System context: {json.dumps(system_context)}' if system_context else ''}

Respond in JSON:
{{
  "root_cause": "What caused this error",
  "suggested_fix": "How to fix it",
  "fix_command": "ollama command to fix (or null if manual fix needed)",
  "auto_fixable": true/false
}}"""

        try:
            raw = await self._generate_response(prompt, model)
            parsed = self._parse_json_response(raw)

            fix_command = parsed.get("fix_command")
            auto_fixable = parsed.get("auto_fixable", False)

            # Validate fix command safety
            if fix_command and not validate_command(fix_command):
                fix_command = None
                auto_fixable = False

            analysis = CommandErrorAnalysis(
                command=command,
                error_output=error_output[:5000],
                root_cause=parsed.get("root_cause", "Unknown"),
                suggested_fix=parsed.get("suggested_fix", "Check Ollama logs"),
                fix_command=fix_command,
                severity=severity,
                auto_fixable=auto_fixable,
                model_used=model,
            )
            session.add(analysis)
            await session.commit()
            await session.refresh(analysis)

            return ErrorAnalysisResponse(
                id=str(analysis.id),
                command=command,
                root_cause=analysis.root_cause,
                suggested_fix=analysis.suggested_fix,
                fix_command=analysis.fix_command,
                severity=severity,
                auto_fixable=auto_fixable,
                additional_context=f"Analyzed by {model}",
            )

        except Exception as exc:
            logger.error("Error analysis failed: %s", exc)
            return self._fallback_error_analysis(command, error_output, severity)

    def _classify_severity(self, error_output: str) -> str:
        """Classify error severity based on keywords."""
        error_lower = error_output.lower()
        for severity, keywords in SEVERITY_KEYWORDS.items():
            if any(kw in error_lower for kw in keywords):
                return severity
        return "medium"

    def _fallback_error_analysis(self, command: str, error_output: str, severity: str) -> ErrorAnalysisResponse:
        """Rule-based error analysis fallback."""
        error_lower = error_output.lower()

        if "connection refused" in error_lower:
            return ErrorAnalysisResponse(
                id="fallback",
                command=command,
                root_cause="Ollama service is not running or not accessible",
                suggested_fix="Start the Ollama service: ensure the Ollama container/process is running",
                fix_command=None,
                severity="high",
                auto_fixable=False,
                additional_context="Fallback analysis — Ollama AI unavailable",
            )

        if "not found" in error_lower or "404" in error_lower:
            return ErrorAnalysisResponse(
                id="fallback",
                command=command,
                root_cause="The specified model or resource was not found",
                suggested_fix="Verify the model name exists in the Ollama registry (ollama.com/library)",
                fix_command="ollama list",
                severity="medium",
                auto_fixable=False,
                additional_context="Fallback analysis",
            )

        if "out of memory" in error_lower or "oom" in error_lower:
            return ErrorAnalysisResponse(
                id="fallback",
                command=command,
                root_cause="Insufficient GPU/system memory for the requested operation",
                suggested_fix="Unload other models or use a smaller quantization",
                fix_command="ollama ps",
                severity="high",
                auto_fixable=False,
                additional_context="Fallback analysis",
            )

        return ErrorAnalysisResponse(
            id="fallback",
            command=command,
            root_cause="Unidentified error occurred during command execution",
            suggested_fix="Check Ollama logs for more details. Try restarting the Ollama service.",
            fix_command=None,
            severity=severity,
            auto_fixable=False,
            additional_context="Fallback analysis — could not determine specific issue",
        )

    # ---------------------------------------------------------------------------
    # Smart autocomplete
    # ---------------------------------------------------------------------------
    async def get_autocomplete(
        self,
        partial_input: str,
        session: AsyncSession,
    ) -> SmartAutocompleteResponse:
        """Get context-aware autocomplete suggestions."""
        partial_lower = partial_input.lower().strip()
        items: list[AutocompleteItem] = []

        # 1. Match against known commands
        for cmd_info in OLLAMA_COMMANDS:
            cmd = cmd_info["cmd"]
            if cmd.startswith(partial_lower) or partial_lower in cmd:
                items.append(AutocompleteItem(
                    completion=cmd,
                    description=cmd_info["desc"],
                    category="command",
                    score=0.9 if cmd.startswith(partial_lower) else 0.6,
                ))

        # 2. If partial matches a model-arg command, suggest models
        model_cmd_prefixes = ["ollama pull ", "ollama rm ", "ollama show ", "ollama stop "]
        for prefix in model_cmd_prefixes:
            if partial_lower.startswith(prefix):
                model_partial = partial_lower[len(prefix):]
                for model in POPULAR_MODELS:
                    if model_partial in model.lower():
                        items.append(AutocompleteItem(
                            completion=f"{prefix.strip()} {model}",
                            description=f"Model: {model}",
                            category="model",
                            score=0.85 if model.lower().startswith(model_partial) else 0.5,
                        ))

        # 3. Check command history for patterns
        try:
            result = await session.execute(
                select(CommandContext)
                .where(CommandContext.command_pattern.ilike(f"%{partial_lower}%"))
                .order_by(CommandContext.frequency.desc())
                .limit(5)
            )
            for ctx in result.scalars().all():
                items.append(AutocompleteItem(
                    completion=ctx.command_pattern,
                    description=f"Used {ctx.frequency}x",
                    category="history",
                    score=min(0.8, 0.4 + (ctx.frequency * 0.1)),
                ))
        except Exception as exc:
            logger.debug("History autocomplete failed: %s", exc)

        # Sort by score, deduplicate, limit
        seen = set()
        unique_items = []
        for item in sorted(items, key=lambda x: x.score, reverse=True):
            if item.completion not in seen:
                seen.add(item.completion)
                unique_items.append(item)
            if len(unique_items) >= 10:
                break

        return SmartAutocompleteResponse(items=unique_items, partial_input=partial_input)

    # ---------------------------------------------------------------------------
    # Track command usage for autocomplete context
    # ---------------------------------------------------------------------------
    async def track_command_usage(self, command: str, session: AsyncSession) -> None:
        """Update command frequency tracking for autocomplete improvement."""
        try:
            result = await session.execute(
                select(CommandContext).where(CommandContext.command_pattern == command)
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.frequency += 1
                existing.last_used_at = datetime.now(timezone.utc)
            else:
                session.add(CommandContext(
                    command_pattern=command,
                    frequency=1,
                    last_used_at=datetime.now(timezone.utc),
                ))
            await session.commit()
        except Exception as exc:
            logger.debug("Failed to track command usage: %s", exc)

    # ---------------------------------------------------------------------------
    # Utilities
    # ---------------------------------------------------------------------------
    @staticmethod
    def _parse_json_response(raw: str) -> dict:
        """Extract JSON from potentially messy LLM output."""
        # Try direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON block
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Try code fence extraction
        code_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", raw)
        if code_match:
            try:
                return json.loads(code_match.group(1))
            except json.JSONDecodeError:
                pass

        return {}


# Module-level singleton
smart_command_service = SmartCommandService()
