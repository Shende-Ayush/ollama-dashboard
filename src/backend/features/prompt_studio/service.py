"""
Prompt Engineering Studio — Service layer.

Handles prompt CRUD, versioning, testing, and multi-model comparison.
"""
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.features.prompt_studio.models import (
    PromptTemplate,
    PromptTestResult,
    PromptVersion,
)
from backend.features.prompt_studio.schemas import (
    CreatePromptTemplateRequest,
    MultiModelComparisonResponse,
    PromptTemplateResponse,
    PromptTestResultResponse,
    PromptVersionResponse,
    TokenAnalysisResponse,
    UpdatePromptTemplateRequest,
)
from backend.services.ollama_client import OllamaClient
from backend.services.token_counter import token_counter

logger = logging.getLogger(__name__)



class PromptStudioService:
    """Service for managing prompt templates, versioning, and testing."""

    def __init__(self, ollama_client: OllamaClient | None = None) -> None:
        self.client = ollama_client or OllamaClient()

    # -----------------------------------------------------------------------
    # Template CRUD
    # -----------------------------------------------------------------------
    async def create_template(
        self, request: CreatePromptTemplateRequest, session: AsyncSession
    ) -> PromptTemplateResponse:
        """Create a new prompt template with initial version."""
        template = PromptTemplate(
            name=request.name,
            description=request.description,
            template=request.template,
            variables=request.variables,
            tags=request.tags,
            model_name=request.model_name,
            is_public=request.is_public,
        )
        session.add(template)
        await session.flush()

        # Create initial version
        version = PromptVersion(
            template_id=template.id,
            version_number=1,
            template_content=request.template,
            variables=request.variables,
            change_notes="Initial version",
        )
        session.add(version)
        await session.commit()
        await session.refresh(template)

        return self._template_to_response(template, version_count=1)

    async def get_template(
        self, template_id: str, session: AsyncSession
    ) -> PromptTemplateResponse:
        """Get a prompt template by ID."""
        tid = uuid.UUID(template_id)
        result = await session.execute(
            select(PromptTemplate)
            .options(selectinload(PromptTemplate.versions))
            .where(PromptTemplate.id == tid)
        )
        template = result.scalar_one_or_none()
        if not template:
            raise ValueError(f"Template {template_id} not found")
        return self._template_to_response(
            template, version_count=len(template.versions)
        )


    async def list_templates(
        self,
        session: AsyncSession,
        search: Optional[str] = None,
        tag: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """List prompt templates with filtering."""
        stmt = select(PromptTemplate).order_by(PromptTemplate.updated_at.desc())

        if search:
            stmt = stmt.where(
                PromptTemplate.name.ilike(f"%{search}%")
                | PromptTemplate.description.ilike(f"%{search}%")
            )
        if tag:
            stmt = stmt.where(PromptTemplate.tags.contains([tag]))

        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        # Paginate
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(
            stmt.options(selectinload(PromptTemplate.versions))
        )
        templates = result.scalars().all()

        items = [
            self._template_to_response(t, version_count=len(t.versions))
            for t in templates
        ]
        return {
            "items": [i.model_dump() for i in items],
            "page": {
                "pg_no": page,
                "pg_size": page_size,
                "total_records": total,
                "total_pg": (total + page_size - 1) // page_size if total else 0,
            },
        }


    async def update_template(
        self,
        template_id: str,
        request: UpdatePromptTemplateRequest,
        session: AsyncSession,
    ) -> PromptTemplateResponse:
        """Update template and create new version if content changed."""
        tid = uuid.UUID(template_id)
        template = await session.get(PromptTemplate, tid)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        content_changed = False
        if request.name is not None:
            template.name = request.name
        if request.description is not None:
            template.description = request.description
        if request.template is not None and request.template != template.template:
            template.template = request.template
            content_changed = True
        if request.variables is not None:
            template.variables = request.variables
            content_changed = True
        if request.tags is not None:
            template.tags = request.tags
        if request.model_name is not None:
            template.model_name = request.model_name
        if request.is_public is not None:
            template.is_public = request.is_public

        template.updated_at = datetime.now(timezone.utc)

        # Create new version if content changed
        version_count = 1
        if content_changed:
            max_ver = await session.execute(
                select(func.max(PromptVersion.version_number))
                .where(PromptVersion.template_id == tid)
            )
            current_max = max_ver.scalar() or 0
            new_version = PromptVersion(
                template_id=tid,
                version_number=current_max + 1,
                template_content=template.template,
                variables=template.variables,
                change_notes=request.change_notes or "Updated",
            )
            session.add(new_version)
            version_count = current_max + 1

        await session.commit()
        await session.refresh(template)
        return self._template_to_response(template, version_count=version_count)

    async def delete_template(
        self, template_id: str, session: AsyncSession
    ) -> None:
        """Delete a prompt template and all its versions."""
        tid = uuid.UUID(template_id)
        template = await session.get(PromptTemplate, tid)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        await session.delete(template)
        await session.commit()


    # -----------------------------------------------------------------------
    # Version management
    # -----------------------------------------------------------------------
    async def get_versions(
        self, template_id: str, session: AsyncSession
    ) -> list[PromptVersionResponse]:
        """Get all versions of a prompt template."""
        tid = uuid.UUID(template_id)
        result = await session.execute(
            select(PromptVersion)
            .where(PromptVersion.template_id == tid)
            .order_by(PromptVersion.version_number.desc())
        )
        versions = result.scalars().all()
        return [
            PromptVersionResponse(
                id=str(v.id),
                template_id=str(v.template_id),
                version_number=v.version_number,
                template_content=v.template_content,
                variables=v.variables,
                change_notes=v.change_notes,
                created_at=v.created_at,
            )
            for v in versions
        ]

    async def restore_version(
        self, template_id: str, version_number: int, session: AsyncSession
    ) -> PromptTemplateResponse:
        """Restore a template to a specific version."""
        tid = uuid.UUID(template_id)
        result = await session.execute(
            select(PromptVersion).where(
                PromptVersion.template_id == tid,
                PromptVersion.version_number == version_number,
            )
        )
        version = result.scalar_one_or_none()
        if not version:
            raise ValueError(
                f"Version {version_number} not found for template {template_id}"
            )

        template = await session.get(PromptTemplate, tid)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        template.template = version.template_content
        template.variables = version.variables
        template.updated_at = datetime.now(timezone.utc)

        # Create new version for the restore
        max_ver = await session.execute(
            select(func.max(PromptVersion.version_number))
            .where(PromptVersion.template_id == tid)
        )
        new_ver_num = (max_ver.scalar() or 0) + 1
        restore_version = PromptVersion(
            template_id=tid,
            version_number=new_ver_num,
            template_content=version.template_content,
            variables=version.variables,
            change_notes=f"Restored from version {version_number}",
        )
        session.add(restore_version)
        await session.commit()
        await session.refresh(template)
        return self._template_to_response(template, version_count=new_ver_num)


    # -----------------------------------------------------------------------
    # Multi-model comparison
    # -----------------------------------------------------------------------
    async def test_prompt_multi_model(
        self,
        prompt: str,
        models: list[str],
        template_id: Optional[str],
        variables: dict[str, str],
        session: AsyncSession,
    ) -> MultiModelComparisonResponse:
        """Test a prompt against multiple models and compare results."""
        # Resolve variables in prompt
        resolved_prompt = self._resolve_variables(prompt, variables)

        results: list[PromptTestResultResponse] = []
        for model_name in models:
            result = await self._test_single_model(
                resolved_prompt, model_name, template_id, session
            )
            results.append(result)

        # Determine best model (lowest latency with output)
        valid_results = [r for r in results if r.tokens_output > 0]
        best_model = None
        if valid_results:
            best = min(valid_results, key=lambda r: r.latency_ms)
            best_model = best.model_name

        summary = self._generate_comparison_summary(results)

        return MultiModelComparisonResponse(
            prompt=resolved_prompt,
            results=results,
            best_model=best_model,
            summary=summary,
        )

    async def _test_single_model(
        self,
        prompt: str,
        model_name: str,
        template_id: Optional[str],
        session: AsyncSession,
    ) -> PromptTestResultResponse:
        """Test a prompt against a single model."""
        input_tokens = token_counter.count_text(prompt)
        start_time = time.time()
        response_text = ""

        try:
            messages = [{"role": "user", "content": prompt}]
            async for token in self.client.chat_stream(
                model=model_name, messages=messages
            ):
                response_text += token
        except Exception as exc:
            response_text = f"Error: {str(exc)}"

        latency_ms = int((time.time() - start_time) * 1000)
        output_tokens = token_counter.count_text(response_text)

        # Persist result
        test_result = PromptTestResult(
            template_id=uuid.UUID(template_id) if template_id else None,
            prompt_text=prompt,
            model_name=model_name,
            response=response_text,
            tokens_input=input_tokens,
            tokens_output=output_tokens,
            latency_ms=latency_ms,
        )
        session.add(test_result)
        await session.commit()

        return PromptTestResultResponse(
            model_name=model_name,
            response=response_text,
            tokens_input=input_tokens,
            tokens_output=output_tokens,
            latency_ms=latency_ms,
            quality_score=None,
        )


    # -----------------------------------------------------------------------
    # Token analysis
    # -----------------------------------------------------------------------
    def analyze_tokens(self, text: str) -> TokenAnalysisResponse:
        """Analyze token usage breakdown for a prompt."""
        estimated_tokens = token_counter.count_text(text)
        text_length = len(text)

        # Breakdown by content type
        lines = text.split("\n")
        code_lines = sum(
            1 for line in lines
            if line.strip().startswith(("def ", "class ", "import ", "from ", "{", "}", "//", "#"))
        )
        natural_lines = len(lines) - code_lines

        breakdown = {
            "total_characters": text_length,
            "total_lines": len(lines),
            "code_lines": code_lines,
            "natural_language_lines": natural_lines,
            "avg_tokens_per_line": round(estimated_tokens / max(len(lines), 1), 1),
            "whitespace_ratio": round(
                text.count(" ") / max(text_length, 1), 3
            ),
        }

        # Context window usage
        context_sizes = {
            "4K context (4096)": f"{round(estimated_tokens / 4096 * 100, 1)}%",
            "8K context (8192)": f"{round(estimated_tokens / 8192 * 100, 1)}%",
            "32K context (32768)": f"{round(estimated_tokens / 32768 * 100, 1)}%",
            "128K context (131072)": f"{round(estimated_tokens / 131072 * 100, 1)}%",
        }
        breakdown["context_usage"] = context_sizes

        cost_context = (
            f"{estimated_tokens} tokens ≈ {round(estimated_tokens / 4096 * 100, 1)}% "
            f"of a 4K context window"
        )

        return TokenAnalysisResponse(
            text_length=text_length,
            estimated_tokens=estimated_tokens,
            estimated_cost_context=cost_context,
            breakdown=breakdown,
        )

    # -----------------------------------------------------------------------
    # Utilities
    # -----------------------------------------------------------------------
    @staticmethod
    def _resolve_variables(template: str, variables: dict[str, str]) -> str:
        """Replace {variable} placeholders with values."""
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{{key}}}", value)
        return result

    @staticmethod
    def _generate_comparison_summary(results: list[PromptTestResultResponse]) -> str:
        """Generate human-readable summary of model comparison."""
        if not results:
            return "No results to compare."

        valid = [r for r in results if r.tokens_output > 0]
        if not valid:
            return "All models failed to generate output."

        fastest = min(valid, key=lambda r: r.latency_ms)
        most_verbose = max(valid, key=lambda r: r.tokens_output)

        parts = [
            f"Tested {len(results)} model(s).",
            f"Fastest: {fastest.model_name} ({fastest.latency_ms}ms).",
            f"Most detailed: {most_verbose.model_name} ({most_verbose.tokens_output} tokens).",
        ]
        return " ".join(parts)

    @staticmethod
    def _template_to_response(
        template: PromptTemplate, version_count: int = 0
    ) -> PromptTemplateResponse:
        return PromptTemplateResponse(
            id=str(template.id),
            name=template.name,
            description=template.description,
            template=template.template,
            variables=template.variables,
            tags=template.tags,
            model_name=template.model_name,
            is_public=template.is_public,
            usage_count=template.usage_count,
            version_count=version_count,
            created_at=template.created_at,
            updated_at=template.updated_at,
        )


# Module singleton
prompt_studio_service = PromptStudioService()
